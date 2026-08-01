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
| `scripts/` | **Destructive operator CLI scripts. See the warning below.** |

> **Read the installed Evennia, not the submodule.** Imports resolve to
> `evenv/Lib/site-packages/evennia/`, which can differ from the pinned
> submodule. When checking contrib behaviour, read the installed copy.

## Danger: `blackout/scripts/`

These act on the **live** development database, not a test DB. One of them
(`xyz_cleanup.py`) deletes map rooms.

**Never write a loop that bulk-imports modules under `blackout/`** — for an
import check, a linter, a doc pass. Doing so once executed `xyz_cleanup.py` and
deleted 347 grid rooms. It now has an `if __name__ == "__main__"` guard, but
treat everything in `scripts/` as import-unsafe and exclude the directory
explicitly.

Maps are regenerable from `world/maps/*.py` via
`scripts/clean_and_reload_all_maps.ps1`; accounts and characters are not stored
there.

## Testing

One command, run from `blackout/`:

```bash
../evenv/Scripts/evennia.exe test --settings settings.py items systems typeclasses commands world
```

- **Omitting a root silently runs fewer tests** rather than erroring. `items`,
  `systems`, and `world` are the roots that hold tests.
- `evennia test .` is **not** equivalent — it collects fewer tests, because
  `world/maps/test_oasis.py` and `test_neo_cairo.py` are map definitions whose
  names match the discovery pattern.
- Every test module must subclass `unittest.TestCase`. **Bare module-level
  `def test_*()` functions are silently skipped** by Django's discovery.
- A `tests/` directory without `__init__.py` is not collected at all.
- `pytest` is installed but **`pytest-django` is not**, so pytest cannot
  bootstrap the DB. It is not the runner here.

Server control: `../evenv/Scripts/evennia.exe status | reload | start | stop`

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

## Design intent

Gameplay rules come from the Obsidian vault, not from the code:

```
C:\Users\NickR\OneDrive\Documents\Obsidian Vault\Blackout\
```

Check it before changing any gameplay rule. Example: max HP scales 1:1 with
Fortitude because `02_Player/Player_Overview.md` says so.

Combat maths is OSRS-derived, rescaled from OSRS's 1–99 to Blackout's 0–127.
The formulas are scale-agnostic, so raw OSRS monster stats transfer directly.
