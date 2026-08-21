# 3D Inventory for the Webclient

**Status:** implemented, phases 0–4. See §9.
**Author:** Nick Hobar
**Date:** 08/15/2026

> §8 records where the build diverged from this plan and what it found on the
> way. Read it before trusting the details above.

A dockable **Inventory** pane rendering the character's 32 carried slots and 11
equipment slots as real 3D objects, with click actions and drag-and-drop.

The word is **inventory** everywhere — pane title, plugin file, component name,
payload field, command help. Not "bag", not "pack", not "items" except where a
published GMCP name forces it (see §2.1).

---

## 0. What already exists, and what does not

Read before planning any of the below, because two gaps decide the ordering.

**Exists:**

- `items/inventory/handler.py` — the authoritative 32-slot grid. `slots` is a
  `{index: object_id}` dict persisted as an Attribute. Has `add_item`,
  `remove_item`, `all_items`, `sync`.
- `items/equipment/handler.py` — 11 `WieldLocation` slots, `equip` / `unequip`.
- `systems/statefeed/` — channels, payloads, serializers, emit, resync. The
  asset-key design already in place: every entity ships a stable string naming
  what it is, and a client with no asset for that key draws a generic mesh with
  the real name.
- `web/static/webclient/js/plugins/blackout3d.js` — the World pane. 1,493 lines,
  GoldenLayout component `blackout3d`, its own three.js scene.
- `ITEM_DB` tags carrying a usable family vocabulary: `weapon`, `armor`,
  `jewellery`, `crafting_material`, `crafting_tool`, `currency`.

**Does not exist, and blocks the interesting half:**

1. **No argument-taking equip command.** `commands/equipment_cmds.py` defines
   `equip` / `equipment`, which opens an EvMenu. Unequip is a menu node. The
   3D pane's standing rule is that it sends only what a telnet player could
   type — and an EvMenu is a stateful cmdset that captures the player's *text*
   input, so a graphical client firing `equip` would trap them in a menu they
   never opened. **Drag-to-equip has nothing to send today.** §3 adds it.
2. **No way to reorder slots.** `InventoryHandler` has no `move_slot`. Dragging
   slot 3 onto slot 17 has no server-side meaning at all. §3 adds it.

Both gaps are filled by ordinary text commands that telnet players get too.
Neither is a client-only backdoor. That is not incidental — see §1.

---

## 1. The two rules this design is bound by

Everything below follows from these, and any deviation should be argued for
explicitly rather than drifted into.

**The pane sends only what a telnet player could type.** Stated at the top of
`blackout3d.js` and load-bearing: because every gesture becomes an ordinary
`["text", [...]]` command, no permission, lock or cooldown has to be audited a
second time for the graphical client. A drag gesture with no corresponding
command is therefore a *missing command*, not a reason for a privileged channel.

**One owner per fact.** The inventory grid's owner is `InventoryHandler.slots`.
The feed reports it; it never computes a second version of it. The 3D pane
renders what the feed reports; it never keeps its own idea of where an item is
beyond the length of a drag gesture.

---

## 2. Server side — the feed

### 2.1 Channel: snapshot, not delta

**Recommendation: one whole-state channel, `char_items_list`, replacing its own
previous message. No add/remove/update deltas.**

This deliberately departs from `room_players`, and the reason is worth stating
because the opposite choice looks more consistent and is wrong.

`room_players` uses list-then-delta because with `STATEFEED_ENTITY_RADIUS = 10`
the full list is large and the mutation points are few and well-defined (an
entity enters or leaves a room). The inventory is the exact inverse:

- The full list is **small** — 32 slots plus 11 equipment slots is ~2.5 KB of
  JSON, comfortably inside Godot's 65535-byte inbound buffer, so unlike
  `blackout_map` it needs no chunking.
- The mutation points are **many and undisciplined**. `InventoryHandler.add_item`
  merges stacks with a bare `existing.quantity += additional` — no hook fires.
  Crafting consumes materials directly. Banking moves items in bulk. Equipping
  displaces items back into the grid. A delta protocol would need an emit at
  every one of those and would silently rot at the first one anybody forgot.

A dropped or missed delta on a distant NPC is a cosmetic ghost. A dropped delta
on the player's own inventory is a phantom item they will try to click. Send the
whole grid; it is cheap and it cannot desync.

Channel name follows the GMCP vocabulary, per the standing rationale in
`statefeed/constants.py` — Evennia maps `char_items_list` to `Char.Items.List`,
which is IRE's published name for exactly this, so Mudlet and MUSHclient
understand it for free. That is the one place the published spec wins over the
"inventory" naming rule. The **payload's** own vocabulary stays ours: the
location field carries `"inventory"`, not IRE's `"inv"`.

```python
CHANNEL_CHAR_ITEMS: str = "char_items_list"   # -> Char.Items.List
```

Add to `SUBSCRIBABLE_CHANNELS`. Nothing else in the handshake changes — the
client learns the channel from the `blackout_subscribed` acknowledgement and
binds it automatically, which is precisely what `bindAcknowledged` was built
for after `char_summary` was added and printed raw JSON at players.

### 2.2 Rate limiting: none

**Do not add an entry to `CHANNEL_MIN_INTERVAL_SECONDS`.**

The temptation is obvious — it looks like a continuous value where the latest
supersedes. It is not, and capping it would reproduce the `room_players` bug
documented in `constants.py`: a player picks up an item, the emit is dropped by
the cap, nothing else is scheduled, and the pane shows a stale grid until they
happen to act again. The channel is self-limiting anyway, because it is driven
by discrete player actions bounded by the 0.6s tick.

If it ever genuinely needs capping (a gathering loop firing hard), the cap must
be **coalescing** — schedule a trailing send — not dropping. `emit.py` has no
such mechanism today, and adding one is a larger change than it looks.

### 2.3 Payload

```python
@dataclass
class CharItemsPayload(_Payload):
    channel = const.CHANNEL_CHAR_ITEMS

    location: str = "inventory"   # inventory | equipment, both sent together
    slots_total: int = 0
    slots_used: int = 0
    items: list = field(default_factory=list)      # inventory grid
    equipped: list = field(default_factory=list)   # paper-doll slots
```

One item entry:

```python
{
  "id": 4711,
  "slot": 6,                       # 0-based grid index; equipment uses slot name
  "name": "rusty scrap spear",
  "asset": "rusty_scrap_spear",    # prototype key -- the mesh lookup key
  "family": "weapon",              # ITEM_DB tag category -- the fallback mesh key
  "quantity": 1,
  "stackable": false,
  "equip_slot": "two_hands",       # WieldLocation.value, or "" if not equippable
  "actions": [                     # what a right-click menu offers
      {"label": "Wield", "command": "equip 7"},
      {"label": "Drop",  "command": "drop rusty scrap spear"}
  ]
}
```

Three notes on the shape:

- **`asset` and `family` are two tiers of the same lookup**, mirroring the
  existing generic-mesh fallback. The client tries a model for `asset`, falls
  back to a procedural mesh for `family`, falls back to a cube. A new item in
  `ITEM_DB` therefore renders correctly-labelled on the day it is added, with
  no art request — same guarantee the world pane already gives.
- **`actions` is a list, where `serialize_entity` has a single `interact`
  string.** A thing on the floor affords one obvious verb; a thing in your
  inventory affords several. Same doctrine either way: *the server names the
  verbs*. Note that `serialize_entity` currently returns `get <name>` for items,
  which is the wrong verb for something already carried — so this needs its own
  serializer, sharing `_classify` rather than reusing `serialize_entity`.
- **No `desc`.** Deliberately, for the reason `serialize_entity` gives:
  duplicating prose into the feed is how the feed and the text channel drift.
  Hover shows name and quantity; anything richer is an `inspect` action whose
  output lands in the text pane where it already lives.

### 2.4 New module: `systems/statefeed/inventory.py`

Builds the payload from `caller.inventory` and `caller.equipment`, reusing
`serializers._classify` for the asset key and reading the `ITEM_DB` tag category
for `family`. Kept out of `serializers.py` because that module is about
*entities in the world*, and this is about *slots*.

`events.emit_inventory(observer)` is the single call site the game uses, matching
how every other channel is reached.

### 2.5 Where to emit from

- `commands/inventory_cmds.py::CmdInventory.func` — the player asked.
- `resync.send_full_state` — a pane opened mid-session must show a full
  inventory, not an empty grid until the next pickup.
- `typeclasses/characters.py::at_object_receive` / `at_object_leave` — already
  the choke point where `inventory.add_item` / `remove_item` are called.
- The new `equip` / `unequip` / `swap` commands from §3.
- `items/equipment/handler.py::equip` / `unequip` — because equipping displaces
  items back into the grid, and the menu path reaches it without a command.

That set is deliberately generous. With a snapshot channel an extra emit costs
one small message and cannot corrupt anything, whereas with a delta channel each
of these would have to be exactly right. This is the payoff for §2.1.

---

## 3. Server side — the command surface

Three commands and one handler method. All three are useful to telnet players
independent of the 3D pane, which is the test for whether the rule in §1 is
being respected or worked around.

**`swap <slot> <slot>`** — exchange two inventory positions. Needs
`InventoryHandler.move_slot(from_idx, to_idx)`: swap the two entries in `slots`
and `_save()`. Roughly ten lines including bounds checks. Note the text grid
renders slots 1-based (`display.py::format_slot_cell` prints `slot_idx + 1`), so
the command must take 1-based indices and the payload's 0-based `slot` must be
converted by the client, not by the player.

**`equip <slot|item>`** — equip by grid position or by name. Wraps the same
`EquipmentHandler.equip` the menu already calls, so error text and skill
requirements stay in one place.

**`unequip <slot|item>`** — likewise, accepting a `WieldLocation` value
(`unequip main_hand`) or an item name.

**Accept slot numbers, not just names.** This is the detail that makes the
graphical client honest. Item names are ambiguous — two stacks of `rusty scrap
metal` are a real thing — and a client sending `equip rusty scrap metal` is
sending a command whose target it cannot predict. A slot index is exactly what a
graphical client has and is unambiguous. Telnet players get a faster path too.

Evennia's default `drop` takes a name only. Leave it alone for now; a Blackout
`CmdDrop` accepting a slot is a phase-3 nicety, and the ambiguity is tolerable
because dropping the wrong identical stack is recoverable.

---

## 4. Client side — the Inventory pane

### 4.1 A separate pane, a separate file

`web/static/webclient/js/plugins/blackout_inventory.js`, registering GoldenLayout
component `blackout_inventory`, pane title **Inventory**. Its own scene, camera,
renderer. `blackout3d.js` is not modified.

The reason is written in `blackout3d.js` itself: the world pane's camera is an
orbit rig entangled with player-follow, its picking uses a screen-distance hack
tuned for tiny spheres, and the module carries a long comment about why there can
only ever be one of it. Adding a second camera and a modal picking state to that
file is how it becomes unmaintainable. GoldenLayout already gives docking,
tabbing and resize for free.

The cost — dragging an item out of the Inventory pane onto a world tile to drop
it crosses a pane boundary — is deferred to phase 3 and solved with a
document-level drag ghost, not by merging the panes.

Follow `blackout3d.js`'s wiring exactly: register the component in `init()`
(**not** `postInit()` — the comment there explains that registering late blanks
the entire page for any player with the pane in their saved layout), re-register
in `onLayoutChanged`, bind channels by name onto `Evennia.emitter` rather than
relying on `onUnknownCmd`, and guard against a second pane instance.

Add the `<script>` tag after `blackout3d.js` in the webclient template.

### 4.2 Camera and layout

**Orthographic camera at a fixed gentle tilt.** Not perspective. A grid read at a
glance wants every cell the same size on screen — under perspective the corner
slots foreshorten differently from the centre ones, which looks wrong and makes
drag targeting feel inconsistent. A slight fixed tilt still gives the lit
display-case look. No orbit; the camera does not move.

- A backplate quad, 4 columns × 8 rows of slot frames matching the text grid's
  `GRID_COLS` / `GRID_ROWS`.
- A paper-doll column beside it for the 11 equipment slots in
  `SLOT_DISPLAY_ORDER` — needed as drag targets, and the reason equipment ships
  in the same payload.
- Item meshes float above their slot plate with a slow rotation and the same
  ambient bob the world pane uses, so the pane does not read as frozen.

**Picking is a real raycast here**, unlike the world pane. Slot plates are large
targets; the screen-distance hack in `pickEntity` exists only because entities
there are a handful of pixels across. Worth a comment saying so, since the two
files will otherwise look inconsistent.

**Labels and tooltips are DOM, not three.js text.** Absolutely-positioned divs
projected from mesh positions, using the same `project(camera)` math already in
`pickEntity`. Crisp at any DPI, no font atlas, no geometry.

### 4.3 The mesh resolver — build the tiers now, fill them in later

One module, `meshForItem(asset, family)`, with a three-tier chain:

1. **glTF model** for the exact `asset` key, if one is registered. *Not
   implemented in phase 2* — a documented hook of roughly thirty lines.
2. **Procedural mesh** for the `family` tag. `weapon` → elongated blade,
   `armor` → plate, `jewellery` → torus, `crafting_material` → rough
   icosahedron, `crafting_tool` → shaft-and-head, `currency` → coin stack.
3. **Generic cube.**

**Make the resolver async-shaped from day one** — returning a promise, or a
placeholder mesh that may be swapped — even though tiers 2 and 3 resolve
instantly. This is the whole point of deciding the tier chain now: a glTF arrives
frames after its slot is drawn, and retrofitting asynchrony into a synchronous
placement routine is exactly the change that breaks a frame loop. Cheap now,
expensive later.

Live in a shared module rather than inside the inventory plugin, because the real
payoff is retiring the world pane's coloured spheres onto the same resolver in
phase 4 — one answer to "what does a rusty scrap spear look like", used by the
inventory icon, the dropped item on the ground, and eventually the model in the
character's hand.

### 4.4 Drag and drop

Pointer events, not HTML5 drag — the canvas has no DOM elements to drag.

1. `pointerdown` on an occupied slot records the source and captures the pointer
   (the world pane's `CLICK_SLOP_PX` / `CLICK_MAX_MS` discipline applies: a
   two-pixel wobble is a click, not a drag).
2. Past the slop threshold, the gesture becomes a drag: lift the mesh toward the
   camera, make it translucent, raycast each move for the hovered slot and glow
   it — **emissive, not a colour swap**, for the reason `COLOR_HOVER_GLOW`
   documents. Invalid targets do not glow, which is how the pane refuses a move
   before sending it, exactly as `tileAction` refuses a walk into a wall.
3. `pointerup` on a valid target sends the command; anywhere else cancels and
   snaps back.

Gesture → command:

| From | To | Sends |
|---|---|---|
| inventory slot | inventory slot | `swap <from> <to>` |
| inventory slot | equipment slot | `equip <slot>` |
| equipment slot | inventory | `unequip <equip_slot>` |
| inventory slot | outside the pane | `drop <name>` *(phase 3)* |

**Optimistic, with the snapshot as truth.** Move the mesh immediately on release
— waiting a full tick for the server would make the pane feel dead — and let the
next `char_items_list` be authoritative. If the server refused, the snapshot
corrects it within a tick and the text pane says why. This is the same philosophy
as the world pane's move tween: render the present, not the past.

One guard: **an arriving snapshot cancels any in-flight drag** rather than being
deferred. A drag interrupted by a real inventory change is rare, and cancelling
is one line where deferring is a state machine.

**Right-click opens a DOM context menu** built from the payload's `actions`
array. That is where drop, deposit, use and inspect live without inventing a
gesture for each, and it needs no client-side verb table — the same reason
`blackout3d.js` deleted its verb table after it offered `get Foundry Furnace`
and a test account walked off with the furnace.

---

## 5. Phasing

Each phase is independently useful and independently verifiable.

**Phase 0 — feed.** Channel, payload, `statefeed/inventory.py`,
`events.emit_inventory`, emit sites, resync. Verifiable with the existing debug
checkbox: the JSON arrives with no client work at all.

**Phase 1 — commands.** `move_slot`, `swap`, `equip <slot|item>`,
`unequip <slot|item>`. Fully playable over telnet before any 3D exists, which is
the point.

**Phase 2 — read-only pane.** Plugin file, scene, grid, paper doll, mesh
resolver tiers 2–3, DOM labels, hover tooltips. No mutation, so nothing can go
wrong in the game from a rendering bug.

**Phase 3 — interaction.** Click actions and the context menu first, then drag in
order of risk: rearrange, then equip/unequip, then drop-into-world with the
cross-pane ghost.

**Phase 4 — models.** Fill in resolver tier 1: `GLTFLoader` into `vendor/`, a
static asset directory, a registry mapping asset keys to `.glb` files. Then
migrate the world pane's coloured spheres onto the same resolver. *Built as
described; see §9.*

---

## 6. Testing

Per `CLAUDE.md`, run only the touched modules during development:

```bash
../evenv/Scripts/evennia.exe test --settings settings.py systems.statefeed items.inventory commands
```

- Every test module must subclass `unittest.TestCase` — bare module-level
  `def test_*()` functions are silently skipped, which is how the
  `format_slot_cell` bug in `display.py` survived.
- `systems/statefeed/tests/` is the existing pattern: assert on the payload a
  game event produces, never on bytes reaching a socket.
- Worth covering explicitly: stack merge (two stacks in, one slot out), an
  equip that displaces two items back into the grid, `move_slot` onto an
  occupied slot and onto an empty one, and a snapshot taken while the grid holds
  a stale id (`_load` nulls those, and the payload must not carry a `None`).
- The full suite before merging, ~10 minutes:
  `test --settings settings.py items systems typeclasses commands world`.

---

## 7. Risks

**`InventoryHandler.slots` ordering is not stable across a reload.** `_load` and
`sync` re-pack orphaned entries into the first free slot. Once players can
arrange their inventory by hand, `sync` silently rearranging it is a bug they
will notice. Audit `sync` in phase 1 — it should only fill genuinely empty slots,
never compact.

**`at_object_receive` swallows exceptions** (`except Exception: pass` around
`inventory.add_item`). An emit added there must be inside its own guard, or a
feed error becomes a silently-lost item.

**Do not import anything under `blackout/scripts/`** from the new modules, and
exclude that directory from any tooling sweep. `map_sync.py` acts on the live
database; a bulk import once deleted 347 grid rooms.

**`lazy_property` caching** — if the pane ever needs a new handler accessor on
Character, pass `name=` explicitly to the factory or the accessors collide.

---

## 8. As built

Where the implementation diverged from the plan above, and what it turned up.

### Design changes

**The payload is one message, not two.** The plan had a `location` field
distinguishing an inventory payload from an equipment one. Equipping is a
single transaction that changes both halves, and two messages can be rendered
half-applied — so `items` and `equipped` ship together and the `location`
field is gone.

**The server also ships `equip_slots`** — every wield location in display order,
occupied or not. The client draws one frame per entry. Without it the pane
needed its own copy of `SLOT_DISPLAY_ORDER`, which is the duplication that made
the old client verb table wrong within a week. Adding a slot to `WieldLocation`
now lights up a new frame with no client edit.

**Emission moved off the commands.** The plan listed the commands as emit
sites. `EquipmentHandler` publishes from `equip`/`unequip`/`remove` instead,
because the EvMenu reaches those directly and a command-side emit would leave
the pane stale for the path most players use. `InventoryHandler` deliberately
does NOT publish from its own mutators — they run mid-move, where a stack merge
is about to delete the object being added — so `Character.at_object_receive`
and `at_object_leave` publish after `super()` instead.

**`sync()` needed no change.** §7 flagged it as a risk on the grounds that it
might repack a hand-arranged grid. Reading it, it only ever fills genuinely
empty slots and clears stale ids. The risk was unfounded; there is a test
pinning the behaviour so it stays that way.

### Bugs found during the build

**Unequipped and displaced items were never registered in a grid slot.**
`EquipmentHandler` returned items to the character with a direct
`obj.location = self.obj`, which does not fire `at_object_receive` (CLAUDE.md
gotcha 5), so `InventoryHandler.add_item` never ran. The item sat in contents
with no slot until something happened to call `sync()`. Invisible while the
only reader was the text grid, which syncs before rendering — and fatal the
moment a slot number is addressable, since `unequip main hand` followed by
`swap 1 5` would name an item the grid did not know it held. `equip` had always
done the mirror of this explicitly (`inventory.remove_item`), so the missing
inbound call was an asymmetry rather than a decision. Fixed in
`_return_to_inventory`.

**`|i` is eaten by the ANSI parser.** `"Usage: unequip <slot|item>"` reached
the player as `"Usage: unequip <slottem>"`. No vertical bars in player-facing
strings; there is a test pinning this one.

**A top-level `let` creates no property on `window`.** `blackout_meshes.js`
declared `let blackoutMeshes`, which other scripts can reference lexically but
which leaves `window.blackoutMeshes` undefined — and the window property is the
only form a pane can guard on without risking a `ReferenceError`. Every pane
correctly reported the resolver missing and fell back to its no-3D message. Now
published explicitly.

**Sending a command from `buildPane` blanks the entire webclient.** The pane
asked the server for a cold-start snapshot by sending `inventory` from
`buildPane`. When the pane is restored from a SAVED LAYOUT, `buildPane` runs
inside `myLayout.init()` — before the websocket has finished connecting — so
`Evennia.msg` reached `WebSocket.send` in the CONNECTING state and threw
`InvalidStateError`. GoldenLayout does not survive an exception escaping
component construction, and it aborts *after* goldenlayout's `init()` has
already removed the HTML-defined prompt and input divs. The whole client
renders blank. Not this pane: all of it.

It presents deceptively. Opening the pane by hand always works, because by
then the socket is long up; every page load *afterwards* is blank. Clearing
`evenniaGoldenLayoutSavedState` appears to fix it, which sends you looking at
layout corruption instead of at a send that happened too early. This is the
same class of failure `blackout3d.js` documents about registering components in
`postInit`, reached by a different route — and registering early does not help,
because the throw is in construction rather than registration.

Fixed in three places: `sendCommand` can no longer throw and reports whether it
sent; the cold-start request goes through `requestSnapshot`, which checks
`Evennia.isConnected()` first; and an unsendable request is remembered and
retried from `onLoggedIn`, where the socket is reliably up. In the normal case
the server's own `at_sync` resync arrives first and the request never happens
at all, so the player's text pane does not echo an `inventory` they did not
type.

**The general rule this leaves:** a pane lifecycle hook must never send to the
wire unguarded. `buildPane` in particular runs at a moment when the connection
may not exist.

**Evennia's emitter keeps ONE listener per channel, and binding is theft.**
`DefaultEmitter.on` does `listeners[cmdname] = listener` — it replaces rather
than appends. `blackout_inventory.js` bound every channel the server
acknowledged, copying `blackout3d.js`'s policy without copying its reason, and
so took `room_info`, `blackout_map`, `room_players` and the rest off the world
pane, then dropped them. **The world pane rendered a blank screen**, threw no
error and logged nothing — from its side the feed had simply gone quiet. It
also took `blackout_subscribed`, whose empty-set message is the only signal
that says "the server has forgotten you, subscribe again", so after a reload
nothing re-subscribed at all.

Fixed twice over. The inventory pane now binds exactly one channel, named at
authoring time, and never the acknowledgement — it does not need the
discovery mechanism that exists so `blackout3d` can claim-and-drop channels it
has never heard of. And a new `blackout_channels.js` makes ownership explicit:
a first-claim-wins registry both panes check, so a plugin asking for a channel
another already holds is refused and logged instead of succeeding and breaking
a pane it has never heard of. There is a standalone regression page covering
it — both plugins, real load order, full acknowledgement — asserting that the
world pane keeps its channels and that an empty ack still triggers a
re-subscribe.

**An optimistic move invalidates the server's action strings.** The commands in
a row's `actions` were built against the slot the item was in when the snapshot
was taken. Swapping slot 1 to slot 6 and immediately dragging onto the paper
doll sent the stale `equip 1` — equipping whatever was *now* in slot 1, which
is the wrong item. Optimistically-moved rows are marked, and `namedAction`
refuses them until the next snapshot rebuilds their commands: the frame does
not light up and nothing is sent, for the one tick it takes. Rebuilding the
command client-side from `row.slot` would have been this file inventing a verb,
which is what the world pane's deleted verb table exists to warn against.

**Optimistic drag has to predict the WHOLE outcome.** The first version moved
only the dragged mesh, so a swap left the displaced item sitting underneath it
until the snapshot landed. Each gesture now predicts exactly as much as it
honestly can: a swap moves both meshes and updates both rows' slot numbers, an
equip moves the mesh to the frame that was dropped on, and an unequip *removes*
the mesh rather than guessing — the destination is the first free slot, which
is the server's decision and depends on state the pane does not track.

### A rule this added

**One channel, one owner, declared.** Because Evennia's emitter holds a single
listener per name, a Blackout plugin must bind only channels it actually
handles, and must claim them through `blackout_channels.js`. Sweeping up the
server's acknowledged list is a policy exactly one plugin may have —
`blackout3d`, so that a channel added server-side cannot reach `default_out.js`
and get printed at the player as raw JSON — and it now yields to any explicit
claim.

### Verification

The pane was driven end to end against a stubbed GoldenLayout and Evennia, with
a snapshot shaped exactly like `CharItemsPayload.to_dict()`. Confirmed: the
layout centres, the cold start sends `inventory`, the context menu is built
from the server's `actions`, and the gestures send `swap 1 6`, `equip 1`,
`unequip neck`, and — dropping a body item on the two-hands slot — nothing at
all. A second page loads both plugins in the real order and confirms the world
pane keeps every channel it owns, the inventory pane gets its one, an empty
acknowledgement still triggers a re-subscribe, and nothing falls through
unhandled.

---

## 9. Phase 4 as built

Tier 1 loads, one item has real art, and the world pane has not moved yet.

### There is no UMD `GLTFLoader` at r159

`examples/js` — the non-module build directory — was deprecated at r147 and
**deleted at r148**. The vendored core is r159, so the newest UMD loader that
exists at all is a release older than the core it runs against. The pairing was
checked rather than assumed: all 63 `THREE.*` symbols the r147 loader touches
are present in r159, and the one API that moved (`texture.encoding` →
`.colorSpace`, r152) still has its compatibility accessor, which is why loading
a textured model prints exactly one deprecation warning and renders in correct
sRGB. `vendor/README.md` carries the detail.

Both files fall off the same r160 cliff. Whatever forces three.js into ES
modules forces the loader on the same day, and the fix is one import map rather
than two migrations.

### Models are normalised on load, not trusted

A download arrives in whatever scale, origin and axis convention its author
used. The rusty sword is four units long, pivoted under the grip, lying along Z
because its exporter wrote a Y-up conversion matrix — while tier 2 promises a
unit box, centred, blade up the Y axis. Two tiers that do not agree on that
cannot stand in for each other, so tier 1 measures and refits every model:
scale the longest axis to `UNIT`, then re-measure and re-centre.

What measurement cannot recover is which end is the tip, so `registerModel`
takes an optional `rotation` — applied *inside* the measurement, so that
standing a sword up re-measures the box it turned into. The pane assigns
`rotation.x` and `scale` to what `resolve` returns, so the correction lives on
an inner group and the returned pivot stays identity; putting it on the pivot
would have looked correct and been silently overwritten on placement.

### Failure resolves, it never rejects

A rejected promise propagates into the caller's `.then`, which is a placement
loop: the callback never runs, the slot renders empty, and a cached rejection
makes that permanent for the session. `loadModel` therefore reports failure as
a resolved `null`, which the caller reads as "use tier 2" exactly as an
unregistered key does — and caches it, so a 404 costs one request rather than
one per rebuild. A missing `GLTFLoader.js` degrades the same way, warned once.

### The clone-sharing bug tier 1 would have introduced

`Object3D.clone()` deep-copies the scene graph and shares geometry, materials
and textures with the prototype — which is what makes the cache worth having,
and what made the inventory pane's `disposeMesh` wrong the moment a model
loaded: it disposed both on every clone it dropped, so every rebuild freed the
prototype's GPU resources and the next clone re-uploaded them. Disposal moved
to `blackoutMeshes.release`, which knows which of the two it handed out.
Procedural builds are marked as owning their resources, clones as not.

### One model, and a build step

`assets/pack_model.py` turns a download into the served `.glb`: textures
resampled to 512, everything embedded, four requests and 1.1 MB down to one and
128 KB. Registration is one line in `blackout_models.js` — a file rather than a
directory scan, because with 16 items and one model a convention-based lookup
makes fifteen 404s the normal case.

### Verification

Node harnesses cover the resolver against the real vendored loader and the real
packed `.glb` — 24 assertions: container parse, normalisation, orientation,
cache reuse, clone sharing, `release` semantics, and both failure paths. Then
the same code in a real browser at `/webclient/`: the model fetches and decodes
(2 meshes, two 512² textures, sRGB, normal map bound), normalises to a unit box
on the origin with its long axis on Y, renders in WebGL with no GL error, an
unmodelled item still falls to its procedural mesh, and a second resolve is
served from cache in 0 ms.

### The world pane

Entities are resolved meshes now, not coloured spheres, and the three things
that blocked it were each real.

**The feed names the fallback, not the client.** `serialize_entity` grew a
`family`: an item's ITEM_DB tag category, and the entity's own kind for
everything else. One field rather than two, because the alternative — send
`family` for items and let the client reach for `kind` otherwise — puts the
precedence rule in the renderer, where every client that ever connects has to
repeat it. The two vocabularies cannot collide, so one namespace holds both.
`_item_family` moved from `statefeed/inventory.py` to `serializers.py`, beside
`_classify`, since two callers now need the same answer.

The payoff is the one the shared resolver was built for: a spear on the floor
and the same spear in a bag report the same family and draw the same mesh.

**Colour moved with the shapes.** The `COLOR_ENTITY_*` palette left
`blackout3d.js` for `blackout_meshes.js`, because what a thing looks like is
one fact. `entityColor` is gone; the pane asks for a mesh and draws what it is
given. Four procedural kinds were added to tier 2 — a figure for `npc` and
`character` in the two colours that already distinguished them, a console for
`station`, a rock-with-a-shard for `gatherable`. The gatherable is
deliberately NOT the material family's two lumps: an ore you carry and a node
you mine are different affordances, and drawing them alike is how the rusty
pole came to be offered as `get`.

**Entities own their materials, and the pane frees them.** A resolved mesh may
be a clone sharing a prototype's materials with every other entity of that
asset key, while hover writes `emissive` and the hit flash writes `color` — so
`takeOwnMaterials` clones the materials, and only the materials, at placement.
Geometry and textures stay shared, which is the expensive half. A flash then
whitens one raider instead of every raider in the neighbourhood.

Two consequences fell out. `flashEntity` had to stop restarting a running
flash — a second hit inside the first would record WHITE as the colour to
restore, and a stationary NPC under repeated attack would stay white for the
whole fight — so an overlapping hit extends the timer instead. And
`clearEntities` now disposes the pane's own material clones and hands the rest
to `blackoutMeshes.release`, which is the leak fix: before this it freed
nothing at all, so every list and every delta orphaned a geometry and a
material per entity.

**Placement is asynchronous now**, so it carries a generation counter like the
inventory pane's. A mesh resolved for a superseded list is released rather than
added; without it an NPC that walked out of radius reappears a frame later,
placed where it used to stand, with nothing left to remove it.

### Verification

The pane was driven against a stubbed GoldenLayout and Evennia, served from
the game's own origin so the model URL resolves, with the real files loaded
from `/static/`. Thirteen assertions: a crowd of seven places, an npc and a
station are several meshes rather than one sphere, the dropped shortsword is
the textured glTF model, two raiders of one asset key hold different materials,
flashing one leaves the other alone, overlapping flashes restore `#ff5f56`
rather than white, redrawing the list frees 17 geometries where it used to free
none, and the cached model's own geometry survives that release.

### A thing worth knowing about thin models

A sword normalised to a unit box and then drawn at `ENTITY_SCALE` is 3% of a
tile wide. It renders, and screen-space picking still finds it, but a dark
blade edge-on against a dark tile is much harder to see than the gold sphere it
replaced. Nothing is wrong; the promise that a silhouette says what a thing is
just cashes out worse for a thin object at world zoom than at inventory zoom.
Raising `ENTITY_SCALE`, or giving ground items a marker under them, are the two
obvious answers, and neither is obviously right yet.
