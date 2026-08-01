"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/30/2026
Description: Evennia-backed tests for the combat handler and the global tick
             engine — the layer the pure-math suite in test_combat_calc.py
             cannot reach.

Run with the Evennia/Django test runner from the game dir:

    evennia test --settings settings.py systems.combat

These are deliberately regression-shaped: every case below corresponds to a
concrete defect found in the 07/30 combat audit.
"""

from unittest import mock

from evennia.scripts.models import ScriptDB
from evennia.utils.ansi import strip_ansi
from evennia.utils.test_resources import EvenniaTest

from systems.combat import constants as const
from systems.combat.combat import (
    COMBAT_HANDLER_KEY,
    HANDLER_NO_TIMER_INTERVAL,
    ensure_combat_handler,
    get_defense_bonuses,
    get_handler_for,
)
from systems.combat.tick_engine import (
    TICK_ENGINE_KEY,
    bootstrap_combat,
    get_tick_engine,
    purge_stale_combat_handlers,
)
from typeclasses.npc_combat import spawn_mutant_raider


class TestCombatHandlerWiring(EvenniaTest):
    """The handler must carry no Evennia timer, but still read as live."""

    def test_handler_has_no_evennia_interval(self):
        """Regression: interval was 0.6, truncated to 0 by the IntegerField,
        which made ScriptBase._start_task refuse to start a task at all."""
        handler = ensure_combat_handler(self.char1)

        self.assertEqual(handler.interval, HANDLER_NO_TIMER_INTERVAL)
        self.assertFalse(
            ScriptDB.objects.filter(db_key=COMBAT_HANDLER_KEY, db_interval__gt=0).exists(),
            "no combat handler may own an Evennia timer interval",
        )

    def test_handler_reads_as_active(self):
        """get_handler_for and CombatEntity.combat both key off is_active, and
        Evennia will not set it for a zero-interval script — we must."""
        handler = ensure_combat_handler(self.char1)

        self.assertTrue(handler.is_active)
        self.assertIs(get_handler_for(self.char1), handler)
        self.assertIsNotNone(self.char1.combat)

    def test_stale_handler_is_replaced_not_revived(self):
        """Regression: a handler persisted with a broken interval used to be
        revived forever, so combat could never recover."""
        handler = ensure_combat_handler(self.char1)
        old_id = handler.id

        # Simulate a pre-tick-engine handler left in the DB.
        handler.db_interval = 0
        handler.save(update_fields=["db_interval"])

        replacement = ensure_combat_handler(self.char1)

        self.assertNotEqual(replacement.id, old_id)
        self.assertEqual(replacement.interval, HANDLER_NO_TIMER_INTERVAL)
        self.assertFalse(ScriptDB.objects.filter(id=old_id).exists())


class TestTickEngine(EvenniaTest):
    """The global 0.6s LoopingCall owner."""

    def test_engine_is_a_singleton(self):
        first = get_tick_engine()
        second = get_tick_engine()

        self.assertEqual(first.id, second.id)
        self.assertEqual(ScriptDB.objects.filter(db_key=TICK_ENGINE_KEY).count(), 1)

    def test_engine_watchdog_interval_is_a_whole_number(self):
        """The watchdog rides on Evennia's IntegerField, so it must be an int."""
        engine = get_tick_engine()

        self.assertIsInstance(const.TICK_ENGINE_WATCHDOG_SECONDS, int)
        self.assertEqual(engine.interval, const.TICK_ENGINE_WATCHDOG_SECONDS)
        self.assertGreater(engine.interval, 0)

    def test_registered_handler_is_ticked(self):
        engine = get_tick_engine()
        handler = ensure_combat_handler(self.char1)

        with mock.patch.object(type(handler), "tick") as mocked:
            engine._tick()

        mocked.assert_called_once()

    def test_one_broken_handler_does_not_stop_the_loop(self):
        """A raising combatant must be dropped, not allowed to kill the tick."""
        engine = get_tick_engine()
        handler = ensure_combat_handler(self.char1)

        with mock.patch.object(type(handler), "tick", side_effect=RuntimeError("boom")):
            engine._tick()  # must not raise

        self.assertNotIn(handler.id, engine._registry())

    def test_bootstrap_purges_then_starts_the_engine(self):
        """Server start must both clear leftovers and stand the engine up,
        without depending on a player attacking something first."""
        handler = ensure_combat_handler(self.char1)
        handler_id = handler.id

        engine = bootstrap_combat()

        self.assertFalse(ScriptDB.objects.filter(id=handler_id).exists())
        self.assertEqual(engine.key, TICK_ENGINE_KEY)
        self.assertTrue(engine.is_active)

    def test_purge_clears_stale_handlers(self):
        handler = ensure_combat_handler(self.char1)
        self.char1.db.in_combat = True

        purged = purge_stale_combat_handlers()

        self.assertEqual(purged, 1)
        self.assertFalse(ScriptDB.objects.filter(id=handler.id).exists())
        self.assertFalse(self.char1.db.in_combat)


class TestSwingCadence(EvenniaTest):
    """attack_speed must mean 'ticks between swings', exactly."""

    def _swings_over(self, attack_speed, ticks):
        handler = ensure_combat_handler(self.char1)
        target = spawn_mutant_raider(self.room1)
        ensure_combat_handler(target)

        handler.queue_action({"kind": "attack", "target": target})

        weapon_data = dict(handler.ndb.active_weapon_data)
        weapon_data["attack_speed"] = attack_speed
        handler.ndb.active_weapon_data = weapon_data

        # Never miss, never kill — we are counting cadence, not resolving combat.
        swing_result = {"hit": True, "damage": 0, "hit_prob": 1.0}
        with mock.patch(
            "systems.combat.combat.combat_calc.resolve_melee_swing",
            return_value=swing_result,
        ) as mocked:
            for _ in range(ticks):
                handler.tick()

        return mocked.call_count

    def test_speed_four_swings_every_four_ticks(self):
        """Regression: cooldown_ticks = attack_speed gave a speed+1 cadence
        (3.0s instead of 2.4s for a speed-4 weapon)."""
        self.assertEqual(self._swings_over(attack_speed=4, ticks=12), 3)

    def test_speed_five_swings_every_five_ticks(self):
        self.assertEqual(self._swings_over(attack_speed=5, ticks=15), 3)


class TestHandlerLifecycle(EvenniaTest):

    def test_end_combat_deletes_script_and_clears_state(self):
        handler = ensure_combat_handler(self.char1)
        handler.start_combat_state()
        handler_id = handler.id

        handler.end_combat()

        self.assertFalse(ScriptDB.objects.filter(id=handler_id).exists())
        self.assertFalse(self.char1.db.in_combat)

    def test_end_combat_clears_the_lazy_property_cache(self):
        """Regression: `del obj.ndb.combat` was a swallowed no-op, because
        lazy_property caches in __dict__ and refuses deletion — so
        `caller.combat` kept handing back the deleted script."""
        handler = ensure_combat_handler(self.char1)
        self.assertIsNotNone(self.char1.combat)  # populate the cache

        handler.end_combat()

        self.assertIsNone(self.char1.combat)

    def test_flee_ends_combat_without_touching_a_deleted_script(self):
        """Regression: ActionFlee.resolve returned False after end_combat, so
        tick() carried on reading self.db on a deleted row."""
        handler = ensure_combat_handler(self.char1)
        target = spawn_mutant_raider(self.room1)
        ensure_combat_handler(target)
        handler.queue_action({"kind": "attack", "target": target})
        handler.queue_action({"kind": "flee"})

        handler.tick()  # must not raise

        self.assertFalse(self.char1.db.in_combat)


class TestNpcSeeding(EvenniaTest):
    """The spawner's stat block must actually reach the combat handler."""

    def test_spawned_raider_has_its_spawner_stats(self):
        """Regression: at_object_creation read db.combat_stats before the
        spawner had written it, so every NPC got empty styles and speed 4.

        Values now reflect the OSRS Goblin Level 2 source (Monster ID 3028),
        https://oldschool.runescape.wiki/w/Goblin#Level_2 — the Mutant Raider
        is a faithful goblin-calibration target, not a face-tuned placeholder.
        """
        npc = spawn_mutant_raider(self.room1)

        self.assertEqual(npc.db.attack_speed, 4)            # goblin: 4 ticks (2.4s)
        # The raider declares its own crush/aggressive style in its NpcDef, so
        # it no longer falls back to the unarmed "punch" default.
        self.assertEqual(npc.db.default_combat_style, "headbutt")
        self.assertTrue(npc.db.combat_styles)
        self.assertTrue(npc.db.combat_stat_bonuses)

    def test_spawned_raider_resolves_a_usable_attack_style(self):
        npc = spawn_mutant_raider(self.room1)
        handler = ensure_combat_handler(npc)

        # _refresh_weapon stamps the resolved style as 'active_combat_style'
        # (key shared by _unarmed_weapon_data and the wielded-weapon branch).
        style = handler.ndb.active_weapon_data["active_combat_style"]

        self.assertTrue(style, "NPC resolved to an empty style dict")
        # Goblin attack style per the wiki is Crush.
        self.assertEqual(style["attack_type"], "crush")
        self.assertEqual(handler.ndb.active_weapon_data["attack_speed"], 4)

    def test_raider_skill_levels_reach_the_shim(self):
        # OSRS Goblin L2: Attack 1, Strength 1, Defence 1, Hitpoints 5.
        npc = spawn_mutant_raider(self.room1)

        self.assertEqual(npc.skills.get_level("defense"), 1)
        self.assertEqual(npc.skills.get_level("strike"), 1)

    def test_raider_combat_bonuses_match_goblin_l2(self):
        """OSRS Goblin L2 monster bonuses: attack -21, strength -15,
        all three melee defences -15. Negative bonuses feed the combat math
        identically to positive ones (they only offset the +64 zero-floor)
        so the test asserts exact wiki values."""
        npc = spawn_mutant_raider(self.room1)

        b = npc.db.combat_stat_bonuses
        self.assertEqual(b["stab_attack_bonus"], -21)
        self.assertEqual(b["slash_attack_bonus"], -21)
        self.assertEqual(b["crush_attack_bonus"], -21)
        self.assertEqual(b["melee_strength_bonus"], -15)
        self.assertEqual(b["stab_defense_bonus"], -15)
        self.assertEqual(b["slash_defense_bonus"], -15)
        self.assertEqual(b["crush_defense_bonus"], -15)

    def test_stance_boost_matches_declared_weapon_style(self):
        """Regression: accurate/aggressive boosts were swapped in the spawner."""
        npc = spawn_mutant_raider(self.room1)

        for style in npc.db.combat_styles.values():
            boost = style["weapon_style_level_boost"]
            if style["weapon_style"] == "accurate":
                self.assertEqual(boost, const.MELEE_WEAPON_STYLE_LEVEL_BOOST_ACCURATE)
            elif style["weapon_style"] == "aggressive":
                self.assertEqual(boost, const.MELEE_WEAPON_STYLE_LEVEL_BOOST_AGGRESSIVE)
            elif style["weapon_style"] == "defensive":
                self.assertEqual(boost, const.MELEE_WEAPON_STYLE_LEVEL_BOOST_DEFENSIVE)


class TestNpcDefRegistry(EvenniaTest):
    """The data-driven NPC definition layer (NpcDef + NPC_DB), mirroring
    ItemDef / ITEM_DB and ShopDef / SHOP_DB."""

    def test_mutant_raider_is_registered(self):
        from world.npc_database import NPC_DB, NpcDef

        self.assertIn("mutant_raider", NPC_DB)
        self.assertIsInstance(NPC_DB["mutant_raider"], NpcDef)

    def test_combat_block_has_every_key_apply_combat_stats_reads(self):
        # HostileNPC.apply_combat_stats pulls exactly these keys; any missing
        # key silently falls back to unarmed defaults, which would hide a def
        # that forgot a stat. Assert the surface explicitly.
        from world.npc_database import NPC_DB

        block = NPC_DB["mutant_raider"].to_combat_block()
        for key in (
            "strike_level", "brawn_level", "defense_level",
            "max_hp", "attack_speed",
            "combat_stat_bonuses", "combat_styles", "default_combat_style",
        ):
            self.assertIn(key, block, f"NpcDef.to_combat_block missing {key}")

    def test_spawn_via_registry_matches_spawn_via_spawner(self):
        # The @register_spawner function in npc_combat.py is now a one-line
        # lookup against NPC_DB; spawning through it should produce an NPC
        # with the same stats as NpcDef.create directly.
        from world.npc_database import NPC_DB

        via_spawner = spawn_mutant_raider(self.room1)
        via_def = NPC_DB["mutant_raider"].create(location=self.room1)

        self.assertEqual(via_spawner.db.attack_speed, via_def.db.attack_speed)
        self.assertEqual(via_spawner.db.default_combat_style,
                         via_def.db.default_combat_style)
        self.assertEqual(via_spawner.db.combat_stat_bonuses,
                         via_def.db.combat_stat_bonuses)
        self.assertEqual(via_spawner.db.attack_type,
                         via_def.db.attack_type)
        # OSRS goblin L2 Hitpoints = 5.
        self.assertEqual(via_spawner.db.max_hp, 5)
        self.assertEqual(via_def.db.max_hp, 5)


class TestDefenderBonuses(EvenniaTest):
    """The defender's armour must come from the defender."""

    def test_npc_defense_bonuses_come_from_the_npc(self):
        """Regression: the swing read defence bonuses out of the *attacker's*
        weapon block, so defence never applied to anything."""
        npc = spawn_mutant_raider(self.room1)
        npc.db.combat_stat_bonuses = dict(npc.db.combat_stat_bonuses, slash_defense_bonus=42)

        bonuses = get_defense_bonuses(npc)

        self.assertEqual(bonuses["slash_defense_bonus"], 42)

    def test_unequipped_character_falls_back_to_unarmed_defaults(self):
        bonuses = get_defense_bonuses(self.char1)

        self.assertEqual(bonuses, const.UNARMED_DEFAULT_COMBAT_STATS)


class TestRuntimeStateIsNotPersisted(EvenniaTest):
    """Per-tick handler state belongs on ndb, not db.

    The handler is `persistent = False` and rebuilds this state whenever
    combat starts, so writing it to db bought nothing and cost an Attribute
    read AND write every 0.6s per combatant. `pending_action` also pickled a
    live _Action instance into the database, which would have left unloadable
    rows behind after any rename of an action class.
    """

    _RUNTIME_FIELDS = (
        "target_id",
        "pending_action",
        "cooldown_ticks",
        "active_weapon_data",
    )

    def test_runtime_fields_live_on_ndb(self):
        handler = ensure_combat_handler(self.char1)

        self.assertIsNotNone(handler.ndb.active_weapon_data)
        self.assertEqual(handler.ndb.cooldown_ticks, 0)

    def test_no_runtime_field_is_written_to_the_attribute_table(self):
        handler = ensure_combat_handler(self.char1)
        target = spawn_mutant_raider(self.room1)
        ensure_combat_handler(target)

        # Drive a full action cycle so every field has been assigned.
        handler.queue_action({"kind": "attack", "target": target})
        handler.tick()

        stored_keys = {attr.key for attr in handler.attributes.all()}
        for field in self._RUNTIME_FIELDS:
            self.assertNotIn(
                field,
                stored_keys,
                f"{field} is being persisted to the Attribute table",
            )

    def test_init_runtime_state_reseeds_after_an_ndb_wipe(self):
        """A reload clears ndb; tick() must not then read None."""
        handler = ensure_combat_handler(self.char1)

        # Simulate what a reload does to in-memory-only state.
        handler.ndb.cooldown_ticks = None
        handler.ndb.active_weapon_data = None

        handler.init_runtime_state()

        self.assertEqual(handler.ndb.cooldown_ticks, 0)
        self.assertIsNotNone(handler.ndb.active_weapon_data)

    def test_tick_survives_a_wiped_ndb(self):
        handler = ensure_combat_handler(self.char1)
        handler.ndb.cooldown_ticks = None
        handler.ndb.active_weapon_data = None

        handler.tick()  # must not raise


class TestSwingReporting(EvenniaTest):
    """What a swing actually tells the attacker.

    Combat used to report only "You hit X for N": the XP the swing earned was
    granted silently, and nothing showed how much of the target was left.
    """

    def _sent_lines(self, mocked_msg) -> list:
        """Flatten a mocked .msg into plain strings, in send order.

        Direct sends arrive as a positional string; room broadcasts arrive as
        `text=(message, {})` via msg_contents, so both shapes are unpacked.
        """
        lines = []

        for call in mocked_msg.call_args_list:
            if call.args:
                payload = call.args[0]
            else:
                payload = call.kwargs.get("text", "")

            if isinstance(payload, (tuple, list)):
                payload = payload[0]

            lines.append(strip_ansi(str(payload)))

        return lines

    def _swing_for(self, damage):
        """Land exactly one swing of `damage` and return what char1 was sent."""
        handler = ensure_combat_handler(self.char1)
        target = spawn_mutant_raider(self.room1)
        ensure_combat_handler(target)
        handler.queue_action({"kind": "attack", "target": target})

        swing_result = {"hit": True, "damage": damage, "hit_prob": 1.0}

        with mock.patch(
            "systems.combat.combat.combat_calc.resolve_melee_swing",
            return_value=swing_result,
        ):
            with mock.patch.object(type(self.char1), "msg") as mocked_msg:
                handler.tick()

        return self._sent_lines(mocked_msg)

    def _index_of(self, lines, fragment) -> int:
        for index, line in enumerate(lines):
            if fragment in line:
                return index

        self.fail(f"no line containing {fragment!r} in {lines!r}")

    def test_hit_line_states_the_xp_earned(self):
        """An unarmed punch is an accurate style: Strike at 4.0/damage and
        Fortitude at its own 1.33/damage, both named on the hit line."""
        lines = self._swing_for(damage=3)

        hit_line = lines[self._index_of(lines, "You hit")]

        self.assertIn("+12 Strike", hit_line)
        self.assertIn("+4 Fortitude", hit_line)

    def test_xp_named_on_the_line_is_the_xp_actually_granted(self):
        """The readout must not drift from the award it describes."""
        handler = ensure_combat_handler(self.char1)
        before = self.char1.skills.get_total_xp("strike")

        lines = self._swing_for(damage=3)
        gained = self.char1.skills.get_total_xp("strike") - before

        self.assertIn(f"+{gained} Strike", lines[self._index_of(lines, "You hit")])

    def test_attacker_sees_the_target_hp_bar_after_the_hit(self):
        """OSRS goblin L2 hitpoints = 5, so a 2-damage hit leaves 3."""
        lines = self._swing_for(damage=2)

        bar_line = lines[self._index_of(lines, "3 / 5")]

        self.assertIn("Mutant Raider", bar_line)

    def test_hp_bar_follows_the_hit_line(self):
        lines = self._swing_for(damage=2)

        self.assertLess(
            self._index_of(lines, "You hit"),
            self._index_of(lines, "3 / 5"),
        )

    def test_a_lethal_hit_is_announced_before_the_death_line(self):
        """Regression: at_damage broadcast the death first, so the log read
        'Mutant Raider collapses' ABOVE the hit that killed it."""
        lines = self._swing_for(damage=5)

        self.assertLess(
            self._index_of(lines, "You hit"),
            self._index_of(lines, "collapses"),
        )

    def test_a_lethal_hit_still_shows_an_empty_bar(self):
        lines = self._swing_for(damage=5)

        self.assertIn("0 / 5", lines[self._index_of(lines, "0 / 5")])

    def test_a_miss_reports_no_xp(self):
        handler = ensure_combat_handler(self.char1)
        target = spawn_mutant_raider(self.room1)
        ensure_combat_handler(target)
        handler.queue_action({"kind": "attack", "target": target})

        swing_result = {"hit": False, "damage": 0, "hit_prob": 0.0}

        with mock.patch(
            "systems.combat.combat.combat_calc.resolve_melee_swing",
            return_value=swing_result,
        ):
            with mock.patch.object(type(self.char1), "msg") as mocked_msg:
                handler.tick()

        lines = self._sent_lines(mocked_msg)
        miss_line = lines[self._index_of(lines, "miss")]

        self.assertNotIn("xp", miss_line)
