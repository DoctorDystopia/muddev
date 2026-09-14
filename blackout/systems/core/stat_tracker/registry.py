"""
GNU License or generic module header.
Author: Danny Hered
Creation date: 08/17/2026
Description: Registry of stat definitions for the stat tracker.
"""

from dataclasses import dataclass
from enum import Enum

from systems.core.stat_tracker.constants import KILLS_PER_HOSTILE_STAT_KEY
from systems.core.stat_tracker.constants import DEATHS_PER_HOSTILE_STAT_KEY
from systems.core.stat_tracker.constants import CUTTING_TOTALS_STAT_KEY
from systems.core.stat_tracker.constants import BUTCHERY_TOTALS_STAT_KEY
from systems.core.stat_tracker.constants import CREDITS_SPENT_STAT_KEY


class StatKind(Enum):
    """
    Purpose: Distinguish the two shapes a tracked stat's storage can take.

    Notes/References:
        COUNTER holds one running total (e.g. total credits earned).
        KEYED_COUNTER holds a dict of running totals, one per sub-key (e.g.
        kills for every hostile type).

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

    Notes/References:
        `name` is the stat's full title, the heading on the `stats` sheet.
        `label` is its short form, drawn in the dossier's label column -- which
        is FIELD_LABEL_WIDTH (14) columns and clips anything longer, so
        "Cuttings per Gatherable Type" cannot serve both. The Records panel's
        tests assert every label fits.

    Author: Danny Hered
    Creation date: 08/17/2026
    """
    key: str
    name: str
    desc: str
    kind: StatKind
    category: str
    label: str


STAT_REGISTRY: dict[str, StatDef] = {
    KILLS_PER_HOSTILE_STAT_KEY: StatDef(
        key=KILLS_PER_HOSTILE_STAT_KEY,
        name="Kills per Hostile",
        desc="Number of kills on every hostile.",
        kind=StatKind.KEYED_COUNTER,
        category="combat",
        label="Kills",
    ),
    DEATHS_PER_HOSTILE_STAT_KEY: StatDef(
        key=DEATHS_PER_HOSTILE_STAT_KEY,
        name="Deaths per Hostile",
        desc="Number of deaths to every hostile.",
        kind=StatKind.KEYED_COUNTER,
        category="combat",
        label="Deaths",
    ),
    CUTTING_TOTALS_STAT_KEY: StatDef(
        key=CUTTING_TOTALS_STAT_KEY,
        name="Cuttings per Gatherable Type",
        desc="Number of successful cuts from every Gatherable.",
        kind=StatKind.KEYED_COUNTER,
        category="gatherable",
        label="Cuttings",
    ),
    # butchery.py declared this key as its stat_key before it was registered
    # here, so every harvest raised KeyError inside GatheringSkill._record_stat
    # -- caught and logged, so butchery totals silently never accumulated.
    # test_registry.py now fails for any *_STAT_KEY left unregistered.
    BUTCHERY_TOTALS_STAT_KEY: StatDef(
        key=BUTCHERY_TOTALS_STAT_KEY,
        name="Butcherings per Gatherable Type",
        desc="Number of successful butcherings from every Gatherable.",
        kind=StatKind.KEYED_COUNTER,
        category="gatherable",
        label="Butchered",
    ),
    CREDITS_SPENT_STAT_KEY: StatDef(
        key=CREDITS_SPENT_STAT_KEY,
        name="Total credits spent",
        desc="Total credits spent by this character",
        kind=StatKind.COUNTER,
        category="econ",
        label="Credits spent",
    ),
}
