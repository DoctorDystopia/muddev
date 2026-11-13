"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/08/2026
Description: Cases for the char_music channel, the detail behind it, the
             area hook that feeds it, the quest hook, and the `music`
             command that reads the same rows (DESIGN-0016).

             The load-bearing case is the walk. A character that steps from
             one area into another gets one unlock line, one row turns
             unlocked, and char_music arrives one time. A step inside one
             area marks nothing.

             NOTHING HERE ASSERTS A CENSUS of the shipped tracks. The track
             table is a test table, patched in place, and the areas come
             from the area table.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.interface.statefeed.tests.test_music_feed
"""

import json
from unittest import mock

from evennia.utils.ansi import strip_ansi
from evennia.utils.test_resources import EvenniaCommandTest, EvenniaTest

from commands.music_cmds import CmdMusic
from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import movement
from systems.core.tilegrid.world import TileWorld, set_world
from systems.gameplay.music import constants as music_const
from systems.gameplay.music import detail
from systems.gameplay.quests.quests import QuestBlueprint, QuestStep
from systems.interface.statefeed import buffer
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import events as feed
from systems.interface.statefeed import music as music_feed
from systems.interface.statefeed import resync
from systems.interface.statefeed import subscriptions
from typeclasses.characters import Character as BlackoutCharacter
from world import areas, music_tracks


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = tile_const.CHUNK_SIZE
_GROUND = tile_const.GROUND_PLANE
_FLOOR = "sand"

# Two areas of the area table, so no case names an area by its literal key.
_AREA_KEYS: tuple = tuple(areas.AREAS)
_HOME: str = _AREA_KEYS[0]
_OTHER: str = _AREA_KEYS[1]

# A tile of each area. The home chunk is (0, 0), the other chunk is (1, 0).
_HOME_TILE: tuple = (2, 2)
_HOME_TILE_TWO: tuple = (3, 2)
_OTHER_TILE: tuple = (_SIZE + 2, 2)

_QUEST: str = "music_test_quest"
_HINT: str = "Walk out of the gate."

_TRACKS: dict = {
    "home_track": music_tracks.Track(
        key="home_track", name="Home Track", area=_HOME,
        unlock=music_tracks.UNLOCK_AREA, unlock_key="", hint="", note=""),
    "other_track": music_tracks.Track(
        key="other_track", name="Other Track", area=_OTHER,
        unlock=music_tracks.UNLOCK_AREA, unlock_key="", hint=_HINT, note=""),
    "quest_track": music_tracks.Track(
        key="quest_track", name="Quest Track", area=_HOME,
        unlock=music_tracks.UNLOCK_QUEST, unlock_key=_QUEST, hint="", note=""),
}

_ROW_KEYS: frozenset = frozenset((
    feed_const.MUSIC_ROW_KEY, feed_const.MUSIC_ROW_NAME,
    feed_const.MUSIC_ROW_AREA, feed_const.MUSIC_ROW_STATE,
    feed_const.MUSIC_ROW_HINT,
))

_STATES: frozenset = frozenset((
    feed_const.MUSIC_STATE_LOCKED, feed_const.MUSIC_STATE_UNLOCKED,
))


# ─── Private helper routines ─────────────────────────────────────────────────

def _chunk(cx: int, cy: int, area: str) -> chunkfile.ChunkFile:
    """One open chunk of one area, on the ground plane."""
    tile_count = _SIZE * _SIZE

    return chunkfile.ChunkFile(
        cx=cx, cy=cy, plane=_GROUND, floor_names=[_FLOOR], area_names=[area],
        heights=[0] * tile_const.CORNERS_PER_SIDE ** 2,
        floors=[0] * tile_count, flags=[0] * tile_count,
        areas=[0] * tile_count, objects=[])


def _world() -> TileWorld:
    """The home area in chunk (0, 0), the other area in chunk (1, 0)."""
    world = TileWorld([_chunk(0, 0, _HOME), _chunk(1, 0, _OTHER)])
    world.load_rooms()

    return world


def _blueprint() -> QuestBlueprint:
    """A one-step quest that the quest track names."""
    return QuestBlueprint(
        key=_QUEST, title="Music Test Quest", description="Exists only here.",
        steps=[QuestStep(key="only", description="Do the thing.",
                         targets={"talk:tester": True})],
    )


class _Fixture:
    """The test table, the world, and the read helpers."""

    character_typeclass = BlackoutCharacter

    def _install(self) -> None:
        patcher = mock.patch.dict(music_tracks.TRACKS, _TRACKS, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.world = _world()
        set_world(self.world)
        self.addCleanup(set_world, None)

    def _subscribe(self) -> None:
        for session in self.char1.sessions.all():
            subscriptions.subscribe(session, feed_const.SUBSCRIBE_ALL)

    def _put(self, tile: tuple) -> None:
        rooms = self.world.plane(_GROUND).rooms
        movement.place(rooms, self.char1, *tile, quiet=True)

    def _rows(self) -> list:
        return detail.track_rows(self.char1)

    def _row(self, key: str) -> dict:
        for row in self._rows():
            if row[feed_const.MUSIC_ROW_KEY] == key:
                return row

        self.fail("no row for %s" % key)

    def _unlock_lines(self) -> list:
        """Each unlock line that reached the character."""
        head = music_const.MSG_TRACK_UNLOCKED.split("{name}")[0]
        found = []

        for call in self.char1.msg.call_args_list:
            sent = call.kwargs.get("text", call.args[0] if call.args else "")
            text = sent[0] if isinstance(sent, tuple) else sent

            if head in str(text):
                found.append(str(text))

        return found


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestChannel(_Fixture, EvenniaTest):
    """The shape of the channel in the constants."""

    def setUp(self):
        super().setUp()
        self._install()

    def test_a_client_may_subscribe_to_it(self):
        self.assertIn(feed_const.CHANNEL_CHAR_MUSIC, feed_const.SUBSCRIBABLE_CHANNELS)
        self.assertNotIn(feed_const.CHANNEL_CHAR_MUSIC, feed_const.OPT_IN_CHANNELS)

    def test_channel_is_not_rate_capped(self):
        self.assertNotIn(
            feed_const.CHANNEL_CHAR_MUSIC, feed_const.CHANNEL_MIN_INTERVAL_SECONDS)

    def test_channel_may_be_coalesced(self):
        self.assertIn(feed_const.CHANNEL_CHAR_MUSIC, feed_const.COALESCABLE_CHANNELS)

    def test_emit_is_a_no_op_without_a_subscriber(self):
        self.assertEqual(0, feed.emit_music(self.char1))

    def test_emit_reaches_a_subscribed_session(self):
        self._subscribe()

        self.assertEqual(1, feed.emit_music(self.char1))

    def test_the_payload_survives_json(self):
        body = music_feed.build_payload(self.char1).to_dict()

        self.assertEqual(body, json.loads(json.dumps(body)))

    def test_resync_sends_it(self):
        self._subscribe()

        with mock.patch.object(feed, "emit_music", return_value=1) as sent:
            resync.send_full_state(self.char1)

        sent.assert_called_once()


class TestRows(_Fixture, EvenniaTest):
    """What detail.track_rows says about each track."""

    def setUp(self):
        super().setUp()
        self._install()

    def test_one_row_for_each_track_in_the_order_of_the_table(self):
        keys = [row[feed_const.MUSIC_ROW_KEY] for row in self._rows()]

        self.assertEqual(list(music_tracks.TRACKS), keys)

    def test_every_row_is_well_formed(self):
        for row in self._rows():
            with self.subTest(key=row[feed_const.MUSIC_ROW_KEY]):
                self.assertEqual(_ROW_KEYS, set(row))
                self.assertIn(row[feed_const.MUSIC_ROW_STATE], _STATES)
                self.assertIn(row[feed_const.MUSIC_ROW_AREA], areas.AREAS)
                self.assertTrue(row[feed_const.MUSIC_ROW_NAME])

    def test_a_fresh_character_has_every_row_locked(self):
        for row in self._rows():
            with self.subTest(key=row[feed_const.MUSIC_ROW_KEY]):
                self.assertEqual(
                    feed_const.MUSIC_STATE_LOCKED, row[feed_const.MUSIC_ROW_STATE])

    def test_a_locked_row_carries_its_hint_and_an_unlocked_row_does_not(self):
        self.assertEqual(_HINT, self._row("other_track")[feed_const.MUSIC_ROW_HINT])

        self.char1.music.unlock("other_track")

        row = self._row("other_track")
        self.assertEqual(feed_const.MUSIC_STATE_UNLOCKED, row[feed_const.MUSIC_ROW_STATE])
        self.assertEqual("", row[feed_const.MUSIC_ROW_HINT])

    def test_the_count_reads_the_rows(self):
        self.assertEqual(0, detail.unlocked_count(self._rows()))

        self.char1.music.unlock("home_track")

        self.assertEqual(1, detail.unlocked_count(self._rows()))

    def test_the_area_is_empty_off_the_tile_world(self):
        self.assertEqual("", detail.area_of(self.char1))
        self.assertEqual("", music_feed.build_payload(self.char1).area)

    def test_the_area_is_the_area_of_the_tile(self):
        self._put(_OTHER_TILE)

        self.assertEqual(_OTHER, detail.area_of(self.char1))
        self.assertEqual(_OTHER, music_feed.build_payload(self.char1).area)


class TestTheWalk(_Fixture, EvenniaTest):
    """A step across a border unlocks. A step inside an area does not."""

    def setUp(self):
        super().setUp()
        self._install()
        self._subscribe()
        self.published = []

        patcher = mock.patch.object(feed, "emit", side_effect=self._record)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.char1.msg = mock.Mock()
        self._put(_HOME_TILE)
        buffer.drain_stale()
        self.published.clear()
        self.char1.msg.reset_mock()
        buffer.reset()
        self.addCleanup(buffer.reset)

    def _record(self, obj, payload, force=False):
        self.published.append((payload.channel, payload.to_dict()))

        return 0

    def _music_bodies(self) -> list:
        return [body for sent, body in self.published
                if sent == feed_const.CHANNEL_CHAR_MUSIC]

    def test_the_first_tile_unlocked_the_home_track(self):
        self.assertTrue(self.char1.music.is_unlocked("home_track"))
        self.assertFalse(self.char1.music.is_unlocked("other_track"))
        self.assertEqual(_HOME, self.char1.nattributes.get(music_const.MUSIC_AREA_ATTR))

    def test_a_step_into_another_area_unlocks_once_and_sends_once(self):
        self._put(_OTHER_TILE)
        buffer.drain_stale()

        self.assertEqual(1, len(self._unlock_lines()))
        self.assertIn("Other Track", self._unlock_lines()[0])
        self.assertTrue(self.char1.music.is_unlocked("other_track"))

        bodies = self._music_bodies()
        self.assertEqual(1, len(bodies))
        self.assertEqual(_OTHER, bodies[0][feed_const.MUSIC_AREA_KEY])

        states = {row[feed_const.MUSIC_ROW_KEY]: row[feed_const.MUSIC_ROW_STATE]
                  for row in bodies[0][feed_const.MUSIC_ROWS_KEY]}
        self.assertEqual(feed_const.MUSIC_STATE_UNLOCKED, states["other_track"])
        self.assertEqual(feed_const.MUSIC_STATE_LOCKED, states["quest_track"])

    def test_a_step_inside_the_area_marks_nothing_and_tells_nothing(self):
        self._put(_HOME_TILE_TWO)
        buffer.drain_stale()

        self.assertEqual([], self._unlock_lines())
        self.assertEqual([], self._music_bodies())

    def test_a_step_back_into_a_known_area_sends_the_area_and_tells_nothing(self):
        self._put(_OTHER_TILE)
        buffer.drain_stale()
        self.published.clear()
        self.char1.msg.reset_mock()

        self._put(_HOME_TILE)
        buffer.drain_stale()

        self.assertEqual([], self._unlock_lines())
        self.assertEqual(1, len(self._music_bodies()))
        self.assertEqual(_HOME, self._music_bodies()[0][feed_const.MUSIC_AREA_KEY])

    def test_a_login_inside_an_area_counts_as_an_entry(self):
        self.char1.music.unlock("home_track")
        self.char1.attributes.remove(music_const.UNLOCKED_TRACKS_ATTR)
        self.char1.msg.reset_mock()

        self.char1.at_post_puppet()

        self.assertTrue(self.char1.music.is_unlocked("home_track"))
        self.assertEqual(1, len(self._unlock_lines()))

    def test_a_completed_quest_unlocks_its_track(self):
        self.char1.quests._complete_quest(_blueprint())
        buffer.drain_stale()

        self.assertTrue(self.char1.music.is_unlocked("quest_track"))
        self.assertEqual(1, len(self._unlock_lines()))
        self.assertEqual(1, len(self._music_bodies()))


class TestCommand(_Fixture, EvenniaCommandTest):
    """The listing and the tab are halves of one promise."""

    def setUp(self):
        super().setUp()
        self._install()

    def test_the_listing_names_every_row_with_its_state(self):
        self.char1.music.unlock("home_track")
        rows = self._rows()

        text = strip_ansi(self.call(CmdMusic(), ""))

        self.assertIn("1/%d" % len(rows), text)

        for row in rows:
            with self.subTest(key=row[feed_const.MUSIC_ROW_KEY]):
                self.assertIn(row[feed_const.MUSIC_ROW_NAME], text)

    def test_a_locked_row_prints_its_hint(self):
        text = strip_ansi(self.call(CmdMusic(), ""))

        self.assertIn(_HINT, text)

    def test_an_unlocked_row_prints_no_hint(self):
        self.char1.music.unlock("other_track")

        text = strip_ansi(self.call(CmdMusic(), ""))

        self.assertNotIn(_HINT, text)

    def test_an_empty_table_says_so(self):
        with mock.patch.dict(music_tracks.TRACKS, {}, clear=True):
            text = strip_ansi(self.call(CmdMusic(), ""))

        self.assertIn("no music", text.lower())
