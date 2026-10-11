"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/07/2026
Description: The `par_time_points` buff: more points when the task ends
             inside its par time. The "speed running" idea of the vault
             note.

             A task buff. It changes no combat number, so it overrides no
             seam and adds no modifier. The handler asks it for a points
             bonus when the last kill ends the task. DESIGN-0012, Phase 5.
"""

from systems.gameplay.exterminator import constants as ext_const

from .base_buff import BaseExterminatorBuff



class ParTimePointsBuff(BaseExterminatorBuff):
    """
    Purpose: Add a part of the task points when the task ends inside its par
             time.

    Entry:
        No conditions.

    Exit/Returns:
        Not applicable. A rules definition with no combat effect.

    Module Globals:
        ext_const.RARITY_*, ext_const.SECONDS_PER_MINUTE read.

    Methodology:
        The par time is the total kills times the seconds per kill of the
        creature type (Nick, 10/07/2026). The clock counts online time
        only. ExterminatorHandler owns both numbers:
        par_seconds and elapsed_seconds.

        A buff picked late still counts the time from the assignment. The
        par time belongs to the task, not to the buff.

    Notes/References:
        The numbers are the vault example (+50%) at 1x, 1.5x, 2x, and 3x
        (Nick, 10/07/2026). TBD.

    Author: Nick Hobar
    Creation date: 10/07/2026
    """

    key = ext_const.BUFF_PAR_TIME_POINTS
    archetype = ext_const.BUFF_PAR_TIME_POINTS
    name = "Par Time"  # TBD name
    description = "+{value:.0%} points if you end the task inside the par time."
    par_description = (
        "+{value:.0%} points if you end the task inside the par time: "
        "{minutes} min {seconds} s of online time."
    )

    strengths = {
        ext_const.RARITY_COMMON: 0.50,
        ext_const.RARITY_RARE: 0.75,
        ext_const.RARITY_EPIC: 1.00,
        ext_const.RARITY_LEGENDARY: 1.50,
    }

    def describe(self, rarity, holder=None) -> str:
        """The description, with the par time of the task of the holder."""
        handler = getattr(holder, "exterminator", None)

        if handler is None or not handler.has_task():
            return super().describe(rarity, holder)

        minutes, seconds = divmod(handler.par_seconds(), ext_const.SECONDS_PER_MINUTE)
        value = self.value_at(rarity)

        return self.par_description.format(value=value, minutes=minutes, seconds=seconds)

    def points_bonus(self, holder) -> float:
        """The strength when the task is inside its par time, else 0."""
        handler = getattr(holder, "exterminator", None)

        if handler is None or not handler.has_task():
            return 0.0

        inside_par = handler.elapsed_seconds() <= handler.par_seconds()

        if not inside_par:
            return 0.0

        return self.strength(holder)
