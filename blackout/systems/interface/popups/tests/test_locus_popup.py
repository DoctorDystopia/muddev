"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/09/2026
Description: Cases for the Augmentation Locus pop-up and the `graft` forms
             that it rests on.

             THE LOAD-BEARING CASE sends a sample slot's command through the
             real parser at a real Locus and counts what the graft consumed.
             The rows come from graft.sample_defs, and the XP comes from the
             graft module, never from a literal.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.interface.popups.tests.test_locus_popup
"""

from evennia import create_object
from evennia.utils.test_resources import EvenniaCommandTest

from systems.gameplay.augmentation import constants as aug_const
from systems.gameplay.augmentation import graft as graft_service
from systems.gameplay.augmentation import graft_channel
from systems.interface.popups import service
from systems.interface.popups.popup_defs import locus as locus_popup
from systems.interface.statefeed import buffer
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import popup as popup_feed
from systems.interface.statefeed import subscriptions
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.loci import AugmentationLocus


# ─── Private constant definitions ────────────────────────────────────────────

# The stack of the first sample. More than one, so the count row shows.
_UNITS = 5


# ─── Private helper routines ─────────────────────────────────────────────────

class _LocusFixture(EvenniaCommandTest):
    """A Locus on the tile, a clean buffer, and a channel ended after."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.locus = create_object(AugmentationLocus, key="locus", location=self.room1)
        self.item_def = graft_service.sample_defs()[0]
        buffer.reset()
        self.addCleanup(buffer.reset)
        self.addCleanup(graft_channel.end_grafting, self.char1)

    def _give(self, units: int = _UNITS) -> None:
        self.item_def.create(location=self.char1, home=self.char1, quantity=units)
        self.char1.inventory.sync()

    def _units(self) -> int:
        return graft_service.units_carried(self.char1, self.item_def.name)

    def _subscribe(self) -> None:
        for session in self.char1.sessions.all():
            subscriptions.subscribe(session, feed_const.CHANNEL_CHAR_POPUP)

    def _send(self, command: str) -> None:
        self.char1.execute_cmd(command, session=self.session)

    def _open(self) -> None:
        self._subscribe()
        self._send(aug_const.GRAFT_COMMAND_KEY)

    def _snapshot(self) -> dict:
        return popup_feed.build_payload(self.char1).to_dict()

    def _rows(self) -> list:
        for grid in self._snapshot()["grids"]:
            if grid["key"] == locus_popup.SAMPLES_GRID_KEY:
                return grid["items"]

        self.fail("the Locus has no samples grid")

    def _row(self, item_def) -> dict:
        for row in self._rows():
            if row["name"] == item_def.name:
                return row

        self.fail(f"{item_def.key} has no slot")

    def _commands(self) -> list:
        return [button["command"] for button in self._snapshot()["actions"]]


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestGraftOpensTheLocus(_LocusFixture):
    """A bare `graft` at a Locus opens the pop-up for a client that draws
    one. Every other case lists the samples, as before."""

    def test_a_subscribed_session_gets_the_popup(self):
        self._open()

        self.assertTrue(service.is_open(self.char1))
        self.assertEqual(aug_const.LOCUS_POPUP_TITLE, self._snapshot()["title"])

    def test_an_unsubscribed_session_gets_no_popup(self):
        self._send(aug_const.GRAFT_COMMAND_KEY)

        self.assertFalse(service.is_open(self.char1))

    def test_no_popup_away_from_a_locus(self):
        self.locus.delete()

        self._open()

        self.assertFalse(service.is_open(self.char1))

    def test_a_walk_closes_the_popup(self):
        self._open()

        self.char1.move_to(self.room2, quiet=True)

        self.assertFalse(service.is_open(self.char1))


class TestTheSampleSlots(_LocusFixture):
    """Every sample in the game has a slot. What a slot shows follows the
    bag."""

    def test_every_sample_has_a_slot_in_item_db_order(self):
        self._open()

        expected = [item_def.name for item_def in graft_service.sample_defs()]
        drawn = [row["name"] for row in self._rows()]

        self.assertEqual(expected, drawn)

    def test_a_sample_not_carried_is_dim(self):
        self._open()

        for item_def in graft_service.sample_defs():
            with self.subTest(sample=item_def.key):
                self.assertFalse(self._row(item_def)["enabled"])

    def test_a_carried_sample_is_lit_and_shows_its_count(self):
        self._give()
        self._open()

        row = self._row(self.item_def)

        self.assertTrue(row["enabled"])
        self.assertEqual(_UNITS, row["quantity"])

    def test_the_slot_shows_the_locus_rate(self):
        self._open()

        for item_def in graft_service.sample_defs():
            xp = graft_service.def_xp(item_def, at_locus=True)

            with self.subTest(sample=item_def.key):
                self.assertIn(str(xp), self._row(item_def)["detail"])


class TestGraftingThroughTheSlot(_LocusFixture):
    """A sample slot's command, sent through the parser, grafts what it
    says."""

    def test_a_left_click_grafts_one(self):
        self._give()
        self._open()

        self._send(self._row(self.item_def)["actions"][0]["command"])

        self.assertEqual(_UNITS - 1, self._units())

    def test_every_action_names_the_sample_key(self):
        self._give()
        self._open()

        for action in self._row(self.item_def)["actions"]:
            command = action.get("command") or action.get("template", "")

            with self.subTest(label=action["label"]):
                self.assertIn(self.item_def.key, command)

    def test_a_running_count_offers_stop_and_shows_progress(self):
        self._give()
        self._open()

        self._send(f"{aug_const.GRAFT_COMMAND_KEY} {self.item_def.key} all")

        self.assertIn(aug_const.GRAFT_STOP_COMMAND, self._commands())
        self.assertIn(self.item_def.name, self._snapshot()["status"])

    def test_an_idle_locus_offers_no_stop(self):
        self._open()

        self.assertNotIn(aug_const.GRAFT_STOP_COMMAND, self._commands())
        self.assertEqual(aug_const.LOCUS_IDLE_STATUS, self._snapshot()["status"])

    def test_the_stop_button_ends_the_count(self):
        self._give()
        self._open()
        self._send(f"{aug_const.GRAFT_COMMAND_KEY} {self.item_def.key} all")

        self._send(aug_const.GRAFT_STOP_COMMAND)

        self.assertNotIn(aug_const.GRAFT_STOP_COMMAND, self._commands())
        self.assertIsNone(graft_channel.channel_report(self.char1))
