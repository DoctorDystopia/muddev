# Blackout Glossary

This file gives the technical nouns for prose about Blackout: docs, READMEs,
commit messages, code comments, and replies about this repo. ASD-STE100 rule
1.11 says to use one technical noun for one item. This repo learned the same
rule from a bug. "Metalsmith" and "Metalsmithing" named one skill, and every
anvil recipe disappeared.

Use the noun in the first column. Do not use a noun from the last column for
the same item. An identifier in backticks, for example `npc_key` or `ItemDef`,
is not a noun here. Write it exactly as the code does.

When a new system names a new item, add a row here before the first doc uses
the name.

## Server

| Use | For | Not |
|---|---|---|
| statefeed | the package that shapes TRUE state for a player (`systems/interface/statefeed/`) | state feed, feed system |
| channel | one named stream in the statefeed, for example `char_summary` | topic, event type |
| snapshot | one payload that a channel sends | packet, update |
| emitter | a function that sends a snapshot, for example `emit_vitals` | sender, publisher |
| tick | one step of the global clock | heartbeat |
| phase | one stage inside a tick, for example FEED | stage |
| tile | one square of the tile grid. It has a tile room only while something stands there | cell, square |
| map rebuild | a run of the retired `clean_and_reload_all_maps.ps1` on the xyzgrid maps (`archive/xyzgrid-maps/`). The tile sync took its place | grid rebuild, respawn |
| shopkeep | an NPC that sells items (`ShopkeepNPC`) | shopkeeper, vendor, merchant |
| NPC def | the `NpcDef` of one NPC, one entry in a module under `world/npc_defs/` | NPC template, NPC prototype, NPC data |
| combat block | the `NpcCombat` of an NPC def. Only an NPC that can fight has one | stat block, combat profile |
| role | the typeclass of an NPC: hostile, talkative, shopkeep or Preceptor | NPC type, NPC class |
| dialogue | the EvMenu node tree that an NPC speaks from, one module in `world/npc_dialogues/` | conversation tree, dialogue menu |
| ware | one item kind that a shop sells, one row of `get_buy_items` | good, product |
| stock level | how many units of a ware a shop has now (`stock.level`) | inventory, supply |
| restock | the return of one unit to a ware below its `max_stock` | refill, replenish |
| endless stock | a ware with no `WareStock` rule, which never runs out | infinite stock, unlimited |
| moderator egg | the `egg` item and its staff menu | dev egg, admin tool |
| god mode | the damage-immunity flag that the moderator egg sets | godmode, invulnerability |
| family | the look an item renders with, from `ITEM_FAMILY_PRIORITY` | item type, item class |
| dossier | the summary screen of a character (`score`, `char_summary`) | character summary, character sheet |
| panel | one band of the dossier (`summary/panel_defs/`) | section, block |
| roster | the skills payload that `CHANNEL_CHAR_SKILLS` sends | skill list |
| profile | the menu that shows the dossier, skills and records of any character (`profile`, `profile_menu.py`) | inspect screen, public dossier, honours |
| PvP flag | the per-character choice that allows attacks between two players (`pvp on`, `systems/gameplay/combat/pvp.py`) | PvP mode, PvP toggle, PK flag |
| login token | the random secret that lets one device log in to one account with no password. The server keeps only its digest (`systems/core/login_tokens/`, `remember`, `resume`, `forget`) | auth token, session token, remember-me token |
| speech command | a command that speaks to the characters near the speaker: `say` or `yell` (`systems/gameplay/speech/`) | chat command, talk verb |
| reach | the rule that decides which characters hear a speech command: the say range, or the area of the speaker | earshot, hearing range, scope |
| say range | the tiles that a `say` reaches: `SAY_RADIUS` tiles on the plane of the speaker. It is the radius of the statefeed contents | hearing radius, say radius, earshot |
| listener | a character with a connected session that hears a speech command | hearer, audience member, recipient |
| moment | one game event that the server names for a client to mark, for example `task_complete` (`CHANNEL_MOMENT`, `MOMENTS`) | game event, trigger, sound event |
| status light | the dot in the nav bar of the website that shows if the game server is up, and the player count (`/status.json`, `systems/interface/serverstatus/`) | status indicator, health check, uptime badge |

## Client

| Use | For | Not |
|---|---|---|
| Godot client | the one canonical client, in `godot/` | frontend, game client |
| webclient | the retired browser client in `archive/webclient-js/`, and nothing else | web client, JS client |
| pane | one region of the Godot client UI | window, view |
| pop-up | a box that the server opens over the world pane, for example the bank (`char_popup`) | window, dialog, interface, modal |
| vault layout | the bank tabs, the order of the slots, the tab names and the placeholders of one vault (`systems/gameplay/banking/layout.py`) | bank layout, bank config |
| bank tab | one numbered group of vault slots. A tab that becomes empty disappears (`bank move`, `bank view`) | bank folder, category, page |
| main tab | tab 0 of the vault. It holds each slot that is in no other tab, and it shows every slot, grouped by tab | All tab, default tab, tab zero |
| placeholder | a vault slot that keeps its place and its tab after the last unit leaves. It uses one slot until the player releases it (`bank release`) | ghost slot, empty slot, reserved slot |
| dock | the box of the game log or of the control panel. Both are HUD elements (`%ConsoleDock`, `%PanelDock`) | window, sidebar, drawer |
| grip | the strip on an edge or a corner of a box that a drag resizes (`ResizeGrips`) | handle, resizer, border |
| HUD element | a box over the world pane that the player places in the layout editor: a dock, the minimap, the vitals, the XP drops, or the hover text (`HudElements`) | widget, frame, panel, component |
| layout | where each HUD element sits, and its size, opacity, scale and Shown flag (`ClientSettings.layout`) | UI config, arrangement |
| layout editor | the mode in which the player changes the layout. Options opens it (`LayoutEditor`) | edit mode, UI edit mode, unlock mode |
| layout preset | a layout that the player saved by name (`ClientSettings.layout_presets`) | profile, saved layout, template |
| anchor | the point of the pane that a HUD element keeps its distance from: a corner, an edge centre, or the centre (`HudLayout`) | pin, attach point |
| chat tab | one filter of the game log: All, Game, Combat, Local, Private, or Channel (`ChatTabs`) | chat filter, log tab |
| chat bar | the row of chat tab buttons under the input (`ChatBar`) | tab strip, chat buttons |
| chat mode | where a typed line goes: Command, or a mode that `char_chat` names, for example Say (`ChatModes`) | chat channel, talk mode |
| Command mode | the chat mode that sends a typed line as it is. The default | raw mode, normal mode |
| cue | the name of one sound that the client plays, mapped to one clip (`SoundCues`) | sound effect, SFX key |
| saved login | the login token and the account name that the Godot client keeps on one device (`SavedLogin`, `user://login.cfg`) | stored credentials, remembered login, auto-login |

"Panel" and "pane" are two items. A panel is a band of the dossier on the
server. A pane is a region of the client screen. A Godot node class such as
`PanelContainer` is an identifier, so this rule does not apply to it.

## Skills and crafting

The skill framework in the Obsidian vault
(`03_Systems/Skills/Skill_Framework.md`) is the source of these nouns. It says
what each item means and which rule uses it.

| Use | For | Not |
|---|---|---|
| skill cycle | the loop Gathering → Processing → Production → Combat and Utility → Gathering | pipeline, skill tree, chain |
| category | the group a skill belongs to, for example Processing | skill type, tier, branch |
| stage | the position of an item in the skill cycle | tier, level, grade |
| world resource | an item that a Gathering skill takes from a node | raw material, raw resource |
| crafting component | an item that a Processing skill makes, and that another recipe consumes | intermediate material, refined material |
| finished product | an item that a Production skill makes, and that no recipe consumes | finished item, finished gear, end product |
| forward pass | a recipe that takes inputs from the previous stage | normal recipe |
| same-stage pass | a Processing recipe that takes a crafting component and makes another one | treatment, second pass, sideways recipe |
| placement | an action that consumes items and makes a gathering node | planting, seeding |
| secondary XP | the smaller XP award that a second skill of the same category gets | bonus XP, synergy XP |

The tag `crafting_material` and the field `consumable_tags` are identifiers.
Write them as the code does. In prose, the item they hold is a crafting
component or a world resource.

## Combat

DESIGN-0009 named these on 09/17/2026. The important row is the first one.
"Ranged" is the OSRS skill name, and the code uses "projectile" for every
Blackout item: `PROJECTILE_COMBAT_AXES`, `projectile_strength_bonus`,
`DAMAGE_TYPE_PROJECTILE`. Write the noun the same way in prose.

| Use | For | Not |
|---|---|---|
| projectile | a shot that travels to a tile away from the shooter | ranged, missile, distance attack |
| projectile weapon | a weapon that fires ammunition, for example a shortbow | ranged weapon, gun, bow class |
| ammunition | what a projectile weapon spends per shot | ammo, projectiles, arrows |
| family | the group that matches an ammunition item to a weapon | ammo type, calibre |
| reach | how many tiles an attacker covers, from `max_range` plus the style | range, distance, radius |
| combat axes | the table naming which skills an action resolves against | skill mapping, stat map |
| combat style | one entry in a weapon's `combat_styles` table, for example snipe | stance, attack mode |
| weapon style | the manner a style fights in: accurate, aggressive, defensive, controlled | style class |
| attack type | the bonus a style reads: stab, slash, crush, light, standard, heavy | damage class |
| damage type | what `at_damage` is told the hit was, for example projectile | attack type |
| grace | the ticks an attacker holds after its target leaves reach | grace period, timeout |
| leash | the tiles a chasing NPC follows before it returns | tether, aggro range |
| recovery | the chance a spent projectile drops instead of breaking | salvage, refund |
| max hit | the highest damage that one swing can roll: the top face of its damage die (`ActionResult.max_hit`). A natural 20 is the max hit of a d20 | max damage, crit, perfect hit |
| hitsplat | the damage number that the Godot client draws over a figure for one swing (`HitsplatLayer`) | damage number, damage popup, floating text, splat |
| hitsplat style | the look of one kind of hitsplat: one `.tres` file in `godot/world/hitsplats/styles/` (`HitsplatStyle`) | hitsplat theme, hitsplat skin |
| detail line | the small line under a max hit hitsplat that names the roll and a bonus or a penalty | subtitle, caption, breakdown |

Guns and Ballistics are skill names, so they are identifiers. Guns decides
whether a shot lands. Ballistics decides how hard it lands.

## Exterminator

DESIGN-0012 named these on 10/06/2026. The vault note
`03_Systems/Skills/Utility_Skills/Exterminator_Skill.md` owns the rules.
Most player-facing names are TBD. These are the nouns for prose about the
code.

| Use | For | Not |
|---|---|---|
| Exterminator | the Utility skill of the task loop (`SKILL_KEY_EXTERMINATOR`) | Slayer, hunter skill |
| Preceptor | an NPC that gives a task and teaches buffs | slayer master, task master, task giver |
| task | one order from a Preceptor to kill a count of one creature type | assignment, quest, contract, job |
| creature type | a general kind of hostile NPC that a task names, for example `mutant` (`world/creature_types.py`). One NPC can have several | monster type, category, family, species |
| task kill | the death of a creature of the task type that counts on the task | slay, task credit |
| buff | a change to combat or to the task that a player picks during a task, and keeps until the task ends | boon, perk, modifier, rite |
| archetype | the mechanic of a buff, with no name and no lore, for example `accuracy_vs_type` | buff type, template |
| pick milestone | a point of task progress where the player gets one pick | checkpoint, threshold |
| banked pick | a pick that came due and that the player did not use yet | pending pick, stored pick |
| offer | the cards that one pick shows | draft, choice, roll |
| card | one buff in an offer | option, slot |
| rarity | the tier that a card rolls: Common, Rare, Epic, or Legendary. It sets the strength of the buff (`RARITIES`, `strengths`) | grade, quality, tier level |
| pick menu | the EvMenu that shows the cards to a session with no pop-up (`exterminator_pick_menu.py`) | pick screen, card menu |
| Exterminator points | the points that a completed task gives | slayer points, currency |
| streak | the count of tasks completed in a row | combo, run |
| Task Writ | the free item from a Preceptor that opens the task pop-up (`TASK_WRIT_ITEM_KEY`). Name TBD | slayer gem, task item, task scroll |
| seam buff | a buff that replaces one seam of an action, for example the damage roll | override buff, mechanic buff |
| seam conflict | a seam that a buff and an item, or two buffs, both own. The pick card warns about it (`seam_conflicts`) | clash, collision, overlap |
| damage dealer | a combatant that took HP from a victim before the death of the victim. Each one gets the task kill | contributor, attacker list, participant |
| damage record | the record of each damage dealer and its damage, on the victim (`damage_record`, `DAMAGE_RECORD_ATTR`) | threat table, hit log, damage log |
| pool | the buffs that one Preceptor teaches (`PreceptorDef.buff_pool`). Two pools can share a buff | buff list, deck, loot table |
| par time | the online time inside which a task must end for the `par_time_points` bonus (`par_seconds`) | time limit, deadline, speed target |

## 3D models

The model pipeline in `blackout/assets/`. "Recipe" is a crafting noun, so a
model file is never a recipe.

| Use | For | Not |
|---|---|---|
| source | one download in `assets/sources/`, exactly as it arrived | pack, asset, download folder |
| source record | the `source.toml` of a source: author, URL, license, file hashes | license file, SOURCE.md |
| model record | the `.toml` in `assets/models/<family>/` that says how to build one served model | recipe, manifest row, model config |
| alias | a second asset key that draws the same served model | duplicate, copy |
| fix | a correction to a bad export, baked into the served file by the build | presentation, override |
| license gate | the build's refusal of a source whose license is not allowed | license check, whitelist |
| exception | a reason in a source record that waives the license gate | override, waiver |
| local source | a source with `local = true`: git keeps its source record and ignores its files. A bought pack is one | private source, paid source, untracked source |
| served tree | `web/static/webclient/models/`, the files the client fetches | model tree, static models |
| credits box | the box in the Godot client that the Options pane opens | credits pop-up, credits window |

## Terrain

DESIGN-0011 named these on 09/23/2026. "Tile" keeps its meaning from the
Server section, with one change: on the tile grid, a tile does not always have
a room.

| Use | For | Not |
|---|---|---|
| tile grid | the world-wide grid of heights, floor types, and walk flags | heightmap, world grid, terrain grid |
| chunk | a 64 x 64 part of the tile grid, stored in one chunk file | map square, region, sector |
| chunk file | the file that holds one chunk. The editor writes it, and the server reads it | map file, chunk data |
| height step | the integer unit of a corner height | height unit, elevation level |
| floor type | the named ground on a tile, for example `sand` | ground type, underlay, terrain |
| walk flag | a bit that limits movement on a tile or across an edge | collision flag, blocker |
| area | a named part of the world. The client picks fog and light by area | zone, biome, region |
| plane | one level in a stack, for example a second floor | floor, level, layer, storey |
| tile room | a `TileRoom`: the Evennia room at a tile of the tile grid, which exists only while something stands there | sparse room, grid room |
| pool | the empty tile rooms that wait for the next step (`TileRooms`) | cache, free list |
| parity test | the pair of tests, one in Python and one in GDScript, that hold the two chunk file readers to the same answers | cross-check, sync test |
| semantic dump | the text that says what a chunk file means, one fact on each line. The parity test compares its digest | canonical dump, meaning file |
| object kind | the key of a placed object in a chunk file, a row of `world/object_kinds.py`. One kind for each variant, except the words of a signpost: one `signpost` kind, and each placement holds its own `text` | object type, prefab, object ID |
| sign text | the words of one `signpost` object, in the `text` of its chunk object. The terrain editor edits it | label field, caption, sign string |
| terrain editor | the Godot editor plugin in `godot/addons/blackout_terrain/` that writes the chunk files | map editor, world editor, terrain tool |
| block | the 4 x 4 chunks that the terrain editor loads around its centre chunk | chunk window, loaded area, scene |
| brush | one tool of the terrain editor that changes the corners or tiles in a circle | tool (for a brush), stamp |
| stroke | every dab of a brush from a press to its release. One stroke is one undo entry | drag, paint pass |
| tile world | the chunk files of `world/chunks/`, loaded as one tile grid and one room index (`TileWorld`). Its rooms have the Z `tile_world` | new world, tile map, grid world |
| transition | an object kind that moves a walker to its target tile when the walker steps onto its tile | portal, warp, map link |
| pin | the mark on a tile that keeps its tile room out of the pool, for example under a chunk object | lock, anchor, sticky room |
| tile sync | the operator step that makes the objects on the tile world match the chunk files (`scripts/sync_tile_objects.py`) | map rebuild, respawn, reconcile |
| tile map | the ASCII map of the tile world that a telnet player sees (`world/tile_map.py`) | minimap, xymap |
| landmark | an object kind that names its tile and stands nothing up | marker, waypoint, POI |
| respawn point | the landmark `respawn_point`. A dead player, a new character, and a character with no tile come back on its tile | spawn point, start room, home tile |
| cutover | the operator step that moves every character to the tile world and deletes the xyzgrid maps (`scripts/move_to_tile_world.py`) | migration, map move, switchover |
| walk limit | the largest change of tile height, in height steps, that one step may climb or drop (`WALK_LIMIT`) | slope limit, max climb, step height |
| cliff | an edge between two tiles whose heights differ by more than the walk limit. No step crosses it | ledge, drop, steep edge |
| cliff face | a triangle of the ground mesh that is steeper than the walk limit. The client draws it in the cliff colour | rock face, slope face |
| line of sight (short: sight) | a clear line for a shot between two tiles: no wall and no Blocked tile stops it (`tilegrid/sight.py`) | LOS, visibility, line of fire |
| sweep | the pass that gives each empty tile room with no pin back to the pool (`tilegrid/sweep.py`) | reaper, cleanup, garbage collection |
| climb | an object kind (a ladder or stairs) that moves a walker on its tile one plane up or down. Also the command that does it | ladder link, stair portal, teleport |
| void | the floor type `void`: a tile with no floor, on plane 1 and up. It is always Blocked, and the client draws no ground on it | hole, gap, empty tile |
| hide roofs | the client setting that hides every plane above the plane of the player while the player is under a roof | roof toggle, x-ray |
| content check | one rule of `world/tile_checks.py` over the chunk files of a world, for example "a transition lands on an open tile". The terrain editor runs the same rules as "Check world" | validation, world lint, world test |
| finding | one content check that fails, at one tile | error, issue, violation |
| wall | a walk flag on one edge of a tile. No step and no shot crosses that edge. The client draws a slab on the edge (`WallMeshBuilder`) | fence, barrier, edge block |
| scenery | the model that the client stands on the tile of an object kind with no spawner, for example the teleporter pad of a transition. The `scenery` of the kind row names it | prop, decoration, tile prop |
| primitive | a scenery key with no model record yet, in `SCENERY_PRIMITIVES`: `ladder`, `stairs`, `hatch`, and the decor shapes `crate`, `table`, and `lamp_post`. `PropMeshBuilder` draws it as plain boxes until art arrives | placeholder, stub mesh, proxy |
| hatch | the primitive on the tile of a climb that only leads down: a framed opening in the floor | trapdoor, stairwell, hole |
| rotation | the quarter turns of a placed object in a chunk file, 0 to 3, clockwise from north. The Turn action of the terrain editor adds one | orientation, heading, angle |
| facing | the rotation of the chunk object that stood an entity up. The tile sync writes it on the entity (`FACING_ATTR`), and the statefeed sends it | direction, yaw, heading |
| preview | the asset key and the family of the entity that an object kind stands up. Only the terrain editor reads it, to draw the model on the tile | editor model, thumbnail |
| tile sync stamp | the digest of each chunk file at the last tile sync, in `blackout/server/tile_sync_state.json` | sync marker, sync log |
| link | where a transition or a climb leads. The terrain editor draws it | connection, portal line |
| ghost | the dim copy of a plane other than the edited plane, in the terrain editor. The planes below show as a ghost, and the planes above can | shadow, underlay, onion skin |
| beacon | the tall mark in the terrain editor over the selected object or the tile of a finding | marker, highlight |
| structure | a building or a wall that the Build tools make from walls, floor types, planes, climbs, and roofs (DESIGN-0013) | building object, WMO, prefab |
| structure editor | the Build tab of the terrain editor | building editor, construction mode |
| wall top | the top edge of a wall: the corners of the plane above where that tile has a floor, else the height of its wall style | wall cap, wall height |
| wall style | the look of the walls of one tile, a row of `world/wall_styles.py`. It sets the colour and the height with nothing above. A chunk file of format 2 holds it | wall type, wall material, wall skin |
| format 2 | the chunk file format with the wall style layer (`wall_names`, `walls`). The writer writes it only when a tile has a style other than `plain` | wall format, v2 |
| note | a content check result that warns and does not fail a test. `unreachable` gives a note | warning, soft finding |
| live check | the cheap content rules that the Build tab runs on the tiles of each gesture | instant check, validation |
| hint line | the line at the bottom of the 3D view that names the Build tool, its gesture, each modifier, and each toggle | status bar, tooltip |
| roof | the tiles of a plane above a structure that carry a roof floor type and the Blocked flag. The Roof tool shapes their corner heights | roof object, roof mesh, ceiling |
| roof floor type | a floor type with `roof` set, in `world/floor_types.py`. The client draws no cliff colour on it | roof tile, roof material |
| roof shape | the rule that gives the corner heights of a roof: flat, shed, gable, hip, or pyramid (`roof_shapes.gd`) | roof type, roof style |
| eave | the edge of a roof. The roof meets the walls one plane rise above the base, and the overhang hangs lower | roof edge, roof lip |
| under a roof | a player whose tile has a floor that is not void on some plane above. "Hide roofs" hides the planes above only then | indoors, inside, covered |
| outline | the lattice that a Build tool draws before the release, at the heights of its plan. Green builds, amber builds with a warning, red refuses | ghost, preview, blueprint, hologram |
| template | a saved structure in `blackout/world/structures/<key>.json`. The Place tool writes a copy of it into the chunk files (DESIGN-0013 section 6.6) | prefab, blueprint, stamp |
| template copy | the tiles, corners, and objects that one click of the Place tool writes from a template. Nothing links it to its template | placement, instance, stamp, spawn |
| footprint | the tiles that a template covers, at the tile under the mouse of the Place tool | bounds, lot, plot |
| cover | the mark on a tile of a template that the template owns. The Place tool writes only the covered tiles | mask, used tiles |
| blend ring | the corners around a footprint that the Place tool moves part of the way to the base height | skirt, falloff, feather |
| tile selection | the tiles that the Select tool of the Build tab holds, on one plane or on several. Delete, Copy, and Move act on it | selected tiles, marquee, region |
| clipboard | the template that Ctrl+C makes from the tile selection. It lives in the editor only, until "Save as template" writes it | buffer, copy store |
| structure workbench | the terrain editor scene on scratch chunk files outside the repo, `structure_workbench.tscn`. The author builds a template there, away from the world (DESIGN-0013 Phase S6). The crafting facility keeps the word "workbench" | workbench, sandbox, prefab mode, test map |
| protect structures | the Paint tab toggle that stops a sculpt from changing a corner of a tile with a wall or with a floor above it | lock walls, freeze buildings |
| decor | an object kind of the category `decor`: scenery that pins no tile room and may stand on a Blocked tile. A tile holds one decor. The Decor tool of the Build tab places it (DESIGN-0013 section 6.5) | prop, furniture, clutter |

## Maps

The two maps of the Godot client, named on 09/28/2026. The telnet map keeps
its name: tile map.

| Use | For | Not |
|---|---|---|
| minimap | the small map in the corner of the world pane (`MinimapView`) | radar, mini map, tile map |
| world map | the large map of every chunk of one plane (`WorldMapView`). The `worldmap` command sends its data | overview map, atlas, full map |
| destination marker | the red flag on the goal tile of the current walk | walk flag, click flag, waypoint |
| walk path | the tiles that the current walk still has to step on | route, trail, path line |
| map dot | a dot for a live entity on the minimap | blip, marker, pip |
| map icon | a symbol for a chunk object (a bank, a node, a transition) on either map | map marker, POI icon, map symbol |
| world map summary | the compact form of one chunk for the world map: one character for each tile, and its objects | map chunk, thumbnail, overview chunk |

## Movement

The walk and the run, named on 09/29/2026 (`systems/gameplay/movement/`).

| Use | For | Not |
|---|---|---|
| walk | the tiles that a character still has to step on, which the tick moves (`TileWalk`). A direction command and `goto` each start one | move queue, route, auto-walk |
| walker | a character with a walk | mover, pathing character |
| run | the toggle that moves a walker two tiles each tick, not one. Also the command that sets it | sprint, dash, fast walk |
| stride | one move of a walker across one or more tiles, with one `move_to` (`movement.stride`) | jump, multi-step, leap |
| tile skip | the rule that the middle tile of a run gets no room and no arrival hook | skipped step, pass-through |
| held key | a movement key that the player keeps down. The client sends its direction again every half tick | key repeat, hold-to-walk |
| Run button | the toggle in the top-left corner of the minimap that sends `run` | run orb, run toggle button |

## Deploy

The deploy scripts in `deploy/`, named on 10/05/2026.

| Use | For | Not |
|---|---|---|
| full deploy | a run of `deploy/full_deploy.sh`. Every leg runs | complete deploy, full push |
| diff deploy | a run of `deploy/diff_deploy.sh`. A leg runs only when its inputs changed since its last run | incremental deploy, delta deploy, partial deploy |
| leg | one part of a deploy: the constants check, the server, the Godot client, or the verify | stage, step, phase |
| deploy record | the list of the inputs of one leg at its last successful run, with a SHA-256 for each file (`deploy/.deploy_state/<leg>.list`) | deploy state, deploy cache, snapshot |
| publish record | the SHA-256 of each R2 key at its last upload by `publish.sh` (`deploy/.deploy_state/r2_<bucket>.tsv`) | upload log, R2 manifest, R2 cache |
| baseline | a run of `diff_deploy.sh --baseline`. It writes the deploy records and deploys nothing | seed, mark-deployed |
