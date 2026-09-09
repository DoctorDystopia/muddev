"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/08/2026
Description: Repair for a `db.skills` Attribute that Evennia could not
             unpickle, and the legacy-shape normalisation that goes with it.

             This module exists because of a data-loss incident on
             09/08/2026. Three separate faults had to line up, and the
             module defends against all three:

             1. A historical `init_all_skills` iterated the registry with
                `.items()` rather than over its keys, so every character
                created in that window carries eight JUNK entries keyed by
                the tuple `(skill_key, SkillClass)` alongside the eight real
                entries keyed by the plain string. The junk entries are
                harmless to read -- but they pin a CLASS REFERENCE into the
                pickled Attribute, and a class reference is a module path.

             2. Commit 50854e3 moved `systems/progression/` to
                `systems/gameplay/progression/`. Every pinned class
                reference above became unresolvable, so the whole Attribute
                stopped unpickling.

             3. Evennia's PickledObjectField.from_db_value SWALLOWS that
                failure -- see its own comment about not being sure the
                value is "a definite pickle" -- and hands back the raw
                base64 STRING. So `character.db.skills` silently stopped
                being a dict and started being a str, and every reader died
                on `TypeError: 'str' object does not support item
                assignment` rather than on anything naming the real cause.

             The value handed back is not damaged, only unreadable by the
             current module layout: the real levels are still in it. That is
             the whole point of this module -- a `db.skills` that fails to
             load is RECOVERABLE, and must never be overwritten with a fresh
             empty dict on the assumption that it is garbage.

Notes/References:
    See docs/2026-09-08-DATA-0001-skill-attribute-loss.md for the incident
    write-up and the forensic timeline.
"""


import base64
import io
import pickle

from evennia.utils import logger


# ─── Module-path aliases ────────────────────────────────────────────────────
# The 09/08/2026 reorganisation split `systems/` into three sub-domains. A
# pickle written before it names the OLD path, so unpickling one today needs
# a translation table rather than a code change per skill.
#
# Data rather than branches, per the repo convention: a future move is a row
# added here, not an edit to _LegacyUnpickler. Longest prefix wins, so a more
# specific entry can override a broader one.
_MODULE_ALIASES = {
    "systems.progression": "systems.gameplay.progression",
    "systems.combat": "systems.gameplay.combat",
    "systems.crafting": "systems.gameplay.crafting",
    "systems.quests": "systems.gameplay.quests",
    "systems.banking": "systems.gameplay.banking",
    "systems.shop": "systems.gameplay.shop",
    "systems.loot": "systems.gameplay.loot",
    "systems.spawning": "systems.gameplay.spawning",
    "systems.ai": "systems.gameplay.ai",
    "systems.statefeed": "systems.interface.statefeed",
    "systems.summary": "systems.interface.summary",
    "systems.menus": "systems.interface.menus",
    "systems.ui": "systems.interface.ui",
    "systems.tick": "systems.core.tick",
    "systems.stat_tracker": "systems.core.stat_tracker",
}

# The keys a well-formed per-skill entry carries.
_LEVEL_KEY = "level"
_XP_KEY = "xp"

# Where an unreadable value is parked when even the rescue unpickler cannot
# make sense of it. Kept on the character so the bytes survive for a later
# hand-repair instead of being dropped on the floor.
QUARANTINE_ATTR = "skills_unreadable_backup"


class _GhostClass:
    """
    Purpose: Stand in for a class the rescue unpickler could not import.

    Entry:
        module and name are the two halves of the missing reference.

    Exit/Returns:
        An instance usable as a dict key -- hashable and comparable.

    Module Globals:
        None.

    Methodology:
        A legacy blob's junk keys are `(skill_key, SkillClass)` tuples, and
        the tuple is only ever discarded. The class therefore does not need
        to be the REAL class; it needs to unpickle without raising and to be
        hashable, so the surrounding dict can be reconstructed and the string
        half of the tuple read off. Resolving the real class would drag the
        whole skill package into a repair path that must work even when that
        package is what moved.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/08/2026
    """

    def __init__(self, module: str, name: str) -> None:
        self.module = module
        self.name = name


    def __repr__(self) -> str:
        return f"<unresolved {self.module}.{self.name}>"


    def __hash__(self) -> int:
        identity = (self.module, self.name)
        return hash(identity)


    def __eq__(self, other: object) -> bool:
        is_ghost = isinstance(other, _GhostClass)

        if not is_ghost:
            return NotImplemented

        return (self.module, self.name) == (other.module, other.name)


def _resolve_module(module: str) -> str:
    """
    Purpose: Translate a pre-reorganisation module path to its current one.

    Entry:
        module is a dotted module path as recorded inside a pickle.

    Exit/Returns:
        Returns the aliased path when a prefix matches, else `module`
        unchanged.

    Module Globals:
        _MODULE_ALIASES read.

    Methodology:
        Longest matching prefix wins, so a specific row can override a
        broader one no matter what order the table is written in. A prefix
        matches only on a dot boundary -- `systems.combat` must not rewrite a
        hypothetical `systems.combatant`.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/08/2026
    """
    best_prefix = None

    for old_prefix in _MODULE_ALIASES:
        exact = module == old_prefix
        nested = module.startswith(f"{old_prefix}.")
        matches = exact or nested

        if not matches:
            continue

        if best_prefix is not None and len(old_prefix) <= len(best_prefix):
            continue

        best_prefix = old_prefix

    if best_prefix is None:
        return module

    new_prefix = _MODULE_ALIASES[best_prefix]
    remainder = module[len(best_prefix):]

    return f"{new_prefix}{remainder}"


class _LegacyUnpickler(pickle.Unpickler):
    """
    Purpose: Unpickle a skills blob whose class references may no longer
    resolve, without ever executing game code.

    Entry:
        Constructed over a BytesIO of the decoded pickle payload.

    Exit/Returns:
        load() returns the reconstructed object.

    Module Globals:
        None.

    Methodology:
        find_class tries the aliased path first, then the path as written,
        and falls back to a _GhostClass rather than raising. The fallback is
        the point: a blob must stay recoverable even when the class it names
        was DELETED rather than moved, because the levels live in the dict
        around it, not in the class.

    Notes/References:
        Only ever pointed at bytes already stored in this game's own
        database by this game's own code.

    Author: Nick Hobar
    Creation date: 09/08/2026
    """

    def find_class(self, module: str, name: str) -> object:
        aliased = _resolve_module(module)
        candidates = [aliased, module]

        for candidate in candidates:
            try:
                return super().find_class(candidate, name)
            except Exception:
                continue

        return _GhostClass(module, name)


def _decode_payload(raw: str) -> bytes:
    """
    Purpose: Turn the base64 text Evennia handed back into pickle bytes.

    Entry:
        raw is the string returned by a failed PickledObjectField decode.

    Exit/Returns:
        Returns the decoded bytes, or None when `raw` is not base64 at all.

    Module Globals:
        None.

    Methodology:
        Evennia stores an Attribute as base64 of the pickle. When the decode
        step raises, from_db_value returns that base64 TEXT untouched, so
        undoing exactly one base64 layer is what recovers the payload.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/08/2026
    """
    try:
        return base64.b64decode(raw)
    except Exception:
        return None


def _normalise_entry(entry: object) -> dict:
    """
    Purpose: Coerce one recovered per-skill record into {level, xp} ints.

    Entry:
        entry is whatever sat under a skill key in the recovered blob.

    Exit/Returns:
        Returns a dict with int `level` and `xp`, or None when `entry` is not
        shaped like a skill record at all.

    Module Globals:
        _LEVEL_KEY read.
        _XP_KEY read.

    Methodology:
        Anything that is not a mapping is rejected outright rather than
        guessed at. A missing or non-integer half defaults to zero, so one
        damaged field costs that field and not the whole skill.

    Notes/References:
        Deliberately does NOT clamp xp against the level's threshold. That is
        a game rule, and normalising here would hide a legacy character whose
        banked xp exceeds its next level -- see repair_skills_dict.

    Author: Nick Hobar
    Creation date: 09/08/2026
    """
    is_mapping = isinstance(entry, dict)

    if not is_mapping:
        return None

    level_value = entry.get(_LEVEL_KEY, 0)
    xp_value = entry.get(_XP_KEY, 0)

    try:
        level_int = int(level_value)
    except Exception:
        level_int = 0

    try:
        xp_int = int(xp_value)
    except Exception:
        xp_int = 0

    return {_LEVEL_KEY: level_int, _XP_KEY: xp_int}


def normalise_skills_dict(recovered: dict) -> dict:
    """
    Purpose: Flatten a recovered skills mapping to plain `str -> {level, xp}`.

    Entry:
        recovered is the mapping produced by decode_legacy_blob, which may
        mix string keys with the legacy `(skill_key, SkillClass)` tuples.

    Exit/Returns:
        Returns a fresh dict keyed by skill-key strings only.

    Module Globals:
        _LEVEL_KEY read.

    Methodology:
        Both key shapes reduce to the same skill key, so the two can collide.
        The tie is broken on the HIGHER level, which is what makes the merge
        safe in the direction that matters: the junk tuple entries were
        written at level 0 and the real entries carry the player's progress,
        so a max never lets junk overwrite progress -- whatever order the
        dict happens to iterate in.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/08/2026
    """
    cleaned = {}

    for key, entry in recovered.items():
        if isinstance(key, tuple) and len(key) > 0:
            skill_key = key[0]
        else:
            skill_key = key

        is_usable_key = isinstance(skill_key, str)

        if not is_usable_key:
            continue

        record = _normalise_entry(entry)

        if record is None:
            continue

        existing = cleaned.get(skill_key)

        if existing is not None and existing[_LEVEL_KEY] >= record[_LEVEL_KEY]:
            continue

        cleaned[skill_key] = record

    return cleaned


def decode_legacy_blob(raw: str) -> dict:
    """
    Purpose: Recover a skills dict from the raw string Evennia returns when
    it cannot unpickle the Attribute.

    Entry:
        raw is that string. Anything else returns None.

    Exit/Returns:
        Returns a plain `str -> {level, xp}` dict on success, None on any
        failure. Never raises.

    Module Globals:
        None.

    Methodology:
        base64 -> rescue-unpickle -> normalise. Returns None rather than an
        empty dict when the payload cannot be read, because the CALLER must
        be able to tell "recovered nothing" apart from "recovered a character
        who genuinely has no skills" -- the first has to be quarantined and
        the second does not.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/08/2026
    """
    is_text = isinstance(raw, str)

    if not is_text:
        return None

    payload = _decode_payload(raw)

    if payload is None:
        return None

    try:
        recovered = _LegacyUnpickler(io.BytesIO(payload)).load()
    except Exception as exc:
        logger.log_err(f"skills recovery: could not unpickle blob: {exc!r}")
        return None

    is_mapping = isinstance(recovered, dict)

    if not is_mapping:
        return None

    return normalise_skills_dict(recovered)


def repair_skills_attribute(obj: object) -> bool:
    """
    Purpose: Repair one character's unreadable `db.skills` in place.

    Entry:
        obj is an Evennia object whose db.skills is NOT a Mapping. Note the
        caller must test Mapping and not dict -- a healthy saved Attribute
        comes back as _SaverDict, which is a MutableMapping and not a dict.

    Exit/Returns:
        Returns True when the Attribute was rebuilt from recovered data,
        False when nothing could be recovered. In the False case the original
        value is parked on QUARANTINE_ATTR before the caller resets it.

    Module Globals:
        QUARANTINE_ATTR read.

    Methodology:
        The order is the whole safety property. Recovery is attempted FIRST
        and the original is preserved on failure, so no path through this
        function can turn a recoverable Attribute into an empty one. The
        09/08/2026 loss happened precisely because a guard reset the
        Attribute before anyone asked whether it could be read.

        Quarantine writes the raw value under a different key rather than
        deleting it. It is stored with `.attributes.add` so a raw string is
        stored AS a string and does not go back through the failing decode.

    Notes/References:
        Called from SkillHandler.__init__, the one chokepoint every reader of
        db.skills passes through.

    Author: Nick Hobar
    Creation date: 09/08/2026
    """
    raw = obj.db.skills
    recovered = decode_legacy_blob(raw)

    if recovered:
        obj.db.skills = recovered
        logger.log_info(
            f"skills recovery: rebuilt db.skills for {obj} "
            f"({len(recovered)} skills recovered)"
        )
        return True

    obj.attributes.add(QUARANTINE_ATTR, raw)
    logger.log_err(
        f"skills recovery: could not recover db.skills for {obj}; "
        f"raw value quarantined on db.{QUARANTINE_ATTR}"
    )

    return False


# ─── Stored-Attribute encoding ──────────────────────────────────────────────
# What an Attribute actually looks like in the typeclasses_attribute row, as
# opposed to what it looks like in Python.
#
# This lives HERE rather than in the operator script that needs it, for the
# reason CLAUDE.md already gives about clientexport.py: blackout/scripts/ is
# import-unsafe, so a test cannot reach a fact that is written there. The
# restore script got this encoding wrong on 09/08/2026 -- it wrote a bare
# pickle into a column holding base64 -- and no test could have caught it
# while the knowledge lived in scripts/.


def encode_attribute_value(data: object) -> str:
    """
    Purpose: Render a value exactly as it is stored in an Attribute row.

    Entry:
        data is any value Evennia can store.

    Exit/Returns:
        Returns the base64 TEXT belonging in typeclasses_attribute.db_value.

    Module Globals:
        None.

    Methodology:
        TWO layers, and getting either wrong silently corrupts the row.
        Attribute.value writes `to_pickle(value)` into the field, and
        PickledObjectField base64-encodes that on the way to the column. So
        the column holds `dbsafe_encode(to_pickle(value))`.

        Both halves are imported from Evennia rather than reimplemented, so a
        change to its storage format reaches every caller here.

        The result is coerced to a plain str: dbsafe_encode returns a
        PickledObject, and a driver that binds it as anything but TEXT
        produces a row nothing can read back.

    Notes/References:
        decode_legacy_blob is the inverse, and is deliberately the more
        forgiving of the two -- it also reads rows this function never wrote.

    Author: Nick Hobar
    Creation date: 09/08/2026
    """
    from evennia.utils.dbserialize import to_pickle
    from evennia.utils.picklefield import dbsafe_encode

    packed = to_pickle(data)
    encoded = dbsafe_encode(packed)

    return str(encoded)
