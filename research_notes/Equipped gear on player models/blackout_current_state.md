# Blackout current state: equipped gear on player models

Read-only investigation of local files, done 10/11/2026 on branch `main` at commit `96247fd`. Each path is relative to `C:\Users\NickR\source\repos\muddev\` unless it starts with a drive letter. A citation follows the word "Source:" and has the form `path:line`. A line marked **INFERENCE** is my reading, not a statement of a file. A line marked **CONFLICT** shows two files that do not agree. No Python ran, no test ran, and no binary file was opened.

## 1. Equipment on the server: slots, the equipment handler, hooks, and what an `ItemDef` carries for looks

### Takeaway
The server has twelve equipment slots and one handler that stores a slot-to-object dict on each player character. An `ItemDef` has no look field: the asset key of an item is its prototype key, and its family comes from its tag categories.

### Cited Findings

#### Slots
- `WieldLocation` has twelve members: `main_hand`, `off_hand`, `two_hands`, `body`, `legs`, `head`, `back`, `feet`, `neck`, `main_hand_finger`, `off_hand_finger`, `ammo`. Source: `blackout/items/equipment/constants.py:12-28`
- `WieldLocation.label` derives the player-facing name from the value (`two_hands` gives "Two Hands"). No second table holds labels. Source: `blackout/items/equipment/constants.py:30-59`
- `SLOT_DISPLAY_ORDER` is the order for equipment screens: main hand, off hand, two hands, head, body, legs, feet, back, neck, the two fingers, ammo. Source: `blackout/items/equipment/constants.py:68-81`
- `SLOT_CONFLICTS`: `TWO_HANDS` clears `MAIN_HAND` and `OFF_HAND`. `MAIN_HAND` and `OFF_HAND` each clear `TWO_HANDS`. `AMMO` conflicts with nothing. `slots_displaced_by(use_slot)` is the one reader. Source: `blackout/items/equipment/constants.py:100-115`
- `MAX_INVENTORY_SLOTS = 32`. Equipped items do not count against it. Source: `blackout/items/equipment/constants.py:83-84, 117`

#### The equipment handler
- `EquipmentHandler.slots` is a dict `{WieldLocation: object or None}`. It is stored in one Attribute, `inventory_slots`, category `inventory`, on the character. Source: `blackout/items/equipment/handler.py:23, 31-49, 72-74`
- `_load` adds each enum member that the stored dict lacks, and saves. Thus a slot added to the enum reaches old characters. The default dict at lines 36-48 has no `AMMO` key, and the loop at lines 62-66 adds it. Source: `blackout/items/equipment/handler.py:36-48, 62-69`
- The handler holds object references, not ids, and has no repair pass. Source: `blackout/systems/interface/statefeed/inventory.py:565-567`
- An equipped item has `location = None`. It leaves the inventory grid, and it is not in the `contents` of the character or of the room. Source: `blackout/items/equipment/handler.py:357-375, 398-399`
- Only `Character` has the handler: `equipment = _handler_property(EquipmentHandler, "equipment")`. Source: `blackout/typeclasses/characters.py:136`
- An NPC has no equipment handler. Its combat numbers are on its NPC def. Source: `blackout/world/npc_database.py:130`

#### What runs on equip and unequip
- `equip(obj)` runs: `_check_requirements`, `_displaced_by`, `_check_inventory_room`, `_place`, `_save`, `_publish`, `_refresh_combat`. Source: `blackout/items/equipment/handler.py:377-412`
- `_check_requirements` reads `obj.inventory_use_slot`, then `obj.db.tool_type` against `WEAPON_SKILL_MAP` and `ARMOR_SKILL_MAP`, then `obj.db.req_level` against the skill of the wearer. An unregistered `tool_type` raises `EquipmentError`. Source: `blackout/items/equipment/handler.py:275-332`, `blackout/items/equipment/skill_requirements.py:36-83`
- `unequip(obj_or_slot)` and `remove(obj_or_slot)` each end with `_save`, `_publish`, `_refresh_combat`. `remove` does not return the item to the inventory. Source: `blackout/items/equipment/handler.py:415-460`
- `_publish` makes three calls: `feed.emit_inventory(self.obj)`, `feed.refresh_summary(self.obj)`, `feed.emit_combat_options(self.obj)`. Each one reaches the sessions of the owner only. Source: `blackout/items/equipment/handler.py:105-144`
- `_publish` lives in the handler, not in the commands, because the equipment EvMenu calls `equip()` with no command. Source: `blackout/items/equipment/handler.py:109-113`
- `_refresh_combat` calls `combat_handler._refresh_weapon()` when the character is in a fight. Source: `blackout/items/equipment/handler.py:147-168`
- No item-level hook exists. A search of `blackout/**/*.py` for `at_equip`, `at_unequip`, `at_wield`, `at_wear`, `on_equip`, `on_unequip` matched one test file only (`blackout/systems/interface/statefeed/tests/test_inventory.py`).
- Every caller of the three mutators: `blackout/commands/equipment_cmds.py:298` (`equip`, key `equip`, aliases `equipment` and `wear`, lines 244-245), `blackout/commands/equipment_cmds.py:379` (`unequip`, alias `remove`, lines 329-330), `blackout/systems/interface/menus/equipment_menu.py:159`, `blackout/systems/gameplay/combat/combat.py:1041` (the mid-fight `wield`), `blackout/commands/cleanup_cmds.py:116, 131`, `blackout/systems/devtools/actions.py:689`, `blackout/typeclasses/bank_nodes.py:231`, `blackout/systems/gameplay/banking/handler.py:309`, `blackout/systems/gameplay/combat/ammunition.py:147` (the last arrow of a stack).

#### Item typeclasses
- `EquippableItem.inventory_use_slot` reads the `use_slot` Attribute and gives a `WieldLocation` or `None`. Source: `blackout/typeclasses/items.py:15-35, 101-108`
- `ToolItem`, `WeaponItem`, `AmmunitionItem`, `ArmorItem` are empty subclasses. Each docstring says that every value comes from the `ItemDef`. None holds a look field. Source: `blackout/typeclasses/items.py:146-219`

#### What an `ItemDef` carries
- The `ItemDef` fields are: `key`, `name`, `typeclass`, `desc`, `value`, `weight`, `tradeable`, `stackable`, `use_slot`, `tool_type`, `gatherable_key`, `tier`, `req_level`, `tags`, `heal_amount`, `eat_delay_ticks`, `attack_delay_ticks`, `attack_speed`, `max_range`, `accepted_ammo`, `combat_stat_bonuses`, `combat_styles`, `default_combat_style`, `combat_rules`. No field names an asset key, a model, an attach point, or an appearance. Source: `blackout/world/item_database.py:48-135`
- `to_prototype` sets `prototype_key` to `self.key` and copies `tags`. `_get_attrs` is the one place where a def field becomes an object Attribute. Source: `blackout/world/item_database.py:138-214, 242-276`
- The statefeed reads the prototype tag of a spawned item as its asset key. Source: `blackout/systems/interface/statefeed/serializers.py:45-89, 174-177`
- `ITEM_DB` joins 17 def modules. Source: `blackout/world/item_database.py:332-357`
- The item families are tag categories: `weapon`, `armor`, `jewellery`, `crafting_material`, `crafting_tool`, `currency`, `corpse`, `food`. Source: `blackout/systems/interface/statefeed/constants.py:988-995`
- `ITEM_FAMILY_PRIORITY` resolves an item with several families, in this order: currency, corpse, food, crafting_material, jewellery, crafting_tool, armor, weapon. `ITEM_FAMILIES` derives from it. Source: `blackout/systems/interface/statefeed/constants.py:1013-1033`
- `_item_family` walks the priority tuple over the tag categories of the object and gives `generic` when none matches. Source: `blackout/systems/interface/statefeed/serializers.py:182-239`
- `tool_type` is a finer vocabulary than the family. Weapon values: `axe`, `shortsword`, `scimitar`, `spear`, `dagger`, `battleaxe`, `greatsword`, `bow`, `ammo`, `gadget`, `hammer`, `generic`. Armor values: `helmet`, `chainbody`, `platelegs`, `boots`, `square_shield`, `cape`. The statefeed does not send `tool_type`. Source: `blackout/items/equipment/skill_requirements.py:36-83`

#### Example item definitions
- Weapon, `rusty_scrap_shortsword`: `typeclass="typeclasses.items.WeaponItem"`, `use_slot=WieldLocation.MAIN_HAND`, `tool_type="shortsword"`, `tier=0`, `req_level=0`, `tags=[("rusty_scrap_shortsword", "weapon")]`, `attack_speed=4`, `combat_styles=_SHORTSWORD_COMBAT_STYLES`, `default_combat_style="irimi"`. Source: `blackout/world/item_defs/weapons.py:319-361`
- Armor, `rusty_scrap_chainbody`: `typeclass="typeclasses.items.ArmorItem"`, `use_slot=WieldLocation.BODY`, `tool_type="chainbody"`, `tags=[("rusty_scrap_chainbody", "armor")]`, defense bonuses only. Source: `blackout/world/item_defs/armor_body.py:26-65`
- Two families, `rusty_scrap_axe`: `typeclass="typeclasses.items.ToolItem"`, `use_slot=WieldLocation.MAIN_HAND`, `tool_type="axe"`, tags `(key, TOOL_TAG_CATEGORY)` and `(key, ITEM_FAMILY_WEAPON)`. The priority tuple resolves it to `crafting_tool`. Source: `blackout/world/item_defs/tools.py:67-137`
- Ammunition, `rusty_scrap_arrow`: `use_slot=WieldLocation.AMMO`, `stackable=True`, tags `(AMMO_FAMILY_ARROW, AMMO_FAMILY_TAG_CATEGORY)` and `(key, "crafting_material")`. Its family resolves to `crafting_material`. Source: `blackout/world/item_defs/ammunition.py:48-91`

#### Which slots have items today
- `MAIN_HAND`: daggers, shortswords, scimitars and battleaxes in three tiers, six gadgets, three axes, the hammer. Source: `blackout/world/item_defs/weapons.py:284, 328, 372, 460`, `blackout/world/item_defs/gadgets.py:105-210`, `blackout/world/item_defs/tools.py:101, 154, 207, 260`
- `TWO_HANDS`: spears, greatswords and shortbows in three tiers. Source: `blackout/world/item_defs/weapons.py:416, 504, 1102, 1154, 1206`
- `OFF_HAND`: three square shields. Source: `blackout/world/item_defs/armor_offhand.py:35, 82, 129`
- `HEAD`, `BODY`, `LEGS`, `FEET`, `BACK`: three items each (great helm, chainbody, platelegs, boots, hide cape). Source: `blackout/world/item_defs/armor_head.py:31`, `armor_body.py:35`, `armor_legs.py:31`, `armor_feet.py:35`, `armor_back.py:31`
- `NECK`: `glass_cannon_amulet`. Source: `blackout/world/item_defs/jewellery.py:21-36`
- `AMMO`: three arrows. Source: `blackout/world/item_defs/ammunition.py:57, 108, 159`

### Inferences
- **INFERENCE:** `EquipmentHandler._publish` is the one seam for a "gear changed" send, because all nine callers end there. The file states the same reason for the three sends that exist (`handler.py:109-113, 132-134`).
- **INFERENCE:** A reader that walks room contents cannot find worn items, because a worn item has `location = None`. A row for worn gear must come from `equipment.slots`.
- **INFERENCE:** The server holds two grains that a look can key on: the asset key (one per item) and the family (eight values). `tool_type` is a third grain (18 values), and no payload sends it today.

### Gaps
- No `ItemDef` in the searched def modules uses `MAIN_HAND_FINGER` or `OFF_HAND_FINGER`. I did not search `materials.py`, `currencies.py`, `corpses.py` or `food.py` for `use_slot`.
- I did not read `spray_can` in full (`blackout/world/item_defs/tools.py:280-293`). Its slot is unknown.
- The vault does not say whether an NPC must show gear. See section 8.

## 2. The statefeed: entity rows, channels, coalescing, the inventory payload, and stale marks

### Takeaway
An entity row names one asset key and one family, and nothing about worn gear. The owner gets worn gear on `char_items_list`. No payload tells an observer what another character wears, and no send goes to observers on equip or unequip.

### Cited Findings

#### `serialize_entity`: every field
- Always present: `id`, `name`, `kind`, `asset`, `family`, `interact`, `coords`. Source: `blackout/systems/interface/statefeed/serializers.py:809-821`
- `actions`: present only when the entity has more than one action. Each row is `{command, label}` plus `approach: False` on a self-approaching verb. Source: `serializers.py:446-463, 830-831`
- `spent`: present and `True` only on a gathering node that this observer stripped. Source: `serializers.py:837-838`
- `approach`: present and `False` only when the first action closes its own distance. Source: `serializers.py:844-845`
- `label` and `label_kind`: present together, only on an entity with a `world_label`. Source: `serializers.py:852-856`
- `facing`: present only on an entity that the tile sync stood up. The value is 0 to 3 quarter turns. Source: `serializers.py:681-720, 860-863`
- `hp` and `max_hp`: present only when the entity has a truthy `max_hp`. Source: `serializers.py:865-869`
- The row has no `desc` on purpose. Source: `serializers.py:803-804`
- `asset` is the one field that names a model. `family` is the fallback key of the same lookup. No field names a second model, a slot, or an item. Source: `serializers.py:766-768`

#### A player character row
- `_classify` gives `kind = "character"` and `asset = ASSET_KEY_CHARACTER` for an object whose `_content_types` holds `character`. Source: `serializers.py:169-172`
- `ASSET_KEY_CHARACTER` is `"player_character"`. Every player gets it. Source: `blackout/systems/interface/statefeed/constants.py:813-823`
- `family` is the kind for a non-item, so it is `"character"`. Source: `serializers.py:242-282`
- `interact` is the first row of `Character.extra_actions`: `profile #<dbref>`. The list is Profile, Skills, Records, then Attack when that character has PvP on. Source: `blackout/typeclasses/characters.py:155-221`, `blackout/commands/progression_cmds.py:103-113, 292-299, 361-368`
- `approach` is `False`, because `profile` is in `SELF_APPROACHING_VERBS`. Source: `constants.py:866-867`
- `hp` and `max_hp` are present. Thus an observer already gets the HP of another player.
- **CONFLICT:** The `_classify` docstring says that a character that declares `asset_key` overrides the shared key (`serializers.py:124-129`). The code reads `asset_key` only inside the `asset_kind` branch (`serializers.py:157-162`). `Character` declares no `asset_kind` (no match in `blackout/typeclasses/characters.py`).

#### An NPC row
- `kind = "npc"`. `asset` is the `asset_key` of the object when it has one, else its `npc_key`. Source: `serializers.py:142-149`
- `NpcDef.asset_key` names the model record, and `None` means the def key. Source: `blackout/world/npc_database.py:257, 289, 307-310`
- `family = "npc"`. `interact` is `attack #<dbref>` for a hostile NPC, or the `interact_verb` of the typeclass (`talk`, `trade`). Source: `constants.py:839-842, 885-889`, `blackout/typeclasses/npcs.py:324-325, 642-643`

#### Channels that carry entities
- `room_players` (whole list), `room_players_delta` (one batch for a move of the observer), `room_add_player` (one arrival), `room_remove_player` (one departure, by id). Source: `constants.py:22-36`, `blackout/systems/interface/statefeed/payloads.py:149-186, 254-273`
- `char_avatar` gives the observer its own `entity_id`, `asset`, `family`. The observer is not in its own `room_players` list. Source: `payloads.py:276-304`

#### When the server sends them
- A room arrival: `at_object_receive` sends `emit_room_info`, `emit_room_contents` and `emit_inventory` to the mover when it has a subscriber. Then it sends `emit_entity_arrived(self, moved_obj)` to the area. Source: `blackout/typeclasses/rooms.py:389-413`
- A room departure: `at_object_leave` sends `emit_entity_left`. Source: `blackout/typeclasses/rooms.py:443-450`
- A deleted object: `emit_entity_left`. Source: `blackout/typeclasses/objects.py:98`
- A respawn: `emit_entity_arrived`. Source: `blackout/systems/gameplay/spawning/respawn.py:335-347`
- A PvP flag change: `emit_entity_arrived(location, character)`. The docstring says that the client upserts by id, so a second add replaces the row. Source: `blackout/systems/gameplay/combat/pvp.py:48-93`
- A node that one player stripped: `refresh_room_contents`, which sends the whole list, forced. Source: `blackout/systems/gameplay/progression/skills/skill_defs/gathering/depletion.py:307-311`, `blackout/systems/interface/statefeed/events.py:1746-1781`
- A resync: `emit_room_contents(observer, force=True)`. Source: `blackout/systems/interface/statefeed/resync.py:28-45`
- `emit_room_contents` has four outcomes: the whole list, nothing, the whole list for a large change, or a delta. It compares entity ids only. Source: `events.py:1440-1548`
- A row that changes with the same id is not in a delta. The file says so for the spent node. Source: `events.py:1754-1756`
- `emit_entity_arrived` builds one row with no observer and sends it with `emit_to_area(rooms, payload, exclude=(entity,))`. Source: `events.py:1552-1564`
- The radius is `STATEFEED_ENTITY_RADIUS`, read in `_visible_rooms` only. Its value is 24. Source: `events.py:68-119`, `constants.py:552`
- **CONFLICT:** `godot/README.md:272` and `godot/world/entity_pool.gd:5` say that the radius is 10. `constants.py:552` says 24.
- `emit_avatar` runs on resync only. The docstring says: "When appearance becomes mutable, whatever sets it calls this, and nothing else here changes." Source: `events.py:506-554`, `resync.py:48-66`

#### How `buffer.py` coalesces
- Inside a tick, a channel in `COALESCABLE_CHANNELS` is held, and the newest payload for each `(observer id, channel)` goes out at `PHASE_FEED`. Outside a tick, a send goes at once. Source: `blackout/systems/interface/statefeed/buffer.py:95-124, 257-295, 418-488, 510-518`
- `COALESCABLE_CHANNELS` holds `char_avatar`, `char_vitals`, `char_status`, `char_summary`, `char_skills`, `char_combat`, `char_popup`, `char_chat`, `char_items_list`, `room_info`, `room_players`, `blackout_walk`. Source: `constants.py:650-663`
- `room_add_player`, `room_remove_player` and `room_players_delta` are not coalescable, because two of them compose and do not supersede. Source: `constants.py:636-649`
- `CHANNEL_MIN_INTERVAL_SECONDS` is an empty dict. No channel has a rate cap. Source: `constants.py:557-622`

#### The `refresh_*` and `drain_stale` pattern
- A `refresh_*` routine calls `_mark_stale_if_heard`, which checks for a subscriber and then calls `buffer.mark_stale(observer, builder, delay)`. Source: `events.py:272-290, 1665-1810`
- `mark_stale` keys on `(observer id, builder)`, so three marks give one build. Outside a tick it schedules `drain_stale` with `callLater(0)`. A `delay` schedules the mark itself. Source: `buffer.py:132-174, 298-352`
- `drain_stale` builds each marked snapshot, in up to `STALE_DRAIN_MAX_PASSES` (4) passes. `flush` calls it first, inside the tick. Source: `buffer.py:365-415, 462-466`, `constants.py:665-670`
- The builder is the emitter of the channel, for example `emit_summary`. Source: `buffer.py:54-55`
- Marked snapshots today: the dossier (`refresh_summary`), the roster (`refresh_skills`), the status (`refresh_status`), the room contents (`refresh_room_contents`), the pop-up (`refresh_popup`). Source: `events.py:1665-1810`

#### The emitters that run on equip and unequip
- `emit_inventory(owner)`: sends `char_items_list` at once, and marks the dossier and an open pop-up stale. Source: `events.py:994-1072`
- `refresh_summary(owner)`: marks the dossier stale. Source: `events.py:1665-1707`
- `emit_combat_options(owner)`: sends `char_combat`. Source: `events.py:782`, `handler.py:132-144`

#### What the owner gets about worn gear
- `CharItemsPayload` fields: `slots_total`, `slots_used`, `items`, `equipped`, `equip_slots`. It is a whole snapshot, never a delta. Source: `payloads.py:518-561`
- One item row: `id`, `slot`, `name`, `asset`, `family`, `quantity`, `stackable`, `equip_slot`, `actions`, and `detail` when a pop-up gives one. Source: `blackout/systems/interface/statefeed/inventory.py:322-344, 446-452`
- `equipped` has one row for each occupied slot, in `SLOT_DISPLAY_ORDER`. `slot` is the `WieldLocation` value. The actions are `Unequip`, `Deposit` at a bank, and `Inspect`. Source: `inventory.py:474-512`, `constants.py:1079-1080, 1250`
- `equip_slots` has one `{slot, label}` for every wield location, in display order, occupied or not. Source: `inventory.py:457-471`
- `build_payload` gives the payload, and `emit_inventory` sends it to the sessions of the observer only. Source: `inventory.py:532-607`, `events.py:1056-1072`

#### What an observer gets about the gear of another character
- Nothing. `serialize_entity` has no gear field (`serializers.py:809-871`). `char_items_list` and `char_avatar` go to the owner only (`events.py:554, 1072`). `EquipmentHandler._publish` sends nothing to the room or the area (`handler.py:140-144`).
- The dossier names the wielded weapon and a count of worn items for the owner. Source: `blackout/systems/interface/summary/panel_defs/readiness.py:58, 226`, `blackout/systems/interface/summary/panel_defs/holdings.py:134, 198`
- `profile` shows the dossier of any character as text in a menu. Source: `glossary.md:43`

#### Guards that a new entity field meets
- `test_every_key_a_real_entity_carries_is_in_the_synthetic_row` fails when `serialize_entity` sends a key that the synthetic worst-case row lacks. Source: `blackout/systems/interface/statefeed/tests/test_payload_size.py:233-246`
- `test_a_real_entity_is_not_larger_than_the_synthetic_one` fails when a real row is larger than the synthetic row. Source: `test_payload_size.py:221-231`
- The ceiling: 1,200 entities must fit two thirds of `CLIENT_INBOUND_BUFFER_BYTES` (2 MiB). The file records 845,336 bytes at four actions for each row. Source: `test_payload_size.py:56-93, 174-194`, `constants.py:766`
- `test_emit.py` refuses a payload field named `options`. Source: `blackout/systems/interface/statefeed/tests/test_emit.py:342-375`
- `test_freshness.py` holds the proof that a pane follows a fact. Source: `blackout/systems/interface/statefeed/tests/test_freshness.py:128-353`

#### Other payloads that name what a character does
- `blackout_combat` goes to the attacker, the target and the room for each swing. It carries `attacker_id`, `target_id`, `hit`, `damage`, `damage_type`, `attack_type`, `style`, `killed`, `max_hit`. Source: `payloads.py:592-629`, `events.py:200, 298-364`, `godot/README.md:2265-2267`
- `blackout_walk` goes to the walker only. Source: `constants.py:173-185`

### Inferences
- **INFERENCE:** A gear change of a character that does not move reaches no observer through the delta path, because the delta compares ids. The PvP flag has the same problem and solves it with `emit_entity_arrived` (`pvp.py:66-71`). That is the one precedent in the code for "the row of a standing character changed".
- **INFERENCE:** `room_add_player` is not coalescable. Thus `wear all` inside one command sends one message for each call, if the send uses that channel.
- **INFERENCE:** A gear field on the entity row costs bytes on the largest payload of the feed, for each player in view. A gear field on a separate channel does not. The file argues the same trade for `actions` and `label` (`serializers.py:823-829, 847-851`).
- **INFERENCE:** The observer gets its own look from `char_avatar`, not from an entity row. A gear field for other players does not reach the avatar of the observer unless `char_avatar` or `char_items_list` also feeds it.

### Gaps
- I did not read `_broadcast` (`events.py:200`) line by line. The audience of `blackout_combat` comes from `godot/README.md:2265-2267`.
- I did not read `emit_combat_options` (`events.py:782-838`) in full.
- I did not check whether a death, a drop on death, or a logout changes `equipment.slots` by a path outside the three mutators.

## 3. Constants export: from `constants.py` to `blackout_constants.gd`, and the tests that guard it

### Takeaway
`clientexport.py` renders the server-owned names as GDScript text, and `scripts/export_client_constants.py` writes the file. One test fails on a stale file, and a set of guard tests reads the client tables that cannot be generated. No slot name is exported today.

### Cited Findings
- `clientexport.py` is pure: it returns a string and writes no file. Source: `blackout/systems/interface/statefeed/clientexport.py:41-44`
- The rule for what belongs in the export: Python owns what is true, and the client owns the look. Colours, mesh shapes and the model registry are not generated. Source: `clientexport.py:30-39`
- Export tables: `_CHANNEL_EXPORTS` (lines 112-138), `_KIND_EXPORTS` (151-161), `_LABEL_KIND_EXPORTS` (176-180), `_ITEM_FAMILY_EXPORTS` (192-201), `_TILE_KIND_EXPORTS` (210-215), `_MOMENT_EXPORTS` (221-223), `_SCALAR_EXPORTS` (230 onward), then the clock and tile grid tables. Source: `clientexport.py:112-453`
- The output path table is `_OUTPUT_PATHS`: language `gd` goes to `godot/autoload/blackout_constants.gd`. It lives in `clientexport.py` because a test cannot import `blackout/scripts/`. Source: `clientexport.py:455-479`
- `render(language)`, `languages()` and `output_paths()` are the public routines. Source: `clientexport.py:716, 759, 784`
- The writer is `blackout/scripts/export_client_constants.py`. `--check` writes nothing and exits non-zero. Source: `CLAUDE.md:460-471`
- `FAMILY_CORPSE` is one constant for `ASSET_KIND_CORPSE` and `ITEM_FAMILY_CORPSE`. Source: `clientexport.py:145-150`
- The generated file holds `FAMILY_CHARACTER` (line 45), the item family constants (54-61), `TICK_SECONDS := 0.6` (105), `ASSET_KEY_CHARACTER := "player_character"` (282), `ENTITY_FACING_KEY` (289), `CLIENT_INBOUND_BUFFER_BYTES` (300), `ITEM_FAMILIES` (312). Source: `godot/autoload/blackout_constants.gd:45-312`
- The generated file holds no `WieldLocation` value and no slot constant. A search for `SLOT` and `WIELD` in it gave no match. The slot names reach the client as data, in `equip_slots`. Source: `godot/autoload/blackout_constants.gd`, `inventory.py:457-471`
- `GeneratedConstantsTests.test_committed_files_match_a_fresh_render` compares the committed file with a fresh render. Source: `blackout/systems/interface/statefeed/tests/test_client_constants.py:869-914`
- `MomentExportTests` holds the moment exports equal to `MOMENTS`. Source: `test_client_constants.py:860-866`
- Guard tests for client tables that mix a server fact with a look: skill categories (418), rarity palette (479), area looks (525), floor palette (599), wall palette (626), family models (655), the doll layout (724), and a vacuity guard (830). Source: `test_client_constants.py:418-857`
- `ClientFamilyModelTests.test_every_family_model_is_one_the_build_can_produce` fails when `FamilyShapes.MODELS` names an asset key with no model record. Source: `test_client_constants.py:700-721`
- `ClientDollLayoutTests` fails when `DollLayout.ROWS` names a slot that no `WieldLocation` has, or places one slot two times. A slot with no square is allowed. Source: `test_client_constants.py:724-827`

### Inferences
- **INFERENCE:** A client table keyed by slot name (as `DollLayout.ROWS` is) has typed string keys today. It is guarded from Python by path, not generated.
- **INFERENCE:** A new channel needs a row in `_CHANNEL_EXPORTS`, an entry in `SUBSCRIBABLE_CHANNELS`, and a run of the export script. `godot/README.md:2333-2337` lists the same three edits for a moment.

### Gaps
- I did not read `blackout/scripts/export_client_constants.py`. CLAUDE.md marks that directory import-unsafe, and its role comes from `CLAUDE.md:460-471` and `clientexport.py:468-479`.
- I did not read the helper functions of `test_client_constants.py` (lines 1-417) that parse the GDScript tables.

## 4. The Godot client: who draws a figure, how a model loads, what animation exists, how a figure moves, and how the inventory pane draws an item

### Takeaway
`WorldView` draws the avatar of the observer, and `EntityPool` draws every other figure. Both ask `MeshResolver.resolve_entity(asset, family)` for one node. The client has no `AnimationPlayer`, no `AnimationTree` and no `BoneAttachment3D`. A walk is a slide of a static node.

### Cited Findings

#### Who draws what
- `WorldView` owns the `Marker` (the true tile), the `Avatar` root (the node that slides), the `Entities` pool, and the camera. Source: `godot/world/world_view.gd:77-97`, `godot/README.md:569-575`
- `WorldView._redraw_avatar` frees the old avatar node, calls `_meshes.resolve_entity(asset, family)`, sets the scale to `AVATAR_SCALE`, lifts the node by its measured bottom, sets the yaw, and adds it under `_avatar_root`. Source: `godot/world/world_view.gd:380-409`
- `AVATAR_SCALE` is `EntityPool.ENTITY_SCALE`, which is `1.0`: one figure fills its tile. Source: `godot/world/world_view.gd:63`, `godot/world/entity_pool.gd:68-79`
- `_redraw_avatar` runs on every `CharState.changed`. `CharState.ingest` emits `changed` for `char_avatar`, `char_vitals` and `char_status`. Thus the avatar node is freed and built again on each HP message. Source: `godot/world/world_view.gd:368-371`, `godot/world/char_state.gd:63-84`
- `_redraw_avatar` also runs when art lands, but only when `_char.asset == asset_key`. It does not ask `MeshResolver.redraws_for`. Source: `godot/world/world_view.gd:457-461`
- `CharState` keeps `entity_id`, `asset`, `family` from `char_avatar`. Source: `godot/world/char_state.gd:33-43, 65-68`
- `EntityPool` holds one row for each id, and builds one node for each row with a place. Source: `godot/world/entity_pool.gd:342-403, 763-817`
- `EntityPool._build` calls `_resolver.resolve_entity(asset, family)`, sets `ENTITY_SCALE`, and sets `rotation.y` only when the row has `facing`. Source: `godot/world/entity_pool.gd:994-1006`
- `EntityPool._look_of` lists the fields that decide the look of a node: `asset`, `family`, `label`, `label_kind`, `facing`. A row that arrives with the same look keeps its node. The comment says: "A new field that either one reads goes here too, or a changed row keeps its old node." Source: `godot/world/entity_pool.gd:973-985`
- `_prune` frees the node of an entity whose look changed, and `_sync` builds it again. A rebuild for a new look keeps the `StepAnimator` and does not tint in again. The comment names "new gear or new art". Source: `godot/world/entity_pool.gd:787-795, 836-847`
- `test_entity_pool.gd` proves it: `_a_changed_look_builds_the_node_again` and `_a_changed_look_does_not_rise_again`. Source: `godot/tests/test_entity_pool.gd:556, 653`
- `EntityRoster` is the model of the four entity channels. The console feeds it, and `WorldView.bind_entities` forwards each signal to the pool. Source: `godot/world/entity_roster.gd:1-70`, `godot/world/world_view.gd:469-474`
- An `add` for a known id replaces the row (`_upsert`). Source: `godot/world/entity_pool.gd:371-384`

#### How an entity maps to a model
- The mesh ladder: the model of the asset key, else the model of the family, else the procedural shape of the family, else a generic block. `MeshResolver` is the one owner of the order. Source: `godot/world/meshes/mesh_resolver.gd:3-24, 150-168`, `godot/README.md:164-180`
- `resolve_entity` never gives null. `resolve_scenery` gives art or null. Source: `godot/world/meshes/mesh_resolver.gd:143-178`
- `_art_for` gives a copy of a cached model, or starts a fetch and gives null. Source: `godot/world/meshes/mesh_resolver.gd:285-307`
- `FamilyShapes.MODELS` (tier 2) has two rows: `corpse` gives `corpse_skeleton`, and `food` gives `food_meat`. No row exists for `weapon` or `armor`. Source: `godot/world/meshes/family_shapes.gd:270-287`
- `FamilyShapes.SHAPES` (tier 3) has a part list for `weapon` (a blade, a guard, a grip), `armor` (an open cylinder and a torus), `jewellery`, `crafting_material`, `crafting_tool`, `currency`, `npc`, `character`, `station`, `gatherable`, `sign`. Source: `godot/world/meshes/family_shapes.gd:98-230`
- The `character` and `npc` shapes are one figure of a sphere and two cylinders, in two colours. Source: `godot/world/meshes/family_shapes.gd:169-170, 296-305`
- The keys of both tables are generated constants. Source: `godot/world/meshes/family_shapes.gd:65-72`
- `redraws_for(asset, family, arrived_key)` says whether arrived art changes an entity. Source: `godot/world/meshes/mesh_resolver.gd:189-208`

#### How a `.glb` loads at runtime
- `ModelRegistry` holds `asset_key -> "family/asset_key.glb"` from `manifest.json`. `MODEL_ROOT` is `/static/webclient/models/`. Source: `godot/world/model_registry.gd:44-52, 102-138`
- `ModelLoader.fetch_manifest` gets the manifest with an `HTTPRequest`. `request(asset_key)` gets one file for each URL, and several keys can wait on one URL. Source: `godot/world/meshes/model_loader.gd:273-339, 408-453`
- Caches: `_prototypes` (asset key to a built node, never handed out), `_bodies` (URL to bytes), `_waiting` (URL to keys), `_in_flight`, `_failed` (a failed key stays failed). Source: `godot/world/meshes/model_loader.gd:115-143`
- `_build` reads the bytes with `GLTFDocument.append_from_buffer` and `generate_scene`, puts the scene under a wrapper `Node3D`, normalises it, orients it, and stamps the presentation scale as metadata. Source: `godot/world/meshes/model_loader.gd:483-533`
- `_normalise` scales the scene so that its longest axis is one unit, and centres it on the origin. Source: `godot/world/meshes/model_loader.gd:598-610`
- `_orient` applies `ModelRegistry.PRESENTATION`: `scale`, `rotation`, `offset`. Source: `godot/world/meshes/model_loader.gd:613-635`, `godot/world/model_registry.gd:54-100, 173-218`
- `PRESENTATION` is keyed by asset key, and an alias falls back to the entry of its file key. It holds nine entries today, none for a melee weapon, an armor item, or `player_character`. One entry scales `heavy_machine_gun_clip`. Source: `godot/world/model_registry.gd:57-100, 205-218`
- `cached(asset_key)` duplicates the prototype and gives each copy its own materials, made glow-ready. The mesh and the textures stay shared. Source: `godot/world/meshes/model_loader.gd:210-263`
- Settings: `TIMEOUT_SECONDS := 20.0`, `BODY_CHUNK_BYTES := 4 MiB`, `RETRIES := 2`. The largest served model was 1.3 MiB on 10/05/2026. Source: `godot/world/meshes/model_loader.gd:67-85`
- The console builds one `MeshResolver` for the whole client, with the origin from `ServerEndpoint.asset_origin`. Source: `godot/scenes/console.gd:309-321, 352`
- `prefetch_all` asks for every manifest key when the loading veil goes up. `ShaderWarmer` draws each arrival for `HOLD_FRAMES := 3` frames out of sight. The veil waits for both. Source: `godot/world/meshes/mesh_resolver.gd:244-260, 310-346`, `godot/world/meshes/shader_warmer.gd:45-68`, `godot/scenes/console.gd:436-440`
- The measured cost on a Chromium WebGL 2 export on 09/13/2026: 13.5 s of frozen frames for one draw of each of twenty models. Source: `godot/README.md:215-221`
- A compiled shader lives as long as a material of its exact variant. The prototypes keep the warmed shaders alive. Source: `godot/README.md:232-237`, `godot/world/meshes/model_loader.gd:566-595`
- The client renders through Compatibility (OpenGL 3.3, WebGL 2.0). Source: `godot/README.md:16-25`
- The terrain editor reads the same tree from disk through `MeshResolver.from_directory`. Source: `godot/world/meshes/mesh_resolver.gd:124-133`, `godot/world/meshes/model_loader.gd:342-377`

#### Skeleton and animation support
- A search of every `.gd` and `.tscn` file under `godot/` for `AnimationPlayer`, `AnimationTree`, `BoneAttachment3D` and `AnimationLibrary` gave no match.
- `Skeleton3D` appears in one routine, `ModelLoader._skeleton_bounds`, which reads the rest pose of each bone to measure a rigged model. Source: `godot/world/meshes/model_loader.gd:835-873`
- The comment there says: "nothing here is animated". Source: `godot/world/meshes/model_loader.gd:838-839`
- `bounds_of` merges the skeleton box into the mesh box, because the box of a skinned mesh is its bind pose. Source: `godot/world/meshes/model_loader.gd:657-695`, `godot/README.md:318-330`
- `_instance_bounds` reads a static mesh vertex by vertex, and a skinned mesh (`instance.skin != null`) by its box. Source: `godot/world/meshes/model_loader.gd:773-824`
- The comment and the README both say that the proper fix is to bake the skinning out in the model pipeline, because the models carry skinning attributes for zero animations. Source: `godot/world/meshes/model_loader.gd:686-689`, `godot/README.md:326-330`
- The build keeps animations in a served file unless the record says `animations = false`. Its comment says: "The client plays no animation today." Source: `blackout/assets/pipeline/build_model.mjs:212-234`
- The only animation in the item pane is a slow spin of each item node about Y. Source: `godot/scenes/inventory/item_stage.gd:50-52, 183-193`

#### How a figure moves and turns
- The server moves a character in whole tiles on each tick. `StepAnimator` slides the drawn position to the new target. One animator belongs to each figure. Source: `godot/README.md:458-468`, `godot/world/step_animator.gd:1-62`
- `WALK_TICKS := 1.2` (a crossing takes 0.72 s at a 0.6 s tick). `SNAP_STEPS := 3.0` (a longer move snaps). Source: `godot/world/step_animator.gd:73, 86`, `godot/README.md:481-518`
- The avatar: `_place_marker` moves the marker, calls `_turn_avatar`, and aims the animator. `_process` advances the animator and turns the drawn yaw at `TURN_SPEED := 12.0` radians a second. Source: `godot/world/world_view.gd:137, 270-293, 993-1035`
- `yaw_towards(from, to, keep)` is `atan2(dx, -dy)`. It puts +Z along the step, and +Z is the way that a served character and the procedural figure face. Source: `godot/world/world_view.gd:1049-1080`, `godot/README.md:295-299`
- `WorldView` keeps the yaw in `_avatar_yaw` and `_avatar_yaw_drawn`, because `_redraw_avatar` frees the node. Source: `godot/world/world_view.gd:139-151, 401-408`
- Other figures: `EntityPool._process` sets `node.position` from each animator. The pool writes no yaw from movement. A node turns only by the `facing` of its row. Source: `godot/world/entity_pool.gd:637-654, 994-1006`
- `TerrainView.model_yaw(quarter_turns)` is `PI - quarter_turns * PI * 0.5`. Source: `godot/world/terrain/terrain_view.gd:373-374`
- The setting "figures slide between tiles" turns the animators off for the avatar and the pool together. Source: `godot/world/world_view.gd:347-364`

#### Effects that walk the node of a figure
- The hit flash and the hover glow write to every `StandardMaterial3D` under the node of the entity. Source: `godot/world/entity_pool.gd:517-554, 581-632`
- The tint-in of a new figure tweens the albedo of every material under the node for `FADE_IN_SECONDS := 1.0`. Source: `godot/world/entity_pool.gd:90-98, 870-895`
- `_rest_offset` lifts a node by the bottom of `ModelLoader.bounds_of(node)`. The pool measures it before it attaches the label, because a child counts in the bounds. Source: `godot/world/entity_pool.gd:926-949, 1103-1118`
- A hitsplat asks `_figure_of(entity_id)` for the node of a figure. Source: `godot/world/world_view.gd:497-505`
- `pick` chooses the entity nearest the cursor in screen space. The scene has no collision body. Source: `godot/world/entity_pool.gd:471-496`

#### How the inventory pane and the paper doll draw an item
- `ItemStage` is one `SubViewport` with its own `World3D`, one orthographic camera, and a grid of items. Each cell shows its rectangle through an `AtlasTexture`. Source: `godot/scenes/inventory/item_stage.gd:1-29, 73-118, 149-163`
- `ItemStage.place(index, asset, family, resolver)` calls `resolver.resolve_entity(asset, family)`, divides out the presentation scale, sets `ITEM_SCALE := 0.84`, and tilts the item by `ITEM_TILT_X := -0.34`. Source: `godot/scenes/inventory/item_stage.gd:42-48, 130-146`
- `EquipmentView` is the paper doll. `_dress` places each worn row on its own stage and shows the texture in the cell. Source: `godot/scenes/equipment/equipment_view.gd:59-60, 111-112, 321-331`
- `DollLayout.ROWS` places eleven squares and one wide row for `two_hands`, which shows only while that slot is occupied. Source: `godot/world/doll_layout.gd:54-78`, `godot/README.md:920-946`
- `InventoryState` keeps `equipped` as `WieldLocation value -> row` and `equip_frames` as the frame list. Each row keeps `asset`, `family`, `equip_slot`. Source: `godot/world/inventory_state.gd:57-61, 72-85, 178-209`
- A left click on a worn square sends the first action of the row, `unequip <slot>`. Source: `godot/README.md:948-956`

#### Tests on this path
- `test_entity_pool.gd`, `test_entity_roster.gd`, `test_world_view.gd`, `test_step_animator.gd`, `test_model_loader.gd`, `test_model_registry.gd`, `test_family_shapes.gd`, `test_shader_warmer.gd`, `test_mesh_glow.gd`, `test_char_state.gd`, `test_inventory_state.gd`, `test_inventory_view.gd`, `test_equipment_view.gd`, `test_session_readiness.gd`, `smoke_model_load.gd`. Source: `godot/tests/`
- The README counts seventy-one headless tests, and three need a running Evennia. Source: `godot/README.md:1598-1604`

### Inferences
- **INFERENCE:** The avatar node does not survive an HP change, and the node of another figure does not survive a look change or late art. Anything that hangs on those nodes needs a build step inside `_redraw_avatar` and `EntityPool._node_for_entity`, or a state kept beside the node, as the animators and the yaw are.
- **INFERENCE:** The observer and the other figures use two code paths for one job (`WorldView._redraw_avatar` and `EntityPool._build`). A gear look needs both, or one shared builder.
- **INFERENCE:** `_normalise` discards the real size of each model. A sword and a body both come out one unit long. A sword in a hand needs a size relative to the body, and `PRESENTATION.scale` is the only field that holds a relative size today.
- **INFERENCE:** `GLTFDocument.generate_scene` makes a `Skeleton3D` for a file with a skin, and the loader keeps that node in the prototype. The client code never looks for it, apart from the bounds measurement. I did not confirm what `generate_scene` makes for a file with animations.
- **INFERENCE:** Each new served model adds one fetch and one shader warm behind the loading veil, because `prefetch_all` asks for every manifest key.
- **INFERENCE:** Other players and NPCs face one fixed way while they walk. Only the avatar of the observer turns to its step.
- **INFERENCE:** A new look field on the entity row needs an entry in `EntityPool._look_of`, by the comment at `entity_pool.gd:975-977`.

### Gaps
- I did not read `godot/world/meshes/mesh_builder.gd`, `mesh_palette.gd`, `mesh_glow.gd` or `shader_warmer.gd` in full.
- I did not read `godot/scenes/world.tscn`, so the node tree comes from the `@onready` paths in `world_view.gd:75-101`.
- I did not confirm whether a skinned mesh needs a second shader variant in the warmer. `shader_warmer.gd:29-30` says only that instanced drawing is its own variant.
- **CONFLICT:** `godot/README.md:55` says that a left click on a player does nothing. `blackout/typeclasses/characters.py:155-221` puts `profile` first, so `interact` is not empty.

## 5. The player model: record, source, license, format, rig and animations

### Takeaway
Every player draws one model, `player_character`, built from an Old School RuneScape CreatorsKit export that passes the license gate by exception only. The text form of the source holds no skin and an empty animation list.

### Cited Findings
- The asset key is `player_character` for every player. Source: `blackout/systems/interface/statefeed/constants.py:813-823`
- The model record is two lines: `source = "osrs_player_model"`, `file = "OSRS_player_model_test_blender.glb"`. It has no `[fix]`, no `[output]`, no alias. Source: `blackout/assets/models/characters/player_character.toml:1-2`
- The source record: title "OSRS player model (test export)", author "Jagex", site `osrs-creatorskit`, `license = "LicenseRef-Unconfirmed"`, retrieved 2026-09-13. Source: `blackout/assets/sources/osrs_player_model/source.toml:1-7`
- The exception text: "A CreatorsKit export out of the Old School RuneScape client, so the art is almost certainly Jagex's. No grant exists. Allowed as a placeholder by Nick on 09/18/2026. Replace it before a public release." Source: `blackout/assets/sources/osrs_player_model/source.toml:6`
- The source holds two files: `OSRS_player_model_test.gltf` (the CreatorsKit export, 111.4 KB) and `OSRS_player_model_test_blender.glb` (the same model after a Blender round trip, 51.0 KB). The record reads the `.glb`. Source: `blackout/assets/sources/osrs_player_model/source.toml:8-12`, and the file listing of 10/11/2026
- The served file is `blackout/web/static/webclient/models/characters/player_character.glb`, 49.5 KB. Source: `blackout/web/static/webclient/models/manifest.json:33`, and the file listing of 10/11/2026
- The credits mark it "License not confirmed", `confirmed: false`. Source: `blackout/web/static/webclient/models/credits.json:99-109`
- A text search of the `.gltf` found: `"generator":"CreatorsKit"`, `"animations":[]` (an empty list), one `"targets"`, one `"weights"`, `COLOR_0`, and a material named `vertexColors`. It found no `"skins"`, no `"JOINTS_0"`, no `"WEIGHTS_0"`, no `"images"`, no `"textures"`. Source: `blackout/assets/sources/osrs_player_model/OSRS_player_model_test.gltf:1`
- The placeholder holds one arm forward at chest height. Normalised, it measures 1.0 tall and 0.667 deep (measured 09/18/2026). Source: `godot/tests/smoke_model_load.gd:314-318`
- The `characters` budget is 512 px textures, 3 MiB, 20,000 triangles. The comment calls the byte budget a regression guard. Source: `blackout/assets/pipeline/budgets.py:98-128`
- The model before it was a Quaternius base character (CC0-1.0): a T-pose, 8,483 vertices, `skins: 1, animations: 0`, with unused skinning attributes. Its source is still in the repo, and its record says "No model record uses it now." Source: `blackout/assets/pipeline/budgets.py:104-119`, `blackout/assets/sources/quaternius_universal_base_characters/source.toml:1-7`
- The pipeline README says to replace the OSRS player character and the shopkeeper robot before a public release. Source: `blackout/assets/README.md:125-128`
- **CONFLICT:** `godot/README.md:332-337` describes the character as a T-pose that measures 1.859 wide and 1.820 tall. Those are the numbers of the Quaternius model (`godot/tests/smoke_model_load.gd:298-300`). The served model is the OSRS placeholder.
- **CONFLICT:** `godot/tests/smoke_model_load.gd:25-27` calls `player_character` "The RIGGED one. Carries a skeleton". The text `.gltf` of the current source holds no skin.

### Inferences
- **INFERENCE:** The served player model has no rig and no animation. The evidence is the text `.gltf` (no `skins`, empty `animations`) and the size of the served file (49.5 KB). The record reads the Blender `.glb`, which I did not open, so this is not confirmed.
- **INFERENCE:** The model draws from vertex colours and has no texture, because the `.gltf` has `COLOR_0` and no `images`.
- **INFERENCE:** The one `"targets"` and one `"weights"` in the `.gltf` suggest a morph target entry. I did not read the values.
- **INFERENCE:** A player figure that shows gear on a body needs a new player model with a rig, or a rig added to this one. The current file gives no bone to attach to. The license status of the current model is a second reason, and the source record states it.

### Gaps
- I did not open `OSRS_player_model_test_blender.glb` or the served `player_character.glb`, because they are binary files. Their skin count, animation count, triangle count and node names are unknown.
- The build prints `skins` and `animations` for each model (`blackout/assets/pipeline/build_model.mjs:365-373`), but `build.lock.json` keeps only two hashes for each key (`blackout/assets/build.lock.json:66-69`). No file records those counts.
- No file says which rigged model will replace the placeholder.

## 6. The model pipeline: record fields, what the build writes, what the check tests, and what a record lacks for equipment

### Takeaway
A model record holds a source, a file, aliases, one node name, a texture, a fix, and output limits. It has no field for an attach point, an offset, or hidden body regions, and the loader refuses an unknown field.

### Cited Findings

#### The record
- The file name is the asset key, and the directory is the family: `assets/models/<family>/<asset_key>.toml`. Source: `blackout/assets/pipeline/records.py:5-12, 271-273`
- Top-level fields: `source`, `file`, `aliases`, `node`, `texture`, `fix`, `output`. `[texture]` holds `image`, `roughness`. `[fix]` holds `rotate`, `opaque`, `filter`. `[output]` holds `max_texture_edge`, `texture_format`, `animations`. Source: `blackout/assets/pipeline/records.py:73-113`
- An unknown field in any table raises `RecordError`. The reason given: a typo such as `rotation` for `rotate` must fail. Source: `blackout/assets/pipeline/records.py:118-142`
- `aliases`: more asset keys that draw the same file. The build writes one file, and the manifest points each alias at it. Source: `blackout/assets/pipeline/records.py:33-36`, `blackout/assets/README.md:155-157`
- Two records cannot claim one asset key, as a name or as an alias. Source: `blackout/assets/pipeline/records.py:335-368`
- `[fix] rotate` is baked as a parent node named `blackout_fix`, not as a change to the vertices, "so a skinned model keeps working". Source: `blackout/assets/pipeline/build_model.mjs:48-51, 160-177`
- `[output] animations` defaults to `True`. `false` drops every animation, and the model keeps its rest pose. Source: `blackout/assets/pipeline/records.py:98, 184-219`, `blackout/assets/pipeline/build_model.mjs:212-234`
- One record uses it: `atum_musa`, whose source holds about 130 animations (22 MB of keyframes). Source: `blackout/assets/models/npcs/atum_musa.toml:10-13`
- The rule that separates a fix from a display choice: a fix corrects the export, and a display choice stays in `ModelRegistry.PRESENTATION`. Source: `blackout/assets/pipeline/records.py:38-42`, `blackout/assets/README.md:165-168`
- A model must face +Z with +Y up. Source: `blackout/assets/README.md:170-173`

#### What the build does and writes
- Steps: ingest (Blender or `picocad.py`, only for a source that is not glTF), record and optimize (glTF Transform), validate (Khronos glTF Validator), budget. Source: `blackout/assets/README.md:175-182`
- The Node half runs, in order: `metalRough`, `keepOnlyNode`, `attachTexture`, `applyFix`, `dropAnimations`, `dropBlackEmission`, `prune({keepAttributes: false, keepLeaves: false})`, `dedup`, `weld`, `unpartition`, `encodeTextures`, `dropUnreadableExtensions`. Source: `blackout/assets/pipeline/build_model.mjs:378-427`
- The build writes the served `.glb`, `manifest.json`, `credits.json`, `CREDITS.md`, and `assets/build.lock.json`. The same inputs give the same bytes. Source: `blackout/assets/README.md:184-186`
- `manifest.json` is a flat map of asset key to relative path. It has 43 keys today. Source: `blackout/web/static/webclient/models/manifest.json:1-44`
- A test holds the manifest to paths only: `test_it_carries_paths_only_and_no_presentation`. Source: `blackout/systems/interface/statefeed/tests/test_model_pipeline.py:189-200`
- OBJ carries no skinning and no animation. Source: `docs/old/2026-09-18-DESIGN-0010-model-pipeline.md:51`

#### Budgets
- `items`: 512 px, 1 MiB, 5,000 triangles. `characters`: 512 px, 3 MiB, 20,000 triangles. `npcs`: 512 px, 2 MiB, 40,000 triangles. Source: `blackout/assets/pipeline/budgets.py:123-151`
- An unlisted family gets the default: 256 px, 768 KiB, 5,000 triangles. Source: `blackout/assets/pipeline/budgets.py:81-88, 246-274`

#### The license gate
- Allowed: `CC0-1.0`, `CC-BY-3.0`, `CC-BY-4.0`, `LicenseRef-Blackout-Owned`, `LicenseRef-Purchased`. The last one is `local_only`: its source must be a local source, and no exception waives that. Source: `blackout/assets/pipeline/licenses.py:66-102`, `blackout/assets/README.md:87-123`
- Refused: NC, ND, SA, "Sketchfab Standard", "Editorial", an empty field. Source: `blackout/assets/pipeline/licenses.py:20-27`
- An `exception` in the source record waives the gate. The check prints each one on every run, and the credits box shows "License not confirmed". Source: `blackout/assets/pipeline/licenses.py:14-18, 104-109`, `blackout/assets/README.md:125-128`
- Three source records carry an exception today: `osrs_player_model`, `itch_modosa_robot` (the shopkeeper), `machine_gun` (the gun and its clip). Source: `blackout/assets/sources/osrs_player_model/source.toml:6`, `blackout/assets/sources/itch_modosa_robot/source.toml:6`, `blackout/assets/sources/machine_gun/source.toml:6`
- **CONFLICT:** `blackout/assets/README.md:127` and `CLAUDE.md:899-901` name two exceptions, the OSRS player character and the shopkeeper robot. The `machine_gun` source record carries a third.

#### The runtime loader limits
- `GODOT_RUNTIME_EXTENSIONS` lists the ten glTF extensions that the Godot `GLTFDocument` reads at runtime. Draco, meshopt and mesh quantization are not on it. Source: `blackout/assets/pipeline/glb.py:26-42`
- The build removes an extension that is not on the list when the file does not require it, and stops when the file requires it. Source: `blackout/assets/README.md:188-192`

#### What `python -m assets.pipeline check` tests
- It writes nothing, needs no Node and no Blender, and runs inside the test suite. Source: `blackout/assets/README.md:203-210`, `blackout/systems/interface/statefeed/tests/test_model_pipeline.py:63-83`
- It fails on: a record or source that does not load, a missing file, a failed license gate, a file hash that does not match, a local source with no `.gitignore` from the seal, a served model that is stale, over budget, not from the build, or uses an extension outside the list, a `.glb` that no record builds, and a stale `manifest.json`, `credits.json` or `CREDITS.md`. Source: `blackout/assets/README.md:210-218`, `blackout/assets/pipeline/check.py:91-345`
- It warns on: each license exception, each source that no record uses, each local source whose files are not on the machine. Source: `blackout/assets/README.md:220-221`

#### What a record lacks for an equipment model
- No field names an attach point, a bone, a socket, a hand, or a slot. Source: `blackout/assets/pipeline/records.py:108-113`
- No field holds an offset or a scale. `PRESENTATION` on the client holds `rotation`, `scale`, `offset`, keyed by asset key. Source: `godot/world/model_registry.gd:54-100`
- No field marks body regions to hide. No search hit for such a field exists in `blackout/assets/pipeline/` or `godot/world/`.
- The manifest cannot carry such data today, by the test at `test_model_pipeline.py:189-200`.

### Inferences
- **INFERENCE:** A new record field needs an edit of `_TOP_FIELDS` (or a new table set) in `records.py`, a reader, and a test, because the loader refuses unknown fields.
- **INFERENCE:** By the stated rule, an attach offset is a display choice, so it belongs to the client. A grip that sits at the wrong point of an exported mesh is an export fault, so it can be a fix. The files do not decide this case.
- **INFERENCE:** `prune({keepAttributes: false})` removes vertex attributes that nothing uses. I did not confirm its effect on `JOINTS_0` and `WEIGHTS_0` of a skinned model.
- **INFERENCE:** A worn model in a new family directory, for example `equipment/`, gets the default budget until `FAMILY_BUDGETS` has a row for it.

### Gaps
- I did not read `build.py`, `sources.py`, `outputs.py`, `paths.py`, `blender.py`, `blender_ingest.py` or `fetch.py`.
- I did not confirm whether the Blender ingest keeps a rig and animations of an FBX source. `corpse_skeleton` builds from `skeleton.fbx` (`blackout/assets/models/npcs/corpse_skeleton.toml:1-2`).
- No file states a triangle or byte target for a worn item.

## 7. Existing item models: families, record counts, and which weapons and armor have a model

### Takeaway
The repo has 22 model records in six families. One weapon has a model of its own, two bows and two arrows share a machine gun and its clip, and no armor item has a model.

### Cited Findings
- Record count by family directory: `characters` 1, `gathering_nodes` 3, `items` 8, `npcs` 6, `tiles` 2, `world_objects` 2. Total 22. Source: `blackout/assets/models/` (file listing of 10/11/2026)
- `items` records: `rusty_scrap_shortsword`, `heavy_machine_gun`, `heavy_machine_gun_clip`, `moderator_egg`, `food_meat`, `mutant_raider_cured_chuck`, `mutant_raider_cured_meat_sandwich`, `mutant_raider_steak`. Source: `blackout/assets/models/items/`
- `npcs` records: `atum_musa`, `corpse_skeleton`, `floating_eye`, `lone_android`, `mutant_raider`, `shopkeeper`. Source: `blackout/assets/models/npcs/`
- `rusty_scrap_shortsword` has its own record. Source `sketchfab_rusty_sword`, CC-BY-4.0. `[fix] rotate = [90, 0, 0]` puts the tip up and the guard down. Served size 124.6 KB. Source: `blackout/assets/models/items/rusty_scrap_shortsword.toml:1-7`, `blackout/assets/sources/sketchfab_rusty_sword/source.toml:1-7`
- `rusty_scrap_shortbow` and `scrap_shortbow` are aliases of `heavy_machine_gun`. The comment says that every projectile weapon draws this gun until each one has its own model. Source: `blackout/assets/models/items/heavy_machine_gun.toml:1-9`
- `rusty_scrap_arrow` and `scrap_arrow` are aliases of `heavy_machine_gun_clip`. `PRESENTATION` scales the clip to 0.4. Source: `blackout/assets/models/items/heavy_machine_gun_clip.toml:1-9`, `godot/world/model_registry.gd:78-81`
- `copper_shortbow` and `copper_arrow` are not in the manifest. Source: `blackout/web/static/webclient/models/manifest.json:1-44`, `blackout/world/item_defs/weapons.py:1197`, `blackout/world/item_defs/ammunition.py:150`
- Weapons with no model, which draw the tier 3 `weapon` shape: the 18 other items of `weapons.py` (all daggers, scimitars, spears, battleaxes and greatswords, the scrap and copper shortswords, and `copper_shortbow`) and the six gadgets. Source: `blackout/world/item_defs/weapons.py:275-1210`, `blackout/world/item_defs/gadgets.py:96-214`, `godot/world/meshes/family_shapes.gd:99-110`
- The three axes and the hammer resolve to `crafting_tool` and draw the tool shape. Source: `blackout/world/item_defs/tools.py:92-264`, `blackout/systems/interface/statefeed/constants.py:1013-1028`, `godot/world/meshes/family_shapes.gd:146-153`
- Armor with no model, which draws the tier 3 `armor` shape: all 18 items (great helms, chainbodies, platelegs, boots, hide capes, square shields, three tiers each). Source: `blackout/world/item_defs/armor_head.py:22-129`, `armor_body.py:26-134`, `armor_legs.py:22-131`, `armor_feet.py:26-133`, `armor_back.py:22-129`, `armor_offhand.py:26-133`, `godot/world/meshes/family_shapes.gd:112-124`
- `glass_cannon_amulet` has no model and draws the `jewellery` shape. Source: `blackout/world/item_defs/jewellery.py:21-36`, `godot/world/meshes/family_shapes.gd:126-132`
- No tier 2 family model exists for `weapon` or `armor`. Source: `godot/world/meshes/family_shapes.gd:270-287`
- Served sizes of the item models: 35.7 KB to 258.4 KB. The largest served model is `shopkeeper.glb` at 1,281 KB. Source: the file listing of `blackout/web/static/webclient/models/` on 10/11/2026

### Inferences
- **INFERENCE:** Of 21 weapons in `weapons.py`, three have art, and two of those three show a gun for a bow. Of 18 armor items, none has art. A visible equipment feature starts with almost no worn art.
- **INFERENCE:** The one sword model is oriented for an inventory cell (tip up). Its orientation in a hand is a separate question, and one served file has one baked orientation.
- **INFERENCE:** The armor family shape is one breastplate for a helm, boots and a shield alike. The family grain cannot tell a helm from boots. `use_slot` or `tool_type` can.

### Gaps
- I did not open any `.glb`, so no triangle count or node list is given for an item model.
- I did not check `blackout/web/static/webclient/models/CREDITS.md`.

## 8. Prior design notes: `docs/` and the Obsidian vault

### Takeaway
No note in `docs/` or in the vault designs visible equipment, a rigged player, or a walk animation. The vault asks the central question and leaves it open.

### Cited Findings

#### `docs/`
- A search of `docs/` for paper doll, skeleton, rigged, animation, avatar, player model, character model, worn gear, appearance, cosmetic and attach gave 34 hits in 14 files. None is a design for worn gear on a figure, a rig, or an animation. Source: `docs/` (search of 10/11/2026)
- `docs/old/2026-08-15-DESIGN-0002-3d-inventory.md` is the design of the 3D inventory and the paper doll (lines 95, 249, 370).
- `docs/old/2026-09-18-DESIGN-0010-model-pipeline.md` is the design of the model pipeline. It mentions skinning and animation one time, to say that OBJ has none (line 51).
- `docs/old/2026-08-25-ENG-0006-godot-option-a-plan.md:374` records `animations: 0` for the character model of that date.
- `docs/2026-09-22-ENG-0010-godot-ui-authoring.md:392` states the display choice rule for `PRESENTATION`.
- `docs/old/2026-08-25-ENG-0005-godot-vs-webclient.md:386` lists animation among the things that Godot gives over the retired webclient.

#### The Obsidian vault (readable)
- `02_Player/Player_Overview.md` has a section "Appearance & Cosmetics" that is a stub. One guiding question: "Are there cosmetic-only slots (transmog system) or is displayed gear always equipped gear?" Source: `C:\Users\NickR\OneDrive\Documents\Obsidian Vault\Blackout\02_Player\Player_Overview.md:73-82`
- The same stub asks for the scope of the character creator, for mutation appearance, and for cosmetic monetization against the anti-pay-to-win theme. Source: `...\02_Player\Player_Overview.md:76-82`
- "Blackout does not have a traditional class system." A role comes from skills. Source: `...\02_Player\Player_Overview.md:69-71`
- The vault lists the equipment slots and names the code as the owner: "`WieldLocation` in `items/equipment/constants.py` is the single owner of this fact". Source: `...\04_Content\Items\Equipment Stats.md:15-17`
- **CONFLICT:** The vault table has eleven slots and no `ammo` (`...\04_Content\Items\Equipment Stats.md:19-33`). The code has twelve (`blackout/items/equipment/constants.py:12-28`).
- Weapon loadouts: a two-handed weapon occupies both hands, a single one-handed weapon leaves the left hand empty, and a dual-wield holds two weapons. Source: `...\03_Systems\Combat_System.md:174-180`
- An open question asks what can go in an empty off-hand slot. Source: `...\03_Systems\Combat_System.md:182-183`
- "Outsider characters are displayed with a visible marker. Top-tier Outsider gear/achievements carry distinct visual distinction." Source: `...\02_Player\Character_Modes.md:52`
- An open question asks whether Hardcore characters are visible to other players. Source: `...\02_Player\Character_Modes.md:100`
- "Cult identity is a visible part of the player character". The line adds that practitioners show visual signs of their cult. Source: `...\03_Systems\Skills\Combat Skills\Cult_Magic_Skills.md:21`
- The Glass Cannon amulet has glow states that are not implemented. The note calls them "Pure cosmetic signalling" that "makes a build legible to other players at a glance." Source: `...\04_Content\Items\Item Concepts.md:185`
- Enemies telegraph dangerous attacks with "AOE markers, wind-up animations, audio cues". Source: `...\03_Systems\Combat_System.md:302`
- "Quin has no 3D model yet. He uses the fallback NPC model." Source: `...\03_Systems\Skills\Utility_Skills\Exterminator_Skill.md:96`
- `06_UserInterface/UI_and_HUD.md` is front matter only (13 lines, `status: stub`). Source: `...\06_UserInterface\UI_and_HUD.md:1-13`
- **CONFLICT:** `05_Technical/Tech_Overview.md` names Open 3D Engine as the engine and EMotionFX for animation (lines 3, 19, 109). The repo uses Godot (`CLAUDE.md:429-431`).

### Inferences
- **INFERENCE:** The vault sets no rule on displayed gear against equipped gear. Nick must answer that question before a design depends on it.
- **INFERENCE:** Three vault lines expect looks that other players can read: the Outsider marker, the cult signs, and the amulet glow. A system that shows gear to observers is in line with them. None of the three is a rule about equipment.
- **INFERENCE:** The glossary has no noun yet for a worn model, an attach point, or a rig. CLAUDE.md asks for a glossary row before the first doc uses a new noun (`CLAUDE.md:383-384`).

### Gaps
- I searched the vault by keyword and read four notes in part. I did not read every vault note in full.
- No vault note states a rule for character appearance, for NPC gear, or for animation.
- I did not search `C:\Users\NickR\source\repos\playblackout-site` for worldbuilding text on gear.

## 9. Constraints that a design must obey

### Takeaway
The repository rules put the fact "what a character wears" on the server and the look on the client, and they require that an observer pane follows that fact with no rate cap. The model rules limit what art can ship and how the client can read it.

### Cited Findings

#### The server and client boundary
- "Python owns what is TRUE about the game. The client owns what it LOOKS like." Asset kinds and item families belong to the server. Colors, mesh shapes, camera angles and the model registry belong to the client. Source: `CLAUDE.md:442-445` (section "The Godot client")
- "The server names. The client draws." If the client must branch on what a thing is, the server must already say what the player can do with it. Two client verb tables were deleted. Source: `CLAUDE.md:446-454`
- "The client sends only what a telnet player could type." No privileged channel bypasses a Command. Source: `CLAUDE.md:455-458`, `godot/README.md:2478-2486`
- The server must never learn an art file name. `corpse_skeleton` is the stated example. Source: `godot/README.md:188-190`, `godot/world/meshes/family_shapes.gd:252-261`
- The model registry is the client's own and is never generated. Source: `blackout/systems/interface/statefeed/clientexport.py:36-39`, `godot/world/model_registry.gd:15-17`
- A generated file is never edited by hand. Run `python scripts/export_client_constants.py` after an edit of `statefeed/constants.py`. Source: `CLAUDE.md:460-471`
- "A client key that names nothing is a bug. A server fact with no client entry is fine." Each client table documents a fallback, so new content needs no client edit. Source: `CLAUDE.md:503-518`

#### Freshness
- "What Godot shows must be as current as the server can make it." A pane that refreshes only on a menu open is a bug. Source: `CLAUDE.md:473-481` (section "Every pane follows its facts")
- "No channel is rate-capped." The cap drops snapshots. Source: `CLAUDE.md:483-487`, `blackout/systems/interface/statefeed/constants.py:557-622`
- The statefeed marks an expensive snapshot stale and builds it one time after the last change. Source: `CLAUDE.md:488-497`
- To add a fact to a snapshot, find every write of that fact, make each write reach the emitter or a `refresh_*` call, and put the proof in `statefeed/tests/test_freshness.py`. Source: `CLAUDE.md:499-501`
- When in doubt, leave a channel out of `COALESCABLE_CHANNELS`. Only a whole snapshot can be coalesced. Source: `blackout/systems/interface/statefeed/constants.py:630-649`
- A feed send must never raise into a gameplay path. Source: `blackout/systems/interface/statefeed/emit.py:10-16`

#### Payload rules
- "No payload field is named `options`." Evennia reserves the keyword, and the socket drops it. `test_emit.py` refuses it. Source: `CLAUDE.md:793-797` (section "Pop-ups"), `blackout/systems/interface/statefeed/payloads.py:488-491`
- Every payload field must survive `json.dumps`: no Evennia object, no `SaverDict`. Source: `blackout/systems/interface/statefeed/payloads.py:13-17`
- An optional field on an entity row is sent only when it says something. Source: `blackout/systems/interface/statefeed/serializers.py:823-863`
- A new key on the entity row must be in the synthetic row of `test_payload_size.py`, and the worst case must fit the buffer. Source: `blackout/systems/interface/statefeed/tests/test_payload_size.py:174-246`
- Every number in a parsed payload is a float on the client. Convert at the point of use. Source: `godot/README.md:2472-2477`

#### Code conventions
- A new skill, recipe, item or NPC takes one file or one dict entry, never an edit to a dispatch chain. Source: `CLAUDE.md:329-330` (section "Code conventions")
- "One owner per fact." Slot labels belong to the `WieldLocation` enum. A typed literal that had a named constant caused the "Metalsmith" bug. Source: `CLAUDE.md:332-344`
- "Prefer data over branches." Four registry patterns exist to match. Source: `CLAUDE.md:319-327`
- "An import path belongs in the code, never in a database row." Declare it on the class. Source: `CLAUDE.md:346-373`
- `style.md` is the contract: docstring sections, a 4-space indent, about 50 lines for each routine, no magic literals, no embedded calls inside `return` or `if`. Source: `CLAUDE.md:309-316`
- Gameplay rules come from the vault. "Check it before changing any gameplay rule." Source: `CLAUDE.md:1041-1050` (section "Design intent")

#### Items and families
- "An item declares as many families as it belongs to." `ITEM_FAMILY_PRIORITY` decides the family of such an item, never the tag order. Source: `CLAUDE.md:520-534`
- "A family tag is a look, not a rule." Nothing in combat reads a family tag. `test_an_item_in_the_weapon_family_can_actually_fight` asserts the trap. Source: `CLAUDE.md:536-542`
- `create_object(location=...)` does not fire `at_object_receive`, and `move_to` does. Source: `CLAUDE.md:557-559` (gotcha 5)

#### 3D models
- One download is one source, untouched. One served model is one model record. One command builds everything. Source: `CLAUDE.md:879-890` (section "3D models")
- "Never edit the art in a source." A correction goes in `[fix]`. Source: `CLAUDE.md:894-895`
- "A fix corrects the export. A display choice is the client's." Source: `CLAUDE.md:896-898`
- The license gate refuses anything but CC0, CC-BY, art made here, and art that Nick bought. An `exception` waives it, and the check prints each one. Source: `CLAUDE.md:899-902`
- "Godot's runtime loader cannot read Draco, meshopt, or quantized meshes." Source: `CLAUDE.md:903-904`
- "The files of a bought pack never go into git." `LicenseRef-Purchased` needs a local source. No exception waives this. Source: `CLAUDE.md:905-910`
- Art sharpens in and never blocks: every resolve answers at once from the family shape. Content ships ahead of art. Source: `godot/README.md:210-213`
- Hover changes a colour and never a shader. Every material is glow-ready from birth, through `MeshGlow.prepare`. Source: `godot/README.md:239-250`
- A new family look is one entry in `family_shapes.gd`, keyed by a generated constant. Source: `godot/README.md:252-256`
- On the web, the origin of the page must serve the art, at the same path as the model tree. Source: `godot/README.md:258-270`
- The project renders through Compatibility, because the web export cannot use Forward+. Source: `godot/README.md:16-25`
- Nothing floats at a fixed height: each node is lifted by its own measured bottom. Source: `godot/README.md:346-349`
- The yaw goes on the figure, never on the marker, and `WorldView` keeps the yaw outside the node. Source: `godot/README.md:295-316`

#### Tests and process
- Never assert a census of a registry. Never assert a balance value. Wrap a registry loop in `subTest`. Inherit the cheapest base class. Source: `CLAUDE.md:222-260` (section "Writing tests")
- Always test with `--settings test_settings.py`. Source: `CLAUDE.md:165-168`
- Never bulk-import modules under `blackout/`, and name no module of `blackout/scripts/` from outside it. Source: `CLAUDE.md:104-121`
- After a new `class_name` in Godot, run `--headless --path godot --import` one time. Source: `godot/README.md:1615-1620`
- Technical nouns come from `glossary.md`. Add a row before a doc uses a new noun. Player-facing game text is out of scope for the prose rule. Source: `CLAUDE.md:383-388`
- The glossary defines "family" as the look an item renders with, from `ITEM_FAMILY_PRIORITY`. Source: `glossary.md:39`

### Inferences
- **INFERENCE:** By "the server names, the client draws", the server can send which item is in which slot of a visible character (an asset key and a `WieldLocation` value are both server facts). Where a slot sits on a body, and how a model attaches, are looks, so they belong to the client.
- **INFERENCE:** By "every pane follows its facts", each of the nine callers of `equip`, `unequip` and `remove` must reach the new send. `EquipmentHandler._publish` already covers all nine.
- **INFERENCE:** By "a client key that names nothing is a bug", a client table keyed by slot or by `tool_type` needs a guard test in `test_client_constants.py`, as `DollLayout.ROWS` has.
- **INFERENCE:** By "art sharpens in, it never blocks", a worn item with no model must still draw something, or draw nothing by a stated policy. The ladder has both policies today (`resolve_entity` and `resolve_scenery`).
- **INFERENCE:** The license gate and the placeholder status of the player model mean that a rigged body from a bought pack must be a local source, and a rigged body from a free pack must be CC0 or CC-BY.

### Gaps
- No rule in CLAUDE.md covers animation, a rig, or attached models. The feature has no precedent to match on the client.
- `style.md` was not read for this note. Its rules come from the summary in `CLAUDE.md:309-316`.
