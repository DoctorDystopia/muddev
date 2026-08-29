"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/07/2026
Description: The adapter layer — game events in, payloads out, emitted.

             Every emission call site in the game calls a routine here rather
             than building a payload itself. Two reasons:

               1. The call sites stay one line. combat.py's _land_hit is a
                  documented, order-sensitive routine; a feed that expanded it
                  by fifteen lines of dict-building would be a liability there.
               2. Payload SHAPE is owned in one place. The feed and the prose
                  in combat_msg are both built from the same ActionResult, in
                  the same function, on the same tick -- which is what stops
                  them from drifting into disagreeing about a swing.

             Nothing here raises; emit() swallows and logs.
"""



from . import constants as const
from . import serializers, subscriptions
from .emit import emit, emit_to_area, emit_to_room
from .payloads import (
    AuraPayload,
    CharAvatarPayload,
    CharItemsPayload,
    CharQuestsPayload,
    CharSkillsPayload,
    CharStatusPayload,
    CharSummaryPayload,
    CharVitalsPayload,
    CombatPayload,
    RoomInfoPayload,
    RoomPlayerAddPayload,
    RoomPlayerRemovePayload,
    RoomPlayersPayload,
)



# ─── Public constant definitions ─────────────────────────────────────────────

AURA_EVENT_ACTIVATE: str = "activate"
AURA_EVENT_DEACTIVATE: str = "deactivate"
AURA_EVENT_PULSE: str = "pulse"



# ─── Private helper routines ─────────────────────────────────────────────────

def _visible_rooms(room) -> list:
    """
    Purpose: The rooms whose contents an observer standing in `room` may see.

    Entry:
        room - a room object, or None.

    Exit/Returns:
        Returns a list of rooms, always including `room` itself. Returns []
        for a None room.

    Module Globals:
        const.STATEFEED_ENTITY_RADIUS read.

    Methodology:
        The single place STATEFEED_ENTITY_RADIUS is read, so raising or
        lowering it moves both the contents list and the deltas together.
        Until this existed the constant was set to 10 and consulted nowhere:
        the docstring beside it described a behaviour the code did not have.

        rooms_within_radius short-circuits to [origin] for a radius of 0 and
        for an off-grid room, so the zero case costs no query and the
        hand-built-area case degrades to exactly the old behaviour.

        Imported inside the routine. systems.combat.auras.targeting reaches
        the xyzgrid contrib's models, and this module is imported by
        typeclasses/mixins.py, which every Character and NPC pulls in at
        startup -- a module-scope import would drag those models into
        typeclass import time and couple the two systems' import order.

    Notes/References:
        Raising the radius is a BALANCE change, not a rendering one: a
        graphical client is told about NPCs a telnet player would have to walk
        to. See the constant's own comment.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    if room is None:
        return []

    from systems.combat.auras.targeting import rooms_within_radius

    return rooms_within_radius(room, const.STATEFEED_ENTITY_RADIUS)



def _read_levels(skills) -> dict:
    """
    Purpose: Snapshot the observer's combat skill levels as {key: int}.

    Entry:
        skills - a SkillHandler, a StatBlockSkills, or None. None is the
                 supported "this entity has no skills" case and returns {}.

    Exit/Returns:
        Returns a plain dict of skill key to integer level.

    Module Globals:
        None.

    Methodology:
        Deliberately narrowed to the COMBAT skills, and the narrowing is the
        interesting part. char_status feeds the 3D view, which has nothing to
        draw with a Cutting level; the full table with its XP curves is
        char_summary's job, built by systems/summary/ from the same handler
        reads that render the telnet screen. A skills TAB should read that
        channel, not widen this one -- otherwise two channels carry the same
        fact and the client gets to choose which is right.

        Iterates COMBAT_SKILL_KEYS rather than db.skills, so a combat skill
        added after this character was created reports 0 instead of being
        silently absent from the table -- the same choice get_total_level
        makes for the same reason.

        The import is inside the routine. This module is imported by
        typeclasses/mixins.py, which every Character and NPC pulls in at
        startup, and the skills package walks its own registry at import time.

    Notes/References:
        Moved here from resync.py, which was its only caller until
        emit_status existed. See that routine.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    if skills is None:
        return {}

    from systems.progression.skills.constants import COMBAT_SKILL_KEYS

    levels = {}

    for skill_key in COMBAT_SKILL_KEYS:
        levels[skill_key] = skills.get_level(skill_key)

    return levels



def _style_name(context) -> str:
    """Name the active combat style as a player would recognise it.

    The per-weapon flavour name ("irimi", "swipe") is the dict KEY in a
    weapon's combat_styles table, and the resolved style dict that reaches an
    ActionContext no longer carries it. It is recoverable from the weapon,
    which is worth doing because those names are already animation-shaped.

    Falls back to the weapon_style (accurate / aggressive / defensive /
    controlled), which is always present -- including unarmed, where there is
    no weapon to read a name off at all.
    """
    weapon = context.weapon

    if weapon is not None:
        named = weapon.attributes.get("default_combat_style", default=None)

        if named:
            return str(named)

    return str(context.style.get("weapon_style", ""))



def _broadcast(payload, attacker, target, room) -> int:
    """Send one payload to the two combatants and their onlookers.

    Mirrors the text broadcast beside every call site exactly: attacker,
    target, then the room excluding both. That equivalence is deliberate -- the
    feed must reach precisely the people the prose reaches, so a graphical
    client can never learn something a telnet player in the same room cannot.
    """
    sent = emit(attacker, payload)

    if target is not attacker:
        sent += emit(target, payload)

    sent += emit_to_room(room, payload, exclude=(attacker, target))

    return sent



# ─── Public routines ─────────────────────────────────────────────────────────

# TODO: update emit_swing name (e.g, emit_combat_action). Also, might be
# other useful metadata to carry through the pipeline?
def emit_swing(context, result, hp_after: int, max_hp: int,
               killed: bool, backfire: bool = False) -> int:
    """
    Purpose: Publish one resolved swing to every graphical client that can see
    it.

    Entry:
        context   - the ActionContext the swing resolved against.
        result    - the ActionResult it produced.
        hp_after  - the victim's HP after this hit, computed arithmetically
                    from the PRE-damage total.
        max_hp    - the victim's maximum HP.
        killed    - True if this swing was lethal.
        backfire  - True if the damage landed on the attacker's own head.

    Exit/Returns:
        Returns the number of sends performed.

    Module Globals:
        None.

    Methodology:
        hp_after is passed in rather than read off the victim because this must
        be called BEFORE at_damage runs -- a killed NPC deletes itself inside
        at_damage, and a client that resolved target_id afterwards would find
        nothing to attach a death animation to. combat.py's _land_hit already
        computes the post-hit total for its HP bar for exactly this reason, so
        the value is free.

        A backfire names the attacker as its own victim. That is truthful
        rather than a special case: at_death normalises self-kills, and a
        client animating "who took damage" wants the attacker highlighted.

    Notes/References:
        systems/combat/combat.py:417 _land_hit documents why the
        announce-before-at_damage ordering this depends on exists.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    attacker = context.attacker
    victim = attacker if backfire else context.defender
    room = getattr(victim, "location", None)

    payload = CombatPayload(
        attacker_id=attacker.id,
        attacker_name=str(attacker.key),
        target_id=victim.id,
        target_name=str(victim.key),
        hit=bool(result.hit),
        damage=result.self_damage if backfire else result.damage,
        damage_type=str(result.damage_type),
        attack_type=str(context.attack_type),
        style=_style_name(context),
        hp_after=hp_after,
        max_hp=max_hp,
        killed=bool(killed),
        backfire=backfire,
    )

    return _broadcast(payload, attacker, context.defender, room)



def emit_miss(context) -> int:
    """
    Purpose: Publish a swing that connected with nothing.

    Entry:
        context - the ActionContext the swing resolved against.

    Exit/Returns:
        Returns the number of sends performed.

    Module Globals:
        None.

    Methodology:
        A miss is sent rather than skipped because a client that only hears
        about hits cannot animate a fight -- it would show a combatant standing
        still through every miss and then twitching on a hit. damage is zero
        and hp_after is the victim's current HP, unchanged.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    attacker = context.attacker
    target = context.defender
    room = getattr(target, "location", None)

    payload = CombatPayload(
        attacker_id=attacker.id,
        attacker_name=str(attacker.key),
        target_id=target.id,
        target_name=str(target.key),
        hit=False,
        damage=0,
        damage_type=str(context.style.get("attack_type", "")),
        attack_type=str(context.attack_type),
        style=_style_name(context),
        hp_after=getattr(target, "hp", 0),
        max_hp=getattr(target, "max_hp", 0),
        killed=False,
    )

    return _broadcast(payload, attacker, target, room)



def emit_vitals(entity, force: bool = False) -> int:
    """Publish one entity's own health to its own sessions.

    Rate-capped by channel config, so calling this liberally on any HP change
    is safe -- the cap collapses a burst into one send.

    `force` is for the half of this payload the cap cannot be trusted with. hp
    moves constantly and is re-sent every time, so a dropped send repairs
    itself on the next one; max_hp moves once per Fortitude level and nothing
    repeats it, so its send must not be the one the cap happens to eat. See
    CombatEntity's max_hp setter.
    """
    max_hp = getattr(entity, "max_hp", 0)
    payload = CharVitalsPayload(hp=getattr(entity, "hp", 0), max_hp=max_hp)

    return emit(entity, payload, force=force)



def emit_status(observer, force: bool = False) -> int:
    """
    Purpose: Publish the observer's own non-vital state -- their combat skill
    levels and whether they are fighting -- to the observer alone.

    Entry:
        observer - the puppeted Character, or anything exposing `skills` and
                   `in_combat`. An entity with neither is supported and sends
                   an empty level table rather than raising.
        force    - True to bypass the channel's 1s rate cap. Used by resync.

    Exit/Returns:
        Returns the number of sends performed. Zero when nobody is subscribed,
        which is the normal result on a telnet-only server.

    Module Globals:
        None.

    Methodology:
        This routine is why the channel exists at all. Until it was written
        char_status was built in exactly ONE place -- resync -- so a client
        received its level table at login and never again: levelling a skill
        moved every reader on the server while the graphical client kept
        drawing the levels the character had when it connected. That is the
        same defect the max_hp setter fixes on the vitals channel, one channel
        over, and it is why resync now DELEGATES here instead of assembling
        the payload itself. A resync that built its own copy would be a second
        definition of "what a status message contains", agreeing with this one
        only until somebody edited one of them.

        The subscriber check happens FIRST, for the same reason emit_summary
        does it. `_read_levels` calls get_level once per combat skill, and
        get_level backfills a missing slot through ensure_skill -- a WRITE.
        Cheap, idempotent and wanted when a client is listening; pure waste on
        a server where none is.

    Notes/References:
        Deliberately does NOT carry the full skill table. See _read_levels.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    wants = subscriptions.has_channel_subscribers(
        observer, CharStatusPayload.channel
    )

    if not wants:
        return 0

    skills = getattr(observer, "skills", None)
    payload = CharStatusPayload(
        in_combat=bool(getattr(observer, "in_combat", False)),
        levels=_read_levels(skills),
    )

    return emit(observer, payload, force=force)



def emit_avatar(observer, force: bool = False) -> int:
    """
    Purpose: Tell the observer what they themself look like.

    Entry:
        observer - the puppeted Character, or None (a no-op, matching every
                   other observer-facing emitter here).
        force    - True to bypass rate caps. Used by resync.

    Exit/Returns:
        Returns the number of sends performed. Zero when nobody is subscribed.

    Module Globals:
        None.

    Methodology:
        The body is TAKEN FROM serialize_entity rather than assembled here,
        even though only three of its keys are kept. That routine owns the
        answer to "what names this thing's art" -- it is what decides an NPC by
        npc_key, an item by prototype, a character by ASSET_KEY_CHARACTER --
        and a second place deriving the same pair for the observer alone is a
        second place to forget when a character can choose its appearance. The
        three keys are picked off the result; the rest is dropped because
        char_vitals and room_info already carry it. See CharAvatarPayload.

        Sent on resync only, which is every login, every reconnect and every
        server reload. That is the whole schedule this fact has today: a
        character's asset key is fixed for its lifetime. When appearance
        becomes mutable, whatever sets it calls this, and nothing else here
        changes.

    Notes/References:
        emit_room_contents excludes the observer from their own entity list,
        which is why this channel has to exist at all.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    if observer is None:
        return 0

    body = serializers.serialize_entity(observer)
    payload = CharAvatarPayload(
        entity_id=body["id"],
        asset=body["asset"],
        family=body["family"],
    )

    return emit(observer, payload, force=force)



def emit_summary(observer, force: bool = False) -> int:
    """
    Purpose: Publish the observer's whole dossier to the observer alone.

    Entry:
        observer - the puppeted Character.
        force    - True to bypass rate caps. Used by resync; the channel is
                   uncapped anyway, so this is currently a formality that keeps
                   the call shape identical to every other resync send.

    Exit/Returns:
        Returns the number of sends performed. Zero when nobody is subscribed,
        which is the normal result on a telnet-only server.

    Module Globals:
        None.

    Methodology:
        The subscriber check happens FIRST. Building a summary is the most
        expensive payload in the feed by a wide margin -- it reads every
        handler on the character and walks the XP curve once per skill -- so
        unlike the cheap payloads around it, this one must not be built
        speculatively. emit() would discard it for free, but only after the
        work was already done.

        systems.summary is imported inside the function rather than at module
        scope. This module is imported by typeclasses/mixins.py, which every
        Character and NPC pulls in at startup; a top-level import would drag
        the summary panel registry's package walk into typeclass import time
        for no benefit, and would couple the two systems' import order.

    Notes/References:
        Panel data is built by systems/summary/service.py, which is also what
        renders the telnet screen -- both from the same handler reads, so the
        two cannot disagree about the player's state.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    from systems.summary.service import summary_data

    wants = subscriptions.has_channel_subscribers(
        observer, CharSummaryPayload.channel
    )

    if not wants:
        return 0

    payload = CharSummaryPayload(panels=summary_data(observer))

    return emit(observer, payload, force=force)




def emit_skills(observer, force: bool = False) -> int:
    """
    Purpose: Publish the observer's whole skill roster to the observer alone.

    Entry:
        observer - the puppeted Character. One with no skills handler is a
                   supported no-op.
        force    - True to bypass rate caps. The channel is uncapped, so this
                   is a formality that keeps the resync call shape identical to
                   every other send.

    Exit/Returns:
        Returns the number of sends performed. Zero when nobody is subscribed,
        which is the normal result on a telnet-only server.

    Module Globals:
        None.

    Methodology:
        The subscriber check happens FIRST, and it matters more here than
        anywhere else in this module. Building this payload walks the recipe
        registry, the gatherable table, the equipment requirements and the aura
        registry once per skill -- it is the most expensive payload in the feed
        by some distance. emit() would discard the result for free, but only
        after all of that work was already done.

        WHERE IT IS CALLED FROM is the other half of that cost argument. Not on
        an XP award: combat awards XP on every hit, and the roster's numbers
        would be rebuilt several times a second for a screen nobody is looking
        at. It fires when a level actually MOVES, when the player asks about
        skills, and on resync -- so its rate is bounded by the player rather
        than by the tick. See CHANNEL_MIN_INTERVAL_SECONDS on why that also
        makes a rate cap the wrong tool here.

        systems.statefeed.skills is imported inside the routine. It reaches
        systems/progression/skills/detail.py, which reaches crafting, auras and
        equipment; this module is imported by typeclasses/mixins.py, which
        every Character and NPC pulls in at startup, so a top-level import
        would drag all of that into typeclass import time.

    Notes/References:
        The payload is built by systems/statefeed/skills.py from the same
        per-skill renderer the text sheet uses, so the grid and the sheet
        cannot describe a skill differently.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    from . import skills as skills_serializer

    wants = subscriptions.has_channel_subscribers(
        observer, CharSkillsPayload.channel
    )

    if not wants:
        return 0

    return emit(observer, skills_serializer.build_payload(observer),
                force=force)


def emit_quests(observer, force: bool = False) -> int:
    """
    Purpose: Publish the observer's quest log to the observer alone.

    Entry:
        observer - the puppeted Character. One with no quest handler is a
                   supported no-op.
        force    - True to bypass rate caps. The channel is uncapped, so this
                   is a formality that keeps the resync call shape identical to
                   every other send.

    Exit/Returns:
        Returns the number of sends performed. Zero when nobody is subscribed,
        which is the normal result on a telnet-only server.

    Module Globals:
        None.

    Methodology:
        The subscriber check happens FIRST, for the same reason emit_summary
        does it: building the log walks every active quest's current step and
        every objective on it, and emit() would discard the result for free --
        but only after the work was already done.

        systems.statefeed.quests is imported inside the routine. It reaches the
        quest loader, which imports every module under systems/quests/content/;
        this module is imported by typeclasses/mixins.py, which every Character
        and NPC pulls in at startup, so a top-level import would drag that walk
        into typeclass import time and couple the two systems' import order.

    Notes/References:
        The payload is built by systems/statefeed/quests.py, entirely through
        QuestHandler's public read API -- db.active_quests keeps one owner.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    from . import quests as quests_serializer

    wants = subscriptions.has_channel_subscribers(
        observer, CharQuestsPayload.channel
    )

    if not wants:
        return 0

    return emit(observer, quests_serializer.build_payload(observer),
                force=force)


def emit_inventory(observer, force: bool = False, ignore=None) -> int:
    """
    Purpose: Publish the observer's carried grid and equipment to themself.

    Entry:
        observer - the puppeted Character. An object with no inventory handler
                   is a supported no-op.
        force    - True to bypass rate caps. A formality today, since the
                   channel is uncapped by design, kept so the resync call site
                   looks like every other one.
        ignore   - an object to treat as already gone when building the
                   snapshot, or None. Only at_object_leave needs this; see
                   InventoryHandler.sync for why.

    Exit/Returns:
        Returns the number of sends performed. Zero when nobody is subscribed,
        which is the normal result on a telnet-only server.

    Module Globals:
        None.

    Methodology:
        The subscriber check happens FIRST, for the same reason emit_summary
        does it: building this payload walks 32 slots, syncs the handler, and
        reads the tag set on every item. That is far more than the cheap
        payloads around it, and emit() would discard the result for free but
        only after the work was already done.

        The build is WRAPPED, which the other event routines are not. They are
        called from a command or a combat tick; this one is also called from
        at_object_receive and at_object_leave, which sit directly in the path
        of every item movement in the game. A feed that could raise there could
        lose an item mid-move, and typeclasses/characters.py already swallows
        exceptions around the inventory call it makes -- so a raise here would
        be silently absorbed into exactly the behaviour that loses things.

        systems.statefeed.inventory is imported inside the routine. It reaches
        items.equipment.constants and items.inventory.handler, and this module
        is imported by typeclasses/mixins.py, which every Character and NPC
        pulls in at startup.

    Notes/References:
        payloads.CharItemsPayload documents why this is a snapshot rather than
        a delta, and constants.CHANNEL_MIN_INTERVAL_SECONDS documents why the
        channel must not be rate-capped.

    Author: Nick Hobar
    Creation date: 08/15/2026
    """
    from evennia.utils import logger

    from . import inventory as inventory_serializer

    wants = subscriptions.has_channel_subscribers(
        observer, CharItemsPayload.channel
    )

    if not wants:
        return 0

    try:
        payload = inventory_serializer.build_payload(observer, ignore=ignore)
    except Exception:
        logger.log_trace()
        return 0

    if payload is None:
        return 0

    return emit(observer, payload, force=force)



def emit_room_info(observer, force: bool = False) -> int:
    """Publish the observer's current room to the observer alone.

    Room identity is per-observer, not per-room: two people standing in the
    same tile each get their own message, because this is "where YOU are".
    """
    room = getattr(observer, "location", None)

    if room is None:
        return 0

    payload = RoomInfoPayload(
        num=room.id,
        name=str(room.key),
        room_kind=serializers.room_kind(room),
        coords=serializers.room_coords(room),
        exits=serializers.serialize_exits(room),
        tile_actions=serializers.tile_actions(room),
        cancel_action=serializers.cancel_action(),
    )

    return emit(observer, payload, force=force)



def emit_room_contents(observer, force: bool = False) -> int:
    """Publish the full list of what the observer can see around them.

    The "list" half of list-then-delta: sent on arrival and on resync, with
    emit_entity_arrived / emit_entity_left carrying the changes in between.
    The observer is excluded from their own list -- a client already knows
    where it put the camera.

    "Around them" is STATEFEED_ENTITY_RADIUS tiles, not one room. Every entity
    carries the coords of the room it is in, because a client given a
    neighbourhood and no positions would stack all of it on the player's tile.
    """
    room = getattr(observer, "location", None)

    if room is None:
        return 0

    rooms = _visible_rooms(room)
    entities = serializers.serialize_area(rooms, exclude=(observer,))
    payload = RoomPlayersPayload(entities=entities)

    return emit(observer, payload, force=force)



def emit_entity_arrived(room, entity) -> int:
    """Tell everyone who can see `room` that `entity` just appeared.

    Reaches the same radius emit_room_contents reports over. A narrower
    broadcast would leave observers who were told about this room's contents
    never hearing them change.
    """
    coords = serializers.room_coords(room)
    body = serializers.serialize_entity(entity, coords=coords)
    payload = RoomPlayerAddPayload(entity=body)
    rooms = _visible_rooms(room)

    return emit_to_area(rooms, payload, exclude=(entity,))



def emit_entity_left(room, entity_id: int, exclude=()) -> int:
    """
    Purpose: Tell everyone in `room` that an entity is gone.

    Entry:
        room      - the room being left.
        entity_id - the departing entity's id, captured BEFORE it left or was
                    deleted.
        exclude   - objects to skip.

    Exit/Returns:
        Returns the number of sends performed.

    Module Globals:
        None.

    Methodology:
        Takes a bare id rather than the object precisely because this also
        fires for an NPC that just died. By the time the room learns about it
        the object may already be deleted, and serialising it would either
        raise or produce a row of defaults.

        Reaches the same radius emit_room_contents reports over. This is the
        half that must not be missed: an observer told about a distant NPC and
        never told it died renders it standing there indefinitely, since
        nothing else is scheduled that would correct them.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    payload = RoomPlayerRemovePayload(entity_id=entity_id)
    rooms = _visible_rooms(room)

    return emit_to_area(rooms, payload, exclude=exclude)



def emit_aura(owner, event: str, aura_key: str, radius: int,
              tiles=(), damage: int = 0) -> int:
    """
    Purpose: Publish an aura activating, deactivating, or pulsing.

    Entry:
        owner    - the entity the aura belongs to.
        event    - one of the AURA_EVENT_* constants.
        aura_key - the aura's registry key.
        radius   - its footprint radius in tiles.
        tiles    - the affected world coordinates, as (x, y) pairs.
        damage   - damage dealt by this pulse, if any.

    Exit/Returns:
        Returns the number of sends performed.

    Module Globals:
        None.

    Methodology:
        Sent to the aura's owner only. This is the one channel that names tiles
        the observer is not standing on, and that is legitimate solely because
        the text channel already shows the owner the same footprint, as the
        tinted map overlay in typeclasses/rooms.py. Broadcasting it to the room
        would leak a player's aura radius to everyone nearby, which the text
        game does not do.

    Notes/References:
        systems/combat/auras/map_overlay.py owns the equivalent text rendering.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    coords = []

    for tile in tiles:
        coords.append([tile[0], tile[1]])

    payload = AuraPayload(
        event=event,
        aura_key=str(aura_key),
        radius=radius,
        tiles=coords,
        damage=damage,
    )

    return emit(owner, payload)
