"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: Tests for the player summary screen -- the panel registry, the
             fixed-width layout, the five panels, and the menu node contract.

Two regressions are guarded here above all others:

  1. An EvMenu *node* must return a (text, options) tuple. _execute_node treats
     a non-tuple return as display text, so a node returning a node NAME prints
     that string at the player instead of navigating.

  2. Layout padding must happen on PLAIN text, before colour markup is applied.
     Evennia colour tokens render as zero columns but count toward len(), so
     padding a coloured string overpads by exactly the markup length.
"""

from evennia.utils.ansi import strip_ansi
from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.progression.skills import constants as skill_constants
from systems.interface.menus import summary_menu
from systems.interface.summary import constants as const
from systems.interface.summary import layout, service
from systems.interface.summary.panel_defs.holdings import HoldingsPanel
from systems.interface.summary.panel_defs.identity import IdentityPanel
from systems.interface.summary.panel_defs.readiness import ReadinessPanel
from systems.interface.summary.panel_defs.vitals import VitalsPanel
from systems.interface.summary.panel_defs.world import WorldPanel
from systems.interface.summary.registry import PANEL_REGISTRY, _iter_panel_modules
from typeclasses.characters import Character as BlackoutCharacter


class _SummaryTest(EvenniaTest):
    """Shared fixture: a Blackout character with all its handlers live."""

    character_typeclass = BlackoutCharacter


class TestRegistry(_SummaryTest):

    def test_every_panel_module_contributes_a_panel(self):
        """Every module under panel_defs/ is discovered, whatever it is called.

        Derived from the package rather than from a list of five names. The
        census this replaced failed the day a sixth panel was added as
        intended, which trains a reader to edit the test instead of reading it
        -- CLAUDE.md's rule, and this is the assertion it asks for: the
        relationship between what is DEFINED and what is REGISTERED.
        """
        registered_modules = {
            panel.__module__ for panel in PANEL_REGISTRY.values()
        }
        defined_modules = set(_iter_panel_modules())

        self.assertEqual(defined_modules, registered_modules)

    def test_every_panel_is_well_formed(self):
        for key, panel in PANEL_REGISTRY.items():
            with self.subTest(panel=key):
                self.assertTrue(key)
                self.assertIsInstance(panel.order, int)

    def test_panels_are_ordered_by_declared_order(self):
        orders = [panel.order for panel in PANEL_REGISTRY.values()]

        self.assertEqual(sorted(orders), orders)

    def test_identity_sorts_first(self):
        first_key = next(iter(PANEL_REGISTRY))

        self.assertEqual("identity", first_key)


class TestLayout(_SummaryTest):

    def test_rules_are_exactly_summary_width(self):
        light = strip_ansi(layout.rule())
        heavy = strip_ansi(layout.rule(heavy=True))

        self.assertEqual(const.SUMMARY_WIDTH, len(light))
        self.assertEqual(const.SUMMARY_WIDTH, len(heavy))

    def test_split_line_pads_to_summary_width(self):
        line = strip_ansi(layout.split_line("LEFT", "RIGHT"))

        self.assertEqual(const.SUMMARY_WIDTH, len(line))

    def test_field_values_align_across_rows(self):
        """The padding-before-colour rule: two rows with different-length
        labels must put their values in the same column."""
        rows = layout.fields([("A", "1"), ("Bbbbbbb", "2")])
        plain = strip_ansi(rows[0])

        first_value_col = plain.index("1")
        second_value_col = plain.index("2")
        stride = second_value_col - first_value_col
        expected = const.FIELD_LABEL_WIDTH + const.FIELD_VALUE_WIDTH + len(const.FIELD_GUTTER)

        self.assertEqual(expected, stride)

    def test_fields_chunks_into_rows(self):
        rows = layout.fields([("a", "1"), ("b", "2"), ("c", "3")])

        self.assertEqual(2, len(rows))

    def test_fields_of_nothing_renders_nothing(self):
        self.assertEqual([], layout.fields([]))

    def test_wrapped_field_never_exceeds_width(self):
        items = [f"Skill{index} 100" for index in range(12)]
        lines = layout.wrapped_field("Combat", items)

        self.assertGreater(len(lines), 1)
        for line in lines:
            self.assertLessEqual(len(strip_ansi(line)), const.SUMMARY_WIDTH)

    def test_wrapped_field_labels_only_the_first_row(self):
        items = [f"Skill{index} 100" for index in range(12)]
        lines = layout.wrapped_field("Combat", items)

        self.assertIn("Combat", strip_ansi(lines[0]))
        self.assertNotIn("Combat", strip_ansi(lines[1]))

    def test_wrapped_field_of_nothing_renders_nothing(self):
        self.assertEqual([], layout.wrapped_field("Combat", []))


class TestPanels(_SummaryTest):

    def test_identity_shows_name_and_default_mode(self):
        line = strip_ansi(IdentityPanel.render(self.char1)[0])

        self.assertIn(self.char1.key, line)
        self.assertIn(const.CHARACTER_MODE_DEFAULT.upper(), line)

    def test_identity_shows_hardcore_marker_when_flagged(self):
        self.char1.attributes.add(const.HARDCORE_ATTR, True)
        line = strip_ansi(IdentityPanel.render(self.char1)[0])

        self.assertIn(const.HARDCORE_LABEL, line)

    def test_vitals_shows_combat_level_and_hp(self):
        text = strip_ansi("\n".join(VitalsPanel.render(self.char1)))

        self.assertIn("Combat Level", text)
        self.assertIn("Hitpoints", text)
        self.assertIn(str(self.char1.max_hp), text)

    def test_vitals_data_matches_the_live_character(self):
        payload = VitalsPanel.data(self.char1)

        self.assertEqual(self.char1.hp, payload["hp"])
        self.assertEqual(self.char1.combat_level, payload["combat_level"])

    def test_readiness_reports_unarmed_when_nothing_wielded(self):
        text = strip_ansi("\n".join(ReadinessPanel.render(self.char1)))

        self.assertIn("bare hands", text)

    def test_holdings_reports_the_inventory_cap(self):
        from items.equipment.constants import MAX_INVENTORY_SLOTS

        text = strip_ansi("\n".join(HoldingsPanel.render(self.char1)))

        self.assertIn(str(MAX_INVENTORY_SLOTS), text)

    def test_world_reports_quest_counts(self):
        text = strip_ansi("\n".join(WorldPanel.render(self.char1)))

        self.assertIn("Quests", text)
        self.assertIn("Completed", text)

    def test_world_formats_durations_in_two_units(self):
        one_day_four_hours = ((24 + 4) * 60) * 60

        self.assertEqual("1d 04h", WorldPanel._format_duration(one_day_four_hours))
        self.assertEqual("2h 05m", WorldPanel._format_duration(2 * 3600 + 5 * 60))
        self.assertEqual("7m", WorldPanel._format_duration(7 * 60))

    def test_every_panel_data_is_json_safe(self):
        import json

        payload = service.summary_data(self.char1)
        encoded = json.dumps(payload)

        self.assertIn("vitals", encoded)


class TestService(_SummaryTest):

    def test_screen_is_bracketed_by_heavy_rules(self):
        lines = service.render_summary(self.char1).split("\n")
        heavy = strip_ansi(layout.rule(heavy=True))

        self.assertEqual(heavy, strip_ansi(lines[0]))
        self.assertEqual(heavy, strip_ansi(lines[-1]))

    def test_no_line_exceeds_the_screen_width(self):
        for line in service.render_summary(self.char1).split("\n"):
            self.assertLessEqual(len(strip_ansi(line)), const.SUMMARY_WIDTH)

    def test_a_failing_panel_does_not_take_the_screen_with_it(self):
        def _boom(_character):
            raise RuntimeError("panel exploded")

        original = ReadinessPanel.render
        ReadinessPanel.render = staticmethod(_boom)
        try:
            screen = strip_ansi(service.render_summary(self.char1))
        finally:
            ReadinessPanel.render = original

        self.assertIn(const.PANEL_ERROR_TEXT, screen)
        self.assertIn("Combat Level", screen)

    def test_headings_appear_for_titled_panels_only(self):
        screen = strip_ansi(service.render_summary(self.char1))

        self.assertIn(VitalsPanel.title.upper(), screen)
        self.assertIn("DOSSIER", screen)


class TestPlaytime(_SummaryTest):

    def test_playtime_starts_at_zero(self):
        self.assertEqual(0, self.char1.playtime_seconds)

    def test_banking_a_session_accumulates_and_clears_the_stamp(self):
        import time

        from typeclasses.characters import (
            PLAYTIME_SESSION_START_ATTR,
            PLAYTIME_TOTAL_ATTR,
        )

        self.char1.attributes.add(PLAYTIME_SESSION_START_ATTR, time.time() - 120)
        self.char1._bank_playtime()

        banked = self.char1.attributes.get(PLAYTIME_TOTAL_ATTR)
        stamp = self.char1.attributes.get(PLAYTIME_SESSION_START_ATTR, default=None)

        self.assertGreaterEqual(banked, 120)
        self.assertIsNone(stamp)

    def test_banking_twice_does_not_double_count(self):
        import time

        from typeclasses.characters import (
            PLAYTIME_SESSION_START_ATTR,
            PLAYTIME_TOTAL_ATTR,
        )

        self.char1.attributes.add(PLAYTIME_SESSION_START_ATTR, time.time() - 120)
        self.char1._bank_playtime()
        first = self.char1.attributes.get(PLAYTIME_TOTAL_ATTR)

        self.char1._bank_playtime()
        second = self.char1.attributes.get(PLAYTIME_TOTAL_ATTR)

        self.assertEqual(first, second)


class TestMenuNodes(_SummaryTest):

    def test_start_returns_a_text_options_tuple(self):
        result = summary_menu.start(self.char1)

        self.assertIsInstance(result, tuple)
        self.assertEqual(2, len(result))

    def test_start_offers_every_drill_down_plus_refresh_and_close(self):
        _text, options = summary_menu.start(self.char1)
        expected = len(summary_menu.DRILL_DOWNS) + 1

        self.assertEqual(expected, len(options))

    def test_launch_queues_the_command_and_closes(self):
        text, options = summary_menu.node_launch(self.char1, command="skills")

        self.assertIsNone(options)
        self.assertEqual("", text)
        self.assertEqual(
            "skills", getattr(self.char1.ndb, summary_menu.FOLLOWUP_ATTR)
        )

    def test_quit_closes_without_queueing_anything(self):
        summary_menu.start_summary_menu(self.char1)
        self.char1.execute_cmd("quit")

        self.assertIsNone(getattr(self.char1.ndb, summary_menu.FOLLOWUP_ATTR, None))

    def test_closing_text_is_silent_when_a_drilldown_is_queued(self):
        setattr(self.char1.ndb, summary_menu.FOLLOWUP_ATTR, "skills")

        self.assertEqual("", summary_menu._closing_text(self.char1, None))

    def test_closing_text_speaks_when_nothing_is_queued(self):
        setattr(self.char1.ndb, summary_menu.FOLLOWUP_ATTR, None)

        self.assertEqual(
            summary_menu.CLOSE_TEXT, summary_menu._closing_text(self.char1, None)
        )


class TestDossierContent(_SummaryTest):
    """What the one dossier carries. `score` and `profile <name>` both show
    it, so there is no second view to guard."""

    def test_the_dossier_carries_no_skill_roster(self):
        """Skills left the dossier on 08/28/2026 for a screen of their own.

        Asserted on the BAND rather than on skill names, and the difference is
        the whole subtlety here. A skill name may legitimately appear on this
        screen -- readiness prints "Earns XP: Strike, Fortitude", which is a
        fact about the weapon in your hands and not a roster entry. What must
        not come back is the band: a section listing every skill and its level.

        The registry itself too, because the panel is what would return. The
        aggregates stay -- combat level, total level and total XP are the
        vitals panel's -- and the per-skill breakdown is what `skills` and
        CHANNEL_CHAR_SKILLS own.
        """
        screen = strip_ansi(service.render_summary(self.char1))

        self.assertNotIn("skills", PANEL_REGISTRY)
        self.assertNotIn("SKILLS", screen)
        self.assertNotIn("Closest", screen)

    def test_every_panel_renders_through_one_path(self):
        """No panel keeps a second, narrower renderer. A `render_public` left
        on one panel would be dead code that claims a privacy rule the game
        no longer has."""
        for key, panel in PANEL_REGISTRY.items():
            with self.subTest(panel=key):
                self.assertFalse(hasattr(panel, "render_public"))
                self.assertFalse(hasattr(panel, "public"))

    def test_vitals_status_names_the_pvp_flag_only_when_it_is_on(self):
        from systems.gameplay.combat import pvp
        from systems.interface.summary.panel_defs import vitals

        before = strip_ansi(service.render_summary(self.char1))
        pvp.set_pvp(self.char1, True)
        after = strip_ansi(service.render_summary(self.char1))

        self.assertNotIn(vitals.STATUS_PVP_ON, before)
        self.assertIn(vitals.STATUS_PVP_ON, after)
        self.assertTrue(VitalsPanel.data(self.char1)["pvp"])


class TestProfileCommand(_SummaryTest):
    """`profile` opens the profile menu. Its pages are tested in
    systems/interface/menus/tests/test_profile_menu.py."""

    def _run(self, line: str) -> str:
        """Everything char1 was told. EvMenu sends a node as `text=`, so the
        keyword arguments are captured too."""
        self._captured = []
        self.char1.msg = lambda *args, **kwargs: self._captured.append(
            (args, kwargs))
        self.char1.execute_cmd(line)

        return " ".join(str(entry) for entry in self._captured)

    def test_profile_with_no_argument_shows_your_own(self):
        joined = self._run("profile")

        self.assertIn("DOSSIER", joined)
        self.assertIn(self.char1.key, joined)

    def test_profile_of_another_player_shows_their_full_dossier(self):
        """The whole dossier is public: hitpoints, holdings and location."""
        joined = strip_ansi(self._run(f"profile {self.char2.key}"))

        self.assertIn(self.char2.key, joined)
        self.assertIn("HOLDINGS", joined)
        self.assertIn("Hitpoints", joined)
        self.assertIn("Location", joined)

    def test_profile_refuses_a_non_character(self):
        from commands import progression_cmds

        joined = self._run(f"profile {self.obj1.key}")

        self.assertIn(progression_cmds._NOT_A_CHARACTER_MSG, joined)


class TestSummaryFeed(_SummaryTest):

    def test_channel_is_subscribable(self):
        from systems.interface.statefeed import constants as feed_const

        self.assertIn(
            feed_const.CHANNEL_CHAR_SUMMARY, feed_const.SUBSCRIBABLE_CHANNELS
        )

    def test_channel_is_not_rate_capped(self):
        from systems.interface.statefeed import constants as feed_const

        self.assertNotIn(
            feed_const.CHANNEL_CHAR_SUMMARY, feed_const.CHANNEL_MIN_INTERVAL_SECONDS
        )

    def test_payload_carries_every_panel(self):
        from systems.interface.statefeed.payloads import CharSummaryPayload

        payload = CharSummaryPayload(panels=service.summary_data(self.char1))
        body = payload.to_dict()

        self.assertEqual(set(PANEL_REGISTRY.keys()), set(body["panels"].keys()))

    def test_emit_is_a_no_op_without_a_subscriber(self):
        from systems.interface.statefeed import events as feed

        self.assertEqual(0, feed.emit_summary(self.char1))

    def test_emit_reaches_a_subscribed_session(self):
        from systems.interface.statefeed import constants as feed_const
        from systems.interface.statefeed import events as feed
        from systems.interface.statefeed import subscriptions

        for session in self.char1.sessions.all():
            subscriptions.subscribe(session, feed_const.CHANNEL_CHAR_SUMMARY)

        sent = feed.emit_summary(self.char1)

        self.assertGreater(sent, 0)


class TestSkillRollups(_SummaryTest):

    def test_total_level_sums_every_skill(self):
        from systems.gameplay.progression.skills.registry import SKILL_REGISTRY

        expected = sum(
            self.char1.skills.get_level(key) for key in SKILL_REGISTRY
        )

        self.assertEqual(expected, self.char1.skills.total_level())

    def test_closest_to_level_up_tracks_awarded_xp(self):
        before = self.char1.skills.closest_to_level_up()
        self.char1.skills.add_xp(skill_constants.SKILL_KEY_CUTTING, 1)
        after = self.char1.skills.closest_to_level_up()

        self.assertIsNotNone(before)
        self.assertEqual(skill_constants.SKILL_KEY_CUTTING, after["skill_key"])

    def test_combined_xp_rises_when_xp_is_awarded(self):
        before = self.char1.skills.combined_xp()
        self.char1.skills.add_xp(skill_constants.SKILL_KEY_CUTTING, 50)
        after = self.char1.skills.combined_xp()

        self.assertEqual(before + 50, after)
