"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/20/2026
Description: GatheringHandler -- the per-gatherer channel the global tick
             drives.

A harvest used to be one command and one guaranteed item. It is now a
CHANNEL: the player commits to a node, the server swings at it every
SWING_TICKS ticks, and each swing rolls. The channel ends when the node gives
out, the bag fills, the player walks off, a fight starts, or they say stop.

Why this is a TickableHandler and not a timer
---------------------------------------------
states.py was written with this exact case named in its docstring -- "a
gatherer standing at a node they have not started working" -- because combat,
auras, craft batches and gathering are one shape wearing four sets of nouns.
Reusing the machine means the cadence, the strike policy, the boot sweep and
the `tickdebug` report all already work here, and it means a player cannot be
mid-swing and mid-craft at once without something noticing.

The alternative was a per-player evennia delay loop, which craft_batch.py
still is. That works and it is a SECOND clock beside the tick, with its own
reload behaviour and nothing tying the two together.

What this owns, and what it does not
------------------------------------
This owns CADENCE and the reasons a channel ends that are about the ACTOR:
the node vanished, the player left the room, a fight started, the handler's
owner died.

It does NOT own the roll, the item, the XP, the depletion or any message
about them. Those belong to GatheringSkill, which is the thing a content
author reads. This module never names a skill, a node kind or an item -- it
asks the skill to take one swing and reads back whether to continue.
"""



from evennia.utils import logger

from systems.core.tick import states
from systems.core.tick.tickable import (
    TickableHandler,
    ensure_handler,
    get_handler_for,
    register_tickable,
)
from systems.gameplay.progression.skills.skill_defs.gathering import (
    constants as gather_constants,
)
from systems.interface.statefeed import constants as feed_const



# Every line this module sends a player is gathering, so the routing tag is
# bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/interface/statefeed/constants.py.
_MSG_GATHERING = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_GATHERING}


# Canonical key for the per-gatherer handler. Also what @register_tickable
# files the class under and what the engine's boot sweep queries on.
GATHERING_HANDLER_KEY = "blackout_gathering_handler"



@register_tickable
class GatheringHandler(TickableHandler):
    """One player's channel at one node, advanced by the global tick engine.

    Every field it needs lives on ndb, like every other tickable. A reload
    wipes a channel, which is correct: the player is standing at the node and
    types the verb again.
    """

    HANDLER_KEY = GATHERING_HANDLER_KEY
    ACCESSOR_NAME = "gathering"
    HANDLER_DESC = "Per-gatherer channel state"


    def init_runtime_state(self) -> None:
        """(Re)seed the ndb fields tick() reads.

        Only the counter is seeded. node_id, skill_key and wanted are
        legitimately None while the handler exists and nothing is being
        worked, which is the IDLE state -- seeding them would invent a
        channel nobody started.
        """
        if self.ndb.ticks_until_swing is None:
            self.ndb.ticks_until_swing = 0


    # ── starting and stopping ────────────────────────────────────────────

    def begin(self, skill, node, wanted: str = "") -> bool:
        """
        Purpose: Commit this gatherer to working one node.

        Entry:
            skill is a GatheringSkill instance that has already accepted
                this node, this character and this choice of yield. Every
                refusal happens before this point -- see
                GatheringSkill.execute.
            node is the live node object.
            wanted is the player's explicit yield choice, or "".

        Exit/Returns:
            Returns True when a channel was armed.

        Module Globals:
            None.

        Methodology:
            The first swing is armed for the NEXT tick rather than for a full
            cadence away. A player who types a verb and watches nothing
            happen for two and a half seconds reads it as the command having
            been dropped, and types it again.

            Stores the node by DBREF and the skill by KEY, never the objects.
            An ndb field holding a live script or a live object is a
            reference that outlives the row it names, and the skill instance
            in particular is cheap to rebuild and expensive to keep stale.

        Notes/References:
            CLAUDE.md, "An import path belongs in the code, never in a
            database row" -- the same argument one step down, for a live
            object in a runtime field.

        Author: Nick Hobar
        Creation date: 09/20/2026
        """
        self.init_runtime_state()

        self.ndb.node_id = node.id
        self.ndb.skill_key = skill.key
        self.ndb.wanted = wanted
        self.ndb.ticks_until_swing = 0

        queued = self.dispatch(states.ActivityEvent.ACTION_QUEUED)

        return queued


    def stop_gathering(self, reason: str) -> None:
        """
        Purpose: End this channel, tell the player why, and dismantle.

        Entry:
            reason is one of gather_constants' STOP_REASON_* values.

        Exit/Returns:
            No conditions. Never raises: the engine drops a handler from its
            rotation on any exception, so an error escaping here would leave
            a player unable to gather again until a reload.

        Module Globals:
            gather_constants.STOP_MESSAGES and QUIET_STOP_REASONS read.

        Methodology:
            Announce, then unregister, then delete -- in that order, because
            the node's name is read for the message and this handler is the
            only thing still holding it.

            The teardown mirrors AuraHandler.stop_aura, including the
            accessor-cache pop: lazy_property caches into obj.__dict__ and
            its deleter raises, so a stale entry keeps handing out this
            deleted script for the rest of the session (CLAUDE.md gotcha 7).

        Notes/References:
            systems/gameplay/combat/auras/aura_handler.py stop_aura.

        Author: Nick Hobar
        Creation date: 09/20/2026
        """
        gatherer = self.obj

        if gatherer is not None:
            self._announce_stop(gatherer, reason)
            gatherer.__dict__.pop(self.ACCESSOR_NAME, None)

        try:
            from systems.core.tick.engine import get_tick_engine

            get_tick_engine().unregister(self)
        except Exception as exc:
            logger.log_err(f"GatheringHandler failed to unregister: {exc!r}")

        try:
            self.stop()
        except Exception as exc:
            logger.log_err(f"GatheringHandler failed stop: {exc!r}")

        try:
            self.delete()
        except Exception as exc:
            logger.log_err(f"GatheringHandler failed delete: {exc!r}")


    def _announce_stop(self, gatherer, reason: str) -> None:
        """Say why the channel ended, unless the reason speaks for itself.

        A reason in QUIET_STOP_REASONS sends nothing. Walking away already
        prints a room description, and a second sentence under it telling
        the player they stopped doing the thing they walked away from is
        noise they did not ask for.

        Guarded on its own rather than folded into stop_gathering's blocks,
        which each log a specific failure. A line that cannot be sent has no
        business producing a "handler failed to stop" entry.
        """
        if reason in gather_constants.QUIET_STOP_REASONS:
            return

        template = gather_constants.STOP_MESSAGES.get(reason, "")

        if not template:
            logger.log_err(f"GatheringHandler: undocumented stop reason {reason!r}")
            return

        try:
            node_name = self._node_name()

            gatherer.msg((template.format(node=node_name), _MSG_GATHERING))
        except Exception as exc:
            logger.log_err(f"GatheringHandler._announce_stop failed: {exc!r}")


    def _node_name(self) -> str:
        """The node's key, or a neutral word when it is already gone.

        A stop reason of GONE is reported about a row that no longer loads,
        which is the one case where the name this message wants cannot be
        read. "it" is not elegant and it is better than a traceback inside a
        teardown.
        """
        node = self.node()

        if node is None:
            return "it"

        return str(node.key)


    # ── what the channel is working ──────────────────────────────────────

    def node(self):
        """The live node this channel is working, or None.

        Resolved by dbref on every read rather than cached, because the row
        can be deleted under us -- a corpse is consumed by the swing that
        succeeds on it, and a map rebuild deletes every node in the game.
        """
        node_id = self.ndb.node_id

        if node_id is None:
            return None

        from evennia.objects.models import ObjectDB

        try:
            return ObjectDB.objects.get(id=node_id)
        except ObjectDB.DoesNotExist:
            return None


    def skill(self):
        """A fresh instance of the skill this channel is using, or None.

        Rebuilt per swing from SKILL_REGISTRY. A skill instance holds no
        per-harvest state -- every value it needs arrives as an argument --
        so building one is a class lookup and a constructor, and keeping one
        alive across a reload is a stale object for no gain.
        """
        skill_key = self.ndb.skill_key

        if not skill_key:
            return None

        # Deferred: the registry auto-discovers every skill_defs module, and
        # GatheringSkill imports this one. A module-level import here closes
        # that ring on the third hop.
        from systems.gameplay.progression.skills.registry import SKILL_REGISTRY

        skill_class = SKILL_REGISTRY.get(skill_key)

        if skill_class is None:
            logger.log_err(
                f"GatheringHandler: {skill_key!r} is not in SKILL_REGISTRY.")
            return None

        return skill_class()


    # ── the tick ─────────────────────────────────────────────────────────

    def tick(self) -> None:
        """Advance this channel by one tick.

        Called by the global BlackoutTickEngine's LoopingCall, not by an
        Evennia Script timer -- see systems/core/tick/engine.py for why.

        Every failure path ends the channel rather than raising, for the
        reason AuraHandler.tick does the same: the engine drops a handler on
        an exception, and a channel dropped that way runs forever in the
        player's mind and never again in fact.
        """
        gatherer = self.obj

        if gatherer is None:
            self.stop_gathering(gather_constants.STOP_REASON_GONE)
            return

        # ndb is wiped by a reload; reseed before any read below.
        self.init_runtime_state()

        blocker = self._blocking_reason(gatherer)

        if blocker:
            self.stop_gathering(blocker)
            return

        if self.ndb.ticks_until_swing > 0:
            self.ndb.ticks_until_swing -= 1
            return

        self._swing(gatherer)


    def _blocking_reason(self, gatherer) -> str:
        """
        Purpose: Name the reason this channel cannot continue, if any.

        Entry:
            gatherer is this handler's owner.

        Exit/Returns:
            Returns a STOP_REASON_* value, or "" when the channel may run.

        Module Globals:
            gather_constants' STOP_REASON_* read.

        Methodology:
            Every check here is about the ACTOR or about whether the node is
            still reachable. Nothing here knows what a yield is, what a roll
            is, or what the node produces -- those refusals belong to the
            skill and arrive as a stop reason out of the swing.

            COMBAT IS CHECKED HERE RATHER THAN HOOKED INTO combat.py. The
            channel is already running every 0.6s, so asking costs one
            derived property and the worst latency is one tick. A hook in
            the fight's own start path would be a second place that has to
            know gathering exists, and combat.py has no other reason to.

            Order is cheapest-first and most-certain-first: a dead owner
            cannot be told anything useful about a node, and a node that no
            longer loads cannot be checked for anything else.

        Notes/References:
            Character.at_post_move stops a channel on movement directly, so
            the player is not left swinging at a node in the last room for
            up to a tick.

        Author: Nick Hobar
        Creation date: 09/20/2026
        """
        alive = getattr(gatherer, "is_alive", None)

        if alive is not None and not alive():
            return gather_constants.STOP_REASON_INTERRUPTED

        if getattr(gatherer, "in_combat", False):
            return gather_constants.STOP_REASON_INTERRUPTED

        node = self.node()

        if node is None or node.pk is None:
            return gather_constants.STOP_REASON_GONE

        if node.location is not gatherer.location:
            return gather_constants.STOP_REASON_MOVED

        return ""


    def _swing(self, gatherer) -> None:
        """
        Purpose: Take one swing, and decide whether the channel continues.

        Entry:
            gatherer is this handler's owner, already checked.

        Exit/Returns:
            No conditions.

        Module Globals:
            gather_constants.SWING_TICKS read.

        Methodology:
            The skill does the whole swing: the roll, the item, the XP, the
            quest report, the depletion and every line about them. It hands
            back a stop reason or an empty string, and that is the entire
            contract between a content-shaped module and a state machine.

            The counter is re-armed to SWING_TICKS - 1 rather than
            SWING_TICKS. The swing itself consumes one tick, and assigning
            the full value gives a cadence of SWING_TICKS + 1 -- the same
            off-by-one the aura pulse counter and the weapon-speed counter
            each had to correct.

            The state machine is advanced even though nothing reads it
            between swings yet. It is what makes this handler answer
            `is_busy()` like every other tickable, and it is what a future
            "you cannot craft while gathering" check will read.

        Notes/References:
            GatheringSkill.attempt_swing is the other half of this contract.

        Author: Nick Hobar
        Creation date: 09/20/2026
        """
        skill = self.skill()
        node = self.node()

        if skill is None or node is None:
            self.stop_gathering(gather_constants.STOP_REASON_GONE)
            return

        self.ndb.ticks_until_swing = max(0, gather_constants.SWING_TICKS - 1)

        try:
            stop_reason = skill.attempt_swing(gatherer, node, self.ndb.wanted)
        except Exception as exc:
            logger.log_trace()
            logger.log_err(f"GatheringHandler._swing failed: {exc!r}")
            self.stop_gathering(gather_constants.STOP_REASON_INTERRUPTED)
            return

        self.dispatch(states.ActivityEvent.ACTION_RESOLVED)

        if stop_reason:
            self.stop_gathering(stop_reason)
            return

        self.dispatch(states.ActivityEvent.COOLDOWN_EXPIRED)



def get_gathering_handler(gatherer):
    """Return this character's live channel handler, or None.

    Thin wrapper over the shared lookup so callers outside this package --
    at_post_move, the skill -- name the class in one place.
    """
    handler = get_handler_for(gatherer, GatheringHandler)

    return handler



def start_gathering(gatherer, skill, node, wanted: str = "") -> bool:
    """
    Purpose: Put this character to work on this node.

    Entry:
        gatherer is a Character. skill is a GatheringSkill instance that has
        already accepted the attempt. node is the live node. wanted is the
        explicit yield choice, or "".

    Exit/Returns:
        Returns True when a channel is running.

    Module Globals:
        None.

    Methodology:
        ensure_handler finds or creates, arms the script and registers it
        with the tick engine -- all of which was written twice before
        TickableHandler existed. Nothing here repeats it.

    Notes/References:
        systems/core/tick/tickable.py ensure_handler.

    Author: Nick Hobar
    Creation date: 09/20/2026
    """
    handler = ensure_handler(gatherer, GatheringHandler)

    if handler is None:
        return False

    started = handler.begin(skill, node, wanted)

    return started



def stop_gathering(gatherer, reason: str) -> bool:
    """
    Purpose: End this character's channel, if they have one.

    Entry:
        gatherer is any object. One that has never gathered is the common
        case and a supported no-op.
        reason is a STOP_REASON_* value.

    Exit/Returns:
        Returns True when a channel was actually stopped.

    Module Globals:
        None.

    Methodology:
        The one entry point every outside caller uses -- movement, a `stop`
        command, a future interrupt. Callers do not reach the handler
        themselves, so the teardown order stays in one place.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/20/2026
    """
    handler = get_gathering_handler(gatherer)

    if handler is None:
        return False

    handler.stop_gathering(reason)

    return True
