"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/17/2026
Description: Tests for the projectile shot end to end — the ammunition it
             spends, where the spent unit goes, and the two refusals.

What these are guarding
-----------------------
Every case here is a way a bow can look like it works and not. A shot that
spends nothing makes ammunition a decoration. A shot that spends on a hit but
not on a miss makes accuracy free. A recovered arrow that lands on the
SHOOTER's tile turns recovery into a refund. And a bow that resolves against
Strike and Brawn returns a perfectly plausible number while ignoring both
skills the player levelled.
"""

import random

from evennia.utils.test_resources import EvenniaTest

from items.equipment.constants import WieldLocation
from systems.gameplay.combat import ammunition
from systems.gameplay.combat import constants as const
from systems.gameplay.combat.combat import combat_profile, ensure_combat_handler
from systems.gameplay.combat.rules.context import ActionContext, read_skill_levels
from systems.gameplay.progression.skills import constants as skill_constants
from typeclasses.npc_combat import spawn_mutant_raider
from world.item_database import ITEM_DB


# Public constant definitions

# The bow and the arrow these cases fight with. Named rather than discovered,
# so a failure points at one definition.
BOW_KEY = "rusty_scrap_shortbow"
ARROW_KEY = "rusty_scrap_arrow"

# A stack big enough that no case runs it out by accident.
ARROW_STACK = 20


class _AlwaysRecovers(random.Random):
    """An RNG whose every draw recovers the projectile."""

    def random(self):
        return 0.0


class _NeverRecovers(random.Random):
    """An RNG whose every draw breaks the projectile."""

    def random(self):
        return 1.0


class _ProjectileFixture(EvenniaTest):
    """A character holding a bow and a quiver, and a raider to shoot at."""

    def setUp(self):
        super().setUp()

        self.bow = ITEM_DB[BOW_KEY].create(location=self.char1)
        self.char1.equipment.equip(self.bow)

        self.arrows = ITEM_DB[ARROW_KEY].create(
            location=self.char1, quantity=ARROW_STACK
        )
        # create() may return a row the destination merged away, so the live
        # stack is re-read off the slot rather than trusted from the return.
        self.char1.equipment.equip(self.char1.contents[-1])
        self.arrows = self.char1.equipment.slots[WieldLocation.AMMO]

        self.target = spawn_mutant_raider(self.room1)
        self.handler = ensure_combat_handler(self.char1)

    def _weapon_data(self):
        return combat_profile(self.char1)

    def _quantity(self):
        ammo = self.char1.equipment.slots[WieldLocation.AMMO]

        if ammo is None:
            return 0

        return ammo.quantity


class TestTheBowIsEquipped(_ProjectileFixture):
    """The fixture itself has to hold, or every case below proves nothing."""

    def test_the_profile_reports_the_bow_reach(self):
        self.assertEqual(self._weapon_data()["max_range"], ITEM_DB[BOW_KEY].max_range)

    def test_the_profile_reports_the_accepted_family(self):
        self.assertEqual(
            self._weapon_data()["accepted_ammo"], ITEM_DB[BOW_KEY].accepted_ammo
        )

    def test_the_quiver_is_loaded(self):
        self.assertEqual(self._quantity(), ARROW_STACK)

    def test_the_arrow_bonus_reaches_the_equipment_total(self):
        """The whole reason ammunition is a SLOT and not a bag check.

        The bonus rides in on total_combat_stat_bonuses with everything else,
        so the max-hit formula reads it without combat knowing an AMMO slot
        exists.
        """
        totals = self.char1.equipment.total_combat_stat_bonuses()
        expected = ITEM_DB[ARROW_KEY].combat_stat_bonuses[
            const.PROJECTILE_STRENGTH_BONUS_KEY
        ]

        self.assertEqual(totals[const.PROJECTILE_STRENGTH_BONUS_KEY], expected)


class TestTheShotResolvesAgainstTheRightSkills(_ProjectileFixture):
    """Guns for accuracy, Ballistics for damage. Never Strike, never Brawn."""

    def _context(self):
        profile = self._weapon_data()
        style = profile["active_combat_style"]

        return ActionContext(
            attacker=self.char1,
            defender=self.target,
            weapon=self.bow,
            weapon_data=profile,
            style=style,
            attack_type=style["attack_type"],
            attacker_stats=profile["combat_stat_bonuses"],
            defender_stats={},
            attacker_levels=read_skill_levels(self.char1),
            defender_levels=read_skill_levels(self.target),
            stance_boost=style.get("weapon_style_level_boost") or {},
        )

    def test_accuracy_reads_guns(self):
        self.assertEqual(self._context().accuracy_skill(), skill_constants.SKILL_KEY_GUNS)

    def test_damage_reads_ballistics(self):
        self.assertEqual(
            self._context().damage_skill(), skill_constants.SKILL_KEY_BALLISTICS
        )

    def test_the_damage_bonus_reads_the_projectile_key(self):
        """Not melee_strength_bonus, which the bow deliberately leaves at 0 --
        so a shot reading the melee key would lose the arrow's whole bonus
        and report a smaller hit with no error anywhere."""
        expected = ITEM_DB[ARROW_KEY].combat_stat_bonuses[
            const.PROJECTILE_STRENGTH_BONUS_KEY
        ]

        self.assertEqual(self._context().strength_equip_bonus(), expected)

    def test_the_damage_type_is_projectile(self):
        self.assertEqual(self._context().damage_type(), const.DAMAGE_TYPE_PROJECTILE)


class TestSpendingAmmunition(_ProjectileFixture):
    """One unit per shot, and then it drops or it breaks."""

    def test_a_shot_spends_exactly_one_unit(self):
        ammunition.spend(self.char1, self._weapon_data(), self.target,
                         rng=_NeverRecovers())

        self.assertEqual(self._quantity(), ARROW_STACK - 1)

    def test_a_broken_projectile_leaves_nothing_on_the_tile(self):
        ammunition.spend(self.char1, self._weapon_data(), self.target,
                         rng=_NeverRecovers())
        left = [obj for obj in self.room1.contents if obj.key == ITEM_DB[ARROW_KEY].name]

        self.assertEqual(left, [])

    def test_a_recovered_projectile_lands_on_the_target_tile(self):
        """The TARGET's tile, not the shooter's. Recovery is a walk back to
        where the fight happened, which is what makes it a mechanic rather
        than a refund."""
        ammunition.spend(self.char1, self._weapon_data(), self.target,
                         rng=_AlwaysRecovers())
        left = [obj for obj in self.target.location.contents
                if obj.key == ITEM_DB[ARROW_KEY].name]

        self.assertEqual(len(left), 1)
        self.assertEqual(left[0].quantity, 1)

    def test_recovered_projectiles_merge_into_one_pile(self):
        """A room does not merge an arriving stack the way an inventory does,
        so a fight without the explicit merge leaves one object per arrow."""
        for _shot in range(4):
            ammunition.spend(self.char1, self._weapon_data(), self.target,
                             rng=_AlwaysRecovers())

        left = [obj for obj in self.target.location.contents
                if obj.key == ITEM_DB[ARROW_KEY].name]

        self.assertEqual(len(left), 1)
        self.assertEqual(left[0].quantity, 4)

    def test_the_slot_empties_when_the_last_unit_goes(self):
        """reduce_units deletes the drained object, and a slot still pointing
        at that row reads back as "ammunition equipped" to every check."""
        for _shot in range(ARROW_STACK):
            ammunition.spend(self.char1, self._weapon_data(), self.target,
                             rng=_NeverRecovers())

        self.assertIsNone(self.char1.equipment.slots[WieldLocation.AMMO])

    def test_a_melee_attacker_spends_nothing(self):
        """Every swing in the game takes this path. It has to cost nothing
        and report nothing rather than raise."""
        self.char1.equipment.unequip(self.bow)
        spent = ammunition.spend(self.char1, combat_profile(self.char1), self.target)

        self.assertFalse(spent)


class TestTheAmmunitionCheck(_ProjectileFixture):
    """The two refusals, and the one case that must never be refused."""

    def test_a_loaded_bow_is_accepted(self):
        accepted, _reason = ammunition.check(self.char1, self._weapon_data())

        self.assertTrue(accepted)

    def test_an_empty_slot_is_refused(self):
        self.char1.equipment.unequip(self.arrows)
        accepted, reason = ammunition.check(self.char1, self._weapon_data())

        self.assertFalse(accepted)
        self.assertIn("nothing to fire", reason.lower())

    def test_the_wrong_family_is_refused(self):
        """A different refusal from an empty quiver, because it sends the
        player somewhere different."""
        self.arrows.tags.clear(category=const.AMMO_FAMILY_TAG_CATEGORY)
        self.arrows.tags.add("bolt", category=const.AMMO_FAMILY_TAG_CATEGORY)

        accepted, reason = ammunition.check(self.char1, self._weapon_data())

        self.assertFalse(accepted)
        self.assertIn("does not fit", reason.lower())

    def test_a_melee_weapon_is_never_refused(self):
        self.char1.equipment.unequip(self.bow)
        self.char1.equipment.unequip(self.arrows)

        accepted, _reason = ammunition.check(self.char1, combat_profile(self.char1))

        self.assertTrue(accepted)

    def test_the_queue_refuses_a_shot_with_an_empty_quiver(self):
        """The refusal has to land at queue time, not 600ms later through a
        fight that could never fire."""
        self.char1.equipment.unequip(self.arrows)
        self.handler._refresh_weapon()

        accepted = self.handler._validate_attack(
            {"kind": "attack", "target": self.target}
        )

        self.assertFalse(accepted)


class TestARecoveredArrowIsStillAnArrow(_ProjectileFixture):
    """The recovered unit has to be the same ITEM, not a lookalike.

    A split builds the new stack by hand rather than through the prototype, so
    it is the one path that can make an arrow with no tags. Nothing in the
    game reads an item's family off an attribute -- the bow matches a tag, a
    recipe finds its material by a tag, and the pane picks a mesh from one --
    so a copy that carried only attributes looked right on `examine` and could
    never be fired again.
    """

    def _recovered(self):
        ammunition.spend(
            self.char1, self._weapon_data(), self.target, rng=_AlwaysRecovers()
        )

        for obj in self.room1.contents:
            if obj.key == self.arrows.key and obj is not self.arrows:
                return obj

        return None

    def test_it_lands_on_the_floor(self):
        self.assertIsNotNone(self._recovered())

    def test_it_keeps_its_ammunition_family(self):
        recovered = self._recovered()

        self.assertEqual(ammunition.family_of(recovered), const.AMMO_FAMILY_ARROW)

    def test_it_can_be_picked_up_and_fired_again(self):
        """The player-visible form of the case above.

        The original stack is destroyed first, not merely unequipped: a stack
        arriving in the inventory merges into a mergeable one and is deleted,
        so the recovered unit would otherwise be folded into the very object
        this case is trying to fire.
        """
        recovered = self._recovered()
        self.char1.equipment.unequip(self.arrows)
        self.arrows.delete()
        recovered.move_to(self.char1, quiet=True)
        self.char1.equipment.equip(recovered)

        accepted, reason = ammunition.check(self.char1, self._weapon_data())

        self.assertTrue(accepted, msg=reason)

    def test_it_keeps_every_tag_the_definition_declared(self):
        """Stated over the DEF rather than as a literal list, so a new tag on
        the arrow is covered by this test without editing it."""
        recovered = self._recovered()
        carried = set(recovered.tags.all(return_key_and_category=True))

        for tag in ITEM_DB[ARROW_KEY].tags:
            with self.subTest(tag=tag):
                self.assertIn(tuple(tag), carried)


class TestTheQuiverReachesTheClient(_ProjectileFixture):
    """A shot writes `quantity` on an object that does not move, so not one
    inventory hook fires. The pane held the count the quiver had when the
    player equipped it until the shot that emptied it."""

    def test_spending_a_unit_publishes_the_inventory(self):
        from unittest import mock

        with mock.patch(
            "systems.interface.statefeed.events.emit_inventory"
        ) as mocked_emit:
            ammunition.spend(self.char1, self._weapon_data(), self.target,
                             rng=_NeverRecovers())

        self.assertTrue(mocked_emit.called)

    def test_a_melee_swing_publishes_nothing(self):
        """It spends nothing, so there is nothing to say."""
        from unittest import mock

        self.char1.equipment.unequip(self.bow)

        with mock.patch(
            "systems.interface.statefeed.events.emit_inventory"
        ) as mocked_emit:
            ammunition.spend(self.char1, combat_profile(self.char1), self.target)

        self.assertFalse(mocked_emit.called)
