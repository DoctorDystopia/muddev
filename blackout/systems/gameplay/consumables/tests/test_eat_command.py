"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Tests for the `eat` command and the Eat affordance the inventory
             feed sends a graphical client.

             The two belong in one file because they are two halves of one
             promise: the pane offers Eat on exactly what the command accepts.
             If they ever disagree, a right-click offers an action the server
             then refuses, which is the failure mode a client verb table
             produces and which this repo has deleted two of.

Run with:
    evennia test --settings test_settings.py systems.gameplay.consumables
"""



from evennia.utils.test_resources import EvenniaCommandTest

from commands.consumable_cmds import CmdEat
from systems.gameplay.consumables import constants as consumable_const
from systems.gameplay.consumables import service as consumables
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import inventory as feed_inventory
from typeclasses.characters import Character as BlackoutCharacter
from world.item_database import ITEM_DB



# Private constant definitions

_CHUCK = "mutant_raider_cured_chuck"



class EatCommandTestBase(EvenniaCommandTest):
    """A character with room in the bar to be healed."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.char1.db.max_hp = 20
        self.char1.hp = 10

    def _give(self, item_key):
        """Place an item so it occupies a real inventory slot.

        move_to rather than create(location=...): CLAUDE.md gotcha 5 -- only
        move_to fires at_object_receive, and that hook is what registers the
        item in the grid. A test that skipped it could not then address the item
        by slot number, which is the form the pane sends.
        """
        item = ITEM_DB[item_key].create()
        item.move_to(self.char1, quiet=True)

        return item

    def _eat(self, argument):
        return self.call(CmdEat(), argument)

    def _carried_named(self, item_name):
        return [obj for obj in self.char1.contents if obj.db_key == item_name]



class TestEatCommand(EatCommandTestBase):
    """What a player can type, and what they are told."""

    def test_eating_by_name_works(self):
        self._give(_CHUCK)

        self._eat("cured chuck")

        self.assertEqual(self._carried_named(ITEM_DB[_CHUCK].name), [])

    def test_eating_by_slot_number_works(self):
        """The form the graphical pane sends.

        INVENTORY_ACTION_EAT is `eat {slot}`, so this is the path a right-click
        actually takes -- and the reason it is a slot is that three identical
        cured chucks are a real inventory.
        """
        self._give(_CHUCK)
        slot = self.char1.inventory.find_slot(
            self._carried_named(ITEM_DB[_CHUCK].name)[0]
        )

        self._eat(str(slot + 1))

        self.assertEqual(self._carried_named(ITEM_DB[_CHUCK].name), [])

    def test_eating_heals(self):
        self._give(_CHUCK)
        before = self.char1.hp

        self._eat("cured chuck")

        self.assertEqual(
            self.char1.hp, before + ITEM_DB[_CHUCK].heal_amount
        )

    def test_eating_reports_the_heal(self):
        self._give(_CHUCK)

        response = self._eat("cured chuck")

        self.assertIn("eat", response.lower())
        self.assertIn("hit points", response.lower())

    def test_eating_at_full_health_says_it_did_nothing(self):
        """Allowed, and the player is told plainly that they wasted it."""
        self.char1.hp = self.char1.max_hp
        self._give(_CHUCK)

        response = self._eat("cured chuck")

        self.assertIn("no good", response.lower())

    def test_eating_with_no_argument_asks_what(self):
        response = self._eat("")

        self.assertIn("eat what", response.lower())

    def test_eating_something_inedible_is_refused(self):
        self._give("rusty_metal_chunk")

        response = self._eat("rusty metal chunk")

        self.assertIn("cannot eat", response.lower())
        self.assertEqual(
            len(self._carried_named(ITEM_DB["rusty_metal_chunk"].name)), 1
        )

    def test_eating_something_not_carried_is_refused(self):
        response = self._eat("cured chuck")

        self.assertNotIn("hit points", response.lower())

    def test_a_second_bite_too_soon_is_refused(self):
        """Addressed by SLOT, not by name, and that is not incidental.

        Two identical cured chucks cannot be named: `eat cured chuck` hits
        Evennia's own "More than one match" list, whose suggested forms
        ("chuck-1", "chuck-2") are search ordinals naming no row the pane drew.
        That is the bug that made Inspect and deposit slot-addressed on
        09/11/2026, and it is why INVENTORY_ACTION_EAT sends a slot.
        """
        self._give(_CHUCK)
        self._give(_CHUCK)
        slots = [
            self.char1.inventory.find_slot(item) + 1
            for item in self._carried_named(ITEM_DB[_CHUCK].name)
        ]

        self._eat(str(slots[0]))
        response = self._eat(str(slots[1]))

        self.assertIn("swallowing", response.lower())
        self.assertEqual(len(self._carried_named(ITEM_DB[_CHUCK].name)), 1)



class TestEatAffordance(EatCommandTestBase):
    """The Eat action the inventory feed sends, and what it is gated on."""

    def _rows(self):
        """The carried-grid rows the pane draws from."""
        payload = feed_inventory.build_payload(self.char1)

        return payload.items

    def _actions_for(self, item_name):
        for row in self._rows():
            if row["name"] == item_name:
                return [action["label"] for action in row["actions"]]

        return []

    def test_food_offers_an_eat_action(self):
        self._give(_CHUCK)

        labels = self._actions_for(ITEM_DB[_CHUCK].name)

        self.assertIn(feed_const.INVENTORY_ACTION_EAT[0], labels)

    def test_an_ordinary_item_offers_no_eat_action(self):
        """The pane must not offer a verb the server would refuse."""
        self._give("rusty_metal_chunk")

        labels = self._actions_for(ITEM_DB["rusty_metal_chunk"].name)

        self.assertNotIn(feed_const.INVENTORY_ACTION_EAT[0], labels)

    def test_the_eat_command_sent_names_a_slot(self):
        """`eat 3`, never `eat mutant raider cured chuck`.

        A name is a command whose target the pane cannot predict, which is the
        bug that made Inspect and deposit slot-addressed on 09/11/2026.
        """
        self._give(_CHUCK)

        command = None
        for row in self._rows():
            if row["name"] != ITEM_DB[_CHUCK].name:
                continue
            for action in row["actions"]:
                if action["label"] == feed_const.INVENTORY_ACTION_EAT[0]:
                    command = action["command"]

        self.assertIsNotNone(command)
        self.assertTrue(command.startswith("eat "))
        self.assertTrue(command.split(" ", 1)[1].isdigit())

    def test_the_offered_command_actually_works(self):
        """The whole point of the pair: the pane's verb is a real one.

        Sends exactly the string the feed served, rather than one this test
        composed, so a divergence between the template and the command fails
        here rather than at a player's right-click.
        """
        self._give(_CHUCK)

        command = None
        for row in self._rows():
            if row["name"] != ITEM_DB[_CHUCK].name:
                continue
            for action in row["actions"]:
                if action["label"] == feed_const.INVENTORY_ACTION_EAT[0]:
                    command = action["command"]

        argument = command.split(" ", 1)[1]
        self._eat(argument)

        self.assertEqual(self._carried_named(ITEM_DB[_CHUCK].name), [])

    def test_the_affordance_and_the_service_agree(self):
        """One owner for "is this edible".

        The pane's gate and the command's refusal both read
        consumables.is_edible, so this asserts they are the same question
        rather than two that happen to agree today.
        """
        food = self._give(_CHUCK)
        chunk = self._give("rusty_metal_chunk")

        self.assertTrue(consumables.is_edible(food))
        self.assertFalse(consumables.is_edible(chunk))

        food_labels = self._actions_for(ITEM_DB[_CHUCK].name)
        chunk_labels = self._actions_for(ITEM_DB["rusty_metal_chunk"].name)
        eat_label = feed_const.INVENTORY_ACTION_EAT[0]

        self.assertIn(eat_label, food_labels)
        self.assertNotIn(eat_label, chunk_labels)
