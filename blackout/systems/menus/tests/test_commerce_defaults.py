"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/02/2026
Description: Tests for the `_default` options on the sell and deposit nodes --
             the route a graphical client's right-click takes while the
             counterparty's menu is open.

             THE FAILURE THIS PREVENTS. EvMenuCmdSet is `mergetype="Replace"`
             with `no_objs=True`, so while a menu is open nothing reaches the
             command parser -- not even a command hosted on the counterparty
             the menu was opened from. A player who clicked the merchant (which
             sends `talk`) and then right-clicked an item would have been told
             "Invalid choice". These options are the only route in.

             Two properties, and the second is the one that is easy to lose.
             The verb has to WORK. And everything that is not the verb has to
             go on being refused out loud: arming a `_default` at all
             suppresses EvMenu's own no-match line, because parse_input reaches
             the default branch instead of the else that prints it.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py systems.menus
"""

from evennia import create_object
from evennia.utils.evmenu import EvMenuGotoAbortMessage
from evennia.utils.test_resources import EvenniaTest

from systems.menus import banking_menu
from systems.menus.npc_dialogues import npc_shopkeep
from typeclasses.bank_nodes import BankNode
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.npcs import ShopkeepNPC
from world.item_database import ITEM_DB

CHUNK_KEY = "rusty_metal_chunk"
DUST_KEY = "rusty_metal_dust"


class _CommerceDefaultTest(EvenniaTest):
    """A counterparty in the room and something worth trading."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.char1.inventory.sync()

    def _pile(self, count=3, key=CHUNK_KEY):
        made = [ITEM_DB[key].create(location=self.char1) for _ in range(count)]
        self.char1.inventory.sync()

        return made

    def _slot_number(self, obj):
        return self.char1.inventory.find_slot(obj) + 1


class TestTheSellNodesDefault(_CommerceDefaultTest):

    def setUp(self):
        super().setUp()
        self.shopkeep = create_object(
            ShopkeepNPC, key="Shopkeeper", location=self.room1)
        self.shopkeep.db.shopdef_key = "oasis_shop"

    def test_the_node_arms_a_default_option(self):
        _text, options = npc_shopkeep.node_sell(self.char1, "")
        keys = [opt.get("key") for opt in options]

        self.assertIn("_default", keys)

    def test_the_verb_sells_the_slot_it_names(self):
        pile = self._pile()
        target = pile[-1]
        typed = f"sell {self._slot_number(target)}"

        npc_shopkeep._parse_sell_request(
            self.char1, typed, npc=self.shopkeep)

        self.assertEqual(target.location, self.shopkeep)

    def test_it_returns_to_the_sell_list(self):
        pile = self._pile()
        typed = f"sell {self._slot_number(pile[0])}"

        node, _kwargs = npc_shopkeep._parse_sell_request(
            self.char1, typed, npc=self.shopkeep)

        self.assertEqual(node, "node_sell")

    def test_a_stale_page_is_not_handed_back_to_the_node(self):
        # list_node injects the CURRENT page into every goto's kwargs, and its
        # own merge lets an inherited one win -- so a page built before the
        # sale would be re-rendered after it.
        pile = self._pile()
        typed = f"sell {self._slot_number(pile[0])}"

        _node, kwargs = npc_shopkeep._parse_sell_request(
            self.char1, typed, npc=self.shopkeep,
            available_choices=["a stale row"])

        self.assertNotIn("available_choices", kwargs)

    def test_anything_else_is_still_refused_out_loud(self):
        with self.assertRaises(EvMenuGotoAbortMessage):
            npc_shopkeep._parse_sell_request(
                self.char1, "banana", npc=self.shopkeep)

    def test_a_bare_number_is_not_claimed(self):
        # EvMenu matches explicit options before _default, so a bare "7" never
        # reaches here -- but if it ever does, it must not be mistaken for a
        # sell request.
        with self.assertRaises(EvMenuGotoAbortMessage):
            npc_shopkeep._parse_sell_request(
                self.char1, "7", npc=self.shopkeep)


class TestTheDepositNodesDefault(_CommerceDefaultTest):

    def setUp(self):
        super().setUp()
        self.bank_node = create_object(
            BankNode, key="bank terminal", location=self.room1)

    def test_the_node_arms_a_default_option(self):
        _text, options = banking_menu.node_deposit_select(self.char1)
        keys = [opt.get("key") for opt in options]

        self.assertIn("_default", keys)

    def test_the_verb_banks_the_slot_it_names(self):
        pile = self._pile()
        target = pile[-1]
        typed = f"deposit {self._slot_number(target)}"

        banking_menu._parse_deposit_request(self.char1, typed)

        stored = {obj.id for obj in self.char1.bank.list_items()}
        self.assertIn(target.id, stored)

    def test_it_returns_to_the_deposit_list(self):
        pile = self._pile()
        typed = f"deposit {self._slot_number(pile[0])}"

        node, _kwargs = banking_menu._parse_deposit_request(self.char1, typed)

        self.assertEqual(node, banking_menu.DEPOSIT_FLOW.select_node)

    def test_a_quantity_is_honoured(self):
        stack = ITEM_DB[DUST_KEY].create(location=self.char1, quantity=6)
        self.char1.inventory.sync()
        typed = f"deposit {self._slot_number(stack)} 2"

        banking_menu._parse_deposit_request(self.char1, typed)

        self.assertEqual(stack.db.quantity, 4)

    def test_anything_else_is_still_refused_out_loud(self):
        with self.assertRaises(EvMenuGotoAbortMessage):
            banking_menu._parse_deposit_request(self.char1, "banana")


class TestBothMenusCloseOnTheWalk(_CommerceDefaultTest):
    """A shop counter and a vault are things you STAND at."""

    def test_the_shop_menu_declares_itself_room_bound(self):
        self.assertTrue(getattr(npc_shopkeep, "ROOM_BOUND", False))

    def test_the_bank_menu_declares_itself_room_bound(self):
        self.assertTrue(getattr(banking_menu, "ROOM_BOUND", False))

    def test_a_room_bound_menu_is_closed_by_a_move(self):
        from systems.menus.base_menu import start_blackout_menu

        keep = create_object(ShopkeepNPC, key="Shopkeeper", location=self.room1)
        keep.db.shopdef_key = "oasis_shop"
        start_blackout_menu(
            self.char1, "systems.menus.npc_dialogues.npc_shopkeep",
            startnode="start", npc=keep,
        )
        self.assertIsNotNone(self.char1.ndb._evmenu)

        self.char1.move_to(self.room2, quiet=True)

        self.assertIsNone(self.char1.ndb._evmenu)

    def test_a_menu_that_is_not_room_bound_survives_a_move(self):
        from systems.menus.base_menu import start_blackout_menu

        start_blackout_menu(
            self.char1, "systems.menus.skills_menu", startnode="start")
        self.assertIsNotNone(self.char1.ndb._evmenu)

        self.char1.move_to(self.room2, quiet=True)

        self.assertIsNotNone(self.char1.ndb._evmenu)


class TestTheDepositMenuReachesWornItems(_CommerceDefaultTest):
    """The menu and the command must agree about what is bankable.

    EquipmentHandler.equip holds an equipped object at location=None, so the
    menu's list, its dbid lookup and its transfer all had to widen together --
    listing a worn item that the next node cannot re-resolve reads to the
    player as the item vanishing between two screens.
    """

    def setUp(self):
        super().setUp()
        self.bank_node = create_object(
            BankNode, key="bank terminal", location=self.room1)
        self.weapon = ITEM_DB["rusty_scrap_shortsword"].create(
            location=self.char1)
        self.char1.inventory.sync()
        self.char1.equipment.equip(self.weapon)

    def test_a_worn_item_is_listed(self):
        _text, options = banking_menu.node_deposit_select(self.char1)
        descs = [opt.get("desc", "") for opt in options]

        self.assertTrue(any(self.weapon.key in d for d in descs), descs)

    def test_a_worn_item_is_marked_as_equipped(self):
        # _equipped_marker decorated a list that could never contain an
        # equipped item until this widened. This is what makes it live code.
        _text, options = banking_menu.node_deposit_select(self.char1)
        descs = [opt.get("desc", "") for opt in options]
        worn = [d for d in descs if self.weapon.key in d]

        self.assertTrue(any("equipped" in d for d in worn), worn)

    def test_a_worn_item_still_resolves_a_node_later(self):
        found = banking_menu._find_carried(self.char1, self.weapon.id)

        self.assertEqual(found, self.weapon)

    def test_depositing_it_clears_the_equipment_slot(self):
        slot = self.char1.equipment.get_current_slot(self.weapon)

        banking_menu._do_deposit(self.char1, [self.weapon], 1)

        self.assertIsNone(self.char1.equipment.slots.get(slot))
        stored = {obj.id for obj in self.char1.bank.list_items()}
        self.assertIn(self.weapon.id, stored)
