# Appearance replication and on-demand asset loading for visible equipment

Conventions in these notes:

- Each fact carries an era tag in parentheses.
- "(search snippet)" marks a fact that came from a search result summary. I did not read the full page for it.
- A size that no source states is in Inferences, with the arithmetic.
- All pages were read on 2026-10-11.

## 1. Appearance against equipment

### Takeaway

Shipped games keep apart what the owner holds and what observers see. The server applies the hide rules, the transmog, and the costume override. Then it sends each observer a small public record for each slot: an item ID or an appearance ID. The client resolves that ID to art with its own tables.

### Cited Findings

- (WoW 3.3.5a) A player object has 19 public slot pairs: `PLAYER_VISIBLE_ITEM_n_ENTRYID` (Type INT) and `PLAYER_VISIBLE_ITEM_n_ENCHANTMENT` (Type TWO_SHORT). Each line carries `Flags: PUBLIC`. — [TrinityCore 3.3.5 UpdateFields.h](https://github.com/TrinityCore/TrinityCore/blob/3.3.5/src/server/game/Entities/Object/Updates/UpdateFields.h)
- (WoW 3.3.5a) `Player::SetVisibleItemSlot` writes `pItem->GetEntry()` to `PLAYER_VISIBLE_ITEM_1_ENTRYID + (slot * 2)`. It writes 0 for an empty slot. Thus an observer gets the item template ID, not the item instance. — [TrinityCore 3.3.5 Player.cpp](https://github.com/TrinityCore/TrinityCore/blob/3.3.5/src/server/game/Entities/Player/Player.cpp)
- (WoW 3.3.5a) A field goes to a viewer only when the field flags match the viewer. `GetUpdateFieldData` starts with `UF_FLAG_PUBLIC`. It adds `UF_FLAG_PRIVATE` only when the viewer is the object itself. — [TrinityCore 3.3.5 Object.cpp](https://github.com/TrinityCore/TrinityCore/blob/3.3.5/src/server/game/Entities/Object/Object.cpp)
- (WoW 3.3.5a, community module) `mod-transmog` keeps the fake entry apart from the real item. It holds a map from item GUID to fake entry, and a table `custom_transmogrification (GUID, FakeEntry, Owner)`. Then it calls `player->SetVisibleItemSlot(item->GetSlot(), item)`. The template of the real item does not change. — [mod-transmog Transmogrification.cpp](https://github.com/azerothcore/mod-transmog/blob/master/src/Transmogrification.cpp)
- (same module) A hidden slot uses the sentinel `HIDDEN_ITEM_ID` as its fake entry. — [mod-transmog Transmogrification.cpp](https://github.com/azerothcore/mod-transmog/blob/master/src/Transmogrification.cpp)
- (WoW retail, TrinityCore master) The visible record of a slot is the struct `VisibleItem`. Its fields are `HasTransmog`, `HasIllusion`, `ItemID`, `SecondaryItemModifiedAppearanceID`, `ConditionalItemAppearanceID`, `ItemAppearanceModID`, `ItemVisual`, `ItemModifiedAppearanceID`, `TransmogSlotOption`, and `SheatheCategory`. `PlayerData` holds `VisibleItems` as an array of 19. — [TrinityCore master UpdateFields.h](https://github.com/TrinityCore/TrinityCore/blob/master/src/server/game/Entities/Object/Updates/UpdateFields.h)
- (WoW client table, build 8.0.1.25902) `ItemModifiedAppearance` has the columns `ItemId`, `Id`, `AppearanceModID`, `AppearanceId`, `VariationIndex`, and `SourceType`. This table is the step from an item to an appearance. — [wowdev.wiki ItemModifiedAppearance](https://wowdev.wiki/DB/ItemModifiedAppearance)
- (Guild Wars 2, official web API) An equipment entry has `id` (the item) and an optional `skin` (the look). It also has `slot`, `dyes`, `upgrades`, and `infusions`. `id` resolves in `/v2/items`, and `skin` resolves in `/v2/skins`. The example Coat has `id` 71436 and `skin` 704. — [GW2 wiki API:2/characters/:id/equipment](https://wiki.guildwars2.com/wiki/API:2/characters/:id/equipment)
- (OSRS era, RSMod v1) The appearance block has one value for each of 12 body slots. An item can hide the body part below it. The server writes BYTE 0 for the arms when the chest item has `equipType == 6`. It writes BYTE 0 for the hair when the head item has `equipType` 8 or 11. — [RSMod PlayerUpdateBlockSegment.kt](https://github.com/Tomm0017/rsmod/blob/master/game/src/main/kotlin/gg/rsmod/game/sync/segment/PlayerUpdateBlockSegment.kt)
- (RS2 revision 317) Apollo applies the same hide rule from three item flags: full-body, full-hat, and full-mask. — [Apollo r317 PlayerSynchronizationMessageEncoder.java](https://github.com/apollo-rsps/apollo/blob/kotlin-experiments/game/src/main/java/org/apollo/game/release/r317/PlayerSynchronizationMessageEncoder.java)
- (OSRS era) A whole-body override exists. RSMod writes SHORT `0xFFFF` and then SHORT `transmogId` (an NPC ID) in place of the 12 slot values. — [RSMod PlayerUpdateBlockSegment.kt](https://github.com/Tomm0017/rsmod/blob/master/game/src/main/kotlin/gg/rsmod/game/sync/segment/PlayerUpdateBlockSegment.kt)
- (OSRS, RuneLite API) `getTransformedNpcId()` gives "the ID of the NPC that the player is currently transformed into". A `ColorTextureOverride` for a kit slot replaces the color and texture targets of the item in that slot. — [RuneLite PlayerComposition](https://static.runelite.net/runelite-api/apidocs/net/runelite/api/PlayerComposition.html)
- (Unreal Engine, Lyra sample) Inventory replicates to "Server and Autonomous Proxy only". Equipment replicates to "Server, Autonomous Proxy, and Simulated Proxies". The Controller owns the inventory, and the Pawn owns the equipment. — [Epic: Lyra Inventory and Equipment](https://dev.epicgames.com/documentation/en-us/unreal-engine/lyra-inventory-and-equipment-in-unreal-engine)
- (Veloren, master branch) The server syncs the full `Inventory` component of any entity to clients (`SyncFrom::AnyEntity`). A comment on it says "TODO: change this to `SyncFrom::ClientEntity` and sync the bare minimum". — [Veloren synced_components.rs](https://gitlab.com/veloren/veloren/-/blob/master/common/net/src/synced_components.rs)
- (Luanti, `3d_armor` mod) The server sends no item ID. It sends three texture strings for each player: skin, armor, and wielded item. The armor string is a list of image names with `^` between them. — [3d_armor api.lua](https://github.com/minetest-mods/3d_armor/blob/master/3d_armor/api.lua)

### Inferences

- Three payload styles exist in these sources. Style 1 sends an item ID that the client resolves (WoW 3.3.5, RS2). Style 2 sends an item ID plus an appearance ID (WoW retail, GW2). Style 3 sends resolved presentation (Luanti texture strings).
- Style 1 and style 2 agree with "the server names, the client draws". Style 3 moves a presentation choice to the server.
- The server is the place for the hide rules. RS2 and the transmog module both resolve "what shows" before the write. The observer client applies no rule.
- For Blackout, one public "look key" for each slot is sufficient. The look key is the asset key of the item or of its cosmetic override. A hidden slot sends an explicit empty value.
- A separate public record also protects private data. WoW and Lyra give an observer the equipped look only. The Veloren TODO shows that the full inventory is more than an observer needs.

### Gaps

- No source in this pass states the recommendation in plain words ("send a display ID, not an item ID"). The evidence is the shipped designs.
- I did not read the 3.3.5 `PlayerFlags` enum. Thus the "hide helm" and "hide cloak" mechanism of that era is not confirmed here.
- I found no public protocol documentation for the FFXIV glamour system or the ESO outfit system.
- The wowdev page does not explain how `AppearanceId` leads to an `ItemDisplayInfo` row.

## 2. Protocol case studies

### Takeaway

RS2 packs the full look of a player into one block of about 50 to 60 bytes. WoW stores the look as public fields of the player object and sends only the changed fields. Ryzom packs the look into three 64-bit values. Luanti sends file names.

### Cited Findings

#### (a) RS2 revision 317 and OSRS

- (RS2 revision 317) Apollo writes the appearance block in this order. — [Apollo r317 PlayerSynchronizationMessageEncoder.java](https://github.com/apollo-rsps/apollo/blob/kotlin-experiments/game/src/main/java/org/apollo/game/release/r317/PlayerSynchronizationMessageEncoder.java)
  1. Gender: BYTE.
  2. One BYTE with the value 0. The source gives it no name.
  3. NPC form: BYTE 255, BYTE 255, SHORT NPC ID. This replaces the slot values.
  4. Slot values. An item is SHORT `0x200 + item id`. A bare body part is SHORT `0x100 + style`. An empty slot with no body part is BYTE 0.
  5. Colours: one BYTE for each colour in `appearance.getColors()`.
  6. Seven animation SHORTs: `0x328` stand, `0x337` stand turn, `0x333` walk, `0x334` turn 180, `0x335` turn 90 cw, `0x336` turn 90 ccw, `0x338` run.
  7. Name: LONG.
  8. Combat level: BYTE.
  9. Skill level: SHORT.
- (RS2 revision 317) The block has a length prefix of one BYTE. The update mask bit of the block is `0x10`. — [Apollo r317 PlayerSynchronizationMessageEncoder.java](https://github.com/apollo-rsps/apollo/blob/kotlin-experiments/game/src/main/java/org/apollo/game/release/r317/PlayerSynchronizationMessageEncoder.java)
- (OSRS era, RSMod v1) The newer block has these fields in order. — [RSMod PlayerUpdateBlockSegment.kt](https://github.com/Tomm0017/rsmod/blob/master/game/src/main/kotlin/gg/rsmod/game/sync/segment/PlayerUpdateBlockSegment.kt)
  1. Gender: BYTE.
  2. Skull icon: BYTE.
  3. Prayer icon: BYTE.
  4. 12 slot values with the same `0x200` and `0x100` rule, or SHORT `0xFFFF` plus SHORT `transmogId`.
  5. Colours: 5 BYTEs.
  6. Seven animation SHORTs. The defaults are 808, 823, 819, 820, 821, 822, 824. The `renderAnimations` of the weapon replace them.
  7. Username: STRING.
  8. Combat level: BYTE.
  9. One SHORT with the value 0, then one BYTE with the value 0. The source gives them no name.
- (OSRS era, RSMod v1) The 12 slots map to the body parts through the table `-1, -1, -1, -1, 2, -1, 3, 5, 0, 4, 6, 1`. A value of -1 means that the slot has no body part below it. — [RSMod PlayerUpdateBlockSegment.kt](https://github.com/Tomm0017/rsmod/blob/master/game/src/main/kotlin/gg/rsmod/game/sync/segment/PlayerUpdateBlockSegment.kt)
- (OSRS, RuneLite API) The client holds the same data as one array. IDs from `KIT_OFFSET` up to `ITEM_OFFSET` are kits. IDs at or above `ITEM_OFFSET` are items. `getColors()` always has size 5. `getGender()` gives 0 for male and 1 for female. — [RuneLite PlayerComposition](https://static.runelite.net/runelite-api/apidocs/net/runelite/api/PlayerComposition.html)
- (OSRS, RuneLite API, search snippet) The older API page gives the numbers: 256 to 512 is a kit, and a value above 512 is an item. — [RuneLite PlayerComposition, older page](https://static.runelite.net/api/runelite-api/net/runelite/api/PlayerComposition.html)
- (OSRS, RuneLite API) `setHash()` does this: "Update the cached hash value for player equipment". The caller runs it when equipment or overrides change. The search snippet of the same page says that the hash lets the client cache player models by appearance. — [RuneLite PlayerComposition](https://static.runelite.net/runelite-api/apidocs/net/runelite/api/PlayerComposition.html)
- (OSRS, rsprot library, current) The library builds the info packets of all players one time each cycle with `infoProtocols.update()`. The README calls this the "expensive task". The README gives no detail on the appearance cache. — [rsprot README](https://github.com/blurite/rsprot/blob/master/README.md)
- The triggers of this block are in section 3.

#### (b) World of Warcraft

- (WoW 3.3.5a) The slot fields start at `UNIT_END + 0x0087` and end at `UNIT_END + 0x00AC`. That is 38 fields: 19 `ENTRYID` and 19 `ENCHANTMENT`. Each field has `Size: 1`, and one unit is a 32-bit value. — [TrinityCore 3.3.5 UpdateFields.h](https://github.com/TrinityCore/TrinityCore/blob/3.3.5/src/server/game/Entities/Object/Updates/UpdateFields.h)
- (WoW 3.3.5a) Other public look fields are `UNIT_FIELD_DISPLAYID`, `UNIT_FIELD_NATIVEDISPLAYID`, `UNIT_VIRTUAL_ITEM_SLOT_ID` (Size 3), `UNIT_FIELD_BYTES_2`, `PLAYER_BYTES`, `PLAYER_BYTES_2`, `PLAYER_BYTES_3`, and `PLAYER_FLAGS`. — [TrinityCore 3.3.5 UpdateFields.h](https://github.com/TrinityCore/TrinityCore/blob/3.3.5/src/server/game/Entities/Object/Updates/UpdateFields.h)
- (WoW 3.3.5a) `EquipItem` and `QuickEquipItem` call `VisualizeItem`. `VisualizeItem` calls `SetVisibleItemSlot` when `slot < EQUIPMENT_SLOT_END`. `RemoveItem` and `DestroyItem` call `SetVisibleItemSlot(slot, nullptr)`. — [TrinityCore 3.3.5 Player.cpp](https://github.com/TrinityCore/TrinityCore/blob/3.3.5/src/server/game/Entities/Player/Player.cpp)
- (WoW client table, build 3.0.2.8905) The client resolves a display through `ItemDisplayInfo`. The columns are `LeftModel`, `RightModel`, `LeftModelTexture`, `RightModelTexture`, `Icon1`, `Icon2`, three `geosetGroup` values, `flags`, `spellVisualID`, `groupSoundIndex`, two `helmetGeosetVis` values (male, female), eight body textures, `itemVisual`, and `particleColorID`. — [wowdev.wiki ItemDisplayInfo](https://wowdev.wiki/DB/ItemDisplayInfo)
- (same table) The eight body textures are `UpperArmTexture`, `LowerArmTexture`, `HandsTexture`, `UpperTorsoTexture`, `LowerTorsoTexture`, `UpperLegTexture`, `LowerLegTexture`, and `FootTexture`. A `geosetGroup` value enables a mesh part of the character model. Gloves with `geosetGroup[0]` set to 2 enable mesh part 403. — [wowdev.wiki ItemDisplayInfo](https://wowdev.wiki/DB/ItemDisplayInfo)
- (WoW retail, TrinityCore master) `UnitData` holds `DisplayID`, `NativeDisplayID`, `StandState`, `SheatheState`, and `VirtualItems` (3 entries of `VisibleItem`). `PlayerData` holds `Customizations`, `PlayerFlags`, `NativeSex`, and `VisibleItems`. — [TrinityCore master UpdateFields.h](https://github.com/TrinityCore/TrinityCore/blob/master/src/server/game/Entities/Object/Updates/UpdateFields.h)
- The triggers of these fields are in section 3.

#### (c) Ryzom, Veloren, Luanti

- (Ryzom, structs credited to Nevrax 2002, in the current repository) Three bitfield structs hold the look of a player. Each struct is a union with one `uint64`, and `serial()` sends that `uint64` in one call. — [Ryzom player_visual_properties.h](https://github.com/ryzom/ryzomcore/blob/core4/ryzom/common/src/game_share/player_visual_properties.h)
  - `SPropVisualA`, 64 bits: `Sex` 1, `JacketModel` 8, `JacketColor` 3, `TrouserModel` 8, `TrouserColor` 3, `WeaponRightHand` 10, `WeaponLeftHand` 8, `ArmModel` 8, `ArmColor` 3, `HatModel` 9, `HatColor` 3.
  - `SPropVisualB`, 47 bits: `Name` 16, `HandsModel` 9, `HandsColor` 3, `FeetModel` 9, `FeetColor` 3, `RTrail` 4, `LTrail` 3.
  - `SPropVisualC`, 54 bits: `MorphTarget1` to `MorphTarget8` at 3 each, `EyesColor` 3, `Tattoo` 7, `CharacterHeight` 4, `TorsoWidth` 4, `ArmsWidth` 4, `LegsWidth` 4, `BreastSize` 4.
- (Ryzom) The comments give a maximum and a current count for each field. `JacketModel` has a maximum of 256 and a current count of 93. The file keeps the older, narrower layouts as comments ("old VPA/VPB/VPC before bit extension"). — [Ryzom player_visual_properties.h](https://github.com/ryzom/ryzomcore/blob/core4/ryzom/common/src/game_share/player_visual_properties.h)
- (Veloren, master branch) These components sync from any entity: `Body`, `Scale`, `Inventory`, `CharacterState`, `CharacterActivity`, `Stance`, `Health`, and others. `Admin` and `CanBuild` sync only to the owner client. — [Veloren synced_components.rs](https://gitlab.com/veloren/veloren/-/blob/master/common/net/src/synced_components.rs)
- (Veloren, master branch) The client reduces an inventory to a small cache key. `CharacterCacheKey` has `third_person` (head, shoulder, chest, belt, back, pants), `tool`, `lantern`, `glider`, `foot`, `head`, and `hand`. The comment says "we try to store only the minimum information required to correctly update the model". — [Veloren figure cache.rs](https://gitlab.com/veloren/veloren/-/blob/master/voxygen/src/scene/figure/cache.rs)
- (Luanti, current docs) `object:set_properties()` changes the look of an object at any time, and the updated properties go to all players in range. `textures` is a list of strings with the default `{"no_texture.png"}`. (search snippet) — [Luanti modding book: Objects](https://rubenwardy.com/minetest_modding_book/en/map/objects.html) and [Luanti object properties](https://docs.luanti.org/for-creators/api/object-properties/)
- (Luanti, engine docs) "ObjectProperties should contain the filename of the mesh (which should be transferred like images)". Players and Lua entities both show on the client as `GenericCAO`. — [Luanti engine docs: Objects](https://docs.luanti.org/for-engine-devs/objects/)
- (Luanti `3d_armor`) `armor.set_player_armor` starts with `"blank.png"` and appends `"^" .. tex .. ".png"` for each worn piece. Then `player_api.set_textures(player, {skin, armor, wielditem})` applies the three strings. — [3d_armor api.lua](https://github.com/minetest-mods/3d_armor/blob/master/3d_armor/api.lua)
- (Luanti 5.10.0, 2024, search snippet) `object:set_observers()` lets the server choose which players get an object. The change is on the server only. — [Luanti 5.10.0 release post](https://blog.luanti.org/2024/11/10/5.10.0-released/)

### Inferences

- Size of the 317 block: 1 + 1 + (12 × 2) + 5 + (7 × 2) + 8 + 1 + 2 = 56 bytes at most, plus the 1-byte length. Empty slots cost 1 byte, not 2.
- Size of the OSRS-era block: 3 + 24 + 5 + 14 + 1 + 2 + 1 = 50 bytes at most, plus the name string.
- Size of the WoW 3.3.5 slot data: 38 fields × 4 bytes = 152 bytes when every slot holds an item with an enchant. The packet also carries a field mask. One equip changes one or two fields.
- Size of the Ryzom look: three `uint64` values = 24 bytes, with 165 bits in use.
- RS2 sends the stance of a weapon inside the appearance. The seven animation IDs change with the weapon. Thus "how this player stands and walks" is part of the look, not a separate state.
- The WoW 3.3.5 model draws many pieces with no model file. A chest piece is body textures plus geoset switches. Only some slots (shoulders, helm, weapons) name a model.

### Gaps

- I did not find a current OSRS (2026) field list. RSMod v1 is some years old. The revision that it targets is not confirmed here.
- The rsprot README does not describe the appearance cache. I did not locate the source file for it.
- The Ryzom header does not say when the server sends the three values.
- I did not read the Veloren `entity_sync` system. The exact trigger of an inventory sync is not confirmed.
- I found no usable protocol documentation for Albion Online. I did not review Nakama or SpacetimeDB sample games. The SpacetimeDB subscriptions page gave no text.

## 3. Update rules

### Takeaway

The look is an event, not a part of the position stream. The server sends it in full on first sight and again only on a change. Two shipped designs skip the first-sight send when the observer already holds the current version.

### Cited Findings

- (OSRS era, RSMod v1) When `newPlayer` is true, the server always sets the APPEARANCE bit and writes the block. Otherwise it writes the block only when `other.hasBlock(APPEARANCE)` is true. — [RSMod PlayerUpdateBlockSegment.kt](https://github.com/Tomm0017/rsmod/blob/master/game/src/main/kotlin/gg/rsmod/game/sync/segment/PlayerUpdateBlockSegment.kt)
- (RS2 revision 317, Apollo) Each observer keeps an array of appearance tickets, one for each other player index. When a player enters the local list, the server compares `other.getAppearanceTicket()` with the stored ticket. It adds the appearance block only when they differ. Then it stores the new ticket. — [Apollo PlayerSynchronizationTask.java](https://github.com/apollo-rsps/apollo/blob/kotlin-experiments/game/src/main/java/org/apollo/game/sync/task/PlayerSynchronizationTask.java)
- (same) The test in the source is `if (appearanceTickets[index] != appearanceTicket) { appearanceTickets[index] = appearanceTicket; return false; }`. — [Apollo PlayerSynchronizationTask.java](https://github.com/apollo-rsps/apollo/blob/kotlin-experiments/game/src/main/java/org/apollo/game/sync/task/PlayerSynchronizationTask.java)
- (same) Two limits bound the first-sight cost. `MAXIMUM_LOCAL_PLAYERS = 255`. `NEW_PLAYERS_PER_CYCLE = 20`, "The maximum number of players to load per cycle". The comment says that the cap keeps the packet inside the buffer of the client. — [Apollo PlayerSynchronizationTask.java](https://github.com/apollo-rsps/apollo/blob/kotlin-experiments/game/src/main/java/org/apollo/game/sync/task/PlayerSynchronizationTask.java)
- (same) A player leaves the local list on a teleport, on logout, or when the distance exceeds `player.getViewingDistance()`. — [Apollo PlayerSynchronizationTask.java](https://github.com/apollo-rsps/apollo/blob/kotlin-experiments/game/src/main/java/org/apollo/game/sync/task/PlayerSynchronizationTask.java)
- (WoW 3.3.5a) `SetUInt32Value` records a change only when the value differs: `if (m_uint32Values[index] != value)`. Then it sets the bit in `_changesMask` and queues the object. A write of the same value does nothing. — [TrinityCore 3.3.5 Object.cpp](https://github.com/TrinityCore/TrinityCore/blob/3.3.5/src/server/game/Entities/Object/Object.cpp)
- (WoW 3.3.5a) First sight uses `BuildCreateUpdateBlockForPlayer` with `UPDATETYPE_CREATE_OBJECT` or `UPDATETYPE_CREATE_OBJECT2`. It includes every field with a non-zero value that the viewer can see. — [TrinityCore 3.3.5 Object.cpp](https://github.com/TrinityCore/TrinityCore/blob/3.3.5/src/server/game/Entities/Object/Object.cpp)
- (WoW 3.3.5a) A later change uses `BuildValuesUpdateBlockForPlayer` with `UPDATETYPE_VALUES`. It includes only the fields with a set bit in `_changesMask`. `ClearUpdateMask` then resets the mask. — [TrinityCore 3.3.5 Object.cpp](https://github.com/TrinityCore/TrinityCore/blob/3.3.5/src/server/game/Entities/Object/Object.cpp)
- (WoW retail, TrinityCore master) `VisibleItem` has two writers, `WriteCreate` and `WriteUpdate`, and its own changes mask (`HasChangesMask<11>`). Thus a delta can carry one sub-field of one slot. — [TrinityCore master UpdateFields.h](https://github.com/TrinityCore/TrinityCore/blob/master/src/server/game/Entities/Object/Updates/UpdateFields.h)
- (Colyseus, current docs) "Clients receive the full state when they join the room." After that, "Only the latest mutation of each property is queued and sent to clients during the patchRate interval." — [Colyseus State Synchronization](https://docs.colyseus.io/state)
- (Gaffer On Games, 2015) A snapshot can be a delta against a baseline that the receiver acknowledged. An unchanged object costs one bit: "One bit: Not changed!". With every object at rest, the stream is "around 15 kilobits per-second", mostly headers. — [Gaffer On Games: Snapshot Compression](https://gafferongames.com/post/snapshot_compression/)
- (MSDP, MUD protocol) After `REPORT`, the server sends the variable and then must "re-send each individual variable whenever it changes". — [MSDP specification](https://tintin.mudhalla.net/protocols/msdp/)
- (Aardwolf GMCP, search snippet) "data is only sent when a value in a module you are subscribed to actually changes". — [Aardwolf: GMCP](https://www.aardwolf.com/wiki/index.php/Clients/GMCP)
- (Dune MUD GMCP, search snippet) Some messages send only the fields that changed. The client must store the full state and update it. — [Dune MUD GMCP](https://dunemud.net/gmcp/start)
- (Unreal Engine, Lyra sample) An `EquipmentInstance` is "Created when equipped on a Pawn", and the engine destroys it on unequip. The instance replicates to simulated proxies. Thus equip and unequip are the events. — [Epic: Lyra Inventory and Equipment](https://dev.epicgames.com/documentation/en-us/unreal-engine/lyra-inventory-and-equipment-in-unreal-engine)

### Inferences

- Four rules cover every source: (1) full look on first sight, (2) a resend only on a change, (3) no look data in the movement stream, (4) an optional version test that skips rule 1.
- The Apollo ticket is a version number for each player. The observer state is one integer for each known player. This is the cheapest form of "the client already holds it".
- A hash of the look gives the same result as a ticket. A hash also lets two players with the same gear share one cache entry on the client.
- The WoW dirty-bit pattern fits a Python server. The setter compares, sets a flag, and the tick sends the flagged slots one time.
- For a snapshot protocol, a version number in each entity record is a small cost. The client asks for the look, or the server pushes it, only when the number is new.
- A cap on new entities for each tick (20 in Apollo) spreads the cost of a crowded area over several ticks.

### Gaps

- The Valve page "Source Multiplayer Networking" returned HTTP 403. I did not confirm its delta and PVS statements.
- I did not confirm how the OSRS client stores a look after a player leaves the view. The `Players` class of a deobfuscated client has a `Buffer[2048]` field with no exported name. — [open-osrs Players.java](https://github.com/open-osrs/runelite/blob/master/runescape-client/src/main/java/Players.java)
- No source in this pass gives the Ryzom or the Veloren trigger.

## 4. Snapshot design for JSON over WebSocket at a slow tick

### Takeaway

No source gives a rule for JSON alone. The documented JSON protocols use named keys, optional fields, and a version for each package. The binary protocols use fixed positions and pay for that with strict version locks.

### Cited Findings

- (IRE GMCP, current docs) An item is a JSON object with named keys: `id`, `name`, `icon`, and an optional `attrib`. Example: `Char.Items.Add { "location": "room", "item": { "id": "303060", "name": "a gold nugget", "icon": "commodity" } }`. — [Iron Realms GMCP](https://nexus.ironrealms.com/GMCP)
- (IRE GMCP) The protocol has a full list and three deltas: `Char.Items.List`, `Char.Items.Add`, `Char.Items.Remove`, and `Char.Items.Update`. — [Iron Realms GMCP](https://nexus.ironrealms.com/GMCP)
- (IRE GMCP) The client declares each package with a version: `Core.Supports.Set [ "Char 1", "Char.Skills 1", "Char.Items 1" ]`. — [Iron Realms GMCP](https://nexus.ironrealms.com/GMCP)
- (Guild Wars 2 API) Equipment is a list of objects. Each object names its slot as a string (`"slot": "Coat"`). The optional `skin` key is absent when the item has its default look. — [GW2 wiki API:2/characters/:id/equipment](https://wiki.guildwars2.com/wiki/API:2/characters/:id/equipment)
- (Evennia, current docs) An OOB message is a command name, a list of arguments, and a map of keyword arguments. The web client gets `["cmdname", [arg, ...], {kwargs}]`. GMCP gets `Cmd.Name {kwargs}`. — [Evennia OOB](https://www.evennia.com/docs/latest/Concepts/OOB.html)
- (Evennia) A client with no OOB support gets only `text`, and the other instructions drop. Thus an OOB message must not carry a fact that every client needs. — [Evennia OOB](https://www.evennia.com/docs/latest/Concepts/OOB.html)
- (Colyseus) The binary schema has hard limits. "Each `Schema` structure can hold up to `63` serialized fields." The encoder and the decoder must hold the same schema with the fields in the same order. — [Colyseus State Synchronization](https://docs.colyseus.io/state)
- (RS2, positional) The 12 slots have a fixed order, and an empty slot is one zero byte. — [Apollo r317 PlayerSynchronizationMessageEncoder.java](https://github.com/apollo-rsps/apollo/blob/kotlin-experiments/game/src/main/java/org/apollo/game/release/r317/PlayerSynchronizationMessageEncoder.java)
- (Ryzom, bit-packed) A field width is a hard limit. The header shows that the team widened the fields one time and kept the old layout as a comment. — [Ryzom player_visual_properties.h](https://github.com/ryzom/ryzomcore/blob/core4/ryzom/common/src/game_share/player_visual_properties.h)
- (Luanti `3d_armor`, compact string) One string holds the full armor look: image names with `^` between them. — [3d_armor api.lua](https://github.com/minetest-mods/3d_armor/blob/master/3d_armor/api.lua)
- (Minecraft) A client that meets a missing texture or model draws a placeholder and continues. Before version 1.4, a missing texture stopped the game. — [Minecraft Wiki: Missing textures and models](https://minecraft.wiki/w/Missing_textures_and_models)

### Inferences

- A map from slot name to asset key is the JSON form of the WoW field array. It tolerates a new slot, because an old client ignores a key that it does not know.
- An ordered list is smaller but ties the client to the slot order. RS2, Ryzom, and Colyseus all show that cost.
- A compact string is the smallest form. It is harder to extend and harder to read in a log.
- Estimate, not measured: a map of 8 slots with 12-character keys is about 220 to 300 bytes of JSON. The server sends it on first sight and on a change only. At a 0.6 second tick this cost is small beside the position data.
- Omit an empty slot from the map. The GW2 API treats an absent `skin` the same way.
- Put a version integer beside the map. The client then compares one number before it reads the map.
- Forward compatibility has two parts. An unknown slot name: the client ignores it. An unknown asset key: the client uses a fallback (section 6).
- The Evennia rule applies to Blackout. A telnet player gets no OOB data. Thus the text output must still name what a character wears.

### Gaps

- I found no source that compares payload shapes for a JSON game protocol with numbers.
- I found no source that gives a bandwidth budget for a WebSocket MMO at a slow tick.
- The Colyseus page does not state its rules for a schema change across versions.

## 5. Client asset loading

### Takeaway

The common pattern is a cache with a key, a pending state, and a late eviction. The client draws the body first and adds the gear when the load ends. On the web, Godot runs on one thread by default, so a threaded load does not remove a stall there.

### Cited Findings

- (Veloren, master branch) `FigureModelCache` is a `HashMap` from `FigureKey` to a model entry plus a last-used tick. An entry is `Pending` or `Done`. — [Veloren figure cache.rs](https://gitlab.com/veloren/veloren/-/blob/master/voxygen/src/scene/figure/cache.rs)
- (same) A miss starts a background job: `slow_jobs.spawn("FIGURE_MESHING", move || {`. The call returns `None` until the job ends. A hit sets `*last_used = tick`. — [Veloren figure cache.rs](https://gitlab.com/veloren/veloren/-/blob/master/voxygen/src/scene/figure/cache.rs)
- (same) Eviction runs on each tick that is a multiple of 60. It removes an entry that nothing used for `60 * 60` ticks: "Wait about a minute at 60 fps before invalidating old models." — [Veloren figure cache.rs](https://gitlab.com/veloren/veloren/-/blob/master/voxygen/src/scene/figure/cache.rs)
- (OSRS, RuneLite API) The client keeps a hash of the equipment of a player so that it can cache player models by appearance. (search snippet for the purpose, API page for `setHash()`) — [RuneLite PlayerComposition](https://static.runelite.net/runelite-api/apidocs/net/runelite/api/PlayerComposition.html)
- (Unity Addressables 2.3) "The Addressables system keeps a reference count of every item it loads." "When the reference count of an Addressable returns to zero, it can be unloaded." — [Unity Addressables: Memory management](https://docs.unity3d.com/Packages/com.unity.addressables@2.3/manual/MemoryManagement.html)
- (same) "you can't unload part of an AssetBundle". A release and a quick reload of the same bundle is "churn", and the page tells the developer to detect it with the Profiler. The page also says "mirror every call to a load method with a call to a release method". — [Unity Addressables: Memory management](https://docs.unity3d.com/Packages/com.unity.addressables@2.3/manual/MemoryManagement.html)
- (Godot 4, stable docs) `GLTFDocument` with `GLTFState` loads a `.glb` at runtime. `append_from_file` or `append_from_buffer` fills the state. `generate_scene` builds the nodes. For a buffer, the caller must set `GLTFState.base_path`. — [Godot: Runtime file loading and saving](https://docs.godotengine.org/en/stable/tutorials/io/runtime_file_loading_and_saving.html)
- (Godot 4) "creating scene chunks (nodes in tree arrangement) outside the active tree is fine." "parts of a scene can be built or instantiated in a thread, then added in the main thread". — [Godot: Thread-safe APIs](https://docs.godotengine.org/en/stable/tutorials/performance/thread_safe_apis.html)
- (Godot 4) "Instancing nodes that render anything in 2D or 3D (such as Sprite2D or MeshInstance3D) is not thread-safe by default." The fix is the project setting Rendering > Driver > Thread Model = Separate. — [Godot: Thread-safe APIs](https://docs.godotengine.org/en/stable/tutorials/performance/thread_safe_apis.html)
- (Godot 4) "one must be careful not to load the same resource from multiple threads at once." "it's easiest to use one thread for loading and modifying resources, and then the main thread for adding them." — [Godot: Thread-safe APIs](https://docs.godotengine.org/en/stable/tutorials/performance/thread_safe_apis.html)
- (Godot web export, since 4.3) The single-threaded export "is the preferred and now default way to export your games on the Web". A multi-threaded export needs `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp`. — [Godot: Exporting for the Web](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html)
- (Godot web export) HTTP has limits in the browser: "Threaded/Blocking mode is not available." "Cannot progress more than once per frame, so polling in a loop will freeze." Requests are "Subject to same-origin policy." — [Godot: Exporting for the Web](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html)
- (Godot web export) "The project will be paused by the browser when the tab is no longer the active tab". "This can cause networked games to disconnect if the user switches tabs for a long duration." — [Godot: Exporting for the Web](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html)
- (Godot web export) The `user://` file system persists only when the browser allows IndexedDB. Private browsing prevents it. Native exports "will always perform better by a significant margin". — [Godot: Exporting for the Web](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html)
- (V8, 2020) WebAssembly with 32-bit pointers has a limit of 4 GB. Chrome allowed 2 GB before version M83. Emscripten allows 2 GB by default. The post tells apps to start small and to handle a failed `malloc()`. — [V8: Up to 4GB of memory in WebAssembly](https://v8.dev/blog/4gb-wasm-memory)
- (MDN, current) For a file that never changes, put a version or a hash in the URL and send `Cache-Control: max-age=31536000, immutable`. — [MDN: HTTP caching](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Caching)
- (MDN) For a file with a fixed URL, such as `manifest.json`, send `Cache-Control: no-cache` with an `ETag`. The server then answers `304 Not Modified` when nothing changed. — [MDN: HTTP caching](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Caching)
- (Luanti, current docs) The client gets `index.mth`, a list of SHA1 hashes on the media host. Then it requests `[remote_media][SHA1 hash]` for each hash that its cache does not hold. Since 5.12.0 the index request is a GET, "to facilitate using static hosting". — [Luanti: Remote media](https://docs.luanti.org/for-server-hosts/remote-media/)
- (Luanti) When the media host lacks a file or does not answer, the client gets the file from the game connection. (search snippet) The client makes sure that the SHA1 of each download agrees with the hash that the game server gave. — [Luanti: Remote media](https://docs.luanti.org/for-server-hosts/remote-media/)
- (RS2 revision 317, Apollo) The server adds at most 20 new players to a client in one cycle. This limits how many looks the client must build at the same time. — [Apollo PlayerSynchronizationTask.java](https://github.com/apollo-rsps/apollo/blob/kotlin-experiments/game/src/main/java/org/apollo/game/sync/task/PlayerSynchronizationTask.java)

### Inferences

- The Veloren cache is the closest model for Blackout: key, `Pending` or `Done`, last-used tick, and eviction after about one minute with no use.
- A reference count and a late eviction answer two different questions. The count says "is this in use now". The delay prevents the "churn" that Unity names.
- Key the mesh cache by asset key, not by player. Two players with the same jacket then share one mesh.
- The content-hash manifest of Luanti maps to Blackout directly. The project already writes a `manifest.json` in its model build. A hash in each `.glb` URL permits the `immutable` header. The manifest itself gets `no-cache`.
- On the Godot web export, the parse of a `.glb` and `generate_scene` run on the main thread unless the host sends the two isolation headers. Thus the client must spread the work: one model for each frame, from a queue.
- On desktop, one loader thread can run `append_from_buffer` and `generate_scene` outside the tree. The main thread then adds the node. The Godot docs permit this pattern with the Thread Model setting.
- The browser HTTP cache is the disk cache on the web. The client needs no file cache of its own there. On desktop, the client must keep its own files, keyed by hash.
- The area of interest gives a free preload. The look arrives when a player enters the radius, and that is before the player is close.
- Wasm memory is finite and the tab can pause. Thus eviction is more important on the web than on desktop.

### Gaps

- I found no primary source on a preload of the gear of nearby players as a named technique.
- I found no Godot source that measures the cost of `GLTFDocument.generate_scene` on the web. The stall on the main thread is a deduction from the single-thread default.
- I did not confirm memory limits of mobile browsers. The V8 post does not cover them.
- I did not confirm how the OSRS and WoW clients show a character while a model streams.
- The Unity page does not cover content catalogs or hashes.

## 6. Fallback rules

### Takeaway

Games resolve a look through one or two tables, so many items share one piece of art. A missing asset gives a visible placeholder or nothing, and the game continues. Only the Luanti design lets a server add content with no client release.

### Cited Findings

- (WoW 3.0.2 client table) An `ItemDisplayInfo` row can draw an item with no model file. It names body textures for eight regions and geoset values that switch mesh parts of the character. — [wowdev.wiki ItemDisplayInfo](https://wowdev.wiki/DB/ItemDisplayInfo)
- (WoW, later builds) The item to look step became a table of its own (`ItemModifiedAppearance`, with `ItemId`, `AppearanceModID`, `AppearanceId`). Build 7.0.1.21737 moved textured items to `ItemDisplayInfoMaterialRes`. — [wowdev.wiki ItemModifiedAppearance](https://wowdev.wiki/DB/ItemModifiedAppearance) and [wowdev.wiki ItemDisplayInfo](https://wowdev.wiki/DB/ItemDisplayInfo)
- (OSRS cache, RuneLite) An item definition has `maleModel0`, `maleModel1`, `maleModel2`, `femaleModel0`, `femaleModel1`, `femaleModel2`, head models, and offsets. Each model field has the default -1. It also has `colorFind`, `colorReplace`, `textureFind`, and `textureReplace`. — [RuneLite ItemDefinition.java](https://github.com/runelite/runelite/blob/master/cache/src/main/java/net/runelite/cache/definitions/ItemDefinition.java)
- (RS2 and OSRS) A slot with no item and no body part is a zero byte in the appearance block. The client draws nothing there. — [RSMod PlayerUpdateBlockSegment.kt](https://github.com/Tomm0017/rsmod/blob/master/game/src/main/kotlin/gg/rsmod/game/sync/segment/PlayerUpdateBlockSegment.kt)
- (Luanti `3d_armor`) A piece with no declared texture gets a name from a convention: `tex = def.texture or item:gsub("%:", "_")`. The base of the string is `"blank.png"`. — [3d_armor api.lua](https://github.com/minetest-mods/3d_armor/blob/master/3d_armor/api.lua)
- (Luanti) The default of `textures` is `{"no_texture.png"}`. (search snippet) — [Luanti object properties](https://docs.luanti.org/for-creators/api/object-properties/)
- (Luanti) A server names any mesh or image file in the object properties, and the client downloads the file by hash at connect. — [Luanti engine docs: Objects](https://docs.luanti.org/for-engine-devs/objects/) and [Luanti: Remote media](https://docs.luanti.org/for-server-hosts/remote-media/)
- (Minecraft) A missing texture is "a prominent black #000000 and magenta #f800f8 checkerboard". A missing model is a full cube with that texture. A missing sound does not play. — [Minecraft Wiki: Missing textures and models](https://minecraft.wiki/w/Missing_textures_and_models)
- (Minecraft) "The game now generates missing textures for absent assets." Before 1.4 a missing texture stopped the game. — [Minecraft Wiki: Missing textures and models](https://minecraft.wiki/w/Missing_textures_and_models)
- (Guild Wars 2 API) An item with no `skin` key shows its own default look. — [GW2 wiki API:2/characters/:id/equipment](https://wiki.guildwars2.com/wiki/API:2/characters/:id/equipment)
- (WoW 3.3.5a module) A sentinel entry (`HIDDEN_ITEM_ID`) means "draw nothing in this slot". — [mod-transmog Transmogrification.cpp](https://github.com/azerothcore/mod-transmog/blob/master/src/Transmogrification.cpp)

### Inferences

- Three fallback levels appear. Level 1: a shared look (many WoW items point at one display row). Level 2: a tinted variant of a shared model (the OSRS find and replace colors). Level 3: no visible change (the OSRS model default of -1).
- The OSRS color fields suggest that many items reuse one model with new colors. The source lists the fields only. It does not state how often items share a model.
- WoW and OSRS do not keep "new content needs no client change" true. Both resolve an ID through a table in the client data. New content needs a data update.
- Luanti keeps it true, because the server names the file and the client downloads it by hash.
- For Blackout, the rule holds when the server sends an asset key and the manifest lists it. A new item with a new model needs a model build and a manifest update, with no client release.
- A fallback chain keeps a client safe when the key is unknown: exact key, then the model of the item family, then no visible change. The project already has a family priority order for items.
- A loud placeholder (the Minecraft checkerboard) helps a developer. A quiet fallback (the bare body) is better for a player. A debug flag can select one.
- The server can do the fallback before the send. Then the client never meets a key with no model. But this makes the server read the model manifest.

### Gaps

- I found no source that documents the WoW or OSRS client behavior for an ID with no table row.
- I found no source on a generic model for each item family as a named practice. The level list above is a deduction from the tables.

## 7. Draw and sheathe, combat stance, and held tools

### Takeaway

WoW replicates the sheathe state as one public byte. RS2 has no sheathe state: the weapon always shows, and the look carries the stance animations. Both games let an animation carry a temporary held item.

### Cited Findings

- (WoW 3.3.5a) `enum SheathState : uint8` has `SHEATH_STATE_UNARMED = 0` ("non prepared weapon"), `SHEATH_STATE_MELEE = 1` ("prepared melee weapon"), and `SHEATH_STATE_RANGED = 2` ("prepared ranged weapon"). — [TrinityCore 3.3.5 UnitDefines.h](https://github.com/TrinityCore/TrinityCore/blob/3.3.5/src/server/game/Entities/Unit/UnitDefines.h)
- (WoW 3.3.5a) The state is the "low byte (0 from 0..3) of UNIT_FIELD_BYTES_2" (`UNIT_BYTES_2_OFFSET_SHEATH_STATE = 0`). `UNIT_FIELD_BYTES_2` has `Flags: PUBLIC`. — [TrinityCore 3.3.5 UnitDefines.h](https://github.com/TrinityCore/TrinityCore/blob/3.3.5/src/server/game/Entities/Unit/UnitDefines.h) and [TrinityCore 3.3.5 UpdateFields.h](https://github.com/TrinityCore/TrinityCore/blob/3.3.5/src/server/game/Entities/Object/Updates/UpdateFields.h)
- (WoW 3.3.5a) The stand state is also a replicated byte: `UnitStandStateType` in byte 0 of `UNIT_FIELD_BYTES_1`, with values such as `STAND`, `SIT`, `SLEEP`, `DEAD`, and `KNEEL`. — [TrinityCore 3.3.5 UnitDefines.h](https://github.com/TrinityCore/TrinityCore/blob/3.3.5/src/server/game/Entities/Unit/UnitDefines.h)
- (WoW 3.3.5a) `UNIT_VIRTUAL_ITEM_SLOT_ID` has Size 3 and `Flags: PUBLIC`. It holds the held items of a unit apart from the 19 player slots. — [TrinityCore 3.3.5 UpdateFields.h](https://github.com/TrinityCore/TrinityCore/blob/3.3.5/src/server/game/Entities/Object/Updates/UpdateFields.h)
- (WoW retail, TrinityCore master) `UnitData` has `SheatheState` (uint8) and `VirtualItems` (3 entries). Each `VisibleItem` also has a `SheatheCategory` (uint8). — [TrinityCore master UpdateFields.h](https://github.com/TrinityCore/TrinityCore/blob/master/src/server/game/Entities/Object/Updates/UpdateFields.h)
- (RS2 and OSRS) The field lists of the appearance block hold no sheathe field. The block holds seven animation IDs for stand, turn, walk, and run. In RSMod, the `renderAnimations` of the weapon replace the defaults. — [RSMod PlayerUpdateBlockSegment.kt](https://github.com/Tomm0017/rsmod/blob/master/game/src/main/kotlin/gg/rsmod/game/sync/segment/PlayerUpdateBlockSegment.kt)
- (OSRS cache, RuneLite) A sequence (animation) definition has two item fields. Opcode 6 reads `leftHandItem` and opcode 7 reads `rightHandItem`, each with `readUnsignedShort()`. — [RuneLite SequenceLoader.java](https://github.com/runelite/runelite/blob/master/cache/src/main/java/net/runelite/cache/definitions/loaders/SequenceLoader.java)
- (Veloren, master branch) `CharacterState`, `CharacterActivity`, and `Stance` sync from any entity. The client cache key holds `tool` only when the tools are visible. — [Veloren synced_components.rs](https://gitlab.com/veloren/veloren/-/blob/master/common/net/src/synced_components.rs) and [Veloren figure cache.rs](https://gitlab.com/veloren/veloren/-/blob/master/voxygen/src/scene/figure/cache.rs)
- (Luanti `3d_armor`) The wielded item is the third texture string of the player. The server sends it with the skin and the armor. — [3d_armor api.lua](https://github.com/minetest-mods/3d_armor/blob/master/3d_armor/api.lua)

### Inferences

- Two models exist. WoW replicates "weapon drawn" as its own state. RS2 and Veloren derive what the hands show from the equipment plus the current action.
- The RS2 model is the smaller one. The server sends the equipment, the stance animations, and the animation that plays. The client needs no drawn flag.
- The sequence item fields put "show a tool during this action" in client data. The server sends only the animation ID. This is the override that the question describes. The exact client rule for the two fields is not in the source that I read.
- For Blackout, the server already knows the action of a character (a fight, a gather, a craft). It can send an action name, and the client can own the table from action to held tool. That agrees with "the server names, the client draws".
- If a tool must show an item that the character does not wear, the server must name it. An axe from the bag during a cut is an example. WoW uses the virtual item fields for that.
- A sheathe flag is useful only when the client draws a weapon in two places (hand and back). A game with one place can skip it.

### Gaps

- I did not confirm how the OSRS client applies `leftHandItem` and `rightHandItem` to the weapon and shield slots. Two searches gave no source.
- I did not read `Player::SetSheath` or the opcode that a WoW client sends to change the state. The file chunk that I read did not hold it.
- I did not confirm how the WoW client uses `SheatheCategory`.

## 8. Security and trust

### Takeaway

The shipped designs give the client no write path to the look. The server derives the look from equipment that it already validated. The two real risks are a client that claims a look that it does not own, and a server that sends observers more than the look.

### Cited Findings

- (WoW 3.3.5a) Only server code writes the visible slot fields. `EquipItem`, `QuickEquipItem`, `RemoveItem`, and `DestroyItem` reach `SetVisibleItemSlot`. — [TrinityCore 3.3.5 Player.cpp](https://github.com/TrinityCore/TrinityCore/blob/3.3.5/src/server/game/Entities/Player/Player.cpp)
- (WoW 3.3.5a) The per-field flags separate what the owner gets from what an observer gets: `UF_FLAG_PUBLIC`, `UF_FLAG_PRIVATE`, `UF_FLAG_OWNER`. — [TrinityCore 3.3.5 Object.cpp](https://github.com/TrinityCore/TrinityCore/blob/3.3.5/src/server/game/Entities/Object/Object.cpp) and [AzerothCore UpdateFieldFlags.h](https://www.azerothcore.org/doxygen/d8/dd3/UpdateFieldFlags_8h.html)
- (Unreal Engine, Lyra sample) Inventory goes to the owner only. Equipment goes to all clients. — [Epic: Lyra Inventory and Equipment](https://dev.epicgames.com/documentation/en-us/unreal-engine/lyra-inventory-and-equipment-in-unreal-engine)
- (Veloren, master branch) The full inventory of every entity goes to every client in range. The code marks this with a TODO to "sync the bare minimum". — [Veloren synced_components.rs](https://gitlab.com/veloren/veloren/-/blob/master/common/net/src/synced_components.rs)
- (Minecraft mod, search snippet) A skin mod fixed an exploit where any client could skip the unlock progression and equip locked skins. The same changelog hardened network payloads against unbounded varints that could exhaust client memory. — [TACZ Advanced Skin System changelog](https://www.curseforge.com/minecraft/mc-mods/tacz-advanced-skin-system-neoforge/files/8542968)
- (Counter-Strike 2, forum post, search snippet) A client-side skin changer changes only what its own user sees. — [Steam community discussion](https://steamcommunity.com/app/730/discussions/0/1738888024498810945)
- (MUME, search snippet) The game does not give extra data over GMCP that can put players on basic clients at a disadvantage. — [MUME: GMCP help](https://mume.org/help/gmcp)
- (Godot web export) Browser requests are "Subject to same-origin policy." — [Godot: Exporting for the Web](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html)
- (Luanti) The client makes sure that each downloaded file has the SHA1 that the game server announced. (search snippet) — [Luanti: Remote media](https://docs.luanti.org/for-server-hosts/remote-media/)

### Inferences

- When the server derives the look from server state, a client cannot fake a look for other players. A local model swap affects only that client.
- The risk moves to the equip command. Blackout already sends only commands that a telnet player can type. Thus the equip path keeps every lock and check.
- Information exposure is the second risk. The look tells an observer what a player wears. That is public by design. Stats, the bag, and hidden slots must stay out of the observer payload.
- A cosmetic override can hide real gear in a fight. A design must decide if observers get the real item, the look, or both. WoW retail sends both in `VisibleItem` (`ItemID` and the appearance fields).
- An asset key in a payload becomes a URL on the client. The client must build the URL from the manifest, not from the raw key. Then a bad key cannot make a request to another path or host.
- A content hash in the manifest also protects against a wrong or stale file on the static host. Luanti makes the same check.
- A text field in a look (a name, a sign) needs the same output escape as chat.

### Gaps

- I found no primary engineering source that lists appearance exploits in an MMO. The two search snippets are low-grade sources.
- I did not find a post-mortem of an appearance spoof in a shipped MMO.

## 9. Text-first and hybrid games

### Takeaway

The MUD protocols carry the inventory of the player to a client, with a worn flag and an icon key. I found no MUD protocol or project that sends the equipment of other characters for a 3D view. Blackout must define that payload itself.

### Cited Findings

- (IRE GMCP, current docs) `Char.Items.List` carries a `location` (`"inv"`, `"room"`, or `"repNUMBER"` for a container) and an `items` array. — [Iron Realms GMCP](https://nexus.ironrealms.com/GMCP)
- (IRE GMCP) The `attrib` string holds one letter for each property: `w` worn, `W` wearable but not worn, `l` wielded, `g` groupable, `c` container, `t` takeable, `m` monster, `d` dead monster, `x` not a target. — [Iron Realms GMCP](https://nexus.ironrealms.com/GMCP)
- (IRE GMCP) `icon` is the image key of the item in the client, for example `"scroll"` or `"commodity"`. The server names the icon, and the client owns the image. — [Iron Realms GMCP](https://nexus.ironrealms.com/GMCP)
- (IRE GMCP) The server sends `Char.Items.Update` only for inventory items. The client asks for a list with `Char.Items.Inv ""` or `Char.Items.Room ""`. — [Iron Realms GMCP](https://nexus.ironrealms.com/GMCP)
- (Achaea forum, search snippet) A user notes that GMCP does not say which hand holds a wielded item. — [Achaea forums: GMCP questions](https://forums.achaea.com/discussion/2048/gmcp-questions)
- (Aardwolf, text tags) `eqdata` and `invdata` give one line for each item: `objectid,flags,itemname,level,type,unique,wear-loc,timer`. `wear-loc` is a location number, or -1 when the item is not worn. — [Aardwolf: Help/Invdata](https://www.aardwolf.com/wiki/index.php/Help/Invdata)
- (MSDP) The suggested variables cover the character (`HEALTH`, `LEVEL`, `MONEY`, `AFFECTS`), the opponent, and the room. No variable covers equipment or appearance. — [MSDP specification](https://tintin.mudhalla.net/protocols/msdp/)
- (Evennia, current docs) `caller.msg(commandname=((args, ...), {key:value, ...}))` sends one OOB command. Evennia maps `foo_bar` to the GMCP name `Foo.Bar`. The web client gets a JSON array. — [Evennia OOB](https://www.evennia.com/docs/latest/Concepts/OOB.html)
- (Evennia) A session with no OOB support gets only `text`. SSH supports only `text`. — [Evennia OOB](https://www.evennia.com/docs/latest/Concepts/OOB.html)
- (Usurper Reborn v0.60.0, search snippet) The release notes describe GMCP support and an Electron graphical client. The notes cover vitals and status panes, not equipment visuals. — [Usurper Reborn v0.60.0 release notes](https://newreleases.io/project/github/binary-knight/usurper-reborn/release/v0.60.0)
- (BSX MUDs, history, search snippet) BSX added a graphics protocol to an LPMud to draw polygon scenes in a side view. — [Raph Koster: Online World Timeline](https://www.raphkoster.com/gaming/book/3b.html)
- (Ryzom) Ryzom is a 3D MMO, not a text game. Its visual property structs are the nearest open-source example of a server-sent look for other characters. — [Ryzom player_visual_properties.h](https://github.com/ryzom/ryzomcore/blob/core4/ryzom/common/src/game_share/player_visual_properties.h)

### Inferences

- The MUD payloads describe the own character for a user interface. None of them describes another character for a renderer.
- The IRE `icon` key and the `attrib` letters are the same idea as an asset key and a slot name. The MUD field gives a precedent for "the server names, the client draws".
- The GMCP pattern of a full list plus add, remove, and update messages fits a slow tick. A look payload can follow it: the full look on first sight, then a slot change.
- The Evennia rule makes the text channel the base. The look payload is an extra for a client that subscribes. Blackout already uses this pattern for its statefeed channels.
- A telnet player needs the same fact as text. A `look` at a character must list the visible gear from the same resolved look. Then the two views cannot disagree.

### Gaps

- I found no Evennia project that sends equipment to a graphical client.
- I found no MUD with a 3D client that documents an equipment payload.
- I did not read the Aardwolf GMCP page or the Dune MUD page in full. I did not find the `invmon` codes.
