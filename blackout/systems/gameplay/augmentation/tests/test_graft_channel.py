"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/09/2026
Description: The graft channel (Nick, 11/09/2026): a count of grafts on the
             global tick, one graft each GRAFT_TICKS ticks. A walk, a
             fight, or `graft stop` ends it, and a count works anywhere.

             The tests drive the channel with handler.tick(), as the
             gathering tests do. Every number comes from the constants or
             the ItemDef, never from a literal.
Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.gameplay.augmentation.tests.test_graft_channel
"""

from unittest import mock

from evennia import create_object
from evennia.utils.test_resources import EvenniaCommandTest

from commands.augment_cmds import CmdGraft
from systems.gameplay.augmentation import constants as aug_const
from systems.gameplay.augmentation import graft as graft_service
from systems.gameplay.augmentation import graft_channel
from systems.gameplay.progression.skills.constants import SKILL_KEY_AUGMENTATION
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.loci import AugmentationLocus


# ─── Private constant definitions ────────────────────────────────────────────

# The stack that each test carries. Large enough for a count of several.
_UNITS = 6

# A count below the stack, so the clamp and "all" differ from it.
_COUNT = 3


# ─── Private helper routines ─────────────────────────────────────────────────

class _ChannelFixture(EvenniaCommandTest):
    """A stack of the first sample in the bag, and a channel ended after."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.item_def = graft_service.sample_defs()[0]
        self.name = self.item_def.name.lower()
        self.item_def.create(location=self.char1, home=self.char1, quantity=_UNITS)
        self.addCleanup(graft_channel.end_grafting, self.char1)

    def _units(self) -> int:
        return graft_service.units_carried(self.char1, self.name)

    def _xp(self) -> int:
        return self.char1.skills.get_total_xp(SKILL_KEY_AUGMENTATION)

    def _graft(self, tail: str = "") -> str:
        return self.call(CmdGraft(), f" {self.item_def.name}{tail}", caller=self.char1)

    def _stop(self) -> str:
        return self.call(CmdGraft(), f" {aug_const.GRAFT_STOP_ARG}", caller=self.char1)

    def _handler(self):
        return graft_channel.get_graft_handler(self.char1)

    def _tick(self, times: int) -> None:
        """Tick the channel, while it lives."""
        for _ in range(times):
            handler = self._handler()

            if handler is None:
                return

            handler.tick()

    def _run_out(self) -> None:
        """Tick until the channel ends. Bounded, so a fault cannot hang."""
        bound = (_UNITS + 2) * aug_const.GRAFT_TICKS

        self._tick(bound)

    def _said(self, action) -> str:
        """The text of the lines sent to char1 while `action` runs."""
        with mock.patch.object(self.char1, "msg") as msg:
            action()

        lines = []

        for call in msg.call_args_list:
            text = call.args[0] if call.args else call.kwargs.get("text")

            if isinstance(text, tuple):
                lines.append(str(text[0]))

        return "\n".join(lines).lower()


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestTheCount(_ChannelFixture):
    """A count grafts one unit at once, then one each GRAFT_TICKS ticks."""

    def test_the_first_graft_happens_at_once(self):
        self._graft(f" {_COUNT}")

        self.assertEqual(self._units(), _UNITS - 1)

    def test_the_next_graft_waits_for_its_ticks(self):
        self._graft(f" {_COUNT}")

        self._tick(aug_const.GRAFT_TICKS - 1)
        self.assertEqual(self._units(), _UNITS - 1)

        self._tick(1)
        self.assertEqual(self._units(), _UNITS - 2)

    def test_a_count_runs_to_its_end_and_the_channel_ends(self):
        self._graft(f" {_COUNT}")

        self._run_out()

        self.assertEqual(self._units(), _UNITS - _COUNT)
        self.assertIsNone(self._handler())

    def test_all_grafts_every_unit(self):
        self._graft(" all")

        self._run_out()

        self.assertEqual(self._units(), 0)

    def test_a_count_above_the_stack_clamps_to_it(self):
        self._graft(f" {_UNITS * 2}")

        self._run_out()

        self.assertEqual(self._units(), 0)
        self.assertIsNone(self._handler())

    def test_the_done_line_follows_the_last_graft(self):
        self._graft(f" {_COUNT}")

        said = self._said(self._run_out)

        self.assertIn("complete", said)

    def test_the_popup_key_names_the_sample_too(self):
        self.call(CmdGraft(), f" {self.item_def.key} {_COUNT}", caller=self.char1)

        self._run_out()

        self.assertEqual(self._units(), _UNITS - _COUNT)


class TestThePace(_ChannelFixture):
    """The wait holds for every graft, so a click again and again is not
    faster than a count."""

    def test_a_second_command_joins_the_wait(self):
        self._graft()
        self._graft()

        self.assertEqual(self._units(), _UNITS - 1)

        self._tick(aug_const.GRAFT_TICKS)
        self.assertEqual(self._units(), _UNITS - 2)

    def test_the_wait_ends_the_channel_with_no_count_left(self):
        self._graft()

        self._tick(aug_const.GRAFT_TICKS)

        self.assertIsNone(self._handler())
        self.assertEqual(self._units(), _UNITS - 1)

    def test_a_stop_keeps_the_wait(self):
        self._graft(f" {_COUNT}")
        self._stop()
        self._graft()

        self.assertEqual(self._units(), _UNITS - 1)
        self.assertIsNotNone(graft_channel.channel_report(self.char1))


class TestTheEnds(_ChannelFixture):
    """Why a running count ends, and what the player reads."""

    def test_stop_ends_the_count(self):
        self._graft(f" {_COUNT}")

        response = self._stop()
        self._run_out()

        self.assertIn("stop", response.lower())
        self.assertEqual(self._units(), _UNITS - 1)

    def test_stop_with_nothing_running_says_so(self):
        response = self._stop()

        self.assertIn("not grafting", response.lower())

    def test_a_walk_ends_the_channel(self):
        self._graft(f" {_COUNT}")

        self.char1.move_to(self.room2, quiet=True)
        self._run_out()

        self.assertEqual(self._units(), _UNITS - 1)
        self.assertIsNone(self._handler())

    def test_a_fight_ends_the_channel_and_says_so(self):
        self._graft(f" {_COUNT}")

        with mock.patch.object(BlackoutCharacter, "in_combat",
                               new_callable=mock.PropertyMock, return_value=True):
            said = self._said(lambda: self._tick(1))

        self.assertIn("fight", said)
        self.assertIsNone(self._handler())
        self.assertEqual(self._units(), _UNITS - 1)

    def test_a_count_halts_when_the_samples_run_out(self):
        self._graft(f" {_COUNT}")

        graft_service.next_unit(self.char1, self.name).delete()
        said = self._said(self._run_out)

        self.assertIn("halted", said)
        self.assertIsNone(self._handler())

    def test_a_sample_not_carried_is_refused(self):
        graft_service.next_unit(self.char1, self.name).delete()

        response = self._graft(f" {_COUNT}")

        self.assertIn("not carrying", response.lower())
        self.assertIsNone(self._handler())


class TestTheRate(_ChannelFixture):
    """A count works anywhere. Only the rate changes at a Locus."""

    def test_a_count_away_from_a_locus_pays_the_base_rate(self):
        before = self._xp()

        self._graft(f" {_COUNT}")
        self._run_out()

        expected = _COUNT * graft_service.def_xp(self.item_def, at_locus=False)
        self.assertEqual(self._xp() - before, expected)

    def test_a_count_at_a_locus_pays_the_locus_rate(self):
        create_object(AugmentationLocus, key="locus", location=self.room1)
        before = self._xp()

        self._graft(f" {_COUNT}")
        self._run_out()

        expected = _COUNT * graft_service.def_xp(self.item_def, at_locus=True)
        self.assertEqual(self._xp() - before, expected)
