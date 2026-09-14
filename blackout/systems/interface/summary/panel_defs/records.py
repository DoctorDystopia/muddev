"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/13/2026
Description: Summary panel: the character's lifetime tallies -- kills and
             deaths per hostile, harvests per node, credits spent -- as kept
             by systems/core/stat_tracker/.
"""

from evennia.utils import logger

from systems.core.stat_tracker.registry import StatKind

from .. import constants as const
from .. import layout
from .base_panel import BasePanel


# Public constant definitions

PANEL_TITLE = "Records"

LABEL_TOTAL = "Total"

# Shown on the `stats` sheet before anything has been recorded. The dossier
# band says nothing at all in that state -- see RecordsPanel.render.
EMPTY_SHEET_TEXT = "Nothing recorded yet."

# How many entries of one keyed stat the dossier names before summarising the
# rest. The `stats` sheet names every one; this only keeps a character with
# thirty hostiles on their kill list from turning the dossier into a list.
MAX_LISTED_ENTRIES = 3
MORE_ENTRIES_TEMPLATE = "+{count} more"


class RecordsPanel(BasePanel):
    """
    Purpose: Every stat the tracker holds for this character, on one band.

    Entry:
        character is a Character. It need not have a stats handler.

    Exit/Returns:
        Not applicable -- see render / data / sheet.

    Module Globals:
        None.

    Methodology:
        IT NAMES NO STAT. Rows come from StatHandler.recorded(), which walks
        STAT_REGISTRY, and each row's wording is that StatDef's `label` and
        `name` -- so a stat added to the registry appears here, on the `stats`
        sheet and in the Godot Character tab with no edit to any of the three.
        The only thing this module branches on is the stat's KIND, which is
        the storage shape, not the stat.

        Three outputs from one read:

          render -> the dossier band. Counters pair up; each keyed stat gets a
                    wrapped row naming its top MAX_LISTED_ENTRIES.
          data   -> the Character tab. Every entry, uncapped: a counter is a
                    scalar row, a keyed stat a nested dict, which SummaryState
                    draws as a boxed group with no knowledge of what it is.
          sheet  -> the `stats` command. Every entry, each stat under its own
                    heading, with a total.

        A sub-key ("mutant_raider", "rusty_pole") is labelled by humanising
        it rather than by a lookup into NPC_DB or GATHERABLE_REGISTRY. Those
        would make the tracker's presentation depend on every system that
        feeds it, and the mechanical rule is exactly the one SummaryState
        applies to the same keys in Godot -- so both screens spell an entry
        the same way.

        Silent when nothing is recorded, like Processing: a fresh character's
        dossier should not open on a band of zeroes.

        Private, the default. What someone has spent and how often they have
        died is not a stranger's to read; making tallies public is a decision
        about this band, not something it should inherit.

    Notes/References:
        systems/core/stat_tracker/registry.py owns what a stat is.

    Author: Nick Hobar
    Creation date: 09/13/2026
    """

    key = "records"
    title = PANEL_TITLE
    order = const.PANEL_ORDER_RECORDS
    public = False


    @classmethod
    def _recorded(cls, character: object) -> list:
        """
        Purpose: Fetch the character's recorded stats, tolerating a failure.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns StatHandler.recorded()'s list, or [] if the character has
            no stats handler or the read raised.

        Module Globals:
            None.

        Methodology:
            Guarded for the reason ReadinessPanel guards its profile: a corrupt
            stats row should cost the player this band, not the dossier.

        Author: Nick Hobar
        Creation date: 09/13/2026
        """
        stats = getattr(character, "stats", None)

        if stats is None:
            return []

        try:
            recorded = stats.recorded()
        except Exception as exc:
            logger.log_err(f"RecordsPanel._recorded failed: {exc!r}")

            return []

        return recorded


    @classmethod
    def _ranked(cls, bucket: dict) -> list:
        """
        Purpose: Order one keyed stat's entries for display.

        Entry:
            bucket is a {sub_key: total} dict.

        Exit/Returns:
            Returns a list of (sub_key, total) pairs, highest total first,
            ties broken by sub_key so the order is the same on every read.

        Author: Nick Hobar
        Creation date: 09/13/2026
        """
        ranked = sorted(bucket.items(), key=lambda pair: (-pair[1], pair[0]))

        return ranked


    @classmethod
    def _entry_label(cls, sub_key: str) -> str:
        """
        Purpose: Turn a stable snake_case sub-key into a display name.

        Entry:
            sub_key is a stat sub-key, e.g. "mutant_raider".

        Exit/Returns:
            Returns e.g. "Mutant Raider".

        Methodology:
            Mechanical, for the reason given on the class. The same rule
            combat_msg._label_for_stat_key uses for bonus keys.

        Author: Nick Hobar
        Creation date: 09/13/2026
        """
        spaced = str(sub_key).replace("_", " ")
        label = spaced.title()

        return label


    @classmethod
    def _listed_items(cls, bucket: dict) -> list:
        """
        Purpose: Build the dossier's capped item list for one keyed stat.

        Entry:
            bucket is a {sub_key: total} dict.

        Exit/Returns:
            Returns up to MAX_LISTED_ENTRIES "<Name> <total>" strings, plus one
            "+N more" item when entries were left out.

        Module Globals:
            MAX_LISTED_ENTRIES, MORE_ENTRIES_TEMPLATE read.

        Author: Nick Hobar
        Creation date: 09/13/2026
        """
        ranked = cls._ranked(bucket)
        listed = ranked[:MAX_LISTED_ENTRIES]
        items = [f"{cls._entry_label(sub_key)} {total}" for sub_key, total in listed]

        hidden = len(ranked) - len(listed)

        if hidden > 0:
            items.append(MORE_ENTRIES_TEMPLATE.format(count=hidden))

        return items


    @classmethod
    def render(cls, character: object) -> list:
        """
        Purpose: Render the records band.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns a list of display lines, empty when nothing is recorded.

        Module Globals:
            None.

        Methodology:
            Counters first, paired, because they are short; then one wrapped
            row per keyed stat. Within each group the registry's order holds.

        Author: Nick Hobar
        Creation date: 09/13/2026
        """
        pairs = []
        keyed_lines = []

        for stat_def, value in cls._recorded(character):
            if stat_def.kind == StatKind.KEYED_COUNTER:
                items = cls._listed_items(value)
                keyed_lines.extend(layout.wrapped_field(stat_def.label, items))
            else:
                pairs.append((stat_def.label, str(value)))

        lines = layout.fields(pairs)
        lines.extend(keyed_lines)

        return lines


    @classmethod
    def data(cls, character: object) -> dict:
        """
        Purpose: Structured form of the records band.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns {stat_key: int} for a counter and
            {stat_key: {sub_key: int}} for a keyed stat, empty when nothing is
            recorded.

        Module Globals:
            None.

        Methodology:
            Keyed by the stable stat key and sub-key rather than display
            names, like every other panel's data -- the client humanises field
            names itself. Keyed entries are uncapped and pre-ranked: a Godot
            dictionary keeps the order it was parsed in, so the tab shows the
            same order as the sheet with no sorting of its own.

        Author: Nick Hobar
        Creation date: 09/13/2026
        """
        payload = {}

        for stat_def, value in cls._recorded(character):
            if stat_def.kind == StatKind.KEYED_COUNTER:
                ranked = cls._ranked(value)
                payload[stat_def.key] = {str(sub_key): int(total) for sub_key, total in ranked}
            else:
                payload[stat_def.key] = int(value)

        return payload


    @classmethod
    def sheet(cls, character: object) -> str:
        """
        Purpose: Build the full `stats` screen -- every stat, every entry.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns the screen, newline-joined and bracketed by heavy rules.

        Module Globals:
            PANEL_TITLE, LABEL_TOTAL, EMPTY_SHEET_TEXT read.

        Methodology:
            The dossier band's uncapped form, drawn through the same layout
            module so the two read as one design. Each stat gets its own
            section headed by its full `name`, since the sheet has room the
            band's label column does not.

        Notes/References:
            Called by commands/progression_cmds.CmdStats.

        Author: Nick Hobar
        Creation date: 09/13/2026
        """
        recorded = cls._recorded(character)

        lines = [layout.rule(heavy=True)]
        lines.append(layout.split_line(PANEL_TITLE.upper(), str(character.key)))

        if not recorded:
            lines.append(layout.rule())
            lines.append(layout.wide_field("", EMPTY_SHEET_TEXT))

        for stat_def, value in recorded:
            lines.extend(layout.section(stat_def.name))
            lines.extend(cls._sheet_rows(stat_def, value))

        lines.append(layout.rule(heavy=True))
        screen = "\n".join(lines)

        return screen


    @classmethod
    def _sheet_rows(cls, stat_def: object, value: object) -> list:
        """
        Purpose: The body of one stat's section on the `stats` sheet.

        Entry:
            stat_def is a StatDef; value is what StatHandler.recorded() paired
            with it.

        Exit/Returns:
            Returns a list of display lines: the ranked tally and its total for
            a keyed stat, the total alone for a counter.

        Module Globals:
            LABEL_TOTAL read.

        Author: Nick Hobar
        Creation date: 09/13/2026
        """
        if stat_def.kind != StatKind.KEYED_COUNTER:
            return [layout.wide_field(LABEL_TOTAL, str(value))]

        ranked = cls._ranked(value)
        entries = [(cls._entry_label(sub_key), total) for sub_key, total in ranked]
        grand_total = sum(value.values())

        rows = layout.ranked_rows(entries)
        rows.append(layout.wide_field(LABEL_TOTAL, str(grand_total)))

        return rows
