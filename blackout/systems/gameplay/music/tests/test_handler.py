"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/08/2026
Description: Cases for MusicHandler, the one writer of db.unlocked_tracks.

             The track table is a test table, patched in place. The shipped
             table has one track today, and a case that reads it would
             break on the second track.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.gameplay.music.tests.test_handler
"""

from unittest import mock

from evennia import DefaultObject
from evennia.utils.create import create_object
from evennia.utils.test_resources import EvenniaTestCase

from systems.gameplay.music import constants
from systems.gameplay.music.handler import MusicHandler
from world import areas, music_tracks


# ─── Private constant definitions ────────────────────────────────────────────

# Two areas of the area table, so no case names an area by its literal key.
_AREA_KEYS: tuple = tuple(areas.AREAS)
_HOME: str = _AREA_KEYS[0]
_OTHER: str = _AREA_KEYS[1]

_QUEST: str = "a_test_quest"

_TRACKS: dict = {
    "home_one": music_tracks.Track(
        key="home_one", name="Home One", area=_HOME,
        unlock=music_tracks.UNLOCK_AREA, unlock_key="", hint="", note=""),
    "home_two": music_tracks.Track(
        key="home_two", name="Home Two", area=_HOME,
        unlock=music_tracks.UNLOCK_AREA, unlock_key="", hint="", note=""),
    "home_quest": music_tracks.Track(
        key="home_quest", name="Home Quest", area=_HOME,
        unlock=music_tracks.UNLOCK_QUEST, unlock_key=_QUEST, hint="", note=""),
    "other_one": music_tracks.Track(
        key="other_one", name="Other One", area=_OTHER,
        unlock=music_tracks.UNLOCK_AREA, unlock_key="", hint="", note=""),
}


# ─── Tests ───────────────────────────────────────────────────────────────────

class HandlerTests(EvenniaTestCase):
    """The reads and the three writers, on a plain object."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(music_tracks.TRACKS, _TRACKS, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.obj = create_object(DefaultObject, key="listener")
        self.obj.msg = mock.Mock()
        self.handler = MusicHandler(self.obj)

    def _lines(self) -> list:
        return [call.args[0][0] for call in self.obj.msg.call_args_list]

    def test_a_fresh_character_holds_nothing(self):
        self.assertEqual((), self.handler.unlocked_keys())
        self.assertFalse(self.handler.is_unlocked("home_one"))

    def test_an_unlock_is_stored_and_told_once(self):
        self.assertTrue(self.handler.unlock("home_one"))
        self.assertFalse(self.handler.unlock("home_one"))

        self.assertEqual(("home_one",), self.handler.unlocked_keys())
        self.assertEqual(1, len(self._lines()))
        self.assertIn("Home One", self._lines()[0])

    def test_an_unknown_key_is_refused_and_stores_nothing(self):
        self.assertFalse(self.handler.unlock("no_such_track"))

        self.assertIsNone(self.obj.attributes.get(constants.UNLOCKED_TRACKS_ATTR))
        self.obj.msg.assert_not_called()

    def test_the_keys_come_back_in_table_order(self):
        self.handler.unlock("other_one")
        self.handler.unlock("home_one")

        self.assertEqual(("home_one", "other_one"), self.handler.unlocked_keys())

    def test_entering_an_area_unlocks_its_area_tracks_only(self):
        new_keys = self.handler.enter_area(_HOME)

        self.assertEqual(["home_one", "home_two"], new_keys)
        self.assertFalse(self.handler.is_unlocked("home_quest"))
        self.assertFalse(self.handler.is_unlocked("other_one"))
        self.assertEqual(2, len(self._lines()))

    def test_entering_an_area_again_unlocks_nothing(self):
        self.handler.enter_area(_HOME)
        self.obj.msg.reset_mock()

        self.assertEqual([], self.handler.enter_area(_HOME))
        self.obj.msg.assert_not_called()

    def test_no_area_unlocks_nothing(self):
        for area in ("", None):
            with self.subTest(area=area):
                self.assertEqual([], self.handler.enter_area(area))

    def test_a_completed_quest_unlocks_its_quest_tracks(self):
        self.assertEqual(["home_quest"], self.handler.on_quest_complete(_QUEST))
        self.assertEqual([], self.handler.on_quest_complete("some_other_quest"))

    def test_a_key_the_table_dropped_stays_stored_and_shows_nowhere(self):
        self.handler.unlock("home_one")
        self.obj.attributes.add(constants.UNLOCKED_TRACKS_ATTR, ["home_one", "gone"])

        self.assertEqual(("home_one",), self.handler.unlocked_keys())
        self.assertTrue(self.handler.is_unlocked("gone"))

    def test_every_writer_marks_the_feed(self):
        with mock.patch("systems.interface.statefeed.events.refresh_music") as marked:
            self.handler.unlock("home_one")
            self.handler.enter_area(_OTHER)
            self.handler.on_quest_complete(_QUEST)

        self.assertEqual(3, marked.call_count)
        marked.assert_called_with(self.obj)
