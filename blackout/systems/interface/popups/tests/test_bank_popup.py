"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: Cases for the bank pop-up: who gets it, what it shows, that every
             command it names does what it says, and when it closes.

             THE LOAD-BEARING CASES run a slot's command through the real
             command parser, with the real terminal in the room, and count
             what moved. A pop-up that names a line the parser refuses is a
             button that does nothing, and only this kind of case finds it.

             Expected amounts come from the quantity constants and from the
             items the case made, never from a literal count of the vault.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.interface.popups.tests.test_bank_popup
"""

import json
from unittest import mock

from evennia import create_object
from evennia.utils.test_resources import EvenniaCommandTest

from systems.interface.popups import constants as popup_const
from systems.interface.popups import service
from systems.interface.popups.popup_defs import bank as bank_popup
from systems.interface.statefeed import buffer
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import events
from systems.interface.statefeed import inventory as items_feed
from systems.interface.statefeed import popup as popup_feed
from systems.interface.statefeed import subscriptions
from typeclasses.bank_nodes import BankNode
from typeclasses.characters import Character as BlackoutCharacter
from world.item_database import ITEM_DB


# ─── Private constant definitions ────────────────────────────────────────────

# Stackable: one object, many units.
_DUST_KEY = "rusty_metal_dust"
_DUST_UNITS = 40

# Non-stackable: many objects, one vault slot.
_CHUNK_KEY = "rusty_metal_chunk"
_CHUNK_COUNT = 6

# An amount the X button sets, that no fixed button shows.
_CUSTOM_AMOUNT = 7


# ─── Private helper routines ─────────────────────────────────────────────────

class _BankFixture(EvenniaCommandTest):
    """A terminal in the room, a subscribed session, and a clean buffer."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.terminal = create_object(
            BankNode, key="bank terminal", location=self.room1)
        self.char1.inventory.sync()
        buffer.reset()
        self.addCleanup(buffer.reset)

    def _subscribe(self) -> None:
        for session in self.char1.sessions.all():
            subscriptions.subscribe(session, feed_const.CHANNEL_CHAR_POPUP)

    def _carry(self, key: str, count: int = 1) -> list:
        made = [ITEM_DB[key].create(location=self.char1) for _ in range(count)]
        self.char1.inventory.sync()

        return made

    def _carry_dust(self):
        dust = self._carry(_DUST_KEY)[0]
        dust.quantity = _DUST_UNITS

        return dust

    def _bank(self, items) -> None:
        self.char1.bank.deposit_many(items)

    def _open(self) -> None:
        self._subscribe()
        self.char1.execute_cmd("bank", session=self.session)

    def _snapshot(self) -> dict:
        return popup_feed.build_payload(self.char1).to_dict()

    def _grid(self, grid_key: str) -> dict:
        for grid in self._snapshot()["grids"]:
            if grid["key"] == grid_key:
                return grid

        self.fail(f"no {grid_key} grid in the snapshot")

    def _pane_row(self) -> dict:
        """The first row of the inventory PANE, as the client gets it."""
        return items_feed.build_payload(self.char1).items[0]

    def _bank_everything_carried(self) -> None:
        """Put back what a case withdrew, so the next case starts full."""
        self.char1.inventory.sync()
        carried = [obj for _slot, obj in self.char1.inventory.all_items() if obj]

        if carried:
            self._bank(carried)

    def _stored_units(self) -> int:
        return sum(int(getattr(obj, "quantity", 1) or 1)
                   for obj in self.char1.bank.list_items())

    def _carried_units(self) -> int:
        return sum(int(getattr(obj, "quantity", 1) or 1)
                   for _slot, obj in self.char1.inventory.all_items()
                   if obj is not None)

    def _send(self, command: str) -> None:
        self.char1.execute_cmd(command, session=self.session)

    def _text_of(self, command: str) -> str:
        """Send a command and return the text lines it printed, joined."""
        with mock.patch.object(self.char1, "msg") as msg:
            self._send(command)

        lines = []

        for call in msg.call_args_list:
            text = call.kwargs.get("text", call.args[0] if call.args else None)

            if isinstance(text, tuple):
                lines.append(str(text[0]))

        return "\n".join(lines)


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestChannel(EvenniaCommandTest):
    """The channel's declaration, which decides whether it can be reached."""

    def test_a_client_may_subscribe_to_it(self):
        self.assertIn(
            feed_const.CHANNEL_CHAR_POPUP, feed_const.SUBSCRIBABLE_CHANNELS)

    def test_channel_is_not_rate_capped(self):
        self.assertNotIn(
            feed_const.CHANNEL_CHAR_POPUP,
            feed_const.CHANNEL_MIN_INTERVAL_SECONDS)

    def test_nothing_open_is_the_closed_state(self):
        payload = popup_feed.build_payload(self.char1).to_dict()

        self.assertFalse(payload["open"])
        self.assertEqual([], payload["grids"])


class TestWhoGetsThePopup(_BankFixture):
    """A client that draws pop-ups gets one. Every other client gets the menu."""

    def test_a_subscribed_session_gets_the_popup_and_no_menu(self):
        self._open()

        self.assertTrue(service.is_open(self.char1))
        self.assertIsNone(self.char1.ndb._evmenu)

    def test_an_unsubscribed_session_gets_the_menu(self):
        self._send("bank")

        self.assertFalse(service.is_open(self.char1))
        self.assertIsNotNone(self.char1.ndb._evmenu)

    def test_the_open_snapshot_reaches_the_client(self):
        self._subscribe()

        with mock.patch.object(events, "emit", return_value=1) as sent:
            self._send("bank")

        channels = [call.args[1].channel for call in sent.call_args_list]
        self.assertIn(feed_const.CHANNEL_CHAR_POPUP, channels)


class TestWhatItShows(_BankFixture):
    """The vault and the inventory, in the shapes a client draws."""

    def test_a_pile_is_one_vault_slot_with_every_unit(self):
        self._bank(self._carry(_CHUNK_KEY, _CHUNK_COUNT))
        self._open()

        vault = self._grid(bank_popup.VAULT_GRID_KEY)

        self.assertEqual(1, vault["slots_total"])
        self.assertEqual(_CHUNK_COUNT, vault["items"][0]["quantity"])

    def test_the_pop_up_draws_no_copy_of_the_bag(self):
        self._carry(_CHUNK_KEY, 2)
        self._open()

        keys = [grid["key"] for grid in self._snapshot()["grids"]]

        self.assertEqual([bank_popup.VAULT_GRID_KEY], keys)

    def test_the_pane_leads_with_deposit_only_while_the_vault_is_open(self):
        self._carry_dust()
        self._open()
        mode = service.quantity_mode(self.char1, bank_popup.BANK_POPUP_KEY)
        opened = [action["label"] for action in self._pane_row()["actions"]]

        service.close_popup(self.char1)
        closed = [action["label"] for action in self._pane_row()["actions"]]

        # The pop-up's own quantity row leads: "Deposit <mode>" first, then
        # every fixed mode. The pane's plain group has no fixed modes.
        self.assertEqual(f"{bank_popup.VERB_DEPOSIT_LABEL} {mode}", opened[0])
        self.assertNotEqual(opened, closed)

    def test_the_snapshot_survives_json(self):
        self._bank([self._carry_dust()])
        self._carry(_CHUNK_KEY, 2)
        self._open()

        json.dumps(self._snapshot())

    def test_the_close_button_names_the_close_command(self):
        self._open()

        self.assertEqual(
            popup_const.POPUP_CLOSE_COMMAND, self._snapshot()["close_command"])

    def test_exactly_one_quantity_button_is_active(self):
        self._open()

        active = [button for button in self._snapshot()["quantity"]
                  if button["active"]]

        self.assertEqual(1, len(active))


class TestEveryCommandWorks(_BankFixture):
    """Each line a slot names, sent through the parser, moves what it says."""

    def test_a_left_click_withdraws_the_default_quantity(self):
        self._bank([self._carry_dust()])
        self._open()
        before = self._stored_units()

        row = self._grid(bank_popup.VAULT_GRID_KEY)["items"][0]
        self._send(row["actions"][0]["command"])

        moved = before - self._stored_units()
        self.assertEqual(popup_const.QUANTITY_DEFAULT_MODE, moved)

    def test_a_left_click_follows_the_quantity_mode(self):
        mode = popup_const.QUANTITY_FIXED_MODES[-1]
        self._bank([self._carry_dust()])
        self._open()
        self._send(f"{popup_const.POPUP_COMMAND_KEY} "
                   f"{popup_const.POPUP_ARG_QUANTITY} {mode}")
        before = self._stored_units()

        row = self._grid(bank_popup.VAULT_GRID_KEY)["items"][0]
        self._send(row["actions"][0]["command"])

        self.assertEqual(mode, before - self._stored_units())

    def test_every_whole_withdraw_moves_its_amount(self):
        self._bank([self._carry_dust()])
        self._open()
        row = self._grid(bank_popup.VAULT_GRID_KEY)["items"][0]

        for action in row["actions"]:
            command = action["command"]

            if not command:
                continue

            with self.subTest(command=command):
                before = self._stored_units()
                amount = command.rsplit(" ", 1)[-1]
                expected = before if amount == popup_const.QUANTITY_ALL \
                    else min(int(amount), before)

                self._send(command)

                self.assertEqual(expected, before - self._stored_units())
                self._bank_everything_carried()

    def test_the_x_withdraw_moves_the_typed_amount(self):
        self._bank([self._carry_dust()])
        self._open()
        row = self._grid(bank_popup.VAULT_GRID_KEY)["items"][0]
        prompted = [action for action in row["actions"] if not action["command"]]
        before = self._stored_units()

        template = prompted[0]["template"]
        self._send(template.replace(
            feed_const.ACTION_AMOUNT_PLACEHOLDER, str(_CUSTOM_AMOUNT)))

        self.assertEqual(_CUSTOM_AMOUNT, before - self._stored_units())

    def test_a_pane_left_click_deposits_the_default_quantity(self):
        self._carry_dust()
        self._open()
        before = self._carried_units()

        row = self._pane_row()
        self._send(row["actions"][0]["command"])

        moved = before - self._carried_units()
        self.assertEqual(popup_const.QUANTITY_DEFAULT_MODE, moved)

    def test_deposit_all_on_one_chunk_banks_the_whole_pile(self):
        self._carry(_CHUNK_KEY, _CHUNK_COUNT)
        self._open()
        self._send(f"{popup_const.POPUP_COMMAND_KEY} "
                   f"{popup_const.POPUP_ARG_QUANTITY} {popup_const.QUANTITY_ALL}")

        row = self._pane_row()
        self._send(row["actions"][0]["command"])

        self.assertEqual(_CHUNK_COUNT, self._stored_units())


class TestQuantityMode(_BankFixture):
    """The mode belongs to one pop-up, and it outlives the pop-up."""

    def test_a_mode_with_nothing_open_is_refused(self):
        succeeded, message = service.set_quantity_mode(self.char1, "5")

        self.assertFalse(succeeded)
        self.assertEqual(popup_const.MSG_NOTHING_OPEN, message)

    def test_a_bad_mode_is_refused_and_changes_nothing(self):
        self._open()

        for raw in ("0", "-3", "lots", "", str(popup_const.QUANTITY_MAX_CUSTOM + 1)):
            with self.subTest(raw=raw):
                succeeded, _message = service.set_quantity_mode(self.char1, raw)

                self.assertFalse(succeeded)
                self.assertEqual(
                    popup_const.QUANTITY_DEFAULT_MODE,
                    service.quantity_mode(self.char1, bank_popup.BANK_POPUP_KEY))

    def test_a_custom_mode_lights_the_x_button(self):
        self._open()
        service.set_quantity_mode(self.char1, str(_CUSTOM_AMOUNT))

        active = [button for button in self._snapshot()["quantity"]
                  if button["active"]]

        self.assertEqual(1, len(active))
        self.assertEqual(str(_CUSTOM_AMOUNT), active[0]["label"])

    def test_the_mode_survives_a_close(self):
        self._open()
        service.set_quantity_mode(self.char1, popup_const.QUANTITY_ALL)
        self._send(popup_const.POPUP_CLOSE_COMMAND)

        mode = service.quantity_mode(self.char1, bank_popup.BANK_POPUP_KEY)

        self.assertEqual(popup_const.QUANTITY_ALL, mode)


class TestItFollowsItsFacts(_BankFixture):
    """A transfer marks the pop-up stale, and the drain rebuilds it."""

    def test_a_withdraw_rebuilds_the_popup(self):
        self._bank([self._carry_dust()])
        self._open()
        buffer.reset()

        with mock.patch.object(events, "emit", return_value=1) as sent:
            self._send(f"withdraw {self.char1.bank.list_items()[0].key} 3")
            buffer.drain_stale()

        channels = [call.args[1].channel for call in sent.call_args_list]
        self.assertIn(feed_const.CHANNEL_CHAR_POPUP, channels)

    def test_nothing_is_marked_when_nothing_is_open(self):
        self._subscribe()

        self.assertFalse(events.refresh_popup(self.char1))


class TestItCloses(_BankFixture):
    """Walking away, the close command, and a lost terminal all close it."""

    def test_walking_away_closes_it(self):
        self._open()

        self.char1.move_to(self.room2, quiet=True)

        self.assertFalse(service.is_open(self.char1))

    def test_the_close_command_closes_it(self):
        self._open()

        said = self._text_of(popup_const.POPUP_CLOSE_COMMAND)

        self.assertIn("you close", said.lower())
        self.assertFalse(service.is_open(self.char1))

    def test_close_with_nothing_open_says_so(self):
        said = self._text_of(popup_const.POPUP_CLOSE_COMMAND)

        self.assertEqual(popup_const.MSG_NOTHING_OPEN, said)

    def test_a_deleted_terminal_closes_it(self):
        self._open()

        self.terminal.delete()

        self.assertFalse(self._snapshot()["open"])
        self.assertFalse(service.is_open(self.char1))

