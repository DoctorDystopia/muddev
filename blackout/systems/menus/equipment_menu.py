"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: EvMenu nodes for the equipment screen: view slots, equip from
             inventory, unequip, inspect.
"""

from items.equipment.constants import (
    MAX_INVENTORY_SLOTS,
    SLOT_DISPLAY_ORDER,
    WieldLocation,
)
from items.equipment.handler import EquipmentError
from systems.combat.combat_msg import format_combat_stat_bonuses
from systems.ui.colors import (
    ERROR_COLOR,
    HIGHLIGHT_COLOR,
    RESET_COLOR,
    SUCCESS_COLOR,
    TITLE_COLOR,
)


EQUIPPED_MARKER = "(equipped)"



def start(caller: object, **kwargs) -> tuple:
    eq_handler = caller.equipment
    slots_data = eq_handler.slots

    text_lines = [f"{TITLE_COLOR}--- Equipment ---{RESET_COLOR}"]
    options_list = []

    for slot_key in SLOT_DISPLAY_ORDER:
        slot_label = slot_key.label
        slot_item = slots_data.get(slot_key)

        if slot_item is not None:
            item_key = slot_item.key
            slot_line = f"  {slot_label}: {SUCCESS_COLOR}{item_key}{RESET_COLOR} {EQUIPPED_MARKER}"
            text_lines.append(slot_line)

            option_dict = {
                "desc": f"Inspect {item_key} ({slot_label})",
                "goto": ("node_item_detail", {"item_id": slot_item.id, "slot": slot_key.value}),
            }
            options_list.append(option_dict)

            option_dict = {
                "desc": f"Unequip {item_key}",
                "goto": ("node_unequip", {"item_id": slot_item.id, "slot": slot_key.value}),
            }
            options_list.append(option_dict)
        else:
            slot_line = f"  {slot_label}: {HIGHLIGHT_COLOR}(empty){RESET_COLOR}"
            text_lines.append(slot_line)

    text_lines.append("")
    text_lines.append(f"{TITLE_COLOR}Total Combat Bonuses{RESET_COLOR}")
    total_bonuses = eq_handler.total_combat_stat_bonuses()
    bonus_lines = format_combat_stat_bonuses(total_bonuses)
    if bonus_lines:
        for bonus_line in bonus_lines:
            text_lines.append(f"  {bonus_line}")
    else:
        text_lines.append(f"  {HIGHLIGHT_COLOR}(none){RESET_COLOR}")

    text_lines.append("")
    inv_count = caller.inventory.count_used()
    text_lines.append(
        f"{HIGHLIGHT_COLOR}Carrying {inv_count}/{MAX_INVENTORY_SLOTS} slots{RESET_COLOR}"
    )
    text = "\n".join(text_lines)

    inventory_cmd = {
        "desc": "Open inventory to equip items",
        "goto": "node_inventory",
    }
    options_list.append(inventory_cmd)
    options_list.append({"desc": "Exit equipment menu", "goto": "node_exit"})

    return text, tuple(options_list)



def node_inventory(caller: object, **kwargs) -> tuple:
    from items.inventory.display import render_grid

    handler = caller.inventory
    handler.sync()

    title, grid_str = render_grid(handler)
    text_lines = [
        f"{TITLE_COLOR}--- Inventory ---{RESET_COLOR}",
        grid_str,
    ]

    items = handler.all_items()
    if not items:
        text_lines.append(f"{HIGHLIGHT_COLOR}You are not carrying anything.{RESET_COLOR}")
        text = "\n".join(text_lines)
        options = ({"desc": "Back to equipment overview", "goto": "start"},)
        return text, options

    options_list = []

    for slot_idx, item_obj in items:
        item_key = item_obj.key
        use_slot = getattr(item_obj, "inventory_use_slot", None)
        qty = getattr(item_obj, "quantity", 1)
        qty_str = f" (x{qty})" if qty > 1 and getattr(item_obj, "is_stackable", False) else ""

        if use_slot is not None:
            slot_label = use_slot.label
            desc_string = f"Equip {item_key}{qty_str} to {slot_label}"
            text_lines.append(f"  [{slot_idx+1}] {HIGHLIGHT_COLOR}{item_key}{RESET_COLOR}{qty_str} -> {slot_label}")
            options_list.append({
                "desc": desc_string,
                "goto": ("node_equip_item", {"item_id": item_obj.id}),
            })
        else:
            text_lines.append(f"  [{slot_idx+1}] {item_key}{qty_str}")
            options_list.append({
                "desc": f"Select {item_key}{qty_str}",
                "goto": ("node_item_detail_inv", {"item_id": item_obj.id}),
            })

    text = "\n".join(text_lines)
    options_list.append({"desc": "Back to equipment overview", "goto": "start"})
    return text, tuple(options_list)



def node_equip_item(caller: object, **kwargs) -> tuple:
    item_id = kwargs.get("item_id")

    target_item = None
    for obj in caller.contents:
        if obj.id == item_id:
            target_item = obj
            break

    if target_item is None:
        text = f"{ERROR_COLOR}That item is no longer in your inventory.{RESET_COLOR}"
        options = ({"desc": "Back to inventory", "goto": "node_inventory"},)
        return text, options

    try:
        caller.equipment.equip(target_item)
        item_key = target_item.key
        text = f"{SUCCESS_COLOR}You equip {item_key}.{RESET_COLOR}"
    except EquipmentError as equip_err:
        error_text = str(equip_err)
        text = f"{ERROR_COLOR}{error_text}{RESET_COLOR}"

    options = ({"desc": "Back to equipment overview", "goto": "start"},)
    return text, options



def node_unequip(caller: object, **kwargs) -> tuple:
    slot_value = kwargs.get("slot")
    item_id = kwargs.get("item_id")

    eq_handler = caller.equipment
    slots_data = eq_handler.slots

    try:
        slot_key = WieldLocation(slot_value)
    except ValueError:
        text = f"{ERROR_COLOR}Invalid equipment slot.{RESET_COLOR}"
        options = ({"desc": "Back to equipment overview", "goto": "start"},)
        return text, options

    current_item = slots_data.get(slot_key)

    if current_item is None or current_item.id != item_id:
        text = f"{ERROR_COLOR}That item is no longer equipped.{RESET_COLOR}"
        options = ({"desc": "Back to equipment overview", "goto": "start"},)
        return text, options

    try:
        eq_handler.unequip(slot_key)
        item_key = current_item.key
        text = f"{SUCCESS_COLOR}You unequip {item_key}.{RESET_COLOR}"
    except EquipmentError as err:
        text = f"{ERROR_COLOR}{err}{RESET_COLOR}"

    options = ({"desc": "Back to equipment overview", "goto": "start"},)
    return text, options



def node_item_detail(caller: object, **kwargs) -> tuple:
    slot_value = kwargs.get("slot")
    item_id = kwargs.get("item_id")

    eq_handler = caller.equipment
    slots_data = eq_handler.slots

    slot_key = WieldLocation(slot_value)
    item_obj = slots_data.get(slot_key)

    if item_obj is None or item_obj.id != item_id:
        text = f"{HIGHLIGHT_COLOR}That item is no longer equipped.{RESET_COLOR}"
        options = ({"desc": "Back to equipment overview", "goto": "start"},)
        return text, options

    slot_label = slot_key.label
    item_desc = item_obj.db.desc or "No description available."

    text_lines = [
        f"{TITLE_COLOR}--- {item_obj.key} ---{RESET_COLOR}",
        f"Slot: {slot_label}",
        f"Description: {item_desc}",
    ]

    tool_type = item_obj.db.tool_type
    if tool_type:
        tier_value = item_obj.db.tier or 0
        req_level = item_obj.db.req_level or 0
        text_lines.append(f"Tool: {tool_type} (Tier {tier_value}, Req. Level {req_level})")

    item_bonuses = item_obj.db.combat_stat_bonuses
    if item_bonuses:
        bonus_lines = format_combat_stat_bonuses(item_bonuses)
        if bonus_lines:
            text_lines.append(f"{TITLE_COLOR}Combat Bonuses:{RESET_COLOR}")
            for bonus_line in bonus_lines:
                text_lines.append(f"  {bonus_line}")

    text = "\n".join(text_lines)
    options = ({"desc": "Back to equipment overview", "goto": "start"},)
    return text, options



def node_item_detail_inv(caller: object, **kwargs) -> tuple:
    item_id = kwargs.get("item_id")

    target_item = None
    for obj in caller.contents:
        if obj.id == item_id:
            target_item = obj
            break

    if target_item is None:
        text = f"{ERROR_COLOR}That item is no longer in your inventory.{RESET_COLOR}"
        options = ({"desc": "Back to inventory", "goto": "node_inventory"},)
        return text, options

    slot_idx = caller.inventory.find_slot(target_item)
    item_desc = target_item.db.desc or "No description available."
    qty = getattr(target_item, "quantity", 1)
    stackable = getattr(target_item, "is_stackable", False)

    lines = [
        f"{TITLE_COLOR}--- {target_item.key} ---{RESET_COLOR}",
        f"Slot: {slot_idx + 1 if slot_idx >= 0 else 'N/A'}",
        f"Description: {item_desc}",
    ]
    if stackable:
        lines.append(f"Quantity: {qty}")
    if target_item.attributes.get("value", 0):
        lines.append(f"Value: {target_item.attributes.get('value', 0)} credits")

    tool_type = target_item.db.tool_type
    if tool_type:
        tier_value = target_item.db.tier or 0
        req_level = target_item.db.req_level or 0
        lines.append(f"Tool: {tool_type} (Tier {tier_value}, Req. Level {req_level})")

    item_bonuses = target_item.db.combat_stat_bonuses
    if item_bonuses:
        bonus_lines = format_combat_stat_bonuses(item_bonuses)
        if bonus_lines:
            lines.append(f"{TITLE_COLOR}Combat Bonuses:{RESET_COLOR}")
            for bonus_line in bonus_lines:
                lines.append(f"  {bonus_line}")

    text = "\n".join(lines)
    options = ({"desc": "Back to inventory", "goto": "node_inventory"},)
    return text, options


def node_exit(caller: object, **kwargs) -> tuple:
    text = "Closing equipment menu."
    return text, None
