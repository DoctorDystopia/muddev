
from items.equipment.constants import WieldLocation, MAX_INVENTORY_SLOTS
from items.equipment.handler import EquipmentError


TITLE_COLOR = "|w"
HIGHLIGHT_COLOR = "|y"
SUCCESS_COLOR = "|g"
ERROR_COLOR = "|r"
RESET_COLOR = "|n"
EQUIPPED_MARKER = "(equipped)"
SLOT_DISPLAY_ORDER = [
    WieldLocation.MAIN_HAND,
    WieldLocation.OFF_HAND,
    WieldLocation.TWO_HANDS,
    WieldLocation.HEAD,
    WieldLocation.BODY,
    WieldLocation.LEGS,
    WieldLocation.FEET,
    WieldLocation.BACK,
]



def _get_slot_label(slot: WieldLocation) -> str:
    label_map = {
        WieldLocation.MAIN_HAND: "Main Hand",
        WieldLocation.OFF_HAND: "Off Hand",
        WieldLocation.TWO_HANDS: "Two Hands",
        WieldLocation.HEAD: "Head",
        WieldLocation.BODY: "Body",
        WieldLocation.LEGS: "Legs",
        WieldLocation.FEET: "Feet",
        WieldLocation.BACK: "Back",
    }
    return label_map.get(slot, slot.value)



def start(caller: object, **kwargs) -> tuple:
    eq_handler = caller.equipment
    slots_data = eq_handler.slots

    text_lines = [f"{TITLE_COLOR}--- Equipment ---{RESET_COLOR}"]
    options_list = []

    for slot_key in SLOT_DISPLAY_ORDER:
        slot_label = _get_slot_label(slot_key)
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
    inventory_count = eq_handler.count_inventory()
    text_lines.append(
        f"{HIGHLIGHT_COLOR}Carrying {inventory_count}/{MAX_INVENTORY_SLOTS} items{RESET_COLOR}"
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
    eq_handler = caller.equipment
    inventory_items = list(caller.contents)

    text_lines = [f"{TITLE_COLOR}--- Inventory ---{RESET_COLOR}"]

    if not inventory_items:
        text_lines.append(f"{HIGHLIGHT_COLOR}You are not carrying anything.{RESET_COLOR}")
        text = "\n".join(text_lines)
        options = ({"desc": "Back to equipment overview", "goto": "start"},)
        return text, options

    options_list = []

    for item_obj in inventory_items:
        item_key = item_obj.key
        use_slot = getattr(item_obj, "inventory_use_slot", None)

        if use_slot is not None:
            slot_label = _get_slot_label(use_slot)
            desc_string = f"Equip {item_key} to {slot_label}"
            text_lines.append(f"  {HIGHLIGHT_COLOR}{item_key}{RESET_COLOR} -> {slot_label}")

            option_dict = {
                "desc": desc_string,
                "goto": ("node_equip_item", {"item_id": item_obj.id}),
            }
            options_list.append(option_dict)
        else:
            text_lines.append(f"  {item_key}")

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

    slot_label = _get_slot_label(slot_key)
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

    text = "\n".join(text_lines)
    options = ({"desc": "Back to equipment overview", "goto": "start"},)
    return text, options



def node_exit(caller: object, **kwargs) -> tuple:
    text = "Closing equipment menu."
    return text, None
