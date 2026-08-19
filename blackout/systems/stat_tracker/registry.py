"""
GNU License or generic module header.
Author: Danny Hered
Creation date: 08/17/2026
Description: Registry of stat definitions for the stat tracker.
"""

from dataclasses import dataclass
from enum import Enum

from systems.stat_tracker.constants import KILLS_PER_HOSTILE_STAT_KEY, CUTTING_TOTALS_STAT_KEY



class StatKind(Enum):
    """
    Purpose: Distinguish the two shapes a tracked stat's storage can take.

    Notes/References:
        COUNTER holds one running total (e.g. total credits earned).
        KEYED_COUNTER a dict holding a running total per sub-key (e.g. kills for every hostile type)

    Author: Danny Hered
    Creation date: 08/17/2026
    """
    COUNTER = "counter"
    KEYED_COUNTER = "keyed_counter"
    # milestone flags, e.g. has player found [secret]? completed X quest?
    # high water mark, e.g. highest hit


@dataclass
class StatDef:
    """
    Purpose: Pure-data description of one trackable stat. Carries no runtime
    state -- current totals live in StatHandler storage, not here.

    Module Globals:
        None

    Author: Danny Hered
    Creation date: 08/17/2026
    """
    key: str
    name: str
    desc: str
    kind: StatKind
    category: str


STAT_REGISTRY: dict[str, StatDef] = {
    KILLS_PER_HOSTILE_STAT_KEY: StatDef(
        key=KILLS_PER_HOSTILE_STAT_KEY,
        name="Kills per Hostile",
        desc="Number of kills on every hostile.",
        kind=StatKind.KEYED_COUNTER,
        category="combat",
    ),
    CUTTING_TOTALS_STAT_KEY: StatDef(
        key=CUTTING_TOTALS_STAT_KEY,
        name="Cuttings per Gatherable Type",
        desc="Number of successful cuts from every Gatherable.",
        kind=StatKind.KEYED_COUNTER,
        category="gatherable",
    ),
}
