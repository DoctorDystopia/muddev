"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/05/2026
Description: Tests for the reach of `say` and `yell`.

             The world is built in memory. Plane 0 is one area that holds the
             say range and one tile more, with a chunk of a second area past
             it. Plane 1 has one chunk of the first area.

             No test names a radius. Each position comes from SAY_RADIUS, so
             a change of the radius is not a test failure.

             The load-bearing case is
             `test_say_reaches_exactly_the_rooms_that_the_client_draws`. A say
             reaches each person that the client shows, and no other person.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.gameplay.speech
"""

from unittest import mock

from evennia import DefaultObject, DefaultRoom
from evennia.utils.create import create_object
from evennia.utils.test_resources import EvenniaTest, EvenniaTestCase

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import movement
from systems.core.tilegrid.world import TileWorld, set_world
from systems.gameplay.speech import constants as speech_const
from systems.gameplay.speech import hearing
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import events
from typeclasses.characters import Character as BlackoutCharacter


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = tile_const.CHUNK_SIZE
_GROUND = tile_const.GROUND_PLANE
_UPPER = tile_const.GROUND_PLANE + 1

_HOME_AREA = "oasis"
_OTHER_AREA = "azm_plains"
_FLOOR = "sand"

_RADIUS = speech_const.SAY_RADIUS
_ORIGIN = (2, 2)

# The chunks on each axis that hold the say range and one tile more.
_SPAN = (_ORIGIN[0] + _RADIUS + 1) // _SIZE + 1

# The tiles at the edge of the say range, and one tile past it.
_EDGE = (_ORIGIN[0] + _RADIUS, _ORIGIN[1])
_PAST_EDGE = (_ORIGIN[0] + _RADIUS + 1, _ORIGIN[1])

# A tile of the second area, in the chunk row past the span.
_OTHER_AREA_TILE = (_ORIGIN[0], _SPAN * _SIZE + _ORIGIN[1])

_SPOKEN = "hello there"


# ─── Private helper routines ─────────────────────────────────────────────────

def _chunk(cx: int, cy: int, plane: int, area: str) -> chunkfile.ChunkFile:
    """One open chunk of one area."""
    tile_count = _SIZE * _SIZE

    return chunkfile.ChunkFile(
        cx=cx, cy=cy, plane=plane, floor_names=[_FLOOR], area_names=[area],
        heights=[0] * tile_const.CORNERS_PER_SIDE ** 2,
        floors=[0] * tile_count, flags=[0] * tile_count,
        areas=[0] * tile_count, objects=[])


def _world() -> TileWorld:
    """The home area on plane 0 and plane 1, and the other area past it."""
    chunks = [_chunk(cx, cy, _GROUND, _HOME_AREA)
              for cx in range(_SPAN) for cy in range(_SPAN)]
    chunks.append(_chunk(0, _SPAN, _GROUND, _OTHER_AREA))
    chunks.append(_chunk(0, 0, _UPPER, _HOME_AREA))
    world = TileWorld(chunks)
    world.load_rooms()

    return world


def _lines(character) -> list:
    """Each (text, message type) that the mocked `character.msg` got."""
    found = []

    for call in character.msg.call_args_list:
        sent = call.kwargs.get("text", call.args[0] if call.args else "")

        if isinstance(sent, tuple):
            found.append((str(sent[0]), sent[1].get(feed_const.MESSAGE_TYPE_KEY)))
        else:
            found.append((str(sent), None))

    return found


def _heard(character) -> list:
    """The lines of `character` that carry the spoken text."""
    return [line for line in _lines(character) if _SPOKEN in line[0]]


class _TileWorldMixin:
    """Install the world, and put things on its tiles."""

    def _install_world(self):
        self.world = _world()
        set_world(self.world)
        self.addCleanup(set_world, None)

    def _put(self, thing, tile: tuple, plane: int = _GROUND):
        rooms = self.world.plane(plane).rooms
        movement.place(rooms, thing, *tile, quiet=True)


# ─── Tests ───────────────────────────────────────────────────────────────────

class ListenerTests(_TileWorldMixin, EvenniaTestCase):
    """Who hears each reach. Plain objects stand in for characters."""

    def setUp(self):
        super().setUp()
        self._install_world()
        self.speaker = self._thing("speaker", _ORIGIN)

    def _thing(self, key: str, tile: tuple, plane: int = _GROUND):
        thing = create_object(DefaultObject, key=key)
        self._put(thing, tile, plane)

        return thing

    def _listeners(self, reach: str, *online) -> list:
        return hearing.listeners(self.speaker, reach,
                                 online=[self.speaker, *online])

    def test_say_reaches_the_edge_of_the_say_range(self):
        edge = self._thing("edge", _EDGE)

        self.assertIn(edge, self._listeners(speech_const.REACH_SAY, edge))

    def test_say_stops_past_the_say_range(self):
        past = self._thing("past", _PAST_EDGE)

        self.assertNotIn(past, self._listeners(speech_const.REACH_SAY, past))

    def test_say_does_not_reach_another_plane(self):
        above = self._thing("above", _ORIGIN, plane=_UPPER)

        self.assertNotIn(above, self._listeners(speech_const.REACH_SAY, above))

    def test_say_reaches_exactly_the_rooms_that_the_client_draws(self):
        """
        Nick's rule: a player hears each person that the client shows. The
        diagonals make sure that the two use one metric.
        """
        offsets = [(_RADIUS, 0), (_RADIUS + 1, 0), (0, _RADIUS),
                   (_RADIUS - 3, _RADIUS - 3), (_RADIUS - 2, _RADIUS - 2)]
        others = [self._thing(f"at_{dx}_{dy}",
                              (_ORIGIN[0] + dx, _ORIGIN[1] + dy))
                  for dx, dy in offsets]
        heard = self._listeners(speech_const.REACH_SAY, *others)
        drawn = events._visible_rooms(self.speaker.location)

        for other in others:
            with self.subTest(listener=other.key):
                self.assertEqual(other.location in drawn, other in heard)

    def test_yell_reaches_past_the_say_range(self):
        past = self._thing("past", _PAST_EDGE)

        self.assertIn(past, self._listeners(speech_const.REACH_YELL, past))

    def test_yell_reaches_another_plane_of_the_area(self):
        above = self._thing("above", _ORIGIN, plane=_UPPER)

        self.assertIn(above, self._listeners(speech_const.REACH_YELL, above))

    def test_yell_stops_at_the_edge_of_the_area(self):
        outside = self._thing("outside", _OTHER_AREA_TILE)

        self.assertNotIn(outside,
                         self._listeners(speech_const.REACH_YELL, outside))

    def test_the_speaker_never_hears_itself(self):
        for reach in (speech_const.REACH_SAY, speech_const.REACH_YELL):
            with self.subTest(reach=reach):
                self.assertNotIn(self.speaker, self._listeners(reach))

    def test_an_unknown_reach_reaches_nobody_and_logs(self):
        edge = self._thing("edge", _EDGE)

        with mock.patch.object(hearing.logger, "log_err") as logged:
            found = self._listeners("no_such_reach", edge)

        self.assertEqual([], found)
        logged.assert_called_once()

    def test_off_the_tile_world_only_the_room_hears(self):
        room = create_object(DefaultRoom, key="limbo_like")
        other_room = create_object(DefaultRoom, key="next_door")
        self.speaker.move_to(room, quiet=True)
        same = create_object(DefaultObject, key="same", location=room)
        apart = create_object(DefaultObject, key="apart", location=other_room)

        for reach in (speech_const.REACH_SAY, speech_const.REACH_YELL):
            with self.subTest(reach=reach):
                self.assertEqual([same], self._listeners(reach, same, apart))


class SpeechCommandTests(_TileWorldMixin, EvenniaTest):
    """`say` and `yell` as a player types them."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self._install_world()
        self._put(self.char1, _ORIGIN)

        patcher = mock.patch.object(hearing, "_online_characters",
                                    return_value=[self.char1, self.char2])
        patcher.start()
        self.addCleanup(patcher.stop)

    def _speak(self, listener_tile: tuple, line: str) -> None:
        """Put char2 on a tile, then send a line as char1."""
        self._put(self.char2, listener_tile)
        self.char1.msg = mock.Mock()
        self.char2.msg = mock.Mock()
        self.char1.execute_cmd(line)

    def test_a_say_reaches_a_listener_on_another_tile(self):
        self._speak(_EDGE, f"say {_SPOKEN}")
        heard = _heard(self.char2)

        self.assertEqual(1, len(heard))
        self.assertIn("says", heard[0][0].lower())

    def test_a_say_does_not_reach_past_the_say_range(self):
        self._speak(_PAST_EDGE, f"say {_SPOKEN}")

        self.assertEqual([], _heard(self.char2))

    def test_a_listener_on_the_same_tile_hears_the_line_once(self):
        self._speak(_ORIGIN, f"say {_SPOKEN}")

        self.assertEqual(1, len(_heard(self.char2)))

    def test_the_speaker_sees_the_line_once(self):
        self._speak(_EDGE, f"say {_SPOKEN}")

        self.assertEqual(1, len(_heard(self.char1)))

    def test_a_yell_reaches_past_the_say_range(self):
        self._speak(_PAST_EDGE, f"yell {_SPOKEN}")
        heard = _heard(self.char2)

        self.assertEqual(1, len(heard))
        self.assertIn("yells", heard[0][0].lower())

    def test_a_yell_stops_at_the_edge_of_the_area(self):
        self._speak(_OTHER_AREA_TILE, f"yell {_SPOKEN}")

        self.assertEqual([], _heard(self.char2))

    def test_every_line_has_the_say_type(self):
        """Both commands land on the Local tab, for both sides."""
        for command in ("say", "yell"):
            with self.subTest(command=command):
                self._speak(_EDGE, f"{command} {_SPOKEN}")
                lines = _heard(self.char1) + _heard(self.char2)

                self.assertEqual(2, len(lines))

                for _text, message_type in lines:
                    self.assertEqual(feed_const.MESSAGE_TYPE_SAY, message_type)

    def test_a_whisper_still_needs_the_same_tile(self):
        beside = (_ORIGIN[0] + 1, _ORIGIN[1])
        self._speak(beside, f"whisper {self.char2.key} = {_SPOKEN}")

        self.assertEqual([], _heard(self.char2))

    def test_an_empty_yell_asks_for_a_line(self):
        self._speak(_EDGE, "yell")
        said = " ".join(text for text, _type in _lines(self.char1)).lower()

        self.assertIn("yell what", said)
        self.assertEqual([], _lines(self.char2))
