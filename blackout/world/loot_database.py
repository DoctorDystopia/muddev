"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/14/2026
Description: LootEntry / LootTableDef dataclasses and the LOOT_DB registry,
             the third sibling of ItemDef / ITEM_DB and NpcDef / NPC_DB.

             A table's roll() is deliberately PURE -- it returns
             [(item_key, quantity), ...] and touches no database, spawns
             nothing, and imports no Evennia object layer. That is what makes
             the entire probability surface testable with a seeded
             random.Random and zero game objects. Turning those pairs into
             real items is systems/loot/drops.py's job, because only the
             delivery side needs to know whether an item stacks.

             Weights are raw integers rather than floats so an OSRS drop table
             transfers verbatim at its native /128 denominators, the same way
             the monster stat blocks in world/npc_defs/hostile.py do.
"""

import random as _random_module
from dataclasses import dataclass, field
from typing import Optional


# ─── Private constant definitions ────────────────────────────────────────────

# Lowest value rng.randint may return for a weighted pick. The weighted range
# is 1-based so that a cumulative cursor comparison (`roll_value <= cursor`)
# selects the correct entry without an off-by-one at the first entry.
_MIN_ROLL_VALUE = 1

# A total weight at or below this means the pool cannot be rolled at all.
_EMPTY_WEIGHT = 0

# The single value out of chance_denominator that makes a tertiary drop fire.
_TERTIARY_HIT_VALUE = 1


@dataclass
class LootEntry:
    """One droppable line on a loot table.

    item_key must be a key into ITEM_DB; nothing here validates that, because
    an unresolvable key must not be able to take the server down at import
    time. validate_loot_tables() is the loud check, run from the test suite,
    and systems/loot/drops.py logs-and-skips at runtime -- the same
    fail-loud-in-tests / fail-soft-at-runtime split the combat_rules lists
    use (world/item_database.py, ItemDef.combat_rules).

    min_quantity / max_quantity are INCLUSIVE bounds on the stack size. Equal
    values mean a fixed quantity and skip the roll entirely. A max below the
    min is a data error caught by validate_loot_tables().

    weight is this entry's share of ONE main-table roll, relative to every
    other entry in the same pool plus the table's nothing_weight. It is
    meaningless for `always` and `tertiary` entries, which do not compete in a
    weighted pool -- it is left on the shared dataclass rather than split into
    three near-identical types.
    """

    item_key: str
    min_quantity: int = 1
    max_quantity: int = 1
    weight: int = 1


@dataclass
class TertiaryDrop:
    """An independent 1-in-N roll that ignores the main table entirely.

    OSRS's tertiary slot: a rare that can land alongside a main-table drop
    rather than instead of one. Each TertiaryDrop is rolled separately, so a
    table may award several in one kill.
    """

    entry: LootEntry
    chance_denominator: int


@dataclass
class LootTableDef:
    """Data-driven definition of what one NPC (or container) drops.

    Three independent stages, resolved in order by roll():

        always   -- every entry drops on every kill. The 100% slot.
        main     -- `rolls` weighted picks from this pool. nothing_weight
                    sits in the same pool as the "no drop" share, so a table
                    where most kills yield nothing needs no sentinel entry.
        tertiary -- independent 1/N rolls, each able to fire alongside the
                    main-table result.

    key is the registry key. Two NpcDefs may name the same table, which is how
    a shared rare table works without duplicating data.
    """

    key: str
    always: list = field(default_factory=list)
    main: list = field(default_factory=list)
    nothing_weight: int = 0
    rolls: int = 1
    tertiary: list = field(default_factory=list)


    def total_main_weight(self) -> int:
        """
        Purpose: Sum the weighted pool, including the no-drop share.

        Entry:
            No conditions.

        Exit/Returns:
            Returns the integer denominator one main-table roll is taken
            against. _EMPTY_WEIGHT when the pool is empty and nothing_weight
            is zero.

        Module Globals:
            None.

        Methodology:
            nothing_weight participates in the same sum as the entries, so it
            occupies the tail of the roll range and needs no sentinel entry
            in `main`.

        Notes/References:
            Public rather than private because the validator and the tests
            both assert against it.

        Author: Nick Hobar
        Creation date: 08/14/2026
        """
        total = self.nothing_weight

        for entry in self.main:
            total += entry.weight

        return total


    def roll(self, rng: Optional[_random_module.Random] = None) -> list:
        """
        Purpose: Resolve one kill's worth of drops from this table.

        Entry:
            rng - optional random.Random instance for deterministic tests. If
                  None, uses the module-level random, matching the injection
                  pattern in systems/combat/combat_calc.py roll_damage.

        Exit/Returns:
            Returns a list of (item_key, quantity) tuples, possibly empty.
            Duplicate item_keys are NOT merged -- see Notes.

        Module Globals:
            _random_module read when rng is None.

        Methodology:
            1. Every `always` entry contributes one pair.
            2. `rolls` weighted picks from `main`; a pick that lands in the
               nothing_weight tail contributes nothing.
            3. Each `tertiary` drop is rolled independently.

        Notes/References:
            Same-key pairs are deliberately left unmerged. Merging would have
            to happen before delivery knows whether the item stacks, and
            collapsing two non-stackable drops into quantity=2 would silently
            yield ONE object -- ItemDef._get_attrs only stamps `quantity` when
            `stackable` is set. drops.py expands per-pair instead.

        Author: Nick Hobar
        Creation date: 08/14/2026
        """
        source = rng if rng is not None else _random_module
        drops = []

        for entry in self.always:
            quantity = _resolve_quantity(entry, source)
            drops.append((entry.item_key, quantity))

        main_drops = self._roll_main(source)
        drops.extend(main_drops)

        tertiary_drops = self._roll_tertiary(source)
        drops.extend(tertiary_drops)

        return drops


    def _roll_main(self, source) -> list:
        """
        Purpose: Take this table's weighted picks from the main pool.

        Entry:
            source - a random.Random-compatible object exposing randint.

        Exit/Returns:
            Returns a list of (item_key, quantity) tuples, empty when every
            pick landed in the no-drop tail or the pool is unrollable.

        Module Globals:
            None.

        Methodology:
            Each of `rolls` iterations is an independent pick, so a table with
            rolls=2 can drop the same entry twice.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 08/14/2026
        """
        drops = []
        total_weight = self.total_main_weight()

        if total_weight <= _EMPTY_WEIGHT:
            return drops

        for _ in range(self.rolls):
            entry = _pick_weighted(self.main, total_weight, source)

            if entry is not None:
                quantity = _resolve_quantity(entry, source)
                drops.append((entry.item_key, quantity))

        return drops


    def _roll_tertiary(self, source) -> list:
        """
        Purpose: Roll every independent rare slot on this table.

        Entry:
            source - a random.Random-compatible object exposing randint.

        Exit/Returns:
            Returns a list of (item_key, quantity) tuples, usually empty.

        Module Globals:
            None.

        Methodology:
            One 1..chance_denominator roll per slot, hitting on
            _TERTIARY_HIT_VALUE. Slots do not compete, so more than one can
            fire on the same kill.

        Notes/References:
            A chance_denominator below _TERTIARY_HIT_VALUE would make the drop
            unconditional; validate_loot_tables() rejects it rather than
            letting a typo turn a rare into a guaranteed drop.

        Author: Nick Hobar
        Creation date: 08/14/2026
        """
        drops = []

        for tertiary in self.tertiary:
            roll_value = source.randint(_TERTIARY_HIT_VALUE,
                                        tertiary.chance_denominator)

            if roll_value == _TERTIARY_HIT_VALUE:
                quantity = _resolve_quantity(tertiary.entry, source)
                drops.append((tertiary.entry.item_key, quantity))

        return drops


# ─── Private helper routines ─────────────────────────────────────────────────

def _resolve_quantity(entry: LootEntry, source) -> int:
    """
    Purpose: Pick a stack size for one loot entry.

    Entry:
        entry  - the LootEntry whose bounds are being resolved.
        source - a random.Random-compatible object exposing randint.

    Exit/Returns:
        Returns an integer in [min_quantity, max_quantity] inclusive.

    Module Globals:
        None.

    Methodology:
        A max at or below the min short-circuits to the min, which covers both
        the common fixed-quantity case and a malformed inverted range without
        letting randint raise inside a death handler.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    if entry.max_quantity <= entry.min_quantity:
        return entry.min_quantity

    quantity = source.randint(entry.min_quantity, entry.max_quantity)

    return quantity


def _pick_weighted(entries: list, total_weight: int, source):
    """
    Purpose: Select one entry from a weighted pool, or nothing.

    Entry:
        entries      - list of LootEntry competing in the pool.
        total_weight - the pool's denominator, INCLUDING the table's
                       nothing_weight. Must be above _EMPTY_WEIGHT.
        source       - a random.Random-compatible object exposing randint.

    Exit/Returns:
        Returns the selected LootEntry, or None when the roll landed in the
        no-drop share of the range.

    Module Globals:
        _MIN_ROLL_VALUE read.

    Methodology:
        Walk a cumulative cursor across the entries and take the first one the
        roll value reaches. nothing_weight is never visited: it is the tail of
        the range that no entry covers, so falling off the end of the loop IS
        the no-drop outcome. That is why no sentinel "nothing" item key exists.

    Notes/References:
        The caller supplies total_weight rather than this routine recomputing
        it, because _roll_main takes several picks against the same pool.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    roll_value = source.randint(_MIN_ROLL_VALUE, total_weight)
    cursor = _EMPTY_WEIGHT

    for entry in entries:
        cursor += entry.weight

        if roll_value <= cursor:
            return entry

    return None


# ─── Public routines ─────────────────────────────────────────────────────────

def validate_loot_tables() -> list:
    """
    Purpose: Report every data error across the whole LOOT_DB registry.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a list of human-readable problem strings, empty when the
        registry is clean. Never raises.

    Module Globals:
        LOOT_DB read.

    Methodology:
        Collects rather than raises so one run names every problem instead of
        the first. This is the LOUD half of the fail-loud-in-tests /
        fail-soft-at-runtime split: world/tests/test_loot_database.py asserts
        the returned list is empty, while systems/loot/drops.py logs and skips
        a bad key at kill time. Import-time validation was rejected because a
        single typo in a def module would then refuse to boot the server.

    Notes/References:
        ITEM_DB is imported inside the routine, not at module scope, to keep
        this module leaf-of-graph -- world/item_database.py pulls in
        evennia.prototypes.spawner and items.equipment.constants, and
        loot_database is imported by world/npc_database.py.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    from world.item_database import ITEM_DB

    problems = []

    for table_key, table in LOOT_DB.items():
        table_problems = _validate_table(table_key, table, ITEM_DB)
        problems.extend(table_problems)

    return problems


def _validate_table(table_key: str, table: LootTableDef, item_db: dict) -> list:
    """
    Purpose: Report the data errors on one loot table.

    Entry:
        table_key - the registry key this table was filed under.
        table     - the LootTableDef to check.
        item_db   - the ITEM_DB mapping to resolve item keys against.

    Exit/Returns:
        Returns a list of problem strings, empty when the table is clean.

    Module Globals:
        None.

    Methodology:
        Checks, in order: registry key matches the def's own key; every entry
        across all three stages names a real item and has a sane quantity
        range; the main pool is rollable; every tertiary denominator can
        actually fail.

    Notes/References:
        A mismatched registry key is worth catching because LOOT_DB is built
        by dict merge -- a def whose key disagrees with its dict key is
        reachable under one name and self-reports the other, which is exactly
        how the "Metalsmith" / "Metalsmithing" bug hid every anvil recipe.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    problems = []

    if table.key != table_key:
        problems.append(
            f"{table_key}: registered under a key its def calls {table.key!r}."
        )

    all_entries = _collect_entries(table)

    for entry in all_entries:
        if entry.item_key not in item_db:
            problems.append(
                f"{table_key}: entry names unknown item {entry.item_key!r}."
            )

        if entry.max_quantity < entry.min_quantity:
            problems.append(
                f"{table_key}: {entry.item_key} has max_quantity "
                f"{entry.max_quantity} below min_quantity {entry.min_quantity}."
            )

    pool_problems = _validate_pools(table_key, table)
    problems.extend(pool_problems)

    return problems


def _validate_pools(table_key: str, table: LootTableDef) -> list:
    """
    Purpose: Report the errors that live on a table's pools rather than on an
    individual entry.

    Entry:
        table_key - the registry key, for the message text.
        table     - the LootTableDef to check.

    Exit/Returns:
        Returns a list of problem strings, empty when the pools are sane.

    Module Globals:
        _EMPTY_WEIGHT read.
        _TERTIARY_HIT_VALUE read.

    Methodology:
        A populated main pool whose total weight is zero would silently never
        drop anything, and a tertiary denominator at or below the hit value
        would make a rare unconditional. Both are typos that produce no error
        at runtime, only wrong loot, so they are caught here.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    problems = []
    total_weight = table.total_main_weight()

    if table.main and total_weight <= _EMPTY_WEIGHT:
        problems.append(
            f"{table_key}: main pool has {len(table.main)} entries but a "
            f"total weight of {total_weight}, so it can never drop."
        )

    for tertiary in table.tertiary:
        if tertiary.chance_denominator <= _TERTIARY_HIT_VALUE:
            problems.append(
                f"{table_key}: tertiary {tertiary.entry.item_key} has "
                f"chance_denominator {tertiary.chance_denominator}, which "
                f"drops it on every kill."
            )

    return problems


def _collect_entries(table: LootTableDef) -> list:
    """
    Purpose: Flatten a table's three stages into one list of LootEntry.

    Entry:
        table - the LootTableDef to flatten.

    Exit/Returns:
        Returns a list of every LootEntry the table references, in
        always / main / tertiary order.

    Module Globals:
        None.

    Methodology:
        Unwraps each TertiaryDrop to the LootEntry it carries so the per-entry
        checks in _validate_table need only one loop over one type.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    entries = list(table.always)
    entries.extend(table.main)

    for tertiary in table.tertiary:
        entries.append(tertiary.entry)

    return entries


from .loot_defs.hostile import TABLES as _HOSTILE

# Every def module must appear in BOTH lists below. A module imported but left
# out of the loop contributes nothing and raises nothing -- its tables simply
# do not exist as far as the rest of the game is concerned. Same trap as the
# ITEM_DB merge at the bottom of world/item_database.py.
LOOT_DB: dict = {}

for _d in [_HOSTILE]:
    LOOT_DB.update(_d)
