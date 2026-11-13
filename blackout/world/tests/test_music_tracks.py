"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/08/2026
Description: Guard the music track table (`world/tables/music_tracks.json`)
             and its reader, `world/music_tracks.py`.

             Run from blackout/:
                 ../evenv/Scripts/evennia.exe test --settings test_settings.py world.tests.test_music_tracks

             The table in git must name real areas and real quests. The
             reader refuses each kind of bad row. No test names a track or
             an area by its literal key: each expectation comes from the
             tables themselves.
"""

import unittest
from dataclasses import replace

from systems.gameplay.quests.loader import GLOBAL_QUEST_REGISTRY
from world import areas, music_tracks, table_file


def _a_track(**changes) -> music_tracks.Track:
    """Give one good area track, with the given fields changed."""
    track = music_tracks.Track(
        key="a_track", name="A Track", area=areas.DEFAULT_AREA,
        unlock=music_tracks.UNLOCK_AREA, unlock_key="", hint="", note="A note.")

    return replace(track, **changes)


class TableTests(unittest.TestCase):
    """The rows in git agree with the area table and the quest registry."""

    def test_each_track_names_an_area_of_the_area_table(self):
        for key, track in music_tracks.TRACKS.items():
            with self.subTest(track=key):
                self.assertIn(track.area, areas.AREAS)

    def test_each_track_has_an_unlock_of_the_vocabulary(self):
        for key, track in music_tracks.TRACKS.items():
            with self.subTest(track=key):
                self.assertIn(track.unlock, music_tracks.UNLOCKS)

    def test_each_quest_unlock_names_a_quest(self):
        quests = GLOBAL_QUEST_REGISTRY.keys()

        for key, track in music_tracks.TRACKS.items():
            if track.unlock != music_tracks.UNLOCK_QUEST:
                continue

            with self.subTest(track=key):
                self.assertIn(track.unlock_key, quests)

    def test_each_track_has_a_name_and_a_note(self):
        for key, track in music_tracks.TRACKS.items():
            with self.subTest(track=key):
                self.assertTrue(track.name.strip())
                self.assertTrue(track.note.strip())

    def test_the_tracks_of_an_area_are_its_rows_in_order(self):
        for area in areas.AREAS:
            expected = [track for track in music_tracks.TRACKS.values()
                        if track.area == area]

            with self.subTest(area=area):
                self.assertEqual(list(music_tracks.tracks_of_area(area)),
                                 expected)

    def test_the_served_file_comes_from_the_key(self):
        for key in music_tracks.TRACKS:
            with self.subTest(track=key):
                self.assertEqual(
                    music_tracks.served_relative(key),
                    "%s/%s%s" % (music_tracks.SERVED_DIRECTORY, key,
                                 music_tracks.SERVED_SUFFIX))


class RefusalTests(unittest.TestCase):
    """The reader refuses each kind of bad row, and takes a good one."""

    def test_a_good_row_passes(self):
        self.assertEqual(music_tracks.row_problem(_a_track(), areas.AREAS), "")

    def test_an_unknown_area_is_refused(self):
        problem = music_tracks.row_problem(_a_track(area="no_such_area"),
                                           areas.AREAS)

        self.assertIn("no_such_area", problem)

    def test_an_unknown_unlock_is_refused(self):
        problem = music_tracks.row_problem(_a_track(unlock="boss"),
                                           areas.AREAS)

        self.assertIn("boss", problem)

    def test_a_quest_unlock_needs_a_quest_key(self):
        problem = music_tracks.row_problem(
            _a_track(unlock=music_tracks.UNLOCK_QUEST), areas.AREAS)

        self.assertIn("quest key", problem)

    def test_an_area_unlock_takes_no_unlock_key(self):
        problem = music_tracks.row_problem(_a_track(unlock_key="a_quest"),
                                           areas.AREAS)

        self.assertIn("stay empty", problem)

    def test_a_track_with_no_name_is_refused(self):
        problem = music_tracks.row_problem(_a_track(name=""), areas.AREAS)

        self.assertIn("no name", problem)

    def test_check_rows_raises_for_the_first_bad_row(self):
        rows = (_a_track(), _a_track(key="b_track", area="no_such_area"))

        with self.assertRaises(table_file.TableFileError) as caught:
            music_tracks.check_rows(rows, areas.AREAS)

        self.assertIn("b_track", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
