"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/02/2026
Description: Implementation of the Cutting gathering skill.
"""



from evennia.utils import logger

from systems.quests import constants as quest_constants
from systems.quests.hooks import notify_quests

from systems.progression.skills.skill_defs.base_skill import BaseSkill
from systems.progression.skills.gatherables import GATHERABLE_REGISTRY
from world.item_database import ITEM_DB
from systems.stat_tracker import constants as stat_constants
from systems.statefeed import constants as feed_const

# Every line this module sends a player is gathering, so the routing tag is
# bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/statefeed/constants.py.
_MSG_GATHERING = {
    feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_GATHERING}


_MIN_HARVEST_COOLDOWN = 2.0

# What working a node without a tool costs, from the opening quest's design:
# "First they try to cut with bare hands, receive the material, but hurt
# themselves 1 Hitpoint."
_BARE_HAND_HP_COST = 1

_MSG_BARE_HANDS = (
    "You have no axe. You tear at the {node} with your bare hands, and it "
    "tears back."
)

_MSG_BARE_HAND_COST = "You lose {amount} Hitpoint working it loose."



class Cutting(BaseSkill):
    """
    Purpose: Manages the mechanics and unlock requirements for Cutting.
    """
    key = "cutting"
    name = "Cutting"
    category = "Gathering"
    description = "Proficiency with harvesting materials from anything cuttable."
    cooldown_seconds = _MIN_HARVEST_COOLDOWN



    def get_unlock_requirements(self, character: object) -> bool:
        """
        Purpose: Cutting is always unlocked for all players.
        """
        return True



    def _get_loot_info(self, target: object) -> tuple[str | None, str | None, int]:
        """
        Purpose: Determines what loot to generate from a cutting target.

        Entry:
            target is a valid Evennia object with db attributes

        Exit/Returns:
            Tuple of (item_key, item_name, xp_reward). item_key and
            item_name are None if target's gatherable_key is missing or
            unregistered.

        Module Globals:
            GATHERABLE_REGISTRY read

        Methodology:
            Looks up target.db.gatherable_key in GATHERABLE_REGISTRY to find
            the item this node yields, then resolves that item's display
            name from ITEM_DB. xp_reward still comes off the node instance
            so a per-spawn override remains possible. Fails closed (logs and
            returns None item_key/item_name) on an unregistered key rather
            than guessing an item.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 06/09/2026
        """
        xp_reward = target.db.xp_reward or 0
        gatherable_key = target.db.gatherable_key
        gatherable_def = GATHERABLE_REGISTRY.get(gatherable_key)

        if gatherable_def is None:
            logger.log_err(
                f"Cutting._get_loot_info: {target} has unregistered "
                f"gatherable_key {gatherable_key!r}."
            )
            return None, None, xp_reward

        item_key = gatherable_def.item_key
        item_name = ITEM_DB[item_key].name

        return item_key, item_name, xp_reward



    def _has_tool(self, character: object) -> bool:
        """
        Purpose: Checks if the character has an axe in inventory or equipped.
        """
        def _is_axe(item):
            return getattr(item.db, "tool_type", None) == "axe"

        has_axe = any(_is_axe(item) for item in character.contents)
        if not has_axe:
            has_axe = any(_is_axe(item) for item in character.equipment.all())

        return has_axe



    def _allows_bare_hands(self, target: object) -> bool:
        """
        Purpose: Whether this node may be worked without an axe.

        Entry:
            target is a cutting node with a db.gatherable_key.

        Exit/Returns:
            Returns True only if the node's GatherableDef opts in.

        Module Globals:
            GATHERABLE_REGISTRY read.

        Methodology:
            The permission is a property of the NODE, not of the character or
            of any quest. Cutting requires an axe, the only axe is crafted
            from scrap metal, and the only scrap metal is cut -- a deadlock
            that a brand-new character cannot break from inside. Exactly one
            node, the rusty pole, is soft enough to tear at by hand, which
            opens the loop without making axes optional anywhere else.

            Fails closed: an unregistered node is not bare-handable.

        Notes/References:
            GatherableDef.bare_hands in
            systems/progression/skills/gatherables.py carries the flag and the
            reasoning.

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        gatherable_def = GATHERABLE_REGISTRY.get(target.db.gatherable_key)

        if gatherable_def is None:
            return False

        return bool(gatherable_def.bare_hands)



    def _pay_bare_hand_cost(self, character: object, target: object) -> bool:
        """
        Purpose: Charge the character for working a node without a tool.

        Entry:
            character is a Character with combat attributes.
            target is the node being worked.

        Exit/Returns:
            Returns True if the character survived the cost, False if it
            killed them.

        Module Globals:
            _BARE_HAND_HP_COST read.
            _MSG_BARE_HANDS read.
            _MSG_BARE_HAND_COST read.

        Methodology:
            Applies the cost through at_damage so the hit runs the same
            death and messaging path any other damage does -- a player who
            tears at a pole on their last hit point dies of it, rather than
            silently landing on zero or on minus one.

            at_damage itself never messages the target -- combat callers do
            their own damage narration, and this is the only non-combat
            caller. Without a message here the player sees the flavor text
            and the eventual "for N XP" line but nothing in between telling
            them they were actually hurt, so this sends the HP-loss line
            explicitly using at_damage's returned delta.

            attacker is the character itself, which is the truth and which
            at_death normalises to no killer, so nobody is credited with the
            kill and no quest records it.

        Notes/References:
            The cost is from the quest design: "First they try to cut with
            bare hands, receive the material, but hurt themselves 1
            Hitpoint."

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        # Decided BEFORE the blow, because it cannot be read after one.
        # at_damage routes a fatal hit through at_death, and Character.respawn
        # restores HP to full -- so a character killed here is back at max HP
        # and is_alive() by the time at_damage returns. Asking afterwards
        # always answers "fine".
        survives = character.hp > _BARE_HAND_HP_COST

        character.msg((_MSG_BARE_HANDS.format(node=target.key), _MSG_GATHERING))
        delta = character.at_damage(_BARE_HAND_HP_COST, attacker=character,
                                    source=target)
        character.msg((_MSG_BARE_HAND_COST.format(amount=delta), _MSG_GATHERING))

        return survives



    def _execute_gathering(self, character: object, target: object, item_key: str, item_name: str, xp_reward: int) -> None:
        """
        Purpose: Performs the gathering action after all validations have passed.

        Entry:
            character is a valid Evennia Character object
            target is a valid Evennia object with a .key attribute
            item_key is a valid key in ITEM_DB
            item_name is a non-empty string for the created item
            xp_reward is a non-negative integer

        Exit/Returns:
            No conditions

        Module Globals:
            None

        Methodology:
            Creates the loot item from the ITEM_DB. Arms this skill's
            cooldown through the shared BaseSkill helper. Adds XP via the
            character.skills interface. Sends a success message combining all
            results.

        Notes/References:
            Requires target.db.xp_reward to be populated

        Author: Nick Hobar
        Creation date: 06/09/2026
        """
        ITEM_DB[item_key].create(
            location=character,
            home=character,
        )

        self.arm_cooldown(character)

        character.skills.add_xp(self.key, xp_reward)

        stats = getattr(character, "stats", None)
        gatherable_key = getattr(target.db, "gatherable_key", None)

        # Two verbs, deliberately. A quest that wants "harvest from this node"
        # names `cut:<gatherable_key>`; one that wants "obtain this material",
        # from any source, names `gather:<item_key>`. Collapsing them would
        # force every material objective to know which skill produced it.
        if gatherable_key:
            notify_quests(character, quest_constants.ACTION_CUT, gatherable_key)

        notify_quests(character, quest_constants.ACTION_GATHER, item_key)

        if stats is not None and gatherable_key:
            try:
                stats.increment(stat_constants.CUTTING_TOTALS_STAT_KEY, gatherable_key)
            except Exception as exc:
                logger.log_err(f"Cutting._execute_gathering {stat_constants.CUTTING_TOTALS_STAT_KEY} stat update failed: {exc!r}")
        
        success_msg = f"You successfully cut the {target.key} and receive a {item_name} for {xp_reward} XP."
        character.msg((success_msg, _MSG_GATHERING))



    def execute(self, character: object, target: object) -> None:
        """
        Purpose: Executes the entire cutting harvesting action, including all validations.
        
        Entry:
            character is a valid Evennia Character object
            target is a valid Evennia object
        
        Exit/Returns:
            No conditions (early returns on validation failures)
        
        Module Globals:
            None.

        Methodology:
            Validates the target is a node first. Accumulates any missing
            unlock or level requirements and returns them in a single
            formatted message if any fail. A missing AXE is only one of those
            failures on a node that demands a tool; a bare-handable node
            instead routes to the bare-handed harvest, which costs hit points
            but still teaches the node's normal XP -- the exemption opens the
            bootstrap deadlock, it does not also make the harvest worthless.
            Evaluates the harvest cooldown. On pass of all checks, invokes
            _execute_gathering to process loot, xp, and cooldown.
            
        Notes/References:
            See _allows_bare_hands for why the axe requirement is not
            absolute.

        Author: Nick Hobar
        Creation date: 06/09/2026
        """
        # 1. Target Type Validation (Fail fast if it's not a node)
        target_is_valid = hasattr(target, 'is_cutting_node') and target.is_cutting_node()
        
        if not target_is_valid:
            # Use Evennia's native inheritance check instead of hasattr
            if target.is_typeclass("typeclasses.characters.Character", exact=False):
                if target.key == character.key:
                    character.msg(
                        ("You cannot cut yourself for materials.", _MSG_GATHERING))
                    return
                character.msg(
                    (f"You cannot cut {target.key} for materials. They're a person! Unless..",
                     _MSG_GATHERING))
                return
            character.msg(
                (f"The {target.key} is not something you can cut for materials.",
                 _MSG_GATHERING))
            return

        # 2. Accumulate all missing requirements
        missing_reqs = []

        # A missing axe is only fatal on a node that demands one. The rusty
        # pole does not -- see _allows_bare_hands for why exactly one node is
        # exempt. bare_handed is carried down to the harvest, which pays for
        # it in hit points and withholds the XP.
        has_axe = self._has_tool(character)
        bare_handed = False

        if not has_axe:
            if self._allows_bare_hands(target):
                bare_handed = True
            else:
                missing_reqs.append("any kind of axe")


        if not self.get_unlock_requirements(character):
            missing_reqs.append("the 'Cutting Reward' unlock")
            
        req_level = target.db.required_level if target.db.required_level is not None else 1
        if not character.skills.meets_prerequisite(self.key, req_level):
            missing_reqs.append(f"Cutting level {req_level}")

        if missing_reqs:
            reqs_string = ", ".join(missing_reqs)
            character.msg(
                (f"To cut the {target.key}, you require: {reqs_string}.",
                 _MSG_GATHERING))
            return

        # 3. Check Cooldowns
        if not self.is_off_cooldown(character):
            character.msg(("You are already busy gathering.", _MSG_GATHERING))
            return

        # 4. Proceed with Gathering
        item_key, item_name, xp_reward = self._get_loot_info(target)
        if item_key is None:
            character.msg(
                (f"Something is wrong with the {target.key}. Tell a builder.",
                 _MSG_GATHERING))
            return

        if bare_handed:
            survived = self._pay_bare_hand_cost(character, target)

            # A character the cost killed has already been respawned
            # elsewhere. Handing them the chunk and telling them they
            # "successfully cut" it is not the experience they just had.
            if not survived:
                return

        self._execute_gathering(character, target, item_key, item_name, xp_reward)
