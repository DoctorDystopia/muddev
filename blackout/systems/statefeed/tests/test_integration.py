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

from systems.banking.handler import BankHandler
from systems.combat import constants as combat_const
from systems.combat.combat import ensure_combat_handler
from systems.combat.rules.context import ActionResult
from systems.statefeed import constants as const
from systems.statefeed import events, resync, serializers, subscriptions
from systems.statefeed.payloads import (
    CharAvatarPayload,
    CharItemsPayload,
    CharVitalsPayload,
    CombatPayload,
)
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

# A stackable ITEM_DB key, so a deposit can take the merging and partial
# paths rather than the plain move_to one.
_STACKABLE_ITEM_KEY = "rusty_metal_dust"


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

    def test_a_character_is_named_by_the_character_asset_key(self):
        body = serializers.serialize_entity(self.char1)

        self.assertEqual(body["asset"], const.ASSET_KEY_CHARACTER)

    def test_a_character_does_not_share_the_generic_asset_key(self):
        # Not a restatement of the test above. Generic is also what an
        # unclassified ITEM falls back to, so the two keys being equal would
        # mean art registered for a person draws one in place of every
        # unmodelled object in the game -- a client-side symptom with a
        # server-side cause, which is the kind that takes a day to find.
        character = serializers.serialize_entity(self.char1)
        unclassified = serializers.serialize_entity(self.obj1)

        self.assertEqual(unclassified["asset"], const.ASSET_KEY_GENERIC)
        self.assertNotEqual(character["asset"], unclassified["asset"])

    def test_a_gathering_node_is_not_an_item(self):
        # A node carries get:false(), so a client told "item" offers to pick up
        # the one thing the object refuses. That is exactly what happened with
        # the rusty pole on 08/12/2026 -- it read as an item, the Godot client
        # sent `get`, and only a superuser's lock bypass let it succeed.
        node = create_object(RustyPole, key="rusty pole", location=self.room1)

        body = serializers.serialize_entity(node)

        self.assertEqual(body["kind"], const.ASSET_KIND_GATHERABLE)
        self.assertEqual(body["asset"], "rusty_pole")

    def test_an_item_on_the_floor_reports_the_family_it_reports_in_a_bag(self):
        # The whole reason the resolver is shared: the mesh drawn for a spear
        # lying on the ground is the mesh drawn for the same spear in a slot,
        # which can only hold if both are told the same family.
        item = ITEM_DB[_TEST_ITEM_KEY].create(location=self.room1)

        body = serializers.serialize_entity(item)

        self.assertEqual(body["family"], const.ITEM_FAMILY_WEAPON)

    def test_a_non_item_falls_back_to_its_own_kind(self):
        npc = spawn_mutant_raider(self.room1)

        body = serializers.serialize_entity(npc)

        self.assertEqual(body["family"], const.ASSET_KIND_NPC)

    def test_a_gathering_node_reports_the_gatherable_family(self):
        node = create_object(RustyPole, key="rusty pole", location=self.room1)

        body = serializers.serialize_entity(node)

        self.assertEqual(body["family"], const.ASSET_KIND_GATHERABLE)

    def test_family_is_never_empty(self):
        # An empty family would send the client to its generic cube by way of
        # a lookup miss rather than a decision, which is the failure mode that
        # looks like a rendering bug and is a serialisation one.
        plain = self.obj1

        body = serializers.serialize_entity(plain)

        self.assertTrue(body["family"])

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

        body = serializers.serialize_entity(npc, coords=[1, 2, "oasis"])

        for key, value in body.items():
            self.assertIsInstance(value, (int, str, bool, list), msg=key)

        # A list is only json-safe if what is in it is. `coords` is the one
        # list field, and it carries two ints and the map NAME.
        for member in body["coords"]:
            self.assertIsInstance(member, (int, str))


class TestCharAvatarChannel(EvenniaTest):
    """The one thing a client cannot learn from room_players: itself."""

    character_typeclass = BlackoutCharacter

    def _emit_avatar(self):
        """Run the avatar emitter with the emit seam recorded."""
        recorder = _FeedRecorder()

        with mock.patch("systems.statefeed.events.emit", recorder):
            events.emit_avatar(self.char1, force=True)

        return recorder

    def test_the_avatar_names_the_observers_own_asset(self):
        recorder = self._emit_avatar()

        avatar = recorder.of_type(CharAvatarPayload)[-1]
        self.assertEqual(avatar.asset, const.ASSET_KEY_CHARACTER)

    def test_the_avatar_carries_the_family_tier_as_well(self):
        # Both tiers, spelled the way every entity dict spells them, so the
        # client resolves its own mesh through the lookup it already runs for
        # an NPC instead of a special case that can rot on its own.
        recorder = self._emit_avatar()

        avatar = recorder.of_type(CharAvatarPayload)[-1]
        self.assertEqual(avatar.family, const.ASSET_KIND_CHARACTER)

    def test_the_avatar_carries_the_observers_entity_id(self):
        # What makes a combat event recognisable as being about you:
        # CombatPayload names its attacker and target by id.
        recorder = self._emit_avatar()

        avatar = recorder.of_type(CharAvatarPayload)[-1]
        self.assertEqual(avatar.entity_id, self.char1.id)

    def test_the_avatar_agrees_with_how_anyone_else_would_be_drawn(self):
        # The observer is excluded from their own room_players list, so this
        # is the only place the two descriptions can be compared -- and they
        # have to match, or you would render differently in your own client
        # than you do in the client of the person standing next to you.
        recorder = self._emit_avatar()
        seen_by_others = serializers.serialize_entity(self.char1)

        avatar = recorder.of_type(CharAvatarPayload)[-1]
        self.assertEqual(avatar.asset, seen_by_others["asset"])
        self.assertEqual(avatar.family, seen_by_others["family"])

    def test_a_missing_observer_is_absorbed(self):
        # Every observer-facing emitter in the feed tolerates None; a session
        # that subscribed before puppeting anything is the ordinary case.
        sent = events.emit_avatar(None)

        self.assertEqual(sent, 0)

    def test_the_payload_is_json_safe_throughout(self):
        recorder = self._emit_avatar()

        avatar = recorder.of_type(CharAvatarPayload)[-1]

        for key, value in avatar.to_dict().items():
            self.assertIsInstance(value, (int, str), msg=key)

    def test_a_full_resync_includes_the_avatar(self):
        # The wiring half. The payload being correct is worth nothing if the
        # only path that sends it -- login, reconnect, reload -- does not.
        recorder = _FeedRecorder()

        with mock.patch("systems.statefeed.events.emit", recorder):
            with mock.patch("systems.statefeed.resync.emit", recorder):
                resync.send_full_state(self.char1)

        self.assertTrue(recorder.of_type(CharAvatarPayload))

    def test_the_avatar_precedes_the_vitals_it_describes(self):
        # Vitals arriving first describe a character the client cannot draw.
        recorder = _FeedRecorder()

        with mock.patch("systems.statefeed.events.emit", recorder):
            with mock.patch("systems.statefeed.resync.emit", recorder):
                resync.send_full_state(self.char1)

        order = [type(payload) for payload in recorder.payloads]
        self.assertLess(order.index(CharAvatarPayload),
                        order.index(CharVitalsPayload))


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
        handler.apply_action({"kind": "attack", "target": target})

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


class TestInventoryFeedDuringAMove(EvenniaTest):
    """
    The snapshot published from at_object_leave must describe the
    inventory the player is LEFT with.

    This needs a SUBSCRIBED session and that is the whole point of it.
    emit_inventory returns 0 before building anything when nobody is
    listening, so on an unsubscribed character the serializer never runs,
    sync() is never called mid-move, and the defect is invisible -- which
    is exactly why it reached the 3D webclient with a green suite behind
    it. Reproducing it requires paying the subscription cost.

    The defect: move_to calls source.at_object_leave at step 4 and only
    reassigns the moved object's location at step 5, so the departing item
    is still in contents while the hook runs. sync()'s adoption loop then
    re-slots the item the hook just removed, persists that, and publishes
    a payload identical to the pre-drop one.

    Author: Nick Hobar
    Creation date: 08/17/2026
    """

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        subscriptions.subscribe(self.session, [const.CHANNEL_CHAR_ITEMS])

    def _drop(self, item):
        """Move one carried item to the floor, recording what the feed said."""
        recorder = _FeedRecorder()

        with mock.patch("systems.statefeed.events.emit", recorder):
            item.move_to(self.room1, quiet=True, move_type="drop")

        return recorder

    def test_the_snapshot_omits_the_item_being_dropped(self):
        item = ITEM_DB[_TEST_ITEM_KEY].create(location=self.char1)

        recorder = self._drop(item)
        snapshots = recorder.of_type(CharItemsPayload)

        self.assertTrue(snapshots, "the leave hook published nothing")
        dropped = snapshots[-1]
        carried_ids = [row["id"] for row in dropped.items]
        self.assertNotIn(item.id, carried_ids)

    def test_the_snapshot_counts_the_dropped_item_as_gone(self):
        ITEM_DB[_TEST_ITEM_KEY].create(location=self.char1)
        item = ITEM_DB["rusty_metal_chunk"].create(location=self.char1)

        recorder = self._drop(item)
        dropped = recorder.of_type(CharItemsPayload)[-1]

        self.assertEqual(dropped.slots_used, 1)

    def test_the_departing_item_is_not_re_slotted_in_the_saved_grid(self):
        """The half that outlives the payload. A re-adopted item writes a
        corrupted slot map to the database mid-move."""
        item = ITEM_DB[_TEST_ITEM_KEY].create(location=self.char1)

        self._drop(item)

        self.assertEqual(self.char1.inventory.find_slot(item), -1)
        self.assertEqual(self.char1.inventory.count_used(), 0)

    def test_a_pickup_still_reports_the_item_it_gained(self):
        """The receive side runs at step 8, after the location change, so it
        must keep seeing the arriving object -- `ignore` is leave-only."""
        item = ITEM_DB[_TEST_ITEM_KEY].create(location=self.room1)
        recorder = _FeedRecorder()

        with mock.patch("systems.statefeed.events.emit", recorder):
            item.move_to(self.char1, quiet=True, move_type="get")

        gained = recorder.of_type(CharItemsPayload)[-1]
        carried_ids = [row["id"] for row in gained.items]
        self.assertIn(item.id, carried_ids)
        self.assertEqual(gained.slots_used, 1)


class TestInventoryFeedAfterABankDeposit(EvenniaTest):
    """
    A deposit must republish the grid, even when nothing was moved off the
    character.

    The character's move hooks are the only thing that publishes an
    inventory snapshot, and they only fire for a move_to. Two of the three
    deposit paths never move the carried object at all: a whole stack that
    matches one already in the vault is folded into it and DELETED where it
    stands, and a partial deposit is a pair of quantity writes. Neither
    fires a hook, so the 3D pane kept drawing a stack the vault already
    held -- the player saw it vanish only after typing `inventory`.

    Needs a SUBSCRIBED session for the same reason
    TestInventoryFeedDuringAMove does: emit_inventory builds nothing when
    nobody is listening, so the defect cannot be reproduced without paying
    the subscription cost.

    Author: Nick Hobar
    Creation date: 08/24/2026
    """

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        subscriptions.subscribe(self.session, [const.CHANNEL_CHAR_ITEMS])
        self.bank = BankHandler(self.char1)

    def _carry(self, quantity):
        """Put one stack of the test material in the character's hands."""
        return ITEM_DB[_STACKABLE_ITEM_KEY].create(
            location=self.char1, quantity=quantity
        )

    def _record(self, action):
        """Run one banking action with the emit seam recorded."""
        recorder = _FeedRecorder()

        with mock.patch("systems.statefeed.events.emit", recorder):
            action()

        return recorder

    def _last_snapshot(self, recorder):
        """The final inventory payload the action published."""
        snapshots = recorder.of_type(CharItemsPayload)
        self.assertTrue(snapshots, "the deposit published nothing")

        return snapshots[-1]

    def _rows_named(self, snapshot, key):
        """Every carried row in a snapshot holding the named item."""
        matching = []

        for row in snapshot.items:
            if row["name"] == key:
                matching.append(row)

        return matching

    def test_merging_a_whole_stack_into_the_vault_republishes(self):
        """The reported defect: the pane still drew the deposited dust."""
        self.bank.deposit(self._carry(2))
        second = self._carry(2)

        recorder = self._record(lambda: self.bank.deposit(second))
        snapshot = self._last_snapshot(recorder)

        self.assertEqual(self._rows_named(snapshot, second.key), [])
        self.assertEqual(snapshot.slots_used, 0)

    def test_the_menu_path_republishes_once(self):
        """deposit_many is what the banking EvMenu calls, and it must publish
        one snapshot for the whole action rather than one per object -- a
        snapshot syncs the handler and walks all 32 slots."""
        self.bank.deposit(self._carry(2))
        second = self._carry(2)

        recorder = self._record(lambda: self.bank.deposit_many([second], None))
        snapshots = recorder.of_type(CharItemsPayload)

        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[-1].slots_used, 0)

    def test_a_partial_deposit_republishes_the_reduced_stack(self):
        """The vault already holds the key, so this is two quantity writes
        and no move at all."""
        self.bank.deposit(self._carry(2))
        carried = self._carry(5)

        recorder = self._record(lambda: self.bank.deposit(carried, 3))
        snapshot = self._last_snapshot(recorder)
        rows = self._rows_named(snapshot, carried.key)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["quantity"], 2)

    def test_a_partial_deposit_into_an_empty_vault_republishes(self):
        """split() moves a DETACHED copy into the vault, so the character's
        leave hook never runs here either."""
        carried = self._carry(5)

        recorder = self._record(lambda: self.bank.deposit(carried, 3))
        snapshot = self._last_snapshot(recorder)
        rows = self._rows_named(snapshot, carried.key)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["quantity"], 2)


class TestFeedIsSilentWithoutSubscribers(EvenniaTest):
    """The whole point of the opt-in: telnet players pay nothing."""

    character_typeclass = BlackoutCharacter

    def test_a_swing_sends_no_feed_messages_to_an_unsubscribed_session(self):
        handler = ensure_combat_handler(self.char1)
        target = spawn_mutant_raider(self.room1)
        ensure_combat_handler(target)
        handler.apply_action({"kind": "attack", "target": target})
        result = ActionResult(hit=True, damage=_SMALL_DAMAGE, hit_prob=1.0)

        with mock.patch("systems.combat.combat.resolve_action", return_value=result):
            with mock.patch.object(type(self.char1), "msg") as mocked_msg:
                handler.tick()

        for call in mocked_msg.call_args_list:
            _args, kwargs = call

            for channel in const.SUBSCRIBABLE_CHANNELS:
                self.assertNotIn(channel, kwargs)
