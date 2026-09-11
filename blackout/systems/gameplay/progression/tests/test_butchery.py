"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/10/2026
Description: Butchery, the corpse it works on, and the parts of the gathering
             machinery that only a multi-yield node can exercise.

             The registry-derived assertions here read their expectations out
             of GATHERABLE_REGISTRY rather than restating them, so tuning a
             level or an XP number does not require editing a test -- and
             adding a third cut is covered the day it is declared.
"""

from evennia import create_object
from evennia.utils.test_resources import EvenniaCommandTest, EvenniaTest

from commands.gathering_cmds import (
    CmdButcherGatheringNode,
    CmdHarvestGatheringNode,
    gathering_verbs,
    resolve_gathering_skill,
)
from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills.gatherables import GATHERABLE_REGISTRY
from systems.gameplay.progression.skills.registry import SKILL_REGISTRY
from systems.gameplay.spawning.respawn import get_respawn_manager, npc_present
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import serializers
from typeclasses.corpses import CORPSE_NPC_KEY_ATTR
from typeclasses.objects import DefaultObject
from world.item_database import ITEM_DB
from world.npc_database import NPC_DB


_CORPSE_KEY = "mutant_raider_corpse"
_BUTCHERY = skill_constants.BUTCHERY_SKILL_KEY

# Far enough past any deadline that a sweep fires every queued entry.
_LONG_AFTER = 10 ** 12



def _corpse_def():
    return GATHERABLE_REGISTRY[_CORPSE_KEY]


def _yields():
    """Butchery's yields off a raider corpse, easiest first."""
    return _corpse_def().yields_for_skill(_BUTCHERY)



class CorpseFromDeathTest(EvenniaTest):
    """What a kill leaves on the floor, and what it must not break."""

    def _raider(self):
        return NPC_DB["mutant_raider"].create(location=self.room1)


    def _corpses_in(self, room):
        return [
            obj for obj in room.contents
            if obj.attributes.get("gatherable_key", default=None) == _CORPSE_KEY
        ]


    def test_a_kill_leaves_a_corpse(self):
        npc = self._raider()

        npc.at_death(killer=self.char1)

        self.assertEqual(len(self._corpses_in(self.room1)), 1)


    def test_an_npc_with_no_corpse_key_leaves_nothing(self):
        """Opt-in, exactly as loot_table and respawn_seconds are."""
        npc = self._raider()
        npc.db.npc_key = "floating_eye"

        npc.at_death(killer=self.char1)

        self.assertEqual(self._corpses_in(self.room1), [])


    def test_the_corpse_remembers_which_npc_it_came_from(self):
        npc = self._raider()

        npc.at_death(killer=self.char1)
        corpse = self._corpses_in(self.room1)[0]

        self.assertEqual(
            corpse.attributes.get(CORPSE_NPC_KEY_ATTR), "mutant_raider")


    def test_the_corpse_does_not_carry_npc_key(self):
        """The single most load-bearing assertion in this file.

        npc_present() matches on db.npc_key. A corpse carrying it reads as a
        live raider standing on the tile, and the respawn sweep does not
        requeue a blocked entry -- it DROPS it. The raider would never come
        back, and taking the corpse away afterwards could not undo it.
        """
        npc = self._raider()

        npc.at_death(killer=self.char1)
        corpse = self._corpses_in(self.room1)[0]

        self.assertIsNone(corpse.attributes.get("npc_key", default=None))
        self.assertFalse(npc_present("mutant_raider", self.room1))


    def test_the_raider_still_respawns_with_its_corpse_lying_there(self):
        """The bug this whole design exists to avoid, stated end to end."""
        npc = self._raider()
        npc.at_death(killer=self.char1)

        get_respawn_manager().sweep(now=_LONG_AFTER)

        self.assertTrue(npc_present("mutant_raider", self.room1))
        self.assertEqual(len(self._corpses_in(self.room1)), 1)


    def test_a_corpse_can_be_picked_up(self):
        """Butcher it where it fell, or pocket it for later -- both."""
        npc = self._raider()
        npc.at_death(killer=self.char1)
        corpse = self._corpses_in(self.room1)[0]

        self.assertTrue(corpse.access(self.char1, "get"))
        self.assertTrue(corpse.at_pre_get(self.char1))



class CorpseSerializationTest(EvenniaTest):
    """What a graphical client is told a corpse affords."""

    def _corpse(self):
        return ITEM_DB[_CORPSE_KEY].create(location=self.room1)


    def test_a_corpse_is_not_reported_as_a_walking_npc(self):
        corpse = self._corpse()
        corpse.attributes.add(CORPSE_NPC_KEY_ATTR, "mutant_raider")

        body = serializers.serialize_entity(corpse)

        self.assertEqual(body["kind"], feed_const.ASSET_KIND_CORPSE)


    def test_a_corpse_offers_both_butchering_and_taking(self):
        """The reason serialize_entity grew an action list at all."""
        corpse = self._corpse()

        body = serializers.serialize_entity(corpse)
        commands = [action["command"] for action in body["actions"]]

        self.assertIn(f"butcher {corpse.key}", commands)
        self.assertIn(f"get {corpse.key}", commands)


    def test_interact_is_the_head_of_the_action_list(self):
        """A client reading only `interact` must keep working."""
        corpse = self._corpse()

        body = serializers.serialize_entity(corpse)

        self.assertEqual(body["interact"], body["actions"][0]["command"])


    def test_the_corpse_names_its_source_npc_as_its_asset(self):
        corpse = self._corpse()
        corpse.attributes.add(CORPSE_NPC_KEY_ATTR, "mutant_raider")

        body = serializers.serialize_entity(corpse)

        self.assertEqual(body["asset"], "mutant_raider")


    def test_every_offered_command_starts_with_a_real_verb(self):
        """The invariant that keeps a graphical client honest.

        Every string sent is a command a telnet player could type, so a click
        can do nothing a typed line cannot -- which is what keeps every lock,
        permission and cooldown in force with no separate audit.
        """
        corpse = self._corpse()

        body = serializers.serialize_entity(corpse)

        for action in body["actions"]:
            with self.subTest(command=action["command"]):
                verb = action["command"].split(" ")[0]
                self.assertEqual(verb.lower(), action["label"].lower())


    def test_labels_are_capitalised_the_way_the_inventory_capitalises_its_own(self):
        """One rule for the same field in the same client.

        INVENTORY_ACTION_EQUIP is ("Equip", "equip {slot}"). An entity's
        actions are read by the same menu code, so leaving these lowercase
        would put "butcher" beside "Equip" and make the capitalisation a
        client-side guess.
        """
        corpse = self._corpse()

        body = serializers.serialize_entity(corpse)

        for action in body["actions"]:
            with self.subTest(label=action["label"]):
                self.assertEqual(action["label"][:1], action["label"][:1].upper())



class ButcheryYieldTest(EvenniaCommandTest):
    """Which cut a harvest gives, and who decides."""

    def setUp(self) -> None:
        super().setUp()

        self.corpse = ITEM_DB[_CORPSE_KEY].create(location=self.room1)

        knife = create_object(DefaultObject, key="knife", location=self.char1)
        knife.db.tool_type = "dagger"
        self.knife = knife


    def _set_level(self, level):
        self.char1.db.skills[_BUTCHERY] = {"level": level, "xp": 0}


    def _butcher(self, wanted=""):
        args = " corpse"

        if wanted:
            args = f"{args} = {wanted}"

        return self.call(
            CmdButcherGatheringNode(),
            args,
            cmdstring="butcher",
            caller=self.char1,
            obj=self.corpse,
        )


    def _carried_keys(self):
        return [
            obj.attributes.get("prototype_key", default=None)
            or obj.key
            for obj in self.char1.contents
        ]


    def test_a_beginner_gets_the_starter_cut(self):
        starter = _yields()[0]
        self._set_level(starter.required_level)

        response = self._butcher()

        self.assertIn(ITEM_DB[starter.item_key].name, response)


    def test_the_best_unlocked_cut_is_the_default(self):
        """Levelling changes what happens by DEFAULT, not just what is legal."""
        best = _yields()[-1]
        self._set_level(best.required_level)

        response = self._butcher()

        self.assertIn(ITEM_DB[best.item_key].name, response)


    def test_a_locked_cut_is_refused_with_its_level(self):
        best = _yields()[-1]
        self._set_level(_yields()[0].required_level)

        response = self._butcher(wanted=ITEM_DB[best.item_key].name)

        self.assertIn(str(best.required_level), response)
        self.assertIn("Butchery", response)


    def test_a_locked_cut_is_not_quietly_downgraded(self):
        """Handing someone a chuck when they asked for a filet reads as a bug."""
        cheap, best = _yields()[0], _yields()[-1]
        self._set_level(cheap.required_level)

        response = self._butcher(wanted=ITEM_DB[best.item_key].name)

        self.assertNotIn(ITEM_DB[cheap.item_key].name, response)


    def test_an_unlocked_cut_can_still_be_named(self):
        cheap, best = _yields()[0], _yields()[-1]
        self._set_level(best.required_level)

        response = self._butcher(wanted=ITEM_DB[cheap.item_key].name)

        self.assertIn(ITEM_DB[cheap.item_key].name, response)


    def test_a_yield_can_be_named_by_its_item_key(self):
        cheap = _yields()[0]
        self._set_level(cheap.required_level)

        response = self._butcher(wanted=cheap.item_key)

        self.assertIn(ITEM_DB[cheap.item_key].name, response)


    def test_a_name_that_matches_nothing_is_refused(self):
        self._set_level(_yields()[-1].required_level)

        response = self._butcher(wanted="wingtip")

        self.assertIn("wingtip", response)


    def test_one_corpse_is_one_harvest(self):
        self._set_level(_yields()[0].required_level)

        self._butcher()

        self.assertIsNone(self.corpse.pk)


    def test_the_harvest_teaches_the_secondary_skills_too(self):
        """The skill-tree map's dashed 'cutting + butchery XP' arrow."""
        chosen = _yields()[0]
        self._set_level(chosen.required_level)
        before = {
            key: self.char1.skills.get_total_xp(key)
            for key in chosen.secondary_xp
        }

        self._butcher()

        for key, amount in chosen.secondary_xp.items():
            with self.subTest(skill=key):
                self.assertEqual(
                    self.char1.skills.get_total_xp(key), before[key] + amount)


    def test_butchery_itself_takes_the_whole_primary_award(self):
        chosen = _yields()[0]
        self._set_level(chosen.required_level)
        before = self.char1.skills.get_total_xp(_BUTCHERY)

        self._butcher()

        self.assertEqual(
            self.char1.skills.get_total_xp(_BUTCHERY),
            before + chosen.xp_reward)


    def test_a_corpse_cannot_be_cut(self):
        """A skill refuses a node the registry does not give it."""
        from commands.gathering_cmds import CmdCutGatheringNode

        self._set_level(_yields()[0].required_level)

        response = self.call(
            CmdCutGatheringNode(),
            " corpse",
            cmdstring="cut",
            caller=self.char1,
            obj=self.corpse,
        )

        self.assertIn("not something you can cut", response)


    def test_bare_hands_cost_a_hit_point(self):
        """A corpse is bare_hands=True, and the exemption still costs blood."""
        self._set_level(_yields()[0].required_level)
        self.knife.delete()

        # The fixture character starts on 1 hp, and the cost would kill them
        # -- at which point respawn() refills to max and the delta is
        # unreadable. That path is covered by
        # _pay_bare_hand_cost's own survives-check, not here.
        self.char1.max_hp = 20
        self.char1.hp = 10

        self._butcher()

        self.assertEqual(self.char1.hp, 9)


    def test_a_bare_handed_harvest_that_kills_you_gives_nothing(self):
        """Being told you 'successfully butchered' it is not what happened."""
        self._set_level(_yields()[0].required_level)
        self.knife.delete()
        self.char1.hp = 1

        response = self._butcher()

        self.assertNotIn("You successfully", response)



class GatheringToolResolutionTest(EvenniaTest):
    """Which skill a tool decides on, for the generic `harvest` verb."""

    def setUp(self) -> None:
        super().setUp()
        self.corpse = ITEM_DB[_CORPSE_KEY].create(location=self.room1)


    def test_a_single_skill_node_needs_no_tool_to_disambiguate(self):
        skill, choices = resolve_gathering_skill(self.char1, self.corpse)

        self.assertEqual(skill.key, _BUTCHERY)
        self.assertEqual(choices, [])


    def test_a_non_node_resolves_to_nothing(self):
        skill, choices = resolve_gathering_skill(self.char1, self.obj1)

        self.assertIsNone(skill)
        self.assertEqual(choices, [])


    def test_an_equipped_tool_outranks_one_in_the_bag(self):
        """The design rule, asserted where it is decided.

        find_tool walks equipped items before carried ones, which is what
        makes "what is in your hands says which skill you meant" true rather
        than aspirational.
        """
        butchery = SKILL_REGISTRY[_BUTCHERY]()
        carried = create_object(
            DefaultObject, key="bag knife", location=self.char1)
        carried.db.tool_type = "dagger"

        found = butchery.find_tool(self.char1)

        self.assertIs(found, carried)

        equipped = create_object(
            DefaultObject, key="held knife", location=self.char1)
        equipped.db.tool_type = "dagger"
        self.char1.equipment.all = lambda: [equipped]

        self.assertIs(butchery.find_tool(self.char1), equipped)



class GatheringVerbTableTest(EvenniaTest):
    """The server names the verbs; the client draws them."""

    def test_a_corpse_offers_the_verbs_its_registry_entry_names(self):
        corpse = ITEM_DB[_CORPSE_KEY].create(location=self.room1)

        verbs = {action["label"] for action in gathering_verbs(corpse)}

        self.assertIn(SKILL_REGISTRY[_BUTCHERY].verb, verbs)


    def test_a_pole_offers_cutting_and_not_butchery(self):
        from typeclasses.gathering_nodes import RustyPole

        node = create_object(RustyPole, key="rusty pole", location=self.room1)

        verbs = {action["label"] for action in gathering_verbs(node)}

        self.assertEqual(verbs, {"cut"})


    def test_every_skill_a_registry_entry_names_actually_exists(self):
        """A node naming a skill with no class gives it a verb that runs
        nothing. Derived from the registry, so a new node is covered on the
        day it is declared."""
        for key, gatherable_def in GATHERABLE_REGISTRY.items():
            for skill_key in gatherable_def.skill_keys():
                with self.subTest(node=key, skill=skill_key):
                    self.assertIn(skill_key, SKILL_REGISTRY)


    def test_every_gathering_skill_key_names_a_real_skill(self):
        for skill_key in skill_constants.GATHERING_SKILL_KEYS:
            with self.subTest(skill=skill_key):
                self.assertIn(skill_key, SKILL_REGISTRY)



class HarvestVerbTest(EvenniaCommandTest):
    """The generic verb, which picks the skill from the tool."""

    def test_harvest_works_a_corpse_without_naming_butchery(self):
        corpse = ITEM_DB[_CORPSE_KEY].create(location=self.room1)
        knife = create_object(DefaultObject, key="knife", location=self.char1)
        knife.db.tool_type = "dagger"
        self.char1.db.skills[_BUTCHERY] = {
            "level": _yields()[0].required_level, "xp": 0}

        response = self.call(
            CmdHarvestGatheringNode(),
            " corpse",
            cmdstring="harvest",
            caller=self.char1,
            obj=corpse,
        )

        self.assertIn("You successfully butcher", response)


    def test_harvest_refuses_something_that_is_not_a_node(self):
        """Named, it is refused for being the wrong thing."""
        response = self.call(
            CmdHarvestGatheringNode(),
            " Obj",
            cmdstring="harvest",
            caller=self.char1,
            obj=self.obj1,
        )

        self.assertIn("not something you can harvest", response)


    def test_harvest_with_nothing_around_says_so(self):
        """Unnamed, it looks around and reports honestly."""
        response = self.call(
            CmdHarvestGatheringNode(),
            "",
            cmdstring="harvest",
            caller=self.char1,
            obj=self.obj1,
        )

        self.assertIn("nothing here to harvest", response)


class VerbSurvivesItsTargetTest(EvenniaCommandTest):
    """The playtest bug: `butcher` worked once, then stopped being a command.

    The verbs used to live on a cmdset added to each node. Butchering a corpse
    deletes the corpse, which deleted the cmdset, which deleted the verb -- so
    the second attempt was not "nothing to butcher here" but Evennia's
    unknown-command spell-checker offering "charcreate". A player cannot tell
    those apart, and the second one reads as the game being broken.
    """

    def _butcher(self, args=""):
        return self.call(
            CmdButcherGatheringNode(),
            args,
            cmdstring="butcher",
            caller=self.char1,
        )


    def setUp(self) -> None:
        super().setUp()
        self.char1.db.skills[_BUTCHERY] = {
            "level": _yields()[0].required_level, "xp": 0}

        # With a blade, so these tests exercise the verb's TARGETING and not
        # the bare-handed path -- the fixture character starts on 1 hp, and a
        # bare-handed harvest would kill them before the harvest resolved.
        knife = create_object(DefaultObject, key="knife", location=self.char1)
        knife.db.tool_type = "dagger"


    def test_butchering_the_only_corpse_still_leaves_the_verb_answerable(self):
        ITEM_DB[_CORPSE_KEY].create(location=self.room1)

        self._butcher()
        second = self._butcher()

        self.assertIn("nothing here to butcher", second)


    def test_a_bare_verb_finds_the_corpse_on_the_floor(self):
        ITEM_DB[_CORPSE_KEY].create(location=self.room1)

        response = self._butcher()

        self.assertIn("You successfully butcher", response)


    def test_a_bare_verb_finds_a_corpse_in_your_bag(self):
        """Butcher it where it fell, or pocket it for later -- both."""
        ITEM_DB[_CORPSE_KEY].create(location=self.char1)

        response = self._butcher()

        self.assertIn("You successfully butcher", response)


    def test_two_corpses_are_named_rather_than_guessed_between(self):
        ITEM_DB[_CORPSE_KEY].create(location=self.room1)
        ITEM_DB[_CORPSE_KEY].create(location=self.room1)

        response = self._butcher()

        self.assertIn("Which one?", response)


    def test_two_identical_corpses_do_not_stall_a_named_butcher(self):
        """The playtest report, verbatim.

        Kill two raiders on one tile, pocket one body, and `butcher Mutant
        Raider corpse` used to answer "More than one match ... corpse-1
        (carried), corpse-2" -- a disambiguation between two objects that are
        the same object for every purpose this command has, and one a click in
        the 3D pane cannot supply a suffix for at all.
        """
        ITEM_DB[_CORPSE_KEY].create(location=self.room1)
        ITEM_DB[_CORPSE_KEY].create(location=self.char1)

        response = self._butcher(" Mutant Raider corpse")

        self.assertIn("You successfully butcher", response)
        self.assertNotIn("More than one match", response)


    def test_the_one_on_the_ground_is_taken_before_the_one_in_your_bag(self):
        """Room before bag, the same order the bare verb uses."""
        on_the_floor = ITEM_DB[_CORPSE_KEY].create(location=self.room1)
        in_the_bag = ITEM_DB[_CORPSE_KEY].create(location=self.char1)

        self._butcher(" Mutant Raider corpse")

        self.assertIsNone(on_the_floor.pk)
        self.assertIsNotNone(in_the_bag.pk)


    def test_naming_the_live_raider_butchers_nothing(self):
        """The narrowing is what makes taking the first match safe.

        Taking the first of several matches is only defensible because the
        matches are filtered to what the SKILL can work first. Here the player
        named the live raider exactly -- Evennia's exact match beats the
        corpse's partial one -- and the answer is a refusal about the raider,
        not a silent substitution of the body lying next to it.

        That is the property worth pinning. Picking a nearby workable object
        when the player named a specific unworkable one would be the loot bug
        this whole resolution path is trying not to be.
        """
        corpse = ITEM_DB[_CORPSE_KEY].create(location=self.room1)
        raider = NPC_DB["mutant_raider"].create(location=self.room1)

        response = self._butcher(" Mutant Raider")

        self.assertIn("not something you can butcher", response)
        self.assertIsNotNone(corpse.pk)
        self.assertIsNotNone(raider.pk)


    def test_naming_the_corpse_works_with_a_live_raider_standing_there(self):
        """And the case the 3D pane actually sends, which names it in full."""
        corpse = ITEM_DB[_CORPSE_KEY].create(location=self.room1)
        raider = NPC_DB["mutant_raider"].create(location=self.room1)

        response = self._butcher(" Mutant Raider corpse")

        self.assertIn("You successfully butcher", response)
        self.assertIsNone(corpse.pk)
        self.assertIsNotNone(raider.pk)


    def test_something_that_is_not_a_node_still_says_so(self):
        """The fallback to a noisy search. Swallowing it into "nothing here"
        would lose the one message that explains the refusal."""
        response = self._butcher(" Obj")

        self.assertIn("not something you can butcher", response)


    def test_the_verb_answers_with_no_corpse_anywhere(self):
        response = self._butcher()

        self.assertIn("nothing here to butcher", response)


    def test_a_pole_does_not_answer_the_butcher_verb(self):
        from typeclasses.gathering_nodes import RustyPole

        create_object(RustyPole, key="rusty pole", location=self.room1)

        response = self._butcher()

        self.assertIn("nothing here to butcher", response)
