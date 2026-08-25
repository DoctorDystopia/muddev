# Blackout (muddev) — Architecture & Code Review

Reviewed at `42ea3c6`. Scope: `blackout/` game dir (321 `.py` files, 11,731 SLOC,
11,705 docstring lines, 47 test modules). Evennia submodule excluded.

---

## Verdict

This is unusually disciplined for a solo MUD project. You have a written style
contract, an orientation doc that encodes real debugging history, four named
registry patterns, data-driven item/NPC/loot definitions, a rules pipeline with
priority-resolved seams, and 10.8k lines of tests. Average cyclomatic complexity
is A-grade; only 19 of ~1000 routines exceed your own 50-line cap.

So this review isn't about sloppiness. The problems are the specific failure
modes of a codebase that grew **system by system, each one well-built, without a
shared kernel layer underneath them.** Every system reinvented the same three or
four primitives, and each reinvention is individually reasonable.

The single biggest structural observation, and the one that answers your state
machine question directly: **combat state is represented five different ways at
once, and nothing guarantees they agree.**

---

## 1. Combat state is implicit and duplicated (the state machine finding)

"Is this entity in combat?" is currently answered by five independent facts:

| Representation | Storage | Written by |
|---|---|---|
| `db.in_combat` | persistent Attribute | `init_combat_attrs`, `start_combat_state`, `end_combat`, `leave_combat`, `purge_stale_combat_handlers` |
| Handler script exists | ScriptDB row | `ensure_combat_handler` / `end_combat` |
| `db_is_active` | ScriptDB column | `mark_running()` — set by hand, because Evennia won't |
| Tick engine registry membership | `engine.ndb._handler_ids` | `register` / `unregister` / silent discard on exception |
| `ndb.pending_action is None` | in-memory | `queue_action`, `tick` |

These can and do drift. The code already carries the scar tissue:

- `purge_stale_combat_handlers()` exists to repair the drift at boot.
- `get_handler_for` filters on `is_active` specifically to avoid returning a
  parked script.
- `ensure_combat_handler` has a delete-and-recreate branch for handlers "written
  under an older/broken configuration."
- `_tick` **discards a handler from the rotation on any exception**, whose only
  symptom is combat silently stopping — which is why `tick_debug.py` (861 lines)
  had to be written to tell a stalled fight apart from a dropped handler.

That last one is the tell. You built a diagnostic subsystem because the state is
unobservable. An explicit state machine makes the diagnostic mostly unnecessary.

### Proposal

One authoritative field, everything else derived:

```python
# systems/combat/states.py
class CombatState(Enum):
    IDLE        = auto()   # handler may exist; no engagement
    ENGAGED     = auto()   # has a target, action pending
    RECOVERING  = auto()   # mid-cooldown between swings
    DISENGAGING = auto()   # flee resolved, teardown pending
    DEAD        = auto()

# (state, event) -> state. A table, not a branch chain — matches your
# "prefer data over branches" rule.
TRANSITIONS = {
    (CombatState.IDLE,       Event.ATTACK_QUEUED): CombatState.ENGAGED,
    (CombatState.ENGAGED,    Event.SWING_LANDED):  CombatState.RECOVERING,
    (CombatState.RECOVERING, Event.COOLDOWN_DONE): CombatState.ENGAGED,
    (CombatState.ENGAGED,    Event.TARGET_LOST):   CombatState.IDLE,
    (CombatState.ENGAGED,    Event.FLED):          CombatState.DISENGAGING,
    (CombatState.ENGAGED,    Event.OWNER_DIED):    CombatState.DEAD,
    ...
}
```

Then:

- `db.in_combat` stops being stored and becomes
  `@property def in_combat(self): return self.combat_state is ENGAGED/RECOVERING`.
  That deletes five write sites and makes the summary panel, the statefeed
  payload, `examine`, and `CmdFlee` structurally incapable of disagreeing. (Your
  CLAUDE.md already states the principle — "One owner per fact" — this is the
  largest violation of it in the repo.)
- Illegal transitions raise or log instead of silently producing a wedged
  handler.
- `tick_debug status` becomes "print the state and the last transition."

### Second benefit: it collapses the exit-check thicket

`ActionAttack.resolve` currently has **six** separate "should combat end?"
checks:

```python
if target is None: ...                                   # 1
if not hasattr(target, "is_alive") or not target.is_alive(): ...  # 2
if killed: ...                                           # 3
if self_killed: ... (+ a handler.pk is not None guard)   # 4
if target.pk is None: ...                                # 5
if hasattr(target, "is_alive") and not target.is_alive(): ...     # 6
```

Checks 2 and 6 are the same predicate at different times; 5 exists only because
an NPC deletes itself inside `at_damage`. With a state machine, the action emits
an event (`TARGET_LOST`, `TARGET_KILLED`, `SELF_KILLED`) and the transition table
decides — the action stops needing to know about handler teardown or `.pk` at all.

---

## 2. Actions are already a Command pattern — finish the job

`_Action` with `consumes_cooldown` + `next_action()` is genuinely good OCP work,
and the docstring is right that it keeps `tick()` free of `if kind ==` branches.

But transition logic still leaked back into `tick()`: the cooldown decrement, the
keep-alive check, the `speed - 1` recharge arithmetic, and a post-action target
liveness check all live there. `tick()` is cyclomatic 14 — the second most
complex routine in the codebase.

Have `resolve()` return an outcome instead of a bool:

```python
@dataclass
class TickOutcome:
    event: Event                    # what happened
    next_action: _Action | None
    cooldown_ticks: int = 0
```

`tick()` then reduces to: decrement, resolve, feed the event to the transition
table, apply the outcome. Roughly 12 lines, complexity ~4. And a new action type
becomes a file, never an edit to the loop — which is the standard you already set
for skills, recipes, items, and NPCs.

---

## 3. `ensure_combat_handler` and `ensure_aura_handler` are the same function

Compare `systems/combat/combat.py:1140` with
`systems/combat/auras/aura_handler.py:393`. They are ~50 lines each and differ
only in the key string, the class, and the accessor name being popped. Same for
`get_handler_for` / `get_aura_handler_for`, same for `mark_running`, same for
`init_runtime_state`, same for the `__dict__.pop(accessor, None)` dance (which
appears **9 times** across the repo).

```python
# systems/combat/tickable.py
class TickableHandler(DefaultScript):
    HANDLER_KEY: str
    ACCESSOR_NAME: str          # the lazy_property name to invalidate

    def mark_running(self): ...
    def init_runtime_state(self): ...
    def tick(self): raise NotImplementedError

def ensure_handler(owner, handler_cls) -> TickableHandler: ...
def get_handler_for(owner, handler_cls) -> TickableHandler | None: ...
```

Two ~50-line functions and two ~12-line functions collapse into one of each.

### It also closes an OCP hole you already documented

`_tickable_handler_keys()` carries this warning:

> Any new tickable handler must be added HERE as well as registering itself, or
> it will work until the first reload and then silently stop forever.

That's a hand-maintained dispatch list — exactly what CLAUDE.md forbids. With a
base class it becomes `TickableHandler.__subclasses__()`, or a
`@register_tickable` decorator matching the `@register_spawner` pattern you
already use in `typeclasses/spawners.py`.

**Same hole in `server/conf/at_server_startstop.py`:** three hand-listed
`bootstrap_*()` calls. Adding a fourth global system means editing that file.

---

## 4. Four near-identical "global manager Script" implementations

`BlackoutTickEngine`, `BlackoutRegenManager`, `BlackoutRespawnManager` (and
`BlackoutAuraHandler` as the per-entity variant) all independently implement:

- a `*_KEY` module constant
- `get_X()` — lazy singleton lookup-or-create, raise on `errors`
- `bootstrap_X()` — purge, then create
- `at_script_creation` setting key/desc/interval/persistent
- `at_server_start` as the reliable post-reload hook
- `_ensure_running` / `_ensure_loop` re-arm
- a registry (ndb set, or db list)
- a sweep with per-item `try/except log_trace` isolation

That's one `SingletonManagerScript` base with a template method:

```python
class SingletonManagerScript(DefaultScript):
    MANAGER_KEY: str
    SWEEP_INTERVAL: int

    def sweep_one(self, item) -> None:      # subclass implements this only
        raise NotImplementedError

    def at_repeat(self, **kwargs):          # isolation lives here, once
        for item in list(self.registry()):
            try:
                self.sweep_one(item)
            except Exception:
                logger.log_trace()
```

Then `bootstrap_all()` iterates the registered subclasses, and
`at_server_startstop` never needs editing again.

---

## 5. Stack semantics implemented three times — the one with real risk

Three modules independently derive "same key + both stackable ⇒ mergeable" and
"`quantity +=` then `delete()`":

- `items/inventory/handler.py` — `_find_existing_stack`, `add_item`, `remove_item`
- `systems/banking/handler.py` — `_find_existing_stack_in_bank`, `_split_stack`,
  `_copy_item_to`, `_has_existing_stack`
- `systems/loot/drops.py` — `_merge_stackable_pairs`

This is the highest-priority DRY fix, because it's the only duplication in the
codebase that can **lose player items**. Your own CLAUDE.md gotcha #4 documents
the detached-build-then-move rule that makes splitting safe — and that rule is
currently implemented in exactly one of the three places
(`BankHandler._split_stack`). Anywhere else that grows a split later will hit the
same "needs to have a value for field id" bug from scratch.

```python
# items/stacking.py — one owner for the fact
def is_mergeable(a, b) -> bool: ...
def merge(into, src) -> None: ...          # quantity += ; src.delete()
def split(item, count) -> Object: ...      # detached build, caller moves it
def available_units(items) -> int: ...     # sum of quantities, 1 each if not stackable
```

Small, self-contained, high value. I'd do this one first.

---

## 6. Domain/presentation separation is inconsistent across the three services

| Service | Shape | Returns | Talks to the player? |
|---|---|---|---|
| `shop_service` | module functions | `BuyResult` / `SellResult` dataclasses | no |
| `crafting_service` | module functions | dicts / tuples | some (`blackout_recipe.py` has 7 `msg()` calls) |
| `BankHandler` | class | object or `None` | **13 `self.obj.msg()` calls** |

`shop_service` is the correct one — it's the only one a future web/Godot client
could reuse without stripping telnet colour codes out of the domain layer. Given
you're actively building a 3D webclient and a statefeed, that matters.

Banking is also why `deposit` is 68 lines (over your cap) at cyclomatic 16, and
`withdraw` is 13: they're carrying the display branch *and* the storage branch.
Return a `TransferResult`, let the menu render it, and both drop under the cap
without any clever refactoring.

---

## 7. The same wizard state machine is written three times

`banking_menu`, `npc_shopkeep`, and `crafting_menu` each implement:

> select item → choose quantity (1 / custom / all) → confirm → execute → report

Independently. It shows up in the metrics: the five worst violations of your
50-line cap are all menu nodes (`node_craft_quantity` 84, `node_recipe_detail`
78, `node_skill_detail` 63, `node_confirm_craft` 63, `start` 60).

**You already built the right abstraction and left it in the wrong file.**
`banking_menu._TransferFlow` is a dataclass carrying `verb`, `title`,
`empty_text`, `gone_text`, the three node names, and `find_item` / `list_items` /
`execute` / `decorate` callables — with `_select_node`, `_quantity_node`,
`_custom_qty_node`, and `_perform_transfer` all parameterised by it. Deposit and
withdraw are two ~15-line declarations.

Promote it to `base_menu.py` as `QuantityFlow`, then declare
`BUY_FLOW`, `SELL_FLOW`, and `CRAFT_FLOW` against it. That removes several
hundred lines and most of the cap violations at once.

---

## 8. Duck typing where a protocol belongs

31 `hasattr` sites and 58 defensive `getattr(x, y, None)` probes. `hasattr(target,
"is_alive")` appears 6 times, standing in for "is this a `CombatEntity`."

The cost is visible in `_NpcSkillsShim`, whose own docstring says it:

> must cover every method combat code calls on `.skills`, not just the ones NPCs
> meaningfully implement. Combat duck-types on this interface, so a missing
> method raises inside the tick loop, which the tick engine catches by discarding
> the handler — the NPC would silently stop fighting with no error surfaced.

That is precisely the failure mode an interface prevents. `typing.Protocol` costs
nothing at runtime and makes the contract checkable:

```python
class SkillSource(Protocol):
    def get_level(self, skill_key: str) -> int: ...
    def add_xp(self, skill_key: str, amount: int) -> None: ...
    def get_total_xp(self, skill_key: str) -> int: ...

class Combatant(Protocol):
    hp: int
    max_hp: int
    skills: SkillSource
    def is_alive(self) -> bool: ...
    def at_damage(self, amount: int, **kwargs) -> int: ...
```

And where the mixin genuinely is the answer, `isinstance(target, CombatEntity)`
says what you mean and reads better than probing for a method name.

---

## 9. Per-tick DB query fan-out (the thing that breaks at 20 players)

At 0.6s, per tick, with N combatants in rooms averaging M occupants:

1. **`_tick`** runs `ScriptDB.objects.filter(id=handler_id).first()` **once per
   handler** → N queries/tick. Should be one `filter(id__in=registry)`.
2. **`check_stop_combat` → `get_sides`** iterates `location.contents` and calls
   `get_handler_for(comb)` on each, which does `comb.scripts.all()` — **a ScriptDB
   query per occupant, per combatant, per tick.** O(N·M) queries every 0.6s.
3. **`_object_by_id`** does an `ObjectDB.objects.get()` per swing resolution, and
   again at the bottom of `tick()` for the liveness recheck — two per combatant
   per swing.

None of this is visible with one player fighting one mutant raider. At 20
combatants in a busy room it's several hundred queries per second, and the
symptom will be tick drift — which `tick_debug`'s interval window will faithfully
report without saying why.

The fix falls out of the tick engine already holding every live handler: have it
maintain `{owner_id: handler}` and pass that map into `tick()`, so `get_sides`
becomes dict lookups against room contents. Batch (1). Cache the target object on
the action for the duration of a swing rather than re-fetching (3).

---

## 10. Smaller items

**`EquipmentHandler.equip` (77 lines, cyclomatic 20)** — the two-hand slot
conflict rule is written twice, once to build `to_unequip` and again to assign
slots. A table collapses both:

```python
SLOT_CONFLICTS = {
    WieldLocation.TWO_HANDS: (WieldLocation.MAIN_HAND, WieldLocation.OFF_HAND),
    WieldLocation.MAIN_HAND: (WieldLocation.TWO_HANDS,),
    WieldLocation.OFF_HAND:  (WieldLocation.TWO_HANDS,),
}
```

Then split into `_check_requirements` / `_displace_conflicts` / `_place`.
Complexity 20 → ~6, and it drops under your cap.

**Legacy-compat branches in hot paths** — `_stored_combat_styles` (the
`attack_type` fallback), `_normalize_xp_skills`
(`LEGACY_CONTROLLED_XP_SENTINEL`), and
`style.get("weapon_style_xp_skill", style.get("xp_skill"))` all exist to read DB
rows spawned before renames. Every swing pays for them, and they're
untestable-by-construction — only pre-rename rows exercise them. Write a one-shot
migration under `scripts/`, run it, delete the branches.

**`ItemDef` is a wide struct** — 20+ fields, of which 5 are combat-only and
carried by every material and currency. `ItemDef(..., combat: CombatProfile |
None = None)` is the composition fix. Low urgency, but it's what's driving
`_get_attrs` to grow.

**85 `except Exception` sites.** Most are correct (tick isolation is a legitimate
pattern here). But `end_combat` has four sequential try/except-log blocks in a
row; a `_safely(fn, label)` helper would say the same thing in a quarter of the
space.

**Map files match the test discovery pattern.** `world/maps/test_oasis.py`,
`test_neo_cairo.py`, `test_oasis_outskirts.py` are map definitions, not tests —
which CLAUDE.md documents as the reason `evennia test .` collects the wrong set.
They also carry a UTF-8 BOM (radon chokes on them). Renaming to `map_oasis.py`
etc. permanently retires that footgun.

**`_debug_map.py` sits at repo root.** Belongs under `scripts/`, behind the same
`__main__` guard as its neighbours.

---

## 11. Testing

10,870 lines across 47 modules is solid, and the distribution is sensible — combat
has 17 test modules, statefeed 6. Two gaps:

- **`systems/shop` has no tests at all**, and it's the module that moves currency
  (`credits_deduct`, `credits_add`, `execute_buy`, `execute_sell`). Highest-risk
  untested code in the repo.
- **`systems/quests` has no tests.**

`systems/banking/tests.py` is a module rather than a `tests/` package — it works,
but it's inconsistent with every other system and sits next to the CLAUDE.md
warning about `tests/` dirs missing `__init__.py`.

---

## 12. On the docstrings

Worth naming since it's ~50% of the file volume: 11,705 docstring lines against
11,731 SLOC.

The *"why it's like this"* comments are the best thing in this codebase. Notes
like "`copy_object()` fails when the destination's `at_object_receive` mutates the
incoming object" or "assigning the full speed value produced a speed+1 cadence"
are institutional memory that would otherwise be lost, and they're the reason
this review could be written from the code alone.

The cost is the 7-section template applied uniformly. The `hp` getter — a
one-line `return self.db.hp or 0` — carries a 25-line docstring including
"Module Globals: None" and "Notes/References: None." That's ceremony that trains
readers to skim, which is exactly the opposite of what the valuable half needs.

Suggestion: keep the full template mandatory for public system entry points,
anything with non-obvious methodology, and anything with a hard-won gotcha. Allow
a one-line docstring for trivial accessors and properties. Volume is not the same
thing as documentation.

---

## Suggested sequence

Ordered so each step unblocks the next, and each is a self-contained PR:

1. **`items/stacking.py`** — one owner for merge/split. Small, correctness risk,
   no dependencies.
2. **Banking returns results; menus render.** Unblocks 3, and drops two routines
   under the style cap for free.
3. **Promote `_TransferFlow` → `base_menu.QuantityFlow`;** port shopkeep and
   crafting onto it.
4. **`TickableHandler` base + `@register_tickable`.** Deletes
   `_tickable_handler_keys` and the hand-listed bootstrap calls. Also lands
   `SingletonManagerScript` (item 4 above) as the same shape.
5. **`CombatState` enum + transition table.** The big one. Do it *after* 4,
   because the base handler class is where the state field wants to live.
6. **Tick engine owner-map + batched queries.** Cheap once 5 has clarified who
   owns what.
7. **Protocols, legacy-branch migration, `equip` split.** Cleanup pass.

Steps 1–4 are mostly mechanical and each removes real duplication. Step 5 is the
one that changes how the system is *reasoned about* — and it's much easier once
1–4 have removed the near-duplicate code paths that would otherwise all need
converting.
