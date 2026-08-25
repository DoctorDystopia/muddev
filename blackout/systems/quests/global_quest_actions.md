# Global Quest Actions Reference

This document serves as the master reference for all standardized action verbs used in the Blackout Quest System. To maintain modularity and a clean codebase, always use one of the predefined actions below when defining quest targets or firing progression hooks.

## Target Syntax Structure
All quest targets must strictly adhere to the `{action}:{argument}` format.
- **Action**: One of the global verbs defined in this document.
- **Argument**: A specific, unique identifier for the target (e.g., `lone_android`, `drainage_pipe`, `raider`).

**Example Target Dictionary in Blueprint:**

```python
targets={"interact:pipe": True, "kill:raider": 3}
```

**Example Progression Hook in Game Logic:**

Game systems call `notify_quests`. They know what the player *did*, not which
quest wanted it, so they never name a quest key:

```python
from systems.quests import constants as quest_constants
from systems.quests.hooks import notify_quests

notify_quests(caller, quest_constants.ACTION_INTERACT, "pipe")
notify_quests(killer, quest_constants.ACTION_KILL, npc_key, amount=1)
```

`notify_quests` fans the action out across every quest the character has
active, tolerates an actor with no quest handler (every hostile NPC), rejects
an action that is not in this document, and never raises — it sits inside
`at_death` and `perform_craft`, where an exception would take real game state
down with it.

`character.quests.update_progress("oasis", "interact", "pipe")` still exists
for the rare caller that genuinely knows which quest it is advancing. Prefer
`notify_quests`.

> **The argument is a stable snake_case identifier, never a display name.**
> `db.npc_key` (`"mutant_raider"`), a recipe key, an `ItemDef` key. The
> kill hook in `at_death` used to pass `self.key` — `"Mutant Raider"` — which
> no blueprint could reasonably declare.

**Adding an action:** add the constant to `systems/quests/constants.py`, add
it to `QUEST_ACTIONS`, and add a level-3 heading below whose text is the
verb wrapped in backticks (the same shape every section already uses).
`test_quest_vocabulary.py` parses this file's level-3 headings and asserts
they match `QUEST_ACTIONS` exactly in both directions, so the code and this
document cannot drift.

---

## Social & NPC Interaction

### `talk`

Use this for all dialogue initiation, greeting, or hitting specific conversation nodes.

* **Usage Examples:** `talk:lone_android`, `talk:neo_cairo_guard`, `talk:merchant`

### `give`

For delivery, escort, or barter objectives where the player must transfer an item or entity to an NPC.

* **Usage Examples:** `give:scrap_metal`, `give:water_ration`

---

## Combat & Survival

### `kill`

Fired primarily from combat handlers or `at_death` hooks.

* **Usage Examples:** `kill:desolate_raider`, `kill:mutated_hound`

### `survive`

For time-based, environmental, or wave-based endurance objectives.

* **Usage Examples:** `survive:sandstorm`, `survive:raider_ambush`

---

## World & Environment

### `interact`

A powerful catch-all that replaces highly specific verbs like `clear`, `analyze`, `push`, `pull`, or `press`. Use this for any static world objects or room features.

* **Usage Examples:** `interact:drainage_pipe`, `interact:soil_analyzer`, `interact:bunker_door`

### `visit`

Fired upon entering a specific room or region. Perfect for exploration and traversal objectives.

* **Usage Examples:** `visit:oasis_perimeter`, `visit:neo_cairo_gates`

---

## Economy & Crafting

### `gather`

Fired when an item is added to the inventory from the world or a resource node.

* **Usage Examples:** `gather:desert_bloom`, `gather:crystalline_structure`

### `craft`

Fired from the crafting system upon successful item creation.

* **Usage Examples:** `craft:makeshift_weapon`, `craft:water_filter`

### `use`

Fired when a player consumes, equips, or activates an item from their inventory.

* **Usage Examples:** `use:medkit`, `use:battery_pack`

---

## Blackout Specific Skills & Progression

*(These actions map directly to custom mechanics like cutting, mining, and brain farming.)*

### `cut`

Tied to the core "Cutting" skill. Fired when successfully slicing synthetic crystalline structures or old metal scavenged loot.

* **Usage Examples:** `cut:synthetic_crystal`, `cut:old_metal`

### `mine`

Tied to the core "Mining" skill. Fired when successfully extracting from ore/mineral deposits.

* **Usage Examples:** `mine:iron_deposit`, `mine:earthen_rubble`

### `harvest_brain`

Specific to the "Brain Farming" skill. Fired when successfully harvesting conscious energy from a living creature.

* **Usage Examples:** `harvest_brain:mutant_rat`, `harvest_brain:raider`