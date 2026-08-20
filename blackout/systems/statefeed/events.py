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
    CharItemsPayload,
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


def emit_vitals(entity) -> int:
    """Publish one entity's own health to its own sessions.

    Rate-capped by channel config, so calling this liberally on any HP change
    is safe -- the cap collapses a burst into one send.
    """
    max_hp = getattr(entity, "max_hp", 0)
    payload = CharVitalsPayload(hp=getattr(entity, "hp", 0), max_hp=max_hp)

    return emit(entity, payload)


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
