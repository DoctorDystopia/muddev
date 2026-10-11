"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: ExterminatorHandler, one character's task, streak, and points.

             The one reader and the one writer of the three Exterminator
             Attributes. The `task` command, the kill hook, the dialogue, and
             the task pop-up all go through this class. QuestHandler owns
             db.active_quests by the same rule (CLAUDE.md, "The quest
             system").

             Every public write marks the open pop-up stale, so the task
             pop-up follows its facts (CLAUDE.md, "Every pane follows its
             facts"). DESIGN-0012, Phase 2.
"""

import functools
import math
import random
import time

from evennia.utils import logger

from systems.gameplay.exterminator import constants
from systems.gameplay.exterminator.preceptors import PRECEPTOR_DB, assignment_for
from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills import xp_awards
from systems.interface.statefeed import constants as feed_const
from world.creature_types import CREATURE_TYPES



# Every line this module sends is about skill progress.
_MSG_PROGRESSION = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_PROGRESSION}

# The default source of chance. A test passes a seeded random.Random.
_DEFAULT_RNG = random.Random()



# ─── Private helper routines ────────────────────────────────────────────────

def _publishes(method):
    """
    Purpose: Mark the open pop-up stale after a method that wrote the task.

    Entry:
        method is an unbound ExterminatorHandler method that writes one of
        the three Exterminator Attributes.

    Exit/Returns:
        Returns the wrapped method. It returns what the original returns.

    Module Globals:
        None.

    Methodology:
        One marker on each public write, as `_publishes` in the quest
        handler does. The mark is cheap: refresh_popup reads one ndb
        attribute and stops when no pop-up is open. The statefeed builds the
        snapshot one time, after the last change.

        The import is inside the wrapper. typeclasses/characters.py imports
        this module at startup, and the statefeed events module reaches the
        payload builders.

    Notes/References:
        The task pop-up is systems/interface/popups/popup_defs/exterminator.py.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        result = method(self, *args, **kwargs)

        from systems.interface.statefeed import events as _feed

        _feed.refresh_popup(self.obj)

        return result

    return wrapper


def streak_multiplier(streak: int) -> int:
    """
    Purpose: Give the points multiplier for a streak.

    Entry:
        streak >= 0. It is the streak after the completed task counts.

    Exit/Returns:
        Returns the multiplier of the highest streak milestone that divides
        the streak. Returns STREAK_BASE_MULTIPLIER if none divides it, or if
        the streak is 0.

    Module Globals:
        constants.STREAK_MULTIPLIERS, constants.STREAK_BASE_MULTIPLIER read.

    Methodology:
        STREAK_MULTIPLIERS is highest first, so the first match is the
        highest. Only one multiplier applies (Nick, 10/06/2026).

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """
    if streak <= 0:
        return constants.STREAK_BASE_MULTIPLIER

    for milestone, multiplier in constants.STREAK_MULTIPLIERS:
        if streak % milestone == 0:
            return multiplier

    return constants.STREAK_BASE_MULTIPLIER



# ─── Public classes ─────────────────────────────────────────────────────────

class ExterminatorHandler:
    """
    Purpose: One character's Exterminator task, streak, and points.

    Entry:
        obj is the Character that this handler belongs to.

    Exit/Returns:
        No conditions.

    Module Globals:
        PRECEPTOR_DB, CREATURE_TYPES read.

    Methodology:
        The task is one Attribute: a dict with the FIELD_* keys, or None. The
        streak and the points are two more Attributes. The read API gives
        copies and plain values, so no caller can change a stored dict.

    Notes/References:
        Reached as `character.exterminator`, a lazy_property that
        typeclasses/characters.py builds.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """

    def __init__(self, obj: object) -> None:
        self.obj = obj


    # ─── Read API ───────────────────────────────────────────────────────────

    def _task(self):
        """The stored task dict, or None. Private: callers get a copy."""
        task = self.obj.attributes.get(constants.TASK_ATTR, default=None)

        return task or None


    def has_task(self) -> bool:
        """Say whether the character has a task."""
        task = self._task()

        return task is not None


    def task(self):
        """Give a copy of the task dict, or None when there is no task."""
        task = self._task()

        if task is None:
            return None

        return dict(task)


    def creature_type(self) -> str:
        """The creature type key of the task, or "" when there is no task."""
        task = self._task() or {}

        return str(task.get(constants.FIELD_CREATURE_TYPE, ""))


    def kills(self) -> int:
        """The task kills so far, or 0 when there is no task."""
        task = self._task() or {}

        return int(task.get(constants.FIELD_KILLS, 0))


    def total(self) -> int:
        """The kills that the task needs, or 0 when there is no task."""
        task = self._task() or {}

        return int(task.get(constants.FIELD_TOTAL, 0))


    def streak(self) -> int:
        """The count of tasks completed in a row."""
        streak = self.obj.attributes.get(constants.STREAK_ATTR, default=0)

        return int(streak or 0)


    def points(self) -> int:
        """The Exterminator points of the character."""
        points = self.obj.attributes.get(constants.POINTS_ATTR, default=0)

        return int(points or 0)


    def _held_cards(self) -> list:
        """The held buffs as card dicts. Private: callers get keys or copies."""
        task = self._task() or {}

        return list(task.get(constants.FIELD_BUFFS) or [])


    def held_buffs(self) -> tuple:
        """The buff keys of the task, in pick order. Empty with no task."""
        cards = self._held_cards()

        return tuple(card[constants.CARD_KEY] for card in cards)


    def buff_rarity(self, buff_key: str):
        """The rarity of one held buff, or None when the task does not hold it."""
        for card in self._held_cards():
            if card[constants.CARD_KEY] == buff_key:
                return card[constants.CARD_RARITY]

        return None


    def banked_picks(self) -> int:
        """The picks that came due and wait for the player. 0 with no task."""
        task = self._task() or {}

        return int(task.get(constants.FIELD_BANKED_PICKS, 0))


    def preceptor_key(self):
        """The key of the Preceptor of the task, or None with no task."""
        task = self._task() or {}

        return task.get(constants.FIELD_PRECEPTOR)


    def picks_earned(self) -> int:
        """The pick milestones that the task passed so far. 0 with no task."""
        task = self._task() or {}

        return int(task.get(constants.FIELD_PICKS_EARNED, 0))


    def _playtime(self) -> int:
        """The online seconds of the character. typeclasses/characters.py owns them."""
        playtime = getattr(self.obj, "playtime_seconds", 0)

        return int(playtime or 0)


    def elapsed_seconds(self) -> int:
        """
        The online seconds since the assignment, or 0 with no task. The
        clock stops at logout (Nick, 10/07/2026), because playtime_seconds
        counts online time only.
        """
        task = self._task()

        if task is None:
            return 0

        started = int(task.get(constants.FIELD_PLAYTIME_AT_START, 0))

        return max(self._playtime() - started, 0)


    def par_seconds(self) -> int:
        """
        The par time of the task: its total kills times the seconds per kill
        of its creature type. 0 with no task. A type that the Preceptor no
        longer lists uses DEFAULT_PAR_SECONDS_PER_KILL.
        """
        if not self.has_task():
            return 0

        assignment = assignment_for(self.preceptor_key(), self.creature_type())
        per_kill = constants.DEFAULT_PAR_SECONDS_PER_KILL

        if assignment is not None:
            per_kill = assignment.par_seconds_per_kill

        return self.total() * per_kill


    def offer(self) -> list:
        """A copy of the cards of the open offer. Empty when none is open."""
        task = self._task() or {}
        cards = task.get(constants.FIELD_OFFER) or []

        return [dict(card) for card in cards]


    def pick_milestone_count(self) -> int:
        """
        The count of pick milestones in a task of this character. The one
        reader of PICK_MILESTONE_COUNT, so a permanent upgrade can add to it
        here later.
        """
        return constants.PICK_MILESTONE_COUNT


    def cards_per_offer(self) -> int:
        """The cards in one offer. The one reader of CARDS_PER_OFFER."""
        return constants.CARDS_PER_OFFER


    def counts_kill_of(self, victim_types) -> bool:
        """Say whether a victim with these creature types counts on the task."""
        task_type = self.creature_type()

        return bool(task_type) and task_type in victim_types


    def summary_lines(self) -> list:
        """
        Purpose: Give the task as lines of text, for `task` and the pop-up.

        Entry:
            No conditions.

        Exit/Returns:
            Returns a list of plain strings. The first line is the task, or
            MSG_NO_TASK. The last line is the streak and the points.

        Module Globals:
            CREATURE_TYPES, constants.MSG_* read.

        Methodology:
            1. If there is no task, give MSG_NO_TASK.
            2. Else, give the task line with the plural of the creature type.
            3. Add the streak line.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 10/06/2026
        """
        lines = []

        if self.has_task():
            plural = self._plural()
            task_line = constants.MSG_TASK_LINE.format(
                total=self.total(), plural=plural, kills=self.kills())
            lines.append(task_line)
        else:
            lines.append(constants.MSG_NO_TASK)

        held_line = self._held_buffs_line()

        if held_line:
            lines.append(held_line)

        banked = self.banked_picks()

        if banked > 0:
            picks_line = constants.MSG_PICKS_LINE.format(banked=banked)
            lines.append(picks_line)

        streak_line = constants.MSG_STREAK_LINE.format(
            streak=self.streak(), points=self.points())
        lines.append(streak_line)

        return lines


    def _held_buffs_line(self) -> str:
        """
        One line that names each held buff and its rarity, or "" when the
        task holds none. A key that is not in the registry shows as the key.
        """
        from systems.gameplay.exterminator.buffs import BUFF_REGISTRY, buff_name

        parts = []

        for card in self._held_cards():
            buff_key = card[constants.CARD_KEY]
            rarity = card[constants.CARD_RARITY]
            buff = BUFF_REGISTRY.get(buff_key)
            name = buff_name(buff, self.preceptor_key()) if buff is not None else buff_key
            rarity_name = constants.RARITY_NAMES.get(rarity, rarity)
            parts.append(constants.MSG_HELD_BUFF.format(name=name, rarity=rarity_name))

        if not parts:
            return ""

        joined = constants.HELD_BUFF_SEPARATOR.join(parts)

        return constants.MSG_HELD_BUFFS_LINE.format(buffs=joined)


    def _plural(self) -> str:
        """The plural display name of the task type, or the raw key."""
        type_key = self.creature_type()
        row = CREATURE_TYPES.get(type_key)

        if row is None:
            return type_key

        return row.plural


    # ─── Write API ──────────────────────────────────────────────────────────

    @_publishes
    def assign(self, preceptor_key: str, rng=None) -> tuple:
        """
        Purpose: Take a new task from one Preceptor.

        Entry:
            preceptor_key is a key of PRECEPTOR_DB.
            rng is a random.Random, or None for the module default.

        Exit/Returns:
            Returns (assigned, message). `assigned` is True when the task
            was written. `message` is the line for the player.

        Module Globals:
            PRECEPTOR_DB read. constants.TASK_ATTR written.

        Methodology:
            1. If the character has a task, refuse (one task at a time).
            2. If the Preceptor is unknown, refuse and log.
            3. If the Exterminator level is below the Preceptor level, refuse.
            4. Draw one creature type that the level allows, by weight.
            5. Draw the size from the range of that type, and write the task.

        Notes/References:
            Nick, 10/06/2026: one task at a time, a level for each type.

        Author: Nick Hobar
        Creation date: 10/06/2026
        """
        if self.has_task():
            return False, constants.MSG_ALREADY_HAS_TASK

        preceptor = PRECEPTOR_DB.get(preceptor_key)

        if preceptor is None:
            logger.log_err(f"ExterminatorHandler.assign: no Preceptor {preceptor_key!r}.")
            return False, constants.MSG_NO_PRECEPTOR_HERE

        level = self.obj.skills.get_level(skill_constants.SKILL_KEY_EXTERMINATOR)

        if level < preceptor.required_level:
            refusal = constants.MSG_PRECEPTOR_LEVEL_TOO_LOW.format(
                preceptor=preceptor.name, level=preceptor.required_level)
            return False, refusal

        source = rng or _DEFAULT_RNG
        assignment = self._draw_assignment(preceptor, level, source)

        if assignment is None:
            refusal = constants.MSG_NO_TASK_FOR_LEVEL.format(preceptor=preceptor.name)
            return False, refusal

        total = source.randint(assignment.min_size, assignment.max_size)
        self._write_task(preceptor.key, assignment.creature_type, total)
        self._sync_picks(source, announce=False)
        plural = self._plural()

        message = constants.MSG_TASK_ASSIGNED.format(
            preceptor=preceptor.name, total=total, plural=plural)

        if self.banked_picks() > 0:
            message = f"{message}\n{constants.MSG_PICK_EARNED}"

        return True, message


    def _draw_assignment(self, preceptor, level: int, rng):
        """
        Purpose: Draw one Assignment of a Preceptor that the level allows.

        Entry:
            preceptor is a PreceptorDef. level >= 0. rng is a random.Random.

        Exit/Returns:
            Returns one Assignment, or None if the level allows none.

        Module Globals:
            CREATURE_TYPES read.

        Methodology:
            1. Keep each Assignment whose type level is at or below `level`.
               Skip a type with no row, and log it.
            2. If none is left, return None.
            3. Else, draw one by weight.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 10/06/2026
        """
        allowed = []

        for assignment in preceptor.assignments:
            row = CREATURE_TYPES.get(assignment.creature_type)

            if row is None:
                logger.log_err(
                    f"Preceptor {preceptor.key!r} names unknown creature type "
                    f"{assignment.creature_type!r}.")
                continue

            if row.required_level <= level:
                allowed.append(assignment)

        if not allowed:
            return None

        weights = [assignment.weight for assignment in allowed]
        drawn = rng.choices(allowed, weights=weights)

        return drawn[0]


    def _write_task(self, preceptor_key: str, creature_type: str, total: int) -> None:
        """Write a fresh task dict. Private: assign is the one caller."""
        task = {
            constants.FIELD_PRECEPTOR: preceptor_key,
            constants.FIELD_CREATURE_TYPE: creature_type,
            constants.FIELD_TOTAL: int(total),
            constants.FIELD_KILLS: 0,
            constants.FIELD_STARTED_AT: time.time(),
            constants.FIELD_BUFFS: [],
            constants.FIELD_PICKS_EARNED: 0,
            constants.FIELD_BANKED_PICKS: 0,
            constants.FIELD_OFFER: None,
            constants.FIELD_PLAYTIME_AT_START: self._playtime(),
        }
        self.obj.attributes.add(constants.TASK_ATTR, task)


    @_publishes
    def record_kill(self, victim_types, xp: int, rng=None) -> bool:
        """
        Purpose: Count one task kill, pay its XP, and finish the task at the
                 last kill.

        Entry:
            victim_types is the tuple of creature types of the victim.
            xp >= 0. It is the share of this character.
            rng is a random.Random for an offer, or None for the default.

        Exit/Returns:
            Returns True when the kill counted. False when the character has
            no task, or the victim is not of the task type.

        Module Globals:
            constants.TASK_ATTR written.

        Methodology:
            1. If the kill does not count, return False.
            2. Add one kill and write the task.
            3. Send the progress line with the XP readout, then grant the XP.
               That order puts a level-up line under the award.
            4. If the kills reach the total, complete the task. A banked
               pick is lost then (Nick, 10/06/2026).
            5. Else, bank each pick milestone that came due.

        Notes/References:
            Nick, 10/06/2026: each damage dealer gets one kill, and the XP
            is shared by damage. hooks.notify_exterminator works out the
            share. XP comes only from a task kill.

        Author: Nick Hobar
        Creation date: 10/06/2026
        """
        counts = self.counts_kill_of(victim_types)

        if not counts:
            return False

        task = dict(self._task())
        task[constants.FIELD_KILLS] = int(task.get(constants.FIELD_KILLS, 0)) + 1
        self.obj.attributes.add(constants.TASK_ATTR, task)

        awards = [(skill_constants.SKILL_KEY_EXTERMINATOR, int(xp))]
        progress = constants.MSG_TASK_KILL.format(
            kills=self.kills(), total=self.total(), plural=self._plural())
        suffix = xp_awards.format_xp_suffix(awards)
        self.obj.msg((progress + suffix, _MSG_PROGRESSION))
        xp_awards.grant_xp(self.obj, awards, feed_const.MESSAGE_TYPE_PROGRESSION)

        if self.kills() >= self.total():
            self._complete()
            return True

        self._sync_picks(rng or _DEFAULT_RNG)

        return True


    def _sync_picks(self, rng, announce: bool = True) -> None:
        """
        Purpose: Bank each pick milestone that the task progress passed, and
                 open an offer when a pick waits.

        Entry:
            The character has a task. rng is a random.Random.
            announce is False when the caller tells the player itself.

        Exit/Returns:
            No return value. Writes the task when a milestone came due or an
            offer opened.

        Module Globals:
            constants.TASK_ATTR written.

        Methodology:
            1. Count the milestones due now (offers.picks_due).
            2. Bank the new ones. Kills still count while a pick waits.
            3. If a pick waits and no offer is open, draw one.

        Notes/References:
            Private: assign, record_kill, and pick call it, and each one
            publishes. An MMO cannot pause the world, so the picks wait in
            a bank.

        Author: Nick Hobar
        Creation date: 10/06/2026
        """
        from systems.gameplay.exterminator import offers

        task = dict(self._task())
        due = offers.picks_due(self.kills(), self.total(), self.pick_milestone_count())
        earned = int(task.get(constants.FIELD_PICKS_EARNED, 0))

        if due > earned:
            task[constants.FIELD_PICKS_EARNED] = due
            task[constants.FIELD_BANKED_PICKS] = self.banked_picks() + due - earned
            self.obj.attributes.add(constants.TASK_ATTR, task)

            if announce:
                self.obj.msg((constants.MSG_PICK_EARNED, _MSG_PROGRESSION))

        self._ensure_offer(rng)


    def _ensure_offer(self, rng) -> None:
        """
        Purpose: Draw an offer when a pick waits and none is open.

        Entry:
            The character has a task. rng is a random.Random.

        Exit/Returns:
            No return value. Writes the offer, which can be empty.

        Module Globals:
            PRECEPTOR_DB read. constants.TASK_ATTR written.

        Methodology:
            1. If no pick waits, or an offer is open, stop.
            2. Draw the cards from the pool of the Preceptor of the task.
            3. Write them. An empty draw stores None, so a later pool can
               offer cards. The pick still waits.

        Notes/References:
            The offer is stored, so the pop-up, the text, and the menu all
            show the same cards until the player picks.

        Author: Nick Hobar
        Creation date: 10/06/2026
        """
        from systems.gameplay.exterminator import offers
        from systems.gameplay.exterminator.buffs import BUFF_REGISTRY

        if self.banked_picks() <= 0 or self.offer():
            return

        task = dict(self._task())
        preceptor = PRECEPTOR_DB.get(task.get(constants.FIELD_PRECEPTOR))
        pool = preceptor.buff_pool if preceptor is not None else ()

        cards = offers.draw_offer(
            pool, self.held_buffs(), self.cards_per_offer(), BUFF_REGISTRY, rng)
        task[constants.FIELD_OFFER] = cards or None
        self.obj.attributes.add(constants.TASK_ATTR, task)


    def _complete(self) -> None:
        """
        Purpose: End a finished task, and pay its points.

        Entry:
            The character has a task, and its kills reach its total.

        Exit/Returns:
            No return value. Clears the task. Writes the streak and the points.

        Module Globals:
            PRECEPTOR_DB read. constants.TASK_ATTR, STREAK_ATTR, POINTS_ATTR
            written.

        Methodology:
            1. Add one to the streak.
            2. Pay the base points of the Preceptor times the streak multiplier.
            3. Add the points bonus of the held buffs. Ask the buffs BEFORE
               the task is cleared, because a buff reads the task.
            4. Clear the task, and tell the player.
            5. Send the task-complete moment. The client plays its sound.

        Notes/References:
            Private: record_kill is the one caller, and it publishes. The
            statefeed import is local for the reason that _publishes gives.

        Author: Nick Hobar
        Creation date: 10/06/2026
        """
        task = self._task()
        preceptor = PRECEPTOR_DB.get(task.get(constants.FIELD_PRECEPTOR))
        base_points = preceptor.base_points if preceptor is not None else 0

        streak = self.streak() + 1
        multiplier = streak_multiplier(streak)
        payout = base_points * multiplier
        bonus = self._points_bonus(payout)
        earned = payout + bonus
        total = self.total()
        plural = self._plural()

        self.obj.attributes.add(constants.STREAK_ATTR, streak)
        self.obj.attributes.add(constants.POINTS_ATTR, self.points() + earned)
        self.obj.attributes.add(constants.TASK_ATTR, None)

        message = constants.MSG_TASK_COMPLETE.format(
            total=total, plural=plural, points=earned, streak=streak)

        if bonus > 0:
            bonus_line = constants.MSG_POINTS_BONUS.format(bonus=bonus)
            message = f"{message}\n{bonus_line}"

        self.obj.msg((message, _MSG_PROGRESSION))

        from systems.interface.statefeed import events as _feed

        _feed.emit_moment(self.obj, feed_const.MOMENT_TASK_COMPLETE)


    def _points_bonus(self, payout: int) -> int:
        """
        Purpose: Give the extra points that the held buffs add to one payout.

        Entry:
            The character has a task. payout >= 0: the base points times the
            streak multiplier.

        Exit/Returns:
            Returns the extra points, floored. 0 when no buff adds any.

        Module Globals:
            BUFF_REGISTRY read.

        Methodology:
            Each held buff gives a fraction (points_bonus). The fractions
            add, as two +10% modifiers do in combat. The sum scales the whole
            payout, streak multiplier included: "+50% points" means 50% more
            than the task gives.

        Notes/References:
            Private: _complete is the one caller. A key that is not in the
            registry adds nothing.

        Author: Nick Hobar
        Creation date: 10/07/2026
        """
        from systems.gameplay.exterminator.buffs import BUFF_REGISTRY

        fraction = 0.0

        for buff_key in self.held_buffs():
            buff = BUFF_REGISTRY.get(buff_key)

            if buff is not None:
                fraction += buff.points_bonus(self.obj)

        return math.floor(payout * fraction)


    @_publishes
    def grant_buff(self, buff_key: str, rarity: str = constants.RARITY_COMMON) -> tuple:
        """
        Purpose: Add one buff to the task.

        Entry:
            buff_key is a key of BUFF_REGISTRY.
            rarity is one of constants.RARITIES. It sets the strength.

        Exit/Returns:
            Returns (granted, message).

        Module Globals:
            BUFF_REGISTRY read. constants.TASK_ATTR written.

        Methodology:
            1. If there is no task, refuse. A buff lives on the task.
            2. If the key is unknown, refuse.
            3. If the task holds the buff, refuse.
            4. Else, append the key and the rarity, and write the task.

        Notes/References:
            The one write path of the held buffs. The pick of Phase 4 calls
            it. A test and a staff tool can call it too. The buffs end with
            the task, because they live in the task dict (Nick, 10/06/2026).
            The registry import is local, because the buff registry imports
            the combat rules package.

        Author: Nick Hobar
        Creation date: 10/06/2026
        """
        return self._add_buff(buff_key, rarity)


    def _add_buff(self, buff_key: str, rarity: str) -> tuple:
        """The body of grant_buff, with no publish. pick calls it too."""
        from systems.gameplay.exterminator.buffs import BUFF_REGISTRY, buff_name

        if not self.has_task():
            return False, constants.MSG_BUFF_NEEDS_TASK

        buff = BUFF_REGISTRY.get(buff_key)

        if buff is None:
            return False, constants.MSG_BUFF_UNKNOWN.format(buff=buff_key)

        held = self.held_buffs()
        name = buff_name(buff, self.preceptor_key())

        if buff_key in held:
            return False, constants.MSG_BUFF_ALREADY_HELD.format(buff=name)

        card = {constants.CARD_KEY: buff_key, constants.CARD_RARITY: rarity}
        task = dict(self._task())
        task[constants.FIELD_BUFFS] = self._held_cards() + [card]
        self.obj.attributes.add(constants.TASK_ATTR, task)

        return True, constants.MSG_BUFF_GAINED.format(buff=name)


    @_publishes
    def pick(self, card_number: int, rng=None) -> tuple:
        """
        Purpose: Take one card of the open offer, and use one banked pick.

        Entry:
            card_number is the 1-based number of a card in the offer.
            rng is a random.Random for the next offer, or None.

        Exit/Returns:
            Returns (picked, message).

        Module Globals:
            constants.TASK_ATTR written.

        Methodology:
            1. If no pick waits, refuse.
            2. If no offer is open, or the number is not a card, refuse.
            3. Grant the buff of the card, with the rarity of the card.
            4. Use one banked pick, and close the offer.
            5. If a pick still waits, draw the next offer.

        Notes/References:
            `task pick <n>`, the pop-up card, and the pick menu all call this.

        Author: Nick Hobar
        Creation date: 10/06/2026
        """
        if self.banked_picks() <= 0:
            return False, constants.MSG_NO_PICK

        cards = self.offer()

        if not cards:
            return False, constants.MSG_NO_CARDS

        if card_number < 1 or card_number > len(cards):
            return False, constants.MSG_BAD_CARD.format(count=len(cards))

        card = cards[card_number - 1]
        granted, message = self._add_buff(card[constants.CARD_KEY], card[constants.CARD_RARITY])

        if not granted:
            return False, message

        task = dict(self._task())
        task[constants.FIELD_BANKED_PICKS] = self.banked_picks() - 1
        task[constants.FIELD_OFFER] = None
        self.obj.attributes.add(constants.TASK_ATTR, task)
        self._ensure_offer(rng or _DEFAULT_RNG)

        return True, message


    @_publishes
    def skip(self) -> tuple:
        """
        Purpose: Drop the task for points. A skip ends the streak.

        Entry:
            No conditions.

        Exit/Returns:
            Returns (skipped, message).

        Module Globals:
            constants.SKIP_COST_POINTS read. constants.TASK_ATTR,
            STREAK_ATTR, POINTS_ATTR written.

        Methodology:
            1. If there is no task, refuse.
            2. If the points are below the cost, refuse.
            3. Pay the cost, end the streak, and clear the task.

        Notes/References:
            Nick, 10/06/2026: a skip costs points, a player with too few
            points cannot skip, and a skip breaks the streak.

        Author: Nick Hobar
        Creation date: 10/06/2026
        """
        if not self.has_task():
            return False, constants.MSG_NO_TASK

        cost = constants.SKIP_COST_POINTS
        points = self.points()

        if points < cost:
            refusal = constants.MSG_SKIP_TOO_FEW_POINTS.format(cost=cost, points=points)
            return False, refusal

        self.obj.attributes.add(constants.POINTS_ATTR, points - cost)
        self.obj.attributes.add(constants.STREAK_ATTR, 0)
        self.obj.attributes.add(constants.TASK_ATTR, None)

        message = constants.MSG_TASK_SKIPPED.format(cost=cost)

        return True, message
