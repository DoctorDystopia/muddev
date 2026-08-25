"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/15/2026
Description: Turn a character's inventory grid and equipment slots into the
             plain values CharItemsPayload carries.

             Kept out of serializers.py on purpose. That module answers "what
             is this thing standing in the world", and every routine in it is
             built around an entity that has a location and coordinates. This
             one answers "what is in slot 6", which is a different question
             with a different shape: no coordinates, a slot index, a stack
             size, and several afforded verbs rather than one.

             It does share serializers._classify and serializers._item_family,
             because both are the same fact in both places -- the mesh a client
             draws for a spear on the floor is the mesh it draws for the same
             spear in a bag.

             What it deliberately does NOT carry is `desc`. serialize_entity
             gives the reason and it applies here twice over: the text channel
             already has the prose, and duplicating it into the feed is how the
             two drift apart. A player who wants the description sends the
             Inspect action and reads it in the text pane, where it lives.
"""

from . import constants as const
from .serializers import _classify, _item_family


# ─── Private helper routines ─────────────────────────────────────────────────

def _equip_slot_value(item) -> str:
    """Name the equipment slot this item would occupy, or "" if it is not
    equippable.

    Read through the typeclass's own `inventory_use_slot`, which already
    normalises the three shapes the attribute can hold (enum, member name,
    member value). Reading the raw attribute here would be a second, worse
    copy of _resolve_use_slot.
    """
    use_slot = getattr(item, "inventory_use_slot", None)

    if use_slot is None:
        return ""

    return str(use_slot.value)


def _build_actions(templates, item, slot_number: int, equip_slot: str) -> list:
    """
    Purpose: Render an action template table into concrete commands.

    Entry:
        templates   - an iterable of (label, command_template) pairs from
                      constants.
        item        - the live object the actions act on.
        slot_number - the item's 1-BASED grid position, or 0 when it is
                      equipped and therefore has none.
        equip_slot  - the WieldLocation value the item occupies or would
                      occupy, or "".

    Exit/Returns:
        A list of {"label": str, "command": str} dicts.

    Module Globals:
        None.

    Methodology:
        The SERVER names the verbs, and it names them whole. This is the same
        rule interact_command follows, and it exists because the client's verb
        table was wrong within a week of being written -- a Foundry Furnace
        fell through to "item" and the pane confidently offered to pocket it.

        Slot numbers are made 1-based HERE rather than in the client, because
        1-based is what the player sees when they type `inventory` and what the
        commands parse. The 0-based index elsewhere in the payload is an array
        position and nothing else.

    Notes/References:
        Every command produced here is one a telnet player could type. That is
        the whole contract the graphical client rests on.

    Author: Nick Hobar
    Creation date: 08/15/2026
    """
    actions = []

    for label, template in templates:
        command = template.format(
            slot=slot_number,
            name=str(item.key),
            equip_slot=equip_slot,
        )
        actions.append({"label": str(label), "command": command})

    return actions


def _serialize_item(item, slot, actions: list) -> dict:
    """Render one item row, whether it is carried or worn.

    `slot` is an array index for a carried item and a WieldLocation value for
    an equipped one. Both are the client's key for "which frame does this sit
    in", and keeping them in one field is what lets the pane's drag code treat
    the two grids the same way.
    """
    _kind, asset_key = _classify(item)
    family = _item_family(item)
    equip_slot = _equip_slot_value(item)

    return {
        "id": item.id,
        "slot": slot,
        "name": str(item.key),
        "asset": asset_key,
        "family": family,
        "quantity": getattr(item, "quantity", 1),
        "stackable": bool(getattr(item, "is_stackable", False)),
        "equip_slot": equip_slot,
        "actions": actions,
    }


def _serialize_carried(handler) -> list:
    """Render every occupied slot in the 32-slot grid.

    Empty slots are OMITTED rather than sent as nulls. The client is told
    slots_total and draws that many frames; a list of only the occupied ones is
    smaller, and means a stale id that _load has already nulled cannot reach
    the client as a row of defaults.
    """
    rows = []
    occupied = handler.all_items()

    for slot_index, item in occupied:
        if item is None:
            continue

        slot_number = slot_index + 1
        equip_slot = _equip_slot_value(item)
        templates = [const.INVENTORY_ACTION_INSPECT, const.INVENTORY_ACTION_DROP]

        if equip_slot:
            templates.insert(0, const.INVENTORY_ACTION_EQUIP)

        actions = _build_actions(templates, item, slot_number, equip_slot)
        row = _serialize_item(item, slot_index, actions)
        rows.append(row)

    return rows


def _serialize_slot_frames() -> list:
    """Name every equipment slot in display order, occupied or not.

    The client draws one frame per entry. Derived from SLOT_DISPLAY_ORDER and
    WieldLocation.label rather than tabulated here, so adding a slot to the
    enum reaches the 3D pane without an edit in this module or in the client.
    """
    from items.equipment.constants import SLOT_DISPLAY_ORDER

    frames = []

    for slot in SLOT_DISPLAY_ORDER:
        frames.append({"slot": str(slot.value), "label": str(slot.label)})

    return frames


def _serialize_equipped(handler) -> list:
    """Render every occupied equipment slot, in display order.

    Walks SLOT_DISPLAY_ORDER rather than the handler's dict, so the pane's
    paper doll and the text equipment screen list slots in the same order
    without either of them owning a second copy of that order.
    """
    from items.equipment.constants import SLOT_DISPLAY_ORDER

    rows = []

    for slot in SLOT_DISPLAY_ORDER:
        item = handler.slots.get(slot)

        if item is None:
            continue

        slot_value = str(slot.value)
        templates = (
            const.EQUIPMENT_ACTION_UNEQUIP,
            const.EQUIPMENT_ACTION_INSPECT,
        )
        actions = _build_actions(templates, item, 0, slot_value)
        row = _serialize_item(item, slot_value, actions)
        rows.append(row)

    return rows


# ─── Public routines ─────────────────────────────────────────────────────────

def build_payload(observer, ignore=None):
    """
    Purpose: Snapshot an observer's whole inventory and equipment.

    Entry:
        observer - a puppeted Character. One with no inventory handler (an NPC,
                   a half-built test object) is a supported case and yields an
                   empty payload rather than raising.
        ignore   - an object to omit from the snapshot even though the observer
                   still technically contains it, or None. Passed straight to
                   InventoryHandler.sync, which documents the one case that
                   needs it.

    Exit/Returns:
        Returns a CharItemsPayload, or None when the observer has no inventory
        handler at all. None means "there is nothing to say", and the caller
        skips the send.

    Module Globals:
        None.

    Methodology:
        sync() is called before reading. The handler is the owner of the grid,
        and it is the only thing that knows whether a slot points at an object
        that has since been deleted or moved -- reading `slots` without syncing
        first is how a snapshot ships an id that no longer resolves.

        `ignore` is threaded rather than filtered out afterwards, because the
        thing that must not see the departing object is sync() itself: its
        adoption loop would re-slot the item and persist that, so filtering the
        serialized rows would hide a bad payload while leaving the bad WRITE in
        place.

        The equipment handler is read directly, without a sync, because it
        holds object references rather than ids and has no equivalent repair
        pass.

    Notes/References:
        payloads.CharItemsPayload documents why this is a snapshot rather than
        a delta.

    Author: Nick Hobar
    Creation date: 08/15/2026
    """
    from items.inventory.handler import SLOTS_TOTAL

    from .payloads import CharItemsPayload

    inventory = getattr(observer, "inventory", None)

    if inventory is None:
        return None

    inventory.sync(ignore=ignore)
    carried = _serialize_carried(inventory)
    equipment = getattr(observer, "equipment", None)
    equipped = []

    if equipment is not None:
        equipped = _serialize_equipped(equipment)

    used = inventory.count_used()
    frames = _serialize_slot_frames()

    return CharItemsPayload(
        slots_total=SLOTS_TOTAL,
        slots_used=used,
        items=carried,
        equipped=equipped,
        equip_slots=frames,
    )
