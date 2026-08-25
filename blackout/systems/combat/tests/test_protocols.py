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

import inspect

from evennia.utils.test_resources import EvenniaTest

from systems.combat.protocols import Combatant, SkillSource, XpEarner
from systems.progression.skills.handler import SkillHandler
from systems.progression.skills.stat_block import StatBlockSkills
from world.npc_database import NPC_DB


def _protocol_members(protocol) -> set:
    """The method names a Protocol declares, without the typing machinery."""
    return {name for name in dir(protocol) if not name.startswith("_")}


def _signature_mismatches(protocol, implementation) -> list:
    """Compare each protocol member's parameters against an implementation's.

    Returns a list of human-readable complaints, empty when they agree.

    A Protocol's runtime isinstance check only asks whether the NAMES exist,
    so an implementation whose get_level took different parameters from the
    one combat calls satisfied it. That is the same silent breakage the
    protocol was written to catch, one step further in: it fails at the call
    site, inside the tick loop, where the engine swallows it.

    Return annotations are deliberately not compared -- an implementation is
    free to be more specific about what it hands back than the contract is.
    """
    complaints = []

    for name in _protocol_members(protocol):
        expected = inspect.signature(getattr(protocol, name))
        actual_attr = getattr(implementation, name, None)

        if actual_attr is None:
            complaints.append(f"{implementation.__name__} is missing {name}()")
            continue

        actual = inspect.signature(actual_attr)

        expected_params = list(expected.parameters)
        actual_params = list(actual.parameters)

        if expected_params != actual_params:
            complaints.append(
                f"{implementation.__name__}.{name}{actual} does not match "
                f"the contract's {name}{expected}"
            )

    return complaints


class TestSkillSourceConformance(EvenniaTest):
    """Both `.skills` implementations must cover the same level surface.

    The NPC facade this replaced recorded the failure mode in its own
    docstring: combat calls a method it lacks, the call raises inside the tick
    loop, the engine contains the failure by discarding the handler, and the
    NPC stops fighting with nothing surfaced to the player.
    """

    def test_the_character_skill_handler_satisfies_the_contract(self):
        self.assertIsInstance(self.char1.skills, SkillSource)

    def test_the_npc_stat_block_satisfies_the_contract(self):
        npc = NPC_DB["mutant_raider"].create(location=self.room1)

        self.assertIsInstance(npc.skills, SkillSource)

    def test_the_stat_block_matches_the_contract_signatures(self):
        complaints = _signature_mismatches(SkillSource, StatBlockSkills)

        self.assertEqual(complaints, [], msg="; ".join(complaints))

    def test_the_skill_handler_matches_the_contract_signatures(self):
        complaints = _signature_mismatches(SkillSource, SkillHandler)

        self.assertEqual(complaints, [], msg="; ".join(complaints))


class TestXpEarnerConformance(EvenniaTest):
    """Only a character earns. The split is what the killer-XP gate reads."""

    def test_a_character_is_an_xp_earner(self):
        self.assertIsInstance(self.char1.skills, XpEarner)

    def test_an_npc_is_not_an_xp_earner(self):
        """The assertion the whole split exists for.

        `getattr(killer, "skills", None) is not None` gated the killer-XP
        award in CombatEntity.at_death and the per-hit XP plan in the combat
        handler. Every NPC has a `.skills`, so both gates opened for a monster
        that killed a player -- harmless only for as long as the NPC-side
        add_xp stayed a no-op. StatBlockSkills does not implement the XP
        surface at all, so the question now has a real answer.
        """
        npc = NPC_DB["mutant_raider"].create(location=self.room1)

        self.assertNotIsInstance(npc.skills, XpEarner)

    def test_the_skill_handler_matches_the_contract_signatures(self):
        complaints = _signature_mismatches(XpEarner, SkillHandler)

        self.assertEqual(complaints, [], msg="; ".join(complaints))

    def test_the_two_contracts_do_not_overlap(self):
        """Guards the split itself: a method drifting back into both
        protocols would make the isinstance check above pass for NPCs again
        the moment StatBlockSkills grew it."""
        shared = _protocol_members(SkillSource) & _protocol_members(XpEarner)

        self.assertEqual(shared, set(), msg=f"declared in both: {sorted(shared)}")


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
