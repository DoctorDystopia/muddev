# Welcome to Evennia!

This is your game directory. It lets you start with your new game
immediately. An overview of this directory is here:
https://github.com/evennia/evennia/wiki/Directory-Overview#the-game-directory

Do not delete this README. The Blackout documentation below lives in it. You
can arrange the other things in this game directory to suit your own sense of
organization. The only exception is the structure of the `server/` directory,
which Evennia expects. If you change the structure, you must also edit your
settings file to tell Evennia where to look for things.

The main configuration file of your game is `server/conf/settings.py`. You do
not need to change it to get started. If you just created this directory and
used the default instructions, you already have a `virtualenv` running. Then,
`cd` to this directory and initialize a new database with:

    evennia migrate

To start the server, go to this directory and run:

    evennia start

This command starts the server and logs output to the console. When the
command asks you, create a superuser. By default, you can then connect to your
new game with a MUD client on `localhost`, port `4000`. You can also log in to
the web client: point a browser to `http://localhost:4001`.

# Getting started

From here, you can look at one of the beginner tutorials:
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
- [Loot Tables](#loot-tables)
- [Banking System](#banking-system)
- [Crafting System](#crafting-system)
- [Stat Tracker](#stat-tracker)
- [Admin Commands](#admin-commands)
- [Map Building Workflow](#map-building-workflow)
- [Troubleshooting: The Nuclear Option](#troubleshooting-the-nuclear-option)
- [Scripts & Automation](#scripts--automation)
- [Running Tests](#running-tests)
- [Quick Reference — Python One-Liners](#quick-reference--python-one-liners)

---

## Item Database — Bulk Creation & Management

All items are registered in the `ITEM_DB` dict (`world/item_database.py`). The
`ItemDef.create()` method creates them, and it is the canonical way to spawn
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

1. Add an `ItemDef` entry in `world/item_defs/<category>.py` (for example, `materials.py` or `tools.py`).
2. Restart or reload the server. The new item appears in `ITEM_DB` automatically.

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

Aliases: `sc`, `dossier`, `char`. The command opens the dossier. The dossier is
one screen with combat level, hitpoints, combat readiness, holdings, and world
state. It has numbered jumps into the panel that owns each number.

**Skills are not on it.** The skills panel left on 08/28/2026 for a screen of
its own. Refer to [Skill sheets](#skill-sheets-skills-skill) below for where it
went and why. The aggregates stay here: combat level, total level, and total XP
belong to the vitals panel. `Skills panel` is the first drill-down.

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
HOLDINGS
   Credits       1,204         Banked        18,000
   ...
```

**A new panel is one file.** Drop a `BasePanel` subclass into
`systems/interface/summary/panel_defs/`. The registry walks the package, so
there is no import to add and no dispatch chain to edit. Each panel implements
`render(character)` for the text screen and `data(character)` for the (phase
2) `char_summary` statefeed channel. The two methods read the same handlers, so
they cannot drift.

| Owns | Lives in |
|---|---|
| Screen assembly, per-panel failure containment | `systems/interface/summary/service.py` |
| Fixed-width rows, rules, wrapping | `systems/interface/summary/layout.py` |
| Panel discovery and ordering | `systems/interface/summary/registry.py` |
| The menu and its drill-down handoff | `systems/interface/menus/summary_menu.py` |

Panels are **read-only**. This screen persists nothing. Each panel reads every
value live from the handler that owns it, so the screen can never go stale.
Combat Level used to live on the equipment menu. It moved here, because no
equipped item affects it.

When the dossier opens, it also publishes itself on the `char_summary`
statefeed channel (GMCP `Char.Summary`). Thus, a graphical client renders the
same data that the text screen shows. The dossier is also part of the full
resync snapshot. The channel is uncapped, because a player request drives it.
With a cap, a second `score` in the same second would get no answer.

> **A new statefeed channel can break a client that is not ready for it.**
> A client that subscribes with `channels: "all"` gets every channel that the
> server offers, including channels that its own code has no listener for.
> The Godot client (`godot/scenes/console.gd`) subscribes from the server's own
> `blackout_subscribed` acknowledgment, not from a hardcoded list. It offers
> each incoming message to every model, and each model reports whether it
> wanted the message. Thus, the client silently drops an unclaimed channel and
> gives no error.
>
> The retired webclient failed in a different way. Evennia's stock
> `default_out.js` claims every unhandled outputfunc. If a plugin did not bind
> a listener for a new channel, it printed the raw JSON at the player as
> `Error or Unhandled event`.

### Public profile (`profile`)

```bash
> profile          # your own, i.e. what others see
> profile testchar
```

Aliases: `whois`, `honours`. The command renders only the panels flagged
`public`, each through its `render_public`. There are two gates, not one,
because "may strangers see this panel" and "how much of it" are different
questions:

| Panel | Public? | Shown to others |
|---|---|---|
| Identity | yes | name, path, hardcore flag |
| Vitals → "Standing" | yes | combat level, total level, total XP — **not** current HP, combat state or active aura |
| Combat Readiness | **no** | — your loadout is tactical information |
| Holdings | **no** | — |
| World | yes | quests completed, playtime, created — **not** your location or active quests |
| Records | **no** | — kills, deaths and spending are nobody else's business |

Skills are absent from this table because they are absent from the dossier
entirely. Their panel moved out on 08/28/2026. `skills <character>` shows the
levels of another character, and it always did. About progress, a profile now
carries only the three aggregate figures. OSRS makes the same split between a
hiscores entry and a full stat page.

`public` defaults to **False**, so a new panel is private until its author says
otherwise. The missing location is the load-bearing omission. A profile command
that reported grid coordinates would be a tool to track players from anywhere
in the world.

### Lifetime records (`stats`)

```bash
> stats
```

Alias: `records`. The command shows every tally that
`systems/core/stat_tracker/` holds for you: kills and deaths for each hostile,
cuttings and butcherings for each node, and credits spent. Each stat has its
own heading, every entry has a name, and each stat has a total.

The **Records** panel of the dossier is the short form of the same read. It
pairs the counters, and each stat for a hostile or a node names its top three
with a `+N more`. The Godot Character tab gets every entry, uncapped. All three
screens get their data from `StatHandler.recorded()` through
`panel_defs/records.py`, and none of them names a stat.

**A new stat is one `StatDef` in `registry.py`.** Give it a `label` of 14
characters or fewer for the label column of the dossier, and it appears on all
three screens. `StatHandler.increment` marks the dossier stale itself, so the
tab follows a kill with no call beside it.

### Refresh all characters

This command runs `at_object_creation()` again on every character in the
database. Use it after you add new handler properties to the Character
typeclass.

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

`systems/gameplay/progression/skills/registry.py` **discovers these
automatically** when it walks `skill_defs/`. To add a skill, drop one module in
the right category directory. The module holds a `BaseSkill` subclass with a
unique `key`. There is no registry list to edit. A passive skill needs nothing
but its four class attributes. `get_unlock_requirements` and `execute` already
have correct defaults on `BaseSkill`.

```python
> py from systems.gameplay.progression.skills.registry import SKILL_REGISTRY; sorted(SKILL_REGISTRY)
['brain_farming', 'brawn', 'cutting', 'defense', 'fortitude', 'foundry', 'metalsmith', 'strike']
```

### Check skill levels (in-game command)

```bash
> skills
```

This command opens the interactive skills menu. To see the skills of another
player, give a name:

```bash
> skills testchar

--- testchar's Skills ---
Cutting: Level 7 (1240/1823 XP until next level)
Foundry: Level 3 (240/425 XP until next level)
Metalsmith: Level 1 (0/83 XP until next level)
```

### Skill sheets (`skills <skill>`)

```bash
> skills cutting
> skills brain          # a unique prefix is enough
```

The command shows one skill in full: its level, the XP curve, and **everything
it unlocks**. It lists recipes, gathering nodes, equippable items, and
abilities. Each one shows the level that it needs, in a color that shows
whether you have reached that level.

The argument has **three readings, in this order**: a skill key, the display
name of a skill (or a unique prefix of either), then a character name. When a
skill name wins over a character name, nothing is lost. Before this branch
existed, `skills cutting` searched for a character called "cutting", failed,
and printed "Could not find". Every string that the skill branch claims used to
be an error.

| Owns | Lives in |
|---|---|
| The sheet, as text *and* as data; the unlock section table | `systems/gameplay/progression/skills/detail.py` |
| The `char_skills` payload | `systems/interface/statefeed/skills.py` |
| The menu node's back-navigation, and nothing else | `systems/interface/menus/skills_menu.py` |

**One description, three readers.** The EvMenu used to hold the sheet inline.
Thus, a player could see what a skill unlocked only from inside a menu. Three
readers now share `detail.py`: the menu node, this command, and the
`char_skills` channel. The text renders *from* the structured form, not from a
second set of handler reads. Thus, the grid that a graphical client draws and
the sheet that a telnet player reads cannot describe a skill differently.

A fifth skill-gated system is one row in `_UNLOCK_SECTIONS` plus its row
builder, and it reaches both outputs at once.

Every form of `skills` also publishes the roster on the `char_skills`
statefeed channel (GMCP `Char.Skills`). A level change and a resync publish it
too. An XP award does **not** publish it. Combat awards XP on every hit, and
the payload walks four unlock registries for each skill, so the roster is the
most expensive payload in the statefeed. For the same reason, the channel is
uncapped: the player bounds its rate, not the tick.

### Check skill levels (Python)

```python
> py self.skills.get_level("cutting")
7

> py from systems.gameplay.progression.skills.registry import SKILL_REGISTRY; {s: self.skills.get_level(s) for s in sorted(SKILL_REGISTRY)}
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

The menu shows all 8 equipment slots (Main Hand, Off Hand, Two Hands, Head,
Body, Legs, Feet, Back), what is equipped, and a count of carried items. Browse
the inventory to equip or unequip items.

### Read one item's description (`inspect`)

```bash
> inspect 7
> inspect main hand
> inspect toy sword
```

The command prints exactly what `look` prints, for something that you carry or
wear. It exists because `look` cannot name a row. With three identical cured
chunks in the bag, `look mutant raider cured chunk` can only answer with a
multimatch list. A slot names one object, so every action that the 3D pane
sends is slot-addressed. Refer to `INVENTORY_ACTION_INSPECT` in
`systems/interface/statefeed/constants.py`.

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

A skill level gates an item with a `tool_type` before a player can equip it.
The mapping lives in `items/equipment/skill_requirements.py`:

| `tool_type` | Required skill |
|---|---|
| `axe` | `cutting` |
| `shortsword`, `spear`, `sword` | `strike` |
| `hammer`, `generic` | *(none — explicitly exempt)* |

The item's own `db.req_level` sets the necessary level. **Every `tool_type`
that the game emits must appear in that map.** An unregistered one **fails
closed**: the game refuses the equip and logs it. The reason is a past bug.
The game treated "unknown" as "ungated", so a renamed weapon category silently
lost its level check on every object already in the DB. A `None` value means
*deliberately* unrestricted, so the two cases stay distinguishable.

---

## Combat System

Combat is twitch melee on a **0.6 s tick**, with OSRS-derived accuracy and
damage math rescaled from OSRS's 1–99 to Blackout's 0–127.

### In-game commands

```bash
> attack <target>     # begin swinging at a target
> hold                # stop attacking, stay in combat
> wield <weapon>      # swap weapons mid-fight, then resume attacking
> flee                # leave combat
> tickdebug           # watch the tick that drives all of the above
```

### How a swing resolves

Each combatant runs one `BlackoutCombatHandler` script. On every 0.6 s tick,
the script decrements the personal cooldown of that combatant. At zero, the
pending action fires. A weapon's `attack_speed` is the number of ticks
**between** swings, so a speed-4 weapon swings every 2.4 s.

The global `BlackoutTickEngine` owns a single twisted `LoopingCall` and calls
every registered handler. It cannot use `Script.interval` or `TickerHandler`:
`ScriptDB.db_interval` is a Django `IntegerField` (0.6 truncates to 0) and
`TickerHandler` rejects sub-second intervals.

### Hitpoints and Fortitude

Max HP scales **one-to-one with the Fortitude level**. Characters start at
Fortitude 10, and thus at 10 HP. The cap rises by one for each level, to 127.
The scaling knob is `HP_PER_FORTITUDE_LEVEL` in
`systems/gameplay/combat/constants.py`. Nothing multiplies a Fortitude level by
a bare literal.

Every combatant, player or NPC, regenerates 1 HP each minute, in combat and out
of it. `systems/gameplay/combat/hp_regen.py` runs the sweep, and
`HP_REGEN_INTERVAL_SECONDS` sets the interval.

```python
> py self.skills.get_level("fortitude"), self.db.max_hp, self.db.hp
(10, 10, 10)
```

### Combat XP

Each weapon defines four styles. A style names the skill(s) that it feeds
through `weapon_style_xp_skill`. Every named skill earns the rate of that style
for that skill. Accurate, aggressive, and defensive pay 4.0 XP for each point
of damage. Controlled splits 4.0 XP among its three stats, so each one earns
1.33 (`XP_PER_DAMAGE_CONTROLLED_EACH`). **Fortitude always earns 1.33 for each
point of damage, in every style** (`XP_PER_DAMAGE_BY_SKILL`).

| Stance | Invisible bonus | Feeds |
|---|---|---|
| accurate | +3 strike | strike, fortitude |
| aggressive | +3 brawn | brawn, fortitude |
| defensive | +3 defense | defense, fortitude |
| controlled | +1 to all three | strike, brawn, defense, fortitude |

### Inspect combat state (Python)

```python
> py self.db.in_combat
True

> py self.combat.ndb.active_weapon_data["attack_speed"]
4
```

The handler state for each tick (`target_id`, `pending_action`,
`cooldown_ticks`, `active_weapon_data`) lives on **`ndb`, not `db`**. The
handler builds it again whenever combat starts. Thus, a persisted copy only
cost an Attribute write every 0.6 s for each combatant.

### Watch the tick (`tickdebug`)

Everything that feels like timing is a counter on the tick that nothing
printed: when a swing lands, when an aura pulses, and why a fight seems to
stutter. `tickdebug` prints it.

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

The line shows these fields:

- The tick number
- The **measured** interval against the 0.6 s nominal
- The number of handlers that the engine drives
- Your own weapon cooldown and aura cadence, as `remaining/total`.

`SWING` and `PULSE` mark the tick where an action resolved.

The stream exposes two failures. Without it, both failures are silent:

- **`UNREGISTERED`**: `BlackoutTickEngine._tick` drops a handler from the
  rotation on any exception that the handler raises. The only other symptom is
  that combat quietly stops.
- **`LATE`**: the measured gap was more than `TICK_DEBUG_LATE_TICK_FACTOR` ×
  0.6 s. `tickdebug status` reports mean/max/late over a rolling window, so a
  stall that is already over stays visible.

The stream expires after `TICK_DEBUG_AUTO_EXPIRE_TICKS` (5 minutes) and stops
on disconnect. It costs nothing when nobody watches: both engine hooks return on
a dictionary truth test before they read any handler state.

### Known gaps

- Nothing awards Defense XP when a character *takes* damage
  (`XP_PER_DAMAGE_TAKEN_DEFENSE` is commented out in `constants.py`).

---

## Loot Tables

When you kill an NPC, its drops land **on the floor of the room where it
died**. Take them with the stock `get` command.

### How a drop is resolved

`CombatEntity.at_death` → `drop_loot()` → `systems/gameplay/loot/drops.py`, which reads
`db.npc_key` → `NPC_DB[key].loot_table` → `LOOT_DB[table_key]` and rolls it.
Resolution is **live**, not stamped at spawn. Thus, if you edit a table and run
`evennia reload`, the change affects NPCs already on the grid.

An NPC whose `NpcDef` sets no `loot_table` drops nothing. Every NPC is opt-in,
the same way as for `respawn_seconds`.

### The three stages of a table

| Stage | Behavior |
|---|---|
| `always` | Every entry drops on every kill. |
| `main` | `rolls` weighted picks. `nothing_weight` is the no-drop share of the same pool. |
| `tertiary` | Independent 1/N rolls; can land alongside a main-table drop. |

Weights are relative integers. All the shipped tables use 128ths, so an OSRS
wiki drop rate copies across with no arithmetic.

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

Two NpcDefs can name the same table. A shared rare table works this way, with
no duplicated data.

### Check a table without killing anything

```bash
> py from world.loot_database import LOOT_DB; print(LOOT_DB["mutant_raider_drops"].roll())
```

### Validate every table

The check catches unknown `item_key`s, inverted quantity ranges, unrollable
pools, and a table registered under a key that its def disagrees with:

```bash
> py from world.loot_database import validate_loot_tables; print(validate_loot_tables() or "clean")
```

An empty list means clean. This check also runs as a test
(`world.tests.test_loot_database`). At runtime, the game logs and skips a bad
key and does not raise, so a typo never blocks a death.

### Known gaps

- There is no loot ownership. Some NPCs leave a corpse (`typeclasses/corpses.py`),
  but the drops land on the floor, not in the corpse. Anyone in the room can
  `get` them.
- There is no auto-loot. `award_drops` takes `killer` but does not read it yet.
- A player death drops nothing. `CombatEntity.drop_loot` is a no-op stub for
  anything that is not a `HostileNPC`.
- The statefeed does not publish drops, so a graphical client sees the items
  appear only through the room contents.

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

A quantity is optional, and it can be a number or `all`. **With no quantity,
the command moves everything that matches**: the whole stack for a stackable
item, and every copy of it otherwise. Items that do not stack are separate
objects. Thus, a pile of eleven scrap plates is eleven bank entries, but one
command moves them all.

To bank **one** thing, not the whole group, name where it is, not what it is.
Use an inventory slot number as `inventory` prints it, or an equipment slot for
something that you wear.

```bash
> deposit 7
> deposit main hand
```

This command opens the bank:

```bash
> bank
```

In the Godot client, `bank` opens a pop-up over the world. The vault is on the
left and your inventory is on the right. A left click on a vault item
withdraws the active quantity, and a left click on a carried item deposits it.
A right click lists every action. The 1 / 5 / 10 / X / All buttons set the
quantity, and the game remembers it after you log out. Walk away, click Close,
or press Escape to close it.

The buttons type these commands for you, and you can type them too:

```bash
> popup quantity 5
> popup quantity all
> popup close
```

Every other client gets the banking menu. The deposit and withdraw lists of the
menu show identical items as one row with a total (`rusty scrap metal (x11)`).
Then they prompt for a quantity, so bulk transfers do not need the command
form.

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

## Shops

Stand beside a shopkeeper. These commands work there:

```bash
> trade
> buy rusty metal chunk
> buy rusty metal chunk 5
> buy rusty metal chunk all
> sell 7
> sell 7 all
```

- `buy` without a quantity buys one. `all` buys as many as the shop has and
  you can pay for. If you cannot pay for the full quantity, you buy as many as
  you can.
- `sell` takes an inventory slot number or an item name, as `deposit` does.
- `talk` opens the conversation, which also has the buy and sell menus.

In the Godot client, `trade` opens a pop-up. The stock is on the left, with
each unit price under the item, and your inventory is on the right. A left
click buys or sells the active quantity, and a right click lists every action.
A ware that you cannot pay for is dim. An item that the shop will not buy is
dim and has no actions. A right click on the shopkeeper in the world offers
Talk and Trade.

Every other client gets the shop menu from `trade`.

---

## Gathering System

A harvest is a **channel**, not one command. The verb commits you to a node,
and the server swings at it every **4 ticks (2.4 s)** until something stops
you. The model is OSRS woodcutting.

### In-game commands

```bash
> cut rusty pole
> butcher corpse
> butcher corpse = filet
> harvest corpse
```

`harvest` is the generic verb. It picks the skill from the tool in your hand.
Type the verb again at the same node and the server tells you that you are
already on it. Name a different node and it refuses, because a channel that
switched targets quietly would make the verb mean "abandon what I was doing".

### What one swing does

1. It picks the best cut your level has unlocked, or the one you named.
2. It rolls. A **miss is silent.** This is why the channel says
   "You start to cut the rusty pole." one time at the start.
3. A hit creates the item, teaches the XP, and reports to quests and stats.
4. A hit with bare hands costs **1 hit point**. A miss costs nothing.
5. A hit rolls depletion. A miss never depletes a node.

### The roll

Each node declares a `low` and a `high` numerator for each tool tier, in
**1/255 units**. The chance moves along a straight line between them, from
`low` at level 0 to `high` at level 127. OSRS quotes its woodcutting tables
the same way, so a pair copied off the wiki means here what it means there.

**The tool tier changes the chance and nothing else.** A better axe hits more
often. It does not swing faster. Two knobs multiply, and no table can predict
how fast the tiers then separate.

**A tier is the requirement divided by `TIER_LEVEL_STEP`**, which is 10 and
lives in `world/item_database.py`. `tier_for_level` is its one owner, and
`test_item_database.py` asserts the rule over every entry in `ITEM_DB`.

| Tool | `req_level` | `ItemDef.tier` |
|---|---|---|
| `rusty_scrap_axe`, `rusty_scrap_dagger` | 0 | 0 |
| `scrap_axe`, `scrap_dagger` | 10 | 1 |
| `copper_axe`, `copper_dagger` | 20 | 2 |

The two fields are not one field. `req_level` is the gate, and it says who
may wield the tool. `tier` is the ladder position, and it says what the swing
is worth. A node reads the tier and knows nothing about levels.

A tier the node does not name inherits the best row below it. A new axe tier
therefore needs no edit to any node.

### Depletion is per player

A node you strip stays where it is. It keeps its place in the world pane, it
renders as spent, and it offers **you** nothing until it recovers. Everyone
else sees a whole node. Two players at one pole never compete, and nothing
vanishes under anyone's feet.

The state is `{character_id: expiry}` on the node's own `spent_until`
Attribute, so a deleted node takes the fact with it.

### What ends a channel

| Reason | What you read |
|---|---|
| The node gave out | "You have stripped the ... bare." |
| Your bag filled | "You stop: you have no room to carry any more." |
| You walked away | *(nothing — the room description says it)* |
| A fight started, or you died | "You are interrupted ..." |
| The node was consumed | *(nothing — the harvest line said it)* |

Nothing restarts on its own. Type the verb again.

### Adding a node

One entry in `GATHERABLE_REGISTRY`
(`systems/gameplay/progression/skills/gatherables.py`). It needs `yields`, a
`chances` row per tool tier, and `deplete_chance` with `respawn_seconds`. A
node that allows bare hands also needs `bare_hand_chance`. Every one of those
is checked at import, so a bad row fails at server start and not at a swing.

| Where a fact lives | Module |
|---|---|
| What a node yields, to which skill, at what chance | `skills/gatherables.py` |
| The cadence, the units, the stop messages | `skill_defs/gathering/constants.py` |
| The maths, with no database in it | `skill_defs/gathering/roll.py` |
| Who has stripped a node, and until when | `skill_defs/gathering/depletion.py` |
| The channel on the global tick | `skill_defs/gathering/gather_handler.py` |
| The swing, the item, the XP, the depletion | `skill_defs/gathering/gathering_skill.py` |

---

## Crafting System

### In-game crafting

Stand at a crafting facility (furnace, anvil) and use:

```bash
> craft
> craft rusty metal dust
> craft rusty metal dust 5
> craft rusty metal dust all
> craft cancel
```

A bare `craft` opens the facility. `craft <recipe>` makes that recipe here:
one, a number, or `all` that your materials allow. The recipe is a key or a
name. `craft cancel` stops a batch that is running.

In the Godot client, a bare `craft` opens a pop-up. Every recipe of the
facility shows, with its skill level under the item and its materials on
hover. A recipe that you cannot make yet is dim. A click on it tells you what
is missing. A left click makes the active quantity. The buttons under the
grids stop a batch, or collect a cure at the curing chamber. The pop-up does
not ask for confirmation, because a click names the recipe and the quantity.

Every other client gets the crafting menu. In it, select a category, browse
recipes, check the material and tool requirements, and craft with optional
confirmation.

### Toggle craft confirmation prompt

```bash
> toggle craft confirm
Crafting confirmation turned OFF.
> toggle craft confirm
Crafting confirmation turned ON.
```

The toggle works anywhere, not only at a facility. The Options pane of the
Godot client has the same toggle, as a button under Game.

### Python: browse available recipes

```python
> py from systems.gameplay.crafting.crafting_service import get_categories; get_categories()
{'Foundry': ['rusty scrap metal'],
 'Metalsmith': ['rusty metal dust', 'rusty scrap axe', 'rusty scrap shortsword', 'rusty scrap spear']}

> py from systems.gameplay.crafting.crafting_service import get_recipe_display_data; data = get_recipe_display_data(self, "rusty scrap metal"); data["name"], data["can_craft"]
('Smelt rusty scrap metal', True)
```

### Adding a new recipe

1. Create a class in `systems/gameplay/crafting/recipes/` that extends `BlackoutRecipe`.
2. Register the module in `server/conf/settings.py` under `CRAFT_RECIPE_MODULES`.
3. Reload the server.

```python
# systems/gameplay/crafting/recipes/my_recipes.py
from systems.gameplay.crafting.blackout_recipe import BlackoutRecipe
from systems.gameplay.crafting.constants import CRAFT_CATEGORY_FOUNDRY

class MyNewRecipe(BlackoutRecipe):
    name = "My New Recipe"
    category = CRAFT_CATEGORY_FOUNDRY
    consumable_tags = ["rusty_metal_chunk"]
    tool_tags = ["hammer"]
    output_item_keys = ["rusty_scrap_metal"]
    required_skill = "foundry"
    required_level = 1
    xp_reward = 25
```

**Import `category` from `systems/gameplay/crafting/constants.py`. Never type
the literal.** The game matches a facility's `allowed_categories` against it
with exact string equality. Thus, `"Metalsmithing"` vs `"Metalsmith"` silently
hides every recipe in the category from the craft menu.
`BlackoutRecipe.__init_subclass__` now raises at import on an unregistered
category, so that bug cannot occur again.

---

## Stat Tracker

Generic counters and stats live in a single dict for each character, for example kills for each hostile type and credits spent. 

### In-game commands: inspect a character's stats

```bash
> py me.stats.all()
> py me.stats.get("kills_per_hostile")
> py me.stats.get("kills_per_hostile", key="mutant_raider")
```

### Adding a new tracked stat

1. Add a `STAT_KEY` constant in `systems/core/stat_tracker/constants.py`.
2. Add a matching `StatDef` to `STAT_REGISTRY` in `systems/core/stat_tracker/registry.py`.
3. Record an increment at the site of the event. Use this pattern:

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
`StatKind` in `systems/core/stat_tracker/registry.py` defines each stat type one
time. `StatHandler` defines how the game handles each type.

The source-of-truth definitions are in `systems/core/stat_tracker/registry.py`.

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

The command needs Builder permission. It searches the inventory and the
equipment slots.

### Put words in the world (`sign`, `marker`)

```bash
> sign TRADE TOWN                       # a sign reading TRADE TOWN, here
> sign north post = TRADE TOWN          # ...and call the object "north post"
> marker WIP -- no spawns past here     # a note to the developers
> sign                                  # what is labelled in this room
> destroy north post                    # remove one (Evennia's own command)
```

The command needs Builder permission. The Godot world view draws the text so
that it floats, so the command caps it at 64 characters over 3 lines and strips
color codes. Anything longer goes in the object's `desc`, which `read` shows
under the words:

```bash
> desc north post = Bolted over an older sign nobody has scraped off.
> read north post
```

A **sign** is worldbuilding that a player is meant to believe. A **marker** is
a note *about* the game. The world view draws it in a color that no signage
uses, so nobody mistakes one for the other.

The two live in the **database**, not in the map, so a map rebuild deletes them
with the tiles that they stand on. That is the right lifetime for an
annotation.

### Permanent signage belongs in the map

A signpost needs no new MAPSTR symbol and no tile of its own. There are two
ways to place one, and each is a single row beside the skill-node overrides:

```python
# world/maps/oasis.py
(1, 0): _signpost("OASIS\nBANK: EAST\nFORGE: NORTH"),   # a tile that is only a sign
(6, 3): _signed(_furnace, "FOUNDRY\nNO NAKED FLAMES"),  # a sign ON the furnace tile
```

Use `_signed` to label a facility. The tile keeps its own key, desc, minimap
color, and facility, and the sign stands beside it in the ring of the tile.
Thus, a sign no longer costs a neighboring tile.

**Signs dispatch from a room attribute, not from the room key.** That makes
sharing possible. `SPAWNER_REGISTRY` uses the room key, and a tile has exactly
one key. Thus, a tile with the key `Foundry Furnace Facility` can never also
have the key `Signpost`. `ATTRIBUTE_SPAWNER_REGISTRY` runs every spawner whose
attribute the tile declares. Thus, a tile can carry any number of decorations
on top of the one thing that it *is*.

The map module stays the **owner** of the words. The spawner sets them again
on every rebuild, so a typo fix is an edit plus a rebuild, not a destroyed
tile. `_signed` **copies** the prototype that it gets. Every facility prototype
is one dict, shared by every coordinate that names it. If `_signed` changed
that dict, it would sign all of those tiles.

The change takes effect on the next run of `clean_and_reload_all_maps.sh`.

### Player graffiti (`write`)

```bash
> write THE HEGEMONY LIES               # needs a spray can, spends one charge
> read graffiti
```

The command is available to everyone. The **medium is the gate**, not a
permission. A spray can (`spray_can` in `ITEM_DB`) holds 12 charges, and the
game destroys it when the last charge goes.

Every scrawl records **who wrote it and when**, and it expires after a week. A
global Script (`systems/gameplay/graffiti/decay.py`) sweeps the scrawls every
hour. To give someone a can:

```python
> py from world.item_database import ITEM_DB; ITEM_DB["spray_can"].create(location=me)
```

A blocklist seam exists, and it is **empty by default**. To refuse words, set
`BLACKOUT_GRAFFITI_BLOCKLIST` in settings to a tuple of those words. The
refusal happens before the command spends the charge.

Moderators erase the scrawls of a player from the egg, with **Erase what they
have written**. Before it asks for confirmation, that entry counts the scrawls
and names their author. It cannot reach map signage or builder markers. Those
are sibling typeclasses, not subclasses of `Graffiti`, so the query cannot
return them.

### The Moderator Egg

An in-game item that opens the moderator toolkit as a menu. Give yourself one:

```python
> py from world.item_database import ITEM_DB; ITEM_DB["moderator_egg"].create(location=self, home=self)
```

Then, with it in your inventory:

```bash
> egg
```

The lock of the command is `perm(Admin)`. Superusers bypass this lock, as they
bypass every other lock. The egg is inert in the hands of anyone else, and
`tradeable=False` keeps it out of shops and trades. The only way that an egg
gets to a player is that someone gives it to that player.

What the menu offers:

| Entry | Effect |
|---|---|
| Inspect | The target's full player dossier (the same one `score` renders) plus a staff addendum: dbrefs, the account and its permissions, god-mode state, the itemized bag, and every quest with live objective counters. Read-only. |
| Spawn an item | Any `ITEM_DB` key, 1 or N. Stackables arrive as one stack. The menu clamps a request larger than the grid and says so. |
| Spawn an NPC | Any `NPC_DB` key, 1-20, into **the target's room**. They land live and hostile, with the full combat block and respawn stamp `NpcDef.create` gives a map-placed one. |
| Toggle god mode | The target ignores all incoming damage. It persists on the CHARACTER, not the egg. If you drop the egg, god mode stays on. |
| Restore | Refresh max HP from Fortitude, heal to full, drop out of combat. |
| Empty inventory | Destroys everything carried **and equipped**. A confirmation that counts what it will destroy and names the owner comes first. Staff items are skipped. |
| Teleport to a map | Any map in `scripts/map_manifest.json`, landing on its `(0,0)` entrance tile. |
| Teleport to a player | Sends the target to whichever character you name. |
| Bring target to me | The same call with the arguments swapped. |
| Grant XP / Set a skill level | Any key in `SKILL_REGISTRY`. Levels accept the full 0-127 range. |
| Quests | Accept, abandon, complete, reset, or jump to any step of any quest in the registry. See below. |
| Boot or ban an account | Types Evennia's own `boot` / `ban` / `unban`. `ban` keeps its Developer lock. |
| Change target | Aims every entry above at another character. Blank resets to yourself. |

The egg protects itself. `Empty inventory` refuses to delete anything tagged
as a staff item. Thus, if you empty your own bag, the egg that you hold for
the job survives.

#### Quest testing

Use the quest screen to test content. It has four whole-quest writes plus a
step jump:

| Operation | What it does |
|---|---|
| Accept | Starts the quest properly -- seeds progress, fires step 1's `on_enter`. Indistinguishable from taking it from an NPC. |
| Abandon | Drops progress. **Leaves any completion record standing**, so a finished quest stays finished. |
| Complete | Marks it done and **pays the rewards**. Skipped steps' hooks do not fire. |
| Reset | Clears active *and* completed. The only one that makes a finished quest takeable again. |
| Jump to a step | Moves an active quest to any step, forward or back. Re-seeds that step's counters and fires its `on_enter`, so the quest keeps playing from there. |

Know the difference between Abandon and Reset. **Abandon** returns a quest in
progress to not-started, but does nothing to a quest already completed.
**Reset** is what a tester who replays content wants.

The step jump makes a five-step quest testable in minutes, with no full
replay. Accept the quest, jump to the step under test, exercise it, and jump
back.

Every action through the egg writes one `[MODTOOL]` line to the server log.
The line names the actor, the verb, and the target. A dossier read writes a
line too. To review a session:

```bash
grep MODTOOL server/logs/server.log
```

---

## Map Building Workflow

Use this procedure whenever you expand a grid, shrink a grid, change tile
coordinates, or change the layout of an ASCII map.

### Standard 5-step procedure

**1. Edit the Map File**
Make structural changes in `world/maps/<map_name>.py`.

- Define every new symbol in the `legend` dict, mapped to a `MapNode`.
- Obey Evennia's XYZGrid spacing rules (no spaces between rooms and links,
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

The script stops Evennia, runs `map_sync.py`, spawns, and reloads.

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

- **Add a row** → the rebuild loads the module, registers its map, and spawns
  its tiles.
- **Delete a row** → on the next rebuild, `map_sync.py` removes that map from
  the grid and deletes its tiles and exits. Anyone on a deleted tile goes home
  and is not deleted.

`map_sync.py` validates before it deletes anything. Every listed module must
import, yield exactly one map, and declare the z-coordinate that its row
claims. The script also reads the grid back after it registers the maps. Thus,
a map that fails to load stops the rebuild and does not quietly vanish from it.

Preview a rebuild with no changes (this is safe while the server runs):

```powershell
.\scripts\clean_and_reload_all_maps.ps1 -DryRun
```

```bash
./scripts/clean_and_reload_all_maps.sh --dry-run
```

### Rebuild one map, or one tile

A bare rebuild covers every map in the manifest, and the largest map decides
how long it takes. Two flags narrow it. Both repeat, and both work with
`-DryRun`.

```powershell
.\scripts\clean_and_reload_all_maps.ps1 -Map oasis
.\scripts\clean_and_reload_all_maps.ps1 -Tile "oasis:12,4","oasis:12,5"
.\scripts\clean_and_reload_all_maps.ps1 -Map oasis -Tile "azm_plains:3,3"
```

```bash
./scripts/clean_and_reload_all_maps.sh --map oasis
./scripts/clean_and_reload_all_maps.sh --tile oasis:12,4 --tile oasis:12,5
```

| Flag | Rebuilds |
|---|---|
| none | Every map in the manifest |
| `--map ZCOORD` | That map end to end |
| `--tile ZCOORD:X,Y` | That one tile, its exits, and the exits back into it |

The coordinates are the X,Y that `evennia xyzgrid show <map>` prints, not
character positions in the map string. A coordinate that carries no room stops
the run before it deletes anything.

Three rules apply to a scoped run:

- **It never removes a map.** Removal is about a map the manifest lists
  nowhere, so only a bare rebuild prunes. Delete a manifest row, then run a
  bare rebuild.
- **It never deletes a room that fell off the map string.** A tile rebuild is
  told one coordinate, and a stale room sits at a coordinate you did not name.
  Run `--map` or a bare rebuild after you shrink a map.
- **A map named by both flags is rebuilt whole.** The whole map is the
  superset. The run prints the scope it resolved to, on the line that starts
  `This run rebuilds`.

---

## Color Reference

Evennia uses `|`-prefixed markup to color terminal text. Tags compose inline. Wrap any character or string.

**In game code, do not type these tags directly.** Import the named palette
from `systems/interface/ui/colors.py` (`TITLE_COLOR`, `HIGHLIGHT_COLOR`,
`SUCCESS_COLOR`, `ERROR_COLOR`, `RESET_COLOR`, …) and the `dialog()` /
`highlight()` / `title()` wrappers. Use the table below to read existing markup
and to pick new palette entries. Nine modules once carried their own copy of
these literals, so a retheme meant a search for all nine.

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

A typo in a map file (for example, a symbol not in your legend) can cause
`spawn` to crash with a `RuntimeError`. Then, the standard `delete` command can
miss the ghost tiles that stay behind.

**1.** Fix the typo or the legend mismatch in the map file.

**2.** Sweep the database manually with `evennia shell`:

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
| `scripts/map_sync.py` | Reconciles the grid with `map_manifest.json`: removes unlisted maps, purges and re-registers listed ones. `--map` and `--tile` narrow the run | `../evenv/Scripts/python.exe scripts/map_sync.py [--dry-run] [--map ZCOORD] [--tile ZCOORD:X,Y]` (from `blackout/`) |
| `scripts/clean_and_reload_all_maps.ps1` | Automated map rebuild (stop → sync → spawn → reload), over the whole manifest or one scope | `.\scripts\clean_and_reload_all_maps.ps1 [-DryRun] [-Map oasis] [-Tile "oasis:12,4"]` |
| `scripts/clean_and_reload_all_maps.sh` | Same rebuild from Git Bash | `./scripts/clean_and_reload_all_maps.sh [--dry-run] [--map oasis] [--tile oasis:12,4]` |
| `scripts/backup_db.py` | Snapshots the live sqlite3 database into `server/backups/` (gzip, timestamped), pruning old backups beyond `--keep` | `../evenv/Scripts/python.exe scripts/backup_db.py [--keep N] [--dest DIR]` (from `blackout/`) |
| `scripts/backup_db.ps1` / `.sh` | Argument-light wrappers around `backup_db.py`, meant for Task Scheduler / cron | `.\scripts\backup_db.ps1 [-Keep N] [-Dest DIR]` |

---

## Running Tests

### Always use `test_settings.py`

Pass `--settings test_settings.py`, not `--settings settings.py`. It is
`settings.py` with two changes. The first is the Django password hasher.
Evennia's test fixtures create two accounts for each test method, and the
default PBKDF2 hasher costs 0.46s for each account. The hasher change alone
took the full suite from ~20 minutes to 6.4. See
`../docs/old/2026-08-23-TEST-0001-suite-audit.md`.

The second change is `TEST_RUNNER`, which applies `gc.freeze()` after setup
(`server/conf/testrunner.py`).

### Quick testing (most common)

During development, run **only the module(s) that you changed**. These runs
finish in seconds:

```bash
# Single module
../evenv/Scripts/evennia.exe test --settings test_settings.py systems.gameplay.banking.tests

# Multiple modules
../evenv/Scripts/evennia.exe test --settings test_settings.py systems.gameplay.combat.tests systems.gameplay.crafting.tests
```

### Full test suite (only when necessary)

**2879 tests, ~23 minutes** (measured 09/21/2026). Run it before a merge, or
when a change affects more than one system:

```bash
../evenv/Scripts/evennia.exe test --settings test_settings.py items systems typeclasses commands world profiling analysis
```

Append `--durations 20` to see the slowest tests.

All six roots in the command hold tests. **If you omit a root, the suite
silently runs fewer tests and
gives no error.** That is how nobody noticed `world/tests/`. Plain
`evennia test .` is *not* equivalent: it collects fewer tests.

`--parallel` does not work. Django's cloned worker databases do not carry the
dbrefs that `EvenniaTestMixin` assumes, and every worker dies in `setUp` on
`settings.DEFAULT_HOME (= '#2') does not exist`. Do not spend time on it.

### Writing tests

Every test module must be a `unittest.TestCase` subclass. **Do not write bare
module-level `def test_*()` functions.** Django's unittest discovery skips them
silently. ~27 tests (one of them a real failure) sat unrun that way until
someone converted them.

`pytest` is installed but **`pytest-django` is not**, so pytest cannot
bootstrap the DB the Evennia suites need. It is not the runner for this
project.

Test files live beside the code that they test, in a `tests/` package
(`systems/gameplay/banking/tests.py` is the one legacy exception). **A `tests/`
directory needs an `__init__.py`**, or the runner collects nothing inside it.

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
| List available recipe categories | `py from systems.gameplay.crafting.crafting_service import get_categories; get_categories()` |
| Set a character attribute | `py self.search("testchar2").db.has_cutting_reward = True` |
| Delete all GridTile rooms | `py from typeclasses.rooms import GridTile; GridTile.objects.all().delete()` |
| Count objects by typeclass | `py from typeclasses.characters import Character; Character.objects.all().count()` |
| Teleport to a grid coordinate | `> teleport (5,3,oasis)` |