"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/10/2026
Description: The behaviour every gathering skill shares -- validate, open a
             channel, roll each swing, create the item, teach the XP,
             announce it.

             This exists because Butchery began life as a byte-for-byte copy
             of Cutting with the nouns swapped, including a docstring still
             arguing about axes and rusty poles inside the meat skill. Three
             copies of _pay_bare_hand_cost would have been three places to
             fix the next change to at_damage. A gathering skill is now a
             handful of class attributes, which is the same bargain
             GATHERABLE_REGISTRY offers content: adding one is a declaration,
             not an implementation.

             The harvest is a CHANNEL since 09/20/2026. `execute` no longer
             produces an item: it checks everything once, says the player has
             started, and hands the node to a GatheringHandler on the global
             tick. `attempt_swing` is what that handler calls, and it is
             where the roll, the item and the depletion live.

             The split follows the same line the whole gathering system
             follows. THE SKILL KNOWS WHAT A HARVEST IS; the handler knows
             what a cadence is. Nothing in gather_handler.py names a skill,
             a node kind or an item, and nothing here counts a tick.
"""



import random

from evennia.utils import logger

from systems.gameplay.progression.skills.gatherables import (
    get_gatherable_for_node,
    get_yield_item_name,
    yield_menu_label,
)
from systems.gameplay.progression.skills import xp_awards
from systems.gameplay.progression.skills.skill_defs import base_skill
from systems.gameplay.progression.skills.skill_defs.base_skill import BaseSkill
from systems.gameplay.progression.skills.skill_defs.gathering import (
    constants as gather_constants,
    depletion,
    gather_handler,
    roll,
)
from systems.gameplay.quests import constants as quest_constants
from systems.gameplay.quests.hooks import notify_quests
from systems.interface.statefeed import constants as feed_const
from world.item_database import ITEM_DB

# Every line this module sends a player is gathering, so the routing tag is
# bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/interface/statefeed/constants.py.
_MSG_GATHERING = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_GATHERING}


# The RNG every swing draws from, unless a caller passes its own.
#
# A module-level instance rather than the `random` module, so a test hands in
# a seeded random.Random and gets a run it can assert on. CLAUDE.md, "Writing
# tests": a test that reads the global RNG passes until somebody else seeds
# it.
_RNG = random.Random()

# What working a node without a tool costs, from the opening quest's design:
# "First they try to cut with bare hands, receive the material, but hurt
# themselves 1 Hitpoint."
BARE_HAND_HP_COST = 1

_MSG_BARE_HANDS = (
    "Without {tool}, you tear at the {node} with your bare hands, and it "
    "tears back."
)

_MSG_BARE_HAND_COST = "You lose {amount} Hitpoint working it loose."

# What a player is told when they aim at a DIFFERENT node while a channel is
# running. Aiming at the SAME one is not a refusal -- see MSG_ALREADY_WORKING
# in the gathering constants for why.
_MSG_BUSY = "You are already busy gathering. Stop first."



class GatheringSkill(BaseSkill):
    """
    Purpose: Base for every skill that works a node in GATHERABLE_REGISTRY.

    Entry:
        A subclass sets `key`, `name`, `category`, `description` as any
        BaseSkill does, plus the four attributes below.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        Everything that differs between Cutting and Butchery is a value, so
        it is declared as one. Everything that does not differ is written
        once, here.

    Notes/References:
        Which nodes this skill can work is NOT one of those attributes. It is
        read from GATHERABLE_REGISTRY, so a new node reaches the right skill
        by being declared, with no edit here and none in the node's typeclass
        -- which is what the old per-skill `is_cutting_node()` predicate cost.

    Author: Nick Hobar
    Creation date: 09/10/2026
    """
    # DELIBERATELY NONE. The cadence of a harvest belongs to the channel now
    # (gather_constants.SWING_TICKS), and the skill cooldown was the thing
    # the channel replaced. Leaving the old 2.0s here would gate the FIRST
    # swing of a channel against a timer nothing else in the loop consults,
    # so a player who stopped and restarted would lose a swing to a rule that
    # no longer exists.
    cooldown_seconds = base_skill.NO_COOLDOWN

    # The verb a player types, used in every message this skill sends.
    verb = "gather"

    # The tool_types (world/item_database.py: ItemDef.tool_type) that count as
    # this skill's tool. A TUPLE because one job takes several implements --
    # butchery is happy with anything with an edge -- and because a tuple of
    # one reads the same as a tuple of five at the call site.
    tool_types: tuple = ()

    # What a player without one is told they lack. Not derived from
    # tool_types, because "any kind of axe" is what a player understands and
    # "axe, battleaxe" is what the table happens to contain.
    tool_description = "the right tool"

    # The quest verb a successful harvest fires, keyed on the NODE. Separate
    # from ACTION_GATHER, which every harvest also fires keyed on the ITEM --
    # see _notify_quests for why both.
    quest_action = None

    # The stat_tracker key this skill's harvest totals accumulate under.
    stat_key = None



    def get_unlock_requirements(self, character: object) -> bool:
        """
        Purpose: Whether this skill is available to the character at all.

        Entry:
            character is a valid Evennia Character object.

        Exit/Returns:
            Returns True. Gathering skills are unlocked by default; a subclass
            that is earned rather than given overrides this.

        Module Globals:
            None.

        Methodology:
            Restated here rather than inherited silently from BaseSkill so
            that a reader of a gathering skill can see the default is "open"
            without opening another file.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        return True



    def find_tool(self, character: object) -> object | None:
        """
        Purpose: The tool this character would work a node with, if any.

        Entry:
            character is a Character with an equipment handler.

        Exit/Returns:
            Returns the tool object, or None when the character carries none.

        Module Globals:
            None.

        Methodology:
            EQUIPPED FIRST, then the rest of the inventory. That order is the
            design rule, not an optimisation: a corpse can be worked by
            several skills and it is what is in your hands that says which one
            you meant. Returning the object rather than a bool is what lets
            the caller say WHICH tool decided.

            Reads `db.tool_type` off the object rather than a tag or a
            typeclass, matching how the crafting recipes find their tools and
            how ItemDef declares them.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        if not self.tool_types:
            return None

        equipment = getattr(character, "equipment", None)
        equipped = equipment.all() if equipment is not None else []

        for item in list(equipped) + list(character.contents):
            if getattr(item.db, "tool_type", None) in self.tool_types:
                return item

        return None



    def _allows_bare_hands(self, gatherable_def) -> bool:
        """
        Purpose: Whether this node may be worked without a tool.

        Entry:
            gatherable_def is the node's GatherableDef, or None.

        Exit/Returns:
            Returns True only if the node opts in.

        Module Globals:
            None.

        Methodology:
            The permission is a property of the NODE, not of the character or
            of any quest. Cutting requires an axe, the only axe is crafted
            from scrap metal, and the only scrap metal is cut -- a deadlock
            that a brand-new character cannot break from inside. A node that
            is soft enough to tear at by hand opens the loop without making
            tools optional everywhere else.

            Fails closed: an unregistered node is not bare-handable.

        Notes/References:
            GatherableDef.bare_hands in
            systems/gameplay/progression/skills/gatherables.py carries the
            flag and the reasoning.

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        if gatherable_def is None:
            return False

        return bool(gatherable_def.bare_hands)



    def _choose_yield(self, character: object, gatherable_def, wanted: str = ""):
        """
        Purpose: Decide which of a node's yields this harvest produces.

        Entry:
            character is a valid Evennia Character object.
            gatherable_def is the node's GatherableDef.
            wanted is the player's explicit choice -- an item key, an item
                name, or a unique prefix of either. Empty for "your best".

        Exit/Returns:
            Returns (chosen_yield, refusal). Exactly one is ever set:
            chosen_yield is a GatherableYield and refusal is "", or
            chosen_yield is None and refusal is a sentence to show the player.

        Module Globals:
            None.

        Methodology:
            Unasked, the harvest gives the BEST cut the character has unlocked
            -- the highest required_level they meet, and of the yields tied at
            that level, the one declared first (see _default_yield). At level
            0 the chuck is the default and the hide is available by name. At
            Butchery 10 the filet becomes the default, and the chuck and both
            hides stay available by name. That is the design rule read forwards: levelling should
            change what happens by default, and naming a cut should still be
            possible afterwards.

            An explicit choice is matched the way `skills <arg>` matches its
            argument -- exact, then unique prefix, then unique substring -- so
            `butcher corpse = filet` works without the player knowing that the
            item key is mutant_raider_raw_filet, and so does `= chuck`, which
            is a word in the middle of every name that cut has.

            An ambiguous choice is told what it could have meant. "Yields
            nothing called 'raw'" is false where two cuts are both raw, and a
            player reading it goes looking for a different word rather than a
            longer one.

            A named-but-locked yield is refused with its level rather than
            silently downgraded to the one below it. Handing someone a chuck
            when they asked for a filet is the kind of quiet substitution that
            gets reported as a loot bug.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        candidates = gatherable_def.yields_for_skill(self.key)

        if not candidates:
            return None, (
                f"You cannot {self.verb} the {gatherable_def.node_name}."
            )

        if wanted:
            matches = self._matching_yields(candidates, wanted)

            if not matches:
                return None, (
                    f"The {gatherable_def.node_name} yields nothing called "
                    f"'{wanted}'."
                )

            if len(matches) > 1:
                named = ", ".join(yield_menu_label(entry) for entry in matches)

                return None, (
                    f"'{wanted}' could mean {named}. Name one."
                )

            matched = matches[0]

            if not character.skills.meets_prerequisite(
                    self.key, matched.required_level):
                return None, (
                    f"Taking the {get_yield_item_name(matched)} needs "
                    f"{self.name} level {matched.required_level}."
                )

            return matched, ""

        unlocked = [
            entry for entry in candidates
            if character.skills.meets_prerequisite(self.key, entry.required_level)
        ]

        if not unlocked:
            lowest = candidates[0]
            return None, (
                f"To {self.verb} the {gatherable_def.node_name} you require: "
                f"{self.name} level {lowest.required_level}."
            )

        default = self._default_yield(unlocked)

        return default, ""


    def _default_yield(self, unlocked: list):
        """
        Purpose: The yield an unasked harvest gives, from the ones unlocked.

        Entry:
            unlocked is a non-empty list of GatherableYield, in the order
            yields_for_skill returns them.

        Exit/Returns:
            Returns the FIRST-DECLARED yield of the highest required_level in
            the list.

        Module Globals:
            None.

        Methodology:
            The highest level is the tier the character has most recently
            reached. Inside that tier, declaration order breaks a tie. The
            sort in yields_for_skill is stable, so the list keeps the
            declaration order of yields that share a level.

            "The last one in the list" was the rule until the corpse gained a
            hide beside the chuck at level 0 and beside the filet at level
            10. The ladder had no ties before, so "last" and "best" meant the
            same thing. With a tie, "last" meant "declared last", and one
            added yield silently changed the default of every character at
            that tier.

            First-declared makes the addition safe. A new yield at an
            existing level is available by name and never displaces the
            default. To make a new yield the default, declare it first, or
            give it a level of its own.

        Notes/References:
            GatherableDef.yields_for_skill owns the order this reads.

        Author: Nick Hobar
        Creation date: 09/17/2026
        """
        top_level = unlocked[-1].required_level

        for entry in unlocked:
            if entry.required_level == top_level:
                return entry

        return unlocked[-1]



    def _matching_yields(self, candidates: list, wanted: str) -> list:
        """
        Purpose: Every one of a node's yields a player's typed choice could
        have meant.

        Entry:
            candidates is a non-empty list of GatherableYield.
            wanted is a non-empty, already-stripped string.

        Exit/Returns:
            Returns a list of GatherableYield: empty when nothing matched, one
            when the choice was unambiguous, several when it was not.

        Module Globals:
            None.

        Methodology:
            Three passes over three names each, narrowest first, and the first
            pass that matches anything at all is the answer. Exact wins over
            prefix and prefix over substring, so a cut whose whole name
            another cut merely contains is still reachable by typing it.

            SUBSTRING, not only prefix, is what `= chuck` needs. Every cut off
            the raider is called "mutant raider raw <cut>", so the word that
            tells them apart is the LAST one and no prefix of any name reaches
            it -- `butcher corpse = chuck` was refused as a name the corpse
            does not yield, next to a message that had just used it.

            The menu_label is matched alongside the key and the item name
            because it is the word a right-click row shows. A player who can
            read "Butcher chuck from ..." on screen and cannot type it has
            been shown a vocabulary the parser does not share.

            A list rather than one entry or None, because "matched nothing"
            and "matched three things" are different refusals and the caller
            is the one that phrases them.

        Notes/References:
            The same widening-pass shape `skills <arg>` uses for its argument.

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        wanted = wanted.strip().lower()
        named = [(entry, self._yield_names(entry)) for entry in candidates]

        exact = [entry for entry, names in named if wanted in names]

        if exact:
            return exact

        prefixed = [
            entry for entry, names in named
            if any(name.startswith(wanted) for name in names)
        ]

        if prefixed:
            return prefixed

        return [
            entry for entry, names in named
            if any(wanted in name for name in names)
        ]


    def _yield_names(self, entry) -> tuple:
        """
        Purpose: Every string a player may call one yield by.

        Entry:
            entry is a GatherableYield.

        Exit/Returns:
            Returns a tuple of lower-cased names: the item key, the item's
            display name, and the yield's menu label.

        Module Globals:
            None.

        Methodology:
            Built here rather than inline in each pass so the three passes
            cannot come to disagree about which names count -- the bug that
            shape produces is a word the exact pass knows and the prefix pass
            does not.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        return (
            entry.item_key.lower(),
            get_yield_item_name(entry).lower(),
            yield_menu_label(entry).lower(),
        )



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
            BARE_HAND_HP_COST, _MSG_BARE_HANDS and _MSG_BARE_HAND_COST read.

        Methodology:
            Applies the cost through at_damage so the hit runs the same
            death and messaging path any other damage does -- a player who
            tears at a pole on their last hit point dies of it, rather than
            silently landing on zero or on minus one.

            at_damage itself never messages the target -- combat callers do
            their own damage narration, and this is the only non-combat
            caller. Without a message here the player sees the flavor text
            and the eventual harvest line but nothing in between telling
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
        survives = character.hp > BARE_HAND_HP_COST

        character.msg((
            _MSG_BARE_HANDS.format(tool=self.tool_description, node=target.key),
            _MSG_GATHERING,
        ))
        # `source` is the node, which is the truth about what hurt them and is
        # what the original cutting implementation passed. at_death does not
        # read it today; it is threaded through so that the day a death line
        # names what killed you, a bare-handed harvest can say "a rusty pole".
        delta = character.at_damage(BARE_HAND_HP_COST, attacker=character,
                                    source=target)
        character.msg((
            _MSG_BARE_HAND_COST.format(amount=delta), _MSG_GATHERING))

        return survives



    def _plan_xp(self, chosen) -> list:
        """
        Purpose: Work out this harvest's XP, primary skill and secondaries
        alike, without granting any of it.

        Entry:
            chosen is the GatherableYield being harvested.

        Exit/Returns:
            Returns a list of (skill_key, amount) pairs, primary first.

        Module Globals:
            None.

        Methodology:
            The primary skill is this one, always, and it takes the whole
            xp_reward. The secondaries come off the yield, which is where the
            skill-tree map's "cutting + butchery XP" arrows live -- the motion
            of taking a cut off a corpse is most of a cut, so Cutting learns
            something from it too.

            The secondary award is deliberately NOT a fraction of xp_reward
            computed here. A rule in code is a rule the content table cannot
            see; a number in the table is one a designer can read off the map.

            Planned apart from granting so the harvest line can name every
            skill it taught. The secondary award used to be paid silently,
            under a line reading only "for 25 XP".

        Notes/References:
            systems/gameplay/progression/skills/xp_awards.py.

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        awards = [(self.key, chosen.xp_reward)]

        for secondary_key, amount in (chosen.secondary_xp or {}).items():
            if secondary_key == self.key:
                continue

            awards.append((secondary_key, amount))

        return awards



    def _notify_quests(self, character: object, gatherable_def, chosen) -> None:
        """
        Purpose: Report the harvest to the quest system.

        Entry:
            character is a valid Evennia Character object.
            gatherable_def is the node's GatherableDef.
            chosen is the GatherableYield that was harvested.

        Exit/Returns:
            No conditions.

        Module Globals:
            quest_constants read.

        Methodology:
            Two verbs, deliberately. A quest that wants "work this node" names
            `<verb>:<gatherable_key>`; one that wants "obtain this material",
            from any source, names `gather:<item_key>`. Collapsing them would
            force every material objective to know which skill produced it,
            and every node objective to know which cut the player chose.

            A skill that declares no quest_action fires only the gather half,
            which is the right behaviour for one whose verb the vocabulary
            does not carry yet rather than a reason to invent one.

        Notes/References:
            systems/gameplay/quests/global_quest_actions.md is the other half
            of the vocabulary; test_quest_vocabulary.py asserts the two agree.

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        if self.quest_action:
            notify_quests(character, self.quest_action, gatherable_def.key)

        notify_quests(character, quest_constants.ACTION_GATHER, chosen.item_key)



    def _record_stat(self, character: object, gatherable_def) -> None:
        """
        Purpose: Add one to this skill's per-node harvest tally.

        Entry:
            character may or may not carry a stats handler.
            gatherable_def is the node's GatherableDef.

        Exit/Returns:
            No conditions. Never raises.

        Module Globals:
            None.

        Methodology:
            Wrapped, because a stat tracker is a bystander to the harvest --
            a broken counter must not cost the player the item they just
            earned. Same posture drop_loot takes around a broken loot table.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        stats = getattr(character, "stats", None)

        if stats is None or not self.stat_key:
            return

        try:
            stats.increment(self.stat_key, gatherable_def.key)
        except Exception as exc:
            logger.log_err(
                f"{type(self).__name__}._record_stat {self.stat_key} failed: "
                f"{exc!r}"
            )



    def _execute_gathering(self, character: object, target: object,
                           gatherable_def, chosen) -> str:
        """
        Purpose: Perform the harvest, once every check has passed.

        Entry:
            character is a valid Evennia Character object.
            target is the node being worked.
            gatherable_def is the node's GatherableDef.
            chosen is the GatherableYield to produce.

        Exit/Returns:
            Returns "" when the harvest happened, or STOP_REASON_BAG_FULL
            when it could not be carried. A stop reason rather than a bool,
            because the caller passes it straight back to the channel and a
            bool would need a second table here to say what it meant.

        Module Globals:
            ITEM_DB read.

        Methodology:
            Creates the item, announces the harvest with its XP, teaches that
            XP, then reports to quests and stats. The announcement precedes
            the grant so a level-up line reads below the award that caused
            it, and precedes the quest report so objective progress reads
            below the harvest that made it. The consume step is last of the
            state changes and separate (see consume_node) because a pole
            survives being cut and a corpse does not.

            THE BAG IS CHECKED AGAINST THE REAL OBJECT, not against a free
            slot count. The item is built detached and offered to the
            inventory, which answers with the same decision tree `add_item`
            uses -- already slotted, then a mergeable stack, then a free
            slot. A count of free slots gets the stackable case wrong, and
            that is a channel that stops at a full bag the player could in
            fact have added to.

            A refused item is DELETED. It never reached the character and
            nothing has been taught for it, so the swing that produced it is
            a swing that did not happen.

            It no longer arms a skill cooldown. The channel's own cadence is
            the only clock a harvest has -- see the cooldown_seconds comment
            on the class.

        Notes/References:
            ItemDef.create builds detached and then move_to()s, which is what
            fires at_object_receive and therefore the inventory stack merge.
            See CLAUDE.md "Evennia gotchas found the hard way" items 4 and 5.

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        item = ITEM_DB[chosen.item_key].create(location=None, home=character)
        room = self._has_room_for(character, item)

        if not room:
            item.delete()

            return gather_constants.STOP_REASON_BAG_FULL

        item_name = get_yield_item_name(chosen)
        awards = self._plan_xp(chosen)
        xp_text = xp_awards.format_xp_suffix(awards)

        item.move_to(character, quiet=True)

        character.msg((
            f"You successfully {self.verb} the {target.key} and receive a "
            f"{item_name}.{xp_text}",
            _MSG_GATHERING,
        ))

        xp_awards.grant_xp(character, awards, feed_const.MESSAGE_TYPE_GATHERING)
        self._notify_quests(character, gatherable_def, chosen)
        self._record_stat(character, gatherable_def)

        self.consume_node(target)

        return ""


    def _has_room_for(self, character: object, item) -> bool:
        """
        Purpose: Whether this character can actually carry one more of this.

        Entry:
            character is the harvester. item is a live, detached object.

        Exit/Returns:
            Returns True when the item fits. Returns True for a character
            with no inventory handler at all, which is the NPC case.

        Module Globals:
            None.

        Methodology:
            Asks the inventory rather than counting slots, so the answer
            cannot disagree with what `add_item` would decide a moment later.

            Fails OPEN, not closed. A character with no inventory handler is
            an NPC or a test fixture, and refusing the harvest for them would
            turn a missing handler into a silent gameplay rule.

        Notes/References:
            items/inventory/handler.py can_accept.

        Author: Nick Hobar
        Creation date: 09/20/2026
        """
        inventory = getattr(character, "inventory", None)

        if inventory is None:
            return True

        accepted = inventory.can_accept(item)

        return accepted



    def consume_node(self, target: object) -> None:
        """
        Purpose: What becomes of the node after a successful harvest.

        Entry:
            target is the node that was just worked.

        Exit/Returns:
            No conditions. The default does nothing.

        Module Globals:
            None.

        Methodology:
            A pole is still a pole after you cut a chunk off it. A corpse is
            not: one corpse is one harvest, by design, so the corpse
            typeclass opts in rather than every skill branching on what it is
            holding.

        Notes/References:
            typeclasses/corpses.py sets consumed_by_harvest.

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        if getattr(target, "consumed_by_harvest", False):
            target.delete()



    def execute(self, character: object, target: object, wanted: str = "") -> None:
        """
        Purpose: Open a channel at this node, checks included.

        Entry:
            character is a valid Evennia Character object.
            target is whatever the player named -- it need not be a node.
            wanted is an optional explicit yield choice.

        Exit/Returns:
            No conditions. Every failure path messages the caller and returns.

        Module Globals:
            None.

        Methodology:
            THIS NO LONGER PRODUCES ANYTHING. It answers one question -- may
            this player start working this node -- and then hands the node to
            a GatheringHandler on the global tick. attempt_swing is where the
            roll, the item and the depletion happen.

            In order: is it a node this skill works; is the skill unlocked;
            is a yield available at this level; is a tool in hand or is the
            node soft enough to do without; has this player already stripped
            it; are they already working something else. The tool question
            comes AFTER the yield question so a player who is simply too low
            a level is told that, rather than being sent to find a knife they
            would not be able to use yet.

            THE BARE-HAND COST IS NOT PAID HERE ANY MORE. It is paid per
            successful harvest inside _resolve_success, which is the rule it
            always described: you tear the chunk loose and it tears back. A
            cost at the start of a channel charges a player for swings that
            never landed.

        Notes/References:
            See _allows_bare_hands for why the tool requirement is not
            absolute.

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        gatherable_def = get_gatherable_for_node(target)

        if gatherable_def is None:
            character.msg((self._not_a_node_message(character, target),
                           _MSG_GATHERING))
            return

        if self.key not in gatherable_def.skill_keys():
            character.msg((
                f"The {target.key} is not something you can {self.verb}.",
                _MSG_GATHERING,
            ))
            return

        if not self.get_unlock_requirements(character):
            character.msg((
                f"To {self.verb} the {target.key}, you require: the "
                f"'{self.name}' unlock.",
                _MSG_GATHERING,
            ))
            return

        chosen, refusal = self._choose_yield(character, gatherable_def, wanted)

        if chosen is None:
            character.msg((refusal, _MSG_GATHERING))
            return

        tool = self.find_tool(character)

        if tool is None and not self._allows_bare_hands(gatherable_def):
            character.msg((
                f"To {self.verb} the {target.key}, you require: "
                f"{self.tool_description}.",
                _MSG_GATHERING,
            ))
            return

        if depletion.is_spent_for(target, character):
            character.msg((
                gather_constants.MSG_NODE_SPENT.format(node=target.key),
                _MSG_GATHERING,
            ))
            return

        if self._is_busy_elsewhere(character, target):
            return

        character.msg((
            gather_constants.MSG_CHANNEL_START.format(
                verb=self.verb, node=target.key),
            _MSG_GATHERING,
        ))

        gather_handler.start_gathering(character, self, target, wanted)


    def _is_busy_elsewhere(self, character: object, target: object) -> bool:
        """
        Purpose: Whether a channel already running blocks this one.

        Entry:
            character is the actor. target is the node they just named.

        Exit/Returns:
            Returns True when the caller must not start a channel. Messages
            the player itself in both cases that return True.

        Module Globals:
            None.

        Methodology:
            Two different answers, which is why this is not a plain
            predicate. Re-aiming at the SAME node is reassurance: the player
            is told they are already on it and nothing is torn down.
            Repeating a command is what a player does when they are not sure
            it took, and "you are already busy" reads as a failure of the
            thing that is in fact working.

            Naming a DIFFERENT node is a real conflict. A channel that
            silently switched targets would make `cut pole` mean "abandon
            whatever I was doing", which is the same quiet substitution
            _choose_yield refuses to make about a cut.

        Notes/References:
            gather_handler.get_gathering_handler.

        Author: Nick Hobar
        Creation date: 09/20/2026
        """
        handler = gather_handler.get_gathering_handler(character)

        if handler is None:
            return False

        if handler.ndb.node_id == target.id:
            character.msg((
                gather_constants.MSG_ALREADY_WORKING.format(node=target.key),
                _MSG_GATHERING,
            ))

            return True

        character.msg((_MSG_BUSY, _MSG_GATHERING))

        return True


    def attempt_swing(self, character: object, target: object,
                      wanted: str = "", rng=None) -> str:
        """
        Purpose: Take one swing at a node, and say whether the channel goes on.

        Entry:
            character is the gatherer.
            target is the live node.
            wanted is the explicit yield choice, or "".
            rng is a random.Random, or None for the module instance. A test
                passes a seeded one, and nothing else does.

        Exit/Returns:
            Returns a STOP_REASON_* value, or "" to keep swinging. A MISSED
            swing returns "" and says nothing -- that is the OSRS rule, and
            it is why the channel announces itself once at the start.

        Module Globals:
            _RNG read when rng is None.

        Methodology:
            The order is: what am I taking, what do I roll on, did it land,
            can I carry it, what does it cost me, does the node give out.

            THE ROLL COMES BEFORE THE BAG CHECK. Rolling first costs nothing
            -- it is arithmetic on two integers -- and it means a full bag
            stops the channel on the swing that would have produced
            something, rather than on a swing that missed anyway. The player
            reads one refusal instead of watching a silent halt.

            THE YIELD IS RE-CHOSEN EVERY SWING. A player who levels up
            mid-channel starts taking the better cut on the next swing, with
            no restart. That is _choose_yield's "levelling changes what
            happens by default" rule, read forwards through a channel. The
            tool is re-read each swing for the same reason: a channel is
            seconds long, and swapping an axe inside one is a thing a player
            can do.

        Notes/References:
            skill_defs/gathering/roll.py owns the maths and touches no
            database at all.

        Author: Nick Hobar
        Creation date: 09/20/2026
        """
        gatherable_def = get_gatherable_for_node(target)

        if gatherable_def is None:
            return gather_constants.STOP_REASON_GONE

        chosen, refusal = self._choose_yield(character, gatherable_def, wanted)

        if chosen is None:
            character.msg((refusal, _MSG_GATHERING))

            return gather_constants.STOP_REASON_LEVELLED_OUT

        tool = self.find_tool(character)
        chance = self._chance_for(gatherable_def, tool)

        if chance is None:
            return gather_constants.STOP_REASON_INTERRUPTED

        draws = rng or _RNG
        level = character.skills.get_level(self.key)
        odds = roll.success_chance(level, chance.low, chance.high)
        landed = roll.rolls_success(odds, draws)

        if not landed:
            return ""

        return self._resolve_success(character, target, gatherable_def,
                                     chosen, tool, draws)


    def _chance_for(self, gatherable_def, tool) -> object:
        """
        Purpose: The low/high pair this swing rolls on.

        Entry:
            gatherable_def is the node's GatherableDef.
            tool is the tool in hand, or None for bare hands.

        Exit/Returns:
            Returns a GatherChance, or None when the node declares no row
            this caller can use. A None is LOGGED and refuses the swing.

        Module Globals:
            None.

        Methodology:
            The tool's TIER is the only thing about it that reaches the roll.
            Cadence is a constant, so a better axe cannot also swing faster
            -- see gather_constants.SWING_TICKS for why one knob and not two.

            `db.tier` is read off the live object rather than off the
            ItemDef, because that is where ItemDef.create stamps it and it is
            the value the item in hand actually carries. A tool with no tier
            reads as 0 and falls to the lowest row the node declares.

            A node with no usable row is a content fault, not a gameplay
            state. It is refused at import (gatherables._chance_faults), so
            reaching this branch means the node was built by something other
            than the registry -- which is worth a log line rather than a
            silent channel that never yields.

        Notes/References:
            GatherableDef.chance_for_tier owns the gap rule.

        Author: Nick Hobar
        Creation date: 09/20/2026
        """
        tool_tier = None

        if tool is not None:
            tool_tier = tool.attributes.get("tier", default=0) or 0

        chance = gatherable_def.chance_for_tier(tool_tier)

        if chance is None:
            logger.log_err(
                f"{type(self).__name__}: {gatherable_def.key} declares no "
                f"chance row for tier {tool_tier!r}."
            )

        return chance


    def _resolve_success(self, character: object, target: object,
                         gatherable_def, chosen, tool, draws) -> str:
        """
        Purpose: Pay for a swing that landed, and decide the node's fate.

        Entry:
            character is the gatherer. target is the node.
            gatherable_def is its GatherableDef. chosen is the yield.
            tool is the tool in hand, or None for bare hands.
            draws is the RNG the depletion roll uses.

        Exit/Returns:
            Returns a STOP_REASON_* value, or "" to keep swinging.

        Module Globals:
            None.

        Methodology:
            THE BARE-HAND COST IS PAID ON SUCCESS, not per swing. That is
            what the opening quest describes -- you tear the chunk loose and
            it tears back -- and it is the only version a level 0 character
            survives: a cost on every attempt at a one-in-six chance kills
            them before the first chunk.

            The cost is paid BEFORE the item, because it can kill. A
            character it killed has already respawned somewhere else, and
            handing them the chunk afterwards describes an afternoon they did
            not have.

            A node the harvest consumed ends the channel QUIETLY. The corpse
            is gone, and the harvest line above already said so.

            Depletion is rolled LAST and only on a swing that produced
            something. A tree falls because you took a log from it, never
            because you missed.

        Notes/References:
            skill_defs/gathering/depletion.py owns the spent state and the
            two refreshes that carry it to a client.

        Author: Nick Hobar
        Creation date: 09/20/2026
        """
        if tool is None:
            survived = self._pay_bare_hand_cost(character, target)

            if not survived:
                return gather_constants.STOP_REASON_INTERRUPTED

        blocked = self._execute_gathering(character, target, gatherable_def,
                                          chosen)

        if blocked:
            return blocked

        if target.pk is None:
            return gather_constants.STOP_REASON_CONSUMED

        depleted = roll.depletes(gatherable_def.deplete_chance, draws)

        if not depleted:
            return ""

        depletion.mark_spent(target, character, gatherable_def.respawn_seconds)

        return gather_constants.STOP_REASON_DEPLETED



    def _not_a_node_message(self, character: object, target: object) -> str:
        """
        Purpose: Explain why the named thing cannot be worked.

        Entry:
            character is the actor, target is whatever they named.

        Exit/Returns:
            Returns the sentence to show them.

        Module Globals:
            None.

        Methodology:
            Uses Evennia's own inheritance check rather than hasattr, so a
            Character is recognised as a person however it was subclassed.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        if target.is_typeclass("typeclasses.characters.Character", exact=False):
            if target.key == character.key:
                return f"You cannot {self.verb} yourself for materials."

            return (
                f"You cannot {self.verb} {target.key} for materials. "
                f"They're a person! Unless.."
            )

        return f"The {target.key} is not something you can {self.verb}."
