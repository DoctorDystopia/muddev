# Welcome to Evennia!

This is your game directory, set up to let you start with
your new game right away. An overview of this directory is found here:
https://github.com/evennia/evennia/wiki/Directory-Overview#the-game-directory

You can delete this readme file when you've read it and you can
re-arrange things in this game-directory to suit your own sense of
organisation (the only exception is the directory structure of the
`server/` directory, which Evennia expects). If you change the structure
you must however also edit/add to your settings file to tell Evennia
where to look for things.

Your game's main configuration file is found in
`server/conf/settings.py` (but you don't need to change it to get
started). If you just created this directory (which means you'll already
have a `virtualenv` running if you followed the default instructions),
`cd` to this directory then initialize a new database using

    evennia migrate

To start the server, stand in this directory and run

    evennia start

This will start the server, logging output to the console. Make
sure to create a superuser when asked. By default you can now connect
to your new game using a MUD client on `localhost`, port `4000`.  You can
also log into the web client by pointing a browser to
`http://localhost:4001`.

# Getting started

From here on you might want to look at one of the beginner tutorials:
http://github.com/evennia/evennia/wiki/Tutorials.

Evennia's documentation is here:
https://github.com/evennia/evennia/wiki.

Enjoy!

---

# BLACKOUT Game Documentation

> **Blackout** is a cyberpunk MUD built on Evennia with the XYZGrid
> contrib for tiled overworld maps. It features a skill-progression and
> crafting-economy loop: gather raw materials from the world, process them at
> facilities, forge tools, and bank your haul.
>
> For first-time setup (cloning, venv, pip install), see the [root README](../README.md).

**Table of Contents**
- [Item Database — Bulk Creation & Management](#item-database-bulk-creation--management)
- [Character & Progression](#character--progression)
- [Equipment System](#equipment-system)
- [Combat System](#combat-system)
- [Banking System](#banking-system)
- [Crafting System](#crafting-system)
- [Admin Commands](#admin-commands)
- [Map Building Workflow](#map-building-workflow)
- [Troubleshooting: The Nuclear Option](#troubleshooting-the-nuclear-option)
- [Scripts & Automation](#scripts--automation)
- [Running Tests](#running-tests)
- [Quick Reference — Python One-Liners](#quick-reference--python-one-liners)

---

## Item Database — Bulk Creation & Management

All items are registered in the `ITEM_DB` dict (`world/item_database.py`) and
created via the `ItemDef.create()` method. This is the canonical way to spawn
items in the world.

### List all registered items

```python
> py from world.item_database import ITEM_DB; [f"{k}: {v.name}" for k, v in ITEM_DB.items()]

rusty_metal_chunk: Rusty Metal Chunk
rusty_metal_dust: Rusty Metal Dust
rusty_scrap_metal: Rusty Scrap Metal
rusty_scrap_axe: Rusty Scrap Axe
hammer: Hammer
```

### Create a single item in your inventory

```python
> py ITEM_DB["rusty_metal_chunk"].create(location=self)

You see a Rusty Metal Chunk appear in your inventory.
```

### Create N items at once

```python
> py [ITEM_DB["rusty_metal_chunk"].create(location=self) for _ in range(15)]

Creates 15 Rusty Metal Chunks in your inventory.
```

### Create items at a specific room or on another character

```python
> py room = self.search("#42"); ITEM_DB["rusty_scrap_axe"].create(location=room)

> py target = self.search("testchar2"); ITEM_DB["hammer"].create(location=target)
```

### Quick item give (one-liner)

```python
> py ITEM_DB["rusty_metal_chunk"].create(location=self.search("bob"))
```

### Create a raw typeclass object (not in ITEM_DB)

```bash
> create/drop Rusty Pole:typeclasses.gathering_nodes.RustyPole
```

### Registering a new item

1. Add an `ItemDef` entry in `world/item_defs/<category>.py` (e.g., `materials.py`, `tools.py`).
2. Restart/reload the server. The new item automatically appears in `ITEM_DB`.

```python
# world/item_defs/materials.py — example entry
ITEMS = {
    "my_new_material": ItemDef(
        key="my_new_material",
        name="My New Material",
        desc="A freshly defined crafting material.",
        value=3,
        weight=1.5,
        tags=[("my_new_material", "crafting_material")],
    ),
}
```

---

## Character & Progression

### Refresh all characters

Re-runs `at_object_creation()` on every character in the database. Useful after
adding new handler properties to the Character typeclass.

```python
> py from typeclasses.characters import Character; [char.at_object_creation() for char in Character.objects.all()]
```

### Grant XP to a skill

```bash
> addxp testchar cutting 500

Successfully granted 500 XP to testchar's cutting skill.
```

The skill key must match a key in `SKILL_REGISTRY`:

| Category | Keys |
|---|---|
| Gathering | `cutting`, `brain_farming` |
| Processing | `foundry` |
| Production | `metalsmith` |
| Combat | `strike`, `brawn`, `defense`, `fortitude` |

`systems/progression/skills/registry.py` **discovers these automatically** by
walking `skill_defs/`. To add a skill, drop one module in the right category
directory with a `BaseSkill` subclass carrying a unique `key` — there is no
registry list to edit. A passive skill needs nothing but its four class
attributes; `get_unlock_requirements` and `execute` already default correctly on
`BaseSkill`.

```python
> py from systems.progression.skills.registry import SKILL_REGISTRY; sorted(SKILL_REGISTRY)
['brain_farming', 'brawn', 'cutting', 'defense', 'fortitude', 'foundry', 'metalsmith', 'strike']
```

### Check skill levels (in-game command)

```bash
> skills
```

Opens the interactive skills panel menu. Or view another player's skills:

```bash
> skills testchar

--- testchar's Skills ---
Cutting: Level 7 (1240/1823 XP until next level)
Foundry: Level 3 (240/425 XP until next level)
Metalsmith: Level 1 (0/83 XP until next level)
```

### Check skill levels (Python)

```python
> py self.skills.get_level("cutting")
7

> py from systems.progression.skills.registry import SKILL_REGISTRY; {s: self.skills.get_level(s) for s in sorted(SKILL_REGISTRY)}
{'brain_farming': 0, 'brawn': 0, 'cutting': 7, 'defense': 0, 'fortitude': 10, 'foundry': 3, 'metalsmith': 1, 'strike': 0}
```

### Set a character attribute

```bash
> set testchar2/has_cutting_reward = True
```

Or via Python:

```python
> py self.search("testchar2").db.has_cutting_reward = True
```

---

## Equipment System

### Open the equipment menu (in-game)

```bash
> equip
> equipment
```

Shows all 8 equipment slots (Main Hand, Off Hand, Two Hands, Head, Body, Legs,
Feet, Back), what's equipped, and a count of carried items. Browse inventory to
equip/unequip items.

### Inspect equipment state (Python)

```python
> py self.equipment.all()
[<ToolItem: Rusty Scrap Axe>]

> py self.equipment.count_inventory()
3
```

### Unequip via Python

```python
> py self.equipment.unequip(self.equipment.get_current_slot("main_hand"))
```

### Check what's in a specific slot

```python
> py self.equipment.slots.get(WieldLocation.MAIN_HAND)
<ToolItem: Rusty Scrap Axe>
```

### Skill-gated equipping

An item carrying a `tool_type` is gated on a skill level before it can be
equipped. The mapping lives in `items/equipment/skill_requirements.py`:

| `tool_type` | Required skill |
|---|---|
| `axe` | `cutting` |
| `shortsword`, `spear`, `sword` | `strike` |
| `hammer`, `generic` | *(none — explicitly exempt)* |

The item's own `db.req_level` sets the level needed. **Every `tool_type` the
game emits must appear in that map.** An unregistered one **fails closed** —
the equip is refused and logged — because treating "unknown" as "ungated" is
what let a renamed weapon category silently lose its level check on every
object already in the DB. A `None` value means *deliberately* unrestricted, so
the two cases stay distinguishable.

---

## Combat System

Twitch melee on a **0.6 s tick**, with OSRS-derived accuracy and damage maths
rescaled from OSRS's 1–99 to Blackout's 0–127.

### In-game commands

```bash
> attack <target>     # begin swinging at a target
> hold                # stop attacking, stay in combat
> wield <weapon>      # swap weapons mid-fight, then resume attacking
> flee                # leave combat
```

### How a swing resolves

Each combatant runs one `BlackoutCombatHandler` script. Every 0.6 s tick it
decrements that combatant's personal cooldown; at zero the pending action
fires. A weapon's `attack_speed` is the number of ticks **between** swings, so
a speed-4 weapon swings every 2.4 s.

The global `BlackoutTickEngine` owns a single twisted `LoopingCall` and calls
every registered handler. It cannot use `Script.interval` or `TickerHandler`:
`ScriptDB.db_interval` is a Django `IntegerField` (0.6 truncates to 0) and
`TickerHandler` rejects sub-second intervals.

### Hitpoints and Fortitude

Max HP scales **one-to-one with the Fortitude level**. Characters start at
Fortitude 10, so at 10 HP, and the cap rises by one per level to 127. The
scaling knob is `HP_PER_FORTITUDE_LEVEL` in `systems/combat/constants.py` —
nothing multiplies a Fortitude level by a bare literal.

```python
> py self.skills.get_level("fortitude"), self.db.max_hp, self.db.hp
(10, 10, 10)
```

### Combat XP

Each weapon defines four styles. A style names the skill(s) it feeds via
`weapon_style_xp_skill`, and every named skill earns that style's per-skill
rate — 4.0 XP per point of damage, except **Fortitude, which always earns
1.33/damage regardless of style** (`XP_PER_DAMAGE_BY_SKILL`).

| Stance | Invisible bonus | Feeds |
|---|---|---|
| accurate | +3 strike | strike, fortitude |
| aggressive | +3 brawn | brawn, fortitude |
| defensive | +3 defense | defense, fortitude |
| controlled | +1 to all three | strike, brawn, defense |

### Inspect combat state (Python)

```python
> py self.db.in_combat
True

> py self.combat.ndb.active_weapon_data["attack_speed"]
4
```

Per-tick handler state (`target_id`, `pending_action`, `cooldown_ticks`,
`active_weapon_data`) lives on **`ndb`, not `db`** — it is rebuilt whenever
combat starts, so persisting it only cost an Attribute write every 0.6 s per
combatant.

### Known gaps

- Nothing awards Defense XP on *taking* damage
  (`XP_PER_DAMAGE_TAKEN_DEFENSE` is commented out in `constants.py`).
- `CONTROLLED_XP_SKILLS` omits `fortitude`, so controlled-stance weapons
  (the spear) grant no Hitpoints XP — this contradicts
  `02_Player/Player_Overview.md`, which says any style grants it.
- Passive HP regeneration (1 HP/minute per the design doc) is not implemented.
- NPCs never retaliate; nothing queues actions for them.

---

## Banking System

### In-game commands

```bash
> deposit Rusty Metal Chunk

Item deposited.

> balance

--- Storage ---
1. Rusty Metal Chunk [2.0kg, 1 credits]

> withdraw Rusty Metal Chunk

You withdraw Rusty Metal Chunk from the bank.
```

Opens the full banking menu:

```bash
> bank
```

### Python inspection

```python
> py [item.key for item in self.bank.list_items()]
['Rusty Metal Chunk', 'Hammer']

> py self.bank.count_items()
2
```

### Bulk deposit all items of a type

```python
> py [self.bank.deposit(obj) for obj in self.contents if obj.key == "Rusty Metal Chunk"]
```

---

## Crafting System

### In-game crafting

Stand at a crafting facility (furnace, anvil) and use:

```bash
> craft
```

Opens a menu: select a category, browse recipes, check material/tool
requirements, and craft with optional confirmation.

### Toggle craft confirmation prompt

```bash
> toggle craft confirm
```

### Python: browse available recipes

```python
> py from systems.crafting.crafting_service import get_categories; get_categories()
{'Foundry': ['rusty scrap metal'],
 'Metalsmith': ['rusty metal dust', 'rusty scrap axe', 'rusty scrap shortsword', 'rusty scrap spear']}

> py from systems.crafting.crafting_service import get_recipe_display_data; data = get_recipe_display_data(self, "rusty_scrap_metal_recipe"); data["name"], data["can_craft"]
('Smelt Rusty Scrap Metal', True)
```

### Adding a new recipe

1. Create a class in `systems/crafting/recipes/` extending `BlackoutRecipe`.
2. Register the module in `server/conf/settings.py` under `CRAFT_RECIPE_MODULES`.
3. Reload the server.

```python
# systems/crafting/recipes/my_recipes.py
from systems.crafting.blackout_recipe import BlackoutRecipe
from systems.crafting.constants import CATEGORY_FOUNDRY

class MyNewRecipe(BlackoutRecipe):
    name = "My New Recipe"
    category = CATEGORY_FOUNDRY
    consumable_tags = ["rusty_metal_chunk"]
    tool_tags = ["hammer"]
    output_item_keys = ["rusty_scrap_metal"]
    required_skill = "foundry"
    required_level = 1
    xp_reward = 25
```

**Import `category` from `systems/crafting/constants.py` — never type the
literal.** A facility's `allowed_categories` is matched against it by exact
string equality, so `"Metalsmithing"` vs `"Metalsmith"` silently hides every
recipe in the category from the craft menu. `BlackoutRecipe.__init_subclass__`
now raises at import on an unregistered category to make that impossible.

---

## Admin Commands

### Purge items from the world

```bash
> purge all Rusty Metal Chunk           # deletes from your inventory
> purge all global Rusty Metal Chunk    # deletes from ALL characters
```

Requires Builder permission. Searches both inventory and equipment slots.

---

## Map Building Workflow

Use this procedure whenever you expand a grid, shrink a grid, change room
coordinates, or alter the layout of an ASCII map.

### Standard 5-step procedure

**1. Edit the Map File**
Make structural changes in `world/maps/<map_name>.py`.

- All new symbols must be defined in the `legend` dict mapping to a `MapNode`.
- Respect Evennia's XYZGrid spacing rules (no spaces between rooms/links,
  padding around the `+` borders).

**2. Delete the Old Z-Level**

```bash
> evennia xyzgrid delete "oasis"
evennia xyzgrid delete "trade town sector 1"
```

**3. Add the Updated Map**

```bash
> evennia xyzgrid add world.maps.test_oasis
> evennia xyzgrid add world.maps.test_neo_cairo
```

**4. Spawn the New Grid**

```bash
> evennia xyzgrid spawn
```

**5. Reload the Server**

```bash
> evennia reload
```

### Utility commands

```bash
> evennia xyzgrid list
> evennia xyzgrid show oasis
> evennia xyzgrid show "trade town sector 1"
```

### Automated rebuild (PowerShell)

```powershell
.\scripts\clean_and_reload_all_maps.ps1
```

Stops Evennia, runs `xyz_cleanup.py`, adds all maps, spawns, and reloads.

---

## Color Reference

Evennia uses `|`-prefixed markup to color terminal text. Tags compose inline — wrap any character or string.

**In game code, do not type these tags directly.** Import the named palette
from `systems/ui/colors.py` (`TITLE_COLOR`, `HIGHLIGHT_COLOR`, `SUCCESS_COLOR`,
`ERROR_COLOR`, `RESET_COLOR`, …) plus the `dialog()` / `highlight()` / `title()`
wrappers. The table below is for reading existing markup and picking new
palette entries. Nine modules once carried their own copy of these literals, so
a retheme meant finding all nine.

| Category | Tags | Description |
|----------|------|-------------|
| **ANSI fg bright** | `\|r` `\|g` `\|y` `\|b` `\|m` `\|c` `\|w` | Red, Green, Yellow, Blue, Magenta, Cyan, White |
| **ANSI fg dark** | `\|R` `\|G` `\|Y` `\|B` `\|M` `\|C` `\|W` | Dark red, Dark green, Brown, Dark blue, Dark magenta, Dark cyan, Grey |
| **Xterm256 RGB fg** | `\|RGB` (R,G,B ∈ 0‑5) | 216 colors. e.g. `\|500`=red, `\|050`=green, `\|005`=blue, `\|110`=brown, `\|425`=pink |
| **Greyscale fg** | `\|=a` … `\|=z` | 26 levels: a=black, g=dark grey, o=middle grey, v=bright grey, z=white |
| **Hex fg** | `\|#RRGGBB` | Any 24‑bit RGB color, e.g. `\|#4488FF` |
| **Background** | Prefix any fg tag with `[` | e.g. `\|[r` (bg bright red), `\|[431` (bg orange), `\|[=j` (bg dark grey) |
| **Reset** | `\|n` | Resets all color and formatting to normal |

Example: `\|300P\|n` renders **P** in dark red (R=3,G=0,B=0) then resets.

---

## Troubleshooting: The Nuclear Option

If a typo in a map file (e.g., a symbol not in your legend) causes `spawn` to
crash with a `RuntimeError`, the standard `delete` command may not see the
ghost rooms left behind.

**1.** Fix the map file typo / legend mismatch.

**2.** Sweep the database manually via `evennia shell`:

```python
from typeclasses.rooms import GridTile
from evennia.contrib.grid.xyzgrid.xyzroom import XYZExit

GridTile.objects.all().delete()
XYZExit.objects.all().delete()
```

Type `quit()` to exit the shell.

**3.** Resume the standard build:

```bash
evennia xyzgrid add world.maps.test_oasis
evennia xyzgrid spawn
evennia reload
```

---

## Scripts & Automation

| Script | Purpose | How to run |
|---|---|---|
| `scripts/reload_characters.py` | Re-runs `at_object_creation()` on all Character objects | `py -3 scripts/reload_characters.py` (from `blackout/`) |
| `scripts/xyz_cleanup.py` | Deletes all rooms tagged with configured z-coordinates | `../evenv/Scripts/python.exe scripts/xyz_cleanup.py` (from `blackout/`) |
| `scripts/clean_and_reload_all_maps.ps1` | Full automated map rebuild (stop → cleanup → add → spawn → reload) | `.\scripts\clean_and_reload_all_maps.ps1` |

---

## Running Tests

**One command runs the whole suite.** From `blackout/`:

```bash
../evenv/Scripts/evennia.exe test --settings settings.py items systems typeclasses commands world
```

The three roots that actually hold tests are `items`, `systems`, and `world`;
`typeclasses` and `commands` are listed so any test added there is picked up
too. **Omitting a root silently runs fewer tests rather than erroring** — that
is how `world/tests/` went unnoticed. Plain `evennia test .` is *not*
equivalent: it collects fewer tests, because `world/maps/test_oasis.py` and
`test_neo_cairo.py` are map definitions whose names happen to match the
discovery pattern.

```bash
# A single module, while iterating
../evenv/Scripts/evennia.exe test --settings settings.py systems.banking.tests
```

### Writing tests

Every test module must be a `unittest.TestCase` subclass. **Do not write bare
module-level `def test_*()` functions** — Django's unittest discovery skips
them silently, and ~27 tests (one of them genuinely failing) sat un-run that
way until they were converted.

`pytest` is installed but **`pytest-django` is not**, so pytest cannot
bootstrap the DB the Evennia suites need. It is not the runner for this
project.

Test files live alongside the code they test, in a `tests/` package
(`systems/banking/tests.py` is the one legacy exception). **A `tests/`
directory needs an `__init__.py`** or nothing inside it is collected.

---

## Quick Reference — Python One-Liners

| Task | One-liner |
|---|---|
| List all items in ITEM_DB | `py from world.item_database import ITEM_DB; [f"{k}: {v.name}" for k,v in ITEM_DB.items()]` |
| Create 1 item | `py ITEM_DB["rusty_metal_chunk"].create(location=self)` |
| Create N items | `py [ITEM_DB["rusty_metal_chunk"].create(location=self) for _ in range(15)]` |
| Refresh all characters | `py from typeclasses.characters import Character; [c.at_object_creation() for c in Character.objects.all()]` |
| Check a skill level | `py self.skills.get_level("cutting")` |
| Add XP to a skill | `py self.skills.add_xp("cutting", 500)` |
| List bank contents | `py [i.key for i in self.bank.list_items()]` |
| List equipped items | `py [i.key for i in self.equipment.all()]` |
| Count inventory slots used | `py self.equipment.count_inventory()` |
| List available recipe categories | `py from systems.crafting.crafting_service import get_categories; get_categories()` |
| Set a character attribute | `py self.search("testchar2").db.has_cutting_reward = True` |
| Delete all GridTile rooms | `py from typeclasses.rooms import GridTile; GridTile.objects.all().delete()` |
| Count objects by typeclass | `py from typeclasses.characters import Character; Character.objects.all().count()` |
| Teleport to a grid coordinate | `> teleport (5,3,oasis)` |