"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/17/2026
Description: Tests for what a combat style changes besides its level boost —
             the attack speed it charges, and the XP rate it pays.

Why the speed is tested through combat_profile
----------------------------------------------
There are TWO readers of a weapon's attack speed: _charge_cooldown, which
pays for it, and style_options.combat_options, which shows it. A delta
applied at only one of them would show the player a number the fight does not
use, which is the failure this file exists to catch. Both read
combat_profile, so asserting there covers both.
"""

from evennia.utils.test_resources import EvenniaTest, EvenniaTestCase

from systems.gameplay.combat import constants as const
from systems.gameplay.combat import style_options
from systems.gameplay.combat.combat import (
    _plan_style_xp,
    combat_profile,
    ensure_combat_handler,
    set_combat_style,
)
from systems.gameplay.progression.skills import constants as skill_constants
from world.item_database import ITEM_DB
from world.item_defs.weapons import _SHORTBOW_COMBAT_STYLES


# Public constant definitions

# The weapon these cases carry. Its four styles are the only ones in the game
# that declare a speed delta or an XP rate of their own.
BOW_KEY = "rusty_scrap_shortbow"

# Damage used for the XP plans. Large enough that a rate of 1.33 still rounds
# to something a comparison can see.
_DAMAGE = 12


class TestStyleSpeed(EvenniaTest):
    """Rapid buys one tick. Nothing else changes the weapon's pace."""

    def setUp(self):
        super().setUp()

        self.bow = ITEM_DB[BOW_KEY].create(location=self.char1)
        self.char1.equipment.equip(self.bow)
        self.handler = ensure_combat_handler(self.char1)

    def _speed_with(self, style_key) -> int:
        set_combat_style(self.bow, style_key, self.char1)

        return combat_profile(self.char1)["attack_speed"]

    def test_rapid_charges_one_tick_less_than_the_weapon(self):
        base = ITEM_DB[BOW_KEY].attack_speed

        self.assertEqual(self._speed_with("rapid"), base - 1)

    def test_every_other_style_charges_the_weapon_speed(self):
        """Read from the style table rather than listed, so a fifth style is
        covered the day it is written."""
        base = ITEM_DB[BOW_KEY].attack_speed

        for style_key, style in _SHORTBOW_COMBAT_STYLES.items():
            if style.get(const.STYLE_ATTACK_SPEED_DELTA_KEY):
                continue

            with self.subTest(style=style_key):
                self.assertEqual(self._speed_with(style_key), base)

    def test_the_options_screen_reports_the_style_speed(self):
        """The screen and the cooldown must agree. They read one routine, and
        this is what says so."""
        set_combat_style(self.bow, "rapid", self.char1)
        shown = style_options.combat_options(self.char1)["attack_speed_ticks"]

        self.assertEqual(shown, combat_profile(self.char1)["attack_speed"])

    def test_the_cooldown_charged_matches_the_style_speed(self):
        """_charge_cooldown pays speed - 1, because the action itself
        consumes the tick it resolves on."""
        set_combat_style(self.bow, "rapid", self.char1)
        speed = combat_profile(self.char1)["attack_speed"]

        action = _SelfSustaining()
        self.handler._charge_cooldown(action)

        self.assertEqual(self.handler.ndb.cooldown_ticks, speed - 1)

    def test_no_style_can_charge_less_than_one_tick(self):
        """An action cannot resolve more than once per tick, so a faster
        number would be one nothing could honour."""
        for style_key, style in _SHORTBOW_COMBAT_STYLES.items():
            with self.subTest(style=style_key):
                self.assertGreaterEqual(
                    self._speed_with(style_key), const.MIN_ATTACK_SPEED_TICKS
                )


class _SelfSustaining:
    """An action that keeps itself queued and pays a cooldown, like an attack."""

    consumes_cooldown = True

    def next_action(self, _handler):
        return self


class TestStyleXpBudget(EvenniaTestCase):
    """One action pays one XP budget. A style that names more skills splits it.

    The numbers themselves are balance and are read from their owner. What is
    asserted is the RELATIONSHIP: every style pays the same total, and snipe
    pays two skills where melee defensive pays one.
    """

    def _total_paid(self, style) -> float:
        """What one style pays across every skill it names, per damage."""
        plan = _plan_style_xp(_Earner(), style, _DAMAGE)

        return sum(amount for _skill, amount in plan) / _DAMAGE

    def test_snipe_names_guns_and_defense(self):
        planned = dict(_plan_style_xp(_Earner(), _SHORTBOW_COMBAT_STYLES["snipe"],
                                      _DAMAGE))

        self.assertIn(skill_constants.SKILL_KEY_GUNS, planned)
        self.assertIn(skill_constants.SKILL_KEY_DEFENSE, planned)

    def test_snipe_pays_the_two_the_same(self):
        planned = dict(_plan_style_xp(_Earner(), _SHORTBOW_COMBAT_STYLES["snipe"],
                                      _DAMAGE))

        self.assertEqual(
            planned[skill_constants.SKILL_KEY_GUNS],
            planned[skill_constants.SKILL_KEY_DEFENSE],
        )

    def test_every_projectile_style_pays_the_same_total(self):
        """The whole reason snipe declares its own rate. Without it snipe
        would take the melee defensive rate and pay half again as much as
        every other style in the game."""
        totals = {
            style_key: self._total_paid(style)
            for style_key, style in _SHORTBOW_COMBAT_STYLES.items()
        }
        first = next(iter(totals.values()))

        for style_key, total in totals.items():
            with self.subTest(style=style_key):
                self.assertAlmostEqual(total, first, places=2)

    def test_a_projectile_style_pays_the_same_total_as_a_melee_style(self):
        """Read from the melee tables rather than written as 5.33, so a
        retune of the budget moves both sides together."""
        melee = {
            "weapon_style": "accurate",
            "weapon_style_xp_skill": const.ACCURATE_XP_SKILLS,
        }

        self.assertAlmostEqual(
            self._total_paid(_SHORTBOW_COMBAT_STYLES["accurate"]),
            self._total_paid(melee),
            places=2,
        )

    def test_the_accurate_style_trains_guns_and_not_strike(self):
        planned = dict(_plan_style_xp(_Earner(),
                                      _SHORTBOW_COMBAT_STYLES["accurate"], _DAMAGE))

        self.assertIn(skill_constants.SKILL_KEY_GUNS, planned)
        self.assertNotIn(skill_constants.SKILL_KEY_STRIKE, planned)

    def test_the_aggressive_styles_train_ballistics_and_not_brawn(self):
        for style_key in ("rapid", "penetrate"):
            with self.subTest(style=style_key):
                planned = dict(_plan_style_xp(_Earner(),
                                              _SHORTBOW_COMBAT_STYLES[style_key],
                                              _DAMAGE))

                self.assertIn(skill_constants.SKILL_KEY_BALLISTICS, planned)
                self.assertNotIn(skill_constants.SKILL_KEY_BRAWN, planned)


class _Earner:
    """Something _plan_style_xp will plan awards for.

    It needs a `skills` that satisfies the XpEarner protocol and nothing
    else: the plan is pure arithmetic over the style, and granting is a
    separate call this file never makes.
    """

    def __init__(self):
        self.skills = _Skills()


class _Skills:
    """The whole XpEarner surface, doing nothing.

    Every method is needed: _plan_style_xp gates on
    `isinstance(attacker.skills, XpEarner)`, and a runtime protocol check
    asks for all three. A stub missing one plans no awards at all, and every
    assertion below would pass against an empty dict.
    """

    def add_xp(self, skill_key, amount):
        return None

    def get_total_xp(self, skill_key):
        return 0

    def meets_prerequisite(self, skill_key, required_level):
        return True
