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

rusty_metal_chunk: rusty metal chunk
rusty_metal_dust: rusty metal dust
rusty_scrap_metal: rusty scrap metal
rusty_scrap_axe: rusty scrap axe
hammer: hammer
```

### Create a single item in your inventory

```python
> py ITEM_DB["rusty_metal_chunk"].create(location=self)

# import in same line
> py from world.item_database import ITEM_DB; ITEM_DB["malfunctioning_gizmo"].create(location=self)

You see a rusty metal chunk appear in your inventory.
```

### Create N items at once

```python
> py [ITEM_DB["rusty_metal_chunk"].create(location=self) for _ in range(15)]

Creates 15 rusty metal chunks in your inventory.
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

### Player summary screen (`score`)

```bash
> score
```

Aliases: `sc`, `dossier`, `char`. Opens the dossier — one screen holding
combat level, hitpoints, the whole skill roster, combat readiness, holdings
and world state, with numbered jumps into the panel that owns each number.

```
============================================================
DOSSIER -- Vex                                      STANDARD
------------------------------------------------------------
VITALS
   Hitpoints     [========22 / 32=======]
   Combat Level  36            Total Level   215
   Total XP      81,552        Regen         +1 HP / 60s
   Status        Out of combat
------------------------------------------------------------
COMBAT READINESS
   Wielding      bare hands (speed 4t)
   Style         Accurate / Crush
   Earns XP      Strike, Fortitude
   Attack        crush +0      Strength      +0
   Defence       stab +0  slash +0  crush +0
------------------------------------------------------------
SKILLS
   Combat        Brawn 36  Defense 27  Fortitude 32
                 Strike 32
   Gathering     Brain Farming 0  Cutting 52
   ...
```

**Adding a band is one file.** Drop a `BasePanel` subclass into
`systems/summary/panel_defs/` — the registry walks the package, so there is no
import to add and no dispatch chain to edit. Each panel implements
`render(character)` for the text screen and `data(character)` for the (phase 2)
`char_summary` state-feed channel; both are built from the same handler reads so
they cannot drift.

| Owns | Lives in |
|---|---|
| Screen assembly, per-panel failure containment | `systems/summary/service.py` |
| Fixed-width rows, rules, wrapping | `systems/summary/layout.py` |
| Panel discovery and ordering | `systems/summary/registry.py` |
| The menu and its drill-down handoff | `systems/menus/summary_menu.py` |

Panels are **read-only**. Nothing on this screen is persisted — every value is
fetched live from the handler that owns it, which is why the screen can never
go stale. Combat Level used to live on the equipment menu; it moved here,
because no equipped item affects it.

Opening the dossier also publishes it on the `char_summary` state-feed channel
(GMCP `Char.Summary`), so a graphical client renders the same data the text
screen shows. It is also part of the full resync snapshot. The channel is
uncapped — it is request-driven, so a cap would mean pressing `score` twice in
a second and getting no answer the second time.

> **Adding a state-feed channel used to break the webclient.** A client that
> subscribed with `channels: "all"` would start receiving a channel its plugin
> had no listener for, and Evennia's `default_out.js` claims every unhandled
> outputfunc and prints the raw JSON at the player as
> `Error or Unhandled event`. `blackout3d.js` now binds its listeners from the
> server's own `blackout_subscribed` acknowledgement, so it claims (and
> silently drops) any channel it has no use for. Its hardcoded `CHANNELS` list
> is only a seed for the handshake. **A browser hard-refresh is needed to pick
> up plugin changes** — `evennia reload` does not touch static JS.

### Public profile (`profile`)

```bash
> profile          # your own, i.e. what others see
> profile testchar
```

Aliases: `whois`, `honours`. Renders only panels flagged `public`, each through
its `render_public`. Two gates rather than one, because "may strangers see this
band" and "how much of it" are different questions:

| Panel | Public? | Shown to others |
|---|---|---|
| Identity | yes | name, path, hardcore flag |
| Vitals → "Standing" | yes | combat level, total level, total XP — **not** current HP, combat state or active aura |
| Combat Readiness | **no** | — your loadout is tactical information |
| Skills | yes | everything, same as your own view |
| Holdings | **no** | — |
| World | yes | quests completed, playtime, created — **not** your location or active quests |

`public` defaults to **False**, so a newly added panel is private until its
author says otherwise. The location omission is the load-bearing one: a profile
command that reported grid coordinates would be a player-tracking tool usable
from anywhere in the world.

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
[<ToolItem: rusty scrap axe>]

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
<ToolItem: rusty scrap axe>
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
> tickdebug           # watch the tick that drives all of the above
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

### Watch the tick (`tickdebug`)

Everything that feels like timing — when a swing lands, when an aura pulses,
why a fight seems to stutter — is a counter on the tick that nothing printed.
`tickdebug` prints it.

```bash
> tickdebug           # toggle the stream (defaults to quiet)
> tickdebug quiet     # only ticks where something happens
> tickdebug all       # every tick, ~100 lines a minute
> tickdebug status    # one-shot health report, no stream
> tickdebug off       # stop
```

A streamed line:

```
[t 01432] 0.601s eng 2h | SWING cd 3/4 attack -> mutant raider | rf 2/4
```

tick number, the **measured** interval against the 0.6 s nominal, how many
handlers the engine is driving, then your own weapon cooldown and aura cadence
as `remaining/total`. `SWING`/`PULSE` mark the tick an action resolved.

Two failures it is built to expose, both of which are otherwise silent:

- **`UNREGISTERED`** — `BlackoutTickEngine._tick` drops a handler from the
  rotation on any exception it raises. The only other symptom is combat
  quietly stopping.
- **`LATE`** — the measured gap exceeded `TICK_DEBUG_LATE_TICK_FACTOR` × 0.6 s.
  `tickdebug status` reports mean/max/late over a rolling window, so a stall
  that has already passed is still visible.

The stream expires after `TICK_DEBUG_AUTO_EXPIRE_TICKS` (5 minutes) and stops
on disconnect. It costs nothing when nobody is watching: both engine hooks
return on a dictionary truth test before reading any handler state.

### Known gaps

- Nothing awards Defense XP on *taking* damage
  (`XP_PER_DAMAGE_TAKEN_DEFENSE` is commented out in `constants.py`).
- `CONTROLLED_XP_SKILLS` omits `fortitude`, so controlled-stance weapons
  (the spear) grant no Hitpoints XP — this contradicts
  `02_Player/Player_Overview.md`, which says any style grants it.
- Passive HP regeneration (1 HP/minute per the design doc) is not implemented.
- NPCs never retaliate; nothing queues actions for them.

---

## Loot Tables

Kill an NPC and its drops land **on the floor of the room it died in**. Pick
them up with the stock `get` command.

### How a drop is resolved

`CombatEntity.at_death` → `drop_loot()` → `systems/loot/drops.py`, which reads
`db.npc_key` → `NPC_DB[key].loot_table` → `LOOT_DB[table_key]` and rolls it.
Resolution is **live**, not stamped at spawn, so editing a table and running
`evennia reload` affects NPCs already standing on the grid.

An NPC whose `NpcDef` sets no `loot_table` drops nothing — every NPC is opt-in,
the same way `respawn_seconds` is.

### The three stages of a table

| Stage | Behaviour |
|---|---|
| `always` | Every entry drops on every kill. |
| `main` | `rolls` weighted picks. `nothing_weight` is the no-drop share of the same pool. |
| `tertiary` | Independent 1/N rolls; can land alongside a main-table drop. |

Weights are relative integers. The shipped tables are all denominated in 128ths
so an OSRS wiki drop rate copies across without arithmetic.

### Registering a new table

```python
# world/loot_defs/hostile.py — example entry
"scav_drops": LootTableDef(
    key="scav_drops",
    always=[LootEntry(item_key="rusty_metal_chunk")],
    main=[
        LootEntry(item_key="credits", min_quantity=5, max_quantity=15,
                  weight=40),
    ],
    nothing_weight=88,
    tertiary=[
        TertiaryDrop(entry=LootEntry(item_key="glass_cannon_amulet"),
                     chance_denominator=128),
    ],
),
```

Then name it from the NPC:

```python
# world/npc_defs/hostile.py
"scav": NpcDef(key="scav", ..., loot_table="scav_drops"),
```

Two NpcDefs may name the same table; that is how a shared rare table works
without duplicating data.

### Check a table without killing anything

```bash
> py from world.loot_database import LOOT_DB; print(LOOT_DB["mutant_raider_drops"].roll())
```

### Validate every table

Catches unknown `item_key`s, inverted quantity ranges, unrollable pools, and a
table registered under a key its def disagrees with:

```bash
> py from world.loot_database import validate_loot_tables; print(validate_loot_tables() or "clean")
```

An empty list means clean. This also runs as a test
(`world.tests.test_loot_database`); at runtime a bad key is logged and skipped
rather than raised, so a typo never blocks a death.

### Known gaps

- No corpse object and no loot ownership — drops are free for anyone in the
  room to `get`.
- No auto-loot. `award_drops` takes `killer` but does not read it yet.
- Player death drops nothing; `CombatEntity.drop_loot` is a no-op stub for
  anything that is not a `HostileNPC`.
- Drops are not published to the state feed, so a graphical client sees the
  items appear only via the room contents.

---

## Banking System

### In-game commands

```bash
> deposit rusty metal chunk

You deposit rusty metal chunk (x11) into the bank.

> balance

--- Storage ---
1. rusty metal chunk (2.0kg, 1g) x11

> withdraw rusty metal chunk 4

You withdraw rusty metal chunk (x4) from the bank.
```

A quantity is optional and may be a number or `all`. **Omitting it moves
everything that matches** — the whole stack for a stackable item, and every
copy of it otherwise. Items that do not stack are separate objects, so a pile
of eleven scrap plates is eleven bank entries, but one command moves them all.

Opens the full banking menu:

```bash
> bank
```

The menu's deposit and withdraw lists collapse identical items into one row
with a total (`rusty scrap metal (x11)`) and then prompt for a quantity, so
bulk transfers do not need the command form.

### Python inspection

```python
> py [item.key for item in self.bank.list_items()]
['rusty metal chunk', 'hammer']

> py self.bank.count_items()
2
```

### Bulk deposit all items of a type

```python
> py self.bank.deposit_many([obj for obj in self.contents if obj.key == "rusty metal chunk"])
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

> py from systems.crafting.crafting_service import get_recipe_display_data; data = get_recipe_display_data(self, "rusty scrap metal"); data["name"], data["can_craft"]
('Smelt rusty scrap metal', True)
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

## Stat Tracker

Generic counters and stats all stored in a single per-character dict, e.g. kills per hostile type, credits spent. 

### In-game commands: inspect a character's stats

```bash
> py me.stats.all()
> py me.stats.get("kills_per_hostile")
> py me.stats.get("kills_per_hostile", key="mutant_raider")
```

### Adding a new tracked stat

1. Add a `STAT_KEY` constant in `systems/stat_tracker/constants.py`.
2. Add a matching `StatDef` to `STAT_REGISTRY` in `systems/stat_tracker/registry.py`.
3. Record an increment at the site of the event, following this pattern:

```python
# e.g. typeclasses/mixins.py, CombatEntity.at_death
stats = getattr(killer, "stats", None)
npc_key = getattr(self.db, "npc_key", None)
if stats is not None and npc_key:
    try:
        stats.increment(stat_constants.KILLS_PER_HOSTILE_STAT_KEY, npc_key)
    except Exception as exc:
        logger.log_err(f"CombatEntity.at_death KILLS_PER_HOSTILE_STAT_KEY stat update failed: {exc!r}")
```

### Types of stats
Each stat type is defined in `StatKind` once in `systems/stat_tracker/registry.py`.
`StatHandler` defines how each is handled.

Source of truth definitions in `systems/stat_tracker/registry.py`

```text
COUNTER stat stores         |  {stat_key: total(int)}
KEYED_COUNTER stat stores   |  {stat_key: {sub_key: total(int)}}
```

---

## Admin Commands

### Purge items from the world

```bash
> purge all rusty metal chunk           # deletes from your inventory
> purge all global rusty metal chunk    # deletes from ALL characters
```

Requires Builder permission. Searches both inventory and equipment slots.

### The Moderator Egg

An in-game item that opens the moderator toolkit as a menu. Give yourself one:

```python
> py from world.item_database import ITEM_DB; ITEM_DB["moderator_egg"].create(location=self, home=self)
```

Then, with it in your inventory:

```bash
> egg
```

The command is locked to `perm(Admin)`; superusers bypass the lock as they do
every other. The egg is inert in anyone else's hands, and `tradeable=False`
keeps it out of shops and trades -- the only way one reaches a player is
someone handing it over.

What the menu offers:

| Entry | Effect |
|---|---|
| Inspect | The target's full player dossier (the same one `score` renders) plus a staff addendum: dbrefs, the account and its permissions, god-mode state, the itemised bag, and every quest with live objective counters. Read-only. |
| Spawn an item | Any `ITEM_DB` key, 1 or N. Stackables arrive as one stack; a request larger than the grid is clamped and says so. |
| Spawn an NPC | Any `NPC_DB` key, 1-20, into **the target's room**. They land live and hostile, with the full combat block and respawn stamp `NpcDef.create` gives a map-placed one. |
| Toggle god mode | The target ignores all incoming damage. Persists on the CHARACTER, not the egg -- dropping the egg does not turn it off. |
| Restore | Refresh max HP from Fortitude, heal to full, drop out of combat. |
| Empty inventory | Destroys everything carried **and equipped**. Behind a confirmation that counts what it will destroy and names whose it is. Staff items are skipped. |
| Teleport to a map | Any map in `scripts/map_manifest.json`, landing on its `(0,0)` entrance tile. |
| Teleport to a player | Sends the target to whichever character you name. |
| Bring target to me | The same call with the arguments swapped. |
| Grant XP / Set a skill level | Any key in `SKILL_REGISTRY`. Levels accept the full 0-127 range. |
| Quests | Accept, abandon, complete, reset, or jump to any step of any quest in the registry. See below. |
| Boot or ban an account | Types Evennia's own `boot` / `ban` / `unban`. `ban` keeps its Developer lock. |
| Change target | Aims every entry above at another character. Blank resets to yourself. |

The egg protects itself: `Empty inventory` refuses to delete anything tagged
as a staff item, so emptying your own bag does not destroy the egg you are
holding to do it with.

#### Quest testing

The quest screen is the one to reach for when testing content. Four
whole-quest writes plus a step jump:

| Operation | What it does |
|---|---|
| Accept | Starts the quest properly -- seeds progress, fires step 1's `on_enter`. Indistinguishable from taking it from an NPC. |
| Abandon | Drops progress. **Leaves any completion record standing**, so a finished quest stays finished. |
| Complete | Marks it done and **pays the rewards**. Skipped steps' hooks do not fire. |
| Reset | Clears active *and* completed. The only one that makes a finished quest takeable again. |
| Jump to a step | Moves an active quest to any step, forward or back. Re-seeds that step's counters and fires its `on_enter`, so the quest keeps playing from there. |

Abandon vs. Reset is the distinction worth knowing: **abandon** returns a quest
in progress to not-started, but does nothing to a quest already completed.
**Reset** is what a tester replaying content wants.

The step jump is what makes a five-step quest testable in minutes rather than
by replaying it: accept, jump to the step under test, exercise it, jump back.

Every action taken through the egg writes one `[MODTOOL]` line to the server
log naming the actor, the verb and the target. Reading a dossier is logged
too. To review a session:

```bash
grep MODTOOL server/logs/server.log
```

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

Stops Evennia, runs `map_sync.py`, spawns, and reloads.

**`scripts/map_manifest.json` is the only file you edit to add or remove a
map.** Each row carries a map module and the z-coordinate that module
declares:

```json
{
  "maps": [
    { "module": "world.maps.test_oasis", "zcoord": "oasis" }
  ]
}
```

- **Add a row** → the module is loaded, its map registered, its rooms spawned.
- **Delete a row** → that map is removed from the grid and its rooms and exits
  are deleted on the next rebuild. Anyone standing in a deleted room is sent
  home rather than deleted.

`map_sync.py` validates before it deletes anything: every listed module must
import, yield exactly one map, and declare the z-coordinate its row claims.
It also reads the grid back after registering, so a map that fails to load
aborts the rebuild instead of quietly vanishing from it.

Preview a rebuild without changing anything (safe while the server is up):

```powershell
.\scripts\clean_and_reload_all_maps.ps1 -DryRun
```

```bash
./scripts/clean_and_reload_all_maps.sh --dry-run
```

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
| `scripts/map_sync.py` | Reconciles the grid with `map_manifest.json`: removes unlisted maps, purges and re-registers listed ones | `../evenv/Scripts/python.exe scripts/map_sync.py [--dry-run]` (from `blackout/`) |
| `scripts/clean_and_reload_all_maps.ps1` | Full automated map rebuild (stop → sync → spawn → reload) | `.\scripts\clean_and_reload_all_maps.ps1 [-DryRun]` |
| `scripts/clean_and_reload_all_maps.sh` | Same rebuild from Git Bash | `./scripts/clean_and_reload_all_maps.sh [--dry-run]` |

---

## Running Tests

### Always use `test_settings.py`

Pass `--settings test_settings.py`, not `--settings settings.py`. It is
`settings.py` with one line changed — the Django password hasher — because
Evennia's test fixtures create two accounts per test method and the default
PBKDF2 hasher costs 0.46s per account. That one line took the full suite from
~20 minutes to 6.4. See `../docs/2026-08-23-TEST-0001-suite-audit.md`.

### Quick testing (most common)

While developing, run **only the module(s) you changed** — these finish in
seconds:

```bash
# Single module
../evenv/Scripts/evennia.exe test --settings test_settings.py systems.banking.tests

# Multiple modules
../evenv/Scripts/evennia.exe test --settings test_settings.py systems.combat.tests systems.crafting.tests
```

### Full test suite (only when necessary)

**1273 tests, ~6.5 minutes.** Run it before merging, or when a change affects
multiple systems:

```bash
../evenv/Scripts/evennia.exe test --settings test_settings.py items systems typeclasses commands world
```

Append `--durations 20` to see the slowest tests.

The three roots that actually hold tests are `items`, `systems`, and `world`;
`typeclasses` and `commands` are listed so any test added there is picked up
too. **Omitting a root silently runs fewer tests rather than erroring** — that
is how `world/tests/` went unnoticed. Plain `evennia test .` is *not*
equivalent: it collects fewer tests.

`--parallel` does not work — Django's cloned worker databases do not carry the
dbrefs `EvenniaTestMixin` assumes, and every worker dies in `setUp` on
`settings.DEFAULT_HOME (= '#2') does not exist`. Don't spend time on it.

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