"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/21/2026
Description: Operator script. Renames the combat bonus keys in the live
             database to the spellings with a combat category.

             On 10/21/2026 each bonus key got its combat category as a
             prefix. "stab_attack_bonus" became "melee_stab_attack_bonus",
             and "light_defense_bonus" became
             "projectile_light_defense_bonus". The two strength keys had
             their prefix already.

             A spawn copies the bonus block of a def into the row of the
             object, and no code copies it again. Thus, each item and NPC
             in the database kept the old keys, and combat reads each old
             key as 0. On 10/21/2026 the development database held 248
             items and 58 hostile NPCs with old keys.

             The script changes two Attributes:

             - `combat_stat_bonuses` on each item and each NPC.
             - The `combat_stat_bonuses` block inside `combat_stats` on each
               NPC. `apply_combat_stats` reads this block again when it
               gets no argument.

             It also reports each stored combat style that names an attack
             type with no combat category. Such a style reads no bonus.
             --apply corrects the attack type of a style when the script
             knows the correct spelling (_attack_type_fixes). It does not
             change the other styles.

             IT CHANGES THE LIVE DATABASE. Thus, it REPORTS BY DEFAULT and
             writes only with --apply. Stop the server before you use
             --apply. The server keeps each Attribute in memory, and it
             reads the old value until it starts again. Run deliberately,
             never import.

Usage:
    ../evenv/Scripts/python.exe scripts/migrate_bonus_keys.py [--apply] [--limit N]

    With no flags it changes nothing and prints what it would change.
    --limit caps how many example lines are listed, not how many rows change.
"""

import os
import sys

# The game dir (blackout/), one level up from this file in scripts/. Python
# puts the directory of THIS file on sys.path[0], not the current directory.
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_APPLY_FLAG = "--apply"
_LIMIT_FLAG = "--limit"
_DEFAULT_EXAMPLE_LIMIT = 20

# The Attributes that hold a bonus block.
_BONUS_ATTR = "combat_stat_bonuses"
_NPC_BLOCK_ATTR = "combat_stats"
_STYLES_ATTR = "combat_styles"
_STYLE_ATTACK_TYPE_KEY = "attack_type"

# The spellings before 10/21/2026. Only this script may know them.
_OLD_ATTACK_KEY_TEMPLATE = "{attack_type}_attack_bonus"
_OLD_DEFENSE_KEY_TEMPLATE = "{attack_type}_defense_bonus"

# A stored attack type that a def spelled wrong. The scimitar style chop
# named it until 10/21/2026.
_SCIMITAR_TYPO_ATTACK_TYPE = "sllash"


def _bootstrap_evennia():
    """Bring Django/Evennia up so ObjectDB and the typeclasses are usable."""
    if _GAME_DIR not in sys.path:
        sys.path.insert(0, _GAME_DIR)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")

    import django

    django.setup()

    import evennia

    evennia._init()


def _parse_limit(argv):
    """Read the --limit value out of argv, falling back to the default."""
    limit = _DEFAULT_EXAMPLE_LIMIT

    if _LIMIT_FLAG not in argv:
        return limit

    position = argv.index(_LIMIT_FLAG)
    try:
        limit = int(argv[position + 1])
    except (IndexError, ValueError):
        raise RuntimeError(f"{_LIMIT_FLAG} needs a whole number after it.")

    return limit


def renamed_keys():
    """
    Purpose: Map each old bonus key to its new spelling.

    Entry:
        No conditions. Evennia must already be bootstrapped.

    Exit/Returns:
        Returns a dict of old key -> new key, two rows for each attack type.

    Module Globals:
        _OLD_ATTACK_KEY_TEMPLATE, _OLD_DEFENSE_KEY_TEMPLATE read.

    Methodology:
        The new spellings come from the builders in the combat constants,
        the same builders that the swing uses. Thus, the script cannot
        write a key that combat does not read.

    Notes/References:
        The strength keys are not in the map. Their spelling did not change.

    Author: Nick Hobar
    Creation date: 10/21/2026
    """
    from systems.gameplay.combat import constants as combat_const

    renamed = {}

    for attack_type in combat_const.COMBAT_CATEGORY_BY_ATTACK_TYPE:
        old_attack = _OLD_ATTACK_KEY_TEMPLATE.format(attack_type=attack_type)
        old_defense = _OLD_DEFENSE_KEY_TEMPLATE.format(attack_type=attack_type)
        renamed[old_attack] = combat_const.attack_bonus_key(attack_type)
        renamed[old_defense] = combat_const.defense_bonus_key(attack_type)

    return renamed


def rename_bonuses(bonuses, renamed):
    """
    Purpose: Give a bonus block with each old key renamed.

    Entry:
        bonuses is a plain bonus dict. renamed is the map from renamed_keys.

    Exit/Returns:
        Returns (block, clashes). block is a new dict in the same key order.
        clashes lists each old key that the block held beside its new key.

    Module Globals:
        None

    Methodology:
        A clash keeps the value of the new key and drops the old key. The
        new key is the one that combat reads today.

    Notes/References:
        No row held a clash on 10/21/2026. The report names each one.

    Author: Nick Hobar
    Creation date: 10/21/2026
    """
    block = {}
    clashes = []

    for key, value in bonuses.items():
        new_key = renamed.get(key, key)

        if new_key != key and new_key in bonuses:
            clashes.append(key)
            continue

        block[new_key] = value

    return block, clashes


def _plain(value):
    """Return an Attribute value as plain dicts and lists, or {} if unset."""
    from evennia.utils.dbserialize import deserialize

    plain = deserialize(value)

    return plain or {}


def _holders(attr_key):
    """Return each object that holds an Attribute named attr_key."""
    from evennia.objects.models import ObjectDB

    holders = ObjectDB.objects.filter(db_attributes__db_key=attr_key)

    return list(holders.distinct().order_by("id"))


def plan_changes(renamed):
    """
    Purpose: List each Attribute that holds an old bonus key.

    Entry:
        renamed is the map from renamed_keys.

    Exit/Returns:
        Returns a list of (obj, attr_key, new_value, clashes). new_value is
        the whole value to write back.

    Module Globals:
        _BONUS_ATTR, _NPC_BLOCK_ATTR read.

    Methodology:
        A bonus row is the block itself. An NPC block row holds the bonus
        block under _BONUS_ATTR, beside the other stats of the NPC. A row
        that has no old key is not in the list.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 10/21/2026
    """
    changes = []

    for obj in _holders(_BONUS_ATTR):
        bonuses = _plain(obj.attributes.get(_BONUS_ATTR))
        block, clashes = rename_bonuses(bonuses, renamed)
        if block != bonuses:
            changes.append((obj, _BONUS_ATTR, block, clashes))

    for obj in _holders(_NPC_BLOCK_ATTR):
        stats = _plain(obj.attributes.get(_NPC_BLOCK_ATTR))
        bonuses = stats.get(_BONUS_ATTR) or {}
        block, clashes = rename_bonuses(bonuses, renamed)
        if block != bonuses:
            changes.append((obj, _NPC_BLOCK_ATTR, {**stats, _BONUS_ATTR: block}, clashes))

    return changes


def _attack_type_fixes():
    """Map each known wrong attack type to its correct spelling."""
    from systems.gameplay.combat import constants as combat_const

    return {_SCIMITAR_TYPO_ATTACK_TYPE: combat_const.MELEE_ATTACK_TYPE_SLASH}


def plan_style_fixes(fixes):
    """
    Purpose: List each stored style row that holds a known wrong attack type.

    Entry:
        fixes is the map from _attack_type_fixes.

    Exit/Returns:
        Returns a list of (obj, attr_key, new_value, clashes), the shape of
        plan_changes. clashes is always empty.

    Module Globals:
        _STYLES_ATTR, _STYLE_ATTACK_TYPE_KEY read.

    Methodology:
        new_value is the whole styles table, with each wrong attack type
        corrected. The other styles and the other fields stay as stored.

    Notes/References:
        Three scimitars stored the style chop with "sllash" on 10/21/2026.

    Author: Nick Hobar
    Creation date: 10/21/2026
    """
    changes = []

    for obj in _holders(_STYLES_ATTR):
        styles = _plain(obj.attributes.get(_STYLES_ATTR))
        fixed = {}
        for style_key, style in styles.items():
            attack_type = style.get(_STYLE_ATTACK_TYPE_KEY)
            correct = fixes.get(attack_type, attack_type)
            fixed[style_key] = {**style, _STYLE_ATTACK_TYPE_KEY: correct}
        if fixed != styles:
            changes.append((obj, _STYLES_ATTR, fixed, []))

    return changes


def unknown_attack_types():
    """
    Purpose: List each stored combat style whose attack type has no
             combat category.

    Entry:
        No conditions. Evennia must already be bootstrapped.

    Exit/Returns:
        Returns a list of (obj, style_key, attack_type).

    Module Globals:
        _STYLES_ATTR, _STYLE_ATTACK_TYPE_KEY read.

    Methodology:
        Such a style reads no bonus. plan_style_fixes corrects the ones
        with a known spelling. The report names the others.

    Notes/References:
        Three scimitars stored the style chop with "sllash" on 10/21/2026.
        The def had the typo until that date.

    Author: Nick Hobar
    Creation date: 10/21/2026
    """
    from systems.gameplay.combat import constants as combat_const

    found = []

    for obj in _holders(_STYLES_ATTR):
        styles = _plain(obj.attributes.get(_STYLES_ATTR))
        for style_key, style in styles.items():
            attack_type = style.get(_STYLE_ATTACK_TYPE_KEY)
            if attack_type not in combat_const.COMBAT_CATEGORY_BY_ATTACK_TYPE:
                found.append((obj, style_key, attack_type))

    return found


def describe(changes, limit):
    """Print a census for each Attribute and typeclass, then examples."""
    census = {}

    for obj, attr_key, _new_value, _clashes in changes:
        row = (attr_key, obj.typeclass_path)
        census[row] = census.get(row, 0) + 1

    for (attr_key, path), count in sorted(census.items()):
        print(f"  {count:5d}  {attr_key:<20}  {path}")

    print()

    for obj, attr_key, _new_value, clashes in changes[:limit]:
        clash_text = f" clashes: {clashes}" if clashes else ""
        print(f"    #{obj.id} '{obj.key}' {attr_key}{clash_text}")

    remaining = len(changes) - limit
    if remaining > 0:
        print(f"    ... and {remaining} more")


def apply_changes(changes):
    """Write each planned value back. Returns the number of rows written."""
    for obj, attr_key, new_value, _clashes in changes:
        obj.attributes.add(attr_key, new_value)

    return len(changes)


def _report_unknown_attack_types(fixes, limit):
    """Print each stored style whose attack type has no combat category."""
    found = unknown_attack_types()

    if not found:
        return

    print(f"{len(found)} stored style(s) name an attack type with no combat")
    print(f"category. They read no bonus. {_APPLY_FLAG} corrects a known spelling.")

    for obj, style_key, attack_type in found[:limit]:
        correct = fixes.get(attack_type, "no fix known")
        print(f"    #{obj.id} '{obj.key}' style {style_key!r}: "
              f"{attack_type!r} -> {correct!r}")

    print()


def _plan_all(renamed, fixes):
    """Return the key renames and the style fixes as one list."""
    changes = plan_changes(renamed)
    changes.extend(plan_style_fixes(fixes))

    return changes


def _run(write, limit):
    """Report the old keys and wrong styles, and fix them when asked to."""
    renamed = renamed_keys()
    fixes = _attack_type_fixes()
    print("=== Old combat bonus keys and wrong attack types in the database ===")

    changes = _plan_all(renamed, fixes)
    _report_unknown_attack_types(fixes, limit)

    if not changes:
        print("  none -- nothing to change.")
        return

    print(f"{len(changes)} Attribute row(s) need a change.")
    print()
    describe(changes, limit)
    print()

    if not write:
        print(f"Reported only. Stop the server, then run again with {_APPLY_FLAG}.")
        return

    written = apply_changes(changes)
    print(f"Changed {written} Attribute row(s).")

    left = _plan_all(renamed, fixes)
    if left:
        print(f"WARNING: {len(left)} row(s) still need a change.")


def main(argv):
    """Entry point. Bootstraps Evennia, then reports or renames the keys."""
    write = _APPLY_FLAG in argv

    _bootstrap_evennia()

    try:
        limit = _parse_limit(argv)
        _run(write, limit)
    except Exception as exc:
        print(f"Aborting: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
