"""
GNU License or generic module header.
Author: Danny Hered
Creation date: 08/17/2026
Description: Generic per-character stat storage, keyed off STAT_REGISTRY.
"""

from systems.core.stat_tracker.registry import STAT_REGISTRY, StatKind


class StatHandler:
    """
    Purpose: Track arbitrary per-character stats declared in STAT_REGISTRY
    without requiring a handler class or storage attribute per stat.

    Methodology:
        Every registered stat lives in one dict on the character, obj.db.stats. 
        
        COUNTER stat stores         |  {stat_key: total(int)}
        KEYED_COUNTER stat stores   |  {stat_key: {sub_key: total(int)}}

    Author: Danny Hered
    Creation date: 08/17/2026
    """

    def __init__(self, obj: object) -> None:
        """
        Purpose: Bind this handler to a character and ensure its stat storage exists.

        Entry:
            obj is the Evennia object (character or other) whose stats this handler tracks

        Exit/Returns:
            No return value. Lazily seeds obj.db.stats to {} if falsy.
        
        Author: Danny Hered
        Creation date: 08/17/2026
        """
        self.obj = obj
        if not self.obj.db.stats:
            self.obj.db.stats = {}

    def increment(self, stat_key: str, key: str | None = None, amount: int = 1) -> None:
        """
        Purpose: Add an integer amount to a stat's running total.

        Entry:
            stat_key is a key present in STAT_REGISTRY.
            key is required for a KEYED_COUNTER stat, ignored for a COUNTER
            stat.
            amount must be an int; raises TypeError otherwise.

        Exit/Returns:
            No return value. Updates self.obj.db.stats in place.

            Raises ValueError if StatKind is not one of:
            - COUNTER
            - KEYED_COUNTER

        Notes/References:
            KEYED_COUNTER normalizes the sub-dict to plain dict before
            mutating, then reassigns via one top-level __setitem__.

        Author: Danny Hered
        Creation date: 08/17/2026
        """
        if not isinstance(amount, int):
            raise TypeError(f"{stat_key} expects an int amount, got {type(amount)}")
    
        stat_def = STAT_REGISTRY[stat_key]

        if stat_def.kind == StatKind.COUNTER:
            current_total = self.obj.db.stats.get(stat_key, 0)
            self.obj.db.stats[stat_key] = current_total + amount

        elif stat_def.kind == StatKind.KEYED_COUNTER:
            bucket = dict(self.obj.db.stats.get(stat_key, {}))
            bucket[key] = bucket.get(key, 0) + amount
            self.obj.db.stats[stat_key] = bucket
        else:
            raise ValueError(f"{stat_key} has StatKind {stat_def.kind}, not supported by StatHandler.increment")

        self._mark_dossier_stale()

    def get(self, stat_key: str, key: str | None = None) -> int | dict:
        """
        Purpose: Read the current total for a stat.

        Entry:
            stat_key is a key present in STAT_REGISTRY.
            key, for a KEYED_COUNTER stat, selects one sub-key; omitted,
            the full {sub_key: total} mapping is returned instead.

        Exit/Returns:
            StatKind                   |  Return
            StatKind.COUNTER           |  int
            StatKind.KEYED_COUNTER     |  key, int :  no key, dict
            unrecorded stat or sub-key |  0

            raises ValueError if StatKind is not one of:
            - COUNTER
            - KEYED_COUNTER

        Author: Danny Hered
        Creation date: 08/17/2026
        """
        stat_def = STAT_REGISTRY[stat_key]

        if stat_def.kind == StatKind.COUNTER:
            return self.obj.db.stats.get(stat_key, 0)

        elif stat_def.kind == StatKind.KEYED_COUNTER:
            bucket = self.obj.db.stats.get(stat_key, {})
            if key is None:
                return dict(bucket)
            return bucket.get(key, 0)
        else:
            raise ValueError(f"{stat_key} has StatKind {stat_def.kind}, not supported by StatHandler.get")

    def all(self) -> dict:
        """
        Purpose: Snapshot every stat this character has recorded.

        Exit/Returns:
            Returns a copy of self.obj.db.stats.

        Author: Danny Hered
        Creation date: 08/17/2026
        """
        return dict(self.obj.db.stats)

    def recorded(self) -> list:
        """
        Purpose: Every registered stat this character has a nonzero record
        for, in STAT_REGISTRY order.

        Exit/Returns:
            Returns a list of (StatDef, value) tuples. value is an int for a
            COUNTER stat and a plain {sub_key: total} dict for a KEYED_COUNTER
            stat. A stat never incremented is absent, not reported as zero.

        Module Globals:
            STAT_REGISTRY read.

        Methodology:
            Walks the REGISTRY, not self.obj.db.stats, so a row left behind by
            a stat since removed from the registry is never shown -- the
            registry decides what a stat is called and what shape it has, and
            a stored key it cannot describe has no honest way to be drawn.

            This is the one read the Records dossier band and the `stats`
            sheet share, so the two cannot disagree about what has been
            recorded.

        Author: Nick Hobar
        Creation date: 09/13/2026
        """
        recorded = []

        for stat_key, stat_def in STAT_REGISTRY.items():
            value = self.get(stat_key)

            if not value:
                continue

            recorded.append((stat_def, value))

        return recorded

    def _mark_dossier_stale(self) -> None:
        """
        Purpose: Tell the state feed this character's dossier is out of date.

        Exit/Returns:
            None. A no-op for an object nobody is subscribed through.

        Methodology:
            The Records band on the dossier reads these totals, and CLAUDE.md's
            "Every pane follows its facts" rule puts the mark at the writer of
            the fact rather than beside each caller -- a kill, a harvest and a
            purchase all reach the Character tab because they all come through
            increment. refresh_summary marks, it does not build, so a fight
            recording a kill a tick costs one dossier build a tick at most.

            Imported inside the method: typeclasses/characters.py imports this
            module while its class is being defined, and the statefeed's own
            import graph has no business running ahead of that.

        Author: Nick Hobar
        Creation date: 09/13/2026
        """
        from systems.interface.statefeed.events import refresh_summary

        refresh_summary(self.obj)

    def _hard_reset(self) -> None:
        """
        Purpose: Completely resets self.obj.db.stats, Irreversible.

        Exit/Returns:
            None

        Author: Danny Hered
        Creation date: 08/18/2026
        """
        self.obj.db.stats = {}
        self._mark_dossier_stale()
