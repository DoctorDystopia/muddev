"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/07/2026
Description: Tests that the feed is wired into the real game paths, and that
             the payloads it builds there describe what actually happened.

             These need live objects -- an NPC carrying an npc_key, an item
             carrying a prototype tag, a room on the grid -- so they run on
             EvenniaTest. What they assert on is still the PAYLOAD, never a
             socket: the emit seam is recorded and inspected.

             The ordering assertions are the important ones. A killed NPC
             deletes itself inside at_damage, so a death event emitted on the
             wrong side of that call names an id that no longer resolves.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.statefeed
"""

from types import SimpleNamespace
from unittest import mock

from evennia import create_object
from evennia.utils.test_resources import EvenniaTest

from systems.combat import constants as combat_const
from systems.combat.combat import ensure_combat_handler
from systems.combat.rules.context import ActionResult
from systems.statefeed import constants as const
from systems.statefeed import serializers
from systems.statefeed.payloads import CombatPayload
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.gathering_nodes import RustyPole
from typeclasses.npc_combat import spawn_mutant_raider
from world.item_database import ITEM_DB


# ─── Private constant definitions ────────────────────────────────────────────

# Enough to kill a mutant_raider (max_hp 5) outright.
_LETHAL_DAMAGE = 9999

# Survivable, so the victim is still standing to be inspected.
_SMALL_DAMAGE = 1

# An item key that exists in ITEM_DB and is not stackable, so the spawn under
# test survives an inventory merge intact.
_TEST_ITEM_KEY = "rusty_scrap_spear"


class _FeedRecorder:
    """Stands in for statefeed.events.emit and records every payload."""

    def __init__(self):
        self.payloads = []

    def __call__(self, observer, payload, force=False):
        self.payloads.append(payload)
        return 1

    def of_type(self, payload_type):
        """Return only the recorded payloads of one channel's type."""
        matching = []

        for payload in self.payloads:
            if isinstance(payload, payload_type):
                matching.append(payload)

        return matching


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestEntitySerialisation(EvenniaTest):
    """Every renderable entity leaves with a stable asset key."""

    character_typeclass = BlackoutCharacter

    def test_an_npc_is_named_by_its_npc_key(self):
        npc = spawn_mutant_raider(self.room1)

        body = serializers.serialize_entity(npc)

        self.assertEqual(body["kind"], const.ASSET_KIND_NPC)
        self.assertEqual(body["asset"], "mutant_raider")

    def test_an_item_is_named_by_its_prototype_key(self):
        item = ITEM_DB[_TEST_ITEM_KEY].create(location=self.room1)

        body = serializers.serialize_entity(item)

        self.assertEqual(body["kind"], const.ASSET_KIND_ITEM)
        self.assertEqual(body["asset"], _TEST_ITEM_KEY)

    def test_a_character_is_classified_as_a_character(self):
        body = serializers.serialize_entity(self.char1)

        self.assertEqual(body["kind"], const.ASSET_KIND_CHARACTER)

    def test_a_gathering_node_is_not_an_item(self):
        # A node carries get:false(), so a client told "item" offers to pick up
        # the one thing the object refuses. That is exactly what happened with
        # the rusty pole on 08/12/2026 -- it read as an item, the Godot client
        # sent `get`, and only a superuser's lock bypass let it succeed.
        node = create_object(RustyPole, key="rusty pole", location=self.room1)

        body = serializers.serialize_entity(node)

        self.assertEqual(body["kind"], const.ASSET_KIND_GATHERABLE)
        self.assertEqual(body["asset"], "rusty_pole")

    def test_an_entity_carries_its_real_name_for_the_generic_fallback(self):
        npc = spawn_mutant_raider(self.room1)

        body = serializers.serialize_entity(npc)

        self.assertEqual(body["name"], npc.key)

    def test_a_combatant_carries_health(self):
        npc = spawn_mutant_raider(self.room1)

        body = serializers.serialize_entity(npc)

        self.assertIn("hp", body)
        self.assertIn("max_hp", body)

    def test_a_plain_object_carries_no_health_bar(self):
        # An item reported at 0/0 would have a client drawing a health bar on
        # a rock.
        body = serializers.serialize_entity(self.obj1)

        self.assertNotIn("hp", body)

    def test_the_body_is_json_safe_throughout(self):
        npc = spawn_mutant_raider(self.room1)

        body = serializers.serialize_entity(npc)

        for key, value in body.items():
            self.assertIsInstance(value, (int, str, bool), msg=key)


class TestRoomSerialisation(EvenniaTest):
    """Rooms, their exits, and the coordinates a renderer places them by."""

    character_typeclass = BlackoutCharacter

    def test_an_ungridded_room_reports_no_coordinates(self):
        # EvenniaTest's room1 is a plain Room with no xyz attribute at all.
        # The feed must absorb that rather than raise inside a broadcast.
        coords = serializers.room_coords(self.room1)

        self.assertEqual(coords, [])

    def test_a_none_room_reports_no_coordinates(self):
        coords = serializers.room_coords(None)

        self.assertEqual(coords, [])

    def test_exits_are_reported_by_direction(self):
        exits = serializers.serialize_exits(self.room1)

        self.assertIn("out", exits)

    def test_an_exit_resolves_to_its_destination_id(self):
        exits = serializers.serialize_exits(self.room1)

        self.assertEqual(exits["out"], self.room2.id)

    def test_a_room_reports_its_key_as_its_kind(self):
        kind = serializers.room_kind(self.room1)

        self.assertEqual(kind, self.room1.key)

    def test_room_kind_ignores_an_auto_generated_prototype_tag(self):
        # Regression. room_kind used to prefer the prototype tag, which for a
        # grid room is an auto-generated per-room hash ("prototype-8ede16d")
        # rather than anything meaningful. Live, that made room_info report a
        # hash while blackout_map reported "Oasis" for the very same tile, so
        # a client could not match the two.
        from evennia.prototypes.prototypes import PROTOTYPE_TAG_CATEGORY

        self.room1.tags.add("prototype-deadbeef",
                            category=PROTOTYPE_TAG_CATEGORY)

        kind = serializers.room_kind(self.room1)

        self.assertEqual(kind, self.room1.key)
        self.assertNotIn("prototype-", kind)

    def test_room_kind_matches_what_the_map_export_reports(self):
        # The contract that makes the field usable: a client looks the tile it
        # is standing on up in the map it was sent, so both sides must derive
        # room_kind from the same value -- the prototype's "key".
        from systems.statefeed.mapexport import build_map_chunks

        prototypes = {("*", "*"): {"key": self.room1.key}}
        node = SimpleNamespace(X=0, Y=0, links={})
        xymap = SimpleNamespace(
            node_index_map={0: node}, prototypes=prototypes, Z="oasis")

        from_map = build_map_chunks(xymap)[0].nodes[0]["room_kind"]
        from_room = serializers.room_kind(self.room1)

        self.assertEqual(from_map, from_room)

    def test_a_none_room_falls_back_to_the_default_kind(self):
        kind = serializers.room_kind(None)

        self.assertEqual(kind, const.ROOM_KIND_DEFAULT)

    def test_contents_exclude_exits(self):
        entities = serializers.serialize_contents(self.room1)
        names = []

        for entry in entities:
            names.append(entry["name"])

        # "out" is a real object in room1.contents, but it is topology, not an
        # occupant -- it reaches the client through RoomInfoPayload.exits.
        self.assertNotIn("out", names)

    def test_the_observer_can_be_excluded_from_their_own_room(self):
        entities = serializers.serialize_contents(self.room1, exclude=(self.char1,))
        ids = []

        for entry in entities:
            ids.append(entry["id"])

        self.assertNotIn(self.char1.id, ids)


class TestCombatFeed(EvenniaTest):
    """A swing's structured mirror must agree with the swing."""

    character_typeclass = BlackoutCharacter

    def _swing(self, result):
        """Resolve one controlled swing, recording what the feed emitted."""
        handler = ensure_combat_handler(self.char1)
        target = spawn_mutant_raider(self.room1)
        ensure_combat_handler(target)
        handler.queue_action({"kind": "attack", "target": target})

        recorder = _FeedRecorder()

        with mock.patch("systems.combat.combat.resolve_action", return_value=result):
            with mock.patch("systems.statefeed.events.emit", recorder):
                with mock.patch("systems.statefeed.events.emit_to_room",
                                return_value=0):
                    handler.tick()

        return recorder, target

    def test_a_connecting_swing_publishes_a_combat_event(self):
        result = ActionResult(hit=True, damage=_SMALL_DAMAGE, hit_prob=1.0)

        recorder, _target = self._swing(result)

        self.assertTrue(recorder.of_type(CombatPayload))

    def test_the_published_damage_matches_the_resolved_damage(self):
        result = ActionResult(hit=True, damage=_SMALL_DAMAGE, hit_prob=1.0)

        recorder, _target = self._swing(result)
        event = recorder.of_type(CombatPayload)[0]

        self.assertEqual(event.damage, _SMALL_DAMAGE)

    def test_the_damage_type_is_carried_through_verbatim(self):
        result = ActionResult(
            hit=True,
            damage=_SMALL_DAMAGE,
            hit_prob=1.0,
            damage_type=combat_const.DAMAGE_TYPE_ENERGY,
        )

        recorder, _target = self._swing(result)
        event = recorder.of_type(CombatPayload)[0]

        self.assertEqual(event.damage_type, combat_const.DAMAGE_TYPE_ENERGY)

    def test_a_miss_is_published_rather_than_skipped(self):
        # A client that only hears about hits would show a combatant standing
        # still through every miss and then twitching on a hit.
        result = ActionResult(hit=False, damage=0, hit_prob=0.0)

        recorder, _target = self._swing(result)
        events = recorder.of_type(CombatPayload)

        self.assertTrue(events)
        self.assertFalse(events[0].hit)

    def test_a_lethal_swing_is_flagged_as_a_kill(self):
        result = ActionResult(hit=True, damage=_LETHAL_DAMAGE, hit_prob=1.0)

        recorder, _target = self._swing(result)
        event = recorder.of_type(CombatPayload)[0]

        self.assertTrue(event.killed)

    def test_a_death_event_names_a_target_that_still_resolved_when_sent(self):
        # The regression this guards: the NPC deletes itself inside at_damage,
        # after which its .id reads None. An event emitted on the wrong side of
        # that call would carry nothing, and a client could not attach a death
        # animation to it.
        #
        # So the assertion is deliberately NOT `event.target_id == target.id`:
        # by the time the test reads it, target.id is None precisely because
        # the delete worked. A real id in the event is the proof of ordering.
        result = ActionResult(hit=True, damage=_LETHAL_DAMAGE, hit_prob=1.0)

        recorder, target = self._swing(result)
        event = recorder.of_type(CombatPayload)[0]

        self.assertIsNone(target.id, msg="fixture no longer deletes on death")
        self.assertIsInstance(event.target_id, int)
        self.assertGreater(event.target_id, 0)

    def test_the_published_hp_is_the_post_hit_total(self):
        result = ActionResult(hit=True, damage=_SMALL_DAMAGE, hit_prob=1.0)

        recorder, target = self._swing(result)
        event = recorder.of_type(CombatPayload)[0]

        self.assertEqual(event.hp_after, target.max_hp - _SMALL_DAMAGE)

    def test_a_lethal_swing_publishes_zero_remaining_hp(self):
        result = ActionResult(hit=True, damage=_LETHAL_DAMAGE, hit_prob=1.0)

        recorder, _target = self._swing(result)
        event = recorder.of_type(CombatPayload)[0]

        self.assertEqual(event.hp_after, 0)

    def test_the_attacker_is_named(self):
        result = ActionResult(hit=True, damage=_SMALL_DAMAGE, hit_prob=1.0)

        recorder, _target = self._swing(result)
        event = recorder.of_type(CombatPayload)[0]

        self.assertEqual(event.attacker_id, self.char1.id)

    def test_a_normal_swing_is_not_flagged_as_a_backfire(self):
        result = ActionResult(hit=True, damage=_SMALL_DAMAGE, hit_prob=1.0)

        recorder, _target = self._swing(result)
        event = recorder.of_type(CombatPayload)[0]

        self.assertFalse(event.backfire)

    def test_a_backfire_names_the_attacker_as_the_victim(self):
        result = ActionResult(
            hit=True,
            damage=_SMALL_DAMAGE,
            self_damage=_SMALL_DAMAGE,
            hit_prob=1.0,
        )

        recorder, _target = self._swing(result)
        backfires = []

        for event in recorder.of_type(CombatPayload):
            if event.backfire:
                backfires.append(event)

        self.assertTrue(backfires)
        self.assertEqual(backfires[0].target_id, self.char1.id)

    def test_the_payload_is_json_safe_throughout(self):
        result = ActionResult(hit=True, damage=_SMALL_DAMAGE, hit_prob=1.0)

        recorder, _target = self._swing(result)
        body = recorder.of_type(CombatPayload)[0].to_dict()

        for key, value in body.items():
            self.assertIsInstance(value, (int, str, bool), msg=key)


class TestFeedIsSilentWithoutSubscribers(EvenniaTest):
    """The whole point of the opt-in: telnet players pay nothing."""

    character_typeclass = BlackoutCharacter

    def test_a_swing_sends_no_feed_messages_to_an_unsubscribed_session(self):
        handler = ensure_combat_handler(self.char1)
        target = spawn_mutant_raider(self.room1)
        ensure_combat_handler(target)
        handler.queue_action({"kind": "attack", "target": target})
        result = ActionResult(hit=True, damage=_SMALL_DAMAGE, hit_prob=1.0)

        with mock.patch("systems.combat.combat.resolve_action", return_value=result):
            with mock.patch.object(type(self.char1), "msg") as mocked_msg:
                handler.tick()

        for call in mocked_msg.call_args_list:
            _args, kwargs = call

            for channel in const.SUBSCRIBABLE_CHANNELS:
                self.assertNotIn(channel, kwargs)
