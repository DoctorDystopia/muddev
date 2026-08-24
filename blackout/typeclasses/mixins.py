"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: CombatEntity mixin —_HP, death, and disconnect hooks for any combatant.
"""

from evennia.utils import logger, lazy_property

from systems.ai.constants import LAST_ATTACKER_ID_ATTR
from systems.combat import constants as combat_constants
from systems.combat import combat_msg
from systems.combat.combat_level.logic import get_combat_level
from systems.combat.protocols import XpEarner
from systems.statefeed import events as feed

from systems.stat_tracker import constants as stat_constants


class CombatEntity:
    """
    Purpose: Generic combat-state mixin. Adds HP, alive-state, damage, and
    death hooks to any Evennia Typeclass that inherits it.

    Methodology:
        Lives entirely off `self.db` attribute access — matches the
        existing Blackout convention (`self.db.skills`, `self.db.active_quests`)
        rather than introducing AttributeProperty only for combat stats, so
        the codebase only has ONE attribute-access pattern.

        The mixin is typeclass-agnostic: it works equally for a player
        Character or a HostileNPC. Any combatant-specific divergence
        (quest updates, respawn location) is gated by `getattr(..., None)`
        probes, not by isinstance checks.

    Notes/References:
        Research doc §"Translating Game State to Evennia: Data Persistence".
        Style guide §7.0 module layout (imports → constants → public class).

    Author: Nick Hobar
    Creation date: 07/26/2026
    """

    # ─── HP lifecycle ───────────────────────────────────────────────────────

    def init_combat_attrs(self, max_hp: int = None) -> None:
        """
        Purpose: Sets the combat-related db attributes on this entity. Called
        from the host typeclass's at_object_creation once fortitude seeding
        has happened (for players) or combat_stats are loaded (for NPCs).

        Entry:
            self.db is available (CombatEntity lives on an Evennia Typeclass).
            max_hp - optional override; if None, defers to db.max_hp if set
                     or falls back to FORTITUDE_START_LEVEL (10).

        Exit/Returns:
            No conditions. After this call, self.db.hp and self.db.max_hp are
            guaranteed to exist. in_combat is NOT seeded -- it is a derived
            property now (see below), not an Attribute.

        Module Globals:
            combat_constants.FORTITUDE_START_LEVEL read as the default floor.

        Methodology:
            We do NOT stamp CombatEntity attributes at import time; the host
            typeclass must call this explicitly so that both Player seeding
            (post-init_all_skills) and NPC seeding (from combat_stats) share
            the one well-defined entry point.

        Notes/References:
            db.* access is the codebase convention per characters.py:188.

        Author: Nick Hobar
        Creation date: 07/26/2026
        """
        if max_hp is None:
            max_hp = self.db.max_hp or combat_constants.FORTITUDE_START_LEVEL

        self.db.max_hp = max_hp
        self.db.hp = max_hp


    @property
    def hp(self) -> int:
        """
        Purpose: Read-only-ish accessor for current HP. Hides the raw db
        access so combat code can read combatant.hp without knowing the
        storage key.

        Entry:
            None.

        Exit/Returns:
            Integer HP. Defaults to 0 if attributes uninitialized (rare;
            defensive).

        Module Globals:
            None.

        Methodology:
            Prefer an explicit @property over a db-style attribute so the
            combat handler can call `attacker.hp` without leaking the
            implementation detail that the attribute is named "hp".

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 07/26/2026
        """
        return self.db.hp or 0


    @hp.setter
    def hp(self, value: int) -> None:
        """
        Purpose: Setter enforcing 0 <= value <= max_hp.

        Entry:
            value - integer HP to set. Negative is clamped to 0; over max_hp
                    clamps to max_hp.

        Exit/Returns:
            No conditions.

        Module Globals:
            None.

        Methodology:
            Clamp + assign. If max_hp is None (defensive — uninitialized
            entity), treat as no upper bound.

            The state-feed publish rides here rather than in at_damage because
            this setter is the single choke point every HP change passes
            through -- damage, healing, and respawn alike. Publishing from
            at_damage would leave a graphical client's health bar stale through
            a heal. The feed's own per-channel rate cap is what makes it safe
            to publish this liberally.

            Passive regen registration rides here for the same reason: it is
            the one place that sees every HP-reducing event, combat or
            otherwise, and regen runs ALL the time (not gated on in_combat) --
            see hp_regen.py.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 07/26/2026
        """
        if value < 0:
            value = 0
        max_hp = self.db.max_hp
        if max_hp is not None and value > max_hp:
            value = max_hp
        self.db.hp = value

        feed.emit_vitals(self)

        if max_hp is not None and value < max_hp:
            try:
                from systems.combat.hp_regen import register_for_regen

                register_for_regen(self)
            except Exception as exc:
                logger.log_err(f"CombatEntity.hp setter regen registration failed: {exc!r}")


    @property
    def max_hp(self) -> int:
        """
        Purpose: Accessor for maximum HP.

        Entry:
            None.

        Exit/Returns:
            Integer max_hp or 0 if uninitialized.

        Module Globals:
            combat_constants.FORTITUDE_START_LEVEL is NOT read here; the
            caller is expected to have called init_combat_attrs first.

        Methodology:
            Plain db read.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 07/26/2026
        """
        return self.db.max_hp or 0


    @property
    def combat_level(self) -> int:
        """
        Purpose: Accessor for this combatant's derived combat level.

        Entry:
            self exposes a `skills` handler (Character's SkillHandler, or
            HostileNPC's StatBlockSkills) -- true for every CombatEntity host
            today.

        Exit/Returns:
            Integer combat level.

        Module Globals:
            None.

        Methodology:
            Delegates to systems.combat.combat_level.logic.get_combat_level,
            which is a pure function of skill levels rather than persisted
            state -- there is no db.combat_level to keep in sync, so this
            property is always current, the same tradeoff hp/max_hp make in
            the other direction (persisted because damage must survive a
            reload; combat level is cheap enough to recompute every read).

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        return get_combat_level(self)


    def is_alive(self) -> bool:
        """
        Purpose: Generic alive check used by combat handlers, AI, etc.

        Entry:
            None.

        Exit/Returns:
            True iff hp > 0.

        Module Globals:
            None.

        Methodology:
            Avoid `isinstance(killer, Character)`. A living entity is one
            with positive HP. The mixin's storage is db.hp, so the check is
            one db read.

        Author: Nick Hobar
        Creation date: 07/26/2026
        """
        return self.hp > 0

    # ─── Damage & death hooks ──────────────────────────────────────────────

    def at_damage(self, amount: int, attacker=None, source=None,
                  damage_type=None) -> int:
        """
        Purpose: Apply incoming damage to this entity, returning the actual
        amount of HP lost (post-clamp). Triggers death handling when HP
        crosses zero.

        Entry:
            amount      - integer damage dealt. Must be >= 0.
            attacker    - optional CombatEntity that caused the damage. Used
                          for death broadcast and killer-side XP / quest
                          hooks. Pass the TRUTH here, including `self` for
                          self-inflicted damage; at_death normalises it.
            source      - optional object responsible: the weapon, the gadget,
                          the aura instance. Distinct from `attacker`, which
                          is always an entity.
            damage_type - optional DAMAGE_TYPE_* constant. None is treated as
                          untyped, not as melee, so a caller that forgets is
                          visible rather than silently mislabelled.

        Exit/Returns:
            Integer HP actually removed. Always >= 0; never exceeds the
            entity's pre-damage HP (no over-kill).

        Module Globals:
            None.

        Methodology:
            1. Snapshot old HP.
            2. Clamp amount down to old HP (no negative HP stored).
            3. Assign new HP via self.hp = old_hp - amount (also clamps high).
            4. If new HP is 0 and old HP was > 0, call at_death.
            5. Return the delta.

            `source` and `damage_type` are keyword-only in practice and both
            default to None, so every pre-existing two-argument call site
            keeps working unchanged.

        Notes/References:
            Per design dialogue: research doc §"Translating Game State".

        Author: Nick Hobar
        Creation date: 07/26/2026
        """
        if amount < 0:
            amount = 0

        self._record_attacker(attacker)

        old_hp = self.hp
        delta = min(amount, old_hp)
        new_hp = old_hp - delta
        self.hp = new_hp

        if old_hp > 0 and new_hp == 0:
            self.at_death(killer=attacker, source=source,
                          damage_type=damage_type)

        return delta


    def _record_attacker(self, attacker) -> None:
        """
        Purpose: Remember who last damaged this entity, for the AI to read.

        Entry:
            attacker - the CombatEntity that dealt the damage, or None for an
                       environmental or unattributed source.

        Exit/Returns:
            No return value. Writes ndb.<LAST_ATTACKER_ID_ATTR>.

        Module Globals:
            LAST_ATTACKER_ID_ATTR read.

        Methodology:
            Stores the id, not the object. A reference would pin a row that may
            be deleted before the next tick reads it; combat.py resolves
            combatants by id throughout for the same reason.

            ndb rather than db: this is fight-scoped, and a server reload ends
            every fight anyway. It also keeps a per-hit write off the Attribute
            table, which would otherwise be a database round trip on every
            connecting blow of every fight in the game.

            A None attacker is ignored rather than clearing the record. Taking
            poison or fall damage mid-fight should not make a monster forget
            who it was fighting.

            Self-damage is ignored for the same reason at_death normalises a
            self-kill to no killer: a backfiring gadget must not make its
            wielder their own retaliation target.

        Notes/References:
            This is the threat-table seam. §3.2 of
            docs/2026-08-23-DESIGN-0003 chose "last attacker" now with a threat
            table later; upgrading means accumulating per-attacker damage HERE
            and changing what systems/ai/behaviors._last_attacker reads. No
            other caller and no behaviour changes.

        Author: Nick Hobar
        Creation date: 08/23/2026
        """
        if attacker is None or attacker is self:
            return

        attacker_id = getattr(attacker, "id", None)

        if attacker_id is None:
            return

        setattr(self.ndb, LAST_ATTACKER_ID_ATTR, attacker_id)


    def at_death(self, killer=None, source=None, damage_type=None) -> None:
        """
        Purpose: Handle this entity's HP hitting zero. Sets hp=0 explicitly,
        broadcasts the death line to the room, runs killer-side hooks if
        the killer is a Character, and finally callls respawn().

        Entry:
            killer      - optional CombatEntity responsible. May be None for
                          environmental deaths, and may legitimately be `self`
                          for a self-inflicted one.
            source      - optional object responsible (weapon, gadget, aura).
            damage_type - optional DAMAGE_TYPE_* constant naming the killing
                          blow. Purely attribution/flavour today (which weapon
                          or aura did it); it does not decide who gets blamed
                          for a self-inflicted death -- that is `killer is self`.

        Exit/Returns:
            No conditions. After return, self.hp == 0 and self.is_alive()
            is False; killer-side XP/quest hooks have fired if applicable.

        Module Globals:
            combat_msg.format_death read.

        Methodology:
            1. Force hp = 0 even if somehow out of band.
            2. Capture the self-inflicted check, THEN normalise a self-kill
               to no killer at all -- format_death needs the former to pick
               the death line, and the killer-side hooks below need the
               latter so a victim cannot award themselves their own kill.
            3. Build and broadcast the death line to the room.
            4. If the killer's `.skills` satisfies XpEarner, award combat XP.
               We do NOT gate on isinstance(killer, Character) here -- but nor
               do we gate on the mere PRESENCE of `.skills`, which every NPC
               also has. The protocol names the capability being asked about.
            5. If killer has `quests`, fire the wildcard kill-progress update.
            6. call self.respawn() to permit subclass divergence (player
               respawn vs NPC despawn).

        Notes/References:
            Research doc §"Translating Game State to Evennia" —
            "if a player unexpectedly disconnects mid-combat..."
            (handled separately in at_disconnect, not here).

        Author: Nick Hobar
        Creation date: 07/26/2026
        """
        self.hp = 0

        # A self-inflicted death has no killer. Callers pass the truthful
        # attacker so a future "who hit me last" tracker can use it, which
        # means a backfiring gadget arrives here with killer IS self -- and
        # both hooks below would then fire on the victim, awarding them the
        # kill XP for their own death and recording a wildcard quest kill of
        # their own key. Captured before the normalisation below erases the
        # identity check -- this is the only place that still knows.
        self_inflicted = killer is self
        if killer is self:
            killer = None

        location = self.location
        if location is not None:
            try:
                death_line = combat_msg.format_death(self, killer,
                                                     damage_type=damage_type,
                                                     self_inflicted=self_inflicted)
                location.msg_contents(death_line, from_obj=self)
            except Exception as exc:
                logger.log_err(f"CombatEntity.at_death broadcast failed: {exc!r}")

        # `getattr(killer, "skills", None) is not None` used to gate this, and
        # it asked the wrong question: every HostileNPC has a `.skills`, so an
        # NPC that killed a player passed the gate and ran the killer-XP path.
        # That was harmless only because the NPC-side skill facade's add_xp was
        # a no-op -- the check was one attribute name standing in for "is this
        # an XP earner?", which is now a protocol that answers directly.
        earns_xp = isinstance(getattr(killer, "skills", None), XpEarner)
        if earns_xp:
            try:
                self._award_killer_xp(killer)
            except Exception as exc:
                logger.log_err(f"CombatEntity.at_death killer XP award failed: {exc!r}")

        quests = getattr(killer, "quests", None)
        if quests is not None:
            try:
                quests.update_progress("*", "kill", self.key)
            except Exception as exc:
                logger.log_err(f"CombatEntity.at_death quest update failed: {exc!r}")

        stats = getattr(killer, "stats", None)
        npc_key = getattr(self.db, "npc_key", None)
        if stats is not None and npc_key:
            try:
                stats.increment(stat_constants.KILLS_PER_HOSTILE_STAT_KEY, npc_key)
            except Exception as exc:
                logger.log_err(f"CombatEntity.at_death KILLS_PER_HOSTILE_STAT_KEY stat update failed: {exc!r}")

        stats_b = getattr(self, "stats", None)
        npc_key_b = getattr(getattr(killer, "db", None), "npc_key", None)
        if stats_b is not None and npc_key_b:
            try:
                stats_b.increment(stat_constants.DEATHS_PER_HOSTILE_STAT_KEY, npc_key_b)
            except Exception as exc:
                logger.log_err(f"CombatEntity.at_death DEATHS_PER_HOSTILE_STAT_KEY stat update failed: {exc!r}")

        # Drops must roll BEFORE respawn. HostileNPC.respawn() deletes the row,
        # and the loot table is resolved off db.npc_key while it still exists.
        self.drop_loot(killer)

        # Tear combat down BEFORE respawn. respawn() restores HP to max, so
        # running it first made the corpse read as alive again and the fight
        # simply continued -- check_stop_combat's "you lost" branch was
        # unreachable for players.
        self.leave_combat()

        self.respawn()


    def _award_killer_xp(self, killer) -> None:
        """
        Purpose: Internal XP award for landing a killing blow. Subclass /
        batch-extension hook; default behavior in this batch is a one-line
        defense-XP bonus so the kill pipeline has a demonstrable trace.

        Entry:
            killer - the CombatEntity that landed the killing blow. Must
                     expose .skills (validated by caller, not this body).

        Exit/Returns:
            No conditions.

        Module Globals:
            None.

        Methodology:
            Defensive getattr around skills.add_xp; combat handler already
            awarded per-hit XP via let-flow XP calls (per constants), so the
            killing-blow bonus here is intentionally small. Real per-hit XP
            is granted by the combat handler in batch 2.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 07/26/2026
        """
        pass


    def drop_loot(self, killer=None) -> None:
        """
        Purpose: Subclass-overridable hook for leaving loot behind on death.
        Default behaviour is to drop nothing.

        Entry:
            killer - the entity that landed the killing blow, or None for an
                     environmental or self-inflicted death (at_death has
                     already normalised a self-kill to None by this point).

        Exit/Returns:
            No conditions.

        Module Globals:
            None.

        Methodology:
            A no-op stub for the same reason respawn() is: what death leaves
            behind differs completely between an NPC (a drop table) and a
            Player (a death penalty Blackout has no policy for yet), and the
            base class should assert neither. HostileNPC overrides this to roll
            its NpcDef's loot_table.

        Notes/References:
            Called from at_death BEFORE leave_combat/respawn, because
            HostileNPC.respawn() deletes the database row this reads
            db.npc_key off.

            A Player override is where inventory-drop-on-death would land; the
            hook exists now so that work needs no change to at_death.

        Author: Nick Hobar
        Creation date: 08/14/2026
        """
        pass


    def respawn(self) -> None:
        """
        Purpose: Subclass-overridable respawn hook. The base behaviour is a
        bare HP refill in place; both real combatant types override it.
        HostileNPC deletes its row and enqueues on the respawn manager, and
        Character moves to the respawn room (world/respawn.py) at full HP.

        This body is therefore the DEGRADED path, not a stub: it is what
        Character.respawn falls back to when the respawn room cannot be
        resolved, which is the behaviour every player death had before there
        was a respawn-room fact anywhere in the codebase.

        Entry:
            None.

        Exit/Returns:
            No conditions.

        Module Globals:
            combat_constants.FORTITUDE_START_LEVEL read for default restore.

        Methodology:
            For an NPC, this is usually overridden to delete() the object
            or move to a corpse-replacement handler. For a Player, the
            Player subclass overrides this to move the character to a
            respawn room and restore HP to max_hp.

        Notes/References:
            Player respawn policy: docs/2026-08-23-DESIGN-0003 §1.4 --
            respawn room, full HP, deliberately no XP penalty.

        Author: Nick Hobar
        Creation date: 07/26/2026
        """
        restore_to = self.db.max_hp or combat_constants.FORTITUDE_START_LEVEL
        self.db.hp = restore_to

    # ─── Disconnect cleanup ─────────────────────────────────────────────────

    def leave_combat(self) -> None:
        """
        Purpose: Cancel this entity's participation in any active combat.
        The single teardown path, shared by death and by disconnect.

        Entry:
            None. self.db must exist.

        Exit/Returns:
            No conditions. Safe to call when not in combat.

        Module Globals:
            None.

        Methodology:
            1. Query self.combat (CombatEntity's lazy accessor) and if the
               accessor returned a non-None handler, call its drop_combatant
               so the per-combatant Script can release the entity cleanly.
            3. Drop the lazy_property cache.

        Notes/References:
            Research doc §"Architecting the Combat Handler".

        Author: Nick Hobar
        Creation date: 07/26/2026
        """
        try:
            handler = self.combat
        except Exception:
            handler = None

        if handler is not None:
            try:
                handler.drop_combatant(self)
            except Exception as exc:
                logger.log_err(f"CombatEntity.leave_combat drop_combatant failed: {exc!r}")

        # Drop the lazy_property cache so a later reconnect re-resolves the
        # accessor instead of handing back the handler we just dropped. Note
        # lazy_property caches in __dict__, not on ndb, and refuses `del`.
        self.__dict__.pop("combat", None)


    def at_disconnect_combat_cleanup(self) -> None:
        """
        Purpose: Prevent "combat logging" — the research doc's term for a
        player disconnecting mid-swing to escape a fight without resolving
        an escape mechanic. Called from the host Character's
        at_post_unpuppet and from any NPC despawn pathway.

        Entry:
            None.

        Exit/Returns:
            No conditions.

        Module Globals:
            None.

        Methodology:
            Delegates to leave_combat, which death also uses, then switches
            off any tick monitor this entity had running.

        Notes/References:
            The monitor is dropped HERE rather than in leave_combat because
            death also routes through leave_combat, and a player who just died
            wants to watch the ticks that follow. Disconnecting is the only
            event that means "stop printing to me".

        Author: Nick Hobar
        Creation date: 07/26/2026
        """
        self.leave_combat()

        # Deferred and guarded: a diagnostic must never be able to break the
        # anti-combat-log path it is riding on.
        try:
            from systems.tick import debug as tick_debug

            tick_debug.detach(self)
        except Exception as exc:
            logger.log_err(f"at_disconnect_combat_cleanup tick_debug detach failed: {exc!r}")

    @property
    def in_combat(self) -> bool:
        """
        Purpose: Report whether this entity is currently in a fight.

        Entry:
            No conditions. Safe on an entity that has never fought.

        Exit/Returns:
            True while a live combat handler exists and is not tearing down.

        Module Globals:
            None.

        Methodology:
            DERIVED, not stored. This was a persistent `db.in_combat`
            Attribute written from five places, alongside four other things
            that also answered "is this entity in combat?" -- whether a
            handler script existed, its db_is_active column, its membership of
            the tick rotation, and whether a pending action was set. Nothing
            kept them in agreement, and the code to repair their disagreement
            was most of what made combat teardown hard to follow.

            The predicate is "has a live handler that is not final" rather
            than "is mid-swing", because a defender who has been attacked but
            has not acted yet IS in combat. `examine mutant raider` reporting
            otherwise was a bug once already.

        Notes/References:
            systems/tick/states.py owns the state this reads.

        Author: Nick Hobar
        Creation date: 08/18/2026
        """
        from systems.tick import states

        try:
            handler = self.combat
        except Exception:
            return False

        if handler is None or handler.pk is None:
            return False

        final = states.is_final(handler.state)

        return not final


    # ─── CombatHandler lazy accessor (filled in by combat.py in batch 2) ────

    @lazy_property
    def combat(self):
        """
        Purpose: Cached property returning the per-combatant
        BlackoutCombatHandler attached to this entity, or None if no
        handler is active. Follows the @lazy_property pattern used by
        Character.skills, Character.equipment, Character.inventory,
        Character.quests.

        Entry:
            None.

        Exit/Returns:
            BlackoutCombatHandler instance or None.

        Module Globals:
            None.

        Methodology:
            The combat handler is implemented as a per-combatant
            DefaultScript that, when running, lives in self.scripts under
            the key 'blackout_combat_handler'. We scan scripts.get() and
            return the first matching one. This keeps the property pure and
            side-effect-free; the combat handler is added by the attack
            command (batch 2), not by this accessor.

        Notes/References:
            Per user design dialogue: one-handler-per-combatant is the
            chosen Evennia-native architecture, NOT a global room script.

        Author: Nick Hobar
        Creation date: 07/26/2026
        """
        from systems.combat.combat import get_handler_for  # local import to avoid circularity

        try:
            return get_handler_for(self)
        except Exception:
            logger.log_trace("CombatEntity.combat accessor: no handler attached.")
            return None

    # ─── AuraHandler lazy accessor ─────────────────────────────────────────

    @lazy_property
    def aura(self):
        """
        Purpose: Cached property returning the BlackoutAuraHandler attached to
        this entity while a damage aura is burning, or None.

        Entry:
            None.

        Exit/Returns:
            BlackoutAuraHandler instance or None.

        Module Globals:
            None.

        Methodology:
            Mirrors the `combat` accessor above exactly, including the pure,
            side-effect-free contract: the handler is created by the `aura`
            command, never by reading this property.

            Both this cache and `combat`'s are cleared with
            `obj.__dict__.pop("aura", None)` rather than `del`, because
            lazy_property stores into obj.__dict__ under its own name and its
            deleter raises — a swallowed `del` is what once left the combat
            accessor handing out a deleted script for a whole session.

        Notes/References:
            systems/combat/auras/aura_handler.py owns the handler itself.

        Author: Nick Hobar
        Creation date: 08/03/2026
        """
        from systems.combat.auras.aura_handler import (  # local import to avoid circularity
            get_aura_handler_for,
        )

        try:
            return get_aura_handler_for(self)
        except Exception:
            logger.log_trace("CombatEntity.aura accessor: no handler attached.")
            return None
