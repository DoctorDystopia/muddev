"""
Phase W0 spike of DESIGN-0014. Make a rigged glTF with one small clip, from
the CC0 Quaternius base character that is in the repository.

Usage: python make_retarget_source.py <source dir> <output dir>

The output directory gets two copies of the same model: plain.gltf and
mapped.gltf. The editor imports the first as it is, and the second with a
bone map. The copies carry no texture, so the import is fast.
"""

import json
import math
import os
import shutil
import struct
import sys

SWINGS = {"upperarm_l": 0.8, "thigh_l": 0.6, "calf_l": -0.5, "upperarm_r": -0.4}
TIMES = (0.0, 0.5, 1.0)
FLOAT = 5126
SCALAR_BYTES = 4
QUAT_BYTES = 16


def multiply(a, b):
    """The quaternion product a * b, each as (x, y, z, w)."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b

    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def main(source_dir, out_dir):
    with open(os.path.join(source_dir, "scene.gltf"), encoding="utf-8") as handle:
        gltf = json.load(handle)

    os.makedirs(out_dir, exist_ok=True)
    binary = gltf["buffers"][0]["uri"]
    shutil.copy(os.path.join(source_dir, binary), os.path.join(out_dir, binary))

    for key in ("images", "textures", "samplers"):
        gltf.pop(key, None)

    gltf["materials"] = [{"name": material.get("name", "plain")}
                         for material in gltf.get("materials", [])]

    names = {node.get("name"): index for index, node in enumerate(gltf["nodes"])}
    blob = struct.pack("<3f", *TIMES)
    views = [{"buffer": 1, "byteOffset": 0, "byteLength": len(blob)}]
    accessors = [{"bufferView": len(gltf["bufferViews"]), "componentType": FLOAT,
                  "count": len(TIMES), "type": "SCALAR",
                  "min": [TIMES[0]], "max": [TIMES[-1]]}]
    time_accessor = len(gltf["accessors"])
    samplers = []
    channels = []

    for bone, angle in SWINGS.items():
        rest = tuple(gltf["nodes"][names[bone]].get("rotation", [0, 0, 0, 1]))
        turn = (math.sin(angle / 2.0), 0.0, 0.0, math.cos(angle / 2.0))
        keys = rest + multiply(rest, turn) + rest

        views.append({"buffer": 1, "byteOffset": len(blob),
                      "byteLength": QUAT_BYTES * len(TIMES)})
        blob += struct.pack("<12f", *keys)
        accessors.append({"bufferView": len(gltf["bufferViews"]) + len(views) - 1,
                          "componentType": FLOAT, "count": len(TIMES), "type": "VEC4"})
        samplers.append({"input": time_accessor,
                         "output": time_accessor + len(accessors) - 1,
                         "interpolation": "LINEAR"})
        channels.append({"sampler": len(samplers) - 1,
                         "target": {"node": names[bone], "path": "rotation"}})

    gltf["buffers"].append({"uri": "clip.bin", "byteLength": len(blob)})
    gltf["bufferViews"].extend(views)
    gltf["accessors"].extend(accessors)
    gltf["animations"] = [{"name": "Swing", "samplers": samplers, "channels": channels}]

    with open(os.path.join(out_dir, "clip.bin"), "wb") as handle:
        handle.write(blob)

    for name in ("plain.gltf", "mapped.gltf"):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as handle:
            json.dump(gltf, handle)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
