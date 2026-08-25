# NPC Hostile Combat AI — research and implementation plan

**Date:** 2026-08-23
**Status:** phases 1-3 implemented and merged to `main`; phase 4 not started
**Branch:** landed on `main` (originally drafted on
`claude/npc-hostile-combat-ai-5dv6gg`, squashed on merge)
**Goal:** hostile NPCs fight back, deal real damage to players, and resolve
that combat against real skill levels rather than a fabricated stat facade.

---

## 1. Where the code actually is today

### 1.1 Hostiles are combatants that never act

`CmdAttack` (commands/combat_cmds.py:55) gives *both* sides a handler:

```python
ensure_combat_handler(target)          # the NPC
handler = ensure_combat_handler(caller)
handler.queue_action({"kind": "attack", "target": target})
```

Only the caller gets an action queued. The command's own comment says so:

> Note this does NOT make the NPC fight back: nothing queues an action for it
> and there is no AI hook yet.

So the NPC's handler is registered on the tick engine and ticks every 0.6s,
but `BlackoutCombatHandler.tick` (systems/combat/combat.py:1018) reaches:

```python
action = self.ndb.pending_action
if action is None:
    return
```

…and returns forever. `queue_action` has exactly four callers, all of them in
`commands/combat_cmds.py`. Nothing in the codebase can produce an NPC action.
**That single fact is the whole "hostiles can't damage the player" gap** — the
damage pipeline, the messaging, the death path and the XP path are all
already symmetric and already work in the NPC→player direction.

There is no AI system at all: no `systems/ai/`, no aggro flag on `NpcDef`, no
threat tracking, no target selection, no retaliation hook.

### 1.2 The skill shim

`_NpcSkillsShim` (typeclasses/npc_combat.py:20) is a four-method read facade
over the NPC's flat `db.combat_stats` dict:

```python
def get_level(self, skill_key: str) -> int:
    stats = self._npc.db.combat_stats or {}
    return int(stats.get(f"{skill_key}_level", 1))
```

It exists because `combat_calc.effective_level` is fed by
`entity.skills.get_level(...)` via `rules/context.read_skill_levels`, and
before the shim `HostileNPC` had no `.skills` at all — so every NPC defended
at level 1.

It is honest about being a stopgap, and `systems/combat/protocols.py` plus
`tests/test_protocols.py` were added to stop it silently drifting from
`SkillHandler`. But it has five concrete problems:

**(a) It fabricates values, and one of them is load-bearing.**
`NpcDef.to_combat_block()` emits `strike_level`, `brawn_level`,
`defense_level` and `max_hp` — but never `fortitude_level`. So
`get_level("fortitude")` hits the `, 1)` default and **every NPC in the game
reads Fortitude 1**, including the Big Mutant with 87 max HP.

That is not cosmetic. `combat_level/logic.get_combat_level` computes its base
term from `COMBAT_LEVEL_BASE_SKILLS = ("fortitude", "defense")`
(systems/combat/constants.py:224), so every hostile's combat level is
computed off a Fortitude of 1. It is not surfaced in the UI today (only
`systems/summary/panel_defs/vitals.py` reads it, for the player), but any
"look at the monster and see its level" feature inherits the bug — and OSRS
aggression semantics ("monsters ignore players above 2× their combat level")
are *built on* that number, so §3.3 below depends on fixing it.

The same fabrication hides a second class of bug: a rules definition that
keys off a skill the NPC has no entry for reads 1 rather than raising. The
Glass Cannon amulet keys off Brawn-over-Fortitude
(`systems/combat/rules/rule_defs/`), so against an NPC it evaluates against a
number nobody wrote down.

**(b) There is no write path.** `add_xp` is a documented no-op. That is
correct for XP, but it means *nothing* can modify an NPC's level at runtime.
`effective_level(base, potion_boost=..., ...)` already takes a boost
parameter; OSRS-style stat drains and boosts are a core mechanic; a
defence-draining special attack has nowhere to write. Every future
stat-modifying effect has to work on characters only or grow a second
mechanism.

**(c) Two storage shapes for one fact.** Characters store
`db.skills[key]["level"]`; NPCs store `db.combat_stats["{key}_level"]`.
Anything that wants to iterate an entity's combat skills generically has to
know which of the two it is holding. That is exactly the "one owner per fact"
rule in CLAUDE.md, inverted.

**(d) The contract is checked by name only.** `test_protocols.py` compares
`dir()` name sets against the Protocol. A signature change, a return-type
change, or a semantic change (does `add_xp` persist?) all pass.

**(e) `.skills` is being used as a type proxy.** `CombatEntity.at_death`
(typeclasses/mixins.py:378) gates killer-side XP on
`getattr(killer, "skills", None) is not None`. The shim makes an NPC pass
that gate. Today it is harmless because `add_xp` is a no-op — but it means
the gate is asking "does this have a skills attribute?" when it means "is
this an XP-earning entity?". Any move toward a real handler on NPCs turns
that latent bug live: `ActionAttack._land_hit` calls `_plan_style_xp` →
`_apply_xp_awards` → `attacker.skills.add_xp` on *every* connecting hit, so a
real handler would start paying monsters XP for hitting players.

### 1.3 What already works and needs no change

- **Damage & death both directions.** `at_damage` / `at_death` are on the
  shared `CombatEntity` mixin and are typeclass-agnostic by design.
- **Messaging.** `_land_hit` sends to attacker, target and room.
  `DefaultObject.msg` is a no-op without sessions, so the NPC-side calls
  simply vanish; the player still gets `format_incoming_hit` and their own HP
  bar, and the room gets `format_third_party_hit`.
- **Fight teardown.** `check_stop_combat` ends combat when a side is dead or
  has left the room, so fleeing already works against an active attacker.
- **Tick ordering.** `enqueue_action` buffers to the engine's INPUT phase, so
  an action queued *during* a tick lands at the top of the next one, for
  every combatant, regardless of rotation position. An AI that queues from
  inside its own tick gets OSRS-style buffering for free.
- **The registry patterns to copy.** `@register_tickable` +
  `_TICKABLE_MODULES` (systems/tick/tickable.py:77), `@register_manager`
  (systems/managers.py), `@register_spawner`, `NpcDef`/`NPC_DB`.

### 1.4 The one genuine blocker

`CombatEntity.respawn` (typeclasses/mixins.py:472) is a stub: it refills HP in
place and does nothing else. No character subclass overrides it. Nothing has
ever killed a player, so this has never mattered — but the moment hostiles
retaliate, a player death means "your HP silently refills and the fight
continues where it stopped". `settings.py` sets neither `START_LOCATION` nor
`DEFAULT_HOME`, so there is no respawn-room fact anywhere to move them to.

**Decision taken:** respawn room, full HP restore, **no XP penalty**. The
penalty is a later tuning decision and is deliberately out of scope.

---

## 2. Replacing the shim — options considered

### A1 — Harden the flat dict
Add `fortitude_level` to `NpcDef` / `to_combat_block`, make `get_level` stop
fabricating unknown keys, add a `set_level` write path onto `combat_stats`.

- **Pros:** one file, no migration, no per-NPC Attribute growth, NPCs stay
  fully decoupled from the progression system.
- **Cons:** two storage shapes remain; the shim grows a method every time
  combat calls something new on `.skills`; still no XP semantics for anything
  that ever wants a levelling NPC.

### A2 — Give NPCs a real `SkillHandler`
Delete the shim; `HostileNPC.skills` returns a `SkillHandler`; `NpcDef.create`
seeds `db.skills` for the four combat axes (**not** `init_all_skills`, which
would allocate the whole registry per NPC).

- **Pros:** exactly one code path everywhere; drains, boosts, combat level and
  `read_skill_levels` all just work; the Protocol stops needing two
  implementations, which retires the entire "forgot to add it to the shim"
  bug class.
- **Cons:** `logic.ensure_skill` **writes into `db.skills` on read** for any
  registered-but-untracked key, so reading `guns` on a goblin permanently adds
  a `guns` entry to that NPC's Attribute row; a persisted dict per NPC is an
  Attribute row churned on every respawn; and it makes NPCs real XP earners,
  which lights up the `at_death` gate in §1.2(e).

### A3 — Two real implementations behind one protocol  ← **CHOSEN**
Keep `SkillSource` as the contract and ship two honest implementations that
share a storage *shape*: `SkillHandler` (characters — XP-driven, level
derived) and a new `StatBlockSkills` (NPCs — level-driven, no XP).

- **Pros:** models the truth (a monster genuinely has no XP); no write-on-read
  hazard, because `StatBlockSkills` never touches `SKILL_REGISTRY`; one
  readable `{skill_key: level}` shape; the protocol grows deliberately.
- **Cons:** two classes to keep in step — which is precisely what the protocol
  plus a strengthened `test_protocols` is for.

### Protocol split (adopted alongside A3)
Split the one protocol in two:

- `SkillSource` — `get_level`, `set_level`, `modify_level`. Implemented by
  both.
- `XpEarner` — `add_xp`, `get_total_xp`, `meets_prerequisite`. Implemented by
  `SkillHandler` only.

Then `at_death`'s killer-XP gate becomes `isinstance(killer, XpEarner)`, and
`_plan_style_xp` skips an attacker that is not one. This is what stops
monsters earning XP, and it removes the `getattr(x, "skills")`-as-type-check
idiom rather than making it more entrenched.

### Fortitude ↔ max HP
The vault says max HP scales 1:1 with Fortitude, and characters honour that
via `sync_max_hp_from_fortitude`. NPCs set `max_hp` directly and never set
Fortitude — two owners for one fact.

- **(i) Derive:** `NpcDef` drops `max_hp`, declares `fortitude_level`, and
  max HP comes from the shared function. One owner; OSRS Hitpoints maps
  straight across.
- **(ii) Bridge:** keep both fields; `to_combat_block` sets
  `fortitude_level = max_hp` when it is unset. One line, identical numbers,
  no data churn, and makes (i) a later rename.
- **(iii) Leave it:** accept a wrong NPC combat level.

**Plan takes (ii) now, with (i) noted as the follow-up rename.** It fixes the
combat-level bug immediately without touching three `NpcDef` entries and
whatever else lands before the rename.

---

## 3. Hostile AI — options considered

The decision splits into three orthogonal questions. Only the first is
required for "hostiles damage the player".

### 3.1 What drives action selection

**B1 — Retaliation branch in the damage path.** ~15 lines: when `_land_hit`
lands on an entity with no pending action, queue an attack back.
- *Pros:* smallest possible diff; hostiles are dangerous today; no new module,
  no extra tick cost.
- *Cons:* a behaviour rule buried in the damage pipeline; catches players too
  unless gated; no aggro, no target choice, no flee; it is the dispatch chain
  CLAUDE.md explicitly warns against, and every later behaviour extends it.
  Spike quality.

**B2 — A dedicated `BlackoutAiHandler` tickable.** A second `TickableHandler`
per NPC, mirroring `BlackoutAuraHandler`, registered via `@register_tickable`
and added to `_TICKABLE_MODULES`.
- *Pros:* the repo's own established shape; runs outside combat, so wandering,
  patrols and idle behaviour land here later with no rework.
- *Cons:* a second Script row and tick slot per hostile on the grid; a second
  teardown path to keep in step with `leave_combat`,
  `at_disconnect_combat_cleanup` and `respawn`.

**B3 — A controller seam on the existing combat handler.**  ← **CHOSEN**
No new script. `BlackoutCombatHandler` acquires one named seam: when
`pending_action` is None at the top of a tick, ask this combatant's
*controller* what to do. Player controller = "nothing, wait for a command".
NPC controller = a behaviour looked up by name from `NpcDef.ai_behavior`.
- *Pros:* no second script, no extra tick cost, one teardown path; the "who
  decides the next action" question gets exactly one home.
- *Cons:* the combat handler only exists *during* combat, so unprovoked aggro
  needs its own trigger regardless (§3.3); mildly mixes "resolve actions" with
  "choose actions".

**Structured so B2 stays cheap later:** the behaviours themselves live in
`systems/ai/` with their own decorator registry from day one. If out-of-combat
AI is wanted later, the behaviour package already exists and only the *driver*
changes — B3 → B2 becomes a swap, not a rewrite.

### 3.2 Target selection

- **(a) Last attacker** — `at_damage` already receives `attacker`; record it.
  Trivial; free tank-swapping; fine now.
- **(b) Threat table** — `ndb.threat = {id: total}` accumulated in `at_damage`,
  highest wins, decays. Standard MMO behaviour, and it would later let loot
  attribution move from `killer` to top-damage.
- **(c) Sticky first attacker** — simplest to reason about, immune to
  tank-swap griefing, reads dumb with several players.

**Plan takes (a), with the write placed in `at_damage` so (b) is a drop-in.**

### 3.3 Aggro (unprovoked attack)

- **(a) Event-driven** — hook the room / `at_after_move`; on entry, scan for
  hostiles flagged aggressive. Zero polling. Misses a hostile *spawning* into
  an occupied room, which the respawn manager can cover.
- **(b) Scheduler scan** — a `schedule_in(N)` entry per aggressive NPC.
  Uniform, and it is the honest home for OSRS's aggression *timer* (tolerance
  lapses after ~10 minutes in an area).
- **(c) Hybrid** — the event arms a scheduler entry that re-evaluates.

**Plan takes (a) for phase 3, with (b) noted as what OSRS tolerance semantics
will need.** Note the coupling: the OSRS rule "monsters ignore players above
2× their combat level" reads `combat_level`, which is wrong for NPCs until the
Fortitude fix in §2 lands. Skills work first, then aggro.

---

## 4. Implementation plan

Each phase is independently shippable and independently testable.

### Phase 1 — Skill source (A3 + protocol split + Fortitude bridge) — DONE
1. `systems/combat/protocols.py`: split `SkillSource` / `XpEarner`; add
   `set_level` / `modify_level` to `SkillSource`.
2. New `systems/progression/skills/stat_block.py` — `StatBlockSkills`, storing
   `{skill_key: level}`, no XP, no `SKILL_REGISTRY` coupling, never mutating
   on read.
3. `SkillHandler`: add `set_level` / `modify_level` (a temporary boost layer,
   *not* an XP write) so `effective_level`'s boost parameter has a source.
4. `NpcDef.to_combat_block`: emit `fortitude_level`, defaulting to `max_hp`.
5. `HostileNPC.skills` returns `StatBlockSkills`; delete `_NpcSkillsShim`.
6. `at_death` killer gate and `_plan_style_xp` switch to `isinstance(x, XpEarner)`.
7. `test_protocols.py`: compare `inspect.signature`, not `dir()` name sets.
8. Tests: Big Mutant reads Fortitude 87 and a sane combat level; an NPC
   landing a hit awards no XP; a drain moves an NPC's effective level.

### Phase 2 — Player death policy — DONE
9. Respawn-room fact in `world/` (one owner, greppable), plus a
   `Character.respawn` override: move, restore full HP, no XP penalty.
10. Test: a player killed by an NPC lands in the respawn room at full HP with
    combat torn down on both sides.

### Phase 3 — Retaliation (B3) — DONE
11. `systems/ai/` — behaviour registry + `@register_behavior`, and an
    `aggressive_melee` behaviour returning an action dict or None.
12. `NpcDef.ai_behavior` field, stamped by `create`, defaulting to retaliate.
13. The controller seam in `BlackoutCombatHandler.tick`: on an idle tick,
    consult the controller and `queue_action` what it returns.
14. `at_damage` records the last attacker (the future threat-table seam).
15. Tests: an attacked raider hits back within its `attack_speed` cadence; it
    stops when the player leaves the room; two players attacking one NPC do
    not become enemies of each other (`get_sides` regression).

### Phase 4 — Aggro (optional, gated on phase 1) — NOT STARTED
16. `NpcDef.aggressive` + a room-entry trigger; combat-level tolerance rule.

**Test command** (per CLAUDE.md — never bulk-import under `blackout/`, and
never touch `blackout/scripts/`):

```bash
../evenv/Scripts/evennia.exe test --settings settings.py systems.combat systems.progression typeclasses
```

Full suite before merge:

```bash
../evenv/Scripts/evennia.exe test --settings settings.py items systems typeclasses commands world
```

---

## 5. Risks

| Risk | Mitigation |
|---|---|
| A tick-loop exception is swallowed by the engine and the NPC silently stops fighting — the exact failure the shim docstring describes | Controller call site logs explicitly; a test asserts sustained multi-tick retaliation, not just one swing |
| Two combatants each queueing at the other every tick | Retaliation only fires when `pending_action is None`; `next_action` already makes an attack self-sustaining |
| Player death loop (respawn in the room they died in, get re-killed) | Phase 2 lands before phase 3; respawn room is not a combat room |
| NPC XP leak via `_land_hit` → `_apply_xp_awards` | `XpEarner` split in phase 1, before any NPC can land a hit |
| Aggro scan cost per tick | Event-driven trigger, not polling; scheduler only if tolerance timers are wanted |


---

## 6. What actually shipped

Phases 1-3 landed together. Deviations from the plan above, and facts learned
in the writing, are recorded here rather than by editing the plan.

### Phase 2

- The respawn fact is `world/respawn.py`: `RESPAWN_XYZ = (0, 0, "oasis")` plus
  `get_respawn_room()`. (0, 0) is the "Oasis Entrance" tile -- a named landmark
  with no NPC prototype, and clear of the Mutant Raider tile at (2, 3), which
  is what stops the death loop §5 warns about.
- The anchor is the zcoord, not the map module. This was load-bearing sooner
  than expected: `world/maps/test_oasis.py` was renamed to `world/maps/oasis.py`
  in the same window this work landed. `scripts/map_manifest.json` binds module
  to zcoord, so the rename moved a manifest row and left `"oasis"` untouched.
- `Character.respawn` restores HP through the `hp` **property**, not `db.hp`.
  The setter is what publishes the state-feed HP event; writing `db.hp`
  directly refills the number and leaves every connected client showing the
  corpse's zero. The base `CombatEntity.respawn` still writes `db.hp` and is
  now documented as the degraded path rather than a stub.
- HP is restored BEFORE the move, because the move is the step that can fail.

### Phase 3

- `systems/ai/` holds `constants.py`, `registry.py` (`@register_behavior`,
  explicit module list -- never a directory walk) and `behaviors.py`.
- The seam is `BlackoutCombatHandler._consult_controller`, called from `tick`
  when `pending_action is None`. The controller IS `db.ai_behavior`: a player
  never stamps it, so the player/NPC split costs no isinstance check.
- `NpcDef.ai_behavior` defaults to `aggressive_melee` and is stamped by
  `create()` alongside `npc_key`, not carried in `to_combat_block()` -- it
  decides who is asked for an action, not how one resolves.
- **`ActionAttack._target_unusable` was promoted to a module-level
  `combat.target_unusable`.** The behaviour has to ask the same question before
  queueing an action that names a target, and a behaviour-local subset of those
  checks would have missed the `pk is None` case -- which is exactly the case
  that bites once something holds an id across a tick boundary.
- Retaliation begins when the first hit lands, because `at_damage` is what
  records the attacker. `ActionAttack.next_action` returns `self`, so one
  queued attack self-sustains at `attack_speed`; the behaviour fires roughly
  once per fight, not once per tick.

### Migration note

`db.ai_behavior` is stamped at spawn. NPCs already standing on the grid from
before this change carry no such attribute and will NOT retaliate until they
respawn or the maps are rebuilt
(`scripts/clean_and_reload_all_maps.ps1`).

### Found in passing, not fixed

`Character.at_object_delete` (typeclasses/characters.py) is annotated `-> None`
and returns nothing. Evennia's `DefaultObject.delete()` treats a falsy return
from that hook as a veto, so **a Blackout Character cannot currently be
deleted**. Unrelated to combat AI and deliberately left alone; the test that
needed a deleted attacker uses a second NPC and says why.
