"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/20/2026
Description: Conformance tests for the interfaces combat duck-types on.

This is the point of systems/combat/protocols.py. The contracts themselves are
just declarations; what makes them useful is that every implementation is
checked against them here, so forgetting one is a failing test rather than an
NPC that silently stops fighting.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.combat
"""

from evennia.utils.test_resources import EvenniaTest

from systems.combat.protocols import Combatant, SkillSource
from typeclasses.npc_combat import _NpcSkillsShim
from world.npc_database import NPC_DB


class TestSkillSourceConformance(EvenniaTest):
    """Both `.skills` implementations must cover the same surface.

    The shim's own docstring records what happens when they diverge: combat
    calls a method the shim lacks, it raises inside the tick loop, the engine
    contains the failure, and the NPC stops fighting with nothing surfaced.
    """

    def test_the_character_skill_handler_satisfies_the_contract(self):
        self.assertIsInstance(self.char1.skills, SkillSource)

    def test_the_npc_shim_satisfies_the_contract(self):
        npc = NPC_DB["mutant_raider"].create(location=self.room1)

        self.assertIsInstance(npc.skills, SkillSource)

    def test_the_shim_implements_every_method_the_contract_names(self):
        """Explicit rather than relying on isinstance alone: a Protocol checks
        that names exist, and naming them here makes the failure message say
        WHICH one is missing."""
        for name in ("get_level", "add_xp", "get_total_xp", "meets_prerequisite"):
            self.assertTrue(
                callable(getattr(_NpcSkillsShim, name, None)),
                msg=f"_NpcSkillsShim is missing {name}()",
            )

    def test_both_implementations_agree_on_the_method_set(self):
        """The regression that matters: a method added to the real handler and
        forgotten on the shim. Compared against the contract rather than
        against each other, so the real handler is free to have extras."""
        contract = {
            name for name in dir(SkillSource)
            if not name.startswith("_")
        }
        shim_methods = {name for name in dir(_NpcSkillsShim) if not name.startswith("_")}

        missing = contract - shim_methods

        self.assertEqual(
            missing, set(), msg=f"_NpcSkillsShim does not implement {sorted(missing)}"
        )


class TestCombatantConformance(EvenniaTest):
    """Everything combat can swing at must satisfy one interface."""

    def test_a_character_is_a_combatant(self):
        self.assertIsInstance(self.char1, Combatant)

    def test_an_npc_is_a_combatant(self):
        npc = NPC_DB["mutant_raider"].create(location=self.room1)

        self.assertIsInstance(npc, Combatant)

    def test_a_plain_object_is_not_a_combatant(self):
        """Guards the assertions above: a Protocol that everything satisfied
        would make them meaningless."""
        self.assertNotIsInstance(self.obj1, Combatant)

    def test_an_item_is_not_a_combatant(self):
        from world.item_database import ITEM_DB

        item = ITEM_DB["rusty_metal_chunk"].create(location=self.room1)

        self.assertNotIsInstance(item, Combatant)
