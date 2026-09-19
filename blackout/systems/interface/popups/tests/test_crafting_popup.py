"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: Cases for the crafting pop-up and the `craft <recipe>` and
             `craft cancel` forms it rests on.

             THE LOAD-BEARING CASE sends a recipe slot's command through the
             real parser at a real station and counts what the craft consumed
             and made. Counts come from crafting_service, never from a
             literal.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.interface.popups.tests.test_crafting_popup
"""

from unittest import mock

from evennia import create_object
from evennia.utils.test_resources import EvenniaCommandTest

from systems.gameplay.crafting import craft_batch, crafting_service
from systems.interface.popups import service
from systems.interface.popups.popup_defs import crafting as crafting_popup
from systems.interface.statefeed import buffer
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import popup as popup_feed
from systems.interface.statefeed import subscriptions
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.crafting_facilities import (
    CRAFT_CANCEL_ARG,
    CRAFT_COMMAND_KEY,
    CraftingFacility,
)
from world.item_database import ITEM_DB


# ─── Private constant definitions ────────────────────────────────────────────

# One hammer and one chunk make one dust, at level 0. The same recipe the
# craft batch tests use.
_RECIPE_KEY = "rusty metal dust"
_CHUNK_KEY = "rusty_metal_chunk"
_CHUNKS = 4

# A category no recipe declares, for a station that makes nothing of ours.
_NO_SUCH_CATEGORY = "no such category"


# ─── Private helper routines ─────────────────────────────────────────────────

class _CraftFixture(EvenniaCommandTest):
    """A station that makes every recipe, a hammer, and a clean buffer."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.station = create_object(
            CraftingFacility, key="workbench", location=self.room1)
        ITEM_DB["hammer"].create(location=self.char1)
        self.char1.inventory.sync()
        buffer.reset()
        self.addCleanup(buffer.reset)
        self.addCleanup(craft_batch.cancel_batch, self.char1)

    def _give_chunks(self, count: int = _CHUNKS) -> None:
        for _ in range(count):
            ITEM_DB[_CHUNK_KEY].create(location=self.char1)

        self.char1.inventory.sync()

    def _chunks(self) -> int:
        return sum(1 for obj in self.char1.contents
                   if obj.key == ITEM_DB[_CHUNK_KEY].name)

    def _subscribe(self) -> None:
        for session in self.char1.sessions.all():
            subscriptions.subscribe(session, feed_const.CHANNEL_CHAR_POPUP)

    def _open(self) -> None:
        self._subscribe()
        self._send(CRAFT_COMMAND_KEY)

    def _send(self, command: str) -> None:
        self.char1.execute_cmd(command, session=self.session)

    def _snapshot(self) -> dict:
        return popup_feed.build_payload(self.char1).to_dict()

    def _recipe_row(self) -> dict:
        recipe_cls = crafting_service.get_recipe_class(_RECIPE_KEY)

        for grid in self._snapshot()["grids"]:
            if grid["key"] != crafting_popup.RECIPE_GRID_KEY:
                continue

            for row in grid["items"]:
                if row["name"] == recipe_cls.name:
                    return row

        self.fail("the recipe has no slot")

    def _text_of(self, command: str) -> str:
        with mock.patch.object(self.char1, "msg") as msg:
            self._send(command)

        lines = []

        for call in msg.call_args_list:
            text = call.kwargs.get("text", call.args[0] if call.args else None)

            if isinstance(text, tuple):
                lines.append(str(text[0]))

        return "\n".join(lines)


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestCraftOpensTheStation(_CraftFixture):
    """A client that draws pop-ups gets one. Every other client gets the menu."""

    def test_a_subscribed_session_gets_the_popup(self):
        self._open()

        self.assertTrue(service.is_open(self.char1))
        self.assertIsNone(self.char1.ndb._evmenu)

    def test_an_unsubscribed_session_gets_the_menu(self):
        self._send(CRAFT_COMMAND_KEY)

        self.assertIsNotNone(self.char1.ndb._evmenu)

    def test_the_station_names_the_popup(self):
        self._open()

        self.assertEqual(self.station.key, self._snapshot()["title"])

    def test_every_recipe_with_an_output_has_a_slot(self):
        self._open()

        expected = [cls.name for _key, cls in
                    crafting_service.get_recipes_for_facility(self.station)
                    if crafting_popup._output_def(cls) is not None]
        drawn = [row["name"] for row in self._snapshot()["grids"][0]["items"]]

        self.assertEqual(expected, drawn)


class TestTheRecipeSlot(_CraftFixture):
    """What a recipe slot shows follows what the player can make."""

    def test_a_recipe_without_materials_is_dim(self):
        self._open()

        self.assertFalse(self._recipe_row()["enabled"])

    def test_a_recipe_with_materials_is_lit(self):
        self._give_chunks()
        self._open()

        self.assertTrue(self._recipe_row()["enabled"])

    def test_the_missing_materials_are_on_the_tooltip(self):
        self._open()

        self.assertIn("missing", self._recipe_row()["info"].lower())


class TestCraftingThroughTheSlot(_CraftFixture):
    """A recipe slot's command, sent through the parser, crafts what it says."""

    def test_a_left_click_makes_one(self):
        self._give_chunks()
        self._open()
        before = self._chunks()

        self._send(self._recipe_row()["actions"][0]["command"])

        self.assertEqual(1, before - self._chunks())

    def test_a_recipe_the_station_does_not_make_is_refused(self):
        self._give_chunks()
        self.station.allowed_categories = [_NO_SUCH_CATEGORY]

        said = self._text_of(f"{CRAFT_COMMAND_KEY} {_RECIPE_KEY}")

        self.assertIn("cannot make", said.lower())
        self.assertEqual(_CHUNKS, self._chunks())

    def test_cancel_with_nothing_running_says_so(self):
        said = self._text_of(f"{CRAFT_COMMAND_KEY} {CRAFT_CANCEL_ARG}")

        self.assertIn("not crafting", said.lower())

    def test_a_running_batch_offers_stop(self):
        self._give_chunks()
        self._open()
        self._send(f"{CRAFT_COMMAND_KEY} {_RECIPE_KEY} all")

        commands = [button["command"] for button in self._snapshot()["actions"]]

        self.assertIn(crafting_popup.CANCEL_COMMAND, commands)

    def test_an_idle_station_offers_no_stop(self):
        self._open()

        commands = [button["command"] for button in self._snapshot()["actions"]]

        self.assertNotIn(crafting_popup.CANCEL_COMMAND, commands)
