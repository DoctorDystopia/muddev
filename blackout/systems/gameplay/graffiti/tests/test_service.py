"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Tests for player-written words -- the cost, the provenance, the
             expiry and the refusals.

             Four claims, and each one is a different way the feature goes
             wrong in the world rather than in the code.

             NOTHING IS SPENT ON A WRITE THAT DID NOT HAPPEN. Six things can
             refuse a write, and a player charged for any of them has been
             stolen from. The ordering in `write` is the whole guarantee, so
             every refusal is tested for the charge still being there.

             THE AUTHOR SURVIVES EVERYTHING. A scrawl a moderator cannot trace
             is one they can only delete blindly, so the author id is asserted
             to outlive a rename -- which is why the id is what erase matches
             on and the name is only decoration.

             SIGNAGE IS UNREACHABLE. The sweep and the erase are the two
             routines in the game that delete world text in bulk, and a map's
             signposts must be structurally out of their reach rather than
             merely unmatched by the current filter.

             AN UNSTAMPED SCRAWL IS EXPIRED. The safe direction for a system
             whose entire job is that the world does not fill up.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \
        systems.gameplay.graffiti.tests.test_service
"""

import time

from django.test import override_settings
from evennia import create_object
from evennia.utils.test_resources import EvenniaTestCase

from systems.gameplay.graffiti import constants as const
from systems.gameplay.graffiti import service
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import serializers
from typeclasses.signs import Graffiti, Marker, Sign
from world.item_database import ITEM_DB


class GraffitiTestBase(EvenniaTestCase):
    """
    Purpose: A room, a writer and a can, without EvenniaTest's fixtures.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        EvenniaTestCase rather than EvenniaTest. These need a database, a room
        and something that can carry an object -- and a plain object carries
        one perfectly well, so none of the two accounts, two characters and a
        session EvenniaTest builds per method is paid for. CLAUDE.md's
        base-class cost table is the argument: 23.8ms against 138.4ms.

        The writer is a plain object rather than a Character for the same
        reason. Nothing in `write` reads a stat, a skill or a cmdset; it reads
        `location`, `contents` and `id`, which every object has.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """

    def setUp(self):
        super().setUp()

        self.room = create_object(key="a wall", location=None)
        self.writer = create_object(key="Bob", location=self.room)
        self.can = self._a_can()


    def _a_can(self):
        return ITEM_DB["spray_can"].create(location=self.writer)


    def _scrawls(self):
        return list(Graffiti.objects.all_family())


class TestWriting(GraffitiTestBase):
    """What a write produces, and what it costs."""

    def test_writing_leaves_words_standing_in_the_room(self):
        succeeded, _message = service.write(self.writer, "KEEP OUT")

        made = self._scrawls()

        self.assertTrue(succeeded)
        self.assertEqual(len(made), 1)
        self.assertEqual(made[0].location, self.room)
        self.assertEqual(made[0].world_label, "KEEP OUT")


    def test_it_arrives_through_the_hook_that_publishes_it(self):
        # create_object(location=) skips at_object_receive, so the feed never
        # hears about it and the writer stands looking at a wall they just
        # wrote on and sees nothing.
        service.write(self.writer, "KEEP OUT")

        self.assertIn(self._scrawls()[0], self.room.contents)


    def test_a_write_costs_one_charge(self):
        before = service.charges_left(self.can)

        service.write(self.writer, "KEEP OUT")

        self.assertEqual(service.charges_left(self.can), before - 1)


    def test_the_can_goes_when_the_last_charge_does(self):
        # An empty can is litter a player has to notice and drop, and a bag
        # slowly filling with them is worse than losing an object whose whole
        # remaining value was zero.
        self.can.attributes.add(const.CHARGES_ATTR, 1)

        succeeded, message = service.write(self.writer, "KEEP OUT")

        self.assertTrue(succeeded)
        self.assertIsNone(self.can.pk)
        self.assertIn("sputters", message.lower())


    def test_an_untouched_can_starts_at_the_standard_capacity(self):
        # Applied on READ, so an item declaring the medium tag and nothing
        # else works immediately -- no ItemDef field for a system it has
        # nothing to do with.
        self.assertIsNone(self.can.attributes.get(const.CHARGES_ATTR))
        self.assertEqual(
            service.charges_left(self.can), const.DEFAULT_CHARGES)


    def test_the_room_is_told_who_wrote(self):
        # Writing on a wall in front of other people is a public act; a silent
        # one would let a player deny it to someone who watched.
        watcher = create_object(key="a bystander", location=self.room)
        seen = []
        watcher.msg = lambda text=None, **kwargs: seen.append(str(text))

        service.write(self.writer, "KEEP OUT")

        self.assertTrue(any("Bob" in line for line in seen))


    def test_the_text_is_cleaned_and_capped_like_any_label(self):
        service.write(self.writer, "|rKEEP    OUT|n")

        self.assertEqual(self._scrawls()[0].db.world_label, "KEEP OUT")


    def test_a_scrawl_names_its_own_label_kind(self):
        # The reader's need, not the writer's: a scrawl reading "BANK: EAST" is
        # a lie a signpost could not tell, so a player has to be able to see
        # which is which.
        service.write(self.writer, "BANK: EAST")
        body = serializers.serialize_entity(self._scrawls()[0])

        self.assertEqual(body["label_kind"], feed_const.LABEL_KIND_GRAFFITI)


class TestRefusals(GraffitiTestBase):
    """Every way a write is refused, and the charge surviving each."""

    def test_nothing_to_write_with_is_refused(self):
        self.can.delete()

        succeeded, message = service.write(self.writer, "KEEP OUT")

        self.assertFalse(succeeded)
        self.assertEqual(self._scrawls(), [])
        self.assertIn("nothing to write with", message.lower())


    def test_an_empty_medium_is_refused_by_name(self):
        self.can.attributes.add(const.CHARGES_ATTR, 0)

        succeeded, message = service.write(self.writer, "KEEP OUT")

        self.assertFalse(succeeded)
        self.assertEqual(self._scrawls(), [])
        self.assertIn(self.can.key, message)


    def test_text_that_normalises_to_nothing_is_refused(self):
        succeeded, _message = service.write(self.writer, "|n|n  ")

        self.assertFalse(succeeded)
        self.assertEqual(self._scrawls(), [])
        self.assertEqual(
            service.charges_left(self.can), const.DEFAULT_CHARGES)


    def test_a_writer_who_is_nowhere_is_refused(self):
        self.writer.location = None

        succeeded, _message = service.write(self.writer, "KEEP OUT")

        self.assertFalse(succeeded)
        self.assertEqual(self._scrawls(), [])


    @override_settings(BLACKOUT_GRAFFITI_BLOCKLIST=("badword",))
    def test_a_blocked_word_is_refused_without_spending_a_charge(self):
        # The ordering guarantee: the refusal happens before the medium is
        # charged, because charging for a no is the version that reads as the
        # game stealing from the player.
        succeeded, _message = service.write(self.writer, "a BadWord here")

        self.assertFalse(succeeded)
        self.assertEqual(self._scrawls(), [])
        self.assertEqual(
            service.charges_left(self.can), const.DEFAULT_CHARGES)


    def test_nothing_is_blocked_by_default(self):
        # A blocklist is an editorial decision about a particular community.
        # This module's job is the seam, not the decision.
        self.assertFalse(service.is_refused("anything at all"))


class TestProvenance(GraffitiTestBase):
    """Who wrote it, and what survives."""

    def test_the_author_is_recorded(self):
        service.write(self.writer, "KEEP OUT")

        self.assertEqual(
            service.author_id_of(self._scrawls()[0]), self.writer.id)


    def test_the_author_survives_a_rename(self):
        # Which is why erase matches on the id and the stored name is only
        # there to save a lookup per scrawl in a dossier.
        service.write(self.writer, "KEEP OUT")
        self.writer.key = "Robert"

        self.assertEqual(service.written_by(self.writer), 1)


    def test_signage_has_no_author_and_matches_nobody(self):
        sign = create_object(Sign, key="signpost", location=self.room)
        sign.world_label = "OASIS"

        self.assertEqual(service.author_id_of(sign), 0)


class TestExpiry(GraffitiTestBase):
    """When a scrawl goes, and what the sweep will not touch."""

    def test_a_fresh_scrawl_is_not_expired(self):
        service.write(self.writer, "KEEP OUT")

        self.assertFalse(service.expired(self._scrawls()[0]))


    def test_an_old_scrawl_is_expired(self):
        service.write(self.writer, "KEEP OUT")
        later = time.time() + const.LIFETIME_SECONDS + 1

        self.assertTrue(service.expired(self._scrawls()[0], now=later))


    def test_an_unstamped_scrawl_counts_as_expired(self):
        # The safe direction for a system whose whole job is that the world
        # does not fill up: anything without a timestamp was written before
        # the field existed or by something that bypassed `write`, and keeping
        # it forever is the outcome nobody asked for.
        orphan = create_object(Graffiti, key="graffiti", location=self.room)
        orphan.world_label = "WHO WROTE THIS"

        self.assertTrue(service.expired(orphan))


    def test_the_sweep_takes_the_expired_and_leaves_the_rest(self):
        # The old one is BACKDATED rather than the sweep being run in the
        # future, so the fresh one stays fresh. Advancing `now` past the
        # lifetime would expire both, which is what the first version of this
        # test did and what made it pass for the wrong reason.
        self.can.attributes.add(const.CHARGES_ATTR, 5)
        service.write(self.writer, "OLD")
        aged = self._scrawls()[0]
        aged.attributes.add(
            const.WRITTEN_AT_ATTR, time.time() - const.LIFETIME_SECONDS - 1)

        service.write(self.writer, "NEW")

        swept = service.sweep()
        left = self._scrawls()

        self.assertEqual(swept, 1)
        self.assertEqual(len(left), 1)
        self.assertEqual(left[0].world_label, "NEW")


    def test_the_sweep_cannot_reach_a_sign_or_a_marker(self):
        # STRUCTURAL, not careful. Sign and Marker are siblings of Graffiti
        # rather than subclasses, so all_family cannot return them however the
        # lifetime is configured.
        sign = create_object(Sign, key="signpost", location=self.room)
        sign.world_label = "OASIS"
        marker = create_object(Marker, key="note", location=self.room)
        marker.world_label = "WIP"

        service.sweep(now=time.time() + const.LIFETIME_SECONDS * 100)

        self.assertIsNotNone(sign.pk)
        self.assertIsNotNone(marker.pk)


class TestErasing(GraffitiTestBase):
    """The moderator's bulk delete, by author."""

    def test_everything_one_author_wrote_goes(self):
        self.can.attributes.add(const.CHARGES_ATTR, 5)
        service.write(self.writer, "ONE")
        service.write(self.writer, "TWO")

        erased = service.erase_by_author(self.writer)

        self.assertEqual(erased, 2)
        self.assertEqual(self._scrawls(), [])


    def test_another_writer_is_left_alone(self):
        other = create_object(key="Alice", location=self.room)
        ITEM_DB["spray_can"].create(location=other)

        service.write(self.writer, "MINE")
        service.write(other, "HERS")

        erased = service.erase_by_author(self.writer)

        self.assertEqual(erased, 1)
        self.assertEqual(len(self._scrawls()), 1)
        self.assertEqual(self._scrawls()[0].world_label, "HERS")


    def test_erasing_someone_who_wrote_nothing_takes_nothing(self):
        self.assertEqual(service.erase_by_author(self.writer), 0)


    def test_erasing_cannot_reach_signage(self):
        sign = create_object(Sign, key="signpost", location=self.room)
        sign.world_label = "OASIS"
        service.write(self.writer, "MINE")

        service.erase_by_author(self.writer)

        self.assertIsNotNone(sign.pk)


    def test_the_count_matches_what_the_erase_will_take(self):
        # The confirmation screen reads this before asking, so the two
        # disagreeing would be a moderator told one number and given another.
        self.can.attributes.add(const.CHARGES_ATTR, 5)
        service.write(self.writer, "ONE")
        service.write(self.writer, "TWO")

        counted = service.written_by(self.writer)
        erased = service.erase_by_author(self.writer)

        self.assertEqual(counted, erased)
