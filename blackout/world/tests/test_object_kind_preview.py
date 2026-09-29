"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/28/2026
Description: Tests that each object kind that stands something up returns
             its entity, and that the `preview` of the kind names the asset
             key and the family that the statefeed sends for that entity.

             The terrain editor draws the `preview` model on the tile. The
             game client draws the entity from its `room_players` row. This
             test keeps the two the same, with no second owner of the key.

             The tile sync gives the facing to the entity that a spawner
             returns. A spawner that returns None leaves its entity with no
             facing, and the model does not turn in the game.
"""

from evennia import create_object
from evennia.utils.test_resources import EvenniaTestCase

from systems.core.tilegrid import constants as tile_const
from systems.interface.statefeed import serializers
from typeclasses.signs import place_signpost
from typeclasses.spawners import SPAWNER_REGISTRY, load_all_spawners
from world.object_kinds import OBJECT_KINDS


# ─── Private constant definitions ────────────────────────────────────────────

_ROOM_TYPECLASS = "typeclasses.rooms.Room"

# The words of a test signpost. Any legal chunk text.
_SIGN_WORDS = "Preview"


# ─── Private helper routines ─────────────────────────────────────────────────

def _stands_up(kind) -> bool:
    """Return True if a kind stands up an entity: a spawner or a sign."""
    return bool(kind.spawner) \
        or kind.category == tile_const.OBJECT_TEXT_CATEGORY


def _stand(kind, room):
    """Stand up the entity of one kind in `room`, as the tile sync does."""
    if kind.spawner:
        return SPAWNER_REGISTRY[kind.spawner](room)

    return place_signpost(room, _SIGN_WORDS)


# ─── Tests ───────────────────────────────────────────────────────────────────

class ObjectKindPreviewTests(EvenniaTestCase):

    def setUp(self):
        super().setUp()
        load_all_spawners()

    def _each_standing_kind(self):
        """Yield (key, kind, fresh room) for each kind that stands up."""
        for key, kind in OBJECT_KINDS.items():
            if _stands_up(kind):
                room = create_object(_ROOM_TYPECLASS, key="preview " + key)

                yield key, kind, room

    def test_every_spawner_returns_the_entity_it_stood_up(self):
        for key, kind, room in self._each_standing_kind():
            with self.subTest(kind=key):
                standing = _stand(kind, room)

                self.assertIsNotNone(standing)
                self.assertEqual(standing.location, room)

    def test_a_second_run_returns_the_same_entity(self):
        for key, kind, room in self._each_standing_kind():
            with self.subTest(kind=key):
                first = _stand(kind, room)

                self.assertEqual(_stand(kind, room), first)

    def test_the_preview_is_the_asset_and_family_the_statefeed_sends(self):
        for key, kind, room in self._each_standing_kind():
            with self.subTest(kind=key):
                row = serializers.serialize_entity(_stand(kind, room))

                self.assertEqual((row["asset"], row["family"]), kind.preview)

    def test_a_kind_that_stands_up_nothing_has_no_preview(self):
        for key, kind in OBJECT_KINDS.items():
            if not _stands_up(kind):
                with self.subTest(kind=key):
                    self.assertEqual(kind.preview, ())
