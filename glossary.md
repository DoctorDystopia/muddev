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
| tile | one room on an XYZ grid map (`GridTile`) | cell, square |
| map rebuild | a run of `scripts/clean_and_reload_all_maps.ps1` | grid rebuild, respawn |
| shopkeep | an NPC that sells items (`ShopkeepNPC`) | shopkeeper, vendor, merchant |
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

## Client

| Use | For | Not |
|---|---|---|
| Godot client | the one canonical client, in `godot/` | frontend, game client |
| webclient | the retired browser client in `archive/webclient-js/`, and nothing else | web client, JS client |
| pane | one region of the Godot client UI | window, view |
| pop-up | a box that the server opens over the world pane, for example the bank (`char_popup`) | window, dialog, interface, modal |

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

Guns and Ballistics are skill names, so they are identifiers. Guns decides
whether a shot lands. Ballistics decides how hard it lands.

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
| served tree | `web/static/webclient/models/`, the files the client fetches | model tree, static models |
| credits box | the box in the Godot client that the Options pane opens | credits pop-up, credits window |
