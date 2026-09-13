"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/12/2026
Description: Tests for assets/glb_to_gltf.py, the step that gives an untextured
             .glb download a material before pack_model.py packs it.

             Beside test_model_budgets.py for the same reason: assets/ is
             import-safe by design and holds no tests root of its own, and the
             packed models are what the statefeed's asset keys resolve to.

             Plain unittest.TestCase throughout. Nothing here touches a
             database, so nothing here pays for one.
"""

import json
import os
import struct
import tempfile
import unittest

# assets/ is import-safe by design -- it touches no database and boots no
# Evennia. Unlike blackout/scripts/, which CLAUDE.md marks import-unsafe.
from assets import glb_to_gltf
from assets import pack_model


# ─── Private helper routines ─────────────────────────────────────────────────

_POSITIONS = (0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
_UVS = (0.0, 0.0, 1.0, 0.0, 0.0, 1.0)
_VERTEX_COUNT = 3
_FLOAT_FORMAT = "<%df"
_GLB_HEADER_FORMAT = "<III"
_CHUNK_HEADER_FORMAT = "<II"
_ALIGNMENT = 4


def _padded(payload, pad_byte):
    """Grow payload to the 4-byte boundary the GLB container requires."""
    shortfall = (-len(payload)) % _ALIGNMENT

    return payload + pad_byte * shortfall


def _glb_bytes(with_uvs=True, with_material=False):
    """
    Build the smallest .glb shaped like the food pack's: one triangle, one
    buffer, no material. The BIN chunk is deliberately left one byte-length
    short of a 4-byte boundary before padding, so the cut back to byteLength
    is exercised.
    """
    positions = struct.pack(_FLOAT_FORMAT % len(_POSITIONS), *_POSITIONS)
    uvs = struct.pack(_FLOAT_FORMAT % len(_UVS), *_UVS)
    payload = positions + (uvs if with_uvs else b"") + b"\x07"
    attributes = {"POSITION": 0}
    views = [{"buffer": 0, "byteOffset": 0, "byteLength": len(positions)}]
    accessors = [{"bufferView": 0, "componentType": 5126,
                  "count": _VERTEX_COUNT, "type": "VEC3",
                  "min": [0.0, 0.0, 0.0], "max": [1.0, 1.0, 0.0]}]

    if with_uvs:
        attributes["TEXCOORD_0"] = 1
        views.append({"buffer": 0, "byteOffset": len(positions),
                      "byteLength": len(uvs)})
        accessors.append({"bufferView": 1, "componentType": 5126,
                          "count": _VERTEX_COUNT, "type": "VEC2"})

    document = {
        "asset": {"version": "2.0", "generator": "test"},
        "nodes": [{"mesh": 0, "name": "Tri"}],
        "meshes": [{"name": "Tri", "primitives": [{"attributes": attributes}]}],
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(payload)}],
    }

    if with_material:
        document["materials"] = [{"name": "already"}]

    encoded = _padded(json.dumps(document).encode("utf-8"), b" ")
    binary = _padded(payload, b"\x00")
    total = 12 + 8 + len(encoded) + 8 + len(binary)
    parts = [
        struct.pack(_GLB_HEADER_FORMAT, 0x46546C67, 2, total),
        struct.pack(_CHUNK_HEADER_FORMAT, len(encoded), 0x4E4F534A), encoded,
        struct.pack(_CHUNK_HEADER_FORMAT, len(binary), 0x004E4942), binary,
    ]

    return b"".join(parts), payload


class GlbToGltfTests(unittest.TestCase):
    """The converter against a synthetic .glb, in a scratch directory."""

    def setUp(self):
        self._scratch = tempfile.TemporaryDirectory()
        self.root = self._scratch.name
        self.textures = os.path.join(self.root, "Textures")
        os.makedirs(self.textures)
        self.texture = os.path.join(self.textures, "T_atlas.png")

        with open(self.texture, "wb") as handle:
            handle.write(b"not decoded by the converter")

        self.dest = os.path.join(self.root, "tri")

    def tearDown(self):
        self._scratch.cleanup()

    def _write_glb(self, **shape):
        data, payload = _glb_bytes(**shape)
        path = os.path.join(self.root, "tri.glb")

        with open(path, "wb") as handle:
            handle.write(data)

        return path, payload

    def _converted_document(self, glb_path):
        glb_to_gltf.convert(glb_path, self.dest, self.texture)

        with open(os.path.join(self.dest, "scene.gltf"),
                  encoding="utf-8") as handle:
            return json.load(handle)

    def test_the_buffer_is_split_out_byte_for_byte(self):
        glb_path, payload = self._write_glb()
        document = self._converted_document(glb_path)

        with open(os.path.join(self.dest, "scene.bin"), "rb") as handle:
            written = handle.read()

        self.assertEqual(written, payload)
        self.assertEqual(document["buffers"][0]["uri"], "scene.bin")
        self.assertEqual(document["buffers"][0]["byteLength"], len(payload))

    def test_the_material_is_opaque_and_on_every_primitive(self):
        """The atlas alpha is roughness, never coverage -- see the module."""
        glb_path, _ = self._write_glb()
        document = self._converted_document(glb_path)
        material = document["materials"][0]

        self.assertEqual(material["alphaMode"], "OPAQUE")
        self.assertEqual(
            material["pbrMetallicRoughness"]["baseColorTexture"]["index"], 0)

        for mesh in document["meshes"]:
            for primitive in mesh["primitives"]:
                with self.subTest(mesh=mesh["name"]):
                    self.assertEqual(primitive["material"], 0)

    def test_the_image_is_referenced_with_a_forward_slashed_relative_uri(self):
        glb_path, _ = self._write_glb()
        document = self._converted_document(glb_path)
        uri = document["images"][0]["uri"]

        self.assertEqual(uri, "../Textures/T_atlas.png")
        self.assertTrue(os.path.isfile(os.path.join(self.dest, uri)))

    def test_the_download_is_never_written_to(self):
        glb_path, _ = self._write_glb()

        with open(glb_path, "rb") as handle:
            before = handle.read()

        self._converted_document(glb_path)

        with open(glb_path, "rb") as handle:
            self.assertEqual(handle.read(), before)

    def test_a_glb_that_already_has_a_material_is_refused(self):
        glb_path, _ = self._write_glb(with_material=True)

        with self.assertRaises(glb_to_gltf.GlbError) as caught:
            glb_to_gltf.convert(glb_path, self.dest, self.texture)

        self.assertIn("materials", str(caught.exception))
        self.assertFalse(os.path.exists(self.dest))

    def test_a_primitive_with_no_uvs_is_refused(self):
        glb_path, _ = self._write_glb(with_uvs=False)

        with self.assertRaises(glb_to_gltf.GlbError) as caught:
            glb_to_gltf.convert(glb_path, self.dest, self.texture)

        self.assertIn("texcoord_0", str(caught.exception).lower())

    def test_a_file_that_is_not_a_glb_is_refused(self):
        path = os.path.join(self.root, "not.glb")

        with open(path, "wb") as handle:
            handle.write(b"PK\x03\x04 plainly a zip file")

        with self.assertRaises(glb_to_gltf.GlbError) as caught:
            glb_to_gltf.read_glb(path)

        self.assertIn("magic", str(caught.exception))

    def test_a_missing_texture_is_refused_before_anything_is_written(self):
        glb_path, _ = self._write_glb()
        missing = os.path.join(self.textures, "absent.png")

        with self.assertRaises(glb_to_gltf.GlbError):
            glb_to_gltf.convert(glb_path, self.dest, missing)

        self.assertFalse(os.path.exists(self.dest))


class ConvertedManifestSourceTests(unittest.TestCase):
    """Every source this converter produced, as the manifest names them."""

    def test_every_converted_source_is_opaque_and_its_image_exists(self):
        """
        Derived from the manifest rather than listed: a converted source is one
        whose generator names this tool, so a model converted tomorrow is
        covered with no edit here.
        """
        seen = set()

        for source_dir, asset_key in pack_model.load_manifest():
            gltf_path = os.path.join(source_dir, "scene.gltf")

            if source_dir in seen or not os.path.isfile(gltf_path):
                continue

            seen.add(source_dir)

            with open(gltf_path, encoding="utf-8") as handle:
                document = json.load(handle)

            generator = document.get("asset", {}).get("generator", "")

            if "glb_to_gltf.py" not in generator:
                continue

            with self.subTest(asset_key=asset_key):
                for material in document.get("materials", []):
                    self.assertEqual(material.get("alphaMode"), "OPAQUE")

                for image in document.get("images", []):
                    self.assertTrue(
                        os.path.isfile(os.path.join(source_dir, image["uri"])),
                        "%s references %s, which is not there"
                        % (asset_key, image["uri"]))


if __name__ == "__main__":
    unittest.main()
