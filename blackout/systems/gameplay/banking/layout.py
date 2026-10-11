"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/08/2026
Description: The vault layout: the tabs, the order of the slots in each tab,
             the name of each tab, and the placeholders. The OSRS bank is the
             model.

             PURE DATA. Nothing here touches the database or Evennia. The bank
             handler reads the record from one Attribute, gives it to these
             routines, and writes it back. Thus, every rule of the layout has
             a test that needs no database.

             ONE SLOT IS ONE ITEM NAME, the vault's own rule
             (BankHandler.used_slots). A slot is a lowercased item key. Eleven
             scrap plates are eleven objects and one slot.

             THE MAIN TAB IS TAB 0. It holds every item that is in no other
             tab. The main view shows the main tab's own items first, then
             tab 1, tab 2, and so on. A tab that becomes empty disappears,
             and the tabs after it move down one number. A placeholder keeps
             its tab, so a tab of placeholders stays.

             THE STORED OBJECTS ARE THE TRUTH. reconcile() fits the layout to
             what the vault holds. A name that is new gets a slot. A name that
             left becomes a placeholder or loses its slot. So an item that
             reaches the vault by any route gets a slot, and the layout can
             never show an item that is not there.
"""

from dataclasses import dataclass, field

from . import constants as bank_const


# ─── Public classes ──────────────────────────────────────────────────────────

@dataclass
class VaultLayout:
    """
    The layout of one vault.

    tabs              - one list of slot names for each tab. tabs[0] is the
                        main tab. Each name is in exactly one tab.
    names             - the text name of each tab, parallel to `tabs`. ""
                        means the tab shows the icon of its first item.
    meta              - slot name -> {key, prototype, placeholder}. The
                        display key and the prototype key outlive the item, so
                        a placeholder can draw its name and its mesh.
    viewed            - the tab the player looks at. A new item name goes into
                        this tab.
    keep_placeholders - True when the last unit to leave leaves a placeholder.
    """

    tabs: list = field(default_factory=lambda: [[]])
    names: list = field(default_factory=lambda: [""])
    meta: dict = field(default_factory=dict)
    viewed: int = bank_const.MAIN_TAB
    keep_placeholders: bool = bank_const.PLACEHOLDERS_DEFAULT


# ─── Private helper routines ─────────────────────────────────────────────────

def _string_list(raw) -> list:
    """Return the strings of `raw` as a list, or [] for anything else."""
    if not isinstance(raw, (list, tuple)):
        return []

    return [str(entry) for entry in raw if isinstance(entry, str)]


def _clean_tabs(raw) -> list:
    """Return the stored tabs with each name in one tab only.

    A record that a bug or an old build wrote can hold a name twice. The
    first tab that holds it keeps it.
    """
    tabs = []
    seen = set()

    for raw_tab in raw if isinstance(raw, (list, tuple)) else []:
        tab = []

        for name in _string_list(raw_tab):
            if name not in seen:
                seen.add(name)
                tab.append(name)

        tabs.append(tab)

    if not tabs:
        tabs.append([])

    return tabs


def _fit_names(raw, count: int) -> list:
    """Return `count` tab names: the stored ones, padded with "" or cut."""
    names = _string_list(raw)[:count]
    names.extend([""] * (count - len(names)))

    return names


def _drop_empty_tabs(layout: VaultLayout) -> None:
    """
    Purpose: Remove each player tab that holds no slot.

    Entry:
        layout - the layout to change.

    Exit/Returns:
        Returns nothing. Changes `layout` in place.

    Module Globals:
        bank_const.MAIN_TAB, bank_const.FIRST_TAB read.

    Methodology:
        Walk from the last tab down, so a removal does not move a tab that is
        not checked yet. Keep the viewed tab on the same tab: a removal before
        it moves it down one, and the removal of the tab itself shows the main
        tab.

    Notes/References:
        The main tab is never removed. It is where an untabbed item lives.

    Author: Nick Hobar
    Creation date: 10/08/2026
    """
    for index in range(len(layout.tabs) - 1, bank_const.FIRST_TAB - 1, -1):
        if layout.tabs[index]:
            continue

        del layout.tabs[index]
        del layout.names[index]

        if layout.viewed == index:
            layout.viewed = bank_const.MAIN_TAB
        elif layout.viewed > index:
            layout.viewed -= 1


def _position_of(layout: VaultLayout, name: str) -> tuple:
    """Return (tab, index) of one slot name, or (-1, -1) when it has none."""
    for tab_index, tab in enumerate(layout.tabs):
        if name in tab:
            return tab_index, tab.index(name)

    return -1, -1


def _remember_present(layout: VaultLayout, present: dict) -> None:
    """Write the display key and prototype of each stored name into meta."""
    for name, (display, prototype) in present.items():
        layout.meta[name] = {
            bank_const.META_KEY: str(display),
            bank_const.META_PROTOTYPE: str(prototype),
            bank_const.META_PLACEHOLDER: False,
        }


def _keeps_slot(layout: VaultLayout, name: str, present: dict) -> bool:
    """
    Purpose: Decide whether one slot name stays in the layout.

    Entry:
        layout  - the layout. Its meta for `name` may change.
        name    - one slot name of the layout.
        present - the stored names, as reconcile() takes them.

    Exit/Returns:
        Returns True when the slot stays.

    Module Globals:
        bank_const.META_PLACEHOLDER read.

    Methodology:
        1. A stored name stays.
        2. A placeholder stays. It goes only when the player releases it.
        3. A name that left since the last fit becomes a placeholder when the
           vault keeps them. Else it loses its slot.

    Notes/References:
        Step 3 reads the meta flag that the last fit wrote. False there means
        "stored at the last fit", so the name just left.

    Author: Nick Hobar
    Creation date: 10/08/2026
    """
    if name in present:
        return True

    entry = layout.meta.get(name)

    if entry is None:
        return False

    if entry.get(bank_const.META_PLACEHOLDER, False):
        return True

    if not layout.keep_placeholders:
        return False

    entry[bank_const.META_PLACEHOLDER] = True

    return True


def _home_tab(layout: VaultLayout, new_tab: int) -> int:
    """Return the tab a new name goes into: `new_tab` if it exists, else main."""
    if bank_const.FIRST_TAB <= new_tab < len(layout.tabs):
        return new_tab

    return bank_const.MAIN_TAB


# ─── Public routines ─────────────────────────────────────────────────────────

def from_record(record) -> VaultLayout:
    """
    Purpose: Read a stored layout record, and repair what is wrong with it.

    Entry:
        record - the dict that to_record() gave, or None for a vault with no
                 layout yet.

    Exit/Returns:
        Returns a VaultLayout. Never raises.

    Module Globals:
        bank_const.RECORD_* read.

    Methodology:
        Read each field with a default, then make the fields agree: one name
        per tab, one tab name per tab, and a viewed tab that exists.

    Notes/References:
        Give this plain Python. An Evennia Attribute gives back a _SaverDict,
        which is not a dict, so the handler deserializes the record first.
        The copies here make sure that a change to the layout writes nothing
        until the handler saves.

    Author: Nick Hobar
    Creation date: 10/08/2026
    """
    if not isinstance(record, dict):
        record = {}

    tabs = _clean_tabs(record.get(bank_const.RECORD_TABS))
    names = _fit_names(record.get(bank_const.RECORD_NAMES), len(tabs))
    raw_meta = record.get(bank_const.RECORD_META)
    meta = {}

    if isinstance(raw_meta, dict):
        meta = {str(name): dict(entry) for name, entry in raw_meta.items()
                if isinstance(entry, dict)}

    viewed = record.get(bank_const.RECORD_VIEWED, bank_const.MAIN_TAB)

    if not isinstance(viewed, int) or not 0 <= viewed < len(tabs):
        viewed = bank_const.MAIN_TAB

    keep = record.get(bank_const.RECORD_KEEP, bank_const.PLACEHOLDERS_DEFAULT)

    return VaultLayout(tabs, names, meta, viewed, bool(keep))


def to_record(layout: VaultLayout) -> dict:
    """Return the layout as a plain dict for one Attribute."""
    return {
        bank_const.RECORD_TABS: [list(tab) for tab in layout.tabs],
        bank_const.RECORD_NAMES: list(layout.names),
        bank_const.RECORD_META: {name: dict(entry)
                                 for name, entry in layout.meta.items()},
        bank_const.RECORD_VIEWED: int(layout.viewed),
        bank_const.RECORD_KEEP: bool(layout.keep_placeholders),
    }


def reconcile(layout: VaultLayout, present: dict, new_tab: int) -> None:
    """
    Purpose: Fit the layout to what the vault holds.

    Entry:
        layout  - the layout to change.
        present - stored slot name -> (display key, prototype key), in the
                  order the vault lists its objects.
        new_tab - the tab a name that is new goes into. The viewed tab, as in
                  OSRS.

    Exit/Returns:
        Returns nothing. Changes `layout` in place.

    Module Globals:
        None.

    Methodology:
        1. Write the meta of each stored name.
        2. Keep each slot that _keeps_slot allows, in its place.
        3. Put each stored name with no slot at the end of the home tab.
        4. Remove each empty tab, and the meta of each name with no slot.

    Notes/References:
        The handler calls this before each read and each change. A deposit,
        a withdrawal, and a test that moves an object into the vault room all
        reach the layout through it.

    Author: Nick Hobar
    Creation date: 10/08/2026
    """
    _remember_present(layout, present)

    for index, tab in enumerate(layout.tabs):
        layout.tabs[index] = [name for name in tab
                              if _keeps_slot(layout, name, present)]

    home = _home_tab(layout, new_tab)
    placed = set(ordered_names(layout))

    for name in present:
        if name not in placed:
            layout.tabs[home].append(name)

    _drop_empty_tabs(layout)
    kept = set(ordered_names(layout))
    layout.meta = {name: entry for name, entry in layout.meta.items()
                   if name in kept}


def ordered_names(layout: VaultLayout) -> list:
    """Return every slot name in main-view order: the main tab's own names
    first, then tab 1, tab 2, and so on."""
    ordered = list(layout.tabs[bank_const.MAIN_TAB])

    for tab in layout.tabs[bank_const.FIRST_TAB:]:
        ordered.extend(tab)

    return ordered


def tab_of(layout: VaultLayout, name: str) -> int:
    """Return the tab number that holds `name`, or -1."""
    tab_index, _index = _position_of(layout, name)

    return tab_index


def is_placeholder(layout: VaultLayout, name: str) -> bool:
    """Return True when `name` is a slot with no stored item."""
    entry = layout.meta.get(name, {})

    return bool(entry.get(bank_const.META_PLACEHOLDER, False))


def placeholder_names(layout: VaultLayout) -> list:
    """Return the placeholder slot names, in main-view order."""
    return [name for name in ordered_names(layout)
            if is_placeholder(layout, name)]


def display_key(layout: VaultLayout, name: str) -> str:
    """Return the item key a slot shows, or the slot name itself."""
    entry = layout.meta.get(name, {})

    return str(entry.get(bank_const.META_KEY, name))


def resolve(layout: VaultLayout, needle: str) -> str:
    """
    Return the slot name that `needle` names, or "".

    An exact name first, then the first slot in main-view order that starts
    with it. The rule of BankHandler.find_items_by_name, but over the slots,
    so a placeholder can be named too.
    """
    wanted = str(needle).strip().lower()

    if not wanted:
        return ""

    ordered = ordered_names(layout)

    if wanted in ordered:
        return wanted

    for name in ordered:
        if name.startswith(wanted):
            return name

    return ""


def move(layout: VaultLayout, name: str, target: int) -> bool:
    """
    Purpose: Move one slot to the end of a tab, or into a new tab.

    Entry:
        layout - the layout to change.
        name   - a slot name of the layout.
        target - a tab number. len(layout.tabs) makes a new tab.
                 bank_const.MAIN_TAB takes the slot out of its tab.

    Exit/Returns:
        Returns True when the slot moved.

    Module Globals:
        None.

    Methodology:
        1. Refuse a name with no slot, and a tab past the new-tab number.
        2. Make the new tab if the target asks for it.
        3. Take the slot out, put it at the end of the target, and remove a
           tab that the move made empty.

    Notes/References:
        A move into the tab that holds the slot puts it at the end of that
        tab. OSRS does the same for a drop on the own tab.

    Author: Nick Hobar
    Creation date: 10/08/2026
    """
    current = tab_of(layout, name)

    if current < 0 or not 0 <= target <= len(layout.tabs):
        return False

    if target == len(layout.tabs):
        layout.tabs.append([])
        layout.names.append("")

    layout.tabs[current].remove(name)
    layout.tabs[target].append(name)
    _drop_empty_tabs(layout)

    return True


def swap(layout: VaultLayout, first: str, second: str) -> bool:
    """Swap the places of two slots, in one tab or across two. Returns True
    when they moved. Across two tabs, each item takes the tab of the other."""
    first_tab, first_index = _position_of(layout, first)
    second_tab, second_index = _position_of(layout, second)

    if first_tab < 0 or second_tab < 0 or first == second:
        return False

    layout.tabs[first_tab][first_index] = second
    layout.tabs[second_tab][second_index] = first

    return True


def clean_tab_name(text: str) -> str:
    """Return a tab name the game can show: letters, digits and the
    characters of TAB_NAME_EXTRA_CHARACTERS, one space between words, and no
    longer than TAB_NAME_MAX_LENGTH."""
    allowed = [char for char in str(text)
               if char.isalnum() or char in bank_const.TAB_NAME_EXTRA_CHARACTERS]
    words = "".join(allowed).split()
    joined = " ".join(words)

    return joined[:bank_const.TAB_NAME_MAX_LENGTH].strip()


def rename(layout: VaultLayout, index: int, text: str) -> bool:
    """Give one tab a text name, or "" to show its item icon again. Returns
    False for a tab that does not exist."""
    if not 0 <= index < len(layout.tabs):
        return False

    layout.names[index] = clean_tab_name(text)

    return True


def set_view(layout: VaultLayout, index: int) -> bool:
    """Look at one tab. Returns False for a tab that does not exist."""
    if not 0 <= index < len(layout.tabs):
        return False

    layout.viewed = index

    return True


def release(layout: VaultLayout, name: str) -> bool:
    """Remove one placeholder and free its slot. Returns False for a name
    that is not a placeholder: a stored item keeps its slot."""
    if not is_placeholder(layout, name):
        return False

    layout.tabs[tab_of(layout, name)].remove(name)
    layout.meta.pop(name, None)
    _drop_empty_tabs(layout)

    return True


def release_all(layout: VaultLayout) -> int:
    """Remove every placeholder. Returns how many slots it freed."""
    names = placeholder_names(layout)

    for name in names:
        release(layout, name)

    return len(names)
