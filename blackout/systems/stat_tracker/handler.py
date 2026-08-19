"""
GNU License or generic module header.
Author: Danny Hered
Creation date: 08/17/2026
Description: Generic per-character stat storage, keyed off STAT_REGISTRY.
"""

from systems.stat_tracker.registry import STAT_REGISTRY, StatKind


class StatHandler:
    """
    Purpose: Track arbitrary per-character stats declared in STAT_REGISTRY,
    without a bespoke handler class or storage attribute per stat.

    Methodology:
        Every registered stat lives in one dict on the character,
        obj.db.stats. A COUNTER stat stores {stat_key: total}; a
        KEYED_COUNTER stat stores {stat_key: {sub_key: total}}.

    Author: Danny Hered
    Creation date: 08/17/2026
    """

    def __init__(self, obj):
        self.obj = obj
        if not self.obj.db.stats:
            self.obj.db.stats = {}

    def increment(self, stat_key, key=None, amount=1):
        """
        Purpose: Add an integer amount to a stat's running total.

        Entry:
            stat_key is a key present in STAT_REGISTRY.
            key is required for a KEYED_COUNTER stat, ignored for a COUNTER
            stat.

        Exit/Returns:
            No return value. Updates self.obj.db.stats in place.

        Notes/References:
            Mutating a nested dict returned from db.stats in place is not
            reliably persisted -- Evennia's Attribute save-tracking only
            catches assignment at the top-level dict. Read the sub-dict as a
            plain copy, mutate the copy, then reassign it back with a single
            top-level __setitem__, same as the COUNTER branch below.

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

    def get(self, stat_key, key=None):
        """
        Purpose: Read the current total for a stat.

        Entry:
            stat_key is a key present in STAT_REGISTRY.
            key, for a KEYED_COUNTER stat, selects one sub-key; omitted,
            the full {sub_key: total} mapping is returned instead.

        Exit/Returns:
            Returns an int for a COUNTER stat, or for a KEYED_COUNTER stat
            an int (key given) or a dict copy (key omitted). Returns 0 for
            an unrecorded stat or sub-key.

        Author: Danny Hered
        Creation date: 08/17/2026
        """
        stat_def = STAT_REGISTRY[stat_key]
        if stat_def.kind == StatKind.KEYED_COUNTER:
            bucket = self.obj.db.stats.get(stat_key, {})
            if key is None:
                return dict(bucket)
            return bucket.get(key, 0)
        return self.obj.db.stats.get(stat_key, 0)

    def all(self):
        """
        Purpose: Snapshot every stat this character has recorded

        Exit/Returns:
            Returns a copy of self.obj.db.stats.

        Author: Danny Hered
        Creation date: 08/17/2026
        """
        return dict(self.obj.db.stats)

    def _hard_reset(self) -> None:
        """
        Purpose: Completely resets self.obj.db.stats, Irreversable

        Exit/Returns:
            None

        Author: Danny Hered
        Creation date: 08/18/2026
        """
        self.obj.db.stats = {}
