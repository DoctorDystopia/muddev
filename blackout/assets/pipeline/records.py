"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: Model records. One served model, one file:
             assets/models/<family>/<asset_key>.toml.

             A MODEL RECORD says which file of which source to build, and what
             to correct on the way. The file name IS the asset key and the
             directory IS the family, so nothing restates either one. A new
             model is one new file, the rule that CLAUDE.md sets for a new
             skill, recipe, item or NPC.

                 source  = "godot_kyle_fuji_food"     # a directory in sources/
                 file    = "Models/meat_haunch.glb"   # a file in that source
                 aliases = ["mutant_raider_cured_filet"]
                 node    = "center_h"                 # optional

                 [texture]                            # optional
                 image     = "Textures/T_protein_atlas_diffuse.png"
                 roughness = 0.7

                 [fix]                                # optional
                 rotate = [0, 90, 0]                  # degrees, baked in
                 opaque = true
                 filter = "nearest"

                 [output]                             # optional
                 max_texture_edge = 256
                 max_triangles    = 9000
                 texture_format   = "webp"
                 animations       = false
                 color_roles      = true

             ALIASES. More asset keys that draw the same model. The build
             writes ONE file, and the manifest points every alias at it. Before
             this, the four cured cuts were four byte-identical files, and a
             player with all four downloaded the same model four times.

             VARIANTS (10/16/2026). A record with `variant_of = "rusty_pole"`
             is a second look of that model: a bent pole beside the straight
             one. The build writes it as its own file, under its own key.
             Then it writes `variants.json` beside the manifest: the base
             key to the keys of its variants. A chunk object picks one by
             key, or lets the client pick by a hash of its tile. Nick chose
             one record for each variant on 10/16/2026, over a file list in
             the base record, so a variant is a model like any other: its
             own source, its own fix, its own budget. The base must be a
             record of its own (not an alias), and not a variant itself.
             `load_all` refuses both.

             [fix] CORRECTS THE EXPORT, and only the export: a sword whose
             blade points at the camera, an eye whose material says alpha 0.
             The build bakes each correction into the served file. A DISPLAY
             choice (the corpse skeleton on its back, the eye lifted to look
             level) is the client's own and stays in ModelRegistry.PRESENTATION.

             COLOR ROLES. In a figure model, the name of each material is a
             color role of a worn look (DESIGN-0014). The build joins two
             materials that differ in the name only. `color_roles = true`
             keeps each name.

             MAX TRIANGLES (10/20/2026). A download with more triangles than
             its family budget. The build simplifies the mesh to at most this
             count, with meshoptimizer. 0, the default, keeps the mesh as it
             is. The family budget still checks the result. Nick chose a
             simplify step over a higher budget for the foundry furnace.
"""

import os
import re
import tomllib
from dataclasses import dataclass

from assets.pipeline import paths


# ─── Public constant definitions ─────────────────────────────────────────────

FILTER_LINEAR: str = "linear"
FILTER_NEAREST: str = "nearest"
FILTERS: tuple = (FILTER_LINEAR, FILTER_NEAREST)

TEXTURE_FORMAT_PNG: str = "png"
TEXTURE_FORMAT_WEBP: str = "webp"
TEXTURE_FORMATS: tuple = (TEXTURE_FORMAT_PNG, TEXTURE_FORMAT_WEBP)

# The roughness of an attached atlas when the record does not say. The
# value of the Kyle Fuji pack's own .tres files.
DEFAULT_ROUGHNESS: float = 0.7

AXES: int = 3

# An asset key, a family and a source id are each a file name and a TOML
# value. Thus they use plain letters only, with a letter first.
KEY_PATTERN: str = r"^[a-z][a-z0-9_]*$"


class RecordError(RuntimeError):
    """A model record that is missing, malformed, or contradicts itself."""


@dataclass(frozen=True)
class ModelRecord:
    """
    One served model, read from its record.

    The field `rotate` holds (x, y, z) in degrees, or None. The field
    `texture_image` is a path relative to the source directory, or "".

    A `max_texture_edge` of 0 lets the family budget decide the edge. A
    `max_triangles` of 0 keeps the mesh as it is. The field `animations` is
    False when the served file must carry no animation. The field
    `color_roles` is True when the build must keep the name of each material.
    The field `variant_of` is the asset key of the base model, or "".
    """

    asset_key: str
    family: str
    record_path: str
    source_id: str
    file: str
    aliases: tuple = ()
    variant_of: str = ""
    node: str = ""
    texture_image: str = ""
    texture_roughness: float = DEFAULT_ROUGHNESS
    rotate: tuple = None
    opaque: bool = False
    filter: str = FILTER_LINEAR
    max_texture_edge: int = 0
    max_triangles: int = 0
    texture_format: str = TEXTURE_FORMAT_PNG
    animations: bool = True
    color_roles: bool = False

    @property
    def keys(self) -> tuple:
        """Every asset key this model answers to, its own first."""
        return (self.asset_key,) + self.aliases


# ─── Private constant definitions ────────────────────────────────────────────

_TOP_FIELDS: frozenset = frozenset(
    ("source", "file", "aliases", "variant_of", "node", "texture", "fix",
     "output"))
_TEXTURE_FIELDS: frozenset = frozenset(("image", "roughness"))
_FIX_FIELDS: frozenset = frozenset(("rotate", "opaque", "filter"))
_OUTPUT_FIELDS: frozenset = frozenset(
    ("max_texture_edge", "max_triangles", "texture_format", "animations",
     "color_roles"))


# ─── Private helper routines ─────────────────────────────────────────────────

def _refuse_unknown(where: str, table: dict, known: frozenset) -> None:
    """
    Purpose: Refuse a table that holds a field this module does not read.

    Entry:
        where names the record and table, for the message.

    Exit/Returns:
        Returns None. Raises RecordError that names the unknown fields.

    Module Globals:
        None.

    Methodology:
        A typo such as "rotation" for "rotate" must fail. Ignored, it builds a
        model with no correction and no error.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    unknown = sorted(set(table) - known)

    if unknown:
        raise RecordError("%s: unknown field(s) %s"
                          % (where, ", ".join(unknown)))


def _read_fix(where: str, fix: dict) -> dict:
    """
    Purpose: Read and check the [fix] table of one record.

    Entry:
        fix is the parsed table, possibly empty.

    Exit/Returns:
        Returns {"rotate", "opaque", "filter"} with defaults filled in.
        Raises RecordError for a bad value.

    Module Globals:
        FILTERS, FILTER_LINEAR, AXES read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    _refuse_unknown(where + " [fix]", fix, _FIX_FIELDS)
    rotate = fix.get("rotate")
    chosen_filter = fix.get("filter", FILTER_LINEAR)

    if rotate is not None:
        numeric = all(isinstance(value, (int, float)) for value in rotate)

        if len(rotate) != AXES or not numeric:
            raise RecordError("%s: rotate must be three numbers in degrees"
                              % where)

        rotate = tuple(float(value) for value in rotate)

    if chosen_filter not in FILTERS:
        raise RecordError("%s: filter must be one of %s"
                          % (where, ", ".join(FILTERS)))

    opaque = bool(fix.get("opaque", False))

    return {"rotate": rotate, "opaque": opaque, "filter": chosen_filter}


def _read_output(where: str, output: dict) -> dict:
    """
    Purpose: Read and check the [output] table of one record.

    Entry:
        output is the parsed table, possibly empty.

    Exit/Returns:
        Returns {"max_texture_edge", "max_triangles", "texture_format",
        "animations", "color_roles"}. An edge of 0 means that the family
        budget decides. A triangle count of 0 means no simplify. Raises
        RecordError for a bad value.

    Module Globals:
        TEXTURE_FORMATS, TEXTURE_FORMAT_PNG read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    _refuse_unknown(where + " [output]", output, _OUTPUT_FIELDS)
    edge = output.get("max_texture_edge", 0)
    max_triangles = output.get("max_triangles", 0)
    texture_format = output.get("texture_format", TEXTURE_FORMAT_PNG)
    animations = output.get("animations", True)
    color_roles = output.get("color_roles", False)

    if not isinstance(edge, int) or edge < 0:
        raise RecordError("%s: max_texture_edge must be a whole number"
                          % where)

    # bool is an int in Python, so `max_triangles = true` must fail here.
    whole = isinstance(max_triangles, int) and not isinstance(max_triangles,
                                                               bool)

    if not whole or max_triangles < 0:
        raise RecordError("%s: max_triangles must be a whole number" % where)

    if texture_format not in TEXTURE_FORMATS:
        raise RecordError("%s: texture_format must be one of %s"
                          % (where, ", ".join(TEXTURE_FORMATS)))

    if not isinstance(animations, bool):
        raise RecordError("%s: animations must be true or false" % where)

    if not isinstance(color_roles, bool):
        raise RecordError("%s: color_roles must be true or false" % where)

    return {"max_texture_edge": edge, "max_triangles": max_triangles,
            "texture_format": texture_format, "animations": animations,
            "color_roles": color_roles}


def _read_texture(where: str, texture: dict) -> dict:
    """
    Purpose: Read and check the [texture] table of one record.

    Entry:
        texture is the parsed table, possibly empty.

    Exit/Returns:
        Returns {"texture_image", "texture_roughness"}. Raises RecordError
        when the table exists with no image, or roughness is out of range.

    Module Globals:
        DEFAULT_ROUGHNESS read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    _refuse_unknown(where + " [texture]", texture, _TEXTURE_FIELDS)
    image = texture.get("image", "")
    roughness = float(texture.get("roughness", DEFAULT_ROUGHNESS))

    if texture and not image:
        raise RecordError("%s: [texture] needs an image" % where)

    if not 0.0 <= roughness <= 1.0:
        raise RecordError("%s: roughness must be from 0 to 1" % where)

    return {"texture_image": image, "texture_roughness": roughness}


# ─── Public routines ─────────────────────────────────────────────────────────

def is_key(text: str) -> bool:
    """
    Purpose: Tell whether one text can be an asset key, a family or a
    source id.

    Entry:
        text is any text, empty included.

    Exit/Returns:
        Returns True when text matches KEY_PATTERN.

    Module Globals:
        KEY_PATTERN read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    match = re.match(KEY_PATTERN, text)

    return match is not None


def load_record(record_path: str) -> ModelRecord:
    """
    Purpose: Read and check one model record.

    Entry:
        record_path names models/<family>/<asset_key>.toml.

    Exit/Returns:
        Returns the ModelRecord. Raises RecordError when the file is not
        valid TOML, lacks `source` or `file`, or holds a bad or unknown field.

    Module Globals:
        paths.MODEL_RECORD_SUFFIX read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    family = os.path.basename(os.path.dirname(record_path))
    filename = os.path.basename(record_path)
    asset_key = filename[:-len(paths.MODEL_RECORD_SUFFIX)]
    where = "models/%s/%s" % (family, filename)

    try:
        with open(record_path, "rb") as handle:
            document = tomllib.load(handle)
    except tomllib.TOMLDecodeError as problem:
        raise RecordError("%s is not valid TOML: %s" % (where, problem))

    _refuse_unknown(where, document, _TOP_FIELDS)

    if not document.get("source") or not document.get("file"):
        raise RecordError("%s needs both `source` and `file`" % where)

    fix = _read_fix(where, document.get("fix", {}))
    output = _read_output(where, document.get("output", {}))
    texture = _read_texture(where, document.get("texture", {}))
    aliases = tuple(document.get("aliases", ()))
    variant_of = document.get("variant_of", "")

    if not isinstance(variant_of, str):
        raise RecordError("%s: variant_of must be an asset key" % where)

    if variant_of == asset_key:
        raise RecordError("%s: a model cannot be a variant of itself" % where)

    return ModelRecord(
        asset_key=asset_key, family=family, record_path=record_path,
        source_id=document["source"], file=document["file"], aliases=aliases,
        variant_of=variant_of, node=document.get("node", ""), **texture,
        **fix, **output)


def record_paths() -> list:
    """
    Purpose: Name every model record on disk.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the sorted paths of models/<family>/*.toml. Returns an empty
        list when MODELS_DIR does not exist.

    Module Globals:
        paths.MODELS_DIR, paths.MODEL_RECORD_SUFFIX read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    found = []

    if not os.path.isdir(paths.MODELS_DIR):
        return found

    families = sorted(os.listdir(paths.MODELS_DIR))

    for family in families:
        folder = os.path.join(paths.MODELS_DIR, family)

        if not os.path.isdir(folder):
            continue

        names = sorted(os.listdir(folder))
        found.extend(os.path.join(folder, name) for name in names
                     if name.endswith(paths.MODEL_RECORD_SUFFIX))

    return found


def load_all() -> list:
    """
    Purpose: Read every model record, and refuse two records for one key.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the ModelRecords, sorted by record path. Raises RecordError
        for the first bad record, or when two records claim one asset key
        (as a file name or as an alias).

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    loaded = []
    owners = {}

    for record_path in record_paths():
        record = load_record(record_path)

        for key in record.keys:
            if key in owners:
                raise RecordError("asset key '%s' is claimed by %s and %s"
                                  % (key, owners[key], record.record_path))

            owners[key] = record.record_path

        loaded.append(record)

    _check_variants(loaded)

    return loaded


def _check_variants(loaded: list) -> None:
    """
    Refuse a variant whose base is not a record of its own, or is a variant
    itself. An alias is no base, because the client groups the variants
    under the key of the file.
    """
    by_key = {record.asset_key: record for record in loaded}

    for record in loaded:
        if not record.variant_of:
            continue

        base = by_key.get(record.variant_of)

        if base is None:
            raise RecordError("%s: variant_of names '%s', which no record has "
                              "as its own key" % (record.record_path,
                                                  record.variant_of))

        if base.variant_of:
            raise RecordError("%s: variant_of names '%s', which is a variant "
                              "itself" % (record.record_path,
                                          record.variant_of))


def variants_of(all_records: list) -> dict:
    """
    Purpose: Group the variants of each base model.

    Entry:
        all_records holds loaded ModelRecords.

    Exit/Returns:
        Returns {base asset key: [variant asset keys, sorted]}, with a row
        only for a base that has a variant. The caller keeps the served
        records only, so no row names a file that a client cannot fetch.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/16/2026
    """
    grouped = {}

    for record in all_records:
        if record.variant_of:
            grouped.setdefault(record.variant_of, []).append(record.asset_key)

    return {base: sorted(keys) for base, keys in sorted(grouped.items())}
