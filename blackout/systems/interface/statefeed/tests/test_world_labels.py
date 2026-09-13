"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Tests for the text an entity carries to be DRAWN in the world.

             Three claims, and they fail in three different places.

             THE CEILING HOLDS. `label` rides the entity row, which is the
             biggest payload the feed sends -- test_payload_size.py prices 1200
             of them against a fixed budget -- so an uncapped label is a budget
             nothing can be written against. labels.normalise is the only thing
             enforcing that, and it has to be idempotent, because the
             serializer runs it a second time over a value the writer already
             cleaned.

             THE FIELDS APPEAR TOGETHER OR NOT AT ALL. Nearly every entity in
             the game has nothing to say, and the absent case is the common
             one: a client reads "no label key" as "draw no text", and two
             empty strings per entity per move would be paid by the whole room
             so that a signpost need not be a special case.

             A SIGN IS NOT AN ITEM. It declares its own asset kind precisely so
             it does not fall through _classify to "item" and get offered as
             `get sign` -- the Foundry Furnace bug, which the statefeed
             constants describe at length because a test account walked off
             with a furnace.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \
        systems.interface.statefeed.tests.test_world_labels
"""

import unittest

from evennia import create_object
from evennia.utils.test_resources import EvenniaTestCase

from systems.interface.statefeed import constants as const
from systems.interface.statefeed import labels, serializers
from typeclasses import signs
from typeclasses.signs import Marker, Sign
from typeclasses.rooms import GridTile
from typeclasses.skill_facilities import FurnaceFacility
from typeclasses.spawners import (
    ATTRIBUTE_SPAWNER_REGISTRY,
    SPAWNER_REGISTRY,
    load_all_spawners,
)


class TestLabelNormalisation(unittest.TestCase):
    """
    Purpose: The cap, the markup and the idempotence, with no database.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        Plain unittest.TestCase: normalise touches no object and no DB, so
        anything heavier would buy 23ms a test for nothing. CLAUDE.md's table
        of base-class costs is the argument.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """

    def test_nothing_in_gives_nothing_out(self):
        for empty in (None, "", "   ", "\n\n", 0):
            with self.subTest(empty=empty):
                self.assertEqual(labels.normalise(empty), "")


    def test_markup_is_stripped_rather_than_drawn(self):
        cleaned = labels.normalise("|rDANGER|n")

        self.assertEqual(cleaned, "DANGER")


    def test_the_cap_counts_what_is_drawn_and_not_the_markup(self):
        # Padded to well past the cap in markup alone. Counting raw characters
        # would cut a label a player sees as short, which is the bug that makes
        # the ceiling feel arbitrary to whoever hits it.
        padding = "|r|n" * 40
        cleaned = labels.normalise(padding + "SHORT")

        self.assertEqual(cleaned, "SHORT")


    def test_a_long_label_is_cut_to_the_cap(self):
        cleaned = labels.normalise("x" * (const.WORLD_LABEL_MAX_CHARS * 3))

        self.assertEqual(len(cleaned), const.WORLD_LABEL_MAX_CHARS)


    def test_more_lines_than_the_cap_allows_are_dropped(self):
        authored = "\n".join(
            str(number) for number in range(const.WORLD_LABEL_MAX_LINES * 2))
        cleaned = labels.normalise(authored)
        lines = cleaned.splitlines()

        self.assertEqual(len(lines), const.WORLD_LABEL_MAX_LINES)


    def test_blank_lines_are_dropped_rather_than_counted(self):
        # An author who double-spaced two lines meant two lines. Spending the
        # line budget on nothing would silently eat the second.
        cleaned = labels.normalise("TOP\n\n\nBOTTOM")

        self.assertEqual(cleaned, "TOP\nBOTTOM")


    def test_runs_of_whitespace_collapse(self):
        cleaned = labels.normalise("  WIDE    GAP  ")

        self.assertEqual(cleaned, "WIDE GAP")


    def test_normalising_twice_changes_nothing(self):
        # The property this whole arrangement rests on: the writer cleans the
        # value and the serializer cleans it again, and the second pass must be
        # free. Without it the two would be two truncations that can disagree.
        authored = "|yTRADE   TOWN|n\n\n" + "z" * 200

        once = labels.normalise(authored)
        twice = labels.normalise(once)

        self.assertEqual(once, twice)


    def test_a_non_string_is_read_rather_than_refused(self):
        cleaned = labels.normalise(42)

        self.assertEqual(cleaned, "42")


class TestSignsCarryTheirText(EvenniaTestCase):
    """
    Purpose: What a Sign stores, and what the feed says about it.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        EvenniaTestCase rather than EvenniaTest: these need a database to make
        an object in and none of the two accounts, two rooms, two characters
        and a session EvenniaTest builds per method.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """

    def _sign(self, text="", typeclass=Sign):
        made = create_object(typeclass, key="test sign", location=None)

        if text:
            made.world_label = text

        return made


    def test_the_property_cleans_what_it_stores(self):
        sign = self._sign("|rKEEP   OUT|n")

        self.assertEqual(sign.db.world_label, "KEEP OUT")


    def test_writing_nothing_removes_the_row(self):
        # A blank attribute and a missing one would be two spellings of "this
        # sign says nothing", and every reader would have to know both.
        sign = self._sign("SOMETHING")
        sign.world_label = "   "

        self.assertIsNone(sign.db.world_label)
        self.assertEqual(sign.world_label, "")


    def test_a_label_reaches_the_serialized_entity(self):
        sign = self._sign("TRADE TOWN")
        body = serializers.serialize_entity(sign)

        self.assertEqual(body["label"], "TRADE TOWN")
        self.assertEqual(body["label_kind"], const.LABEL_KIND_SIGN)


    def test_a_marker_names_its_own_kind(self):
        marker = self._sign("WIP", typeclass=Marker)
        body = serializers.serialize_entity(marker)

        self.assertEqual(body["label_kind"], const.LABEL_KIND_MARKER)


    def test_an_unwritten_sign_sends_neither_field(self):
        sign = self._sign()
        body = serializers.serialize_entity(sign)

        self.assertNotIn("label", body)
        self.assertNotIn("label_kind", body)


    def test_nothing_else_in_the_world_grows_a_label(self):
        # The common case, and the expensive one to get wrong: `label` is
        # omitted for every entity with nothing to say, which is nearly all of
        # them.
        plain = create_object(key="a rock", location=None)
        body = serializers.serialize_entity(plain)

        self.assertNotIn("label", body)


    def test_a_sign_is_not_offered_as_something_to_pocket(self):
        # The Foundry Furnace bug, in a new place: an entity that falls through
        # _classify to "item" is handed a `get` by TARGETED_VERB_BY_KIND, and a
        # client offers to put the signpost in a bag.
        sign = self._sign("TRADE TOWN")
        body = serializers.serialize_entity(sign)

        self.assertEqual(body["kind"], const.ASSET_KIND_SIGN)
        self.assertNotIn("get", body["interact"])


    def test_a_written_sign_offers_the_read_verb(self):
        # What a click sends, and it must be a command a telnet player could
        # type -- the invariant that keeps a graphical client from reaching
        # anything a text one cannot.
        sign = self._sign("TRADE TOWN")
        body = serializers.serialize_entity(sign)

        self.assertEqual(body["interact"], f"read {sign.key}")


    def test_a_blank_sign_affords_nothing(self):
        # A click answering "it is blank" is a click worth not offering. An
        # unwritten sign is a builder's half-finished work, not a puzzle.
        sign = self._sign()
        body = serializers.serialize_entity(sign)

        self.assertEqual(body["interact"], "")


    def test_a_label_written_around_the_property_still_cannot_blow_the_payload(self):
        # The second half of why normalise runs on the read path too. A fixture
        # or a migration writing db.world_label directly bypasses the setter;
        # the feed must still be bounded.
        sign = self._sign()
        sign.db.world_label = "y" * (const.WORLD_LABEL_MAX_CHARS * 5)

        body = serializers.serialize_entity(sign)

        self.assertEqual(len(body["label"]), const.WORLD_LABEL_MAX_CHARS)


class TestMapAuthoredSignage(EvenniaTestCase):
    """
    Purpose: The spawner a map dispatches to, and who owns the words.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        Calls the spawner directly rather than rebuilding a map. The dispatch
        itself -- GridTile.at_object_post_spawn matching a prototype key
        against SPAWNER_REGISTRY -- is machinery every facility already rides,
        and the part that is new here is what the routine does with a room.

        Registration IS asserted, separately, because the map module and the
        decorator agree on a string and nothing else checks the copy. That is
        the same guard test_quest_oasis_in_the_wastes.py keeps over the lone
        android's spawner key, and for the same reason: a typo leaves a tile
        that looks signed with no sign on it and raises nothing either way.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """

    def _tile(self, label=None, desc=None):
        room = create_object(key="a tile", location=None)

        if label is not None:
            room.attributes.add(signs.SIGNPOST_LABEL_ATTR, label)

        if desc is not None:
            room.attributes.add(signs.SIGNPOST_DESC_ATTR, desc)

        return room


    def test_the_map_attribute_reaches_a_spawner(self):
        # The one string a map module and this package have to agree on. It is
        # the ATTRIBUTE and not the room key: dispatching on the key meant a
        # sign could never share a tile, because a tile has exactly one key.
        load_all_spawners()

        self.assertIn(signs.SIGNPOST_LABEL_ATTR, ATTRIBUTE_SPAWNER_REGISTRY)


    def test_a_signed_tile_gets_a_sign_saying_what_the_map_said(self):
        room = self._tile(label="OASIS")

        made = signs.spawn_signpost(room)

        self.assertIsNotNone(made)
        self.assertEqual(made.location, room)
        self.assertEqual(made.world_label, "OASIS")


    def test_the_map_stays_the_owner_of_the_words(self):
        # Re-asserted rather than only set at creation. A map module editing
        # the line and rebuilding has to be enough -- otherwise correcting a
        # typo means destroying the tile, which is the failure mode CLAUDE.md
        # records for facts stamped into database rows.
        room = self._tile(label="OASIS")
        signs.spawn_signpost(room)

        room.attributes.add(signs.SIGNPOST_LABEL_ATTR, "OASIS (EAST GATE)")
        made = signs.spawn_signpost(room)

        self.assertEqual(made.world_label, "OASIS (EAST GATE)")


    def test_a_rebuild_does_not_stack_a_second_post(self):
        room = self._tile(label="OASIS")

        first = signs.spawn_signpost(room)
        second = signs.spawn_signpost(room)

        self.assertEqual(first, second)
        self.assertEqual(len(room.contents), 1)


    def test_a_tile_naming_no_text_gets_nothing(self):
        # A blank post is indistinguishable from scenery, so the author's
        # mistake shows as a missing sign rather than a mystery object.
        room = self._tile()

        made = signs.spawn_signpost(room)

        self.assertIsNone(made)
        self.assertEqual(room.contents, [])


    def test_a_map_may_describe_the_post_itself(self):
        room = self._tile(label="OASIS", desc="A scavenged road sign.")

        made = signs.spawn_signpost(room)

        self.assertEqual(made.db.desc, "A scavenged road sign.")


    def test_a_map_that_describes_nothing_leaves_the_stock_description(self):
        room = self._tile(label="OASIS")

        made = signs.spawn_signpost(room)

        self.assertEqual(made.db.desc, Sign.default_desc)


    def test_the_map_cannot_author_past_the_cap(self):
        room = self._tile(label="z" * (const.WORLD_LABEL_MAX_CHARS * 4))

        made = signs.spawn_signpost(room)

        self.assertEqual(
            len(made.world_label), const.WORLD_LABEL_MAX_CHARS)


class TestTheLabelKindVocabulary(unittest.TestCase):
    """
    Purpose: That no typeclass names a label kind the server does not declare.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        LABEL_KINDS is the vocabulary's one owner, and this is what makes it
        one rather than a list nothing reads. The failure it catches is a
        typeclass declaring `label_kind = "graffito"`: the payload would carry
        it, the client's colour table would miss it, and the entity would draw
        in the fallback colour with nothing raised anywhere -- which is
        precisely the "Pole clearing" bug that cost the room-kind table a
        guard test of its own.

        Derived from the classes rather than asserted as a census, per
        CLAUDE.md: the list of typeclasses comes from Sign's own subclass
        tree, so a fourth kind of sign is covered the moment it exists and
        this test never needs editing.

        Plain unittest.TestCase -- reading a class attribute needs no database.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """

    def _sign_classes(self):
        found = [Sign]
        pending = [Sign]

        while pending:
            current = pending.pop()

            for subclass in current.__subclasses__():
                found.append(subclass)
                pending.append(subclass)

        return found


    def test_every_sign_typeclass_names_a_declared_kind(self):
        classes = self._sign_classes()

        self.assertGreater(
            len(classes), 1,
            "no Sign subclasses found; this test would be inert")

        for sign_class in classes:
            with self.subTest(typeclass=sign_class.__name__):
                self.assertIn(sign_class.label_kind, const.LABEL_KINDS)


    def test_no_two_sign_typeclasses_declare_the_same_kind(self):
        # Only classes that DECLARE a kind are checked. A subclass inheriting
        # its parent's is still a sign and means to be drawn as one; a class
        # that meant to differ and picked a kind already taken is the bug --
        # two things a player is supposed to tell apart, drawn identically.
        declared = {}

        for sign_class in self._sign_classes():
            if "label_kind" not in sign_class.__dict__:
                continue

            kind = sign_class.__dict__["label_kind"]

            with self.subTest(typeclass=sign_class.__name__):
                self.assertNotIn(
                    kind, declared,
                    f"{sign_class.__name__} and {declared.get(kind)} both "
                    f"declare '{kind}'")

            declared[kind] = sign_class.__name__


class TestASignCanShareATile(EvenniaTestCase):
    """
    Purpose: That a signpost stands BESIDE whatever else a tile carries,
             rather than instead of it.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        The limitation this replaced was a dispatch one, not a rendering one:
        SPAWNER_REGISTRY is keyed on the room key and a tile has exactly one
        key, so a tile keyed "Foundry Furnace Facility" could never also be
        keyed "Signpost" and signage could never label anything. Dispatch now
        runs off a room ATTRIBUTE, and these assert the two paths do not
        interfere -- in both orders, because the hook runs the key spawner
        first and a test that only checked one order would pass with the sign
        quietly overwriting the facility.

        Driven through GridTile.at_object_post_spawn rather than by calling
        the spawners directly, because the hook IS the thing that changed.

    Notes/References:
        typeclasses/spawners.py has the argument for two registries.

    Author: Nick Hobar
    Creation date: 09/12/2026
    """

    def _tile(self):
        return create_object(GridTile, key="a tile", location=None)


    def _signed(self, prototype, label):
        signed = dict(prototype)
        signed["attrs"] = [(signs.SIGNPOST_LABEL_ATTR, label)]

        return signed


    def test_the_attribute_is_what_dispatches_a_sign(self):
        # Not the room key. A tile keyed anything at all gets a sign if it
        # declares the attribute, which is the whole fix -- and the key is
        # asserted ABSENT so a well-meant re-registration cannot quietly bring
        # back the one-spawner-per-tile limit this replaced.
        load_all_spawners()

        self.assertIn(
            signs.SIGNPOST_LABEL_ATTR, ATTRIBUTE_SPAWNER_REGISTRY)
        self.assertNotIn(signs.SIGNPOST_ROOM_KEY, SPAWNER_REGISTRY)


    def test_a_tile_with_no_sign_attribute_gets_no_sign(self):
        tile = self._tile()

        tile.at_object_post_spawn(prototype={"key": "Oasis"})

        self.assertEqual(tile.contents, [])


    def test_a_signed_tile_gets_its_sign(self):
        tile = self._tile()
        tile.attributes.add(signs.SIGNPOST_LABEL_ATTR, "OASIS")

        tile.at_object_post_spawn(prototype={"key": "Oasis"})

        standing = tile.contents

        self.assertEqual(len(standing), 1)
        self.assertEqual(standing[0].world_label, "OASIS")


    def test_a_facility_tile_can_also_carry_a_sign(self):
        # The case this was built for: the furnace keeps its key, so it keeps
        # its facility, its minimap colour and its desc, and the sign stands
        # beside it.
        tile = self._tile()
        tile.attributes.add(signs.SIGNPOST_LABEL_ATTR, "FOUNDRY")

        tile.at_object_post_spawn(
            prototype={"key": "Foundry Furnace Facility"})

        standing = tile.contents
        labels_found = [
            obj.world_label for obj in standing
            if getattr(obj, "world_label", "")
        ]

        self.assertEqual(len(standing), 2, f"expected furnace + sign: {standing}")
        self.assertEqual(labels_found, ["FOUNDRY"])
        self.assertTrue(
            any(isinstance(obj, FurnaceFacility) for obj in standing),
            f"the facility did not survive the sign: {standing}")


    def test_a_rebuild_of_a_signed_facility_stacks_nothing(self):
        tile = self._tile()
        tile.attributes.add(signs.SIGNPOST_LABEL_ATTR, "FOUNDRY")
        prototype = {"key": "Foundry Furnace Facility"}

        tile.at_object_post_spawn(prototype=prototype)
        tile.at_object_post_spawn(prototype=prototype)

        self.assertEqual(len(tile.contents), 2)


    def test_a_broken_decoration_does_not_cost_the_tile_its_facility(self):
        # The asymmetry the hook documents: a key spawner is the tile's reason
        # for existing and should be loud, a decoration must never be able to
        # take it out.
        tile = self._tile()
        tile.attributes.add("exploding_decoration", True)

        def _explode(room):
            raise RuntimeError("a decoration that cannot be built")

        ATTRIBUTE_SPAWNER_REGISTRY["exploding_decoration"] = _explode

        try:
            tile.at_object_post_spawn(
                prototype={"key": "Foundry Furnace Facility"})
        finally:
            del ATTRIBUTE_SPAWNER_REGISTRY["exploding_decoration"]

        self.assertTrue(
            any(isinstance(obj, FurnaceFacility) for obj in tile.contents),
            f"the facility was lost to a broken decoration: {tile.contents}")
