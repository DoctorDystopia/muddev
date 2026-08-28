"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/14/2026
Description: Tests that every interactable object in the game tells a client
             what it is and what to do with it, and that the entity feed
             widens to STATEFEED_ENTITY_RADIUS.

             The interaction half of this file exists because the same bug has
             now been found twice by playing the game rather than by reading
             the code: an object with nothing distinctive in its storage falls
             through to "item", and a graphical client then offers the one
             interaction the object refuses. The rusty pole went first, on
             08/12; the Foundry Furnace went on 08/14, and a superuser's lock
             bypass meant the client successfully picked up a furnace.

             A test per interactable typeclass is the cheap way to stop the
             third one. Each asserts the KIND (how it is drawn) and the
             INTERACT command (what a click sends) separately, because the
             shopkeeper is the case that proves they are different questions:
             it is an NPC, and it is not a fight.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py \
        systems.statefeed.tests.test_interaction
"""

import os
import re
import unittest

from evennia import create_object
from evennia.utils.test_resources import EvenniaTest

from systems.statefeed import constants as const
from systems.statefeed import events, serializers
from typeclasses.bank_nodes import BankNode
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.gathering_nodes import RustyPole
from typeclasses.npc_combat import spawn_mutant_raider
from typeclasses.npcs import ShopkeepNPC
from typeclasses.skill_facilities import AnvilFacility, FurnaceFacility
from world.item_database import ITEM_DB

# Public constant definitions

# Non-stackable, so the spawn under test survives an inventory merge intact.
TEST_ITEM_KEY = "rusty_scrap_spear"

# The game dir (blackout/), four levels up from this file, and the repo root
# one further up -- the Godot client is a sibling of the game dir rather than
# inside it. Derived the same way test_client_constants derives them.
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
_REPO_ROOT = os.path.dirname(_GAME_DIR)

# Every 3D pane that turns a click on an entity into a command. A path that
# does not exist is skipped, so a client can be removed without a test edit --
# but the vacuity guard below refuses to let BOTH disappear silently.
_ENTITY_CLICK_SOURCES: tuple = (
    os.path.join(_GAME_DIR, "web", "static", "webclient", "js", "plugins",
                 "blackout3d.js"),
    os.path.join(_REPO_ROOT, "godot", "world", "world_view.gd"),
)

# A comment in either language, stripped before any of these files is read.
# Both panes explain at length what they no longer do -- world_view.gd names
# the deleted `attack %s` in the comment recording its removal -- and prose
# describing a removed pattern must not read as the pattern.
_COMMENT_RE = re.compile(r"/\*.*?\*/|(//|#).*?$", re.DOTALL | re.MULTILINE)

# The field the server names the whole command in.
_INTERACT_FIELD = "interact"


class TestInteractionVerbs(EvenniaTest):
    """
    Purpose: Every object a player can act on names its own verb, and nothing
    is offered an interaction it would refuse.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """

    character_typeclass = BlackoutCharacter

    def test_a_furnace_is_a_station_that_is_crafted_at(self):
        # The 08/14 bug: this fell through to "item" and the 3D pane sent
        # `get Foundry Furnace`, which a superuser was allowed to do.
        furnace = create_object(
            FurnaceFacility, key="Foundry Furnace", location=self.room1)

        body = serializers.serialize_entity(furnace)

        self.assertEqual(body["kind"], const.ASSET_KIND_STATION)
        self.assertEqual(body["asset"], "furnace")
        self.assertEqual(body["interact"], "craft")

    def test_an_anvil_is_told_apart_from_a_furnace(self):
        anvil = create_object(
            AnvilFacility, key="Metalsmith Anvil", location=self.room1)

        body = serializers.serialize_entity(anvil)

        self.assertEqual(body["kind"], const.ASSET_KIND_STATION)
        self.assertEqual(body["asset"], "anvil")

    def test_a_bank_terminal_is_a_station_that_is_banked_at(self):
        terminal = create_object(
            BankNode, key="bank terminal", location=self.room1)

        body = serializers.serialize_entity(terminal)

        self.assertEqual(body["kind"], const.ASSET_KIND_STATION)
        self.assertEqual(body["interact"], "bank")

    def test_a_shopkeeper_is_an_npc_that_is_talked_to_not_attacked(self):
        # The case that proves kind and verb are separate questions. A
        # shopkeeper is an NPC and must be drawn as one; inferring the verb
        # from the kind would have a client opening combat on the shop.
        shopkeep = create_object(
            ShopkeepNPC, key="Shopkeeper", location=self.room1)

        body = serializers.serialize_entity(shopkeep)

        self.assertEqual(body["kind"], const.ASSET_KIND_NPC)
        self.assertEqual(body["interact"], "talk")

    def test_a_gathering_node_is_cut_not_taken(self):
        node = create_object(RustyPole, key="rusty pole", location=self.room1)

        body = serializers.serialize_entity(node)

        self.assertEqual(body["kind"], const.ASSET_KIND_GATHERABLE)
        self.assertEqual(body["interact"], "cut")

    def test_a_hostile_npc_is_attacked_by_name(self):
        # `attack` lives on the CHARACTER's cmdset, so unlike the stations
        # above it has to name its target.
        npc = spawn_mutant_raider(self.room1)

        body = serializers.serialize_entity(npc)

        self.assertEqual(body["interact"], "attack " + npc.key)

    def test_an_item_is_taken_by_name(self):
        item = ITEM_DB[TEST_ITEM_KEY].create(location=self.room1)

        body = serializers.serialize_entity(item)

        self.assertEqual(body["interact"], "get " + item.key)

    def test_a_character_affords_nothing(self):
        # Deliberate: everything else a misclick can do is recoverable, and
        # opening combat on another player is not.
        body = serializers.serialize_entity(self.char1)

        self.assertEqual(body["interact"], "")

    def test_a_station_that_declares_no_verb_still_affords_nothing(self):
        # The fallback has to be silence rather than a guess. TARGETED_VERB_BY
        # _KIND has no entry for a station, so an object declaring itself one
        # without naming a verb is simply not clickable.
        plain = create_object(
            "evennia.objects.objects.DefaultObject",
            key="odd thing", location=self.room1)
        plain.asset_kind = const.ASSET_KIND_STATION

        body = serializers.serialize_entity(plain)

        self.assertEqual(body["kind"], const.ASSET_KIND_STATION)
        self.assertEqual(body["interact"], "")


class TestEntityRadius(EvenniaTest):
    """
    Purpose: The feed reports a neighbourhood, and says where everything in it
    is standing.

    STATEFEED_ENTITY_RADIUS was set to a non-zero value and read by nothing --
    the constant documented a behaviour the code did not have. These cover the
    seam that now reads it, and the coords field without which a client would
    stack the whole neighbourhood onto the player's own tile.

    The radius arithmetic itself is not retested here: rooms_within_radius
    owns it and is covered by systems/combat/auras/tests/test_aura_targeting.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """

    character_typeclass = BlackoutCharacter

    def test_an_off_grid_room_degrades_to_itself(self):
        # EvenniaTest's rooms are plain Rooms with no coordinates. A
        # hand-built area must keep working and must not widen.
        visible = events._visible_rooms(self.room1)

        self.assertEqual(visible, [self.room1])

    def test_a_none_room_is_visible_from_nowhere(self):
        visible = events._visible_rooms(None)

        self.assertEqual(visible, [])

    def test_an_area_gathers_entities_from_every_room_in_it(self):
        here = spawn_mutant_raider(self.room1)
        there = spawn_mutant_raider(self.room2)

        entities = serializers.serialize_area([self.room1, self.room2])

        found = [entry["id"] for entry in entities]
        self.assertIn(here.id, found)
        self.assertIn(there.id, found)

    def test_an_area_excludes_the_observer(self):
        entities = serializers.serialize_area(
            [self.room1], exclude=(self.char1,))

        found = [entry["id"] for entry in entities]
        self.assertNotIn(self.char1.id, found)

    def test_an_area_excludes_exits(self):
        # An exit is a real object in room.contents, but it is topology. A
        # client given one would draw a mesh for a doorway.
        entities = serializers.serialize_area([self.room1])

        found = [entry["id"] for entry in entities]
        self.assertNotIn(self.exit.id, found)

    def test_an_empty_area_is_not_a_query(self):
        entities = serializers.serialize_area([])

        self.assertEqual(entities, [])

    def test_every_entity_says_where_it_is_standing(self):
        spawn_mutant_raider(self.room1)

        entities = serializers.serialize_area([self.room1])

        for entry in entities:
            self.assertIn("coords", entry)

    def test_a_single_room_stamps_the_same_coords_field(self):
        # serialize_contents and serialize_area must produce the same entity
        # shape, or a client has to tell which call built its list.
        spawn_mutant_raider(self.room1)

        contents = serializers.serialize_contents(self.room1)
        area = serializers.serialize_area([self.room1])

        self.assertEqual(sorted(contents[0]), sorted(area[0]))


class TestNoClientKeepsItsOwnVerbTable(unittest.TestCase):
    """
    Purpose: Neither 3D pane decides what a click means. They forward the
    command `interact_command` named, and they build none of their own.

    The class above is a test per interactable TYPECLASS, added on 08/14/2026
    to stop the third furnace bug. It did not, because the third one was not a
    typeclass the server misread -- it was a CLIENT that never asked. The Godot
    pane shipped with a `kind`-to-verb match of its own, so a Foundry Furnace,
    a Bank and a Shopkeeper were all unclickable there while the server had
    been naming their verbs correctly the whole time (fixed 08/27/2026).

    So this is the guard one level up: read the panes as TEXT, which is what
    lets one test cover two languages without importing either.

    Plain unittest.TestCase, deliberately -- nothing here touches the database.

    Author: Nick Hobar
    Creation date: 08/27/2026
    """

    def _live_sources(self):
        """Every pane that exists, as {path: source with comments removed}."""
        found = {}

        for path in _ENTITY_CLICK_SOURCES:
            if not os.path.exists(path):
                continue

            with open(path, "r", encoding="utf-8") as handle:
                found[path] = _COMMENT_RE.sub("", handle.read())

        return found

    def test_there_are_panes_to_read_at_all(self):
        """Vacuity guard: every case below passes on an empty dict."""
        self.assertTrue(
            self._live_sources(),
            "no 3D pane found at any of %s; the checks below are vacuous"
            % (_ENTITY_CLICK_SOURCES,))

    def test_every_pane_reads_the_interact_field(self):
        """
        The positive half. A pane that never names the field cannot be
        forwarding what the server said, whatever else it is doing.
        """
        for path, source in self._live_sources().items():
            with self.subTest(pane=os.path.basename(path)):
                self.assertIn(
                    _INTERACT_FIELD, source,
                    "%s never reads the entity's `interact`, so it is "
                    "deciding for itself what a click means"
                    % os.path.basename(path))

    def test_no_pane_builds_a_targeted_command_out_of_a_verb(self):
        """
        The negative half, and it looks for the SHAPE a verb table has rather
        than for the verb: a targeted command is the verb, a space, and then
        the entity's name substituted in. `"attack %s" % name` in GDScript,
        `'attack ' + name` or a template literal in JS.

        Derived from TARGETED_VERB_BY_KIND rather than listed, so a verb added
        to the server is covered here with no edit.
        """
        for verb in const.TARGETED_VERB_BY_KIND.values():
            # An opening quote, the verb, a space, then something being
            # substituted -- a %s, a ${}, or a closing quote and a +.
            pattern = re.compile(
                r"""["'`]\s*%s\s+(%%s|\$\{|["'`]\s*\+)""" % re.escape(verb))

            for path, source in self._live_sources().items():
                with self.subTest(pane=os.path.basename(path), verb=verb):
                    self.assertIsNone(
                        pattern.search(source),
                        "%s builds `%s <name>` itself; serialize_entity "
                        "already sent the whole command in `interact`"
                        % (os.path.basename(path), verb))
