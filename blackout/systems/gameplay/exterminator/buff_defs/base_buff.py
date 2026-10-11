"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: BaseExterminatorBuff, the shape of every Exterminator buff.

             A buff is a combat rules definition (BaseActionRules) that works
             only against a creature of the task type. One file under
             buff_defs/ is one buff, and systems/gameplay/exterminator/
             buffs.py finds it with no edit.

             Buffs are NOT under combat/rules/rule_defs/. An ItemDef names
             its rules by key in `combat_rules`, and a buff there could then
             ride on an item, against every target. DESIGN-0012, Phase 3.
"""

from systems.gameplay.combat import constants as combat_const
from systems.gameplay.combat.rules.rule_defs.base_rules import BaseActionRules
from systems.gameplay.exterminator import constants as ext_const



# The key of this base class. The registry skips a class that keeps it.
BASE_BUFF_KEY: str = "base_exterminator_buff"



class BaseExterminatorBuff(BaseActionRules):
    """
    Purpose: A rules definition that applies only against the task type of
             the player who holds it.

    Entry:
        A subclass sets `key`, `name`, `description`, and `archetype`, and
        overrides contribute_modifiers or one seam.

    Exit/Returns:
        Not applicable. A rules definition.

    Module Globals:
        combat_const.RULES_PRIORITY_BUFF read.

    Methodology:
        The target check is applies_to, and ONE collector calls it:
        buffs.active_buffs, from _build_context in combat.py. A buff that
        fails the check never enters the rule list of the action. Thus, a
        seam buff never needs a check inside the seam.

        A check inside a seam would be wrong. A seam that fails it can only
        call super(), and super() gives the OSRS default, not the weapon.
        A damage-roll buff would then switch off the toy sword d20 against
        every other target.

        The check tests the OPPONENT of the holder, not the defender. When a
        crab hits the player, the player is the defender, and a defense buff
        on the player must test the crab. active_buffs passes the right
        opponent for each side.

    Notes/References:
        A modifier buff reads context.accuracy_channel() and
        context.damage_channel(), so one buff serves a sword and a bow. It
        reads levels through context.levels_for(bag), as
        glass_cannon_amulet.py does.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """

    key = BASE_BUFF_KEY
    name = "Base buff"
    description = "No effect."

    # The archetype key from the vault note, for example "accuracy_vs_type".
    archetype = ""

    # Above the weapon tier. See RULES_PRIORITY_BUFF in combat/constants.py.
    # Nick, 10/06/2026: a buff beats the weapon by default.
    priority = combat_const.RULES_PRIORITY_BUFF

    # One number for each rarity: {RARITY_*: value}. The rarity of the card
    # sets the strength (Nick, 10/06/2026). A rarity with no row uses the
    # Common row. A buff with no number leaves this empty.
    strengths: dict = {}

    def holder_of(self, context, bag):
        """The entity that holds this buff in one action: the owner of the bag."""
        if bag is context.defender_bag:
            return context.defender

        return context.attacker

    def holder_attacks(self, context, bag) -> bool:
        """Say whether the holder of this bag is the attacker of the action."""
        return bag is context.attacker_bag

    def value_at(self, rarity):
        """
        The number of this buff at one rarity. The Common number when the
        rarity has no row, and 0 when `strengths` is empty.
        """
        common_value = self.strengths.get(ext_const.RARITY_COMMON, 0)

        return self.strengths.get(rarity, common_value)

    def strength(self, holder):
        """
        Purpose: Give the number of this buff at the rarity that the holder
                 picked.

        Entry:
            holder is the entity that holds the buff.

        Exit/Returns:
            Returns value_at for the rarity of the held card. An entity
            with no handler gets the Common number.

        Module Globals:
            None.

        Methodology:
            The registry holds one instance for each buff, so the rarity is
            not on the instance. It is on the task of the holder.

        Notes/References:
            A modifier buff calls strength(self.holder_of(context, bag)).

        Author: Nick Hobar
        Creation date: 10/06/2026
        """
        handler = getattr(holder, "exterminator", None)
        rarity = handler.buff_rarity(self.key) if handler is not None else None

        return self.value_at(rarity)

    def describe(self, rarity, holder=None) -> str:
        """
        The description for a card or a held buff, at one rarity. The
        `description` template can name `{value}`. holder is the player who
        reads it, or None. A buff whose text needs the task reads it.
        """
        value = self.value_at(rarity)

        return self.description.format(value=value)

    def points_bonus(self, holder) -> float:
        """
        The part of the task points that this buff adds when the task ends,
        as a fraction: 0.5 is +50%. The handler asks each held buff while
        the task still exists. Most buffs add nothing.
        """
        return 0.0

    def applies_to(self, holder, opponent) -> bool:
        """
        Purpose: Say whether this buff works in one action.

        Entry:
            holder is the entity that holds the buff.
            opponent is the other side of the action.

        Exit/Returns:
            Returns True when the holder has a task and the opponent has the
            creature type of that task.

        Module Globals:
            None.

        Methodology:
            1. If the holder has no Exterminator handler, return False.
            2. If the holder has no task, return False.
            3. Return whether the task type is a type of the opponent.

        Notes/References:
            A subclass can narrow this, for example to a low HP line. It must
            call super() first.

        Author: Nick Hobar
        Creation date: 10/06/2026
        """
        from world.npc_database import creature_types_of

        handler = getattr(holder, "exterminator", None)

        if handler is None:
            return False

        task_type = handler.creature_type()

        if not task_type:
            return False

        opponent_types = creature_types_of(opponent)

        return task_type in opponent_types
