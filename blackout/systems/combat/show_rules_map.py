"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/22/2026
Description: Structural snapshot of the pluggable action pipeline -- which
             rules definitions exist, what each one replaces, and which items
             and NPCs carry them.

introspect.py already answers this for one LIVE combatant. This answers it for
the CONTENT: no server, no spawned objects, just ItemDefs and NpcDefs, so the
question "what does the game currently contain" can be asked without standing
a world up.

It also produces the caveat list the analytic snapshots need. show_max_hit,
show_hit_chance and show_dps_matrix all model the OSRS formulas, and a rules
definition that owns `roll_damage` or `resolve` is not described by those
formulas at all. Every item named in the final section is a row those
snapshots report fiction for, and show_damage_distribution measures properly.

Run it:
    ../evenv/Scripts/python.exe systems/combat/show_rules_map.py
"""

from __future__ import annotations

import sys
from pathlib import Path


# The game directory has to be importable before `systems.*` resolves.
_GAME_DIR: str = str(Path(__file__).resolve().parents[2])

if _GAME_DIR not in sys.path:
    sys.path.insert(0, _GAME_DIR)

from systems.combat import _snapshot_env as env


# Public constant definitions

# Seams whose owner replaces the damage number outright. A definition owning
# any of these makes the OSRS max-hit formula stop describing the weapon, which
# is what puts its carrier on the unmodellable list.
DAMAGE_OWNING_SEAMS: tuple = ("roll_damage", "resolve", "max_hit")


# Private constant definitions

# Column widths for the printed tables.
_KEY_WIDTH: int = 22
_NAME_WIDTH: int = 24
_PRIORITY_WIDTH: int = 10
_SEAM_WIDTH: int = 26
_CARRIER_WIDTH: int = 26

# Shown for a rule that overrides no seam, or a seam nothing claims.
_NOTHING_LABEL: str = "nothing"
_DEFAULT_LABEL: str = "default (OSRS)"

# Shown when no content carries a registered rule.
_UNUSED_LABEL: str = "(carried by nothing)"

# The attribute the registry stamps on each definition naming what it replaces.
_SEAM_ATTRIBUTE: str = "_overridden_seams"

# Modifier contribution is not a priority contest -- every contributor's
# modifiers run -- so it is excluded from any table that names a single winner.
_MODIFIER_SEAM: str = "contribute_modifiers"


# Private helper routines

def _registered_rules() -> list:
    """Every registered rules definition, ordered the way the pipeline is."""
    from systems.combat.rules.registry import RULES_REGISTRY

    ordered = sorted(RULES_REGISTRY.values(),
                     key=lambda rules: (rules.priority, rules.key))

    return ordered


def _priority_label(priority: int) -> str:
    """Name the priority tier a number belongs to, falling back to the number."""
    combat_const = env.combat_constants()
    tiers = {
        combat_const.RULES_PRIORITY_DEFAULT: "default",
        combat_const.RULES_PRIORITY_MODIFIER: "modifier",
        combat_const.RULES_PRIORITY_WEAPON: "weapon",
        combat_const.RULES_PRIORITY_OVERRIDE: "override",
    }

    return tiers.get(priority, str(priority))


def _seams_of(rules) -> tuple:
    """The seam names one definition replaces, sorted, modifiers excluded."""
    claimed = getattr(rules, _SEAM_ATTRIBUTE, frozenset())
    named = [seam for seam in claimed if seam != _MODIFIER_SEAM]

    return tuple(sorted(named))


def _contributes_modifiers(rules) -> bool:
    """True when a definition writes into modifier channels."""
    claimed = getattr(rules, _SEAM_ATTRIBUTE, frozenset())

    return _MODIFIER_SEAM in claimed


def _carriers() -> dict:
    """Map each rules key to the ItemDefs and NpcDefs that declare it."""
    from world.item_database import ITEM_DB
    from world.npc_database import NPC_DB

    carriers = {}

    for item_def in ITEM_DB.values():
        for rule_key in item_def.combat_rules:
            carriers.setdefault(rule_key, []).append(item_def.name)

    for npc_def in NPC_DB.values():
        for rule_key in npc_def.combat_rules:
            carriers.setdefault(rule_key, []).append(npc_def.name)

    return carriers


def _seam_winners(rule_keys: list) -> dict:
    """Resolve which definition owns each seam for one combat_rules list.

    Uses the pipeline's own winner resolution rather than reimplementing the
    contest, so this table cannot disagree with what actually happens when the
    item is equipped.
    """
    from systems.combat.rules.pipeline import _resolve_winners
    from systems.combat.rules.rule_defs.base_rules import (
        ACTION_SEAM_NAMES,
        DEFAULT_ACTION_RULES,
    )

    contributors = env.rules_for(rule_keys)
    resolved = _resolve_winners(contributors)
    winners = {}

    for seam_name in ACTION_SEAM_NAMES:
        if seam_name == _MODIFIER_SEAM:
            continue

        owner = resolved.owner(seam_name)

        if owner is DEFAULT_ACTION_RULES:
            winners[seam_name] = _DEFAULT_LABEL
            continue

        winners[seam_name] = owner.key

    return winners


def _unmodellable_profiles() -> list:
    """Every weapon whose rules replace a number the OSRS formulas produce."""
    profiles = env.weapon_profiles()
    flagged = []

    for profile in profiles.values():
        if not profile.combat_rules:
            continue

        owned = set()

        for rule_key in profile.combat_rules:
            contributors = env.rules_for([rule_key])

            for rules in contributors:
                owned.update(_seams_of(rules))

        overlap = owned.intersection(DAMAGE_OWNING_SEAMS)

        if overlap:
            flagged.append({
                "name": profile.name,
                "rules": list(profile.combat_rules),
                "seams": tuple(sorted(overlap)),
            })

    return flagged


# Private helper routines -- printing

def _print_registry(rules_list: list, carriers: dict) -> None:
    """Print every registered definition, its tier, and what it replaces."""
    print("REGISTERED ACTION RULES -- ordered as the pipeline applies them")
    print(f"  {'key':<{_KEY_WIDTH}} {'name':<{_NAME_WIDTH}} "
          f"{'priority':<{_PRIORITY_WIDTH}} overrides")

    for rules in rules_list:
        seams = _seams_of(rules)
        seam_label = ", ".join(seams) or _NOTHING_LABEL

        if _contributes_modifiers(rules):
            seam_label = f"{seam_label} (+ modifiers)"

        tier = _priority_label(rules.priority)
        print(f"  {rules.key:<{_KEY_WIDTH}} {rules.name:<{_NAME_WIDTH}} "
              f"{tier:<{_PRIORITY_WIDTH}} {seam_label}")

    print()
    print("CARRIERS -- which content declares each rule")

    for rules in rules_list:
        holders = carriers.get(rules.key, [])
        holder_label = ", ".join(holders) or _UNUSED_LABEL
        print(f"  {rules.key:<{_KEY_WIDTH}} {holder_label}")


def _print_seam_ownership(carriers: dict) -> None:
    """Print the full seam table for every rule that content actually carries."""
    print()
    print("SEAM OWNERSHIP -- per rule, as if equipped alone")

    for rule_key in sorted(carriers):
        winners = _seam_winners([rule_key])
        replaced = {
            seam: owner for seam, owner in winners.items()
            if owner != _DEFAULT_LABEL
        }

        if not replaced:
            print(f"  {rule_key:<{_KEY_WIDTH}} replaces no seam "
                  f"(modifier contributor only)")
            continue

        print(f"  {rule_key}")

        for seam_name, owner in sorted(replaced.items()):
            print(f"      {seam_name:<{_SEAM_WIDTH}} {owner}")


def _print_unmodellable(flagged: list) -> None:
    """Print the weapons the analytic snapshots cannot describe."""
    print()
    print("ANALYTIC-MODEL CAVEAT")

    if not flagged:
        print("  No weapon replaces a damage seam. Every row in show_max_hit and")
        print("  show_dps_matrix is described by the OSRS formulas.")
        return

    print("  These weapons own a seam that produces the damage number, so the")
    print("  OSRS formulas do not describe them. show_max_hit and")
    print("  show_dps_matrix report the FORMULA result for these rows, which is")
    print("  not what the weapon does. show_damage_distribution measures them")
    print("  through the real pipeline instead.")
    print()
    print(f"  {'weapon':<{_CARRIER_WIDTH}} {'seams owned':<{_SEAM_WIDTH}} rules")

    for entry in flagged:
        seam_label = ", ".join(entry["seams"])
        rule_label = ", ".join(entry["rules"])
        print(f"  {entry['name']:<{_CARRIER_WIDTH}} {seam_label:<{_SEAM_WIDTH}} "
              f"{rule_label}")


# Public routines

def main() -> None:
    """
    Purpose: Print the rules registry, its carriers, the per-rule seam table,
    and the analytic-model caveat list.

    Entry:
        No conditions. Bootstraps the game environment itself.

    Exit/Returns:
        Returns nothing. Prints to stdout. This snapshot has no figure --
        the content is a set of names and ownership relations, and a diagram
        of eleven rows would carry less than the table does.

    Module Globals:
        DAMAGE_OWNING_SEAMS read.

    Methodology:
        Seam ownership is resolved through the pipeline's own _resolve_winners
        rather than by reading class definitions, so the report cannot
        disagree with what happens at resolution time.

    Notes/References:
        Modifier CHANNELS are not shown. A channel's contents depend on the
        defender and the rng, so they exist only during an action; an empty
        bag printed here would read as "this amulet does nothing".

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    env.bootstrap()

    rules_list = _registered_rules()
    carriers = _carriers()

    _print_registry(rules_list, carriers)
    _print_seam_ownership(carriers)

    flagged = _unmodellable_profiles()
    _print_unmodellable(flagged)


if __name__ == "__main__":
    main()
