/*
 * Node's stand-in for the browser's import map.
 *
 * The panes import `three` and `three/addons/...` as BARE specifiers, which a
 * browser resolves through the <script type="importmap"> in base.html. Node has
 * no import map, so without this hook every test that imports a pane fails on
 * "Cannot find package 'three'" — and the alternative, a node_modules with a
 * real three.js in it, would mean the tests ran against a DIFFERENT copy of
 * three.js from the one the client ships.
 *
 * The mapping below must mirror the one in
 * web/templates/webclient/base.html. A Python test asserts the template
 * declares these specifiers; this is the other end of the same pair.
 *
 * Author: Nick Hobar
 * Creation date: 08/23/2026
 */

import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const JS_ROOT = path.join(HERE, "..", "static", "webclient", "js");

// specifier (or prefix, ending in "/") -> path under the served js tree.
const IMPORTS = {
    "three": "vendor/three/three.module.js",
    "three/addons/": "vendor/three/addons/",
};

export async function resolve(specifier, context, nextResolve) {
    if (Object.prototype.hasOwnProperty.call(IMPORTS, specifier)) {
        return {
            url: pathToFileURL(path.join(JS_ROOT, IMPORTS[specifier])).href,
            shortCircuit: true,
        };
    }
    // Longest prefix first, as the import-map spec requires, so that `three`
    // and `three/addons/` cannot match in the wrong order.
    for (const prefix of Object.keys(IMPORTS).sort((a, b) => b.length - a.length)) {
        if (prefix.endsWith("/") && specifier.startsWith(prefix)) {
            const tail = specifier.slice(prefix.length);
            const target = path.join(JS_ROOT, IMPORTS[prefix], tail);
            return { url: pathToFileURL(target).href, shortCircuit: true };
        }
    }
    return nextResolve(specifier, context);
}
