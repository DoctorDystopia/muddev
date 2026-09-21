// The Node half of one model build. assets/pipeline/build.py runs it; it is
// not a command a person types.
//
//     node build_model.mjs build <job.json>
//     node build_model.mjs validate <model.glb>
//
// `build` reads one job (written by build.py from a recipe), applies the
// recipe to a glTF or GLB file, optimizes the result, and writes one .glb. It
// prints one JSON line on stdout: what it wrote and what the file holds.
//
// `validate` runs the Khronos glTF Validator over one .glb and prints its
// issue counts as one JSON line.
//
// WHY NODE. glTF Transform is the standard library for this work and it is a
// Node library. The old pipeline did the same work in 4,000 lines of Python
// that wrote buffers and accessors by hand. Python still owns every DECISION
// (which file, which fix, which budget); this file only carries them out.
//
// Author: Nick Hobar
// Creation date: 09/18/2026

import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS, EXTTextureWebP } from '@gltf-transform/extensions';
import {
    dedup, getBounds, metalRough, prune, unpartition, weld,
} from '@gltf-transform/functions';
import sharp from 'sharp';
import validator from 'gltf-validator';

// ─── Constants ───────────────────────────────────────────────────────────────

// glTF sampler vocabulary, from the spec.
const FILTER_NEAREST = 9728;
const ALPHA_OPAQUE = 'OPAQUE';
const FULL_ALPHA = 1.0;
const METALLIC_NONE = 0.0;
const DEGREES_TO_RADIANS = Math.PI / 180.0;

// Written into asset.generator. A fixed string, so the same inputs give the
// same bytes on every machine.
const GENERATOR = 'Blackout model pipeline (assets/pipeline)';

// The name of the node that carries a baked rotation. Godot builds it as an
// ordinary Node3D, so the rotation lands in ModelLoader.bounds_of like any
// other node transform.
const FIX_NODE_NAME = 'blackout_fix';

const TRIANGLES_MODE = 4;

// The highest zlib level, with adaptive row filters: the smallest LOSSLESS
// PNG. Not sharp's `effort`, which quantizes to a 256-colour palette.
const PNG_OPTIONS = { compressionLevel: 9, adaptiveFiltering: true, palette: false };

// Lossy WebP for a record that asks for it: photo textures only.
const WEBP_OPTIONS = { quality: 90, effort: 6 };

// Image suffix -> MIME type, for an atlas that a record attaches.
const IMAGE_MIME = { '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp' };
const VERTICES_PER_TRIANGLE = 3;

// ─── Recipe steps ────────────────────────────────────────────────────────────

/**
 * Keep one named node of a multi-model file (a tileset), and nothing else.
 *
 * The node keeps its own transform and loses its parents' transforms, the
 * same rule split_tileset.py followed. Everything the other nodes used is
 * left for prune() to remove.
 */
function keepOnlyNode(document, nodeName) {
    const root = document.getRoot();
    const wanted = root.listNodes().find((node) => node.getName() === nodeName);

    if (!wanted) {
        const names = root.listNodes().map((node) => node.getName()).sort();
        throw new Error(`no node named '${nodeName}'. The file holds: ${names.join(', ')}`);
    }

    for (const scene of root.listScenes()) {
        for (const child of scene.listChildren()) {
            scene.removeChild(child);
        }
    }

    const parent = wanted.getParentNode();

    if (parent) {
        parent.removeChild(wanted);
    }

    root.listScenes()[0].addChild(wanted);
}

/**
 * Replace every material with one material that samples one image.
 *
 * For a download whose meshes carry UVs but whose look lives outside the
 * file: a Godot Asset Library pack (the look is in a .tres) or an FBX that
 * names no image. The material is opaque on purpose. Pack atlases often keep
 * roughness in the alpha channel, and read as coverage it draws the model
 * partly see-through.
 */
async function attachTexture(document, imagePath, roughness) {
    const image = await readFile(imagePath);
    const mime = IMAGE_MIME[path.extname(imagePath).toLowerCase()];

    if (!mime) {
        throw new Error(`cannot attach ${imagePath}: not a PNG, JPEG or WebP image`);
    }

    const texture = document.createTexture(path.basename(imagePath))
        .setImage(image)
        .setMimeType(mime)
        .setURI(path.basename(imagePath));
    const material = document.createMaterial('blackout_atlas')
        .setBaseColorTexture(texture)
        .setMetallicFactor(METALLIC_NONE)
        .setRoughnessFactor(roughness)
        .setAlphaMode(ALPHA_OPAQUE);

    for (const mesh of document.getRoot().listMeshes()) {
        for (const primitive of mesh.listPrimitives()) {
            if (!primitive.getAttribute('TEXCOORD_0')) {
                throw new Error(`mesh '${mesh.getName()}' has a primitive with no UVs, so no texture can map onto it`);
            }

            primitive.setMaterial(material);
        }
    }
}

/**
 * Build a unit quaternion from Euler angles in degrees.
 *
 * YXZ order, which is the order Godot's Node3D.rotation uses. With one
 * non-zero axis, which is every fix so far, the order does not matter.
 */
function quaternionFromDegrees([xDeg, yDeg, zDeg]) {
    const halfX = (xDeg * DEGREES_TO_RADIANS) / 2;
    const halfY = (yDeg * DEGREES_TO_RADIANS) / 2;
    const halfZ = (zDeg * DEGREES_TO_RADIANS) / 2;
    const [sx, cx] = [Math.sin(halfX), Math.cos(halfX)];
    const [sy, cy] = [Math.sin(halfY), Math.cos(halfY)];
    const [sz, cz] = [Math.sin(halfZ), Math.cos(halfZ)];

    // q = qY * qX * qZ
    return [
        cy * sx * cz + sy * cx * sz,
        sy * cx * cz - cy * sx * sz,
        cy * cx * sz - sy * sx * cz,
        cy * cx * cz + sy * sx * sz,
    ];
}

/**
 * Put every root node under one new node that carries the rotation.
 *
 * A parent node, not a change to the vertices, so a skinned model keeps
 * working: its joints are nodes under the same parent and turn with it.
 */
function bakeRotation(document, degrees) {
    const scene = document.getRoot().listScenes()[0];
    const fix = document.createNode(FIX_NODE_NAME)
        .setRotation(quaternionFromDegrees(degrees));

    for (const child of scene.listChildren()) {
        scene.removeChild(child);
        fix.addChild(child);
    }

    scene.addChild(fix);
}

/** Make every material solid. See ModelRegistry's history of floating_eye. */
function forceOpaque(document) {
    for (const material of document.getRoot().listMaterials()) {
        const [r, g, b] = material.getBaseColorFactor();

        material.setAlphaMode(ALPHA_OPAQUE);
        material.setBaseColorFactor([r, g, b, FULL_ALPHA]);
    }
}

/**
 * Sample every texture with NEAREST and no mipmaps.
 *
 * For palette and pixel art. A smooth filter blends one swatch into the
 * next, and a mip level blends a whole chart into mud.
 */
function forceNearest(document) {
    for (const material of document.getRoot().listMaterials()) {
        const infos = [
            material.getBaseColorTextureInfo(),
            material.getEmissiveTextureInfo(),
            material.getNormalTextureInfo(),
            material.getOcclusionTextureInfo(),
            material.getMetallicRoughnessTextureInfo(),
        ];

        for (const info of infos.filter(Boolean)) {
            info.setMagFilter(FILTER_NEAREST);
            info.setMinFilter(FILTER_NEAREST);
        }
    }
}

/** Apply the recipe's [fix] table, in a fixed order. */
function applyFix(document, fix) {
    if (fix.rotate) {
        bakeRotation(document, fix.rotate);
    }

    if (fix.opaque) {
        forceOpaque(document);
    }

    if (fix.filter === 'nearest') {
        forceNearest(document);
    }
}

/**
 * Resize every texture to the budget edge and encode it in the job's format.
 *
 * Done here with sharp, not with glTF Transform's textureCompress, because
 * that function's PNG `effort` quantizes to a palette and dithers: a silent
 * loss of colour. A texture that NEAREST samples is resized with the nearest
 * kernel, so a pixel-art edge stays sharp. Aspect ratio is kept, and a
 * texture is never enlarged.
 */
async function encodeTextures(document, job) {
    const edge = job.max_texture_edge;
    const kernel = job.fix.filter === 'nearest' ? 'nearest' : 'lanczos3';
    const webp = job.texture_format === 'webp';

    for (const texture of document.getRoot().listTextures()) {
        const pipeline = sharp(Buffer.from(texture.getImage()))
            .resize({ width: edge, height: edge, fit: 'inside', withoutEnlargement: true, kernel });
        const encoded = webp ? pipeline.webp(WEBP_OPTIONS) : pipeline.png(PNG_OPTIONS);

        texture.setImage(new Uint8Array(await encoded.toBuffer()));
        texture.setMimeType(webp ? 'image/webp' : 'image/png');
    }

    if (webp) {
        document.createExtension(EXTTextureWebP).setRequired(true);
    }
}

/**
 * Remove every extension that Godot cannot read at runtime.
 *
 * Python owns the list (glb.GODOT_RUNTIME_EXTENSIONS) and passes it in the
 * job. An optional extension that Godot does not read is dead weight, and
 * Godot draws the file the same without it: KHR_materials_specular is the
 * usual one, from Blender. A REQUIRED one would stop the file from loading,
 * so that is an error, never a silent removal.
 */
function dropUnreadableExtensions(document, allowed) {
    for (const extension of document.getRoot().listExtensionsUsed()) {
        const name = extension.extensionName;

        if (allowed.includes(name)) {
            continue;
        }

        if (extension.isRequired()) {
            throw new Error(`the file requires ${name}, which Godot cannot read at runtime`);
        }

        extension.dispose();
    }
}

// ─── Report ──────────────────────────────────────────────────────────────────

/** Count what one finished document holds, for the budgets and the log. */
function describe(document) {
    const root = document.getRoot();
    let triangles = 0;
    let vertices = 0;

    for (const mesh of root.listMeshes()) {
        for (const primitive of mesh.listPrimitives()) {
            const position = primitive.getAttribute('POSITION');
            const indices = primitive.getIndices();
            const count = indices ? indices.getCount() : position.getCount();

            vertices += position.getCount();

            if (primitive.getMode() === TRIANGLES_MODE) {
                triangles += Math.floor(count / VERTICES_PER_TRIANGLE);
            }
        }
    }

    const textures = root.listTextures().map((texture) => ({
        name: texture.getName() || texture.getURI(),
        size: texture.getSize(),
        mime: texture.getMimeType(),
        bytes: texture.getImage() ? texture.getImage().byteLength : 0,
    }));
    const bounds = getBounds(root.listScenes()[0]);

    return {
        triangles,
        vertices,
        textures,
        materials: root.listMaterials().length,
        skins: root.listSkins().length,
        animations: root.listAnimations().length,
        bounds,
    };
}

// ─── Commands ────────────────────────────────────────────────────────────────

async function build(jobPath) {
    const job = JSON.parse(await readFile(jobPath, 'utf8'));
    const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
    const document = await io.read(job.input);

    // FIRST, before any fix. metalRough converts
    // KHR_materials_pbrSpecularGlossiness, which Sketchfab still exports, and
    // it writes the base colour from the old diffuse factor. Run after the
    // opaque fix, it put the eye's alpha 0 back.
    await document.transform(metalRough());

    if (job.node) {
        keepOnlyNode(document, job.node);
    }

    if (job.texture) {
        await attachTexture(document, job.texture.image, job.texture.roughness);
    }

    applyFix(document, job.fix || {});

    await document.transform(
        prune({ keepAttributes: false, keepLeaves: false }),
        dedup(),
        weld(),
        unpartition(),
    );
    await encodeTextures(document, job);

    dropUnreadableExtensions(document, job.allowed_extensions);

    // Buffers and images go INSIDE the .glb. One file, one request.
    for (const texture of document.getRoot().listTextures()) {
        texture.setURI('');
    }

    document.getRoot().getAsset().generator = GENERATOR;

    await io.write(job.output, document);

    const report = describe(document);

    process.stdout.write(`${JSON.stringify({ output: job.output, ...report })}\n`);
}

async function validate(glbPath) {
    const bytes = new Uint8Array(await readFile(glbPath));
    const result = await validator.validateBytes(bytes, {
        uri: path.basename(glbPath),
        maxIssues: 50,
        // External resources never appear: a served .glb is self-contained.
        externalResourceFunction: () => Promise.reject(new Error('external resource')),
    });
    const issues = result.issues;
    const errors = issues.messages
        .filter((message) => message.severity === 0)
        .map((message) => `${message.code}: ${message.message} (${message.pointer || ''})`);

    process.stdout.write(`${JSON.stringify({
        errors: issues.numErrors,
        warnings: issues.numWarnings,
        messages: errors,
    })}\n`);
}

const [command, argument] = process.argv.slice(2);
const commands = { build, validate };

if (!commands[command] || !argument) {
    process.stderr.write('usage: node build_model.mjs build <job.json> | validate <model.glb>\n');
    process.exit(2);
}

commands[command](argument).catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.exit(1);
});
