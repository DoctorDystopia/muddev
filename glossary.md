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
| moderator egg | the `egg` item and its staff menu | dev egg, admin tool |
| god mode | the damage-immunity flag that the moderator egg sets | godmode, invulnerability |
| family | the look an item renders with, from `ITEM_FAMILY_PRIORITY` | item type, item class |
| dossier | the summary screen of a character (`score`, `char_summary`) | character summary, character sheet |
| panel | one band of the dossier (`summary/panel_defs/`) | section, block |
| roster | the skills payload that `CHANNEL_CHAR_SKILLS` sends | skill list |

## Client

| Use | For | Not |
|---|---|---|
| Godot client | the one canonical client, in `godot/` | frontend, game client |
| webclient | the retired browser client in `archive/webclient-js/`, and nothing else | web client, JS client |
| pane | one region of the Godot client UI | window, view |

"Panel" and "pane" are two items. A panel is a band of the dossier on the
server. A pane is a region of the client screen. A Godot node class such as
`PanelContainer` is an identifier, so this rule does not apply to it.
