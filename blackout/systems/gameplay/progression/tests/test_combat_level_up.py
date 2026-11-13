"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/09/2026
Description: The combat level line. add_xp sends it when an earned skill
             level increases the combat level, and at no other time.
"""

import math
from unittest import mock

from evennia.utils.ansi import strip_ansi
from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.combat import constants as combat_constants
from systems.gameplay.combat.combat_level.logic import get_combat_level
from systems.gameplay.progression.skills import logic
from systems.gameplay.progression.skills.constants import SKILL_KEY_CUTTING
from systems.gameplay.progression.skills.registry import SKILL_REGISTRY
from typeclasses.characters import Character as BlackoutCharacter



# A skill in the flat base of the combat level. The formula owns the list.
_BASE_SKILL: str = combat_constants.COMBAT_LEVEL_BASE_SKILLS[0]

# The level of the skill before each award. Any level well under the cap.
_START_LEVEL: int = 10

# The keyword of the combat level line, in lower case.
_COMBAT_LINE_KEYWORD: str = "combat level"



def _xp_for_levels(start_level: int, levels: int) -> int:
    """The XP that moves a skill from start_level, 0 XP, up by levels."""
    total = 0

    for offset in range(levels):
        total += logic.calculate_xp_needed(start_level + offset)

    return total



class CombatLevelUpLineTests(EvenniaTest):
    """The combat level line follows the combat level, not the skill level."""

    character_typeclass = BlackoutCharacter


    def _award(self, skill_key: str, levels: int) -> list:
        """
        Give a skill enough XP for levels, and return each text line sent.
        """
        self.char1.db.skills[skill_key] = {"level": _START_LEVEL, "xp": 0}
        amount = _xp_for_levels(_START_LEVEL, levels)

        with mock.patch.object(type(self.char1), "msg") as mocked_msg:
            self.char1.skills.add_xp(skill_key, amount)

        sent = [
            strip_ansi(str(call.args[0][0]))
            for call in mocked_msg.call_args_list
            if call.args and isinstance(call.args[0], tuple)
        ]

        return sent


    def _combat_lines(self, sent: list) -> list:
        return [line for line in sent if _COMBAT_LINE_KEYWORD in line.lower()]


    def _levels_for_one_combat_level(self) -> int:
        """
        Enough base skill levels to move the combat level by at least 1.

        Each base level adds COMBAT_LEVEL_BASE_WEIGHT. One level more than
        the exact quotient keeps the float sum clear of the floor.
        """
        exact = math.ceil(1 / combat_constants.COMBAT_LEVEL_BASE_WEIGHT)

        return exact + 1


    def test_a_raised_combat_level_sends_one_line_with_the_new_level(self):
        before = get_combat_level(self.char1)

        sent = self._award(_BASE_SKILL, self._levels_for_one_combat_level())

        after = get_combat_level(self.char1)
        combat_lines = self._combat_lines(sent)
        self.assertGreater(after, before)
        self.assertEqual(len(combat_lines), 1)
        self.assertIn("level_up", combat_lines[0].lower())
        self.assertIn(str(after), combat_lines[0])


    def test_the_combat_line_follows_the_skill_line(self):
        """The skill level is the cause, so the player reads it first."""
        skill_name = SKILL_REGISTRY[_BASE_SKILL].name

        sent = self._award(_BASE_SKILL, self._levels_for_one_combat_level())

        skill_index = next(
            index for index, line in enumerate(sent) if skill_name in line)
        combat_index = sent.index(self._combat_lines(sent)[0])
        self.assertLess(skill_index, combat_index)


    def test_a_level_that_leaves_the_combat_level_sends_no_line(self):
        """Cutting does not feed the formula. The check below proves it."""
        before = get_combat_level(self.char1)

        sent = self._award(SKILL_KEY_CUTTING, 1)

        self.assertEqual(get_combat_level(self.char1), before)
        self.assertEqual(self._combat_lines(sent), [])
