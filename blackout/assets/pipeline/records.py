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
                 texture_format   = "webp"

             ALIASES. More asset keys that draw the same model. The build
             writes ONE file, and the manifest points every alias at it. Before
             this, the four cured cuts were four byte-identical files, and a
             player with all four downloaded the same model four times.

             [fix] CORRECTS THE EXPORT, and only the export: a sword whose
             blade points at the camera, an eye whose material says alpha 0.
             The build bakes each correction into the served file. A DISPLAY
             choice (the corpse skeleton on its back, the eye lifted to look
             level) is the client's own and stays in ModelRegistry.PRESENTATION.
"""

import os
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


class RecordError(RuntimeError):
    """A model record that is missing, malformed, or contradicts itself."""


@dataclass(frozen=True)
class ModelRecord:
    """
    One served model, read from its record.

    rotate is (x, y, z) in degrees, or None. texture_image is a path relative
    to the source directory, or "". max_texture_edge is 0 when the family
    budget decides it.
    """

    asset_key: str
    family: str
    record_path: str
    source_id: str
    file: str
    aliases: tuple = ()
    node: str = ""
    texture_image: str = ""
    texture_roughness: float = DEFAULT_ROUGHNESS
    rotate: tuple = None
    opaque: bool = False
    filter: str = FILTER_LINEAR
    max_texture_edge: int = 0
    texture_format: str = TEXTURE_FORMAT_PNG

    @property
    def keys(self) -> tuple:
        """Every asset key this model answers to, its own first."""
        return (self.asset_key,) + self.aliases


# ─── Private constant definitions ────────────────────────────────────────────

_TOP_FIELDS: frozenset = frozenset(
    ("source", "file", "aliases", "node", "texture", "fix", "output"))
_TEXTURE_FIELDS: frozenset = frozenset(("image", "roughness"))
_FIX_FIELDS: frozenset = frozenset(("rotate", "opaque", "filter"))
_OUTPUT_FIELDS: frozenset = frozenset(("max_texture_edge", "texture_format"))


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
        Returns {"max_texture_edge", "texture_format"}. An edge of 0 means
        that the family budget decides. Raises RecordError for a bad value.

    Module Globals:
        TEXTURE_FORMATS, TEXTURE_FORMAT_PNG read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    _refuse_unknown(where + " [output]", output, _OUTPUT_FIELDS)
    edge = output.get("max_texture_edge", 0)
    texture_format = output.get("texture_format", TEXTURE_FORMAT_PNG)

    if not isinstance(edge, int) or edge < 0:
        raise RecordError("%s: max_texture_edge must be a whole number"
                          % where)

    if texture_format not in TEXTURE_FORMATS:
        raise RecordError("%s: texture_format must be one of %s"
                          % (where, ", ".join(TEXTURE_FORMATS)))

    return {"max_texture_edge": edge, "texture_format": texture_format}


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

    return ModelRecord(
        asset_key=asset_key, family=family, record_path=record_path,
        source_id=document["source"], file=document["file"], aliases=aliases,
        node=document.get("node", ""), **texture, **fix, **output)


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

    return loaded
