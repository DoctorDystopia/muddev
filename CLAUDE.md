# Blackout — Repo Conventions

Cyberpunk MUD on **Evennia 6.0.0**. This file is the orientation doc for
working in this repo. Player-facing and operator recipes live in
[blackout/README.md](blackout/README.md); design intent lives in the Obsidian
vault (see below).

## Layout

```
muddev/
├── blackout/        the Evennia game dir — all game code, all commands run from here
├── evennia/         engine, git submodule (v6.0.0 +119 commits, untagged master)
├── evenv/           virtualenv, NOT on PATH; the INSTALLED evennia lives here
├── docs/            dated engineering/design notes (YYYY-MM-DD-TAG-NNNN-slug.md)
├── style.md         the coding style contract — read it before writing code
└── tutorial_game/   stock Evennia tutorial dir, unrelated to Blackout
```

Inside `blackout/`:

| Directory | Holds |
|---|---|
| `systems/` | Game systems: `combat/`, `crafting/`, `progression/skills/`, `banking/`, `shop/`, `quests/`, `menus/`, `spawning/`, `ui/` |
| `items/` | `equipment/` and `inventory/` handlers + slot constants |
| `typeclasses/` | Evennia typeclasses; `mixins.py` holds `CombatEntity` |
| `world/` | Data registries: `item_database.py`, `npc_database.py`, `item_defs/`, `npc_defs/`, `shop_defs/`, `maps/` |
| `commands/` | Command classes and cmdsets |
| `web/` | Django site + the 3D webclient. See "The webclient" below. |
| `scripts/` | **Destructive operator CLI scripts. See the warning below.** |

> **Read the installed Evennia, not the submodule.** Imports resolve to
> `evenv/Lib/site-packages/evennia/`, which can differ from the pinned
> submodule. When checking contrib behaviour, read the installed copy.

## Danger: `blackout/scripts/`

These act on the **live** development database, not a test DB. One of them
(`map_sync.py`, formerly `xyz_cleanup.py`) deletes map rooms.

**Never write a loop that bulk-imports modules under `blackout/`** — for an
import check, a linter, a doc pass. Doing so once executed the map cleanup
script and deleted 347 grid rooms. Everything in `scripts/` is now behind an
`if __name__ == "__main__"` guard, but treat the directory as import-unsafe and
exclude it explicitly.

`export_client_constants.py` is the one file here that touches no database — it
only renders the generated client constants — but it lives behind the same
guard, and code that needs its output should import
`systems/statefeed/clientexport.py` instead. That is why the output-path table
lives in `clientexport.py` rather than in the script: the test that checks the
generated files are current cannot import this directory.

Maps are regenerable from `world/maps/*.py` via
`scripts/clean_and_reload_all_maps.ps1`; accounts and characters are not stored
there.

**`scripts/map_manifest.json` is the one file that decides which maps exist.**
Adding a row adds a map; deleting a row removes that map and its rooms on the
next rebuild. The manifest is parsed by `world/maps/manifest.py` (importable,
tested) and applied by `scripts/map_sync.py`; the `.ps1`/`.sh` rebuild scripts
are thin wrappers around it. `scripts/clean_and_reload_all_maps.ps1 -DryRun`
(`--dry-run` for the `.sh`) reports the diff without touching anything.

## Testing

**Always pass `--settings test_settings.py`, never `settings.py`.** The only
thing it changes is the password hasher, and that alone is the difference
between a 6-minute suite and a 20-minute one — see
[docs/old/2026-08-23-TEST-0001-suite-audit.md](docs/old/2026-08-23-TEST-0001-suite-audit.md).

**During development:** run only the modules you changed (seconds):

```bash
../evenv/Scripts/evennia.exe test --settings test_settings.py systems.banking.tests
```

**Before merging or major changes:** run the full suite (1324 tests, ~6.6 min):

```bash
../evenv/Scripts/evennia.exe test --settings test_settings.py items systems typeclasses commands world
```

Add `--durations 20` to either to see where the time went.

Details:
- **Omitting a root silently runs fewer tests** rather than erroring. `items`,
  `systems`, and `world` are the roots that hold tests.
- `evennia test .` is **not** equivalent — it collects fewer tests.
- Every test module must subclass `unittest.TestCase`. **Bare module-level
  `def test_*()` functions are silently skipped** by Django's discovery.
- A `tests/` directory without `__init__.py` is not collected at all.
- `pytest` is installed but **`pytest-django` is not**, so pytest cannot
  bootstrap the DB. It is not the runner here.
- **`--parallel` does not work.** Django's cloned worker databases do not
  carry the dbrefs `EvenniaTestMixin` assumes, so every worker dies in setUp
  on `settings.DEFAULT_HOME (= '#2') does not exist`. Don't spend time on it.

### Writing tests

- **Inherit the cheapest base class that works.** `EvenniaTest` builds two
  accounts, two rooms, two objects, two characters, an exit, a script and a
  session *per test method*. If a test never touches `self.char1` and friends,
  it is paying ~0.2s for nothing — use `EvenniaTestCase` (DB, no fixtures) or
  plain `unittest.TestCase` (no DB).
- **Never assert a census of a registry.** `assertEqual(sorted(RECIPE_REGISTRY),
  [six literal names])` fails when someone adds a seventh recipe as intended,
  which trains everyone to edit the test rather than read it. Derive the
  expectation from the source of truth — the modules in
  `settings.CRAFT_RECIPE_MODULES`, the `ItemDef`, the `WieldLocation` enum —
  and assert the *relationship*: everything defined is registered, every
  registered entry is well-formed, every slot has a label.
- **Wrap registry loops in `self.subTest(...)`.** A bare
  `for item_def in ITEM_DB.values():` stops at the first bad entry and hides
  the rest; `subTest` reports all of them and names the offender.
- Assert on message *keywords*, not whole sentences —
  `assertIn("aren't carrying", response.lower())` survives a copy edit.
- Inject a seeded `random.Random(...)` or a scripted stub; never let a test
  read the global RNG.

## Commits

**`DoctorDystopia` is the sole author of every commit. Do not add a
`Co-Authored-By:` trailer**, for Claude or for any other tool.

The reason is that the trailer is redundant here rather than unwanted: this
file exists, it is checked in, and it is addressed to an AI assistant — so the
repository already records how it is worked on, in more detail than a trailer
could. Repeating that on every commit adds a line to every message and tells a
reader nothing the tree does not already say.

Write the message about the change: what moved, and why it had to. The existing
history is the model — a subject line naming the thing that changed, then prose
explaining the decision, not a list of files.

## Code conventions

**`style.md` is the contract.** Docstrings carry Purpose / Entry /
Exit-Returns / Module Globals / Methodology / Notes-References / Author &
Date. Also: 4-space indent, ~50-line routine cap, no magic literals, no
embedded calls inside `return` or `if`, private symbols prefixed `_`.

**Prefer data over branches.** The codebase has four registries to match rather
than reinvent:

| Pattern | Example |
|---|---|
| Package auto-discovery | `systems/progression/skills/registry.py` |
| Settings-driven discovery | `systems/crafting/registry.py` |
| Decorator registration | `@register_spawner` in `typeclasses/spawners.py` |
| Data table + dataclass | `world/item_database.py`, `world/npc_database.py` |

Adding a skill, recipe, item, or NPC should mean **adding one file or one dict
entry**, never editing a dispatch chain.

**One owner per fact.** Colours in `systems/ui/colors.py`; crafting categories
and tag categories in `systems/crafting/constants.py`; combat tunables in
`systems/combat/constants.py`; slot labels on the `WieldLocation` enum. Typing
a literal that already has a named constant is how the "Metalsmith" vs
"Metalsmithing" bug hid every anvil recipe.

The rule crosses the language boundary too — see the webclient section below.

## The webclient

A 3D world pane and a 3D inventory pane, drawn with three.js, docked beside the
text. Full audit and design rationale:
[docs/old/2026-08-23-ENG-0004-webclient-architecture.md](docs/old/2026-08-23-ENG-0004-webclient-architecture.md).

**Python owns what is TRUE about the game; JavaScript owns what it LOOKS like.**
That line decides every question about where something belongs. Channel names,
asset kinds, item families and tile affordances are the server's. Colours, mesh
shapes, camera angles and the model registry are the client's.

**The server names; the client draws.** When the client would branch on what
something *is*, the server should already have said what can be *done* with it.
`serialize_entity` sends `interact: "attack mutant raider"`; `tile_actions`
sends `{command, kind}` per tile; `serialize_inventory` sends whole commands.
The client sends them verbatim. A client verb table has been deleted twice for
being wrong within a week — do not add a third.

**The pane sends only what a telnet player could type.** Clicking a tile sends
`["text", ["north"], {}]`. There is no privileged client channel that bypasses
a Command, so every lock, permission and cooldown keeps working with no audit.

### Regenerate after editing `systems/statefeed/constants.py`

```bash
python scripts/export_client_constants.py
```

It renders `web/static/webclient/js/generated/blackout_constants.js` **and**
`godot/autoload/blackout_constants.gd` from the Python. Both are committed, and
a test fails if either is stale — so a missed run is loud, not silent. Never
hand-edit a generated file. `--check` writes nothing and exits non-zero, for CI.

### ES modules, one entry point

`web/templates/webclient/base.html` carries **one** `<script type="module">`
pointing at `blackout_main.js`, plus an import map for `three` and
`three/addons/`. Dependencies are imports, not script order.

- **`plugins/hotkeys.js` must stay a CLASSIC script.** It has to load before
  Evennia's `default_in.js`, and a module runs after every classic script *by
  definition* — converting it silently breaks movement keys while everything
  else keeps working.
- A module script is deferred, so it runs after all classic scripts but
  **before** `$(document).ready`, which is when `plugin_handler.init()` fires.
  That window is the only reason the panes can register in time.
- three.js is vendored as ESM at **r159**, loader and core the same release.
  Upgrading is now a normal bump; the UMD build it replaced was removed
  upstream at r161 and was a hard ceiling.

### Panes

`js/shell/pane.js` owns everything a pane needs that is not about drawing:
GoldenLayout registration, the single-pane guard, opening, channel claiming and
message routing. A pane calls `createPaneShell({name, title, build, route,
channels})` and keeps its scene, camera, picking and teardown. **A new pane is
a call to that, not another copy of 160 lines** — which is what the two panes
were until 08/23/2026.

JavaScript tests live in `web/jstests/` and need no dependencies:

```bash
node --import ./register.mjs --test
```

They cover pure logic only — `tileAction` is the model case. Rendering, layout
and input are not tested; the pane is non-essential by design, so a headless
browser is not worth its cost.

### Client-side facts that cannot be generated

`ROOM_KIND_COLORS` and `Z_LAYOUT_ORDER` mix a server fact (which room kinds and
maps exist) with a client one (what colour, what order). They are guarded
instead of generated, by `systems/statefeed/tests/test_client_constants.py`.
The asymmetry is deliberate: **a client key naming nothing is a bug; a server
fact with no client entry is fine** — both tables document a fallback, so
adding content must never require a client edit.

### An item may belong to several families

`ItemDef.tags` is a LIST of `(key, category)` pairs and Evennia files each pair
independently, so **an item declares as many families as it belongs to** — the
rusty scrap axe is `crafting_tool` *and* `weapon`. A recipe finds it under the
first (`_has_tool_available` asks only whether that one category carries the
value); the pane picks its mesh out of the second. Neither reader cares that
the other tag is there.

Which family a multi-family item resolves to is decided by
`ITEM_FAMILY_PRIORITY` in `systems/statefeed/constants.py`, **never by tag
order** — Evennia returns an object's tags as an unordered set, so a reader
taking the first family category it sees can answer differently on two calls
about the same item, and the axe would render as a tool in one session and a
weapon in the next. `ITEM_FAMILIES` is derived from that tuple so the ordered
and the membership view cannot list different families.

**A family tag is a look, not a rule.** Nothing in combat reads one:
`_combat_style_source` reads `combat_styles` and `attack_speed` off the wielded
object and never asks its tag or its typeclass. An ItemDef tagged `weapon` with
no `combat_styles` therefore renders as a weapon and swings at unarmed speed
and unarmed accuracy — which is exactly the trap a tool being given a second
family walks into. `test_an_item_in_the_weapon_family_can_actually_fight` in
`world/tests/test_item_database.py` asserts the relationship over `ITEM_DB`, so
a weapon added tomorrow is covered without an edit.

## Evennia gotchas found the hard way

1. **`evennia.utils.utils.crop` is not ANSI-aware** in this build — it measures
   with plain `len()`. Use `evennia.utils.ansi.ANSIString` for width maths.
2. **`EvTable(width=N, evenwidth=True)` is broken together** — it collapses
   columns to width 1. `width` alone is fine.
3. **An EvMenu *node* must return `(text, options)`.** `_execute_node` treats a
   non-tuple return as display text, so returning a node *name* from a node
   prints that string at the player. Only *goto callables* return node names.
4. **`copy_object()` / `DefaultObject.copy()` fail** when the destination's
   `at_object_receive` mutates the incoming object — the inventory stack-merge
   calls `obj.delete()` on it and the contrib then writes to a deleted row.
   Build detached (`location=None`), populate, then `move_to`.
5. **`create_object(location=...)` does not fire `at_object_receive`;
   `move_to` does.** That difference decides whether an item registers in an
   inventory slot and whether stackables merge.
6. **Sub-second timers need a twisted `LoopingCall`.** `ScriptDB.db_interval`
   is a Django `IntegerField` (0.6 truncates to 0) and `TickerHandler` rejects
   sub-second intervals. See `systems/combat/tick_engine.py`.
7. **`lazy_property` caches into `obj.__dict__` under its `__name__`** and its
   deleter raises. Clear it with `obj.__dict__.pop("name", None)`; when
   building accessors from a factory, pass `name=` explicitly or they collide.
8. **Django compiles template tags inside HTML comments.** The `<!-- -->` is
   stripped by the *browser*, long after the engine has parsed the file — so
   writing a tag in explanatory prose is a `TemplateSyntaxError` that 500s the
   whole page. A bare `static` tag in a comment in `base.html` did exactly
   that. Never write tag braces in template prose, not even as an example.
9. **Evennia's emitter keeps ONE listener per channel name.** `Evennia.emitter`
   does `listeners[cmdname] = listener`, so a second plugin binding a name is a
   silent *theft*, not a second subscription — the first stops receiving a
   channel it believes it still handles. `blackout_channels.js` is a
   first-claim-wins registry that makes the collision loud and local.

## The quest system

`systems/quests/` splits four ways, and the split is load-bearing:

| Module | Holds | May import |
|---|---|---|
| `constants.py` | The action vocabulary, status strings, message templates | `systems/ui/colors.py` |
| `quests.py` | `QuestStep`, `QuestBlueprint` — the shapes content declares | `constants` **only** |
| `loader.py` | `GLOBAL_QUEST_REGISTRY`, package auto-discovery of `content/` | `content` |
| `handler.py` | `QuestHandler` — one character's progress | `loader`, `quests`, `constants` |

**`quests.py` must never import `loader.py`.** The loader builds its singleton
at import time by importing every module under `content/`, and every one of
those imports `QuestBlueprint` back out of `quests.py`. An import of the
loader at `quests.py` scope closes that ring, and the third hop finds a
half-initialized module. That was the live state of the game until 08/25/2026:
`typeclasses/characters.py` imported the handler first, so every content
module raised `ImportError` inside the loader's `except Exception`, and
**`GLOBAL_QUEST_REGISTRY` came up empty**. The only symptom was a quest that
could not be accepted. `QuestRegistry.load_errors` plus
`test_quest_registry.py` are what make that loud now.

**Game systems call `notify_quests`, never `update_progress`.**

```python
from systems.quests import constants as quest_constants
from systems.quests.hooks import notify_quests

notify_quests(killer, quest_constants.ACTION_KILL, npc_key)
```

A system knows what the player *did*, not which quest wanted it. `at_death`
used to pass the literal quest key `"*"` meaning "any active quest" — never
implemented, so no kill objective could ever advance. `notify_quests` is that
fan-out, and it tolerates an actor with no quest handler, drops an
undocumented verb loudly, and never raises.

**The argument is a stable snake_case key, never a display name** —
`db.npc_key`, a recipe key, an `ItemDef` key.

**The verb vocabulary has one owner in two files that cannot drift.**
`QUEST_ACTIONS` in `constants.py` and the level-3 verb headings in
`global_quest_actions.md` are asserted equal in both directions by
`test_quest_vocabulary.py`. A `QuestStep` naming an undocumented action raises
at import — which the loader turns into a failing test rather than an
objective that silently never fires.

**Nothing outside `handler.py` reads `db.active_quests`.** Dialogue nodes, the
`quest` command and the summary panel go through the read API (`status`,
`is_active`, `on_step`, `current_step`, `objective_lines`). Three modules
owning that fact is how the android's dialogue came to print `talk:tester: 0/True`
at players.

Progression hooks currently live in `typeclasses/mixins.py` (`kill`),
`systems/crafting/crafting_service.py` (`craft`),
`skill_defs/gathering/cutting.py` (`cut`, `gather`) and `typeclasses/rooms.py`
(`visit`, opt-in per room via `db.quest_visit_key`). `talk` is fired by
dialogue nodes, not by `CmdTalk` — one NPC can be two different targets.

## The moderator egg

An in-game item (`egg`) that opens a menu of staff actions. Three modules, and
the split is the same one the quest system makes:

| Module | Holds | May import |
|---|---|---|
| `systems/devtools/constants.py` | The god-mode attribute name, the audit vocabulary, the bounds, the message templates | `systems/ui/colors.py` |
| `systems/devtools/actions.py` | The effects. Every one is `(actor, target, ...) -> (succeeded, message)` | `constants`, plus whatever system it reaches into |
| `systems/devtools/dossier.py` | The read-only report. Changes nothing | `constants`, `actions`, `systems/summary/` |
| `systems/menus/dev_egg_menu.py` | EvMenu nodes. Presentation only | `actions`, `dossier`, `constants`, `base_menu` |

`dossier.py` is split from `actions.py` on the read/write line, so a reviewer
can tell at a glance which of the two a moderator screen is calling. Most of
the report is not written there at all: `systems/summary/` already renders a
character's dossier and owns what that contains, so the module adds only the
staff half (dbrefs, the account, god mode, the itemised bag, live quest
counters) and pastes the player's own screen above it **verbatim** — a
moderator asking "is this what they are looking at" cannot be answered by a
re-render of the same numbers. It is named `dossier` and not `inspect` because
a module called `inspect.py` inside a package shadows the standard library the
moment anything grows a relative import, and `systems/summary/registry.py`
depends on the real one.

**The menu is not in the package on purpose.** An effect has to stay callable
from a test, a script or a future command with no EvMenu anywhere; a package
that imports EvMenu is one a test has to boot a session to touch.

**`CmdEgg`'s lock is the entire permission story.** `cmd:perm(Admin)`, checked
once, before the menu opens. Nothing in `actions.py` checks a permission, and
nothing should start — a check repeated per effect is one that gets forgotten
on the ninth.

**Nothing here re-implements what already exists.** Boot and ban type
Evennia's own commands through `execute_cmd`, so the `server_bans` ServerConfig
row keeps one writer and `ban`'s Developer lock still refuses an Admin. The
item, skill and map lists are read live from `ITEM_DB`, `SKILL_REGISTRY` and
`scripts/map_manifest.json`, so adding content reaches the menu with no edit
in `systems/devtools/`.

**Quest writes belong to `QuestHandler`, not to the tool.**
`force_complete_quest`, `force_step` and `reset_quest` sit beside
`accept_quest` in `systems/quests/handler.py` for the reason CLAUDE.md already
gives: `db.active_quests` has exactly one owner, and a staff tool writing it
directly would be the fourth module to own that fact. They are the write path
a test fixture or a content migration needs too — the same role
`skills.logic.set_level` plays next to `add_xp`. Three rules they encode:
a forced completion **pays rewards** (exercising that callback is the main
reason to force one); a step jump **re-seeds** the destination's counters and
fires its `on_enter`, but nothing for the steps it skipped; and **reset is not
abandon** — abandon leaves a completion record standing, reset is what makes a
finished quest takeable again.

**One irreversible entry, and it is guarded twice.** `Empty inventory` is the
only thing on the tool that cannot be undone by doing something else, so it is
the only one behind a confirmation — and the confirmation counts what it will
destroy and names whose it is, because a moderator who reads "31 carried and 4
equipped from Bob" catches a wrong target while one who reads "are you sure?"
confirms it. The second guard is `DEV_TOOL_TAG_CATEGORY`, which lives in
`systems/devtools/constants.py` and is imported by `world/item_defs/dev_tools.py`
rather than typed there: the ItemDef stamps the tag and `clear_inventory`
refuses to delete anything carrying it, and a staff item whose tag disagreed
with that check is one a moderator destroys by emptying their own bag.

**God mode is the one new game rule.** A flag on the CHARACTER, read in
`CombatEntity.at_damage` (`typeclasses/mixins.py`), which returns 0 before the
HP write. It is read inline there rather than through
`actions.godmode_enabled`, because that module pulls in `ITEM_DB`, the skill
registry and the xyzgrid contrib and `at_damage` is the combat hot path — every
combatant, every tick. Only the attribute NAME is shared, from `constants.py`,
and `test_actions.py` asserts the two readers agree. The attacker is recorded
*before* the immunity check, so an immune moderator still draws aggro.

Every effect writes one `[MODTOOL]` audit line naming actor, verb and target.

## Design intent

Gameplay rules come from the Obsidian vault, not from the code:

```
C:\Users\NickR\OneDrive\Documents\Obsidian Vault\Blackout\
```

Check it before changing any gameplay rule. Example: max HP scales 1:1 with
Fortitude because `02_Player/Player_Overview.md` says so.

Combat maths is OSRS-derived, rescaled from OSRS's 1–99 to Blackout's 0–127.
The formulas are scale-agnostic, so raw OSRS monster stats transfer directly.
