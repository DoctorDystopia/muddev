"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/13/2026
Description: Tests for xp_awards -- the one way an XP award is shown and paid.

             Plain unittest.TestCase: formatting is string assembly and the
             grant is exercised against a recording stub, so nothing here
             needs a database.

Run with:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py systems.gameplay.progression.tests.test_xp_awards
"""



import unittest

from evennia.utils.ansi import strip_ansi

from systems.gameplay.combat.protocols import XpEarner
from systems.gameplay.progression.skills import xp_awards
from systems.gameplay.progression.skills.registry import SKILL_REGISTRY
from systems.interface.statefeed import constants as feed_const



# Private constant definitions

# A key no skill will ever be registered under.
_UNKNOWN_SKILL_KEY = "not_a_real_skill"

# What these grants announce themselves as. The stubs have no sessions, so the
# feed publish grant_xp makes is a no-op here; test_xp_drop_feed.py covers it.
_KIND = feed_const.MESSAGE_TYPE_PROGRESSION



class _RecordingEarner:
    """Satisfies XpEarner and records every add_xp it receives."""

    def __init__(self) -> None:
        self.awards = []


    def add_xp(self, skill_key: str, amount: int) -> None:
        self.awards.append((skill_key, amount))


    def get_total_xp(self, skill_key: str) -> int:
        return sum(amount for key, amount in self.awards if key == skill_key)


    def meets_prerequisite(self, skill_key: str, required_level: int) -> bool:
        return True



class _AddXpOnly:
    """Has add_xp and nothing else of XpEarner -- an NPC-shaped handler."""

    def __init__(self) -> None:
        self.called = False


    def add_xp(self, skill_key: str, amount: int) -> None:
        self.called = True



class _Holder:
    """The least grant_xp needs: something with a .skills."""

    def __init__(self, skills) -> None:
        self.skills = skills



def _two_skill_keys() -> list:
    return list(SKILL_REGISTRY)[:2]



class TestReadout(unittest.TestCase):
    """What a player reads."""

    def test_the_stub_is_an_earner(self):
        """Every grant test below means nothing if this stops holding."""
        self.assertIsInstance(_RecordingEarner(), XpEarner)


    def test_nothing_granted_renders_nothing(self):
        """Callers append the suffix unconditionally, so it must vanish."""
        for awards in ([], [(_two_skill_keys()[0], 0)]):
            with self.subTest(awards=awards):
                self.assertEqual(xp_awards.format_xp_readout(awards), "")
                self.assertEqual(xp_awards.format_xp_suffix(awards), "")


    def test_every_skill_is_shown_by_its_registry_name(self):
        """A key is never title-cased by hand; the skill names itself."""
        for skill_key, skill_class in SKILL_REGISTRY.items():
            with self.subTest(skill=skill_key):
                visible = strip_ansi(
                    xp_awards.format_xp_readout([(skill_key, 7)]))

                self.assertIn(f"+7 {skill_class.name}", visible)


    def test_an_unknown_key_is_shown_as_itself(self):
        visible = strip_ansi(
            xp_awards.format_xp_readout([(_UNKNOWN_SKILL_KEY, 3)]))

        self.assertIn(f"+3 {_UNKNOWN_SKILL_KEY}", visible)


    def test_several_skills_share_one_readout(self):
        """'(+25 Butchery, +5 Cutting xp)' -- one bracket, not two."""
        first, second = _two_skill_keys()

        visible = strip_ansi(
            xp_awards.format_xp_readout([(first, 25), (second, 5)]))

        self.assertEqual(visible.count("("), 1)
        self.assertIn(xp_awards.XP_ENTRY_SEPARATOR, visible)
        self.assertTrue(visible.endswith(f"{xp_awards.XP_UNIT_LABEL})"))


    def test_a_zero_entry_is_dropped_from_a_mixed_award(self):
        first, second = _two_skill_keys()

        visible = strip_ansi(
            xp_awards.format_xp_readout([(first, 25), (second, 0)]))

        self.assertNotIn("+0", visible)
        self.assertNotIn(xp_awards.XP_ENTRY_SEPARATOR, visible)


    def test_the_suffix_is_the_readout_after_one_space(self):
        awards = [(_two_skill_keys()[0], 4)]

        suffix = xp_awards.format_xp_suffix(awards)

        self.assertEqual(suffix, f" {xp_awards.format_xp_readout(awards)}")


    def test_the_readout_carries_colour_markup(self):
        rendered = xp_awards.format_xp_readout([(_two_skill_keys()[0], 4)])

        self.assertNotEqual(rendered, strip_ansi(rendered))



class TestGrant(unittest.TestCase):
    """What a player receives, and that it matches what they read."""

    def test_the_grant_pays_exactly_what_the_readout_names(self):
        first, second = _two_skill_keys()
        awards = [(first, 25), (second, 0), (second, 5)]
        holder = _Holder(_RecordingEarner())

        granted = xp_awards.grant_xp(holder, awards, _KIND)

        self.assertEqual(holder.skills.awards, granted)
        self.assertEqual(
            xp_awards.format_xp_readout(granted),
            xp_awards.format_xp_readout(awards),
        )


    def test_a_non_earner_is_paid_nothing(self):
        """An NPC's skills have no XP curve to pay into."""
        npc_skills = _AddXpOnly()
        awards = [(_two_skill_keys()[0], 25)]

        granted = xp_awards.grant_xp(_Holder(npc_skills), awards, _KIND)

        self.assertEqual(granted, [])
        self.assertFalse(npc_skills.called)


    def test_something_with_no_skills_at_all_is_safe(self):
        granted = xp_awards.grant_xp(object(), [(_two_skill_keys()[0], 25)], _KIND)

        self.assertEqual(granted, [])
