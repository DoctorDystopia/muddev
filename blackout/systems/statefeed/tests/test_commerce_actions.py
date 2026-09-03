"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/02/2026
Description: Tests for the contextual Sell and Deposit actions on an
             inventory row, and for the contract every action in the payload
             has to satisfy.

             Three things are guarded.

             CONTEXT. The actions are a fact about the ROOM, so they must be
             absent with no counterparty, present with one, and independent
             of each other -- a bank terminal must not conjure a Sell.

             THE PROMPT CONTRACT. An action carries either a non-empty
             `command` or a `template` plus an `input`, never both and never
             neither. The empty command is what makes a prompted action
             degrade safely on a client that has not learned about `input`:
             it shows the entry and does nothing, instead of sending a
             literal "{amount}" at the parser.

             THE TELNET GUARANTEE. Every command template in the payload has
             to name a real Command. "The pane sends only what a telnet
             player could type" is the contract the whole graphical client
             rests on, and until now it was held by convention alone.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py systems.statefeed
"""

from evennia import create_object
from evennia.utils.test_resources import EvenniaTest

from systems.shop.shop_service import _is_sellable
from systems.statefeed import commerce
from systems.statefeed import constants as const
from systems.statefeed import inventory as feed_inventory
from typeclasses.bank_nodes import BankNode
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.items import BaseItem
from typeclasses.npcs import ShopkeepNPC
from world.item_database import ITEM_DB

# Non-stackable and worth something, so it is sellable and offers one verb.
CHUNK_KEY = "rusty_metal_chunk"

# Stackable, so a stack of it offers the three-verb group and a prompt.
DUST_KEY = "rusty_metal_dust"

EQUIPPABLE_KEY = "glass_cannon_amulet"

STACK_SIZE = 6


# ─── Private helper routines ─────────────────────────────────────────────────

def _row_for(payload, name):
    for row in payload.items:
        if row["name"] == name:
            return row

    return None


def _labels(row):
    return [action["label"] for action in row["actions"]]


def _commands(row):
    return [action["command"] for action in row["actions"]]


def _every_action(payload):
    """Every action dict in a payload, carried and worn."""
    actions = []

    for row in list(payload.items) + list(payload.equipped):
        actions.extend(row["actions"])

    return actions


# ─── Test cases ──────────────────────────────────────────────────────────────

class CommerceActionTestBase(EvenniaTest):
    """A character who can be given a counterparty, or not."""

    character_typeclass = BlackoutCharacter

    def _carry(self, item_key=CHUNK_KEY, quantity=1):
        obj = ITEM_DB[item_key].create(location=self.char1, quantity=quantity)
        self.char1.inventory.sync()

        return obj

    def _add_shopkeep(self):
        keep = create_object(
            ShopkeepNPC, key="Shopkeeper", location=self.char1.location)
        keep.db.shopdef_key = "oasis_shop"

        return keep

    def _add_bank(self):
        return create_object(
            BankNode, key="bank terminal", location=self.char1.location)

    def _payload(self):
        return feed_inventory.build_payload(self.char1)


class TestTheRoomDecides(CommerceActionTestBase):

    def test_no_counterparty_offers_neither_verb(self):
        item = self._carry()

        row = _row_for(self._payload(), item.key)

        labels = _labels(row)
        self.assertNotIn(const.INVENTORY_ACTION_SELL[0], labels)
        self.assertNotIn(const.INVENTORY_ACTION_DEPOSIT[0], labels)

    def test_a_shopkeeper_offers_sell(self):
        item = self._carry()
        self._add_shopkeep()

        row = _row_for(self._payload(), item.key)

        self.assertIn(const.INVENTORY_ACTION_SELL[0], _labels(row))

    def test_a_shopkeeper_alone_does_not_offer_deposit(self):
        item = self._carry()
        self._add_shopkeep()

        row = _row_for(self._payload(), item.key)

        self.assertNotIn(const.INVENTORY_ACTION_DEPOSIT[0], _labels(row))

    def test_a_bank_offers_deposit(self):
        item = self._carry()
        self._add_bank()

        row = _row_for(self._payload(), item.key)

        self.assertIn(const.INVENTORY_ACTION_DEPOSIT[0], _labels(row))

    def test_a_bank_alone_does_not_offer_sell(self):
        item = self._carry()
        self._add_bank()

        row = _row_for(self._payload(), item.key)

        self.assertNotIn(const.INVENTORY_ACTION_SELL[0], _labels(row))

    def test_both_counterparties_offer_both_verbs(self):
        item = self._carry()
        self._add_shopkeep()
        self._add_bank()

        labels = _labels(_row_for(self._payload(), item.key))

        self.assertIn(const.INVENTORY_ACTION_SELL[0], labels)
        self.assertIn(const.INVENTORY_ACTION_DEPOSIT[0], labels)

    def test_commerce_sits_above_drop(self):
        """Drop is the destructive neighbour and stays at the bottom, where
        the hand expects it."""
        item = self._carry()
        self._add_shopkeep()
        labels = _labels(_row_for(self._payload(), item.key))

        drop_label = const.INVENTORY_ACTION_DROP[0]

        self.assertLess(
            labels.index(const.INVENTORY_ACTION_SELL[0]),
            labels.index(drop_label),
        )


class TestWhatTheShopWillNotBuy(CommerceActionTestBase):
    """Asserted against _is_sellable, never against a list of item keys, so
    content added tomorrow is covered with no edit here."""

    def _unsellable_row(self, key, attribute, value):
        obj = create_object(BaseItem, key=key, location=self.char1)
        obj.attributes.add(attribute, value)
        self.char1.inventory.sync()
        self._add_shopkeep()

        self.assertFalse(_is_sellable(obj))

        return _row_for(self._payload(), obj.key)

    def test_an_untradeable_row_carries_no_sell(self):
        row = self._unsellable_row("bound relic", "tradeable", False)

        self.assertNotIn(const.INVENTORY_ACTION_SELL[0], _labels(row))

    def test_a_worthless_row_carries_no_sell(self):
        row = self._unsellable_row("scrap of nothing", "value", 0)

        self.assertNotIn(const.INVENTORY_ACTION_SELL[0], _labels(row))

    def test_an_unsellable_row_still_carries_deposit(self):
        """The two refusals are independent: a bank takes what a shop will
        not buy."""
        obj = create_object(BaseItem, key="bound relic", location=self.char1)
        obj.attributes.add("tradeable", False)
        self.char1.inventory.sync()
        self._add_shopkeep()
        self._add_bank()

        labels = _labels(_row_for(self._payload(), obj.key))

        self.assertNotIn(const.INVENTORY_ACTION_SELL[0], labels)
        self.assertIn(const.INVENTORY_ACTION_DEPOSIT[0], labels)

    def test_currency_carries_no_sell(self):
        self._add_shopkeep()
        credits = ITEM_DB["credits"].create(location=self.char1, quantity=50)
        self.char1.inventory.sync()

        row = _row_for(self._payload(), credits.key)

        self.assertNotIn(const.INVENTORY_ACTION_SELL[0], _labels(row))


class TestQuantityDecidesHowManyVerbs(CommerceActionTestBase):

    def test_a_single_unit_offers_one_bare_verb(self):
        """Nobody wants "Sell All" on one sword."""
        item = self._carry()
        self._add_shopkeep()
        labels = _labels(_row_for(self._payload(), item.key))

        self.assertIn(const.INVENTORY_ACTION_SELL[0], labels)
        self.assertNotIn(const.INVENTORY_ACTION_SELL_ALL[0], labels)
        self.assertNotIn(const.INVENTORY_ACTION_SELL_SOME_LABEL, labels)

    def test_a_stack_offers_one_some_and_all(self):
        item = self._carry(DUST_KEY, quantity=STACK_SIZE)
        self._add_shopkeep()
        labels = _labels(_row_for(self._payload(), item.key))

        self.assertIn(const.INVENTORY_ACTION_SELL_ONE[0], labels)
        self.assertIn(const.INVENTORY_ACTION_SELL_SOME_LABEL, labels)
        self.assertIn(const.INVENTORY_ACTION_SELL_ALL[0], labels)
        self.assertNotIn(const.INVENTORY_ACTION_SELL[0], labels)

    def test_a_stack_offers_the_same_three_for_deposit(self):
        item = self._carry(DUST_KEY, quantity=STACK_SIZE)
        self._add_bank()
        labels = _labels(_row_for(self._payload(), item.key))

        self.assertIn(const.INVENTORY_ACTION_DEPOSIT_ONE[0], labels)
        self.assertIn(const.INVENTORY_ACTION_DEPOSIT_SOME_LABEL, labels)
        self.assertIn(const.INVENTORY_ACTION_DEPOSIT_ALL[0], labels)


class TestThePromptContract(CommerceActionTestBase):

    def _prompted(self, label):
        item = self._carry(DUST_KEY, quantity=STACK_SIZE)
        self._add_shopkeep()
        self._add_bank()
        row = _row_for(self._payload(), item.key)

        for action in row["actions"]:
            if action["label"] == label:
                return row, action

        self.fail(f"no {label!r} action on the row")

    def test_a_prompted_action_sends_an_empty_command(self):
        """The whole safety property: an old client shows the entry and does
        nothing, rather than sending a literal placeholder at the parser."""
        _row, action = self._prompted(const.INVENTORY_ACTION_SELL_SOME_LABEL)

        self.assertEqual(action["command"], "")

    def test_a_prompted_action_carries_the_amount_placeholder(self):
        _row, action = self._prompted(const.INVENTORY_ACTION_SELL_SOME_LABEL)

        self.assertIn(const.ACTION_AMOUNT_PLACEHOLDER, action["template"])

    def test_a_prompted_template_has_its_slot_already_filled(self):
        """Only the AMOUNT is left to the client. The slot is the server's."""
        row, action = self._prompted(const.INVENTORY_ACTION_SELL_SOME_LABEL)

        slot_number = row["slot"] + 1
        self.assertIn(str(slot_number), action["template"])

    def test_a_prompted_input_names_a_known_kind(self):
        _row, action = self._prompted(const.INVENTORY_ACTION_SELL_SOME_LABEL)

        kind = action["input"][const.ACTION_INPUT_KIND_KEY]
        self.assertEqual(kind, const.ACTION_INPUT_KIND_QUANTITY)

    def test_a_prompted_input_max_is_what_the_verb_can_reach(self):
        """For a lone stack that IS the row's quantity. It stops being so the
        moment the item is a non-stackable held in several slots -- see
        TestNonStackableGroups."""
        row, action = self._prompted(const.INVENTORY_ACTION_SELL_SOME_LABEL)

        self.assertEqual(
            action["input"][const.ACTION_INPUT_MAX_KEY], row["quantity"])

    def test_a_prompted_input_never_bottoms_out_at_zero(self):
        _row, action = self._prompted(const.INVENTORY_ACTION_SELL_SOME_LABEL)

        self.assertEqual(
            action["input"][const.ACTION_INPUT_MIN_KEY],
            const.ACTION_INPUT_MIN_AMOUNT,
        )

    def test_a_prompted_input_asks_a_question(self):
        _row, action = self._prompted(const.INVENTORY_ACTION_DEPOSIT_SOME_LABEL)

        label = action["input"][const.ACTION_INPUT_LABEL_KEY]
        self.assertTrue(label.strip())

    def test_every_action_is_exactly_one_of_the_two_shapes(self):
        """Never both, never neither -- across every row a busy inventory
        produces, not just the prompted ones."""
        self._carry()
        self._carry(DUST_KEY, quantity=STACK_SIZE)
        equippable = self._carry(EQUIPPABLE_KEY)
        self.char1.equipment.equip(equippable)
        self._add_shopkeep()
        self._add_bank()

        for action in _every_action(self._payload()):
            with self.subTest(label=action["label"]):
                has_command = bool(action["command"])
                has_prompt = "input" in action

                self.assertNotEqual(
                    has_command, has_prompt,
                    "an action must carry a command OR a prompt, not both "
                    "and not neither",
                )

                if has_prompt:
                    self.assertIn("template", action)


class TestWornRows(CommerceActionTestBase):

    def _worn_row(self):
        item = self._carry(EQUIPPABLE_KEY)
        self.char1.equipment.equip(item)

        for row in self._payload().equipped:
            if row["name"] == item.key:
                return row

        self.fail("the equipped item produced no worn row")

    def test_a_worn_row_offers_deposit_beside_a_bank(self):
        """CmdDeposit clears the slot before banking, so this is reachable --
        which is exactly what its docstring has always promised."""
        self._add_bank()

        self.assertIn(const.EQUIPMENT_ACTION_DEPOSIT[0], _labels(self._worn_row()))

    def test_a_worn_row_never_offers_sell(self):
        """An unequipped deposit is undone by `withdraw`; a sale at the miser
        factor is not, and worn gear is what a misclick most wants back."""
        self._add_shopkeep()
        self._add_bank()
        labels = _labels(self._worn_row())

        self.assertNotIn(const.INVENTORY_ACTION_SELL[0], labels)
        self.assertNotIn(const.INVENTORY_ACTION_SELL_ALL[0], labels)

    def test_a_worn_row_offers_no_deposit_without_a_bank(self):
        self._add_shopkeep()

        self.assertNotIn(
            const.EQUIPMENT_ACTION_DEPOSIT[0], _labels(self._worn_row()))


class TestTheCommerceContext(CommerceActionTestBase):

    def test_an_observer_with_no_room_offers_nothing(self):
        loose = create_object(BaseItem, key="floating thing")

        context = commerce.build_context(loose)

        self.assertFalse(context.offers_anything())

    def test_a_counterparty_is_recognised_by_its_declared_role(self):
        keep = self._add_shopkeep()
        bank = self._add_bank()

        self.assertTrue(commerce.is_counterparty(keep))
        self.assertTrue(commerce.is_counterparty(bank))

    def test_an_ordinary_object_is_not_a_counterparty(self):
        obj = create_object(BaseItem, key="rock", location=self.char1.location)

        self.assertFalse(commerce.is_counterparty(obj))

    def test_the_observer_is_never_their_own_counterparty(self):
        self.char1.commerce_role = const.COMMERCE_ROLE_SHOP

        context = commerce.build_context(self.char1)

        self.assertIsNone(context.shopkeep)

    def test_an_unknown_role_is_ignored(self):
        """A role the constants do not name is a typo, and a typo must not
        silently become a counterparty."""
        obj = create_object(BaseItem, key="odd thing", location=self.char1.location)
        obj.commerce_role = "smuggler"

        self.assertFalse(commerce.is_counterparty(obj))


class TestEveryTemplateNamesARealCommand(CommerceActionTestBase):
    """The telnet guarantee, as a test rather than as a convention.

    "The pane sends only what a telnet player could type" is what lets the
    graphical client have no privileged channel, and therefore what keeps
    every lock, permission and cooldown working with no audit. Until now
    nothing checked it.

    Read over the payload rather than over the constants table, so a template
    added without a command fails here even if it is never named in this
    module.
    """

    def _known_verbs(self):
        """Every command key a payload template is allowed to open with.

        Read off the CLASSES, never typed as strings, which is the whole
        point: a template whose verb was renamed on the command but not in
        constants.py fails here rather than at a player.

        `look` and `drop` are Evennia's own defaults; they are imported all
        the same, for the same reason.
        """
        from evennia.commands.default.general import CmdDrop, CmdLook

        from commands.equipment_cmds import CmdEquipment, CmdUnequip
        from commands.inventory_cmds import CmdInventory, CmdSwap
        from typeclasses.bank_nodes import CmdDeposit
        from typeclasses.npcs import CmdSell

        commands = (
            CmdDrop, CmdLook, CmdEquipment, CmdUnequip, CmdInventory,
            CmdSwap, CmdDeposit, CmdSell,
        )

        return {cls.key for cls in commands}

    def test_every_command_opens_with_a_real_verb(self):
        self._carry()
        self._carry(DUST_KEY, quantity=STACK_SIZE)
        equippable = self._carry(EQUIPPABLE_KEY)
        self.char1.equipment.equip(equippable)
        self._add_shopkeep()
        self._add_bank()
        known = self._known_verbs()

        for action in _every_action(self._payload()):
            command = action["command"] or action.get("template", "")

            with self.subTest(label=action["label"], command=command):
                verb = command.split()[0]
                self.assertIn(verb, known)

    def test_the_sell_template_names_the_shopkeeps_own_command(self):
        from typeclasses.npcs import CmdSell

        for _label, template in (
            const.INVENTORY_ACTION_SELL,
            const.INVENTORY_ACTION_SELL_ONE,
            const.INVENTORY_ACTION_SELL_ALL,
        ):
            with self.subTest(template=template):
                self.assertTrue(template.startswith(CmdSell.key + " "))

        self.assertTrue(
            const.INVENTORY_SELL_SOME_TEMPLATE.startswith(CmdSell.key + " "))

    def test_the_deposit_template_names_the_terminals_own_command(self):
        from typeclasses.bank_nodes import CmdDeposit

        for _label, template in (
            const.INVENTORY_ACTION_DEPOSIT,
            const.INVENTORY_ACTION_DEPOSIT_ONE,
            const.INVENTORY_ACTION_DEPOSIT_ALL,
            const.EQUIPMENT_ACTION_DEPOSIT,
        ):
            with self.subTest(template=template):
                self.assertTrue(template.startswith(CmdDeposit.key + " "))

        self.assertTrue(
            const.INVENTORY_DEPOSIT_SOME_TEMPLATE.startswith(
                CmdDeposit.key + " "))


class TestNonStackableGroups(CommerceActionTestBase):
    """Eight separate rusty metal chunks offer 1 / X / All, same as a stack.

    The number that decides this is the GROUP's unit total, not the row's
    `quantity` -- which stays 1 per object, because it is what the pane draws
    in the corner of each frame and eight cells reading "x8" would say the
    player has sixty-four.
    """

    def _pile(self, count=4):
        made = [ITEM_DB[CHUNK_KEY].create(location=self.char1)
                for _ in range(count)]
        self.char1.inventory.sync()

        return made

    def test_each_copy_offers_the_three_verb_group(self):
        self._pile()
        self._add_shopkeep()
        payload = self._payload()
        chunk_rows = [r for r in payload.items
                      if r["name"] == ITEM_DB[CHUNK_KEY].name]

        self.assertEqual(len(chunk_rows), 4)

        for row in chunk_rows:
            with self.subTest(slot=row["slot"]):
                labels = _labels(row)
                self.assertIn(const.INVENTORY_ACTION_SELL_ONE[0], labels)
                self.assertIn(const.INVENTORY_ACTION_SELL_SOME_LABEL, labels)
                self.assertIn(const.INVENTORY_ACTION_SELL_ALL[0], labels)

    def test_the_rows_own_quantity_stays_one(self):
        """The trap this avoids: a group total written into `quantity` makes
        the pane draw x4 on all four cells."""
        self._pile()
        self._add_shopkeep()
        chunk_rows = [r for r in self._payload().items
                      if r["name"] == ITEM_DB[CHUNK_KEY].name]

        for row in chunk_rows:
            with self.subTest(slot=row["slot"]):
                self.assertEqual(row["quantity"], 1)

    def test_the_prompt_is_bounded_by_the_group_not_the_row(self):
        self._pile()
        self._add_shopkeep()
        row = _row_for(self._payload(), ITEM_DB[CHUNK_KEY].name)
        prompted = [a for a in row["actions"]
                    if a["label"] == const.INVENTORY_ACTION_SELL_SOME_LABEL]

        maximum = prompted[0]["input"][const.ACTION_INPUT_MAX_KEY]
        self.assertEqual(maximum, 4)
        self.assertNotEqual(maximum, row["quantity"])

    def test_a_lone_non_stackable_still_offers_one_bare_verb(self):
        self._carry(EQUIPPABLE_KEY)
        self._add_shopkeep()
        row = _row_for(self._payload(), ITEM_DB[EQUIPPABLE_KEY].name)
        labels = _labels(row)

        self.assertIn(const.INVENTORY_ACTION_SELL[0], labels)
        self.assertNotIn(const.INVENTORY_ACTION_SELL_ALL[0], labels)

    def test_the_group_total_agrees_with_what_the_command_would_reach(self):
        """The prompt's bound and the sale's reach are one fact. Asserted
        against group_units rather than against a literal, so a change to the
        grouping rule fails here rather than silently offering to sell more
        than `sell <slot> all` takes."""
        from commands.inventory_cmds import group_units

        pile = self._pile()
        self._add_shopkeep()
        row = _row_for(self._payload(), ITEM_DB[CHUNK_KEY].name)
        prompted = [a for a in row["actions"]
                    if a["label"] == const.INVENTORY_ACTION_SELL_SOME_LABEL]

        self.assertEqual(
            prompted[0]["input"][const.ACTION_INPUT_MAX_KEY],
            group_units(self.char1, pile[0]),
        )

    def test_deposit_groups_the_same_way(self):
        self._pile()
        self._add_bank()
        labels = _labels(_row_for(self._payload(), ITEM_DB[CHUNK_KEY].name))

        self.assertIn(const.INVENTORY_ACTION_DEPOSIT_ONE[0], labels)
        self.assertIn(const.INVENTORY_ACTION_DEPOSIT_SOME_LABEL, labels)
        self.assertIn(const.INVENTORY_ACTION_DEPOSIT_ALL[0], labels)

    def test_two_different_items_do_not_pool(self):
        self._pile(count=2)
        self._carry(EQUIPPABLE_KEY)
        self._add_shopkeep()
        row = _row_for(self._payload(), ITEM_DB[EQUIPPABLE_KEY].name)

        self.assertIn(const.INVENTORY_ACTION_SELL[0], _labels(row))
