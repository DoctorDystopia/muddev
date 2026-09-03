"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/28/2026
Description: Cases for the char_skills channel and the per-skill sheet behind
             it.

             THE POINT OF THE SPLIT is that one description of a skill feeds
             three readers -- the EvMenu node, the `skills <skill>` sheet, and
             this channel -- so the cases that matter most here are the ones
             asserting a RELATIONSHIP between two of those outputs rather than
             a literal. `test_the_sheet_and_the_payload_describe_the_same_skill`
             is the load-bearing one: it is what would fail if someone rebuilt
             the text sheet from its own handler reads.

             NOTHING HERE ASSERTS A CENSUS of the skill roster. Every case
             derives its expectation from SKILL_REGISTRY, so adding a skill
             tomorrow is covered rather than breaking a literal list -- which
             is the rule CLAUDE.md states for exactly this kind of test.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.statefeed.tests.test_skill_feed
"""

import json

from evennia.utils.ansi import strip_ansi
from evennia.utils.test_resources import EvenniaTest, EvenniaTestCase

from systems.progression.skills import detail as skill_detail
from systems.progression.skills.registry import SKILL_REGISTRY
from systems.statefeed import constants as feed_const
from systems.statefeed import events as feed
from systems.statefeed import skills as skill_feed
from systems.statefeed import subscriptions
from typeclasses.characters import Character as BlackoutCharacter


class _SkillFeedTest(EvenniaTest):
    """Shared fixture: a Blackout character with its skills handler live."""

    character_typeclass = BlackoutCharacter

    def _payload(self) -> dict:
        body = skill_feed.build_payload(self.char1).to_dict()

        return body

    def _row(self, skill_key: str) -> dict:
        for row in self._payload()["skills"]:
            if row["key"] == skill_key:
                return row

        self.fail("no row for %s" % skill_key)


class TestChannel(_SkillFeedTest):
    """The channel's declaration, which decides whether it can be reached at
    all."""

    def test_a_client_may_subscribe_to_it(self):
        self.assertIn(
            feed_const.CHANNEL_CHAR_SKILLS, feed_const.SUBSCRIBABLE_CHANNELS)

    def test_channel_is_not_rate_capped(self):
        # It fires on a level change, on the `skills` command and on resync --
        # never on an XP award -- so its rate is bounded by the player.
        self.assertNotIn(
            feed_const.CHANNEL_CHAR_SKILLS,
            feed_const.CHANNEL_MIN_INTERVAL_SECONDS)

    def test_channel_may_be_coalesced(self):
        # A whole-roster snapshot: the newest carries everything the one
        # before it did.
        self.assertIn(
            feed_const.CHANNEL_CHAR_SKILLS, feed_const.COALESCABLE_CHANNELS)

    def test_emit_is_a_no_op_without_a_subscriber(self):
        self.assertEqual(0, feed.emit_skills(self.char1))

    def test_emit_reaches_a_subscribed_session(self):
        for session in self.char1.sessions.all():
            subscriptions.subscribe(session, feed_const.CHANNEL_CHAR_SKILLS)

        self.assertGreater(feed.emit_skills(self.char1), 0)

    def test_an_observer_with_no_skills_handler_is_a_no_op(self):
        payload = skill_feed.build_payload(self.obj1).to_dict()

        self.assertEqual([], payload["skills"])


class TestRoster(_SkillFeedTest):
    """The shape of the snapshot."""

    def test_every_registered_skill_ships(self):
        keys = [row["key"] for row in self._payload()["skills"]]

        self.assertEqual(sorted(SKILL_REGISTRY), sorted(keys))

    def test_rows_are_ordered_by_category_then_name(self):
        # Sorted on the SERVER so a grid and the text screens agree without
        # either of them saying so.
        rows = self._payload()["skills"]
        ordered = sorted(rows, key=lambda row: (row["category"], row["name"]))

        self.assertEqual([row["key"] for row in ordered],
                         [row["key"] for row in rows])

    def test_categories_cover_every_row_and_repeat_none(self):
        payload = self._payload()
        categories = payload["categories"]

        self.assertEqual(len(categories), len(set(categories)))
        self.assertEqual(
            sorted(set(row["category"] for row in payload["skills"])),
            sorted(categories))

    def test_totals_come_from_the_handler(self):
        payload = self._payload()

        self.assertEqual(self.char1.skills.total_level(), payload["total_level"])
        self.assertEqual(self.char1.skills.combined_xp(), payload["total_xp"])

    def test_every_level_matches_the_handler(self):
        for row in self._payload()["skills"]:
            with self.subTest(skill=row["key"]):
                self.assertEqual(
                    self.char1.skills.get_level(row["key"]), row["level"])

    def test_progress_and_cumulative_xp_are_separate_fields(self):
        # Deriving one from the other is what once rendered "1154 / 152".
        self.char1.skills.add_xp("cutting", 40)
        row = self._row("cutting")
        current, needed, remaining = self.char1.skills.get_xp_level("cutting")

        self.assertEqual(current, row["current_xp"])
        self.assertEqual(needed, row["needed_xp"])
        self.assertEqual(remaining, row["remaining_xp"])
        self.assertEqual(
            self.char1.skills.get_total_xp("cutting"), row["total_xp"])
        self.assertEqual(row["total_xp"] + remaining, row["next_level_at"])

    def test_closest_is_an_empty_dict_rather_than_null(self):
        # A JSON null and an absent key are two more things a client would have
        # to branch on to say "every skill is capped".
        payload = self._payload()

        self.assertIsInstance(payload["closest"], dict)

    def test_closest_names_a_registered_skill_while_one_is_uncapped(self):
        closest = self._payload()["closest"]

        if not closest:
            self.skipTest("every skill is at the cap on this fixture")

        self.assertIn(closest["skill_key"], SKILL_REGISTRY)

    def test_the_whole_payload_survives_json(self):
        # Every value on the wire must survive json.dumps -- see payloads.py.
        json.dumps(self._payload())


class TestPerSkillDetail(_SkillFeedTest):
    """One skill, described once and read three ways."""

    def test_the_command_is_one_a_telnet_player_could_type(self):
        from commands.progression_cmds import CmdSkills

        for row in self._payload()["skills"]:
            with self.subTest(skill=row["key"]):
                self.assertEqual(
                    "%s %s" % (CmdSkills.key, row["key"]), row["command"])

    def test_an_empty_unlock_section_is_dropped(self):
        # A client draws headings from what it is sent; a heading with nothing
        # under it is a client-side branch the server can simply not create.
        for row in self._payload()["skills"]:
            for section in row["unlocks"]:
                with self.subTest(skill=row["key"], section=section["title"]):
                    self.assertTrue(section["rows"])

    def test_every_section_title_is_one_the_renderer_owns(self):
        known = {
            skill_detail.SECTION_RECIPES,
            skill_detail.SECTION_GATHERABLES,
            skill_detail.SECTION_EQUIPMENT,
            skill_detail.SECTION_ABILITIES,
        }

        for row in self._payload()["skills"]:
            for section in row["unlocks"]:
                with self.subTest(skill=row["key"]):
                    self.assertIn(section["title"], known)

    def test_the_sheet_and_the_payload_describe_the_same_skill(self):
        """The reason detail.py exists.

        The text sheet is rendered FROM the structured form rather than from a
        second set of handler reads, so every unlock the payload lists is on
        the sheet and the level agrees. This is what would fail if someone
        rebuilt the sheet inline again.
        """
        for skill_key in SKILL_REGISTRY:
            row = skill_detail.skill_detail(self.char1, skill_key)
            sheet = strip_ansi(skill_detail.render_detail(self.char1, skill_key))

            with self.subTest(skill=skill_key):
                self.assertIn(row["name"], sheet)
                self.assertIn(str(row["level"]), sheet)
                self.assertIn(str(row["total_xp"]), sheet)

                for section in row["unlocks"]:
                    self.assertIn(section["title"], sheet)

                    for entry in section["rows"]:
                        self.assertIn(entry["name"], sheet)

    def test_an_unknown_skill_yields_nothing_rather_than_raising(self):
        self.assertEqual({}, skill_detail.skill_detail(self.char1, "no_such"))
        self.assertEqual("", skill_detail.render_detail(self.char1, "no_such"))


class TestResolveSkillKey(EvenniaTestCase):
    """What a player may type and have it understood as a skill."""

    character_typeclass = BlackoutCharacter

    def test_an_exact_key_resolves(self):
        for skill_key in SKILL_REGISTRY:
            with self.subTest(skill=skill_key):
                self.assertEqual(
                    skill_key, skill_detail.resolve_skill_key(skill_key))

    def test_a_display_name_resolves_whatever_its_case(self):
        for skill_key, skill_class in SKILL_REGISTRY.items():
            with self.subTest(skill=skill_key):
                self.assertEqual(
                    skill_key,
                    skill_detail.resolve_skill_key(str(skill_class.name).upper()))

    def test_a_unique_prefix_resolves(self):
        # The display name is what the player just read off a screen.
        self.assertEqual("cutting", skill_detail.resolve_skill_key("cut"))

    def test_an_ambiguous_prefix_resolves_to_nothing(self):
        # Two skills starting the same way is a question only the player can
        # answer, and picking one would show the wrong sheet silently.
        shared = self._an_ambiguous_prefix()

        if shared is None:
            self.skipTest("no two skills share a prefix on this roster")

        self.assertEqual("", skill_detail.resolve_skill_key(shared))

    def test_nothing_and_nonsense_resolve_to_nothing(self):
        self.assertEqual("", skill_detail.resolve_skill_key(""))
        self.assertEqual("", skill_detail.resolve_skill_key("   "))
        self.assertEqual("", skill_detail.resolve_skill_key("Bob"))

    def _an_ambiguous_prefix(self):
        """The shortest prefix two registered skills share, or None."""
        names = sorted(str(cls.name).lower() for cls in SKILL_REGISTRY.values())

        for first, second in zip(names, names[1:]):
            if first[0] == second[0]:
                return first[0]

        return None
