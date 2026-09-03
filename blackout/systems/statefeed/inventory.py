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

from . import commerce
from . import constants as const
from .serializers import _classify, _item_family


# ─── Private helper routines ─────────────────────────────────────────────────

def _prompted_action(label: str, template: str, prompt: str, maximum: int) -> dict:
    """
    Purpose: Render one action whose amount only the client knows.

    Entry:
        label    - the menu entry's text, e.g. "Sell X".
        template - the server's spelling, carrying ACTION_AMOUNT_PLACEHOLDER.
        prompt   - what the quantity box asks.
        maximum  - the largest amount this row can supply.

    Exit/Returns:
        A dict carrying an EMPTY `command`, plus `template` and `input`.

    Module Globals:
        const.ACTION_INPUT_* read.

    Methodology:
        The empty command is the whole safety property. Both clients already
        read "" as "the server declines", so a client that has not learned
        about `input` shows the entry and does nothing -- rather than sending
        a literal "{amount}" at the parser, which is what a non-empty command
        carrying the placeholder would have done.

        The client learns "an action with an `input` asks first" ONCE. Deposit
        X, and a future Drop X, are then free.

    Notes/References:
        INVENTORY_SWAP_TEMPLATE documents the same split for a drag: the
        server owns the spelling, the client composes the one value it holds.

    Author: Nick Hobar
    Creation date: 09/02/2026
    """
    return {
        "label": str(label),
        "command": "",
        "template": str(template),
        "input": {
            const.ACTION_INPUT_KIND_KEY: const.ACTION_INPUT_KIND_QUANTITY,
            const.ACTION_INPUT_MIN_KEY: const.ACTION_INPUT_MIN_AMOUNT,
            const.ACTION_INPUT_MAX_KEY: int(maximum),
            const.ACTION_INPUT_LABEL_KEY: str(prompt),
        },
    }


def _commerce_actions(item, slot_number: int, equip_slot: str, context,
                      units: int) -> list:
    """
    Purpose: Render the Sell and Deposit entries a carried row affords right
             now.

    Entry:
        item        - the live object.
        slot_number - its 1-based grid position.
        equip_slot  - the WieldLocation value it would occupy, or "".
        context     - the CommerceContext for the observer's room.
        units       - how many units of this item the character carries in
                      total, across every slot holding one.

    Exit/Returns:
        A list of action dicts, empty when the room offers nothing.

    Module Globals:
        const.INVENTORY_ACTION_SELL* read.
        const.INVENTORY_ACTION_DEPOSIT* read.

    Methodology:
        Three rules, and each of them is somebody else's fact read once here.

        SELL APPEARS ONLY WHEN THE SHOP WOULD BUY IT. That is
        shop_service._is_sellable, the same predicate the shop's own sell list
        is filtered by -- so the shop refusing an item and the pane not
        offering to sell it are one fact, not two that can disagree.

        DEPOSIT APPEARS WHENEVER A TERMINAL IS HERE. A full vault is a runtime
        failure with its own message, not an absent action: an action that
        vanishes when the vault fills teaches the player nothing about why.

        A SINGLE UNIT OFFERS ONE VERB, NOT THREE. Nobody wants "Sell All" on
        one sword. The count that decides this is `units` -- what the whole
        GROUP holds -- so eight separate rusty metal chunks each offer 1 / X /
        All even though no one of them is a stack.

    Notes/References:
        The import is function-level because shop_service pulls in ITEM_DB and
        SHOP_DB, and this module is imported by every inventory snapshot on a
        server that may have no shop on any map.

    Author: Nick Hobar
    Creation date: 09/02/2026
    """
    from systems.shop.shop_service import _is_sellable

    actions = []

    if context.shopkeep is not None and _is_sellable(item):
        actions.extend(_quantity_group(
            item,
            slot_number,
            equip_slot,
            units,
            one=const.INVENTORY_ACTION_SELL_ONE,
            some_label=const.INVENTORY_ACTION_SELL_SOME_LABEL,
            some_template=const.INVENTORY_SELL_SOME_TEMPLATE,
            prompt=const.ACTION_PROMPT_SELL,
            every=const.INVENTORY_ACTION_SELL_ALL,
            single=const.INVENTORY_ACTION_SELL,
        ))

    if context.bank is not None:
        actions.extend(_quantity_group(
            item,
            slot_number,
            equip_slot,
            units,
            one=const.INVENTORY_ACTION_DEPOSIT_ONE,
            some_label=const.INVENTORY_ACTION_DEPOSIT_SOME_LABEL,
            some_template=const.INVENTORY_DEPOSIT_SOME_TEMPLATE,
            prompt=const.ACTION_PROMPT_DEPOSIT,
            every=const.INVENTORY_ACTION_DEPOSIT_ALL,
            single=const.INVENTORY_ACTION_DEPOSIT,
        ))

    return actions


def _quantity_group(item, slot_number, equip_slot, units, one, some_label,
                    some_template, prompt, every, single) -> list:
    """Render one verb as either a bare action or a 1 / X / All group.

    THE SPLIT IS ON `units`, NOT ON THE ROW'S `quantity`, and the two are
    different numbers on purpose. A row's quantity is what the pane draws in
    the corner of that frame; for one of eight separate rusty metal chunks it
    is 1, and printing 8 on all eight cells would tell the player they have
    sixty-four. `units` is what a group verb can actually reach -- eight --
    which is the bound the prompt needs and the reason a non-stackable gets
    the three-verb group at all.

    They coincide for a stackable held in one stack, which is every stackable
    in practice.
    """
    if units <= const.ACTION_QUANTITY_SINGLE:
        return _build_actions((single,), item, slot_number, equip_slot)

    actions = _build_actions((one,), item, slot_number, equip_slot)
    # Substitutes the slot and leaves the amount token standing, because the
    # amount is the one value the CLIENT holds. Formatting the placeholder
    # back into itself rather than splicing a literal "{slot}" is what keeps
    # ACTION_AMOUNT_PLACEHOLDER the single owner of the token's spelling.
    template = some_template.format(
        slot=slot_number, amount=const.ACTION_AMOUNT_PLACEHOLDER)
    actions.append(_prompted_action(some_label, template, prompt, units))
    actions.extend(_build_actions((every,), item, slot_number, equip_slot))

    return actions

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


def _units_by_key(occupied) -> dict:
    """
    Purpose: Total the units of each distinct item the grid holds.

    Entry:
        occupied - InventoryHandler.all_items()'s (slot index, object) pairs.

    Exit/Returns:
        A dict of lowercased item key -> total units carried.

    Module Globals:
        None.

    Methodology:
        ONE PASS FOR THE WHOLE PAYLOAD. This is the same total
        commands/inventory_cmds.group_units computes for one item, and it is
        computed here rather than called per row because that routine walks
        the grid itself -- thirty-two rows asking it would be a thousand slot
        reads to answer a question one pass answers.

        Keyed on the lowercased key, matching carried_group's grouping rule
        and get_sell_items' and _find_carried_group's before it. What the
        prompt offers and what the command consumes have to be the same group.

    Notes/References:
        This is NOT a row's `quantity` field, which stays per object -- see
        _quantity_group on why conflating them says the player has sixty-four
        chunks.

    Author: Nick Hobar
    Creation date: 09/02/2026
    """
    totals = {}

    for _slot_index, item in occupied:
        if item is None:
            continue

        key = str(item.key).lower()
        quantity = max(0, int(getattr(item, "quantity", 1) or 1))
        totals[key] = totals.get(key, 0) + quantity

    return totals


def _serialize_carried(handler, context) -> list:
    """Render every occupied slot in the 32-slot grid.

    Empty slots are OMITTED rather than sent as nulls. The client is told
    slots_total and draws that many frames; a list of only the occupied ones is
    smaller, and means a stale id that _load has already nulled cannot reach
    the client as a row of defaults.

    Order is Equip, then the commerce group, then Inspect and Drop. Commerce
    sits ABOVE Drop on purpose: Drop is the destructive neighbour and it
    should stay at the bottom, where the hand expects it.
    """
    rows = []
    occupied = handler.all_items()
    units_by_key = _units_by_key(occupied)

    for slot_index, item in occupied:
        if item is None:
            continue

        slot_number = slot_index + 1
        equip_slot = _equip_slot_value(item)
        units = units_by_key.get(str(item.key).lower(), 1)
        leading = []

        if equip_slot:
            leading.append(const.INVENTORY_ACTION_EQUIP)

        actions = _build_actions(leading, item, slot_number, equip_slot)
        actions.extend(
            _commerce_actions(item, slot_number, equip_slot, context, units))
        actions.extend(_build_actions(
            (const.INVENTORY_ACTION_INSPECT, const.INVENTORY_ACTION_DROP),
            item, slot_number, equip_slot,
        ))
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


def _serialize_equipped(handler, context) -> list:
    """Render every occupied equipment slot, in display order.

    Walks SLOT_DISPLAY_ORDER rather than the handler's dict, so the pane's
    paper doll and the text equipment screen list slots in the same order
    without either of them owning a second copy of that order.

    A worn row gets DEPOSIT and never SELL. `deposit` reaches an equipped
    item -- it clears the slot before banking, which is what CmdDeposit's
    docstring has always promised -- and an unequipped deposit is undone by
    `withdraw`. A sale at the miser factor is not, and worn gear is exactly
    what a misclick most wants back.

    It is addressed by NAME rather than by slot, because `deposit` reads a
    name against the equipment handler too and an equipped row has no grid
    number to give it.
    """
    from items.equipment.constants import SLOT_DISPLAY_ORDER

    rows = []

    for slot in SLOT_DISPLAY_ORDER:
        item = handler.slots.get(slot)

        if item is None:
            continue

        slot_value = str(slot.value)
        templates = [const.EQUIPMENT_ACTION_UNEQUIP]

        if context.bank is not None:
            templates.append(const.EQUIPMENT_ACTION_DEPOSIT)

        templates.append(const.EQUIPMENT_ACTION_INSPECT)
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
    # ONCE per payload, not once per row. Asked per item this would be a room
    # scan for each of up to thirty-two rows, on the most expensive payload
    # the feed builds.
    context = commerce.build_context(observer)
    carried = _serialize_carried(inventory, context)
    equipment = getattr(observer, "equipment", None)
    equipped = []

    if equipment is not None:
        equipped = _serialize_equipped(equipment, context)

    used = inventory.count_used()
    frames = _serialize_slot_frames()

    return CharItemsPayload(
        slots_total=SLOTS_TOTAL,
        slots_used=used,
        items=carried,
        equipped=equipped,
        equip_slots=frames,
    )
