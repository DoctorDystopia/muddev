# How shipped MMOs and 3D RPGs show equipped gear on a player model

Notes as of 10/11/2026. Each finding has an era tag and an evidence label.

- **(read)**: the researcher opened the page or the source file.
- **(snippet)**: the search tool quoted the page. The researcher did not open the page.
- **(forum)**: a community post, not a developer document.
- **(page not confirmed)**: the search tool gave several pages for one query. The link is the most likely page. The page did not load for a check.

The RuneScape 2 findings come from the LostCityRS repositories, branch `274`. These repositories are a community reconstruction of the 2004-era client, server, and content. The researcher did not confirm the calendar date of revision 274.

## 1. What are the main techniques, and what does each one cost?

### Takeaway

No shipped game in this research uses one technique. Each game picks a technique for each slot. Rigid attachment covers weapons, shields, and helms. Part replacement or skinned parts cover the torso, arms, and legs. Recolor and texture layers supply most of the item count.

### Cited Findings

**Technique 1: rigid attachment to a bone or socket**

- [WoW, all eras] An M2 model stores a list of attachment points. Each entry has an `id`, a `bone`, a `position` relative to that bone, and an `animate_attached` track. (read) — [wowdev.wiki M2](https://wowdev.wiki/M2)
- [WoW] The attachment ID list includes 0 Shield, 1 HandRight, 2 HandLeft, 5 ShoulderRight, 6 ShoulderLeft, 11 Helm, 12 Back, 26 SheathMainHand, 27 SheathOffHand, 28 SheathShield, and 57 Backpack. (read) — [wowdev.wiki M2](https://wowdev.wiki/M2)
- [Valheim, 2021 to 2026] A simple shield or weapon prefab holds an empty object named `attach` with the mesh as its child. The game picks the attach point from the item type. (read) — [Valheim-Modding wiki](https://github-wiki-see.page/m/Valheim-Modding/Wiki/wiki/Attaching-Weapons-and-Armor)
- [Unreal Lyra, UE5] An equipment definition is data only. It lists the actors to spawn, and each actor has a socket and an attachment transform. (read) — [X157 Lyra notes](https://x157.github.io/UE5/LyraStarterGame/Equipment/)
- [Godot 4] A `BoneAttachment3D` node follows the transform of one bone. It can also point at an external `Skeleton3D`. (snippet) — [Godot class reference](https://docs.godotengine.org/en/4.2/classes/class_boneattachment3d.html)
- [Godot 4] Rigid accessories such as shields, hats, and rings do not deform. A forum poster puts them on a `BoneAttachment3D`. (snippet, forum, page not confirmed) — [Godot Forums](https://godotforums.org/d/40518-accessories-for-3d-characters)
- [Godot 4] One developer reports that many show and hide children on the rig become hard to manage. The same thread reports attached items that ignore a roll of the character. (snippet, forum) — [Godot forum](https://forum.godotengine.org/t/gdscript-how-to-assign-a-skeleton3d-to-a-meshinstance3d/119829)
- [General] A Polycount poster describes MMO gear that code attaches to skeleton joints or to locators on the rig. Code also scales gear, for example WoW shoulder pads on different races. (snippet, forum, page not confirmed) — [Polycount](https://polycount.com/discussion/comment/1737185)
- [WoW] A player post says most armor sets have up to four attached models: two shoulders, a belt buckle, and a helmet. Shoulders and buckles sit on "special attachment points" with fixed scale. (read, forum, 09/2024) — [Blizzard forum](https://eu.forums.blizzard.com/en/wow/t/armor-fitting-tool-idea/534704)

**Technique 2: skinned gear meshes on one shared skeleton**

- [Unreal, UE5] Leader Pose Component: the parent mesh drives the animation and the child meshes follow. Setup cost is minimal. Game thread cost is minimal. Render thread cost is high. (read) — [Epic docs](https://dev.epicgames.com/documentation/en-us/unreal-engine/working-with-modular-characters-in-unreal-engine)
- [Unreal, UE5] Child meshes on a leader pose "cannot run unique animations, or simulate physics independently." Extra or skipped joints render in the reference pose. (read) — [Epic docs](https://dev.epicgames.com/documentation/en-us/unreal-engine/working-with-modular-characters-in-unreal-engine)
- [Unreal, UE5] Copy Pose From Mesh costs the most on both threads, because an animation graph runs on each child. It permits physics for each part. (read) — [Epic docs](https://dev.epicgames.com/documentation/en-us/unreal-engine/working-with-modular-characters-in-unreal-engine)
- [Unreal, UE5] The Epic page calls Leader Pose a good start point for a first modular character. (snippet) — [Epic docs](https://dev.epicgames.com/documentation/unreal-engine/working-with-modular-characters-in-unreal-engine)
- [Godot 4.0] A forum user confirms the method. Each clothing item is a separate object with bone weights on the same rig. The game shows or hides each item. (snippet, forum, page not confirmed) — [Godot Forums](https://godotforums.org/d/28258-3d-rigged-animated-characters-and-interchangeable-clothing)
- [Godot] A forum poster warns that all part files must use the exact same skeleton. The poster says not to remove unused bones, because that breaks the setup. (snippet, forum, page not confirmed) — [Godot Forums](https://godotforums.org/d/40518-accessories-for-3d-characters)
- [Godot 4, 08/2026] One poster gives the runtime steps for a clothing mesh from a separate file. Instantiate the file. Set the owner of the mesh to null. Move the mesh below the body skeleton. Point its skeleton path at the body skeleton. (read, forum) — [Godot forum](https://forum.godotengine.org/t/character-customization-in-godot-3d/59840)
- [Godot 4, 08/2026] Other posters in that thread keep the clothes as separate meshes below the player and show or hide them. One says that for a limited set of clothes the hide system "will work perfectly fine". (read, forum) — [Godot forum](https://forum.godotengine.org/t/character-customization-in-godot-3d/59840)
- [Godot 4, 08/2026] The same thread says the artist must link the clothes to the rig in Blender first. Export the skeleton with the clothing mesh, or the mesh has no weights. (read, forum) — [Godot forum](https://forum.godotengine.org/t/character-customization-in-godot-3d/59840)
- [Unity] A developer reports that a gear prefab loses its bone references after instantiation on an avatar. A new `bones` array and a new `rootBone` did not fix it. (snippet, forum) — [Unity Discussions](https://discussions.unity.com/t/how-do-you-get-a-prefab-w-skinned-mesh-renderer-to-attach-to-an-avatar-on-instantiation/1615331)
- [Valheim] Complex armor uses `attach_skin`: an FBX with an armature and the rigged items. Each vertex group must have the same name and case as its target bone. (read) — [Valheim-Modding wiki](https://github-wiki-see.page/m/Valheim-Modding/Wiki/wiki/Attaching-Weapons-and-Armor)
- [Valheim] A community mod exists only to correct the bone order in the skinned mesh renderers of custom armor. The same mod adds body hide for armor. (snippet) — [Blacksmiths tools](https://thunderstore.io/c/valheim/p/GoldenJude/Blacksmiths_tools/)
- [WoW, Legion 2016 and later] Modders report "collections" M2 models. These models are armor on the same skeleton as the character and hold no animations of their own. (snippet, forum) — [Model Changing Network](https://elijahketchersid.com/forums/thread-1998.html)
- [WoW, Legion and later] A player post agrees: "Starting with Legion, some armor sets have more 3d elements using what is called a collection." Specific bones move the vertices of a collection. (read, forum, 09/2024) — [Blizzard forum](https://eu.forums.blizzard.com/en/wow/t/armor-fitting-tool-idea/534704)

**Technique 3: full body-part replacement**

- [RS2 2004] An equipped item replaces the identity kit value in its appearance slot. The item model is the body part. See question 2 for the data. (read) — [Engine-TS Player.ts](https://github.com/LostCityRS/Engine-TS/blob/274/src/engine/entity/Player.ts)
- [WoW] Many armor items only apply a texture to the base model. Other items replace a section of the model with a more armor-shaped mesh. (read) — [Warcraft Wiki](https://warcraft.wiki.gg/wiki/Character_model)
- [Godot] A forum poster says it is common to swap the whole mesh for one with the clothes on. Another poster splits the body into head, torso, and legs slots. (snippet, forum, page not confirmed) — [Godot Forums](https://godotforums.org/d/40518-accessories-for-3d-characters)
- [Torchlight 2, 2012] The body has sections with Material IDs. The IDs control which model parts hide for each clothing type. (read) — [Runic Games armor set guidelines](https://docs.runicgames.com/wiki/Armorset_Guidelines.html)

**Technique 4: geosets or mesh sections that turn on and off**

- [WoW] Player models have pieces named geosets. The client shows, hides, or swaps them. Geoset IDs come in groups of 100: 04xx gloves, 05xx boots, 08xx sleeves, 13xx robe or trousers, 15xx cape. (read) — [wowdev.wiki Character Customization](https://wowdev.wiki/Character_Customization)
- [WoW] Each item display row carries small `geosetGroup` numbers. The client adds each number to a base ID. A gloves value of 2 enables mesh part 403. (read) — [wowdev.wiki ItemDisplayInfo](https://wowdev.wiki/DB/ItemDisplayInfo)
- [Skyrim, 2011] Each armor mesh stores partitions with body part numbers in a `BSDismemberSkinInstance` block. The numbers must agree with the ArmorAddon record. If they do not agree, the item is invisible. (snippet, forum, page not confirmed) — [Nexus forum](https://forums.nexusmods.com/topic/1303526-help-to-change-body-addon-slot-in-nifscope)

**Technique 5: texture layers on the base body**

- [WoW] An item display row names up to eight body textures: ArmUpper, ArmLower, Hand, TorsoUpper, TorsoLower, LegUpper, LegLower, and Foot. Version 6.0.1 adds an Accessory texture. (read) — [wowdev.wiki ItemDisplayInfo](https://wowdev.wiki/DB/ItemDisplayInfo)
- [WoW] A table gives each section a rectangle (`X`, `Y`, `Width`, `Height`) in a layout. The Accessory section exists only in the 1024x512 layout. (read) — [wowdev.wiki CharComponentTextureSections](https://wowdev.wiki/DB/CharComponentTextureSections)
- [Torchlight 2] All player armor sets use 256x256 texture pages. The main page holds the nude body map. Each armor piece is one PNG with alpha on top of it. (read) — [Runic Games armor set guidelines](https://docs.runicgames.com/wiki/Armorset_Guidelines.html)
- [Torchlight 2] Where the armor PNG has alpha, the base skin shows through. Up to five such PNG files stack on the main page. (read) — [Runic Games armor set guidelines](https://docs.runicgames.com/wiki/Armorset_Guidelines.html)
- [Valheim] An armor item has two parts. A skinned mesh renderer holds the extra pieces. An armor material holds `_ChestTex` and `_LegsTex`, and the game pastes these on the chest and legs of the player. (snippet) — [CustomTextures mod docs](https://thunderstore.io/c/valheim/p/cjayride/CustomTextures)
- [WoW] A forum poster says the body textures are mirrored. Thus armor geometry can be asymmetric, but a body texture cannot. (snippet, forum) — [Blizzard forum](https://us.forums.blizzard.com/en/wow/t/so-we-can-have-asymmetrical-shoulder-pads/2178925/1)
- [WoW] A player post says "armor in wow is mostly textures". All parts other than shoulders, buckles, and helmets rely on textures. (read, forum, 09/2024) — [Blizzard forum](https://eu.forums.blizzard.com/en/wow/t/armor-fitting-tool-idea/534704)
- [General] An MMORPG developer writes that the merge of textures and the attachment of meshes "is not very lightweight". That developer baked NPC textures for clients. (snippet) — [GameDev.net blog](https://gamedev.net/blogs/entry/2267803-animations-and-equipment)

**Technique 6: recolor or palette swap of one mesh**

- [RS2 2004] The seven platebody items from bronze to rune all name the same worn models: `man_torso_platemail` and `man_arms_platemail`. Each item has its own `recolNs` and `recolNd` pairs. (read) — [Content platebodies.obj](https://github.com/LostCityRS/Content/blob/274/scripts/skill_combat/configs/melee/platebodies.obj)
- [RS2 2004] `Model.recolour(src, dst)` reads each face. If the face colour equals `src`, the client sets it to `dst`. No texture is necessary. (read) — [Client-TS Model.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/dash3d/Model.ts)
- [WoW] Models are often used again across items with a new texture. Wowhead tracks this in a "Uses same model" tab. (read) — [Warcraft Wiki](https://warcraft.wiki.gg/wiki/Character_model)
- [Guild Wars 2, 2010 design post] Each armor piece has up to four dye channels. A channel is roughly one cut or one material of the piece. (snippet) — [Kill Ten Rats summary of the ArenaNet post](https://www.killtenrats.com/2010/09/29/guild-wars-2-dye-atribe)
- [Guild Wars 2] A former developer says weapons have no dye because the richer dye system changed how artists author source art. That change added time and complexity. (snippet, forum, page not confirmed) — [GW2 forum](https://en-forum.guildwars2.com/discussion/29101/please-make-all-or-most-backpacks-able-to-be-dyed)
- [Quaternius pack, 2026] Each of the 12 modular outfits ships with 3 texture variations. (read) — [Quaternius on itch.io](https://quaternius.itch.io/modular-character-outfits-fantasy)

**Technique 7: mesh merge into one draw call**

- [RS2 2004] The client merges up to 12 part models into one model, then caches the result. The cache holds 200 models, and a hash of the appearance is the key. (read) — [Client-TS ClientPlayer.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/dash3d/ClientPlayer.ts)
- [Unreal, UE5] Skeletal Mesh Merge has high setup cost, medium game thread cost, and low render thread cost. It cannot use morph targets. (read) — [Epic docs](https://dev.epicgames.com/documentation/en-us/unreal-engine/working-with-modular-characters-in-unreal-engine)
- [Unreal, UE5] The Epic page recommends "one common Material" and a texture atlas for merged characters. (read) — [Epic docs](https://dev.epicgames.com/documentation/en-us/unreal-engine/working-with-modular-characters-in-unreal-engine)
- [Unreal Mutable, UE5] The Mutable overview says it merges meshes to decrease draw calls. It also "removes hidden parts to maximize performance and avoid z-fighting". (snippet) — [Epic Mutable overview](https://dev.epicgames.com/documentation/unreal-engine/mutable-overview-in-unreal-engine?lang=en-US)
- [Synty Sidekick, Unity] The bake option "combines all skinned mesh renderers into one" prefab. (snippet) — [Synty store](https://syntystore.com/products/sci-fi-soldiers-sidekick-modular-characters)
- [Unity] The built-in draw call batching of Unity does not batch skinned mesh renderers. (snippet) — [Unity manual](https://docs.unity3d.com/cn/2022.1/Manual/DrawCallBatching.html)

**Technique 8: morph targets to fit gear to body types**

- [Synty Sidekick] Blend shapes cover body type and proportions, and also facial expressions. (snippet) — [Synty store](https://syntystore.com/products/sci-fi-soldiers-sidekick-modular-characters)
- [Unreal, UE5] Leader Pose and Copy Pose keep morph targets. Skeletal Mesh Merge loses them. (read) — [Epic docs](https://dev.epicgames.com/documentation/en-us/unreal-engine/working-with-modular-characters-in-unreal-engine)
- [RS2 2004] The game uses no morph. An item names separate man and woman models. A shared weapon model gets a vertical offset for the woman (`womanwear=human_weapons_dh-sword,6`). (read) — [Content 2hswords.obj](https://github.com/LostCityRS/Content/blob/274/scripts/skill_combat/configs/melee/2hswords.obj)
- [General] An older Leadwerks thread concludes that clothes must be modeled for each body type. A low-poly RPG developer on Polycount asks the same question and gets no answer. (snippet, forum) — [Leadwerks](https://www.leadwerks.com/community/topic/15003-modular-character-setup), [Polycount](https://polycount.com/discussion/comment/2809050/)

### Inferences

The table is the judgment of the researcher. It applies the findings to a solo developer with a low-poly style.

| Technique | Art cost for each item | Runtime cost | Clipping risk | Fit for Blackout |
|---|---|---|---|---|
| 1 Rigid attachment | Low: one mesh and one offset | One draw call for each item | Low | High for weapons, shields, hats, packs |
| 2 Skinned gear, shared skeleton | Medium: weights for each item | One draw call for each part | Medium | High for torso, arms, legs |
| 3 Part replacement | Medium: the item is the body part | Same as technique 2 | Lowest: no skin stays below | High. This is the OSRS model |
| 4 Geosets | High: all variants live in the body file | Low | Low | Low. It needs one large authored body |
| 5 Texture layers | Low for each item, high to set up | A texture bake on each change | None | Low. Every part needs one shared UV layout |
| 6 Recolor | Almost none | None | None | High. It multiplies each mesh |
| 7 Mesh merge | None | Fewest draw calls, one bake for each look | None | Optional. Add it after a measurement |
| 8 Morph targets | High | Extra vertex work | Medium | Low. Use two body types with offsets |

- Techniques 2 and 3 are the same engine feature in Godot: more than one `MeshInstance3D` on one `Skeleton3D`. The difference is art policy. Technique 3 deletes the body part that the item covers.
- Flat face colors, as in OSRS, make technique 6 almost free. A texture atlas with a palette row gives the same effect on a UV-mapped pack.
- Technique 5 fits a game with one authored body and one UV layout. Art from many CC0 packs has many UV layouts. Thus technique 5 fits Blackout badly.

### Gaps

- The research found no measured numbers for draw calls or skinning cost in Godot 4 with the GL Compatibility renderer. The Godot thread that asks the question has no benchmark.
- The Epic table does not give a clear physics value for Skeletal Mesh Merge.
- The Mutable page body did not load. The Mutable finding is from a search snippet only.
- Two godotforums.org threads and all Polycount pages did not load. Their findings carry the label (page not confirmed).
- The research found no developer source for Albion Online, Brighter Shores, or RuneScape 3 on any of the eight techniques.

## 2. How do Old School RuneScape and RuneScape 2 do it?

### Takeaway

A player is 12 appearance slots and 5 color indexes. Each slot holds nothing, an identity kit, or an item. An item replaces the kit in its slot and can blank two more slots. The client merges the part models into one model, recolors the faces, caches the model, and moves it by vertex labels.

### Cited Findings

**The appearance block**

- [RS2 2004] The client reads 12 appearance values and 5 color values for each player. A value of 0 means nothing. A value from 256 to 511 is an identity kit ID plus 256. A value of 512 or more is an item ID plus 512. (read) — [Client-TS ClientPlayer.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/dash3d/ClientPlayer.ts)
- [OSRS 2026] The RuneLite API keeps the same scheme with a new item offset: `KIT_OFFSET = 256` and `ITEM_OFFSET = 2048`. `getColors()` always returns 5 values. (read) — [RuneLite PlayerComposition.java](https://github.com/runelite/runelite/blob/master/runelite-api/src/main/java/net/runelite/api/PlayerComposition.java)
- [OSRS 2026] The 12 slots in order are HEAD, CAPE, AMULET, WEAPON, TORSO, SHIELD, ARMS, LEGS, HAIR, HANDS, BOOTS, JAW. (read) — [RuneLite KitType.java](https://github.com/runelite/runelite/blob/master/runelite-api/src/main/java/net/runelite/api/kit/KitType.java)
- [RS2 2004] The server names for the same slots are hat 0, back 1, front 2, righthand 3, torso 4, lefthand 5, arms 6, legs 7, head 8, hands 9, feet 10, jaw 11. Ring is 12 and quiver is 13. (read) — [Engine-TS ObjType.ts](https://github.com/LostCityRS/Engine-TS/blob/274/src/cache/config/ObjType.ts)
- [RS2 2004] The appearance loop writes slots 0 to 11 only. Thus a ring and a quiver have a wear position but never show on the model. (read) — [Engine-TS Player.ts](https://github.com/LostCityRS/Engine-TS/blob/274/src/engine/entity/Player.ts)
- [OSRS] The OSRS Wiki describes the jaw slot as a hidden slot that holds facial hair. An item in the jaw slot removes the facial hair from the model. (snippet) — [OSRS Wiki, Worn Equipment](https://oldschool.runescape.wiki/w/Worn_Equipment)

**Identity kits**

- [RS2 2004] An identity kit (`IdkType`) has a `part` type, a list of model IDs, six recolor pairs (`recol_s`, `recol_d`), five chat head model IDs, and a `disable` flag. (read) — [Client-TS IdkType.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/config/IdkType.ts)
- [RS2 2004] The male kit file has seven types: `man_hair`, `man_jaw`, `man_torso`, `man_arms`, `man_hands`, `man_legs`, `man_feet`. A separate `woman.idk` file exists. (read) — [Content man.idk](https://github.com/LostCityRS/Content/blob/274/scripts/player/configs/man.idk)
- [RS2 2004] One kit can stack two models. `man_torso_buttons` is `man_torso_basic` plus `man_torsoextra_buttons`. (read) — [Content man.idk](https://github.com/LostCityRS/Content/blob/274/scripts/player/configs/man.idk)
- [RS2 2004] The server maps seven body choices to seven slots: hair to slot 8, jaw to 11, torso to 4, arms to 6, hands to 9, legs to 7, feet to 10. (read) — [Engine-TS Player.ts](https://github.com/LostCityRS/Engine-TS/blob/274/src/engine/entity/Player.ts)
- [OSRS 2026] The current kit definition has `bodyPartId`, `models`, `chatheadModels` (5), `recolorToFind`, `recolorToReplace`, `retextureToFind`, `retextureToReplace`, and `nonSelectable`. (read) — [RuneLite KitDefinition.java](https://github.com/runelite/runelite/blob/master/cache/src/main/java/net/runelite/cache/definitions/KitDefinition.java)
- [RS2 2004] The model files follow the same split: `models/human/man/arms`, `feet`, `hands`, `legs`, `torso`, and `models/human/weapons/human_weapons_*.ob2`. (read) — [Content models/human](https://github.com/LostCityRS/Content/tree/274/models/human)

**How an item replaces or hides a body part**

- [RS2 2004] The server collects `wearpos2` and `wearpos3` of every worn item into a skip list. It writes 0 for each slot in that list. For each other slot it writes the item, or the kit if no item is there. (read) — [Engine-TS Player.ts](https://github.com/LostCityRS/Engine-TS/blob/274/src/engine/entity/Player.ts)
- [RS2 2004] Rune platebody: `wearpos=torso`, `wearpos2=arms`, `manwear=man_torso_platemail,0`, `manwear2=man_arms_platemail`. The item carries its own arm model and blanks the arms kit. (read) — [Content platebodies.obj](https://github.com/LostCityRS/Content/blob/274/scripts/skill_combat/configs/melee/platebodies.obj)
- [RS2 2004] Rune chainbody: `wearpos=torso` only, with one model for each gender. The arms kit of the player stays visible. (read) — [Content chainbodies.obj](https://github.com/LostCityRS/Content/blob/274/scripts/skill_combat/configs/melee/chainbodies.obj)
- [RS2 2004] Rune full helm: `wearpos=hat`, `wearpos2=head`, `wearpos3=jaw`. It blanks the hair and the beard. (read) — [Content fullhelms.obj](https://github.com/LostCityRS/Content/blob/274/scripts/skill_combat/configs/melee/fullhelms.obj)
- [RS2 2004] Rune med helm: `wearpos=hat`, `wearpos2=head`. It blanks the hair and keeps the beard. (read) — [Content medhelms.obj](https://github.com/LostCityRS/Content/blob/274/scripts/skill_combat/configs/melee/medhelms.obj)
- [RS2 2004] Rune 2h sword: `wearpos=righthand`, `wearpos2=lefthand`. The two-handed weapon blanks the shield slot. (read) — [Content 2hswords.obj](https://github.com/LostCityRS/Content/blob/274/scripts/skill_combat/configs/melee/2hswords.obj)

**Item model fields**

- [RS2 2004] An item has `manwear`, `manwear2`, `manwear3`, `womanwear`, `womanwear2`, `womanwear3`, one offset for each gender, and `manhead`, `manhead2`, `womanhead`, `womanhead2` for the chat head. (read) — [Client-TS ObjType.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/config/ObjType.ts)
- [RS2 2004] The client moves the worn model by the gender offset, then applies the recolor pairs of the item. (read) — [Client-TS ObjType.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/config/ObjType.ts)
- [OSRS 2026] The fields are `maleModel0`, `maleModel1`, `maleModel2`, `maleOffset`, `maleHeadModel`, `maleHeadModel2`, and the same six for female. The defaults are -1. (read) — [RuneLite ItemDefinition.java](https://github.com/runelite/runelite/blob/master/cache/src/main/java/net/runelite/cache/definitions/ItemDefinition.java)
- [OSRS 2026] The item also has `wearPos1`, `wearPos2`, `wearPos3`, `colorFind`, `colorReplace`, `textureFind`, `textureReplace`, and `resizeX`, `resizeY`, `resizeZ` with a default of 128. (read) — [RuneLite ItemDefinition.java](https://github.com/runelite/runelite/blob/master/cache/src/main/java/net/runelite/cache/definitions/ItemDefinition.java)
- [OSRS 2026] Opcodes: 23 and 25 read the first male and female model with the offset. 24, 26, 78, 79 read the second and third models. 90 to 93 read the head models. (read) — [RuneLite ItemLoader.java](https://github.com/runelite/runelite/blob/master/cache/src/main/java/net/runelite/cache/definitions/loaders/ItemLoader.java)
- [OSRS 2026] Opcode 40 reads the recolor pairs and opcode 41 reads the retexture pairs. Opcodes 13, 14, and 27 read the three wear positions. Opcodes 44 to 54 read the same models with 32-bit IDs. (read) — [RuneLite ItemLoader.java](https://github.com/runelite/runelite/blob/master/cache/src/main/java/net/runelite/cache/definitions/loaders/ItemLoader.java)
- [OSRS 2026] A player can carry a `ColorTextureOverride` for each slot. It replaces the colors and textures of the item in that slot. It applies to item slots only. (read) — [RuneLite PlayerComposition.java](https://github.com/runelite/runelite/blob/master/runelite-api/src/main/java/net/runelite/api/PlayerComposition.java)

**The merge**

- [RS2 2004] The client collects one model for each non-empty slot, kit or item. Then it calls `Model.combineForAnim(models, modelCount)`. (read) — [Client-TS ClientPlayer.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/dash3d/ClientPlayer.ts)
- [RS2 2004] The merge copies each face. `addPoint` uses an existing vertex again when a new vertex has the same x, y, and z. Thus two parts with equal seam vertices join with no gap. (read) — [Client-TS Model.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/dash3d/Model.ts)
- [RS2 2004] The merge keeps the vertex label and the face label of each part. The merged model animates as one model. (read) — [Client-TS Model.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/dash3d/Model.ts)
- [RS2 2004] After the merge, the client applies the 5 player colors: hair, torso, legs, feet, skin. Each one is a `recolour` from the default color to the chosen color. (read) — [Client-TS ClientPlayer.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/dash3d/ClientPlayer.ts)
- [RS2 2004] The client then computes the lighting one time and stores the model in an LRU cache of 200 entries. The key is a hash of the 12 slots, the 5 colors, and the gender. (read) — [Client-TS ClientPlayer.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/dash3d/ClientPlayer.ts)
- [RS2 2004] If a part model is not downloaded yet, the client shows the last cached model of that player. (read) — [Client-TS ClientPlayer.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/dash3d/ClientPlayer.ts)
- [RS2 2004] With the `lowMemory` flag of a player set, the client returns the cached model and skips the animation step. (read) — [Client-TS ClientPlayer.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/dash3d/ClientPlayer.ts)

**The animation**

- [RS2 2004] The classic client has no bone hierarchy and no vertex weights. Each vertex has one label. Each face can have one label. (read) — [Client-TS Model.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/dash3d/Model.ts)
- [RS2 2004] An animation base (`AnimBase`) is a list of entries. Each entry has a transform type and a list of labels. The types are ORIGIN 0, TRANSLATE 1, ROTATE 2, SCALE 3, and TRANSPARENCY 5. (read) — [Client-TS AnimBase.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/dash3d/AnimBase.ts)
- [RS2 2004] ORIGIN sets a pivot at the average position of all vertices in its labels, plus an offset. ROTATE and SCALE then act on their labels around that pivot. (read) — [Client-TS Model.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/dash3d/Model.ts)
- [RS2 2004] TRANSPARENCY changes the alpha of the faces in its face labels. (read) — [Client-TS Model.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/dash3d/Model.ts)
- [RS2 2004] `maskAnimate` mixes two frames. Labels in the `walkmerge` list of the sequence take the walk frame. All other labels take the primary frame. (read) — [Client-TS Model.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/dash3d/Model.ts)
- [RS2 2004] A sequence can replace the held items for its duration through `replaceheldleft` and `replaceheldright`. The cooking sequence sets both to `hide`. (read) — [Client-TS SeqType.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/config/SeqType.ts), [Content cooking_sources.seq](https://github.com/LostCityRS/Content/blob/274/scripts/skill_cooking/configs/cooking_source/cooking_sources.seq)
- [OSRS 2026] The current sequence definition keeps these as `leftHandItem`, `rightHandItem`, and `interleaveLeave`. It also has `animMayaID`, `animMayaStart`, `animMayaEnd`, and `animMayaMasks`. (read) — [RuneLite SequenceDefinition.java](https://github.com/runelite/runelite/blob/master/cache/src/main/java/net/runelite/cache/definitions/SequenceDefinition.java)

### Inferences

- The system is techniques 3, 6, and 7 together. No texture bake and no skeleton are necessary.
- The gear model needs no fit to a body below it, because no body is below it. This removes most clipping work from the artist.
- The merge works because every part for one slot ends at the same seam vertices. A kit and an item for the same slot must share that seam.
- A label works like a bone with a weight of 1. An item model animates correctly only if its vertices carry the same label numbers as the body part it replaces.
- A modern engine can get the same result with rigid skin: each vertex has full weight on one bone of a shared skeleton.
- The `animMaya` fields show that current OSRS has a second animation path next to the frame list. The name suggests a skeletal path. The research did not confirm this.
- The cache by appearance hash helps most when many players wear the same gear. That is common in an MMO.

### Gaps

- The research found no Jagex developer blog or talk that describes this system. All findings come from open-source reconstructions and from RuneLite.
- The format of a face color (16-bit HSL, from memory) has no source in these notes. RuneLite stores `colorFind` as `short[]`, which confirms 16 bits only.
- The meaning of `animMayaID` and the date of that change are not confirmed.
- The research did not read how OSRS picks the stance animations of a weapon in 2026. The 2004 data is in question 6.

## 3. How does World of Warcraft do it?

### Takeaway

WoW uses four techniques on one character. Geosets change the outline of the body mesh. Armor textures go on body texture regions. Helms, shoulders, and weapons are separate models on attachment points. From Legion on, some armor pieces are skinned models on the character skeleton.

### Cited Findings

**Geosets**

- [WoW] The geoset groups include: 00xx hair, 01xx to 03xx facial hair, 04xx gloves, 05xx boots, 07xx ears, 08xx sleeves, 09xx kneepads, 10xx chest, 11xx pants, 12xx tabard, 13xx robe or trousers, 15xx cape, 18xx belt. (read) — [wowdev.wiki Character Customization](https://wowdev.wiki/Character_Customization)
- [WoW, later expansions] Higher groups add 20xx toes, 22xx torso, 23xx hand attachments, 26xx shoulders, 27xx helm, 28xx upper arm, and 29xx to 31xx replacement arms, legs, and feet. (read) — [wowdev.wiki Character Customization](https://wowdev.wiki/Character_Customization)
- [WoW] Slot rules: gloves enable 401 plus `geosetGroup[0]`. Boots enable 501 plus `geosetGroup[0]`. With no boots, the client shows 2001. A cape uses the 1501 group. (read) — [wowdev.wiki ItemDisplayInfo](https://wowdev.wiki/DB/ItemDisplayInfo)
- [WoW] The glove group has four shapes: 1 default, 2 thin, 3 folded, 4 thick. (read) — [wowdev.wiki ItemDisplayInfo](https://wowdev.wiki/DB/ItemDisplayInfo)
- [WoW] The wiki lists the shape variants: forearm has base, gloves, folded, and bulky. Lower leg has base, boots, folded, bulky, and heavy boots. A cloak has eight shapes. (read) — [Warcraft Wiki](https://warcraft.wiki.gg/wiki/Character_model)
- [WoW 3.3.5] The item display table of that version has three geoset group columns, `GeosetGroup_0` to `GeosetGroup_2`. (snippet) — [TrinityCore ItemDisplayInfo](https://trinitycore.info/files/DBC/335/itemdisplayinfo)

**The item display table**

- [WoW 0.5.3 to 6.x] `ItemDisplayInfo` holds `modelName[2]`, `modelTexture[2]`, `geosetGroup[3 or 4]`, `flags`, `helmetGeosetVis[1 or 2]`, `texture[8 or 9]`, and `itemVisual`. (read) — [wowdev.wiki ItemDisplayInfo](https://wowdev.wiki/DB/ItemDisplayInfo)
- [WoW 7.0, 2016] The body textures of an item move to a separate table, `ItemDisplayInfoMaterialRes`. (read) — [wowdev.wiki ItemDisplayInfo](https://wowdev.wiki/DB/ItemDisplayInfo)
- [WoW 6.0 and later] Flags include 0x040 inherit the animation of the character, 0x080 mirror the shoulder animation, 0x100 mirror a weapon in the off hand, and 0x200 clip the lower tabard geoset. (read) — [wowdev.wiki ItemDisplayInfo](https://wowdev.wiki/DB/ItemDisplayInfo)
- [WoW 3.3.5] The server item row points at the display row through `displayid`. The display row gives both the model and the icon. (read) — [TrinityCore item_template](https://trinitycore.info/database/335/world/item_template)

**The helm**

- [WoW 6.0.1] `HelmetGeosetVisData` holds `hideGeoset[7]` for groups 0, 100, 200, 300, 700, 1600, and 1700. Legion adds 2400 and 2500. (read) — [wowdev.wiki HelmetGeosetVisData](https://wowdev.wiki/DB/HelmetGeosetVisData)
- [WoW] Each field is a race bitmask. The test is `(flag & (1 << race)) > 0`. If it is true, the client sets that mesh group back to its default value. (read) — [wowdev.wiki HelmetGeosetVisData](https://wowdev.wiki/DB/HelmetGeosetVisData)
- [WoW] Each helm display row has two such values. Version 8.1.5 replaced the table, because the races no longer fit in 32 bits. (read) — [wowdev.wiki HelmetGeosetVisData](https://wowdev.wiki/DB/HelmetGeosetVisData)

**Attachment points and 3D armor**

- [WoW] A weapon model usually has 5 attachment points of its own. Glow effect models attach there. A mount uses ID 0 for the rider. (read) — [wowdev.wiki M2](https://wowdev.wiki/M2)
- [WoW, later eras] The attachment list grew: 53 BeltBuckle in Mists of Pandaria, 55 HeadTop in Legion, 57 Backpack in Battle for Azeroth. (read) — [wowdev.wiki M2](https://wowdev.wiki/M2)
- [WoW] Two players describe the system in 09/2024. Most sets have up to four attached models: two shoulders, a belt buckle, and a helmet. All other parts rely on textures. (read, forum) — [Blizzard forum](https://eu.forums.blizzard.com/en/wow/t/armor-fitting-tool-idea/534704)
- [WoW, Legion and later] The same post: some sets add 3D elements through a "collection". Specific bones of the character model move its vertices. (read, forum) — [Blizzard forum](https://eu.forums.blizzard.com/en/wow/t/armor-fitting-tool-idea/534704)
- [WoW] The fit cost, from the same thread: "Only Helmets are actually adjusted to fit different heads." Collections also need an adjustment for every player model. (read, forum) — [Blizzard forum](https://eu.forums.blizzard.com/en/wow/t/armor-fitting-tool-idea/534704)
- [WoW] A second player lists the parts that still need a custom fit: "Especially helms, 3d modeled shoes and 3d gloves." (read, forum) — [Blizzard forum](https://eu.forums.blizzard.com/en/wow/t/armor-fitting-tool-idea/534704)

### Inferences

- The names of attachment points 11, 5, and 6 (Helm, ShoulderRight, ShoulderLeft) and the two `modelName` columns agree with the player description: a helm is one rigid model, and shoulders are two.
- WoW pays for cheap items with an expensive body. Each race and gender model must hold every geoset variant and one fixed UV layout.
- The history of WoW goes from techniques 4 and 5 toward technique 2. The reason in the sources is the "painted on skin" look.
- For a solo developer, the WoW helm table is the useful idea: one small record for each helm says which head groups to hide.

### Gaps

- The research found no Blizzard talk or engineering post on this system. The wowdev page marks the body texture compositing method as not documented.
- The pixel rectangles of each body region are in the game data. The wiki pages do not list them.
- The research did not confirm a `ModelResourcesID` column or the storage of collection models from a wiki page.
- The path of the body texture files (`item/texturecomponents/...`) comes from a forum snippet. The research did not confirm the thread.

## 4. How do other games do it, in short form?

### Takeaway

The games fall into two families. Bethesda games, Torchlight 2, and Final Fantasy XIV hide body sections for each item. Valheim and the Unreal and Unity samples put skinned parts on a shared skeleton and merge when draw calls matter. Developer sources are thin for several named games.

### Cited Findings

**Skyrim (2011)**

- [Skyrim] The biped slot numbers include 30 head, 32 body, 33 hands, 37 feet, and 42 circlet. Some numbers are free for modders, such as 46 and 49. (snippet) — [UESP Creation Kit wiki](https://ck.uesp.net/wiki/Skyrim_bodyparts_number)
- [Skyrim] The ArmorAddon record (ARMA) has a body template, male and female priority bytes, male and female models for third person and first person, base textures, and a race list. (read) — [UESP ARMA format](https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format/ARMA)
- [Skyrim] A modder explains that bracers overwrite the arm section. The game does not render body parts that other worn items cover, such as feet and calves below boots. (snippet, forum, page not confirmed) — [Nexus forum](https://forums.nexusmods.com/topic/546769-anyone-think-its-possible-to-add-new-dismemberment-partitions)
- [Skyrim] An item can list more slots to hide more of the body. A long glove can use the hand slot and also list the forearm slot. (snippet, forum) — [Nexus forum](https://forums.nexusmods.com/topic/8660818-help-getting-started)

**Torchlight 2 (2012)**

- [Torchlight 2] The Material ID list has base and extra pairs: 1 Chest and 2 Exchest, 7 Calf and 8 EXCalf, 13 Forearm and 14 EXForearm, 15 Hand and 16 EXHand, 17 Pauldrons, 18 Helmet. (read) — [Runic Games armor set guidelines](https://docs.runicgames.com/wiki/Armorset_Guidelines.html)
- [Torchlight 2] Base IDs are geometry tied to the base body. Extra IDs are alpha and floating geometry. The game can cull floating geometry when armor overlaps it. (read) — [Runic Games armor set guidelines](https://docs.runicgames.com/wiki/Armorset_Guidelines.html)
- [Torchlight 2] The seams at the neck, forearm, and calf "MUST be exactly adhered to." (read) — [Runic Games armor set guidelines](https://docs.runicgames.com/wiki/Armorset_Guidelines.html)

**Valheim (2021)**

- [Valheim] Armor uses techniques 2 and 5 together. See the Valheim findings in question 1. — [Valheim-Modding wiki](https://github-wiki-see.page/m/Valheim-Modding/Wiki/wiki/Attaching-Weapons-and-Armor)

**Final Fantasy XIV**

- [FFXIV] A model converter gives an in-game path of this form: `chara/equipment/e0000/model/c0000e0000_top.mdl`. (snippet) — [FFXIVModelConverter](https://github.com/AlexCSDev/FFXIVModelConverter)
- [FFXIV] A modder guide lists metadata entries for each item that hide body sections: "hide legs/waist", "hide elbow", "hide wrist", "hide knee", "hide shins". (snippet, forum) — [Katami modding guide](https://katami.carrd.co/)

**Unreal samples and tools**

- [Lyra, UE5] A third-party guide says a helper Blueprint uses the `FLyraCharacterPart` struct. It defines each cosmetic part that the game spawns and attaches at runtime. (snippet) — [Ready Player Me Lyra guide](https://docs.readyplayer.me/ready-player-me/~/changes/vTOZnVwWwImk1VIbinB6/integration-guides/unreal-engine/code-samples/lyra-project-integration-example)
- [Mutable, UE5, guide for v5.5] Mutable has a Remove Mesh modifier node. A community guide tells artists to group UVs into blocks, so that a later customization can remove a whole block. (snippet) — [Epic Python API](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/CustomizableObjectNodeModifierRemoveMesh), [Mutable community wiki](https://github-wiki-see.page/m/anticto/Mutable-Documentation/wiki/texture-layouts-(v5.5))

**Unity packs**

- [Synty Sidekick] Parts use the Unity Humanoid skeleton. A character creator tool in the editor combines parts from more than one pack. A runtime API changes characters in a built game. (snippet) — [Synty store](https://syntystore.com/products/sci-fi-soldiers-sidekick-modular-characters)
- [Synty Modular Fantasy Hero] A GameDev.tv forum answer (Brian_Trotter) says this pack needs the least preparation for an equipment system. Its armor is already grouped by slot. (read, forum) — [GameDev.tv](https://community.gamedev.tv/t/equipping-armor/235633)

**CC0 packs for a low-poly game**

- [Quaternius, v2.1, 07/2026] The fantasy outfit pack has 12 outfits from 62 modular parts. It uses a Humanoid rig and is compatible with the Universal Base Characters and the Universal Animation Library. (read) — [Quaternius on itch.io](https://quaternius.itch.io/modular-character-outfits-fantasy)
- [Quaternius, v2.0, 01/2026] Version 2.0 gives less clipping between combined parts. All models then work with only the head of a base character. The page lists the license as CC0. (read) — [Quaternius on itch.io](https://quaternius.itch.io/modular-character-outfits-fantasy)
- [Quaternius] A blog post that read the glTF files reports one 65-joint skeleton across the base characters, the outfits, and the animation library. (snippet) — [Cinevva blog](https://app.cinevva.com/tr/blog/2026-05-10-open-world-browser-part-25-universal-characters)
- [KayKit] A guide reports that all KayKit packs are CC0 and that the character packs share one rig. (snippet) — [Cinevva guide](https://app.cinevva.com/fr/guides/free-rigged-3d-character-models)

**Brighter Shores**

- [Brighter Shores, 2024] The game runs on Fenforge, the engine of Fen Research. (snippet) — [Wikipedia](https://en.wikipedia.org/wiki/Brighter_Shores)

### Inferences

- The Quaternius outfit pack already follows technique 3. A body section and its outfit part are the same thing, and only the head is separate.
- A secondary guide says later Quaternius releases use a new license. Read the license on each download page.
- Skyrim, Torchlight 2, and FFXIV all keep a hide list on the item. That agrees with `wearpos2` and `wearpos3` in RuneScape.

### Gaps

- Fallout: the Fallout 4 Creation Kit page returned HTTP 403. A snippet says only that its slot numbers differ from Skyrim.
- Skyrim: the research did not confirm how the priority bytes settle a slot conflict. One forum poster says "I think".
- FFXIV: the research found no page on the `atr_` mesh attributes or the `shp_` shape keys. Four searches failed.
- Guild Wars 2: no source says how the client stores or draws a dye channel.
- Albion Online, Brighter Shores, RuneScape 3: no technical source found.
- Destiny: the GDC 2014 talk "Building Customizable Characters for Bungie's Destiny" exists on the [GDC Vault](https://gdcvault.com/play/1020412/Building-Customizable-Characters-for-Bungie). The research could not read its slides.
- Lyra: the research did not read the engine source. It did not confirm that character parts use a leader pose.

## 5. How do games stop clipping between body and gear, and between two gear items?

### Takeaway

The shipped answer is to delete or hide the skin below gear. No game in this research solves clipping with collision or cloth. Each item carries a small hide list, and a fixed slot order settles a conflict between two items.

### Cited Findings

- [RS2 2004] Hide list on the item: `wearpos2` and `wearpos3` blank up to two more slots. A blanked slot shows nothing, not even an item in that slot. (read) — [Engine-TS Player.ts](https://github.com/LostCityRS/Engine-TS/blob/274/src/engine/entity/Player.ts)
- [RS2 2004] Replacement: the worn model stands in for the body part, so no skin exists below it. (read) — [Client-TS ClientPlayer.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/dash3d/ClientPlayer.ts)
- [WoW] Slot priority: when several slots set the same geoset group, the client uses a fixed order. Gloves outrank chest and shirt. A belt outranks a tabard. (read) — [wowdev.wiki ItemDisplayInfo](https://wowdev.wiki/DB/ItemDisplayInfo)
- [WoW] Chest `geosetGroup[2]` outranks pants `geosetGroup[2]`. Pants outrank boots. A non-zero value from a higher item makes the client ignore the lower items. (read) — [wowdev.wiki ItemDisplayInfo](https://wowdev.wiki/DB/ItemDisplayInfo)
- [WoW] The helm rule is a table, not a mesh test. See the helm findings in question 3. — [wowdev.wiki HelmetGeosetVisData](https://wowdev.wiki/DB/HelmetGeosetVisData)
- [Torchlight 2] Clothing types hide the model parts that overlap. A long-sleeve shirt hides the glove parts above the wrist. (read) — [Runic Games armor set guidelines](https://docs.runicgames.com/wiki/Armorset_Guidelines.html)
- [Torchlight 2] Fixed seams at the neck, forearm, and calf let any two pieces meet. (read) — [Runic Games armor set guidelines](https://docs.runicgames.com/wiki/Armorset_Guidelines.html)
- [Skyrim] Body partitions: the game does not draw a body partition that a worn item claims. An item can claim more slots to hide more. (snippet, forum) — [Nexus forum](https://forums.nexusmods.com/topic/546769-anyone-think-its-possible-to-add-new-dismemberment-partitions)
- [Unreal Mutable] The tool removes hidden mesh parts at build time of the character. One stated reason is to prevent z-fighting. (snippet) — [Epic Mutable overview](https://dev.epicgames.com/documentation/unreal-engine/mutable-overview-in-unreal-engine?lang=en-US)
- [General] A forum answer gives the runtime rule: collect the meshes that the character wears, mark the meshes that outer layers cover as "not drawn", and draw the others. (snippet, forum) — [GameDev.net](https://gamedev.net/forums/topic/710077-how-to-implement-a-modular-clothing-system)
- [General] The same thread gives the cause of clipping. If the clothes do not share the topology of the body, skin comes through at joints. The repair is an outward offset for each piece. (snippet, forum) — [GameDev.net](https://gamedev.net/forums/topic/710077-how-to-implement-a-modular-clothing-system)
- [General] An open collar or an open jacket shows the inside of the mesh. The artist must model the inside or use two-sided geometry. (snippet, forum) — [GameDev.net](https://gamedev.net/forums/topic/710077-how-to-implement-a-modular-clothing-system)
- [Godot, 09/2017, before Godot 3] One poster puts the body faces below the clothes in a vertex group and deletes them at export. The poster warns: "you can accidentally save file with deleted faces". (read, forum) — [Godot forum](https://forum.godotengine.org/t/how-can-i-hide-poly-behind-clothes/30980)
- [Godot, 09/2017] The same answer lists three more options. Paint better weights on the clothes. Offset the clothing vertices in a vertex shader. Hide body faces with an occlusion map. (read, forum) — [Godot forum](https://forum.godotengine.org/t/how-can-i-hide-poly-behind-clothes/30980)
- [Unity] A GameDev.tv forum answer stores "what to equip and what to remove" on the item. A helmet removes the hair. A new chest item removes all other chest armor. (read, forum) — [GameDev.tv](https://community.gamedev.tv/t/equipping-armor/235633)
- [Quaternius] Version 2.0 of the outfit pack lists "less clipping when combining parts" as a change. (read) — [Quaternius on itch.io](https://quaternius.itch.io/modular-character-outfits-fantasy)

### Inferences

- Three rules cover all the cases found: fixed seams, a hide list on the item, and one fixed slot order.
- Gear against gear is a design problem. RuneScape permits one item for each slot and no layers. Thus two torso items never meet.
- Rigid items clip the most with hair. Every game here solves that with a flag on the helm that hides the hair.
- No source describes an alpha mask on the body mesh in a shipped game. Torchlight 2 uses alpha only on the texture, to show skin through armor.

### Gaps

- The research found no source for "body slices" as a named technique outside Skyrim partitions and Torchlight 2 Material IDs.
- The research found no data on how OSRS artists make sure that a new item matches the seam of each kit.
- The research found no source on cape or cloak clipping with a weapon on the back.

## 6. How do games show a sheathed weapon, a drawn weapon, and one-hand and two-hand grips?

### Takeaway

WoW stores a sheath type on the item and has attachment points for the hands and for the sheath places. RuneScape has no sheath state. Its weapon model is one more part of the merged body, and the slot data and the animation IDs carry the grip.

### Cited Findings

**World of Warcraft**

- [WoW 3.3.5] The item row has a `sheath` field. 1 is a two-handed weapon across the back, point down. 2 is a staff across the back, point up. 3 is one-handed at the left side of the waist. (read) — [TrinityCore item_template](https://trinitycore.info/database/335/world/item_template)
- [WoW 3.3.5] The other values: 4 is a shield at the middle of the back. 7 is an off hand item at the right side of the waist. (read) — [TrinityCore item_template](https://trinitycore.info/database/335/world/item_template)
- [WoW 3.3.5] `InventoryType` gives the grip class: 13 WEAPON, 14 SHIELD, 15 RANGED, 17 2HWEAPON, 21 WEAPONMAINHAND, 22 WEAPONOFFHAND, 23 HOLDABLE, 26 RANGEDRIGHT. (read) — [TrinityCore item_template](https://trinitycore.info/database/335/world/item_template)
- [WoW] The model has points for the hands (1 HandRight, 2 HandLeft, 0 Shield) and for the sheath places (26 SheathMainHand, 27 SheathOffHand, 28 SheathShield, 54 SheathCrossbow). (read) — [wowdev.wiki M2](https://wowdev.wiki/M2)
- [WoW] More points exist for large and hip weapons: 30 LargeWeaponLeft, 31 LargeWeaponRight, 32 HipWeaponLeft, 33 HipWeaponRight. 49 is ShieldNoGlove. (read) — [wowdev.wiki M2](https://wowdev.wiki/M2)
- [WoW] An item display flag (0x100) mirrors the weapon model when it is in the off hand. (read) — [wowdev.wiki ItemDisplayInfo](https://wowdev.wiki/DB/ItemDisplayInfo)

**RuneScape 2 and OSRS**

- [RS2 2004] A weapon is a worn model in slot 3 (righthand). A shield is a worn model in slot 5 (lefthand). The client merges both into the body model. (read) — [Client-TS ClientPlayer.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/dash3d/ClientPlayer.ts)
- [RS2 2004] Men and women share one weapon model. The woman value has a vertical offset of 6. Kiteshield: `manwear=human_weapons_kiteshield,0` and `womanwear=human_weapons_kiteshield,6`. (read) — [Content kiteshields.obj](https://github.com/LostCityRS/Content/blob/274/scripts/skill_combat/configs/melee/kiteshields.obj)
- [RS2 2004] A two-handed weapon is data, not a grip type: `wearpos=righthand` plus `wearpos2=lefthand`. (read) — [Content 2hswords.obj](https://github.com/LostCityRS/Content/blob/274/scripts/skill_combat/configs/melee/2hswords.obj)
- [RS2 2004] The appearance block carries seven animation IDs for each player: ready, turn, walk, walk back, walk left, walk right, and run. The server thus picks the stance set. (read) — [Client-TS ClientPlayer.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/dash3d/ClientPlayer.ts)
- [RS2 2004] The item names its attack animations as parameters. The rune 2h sword has `param=slashattack_anim,human_dhsword_slash` and a `category=weapon_2h_sword`. (read) — [Content 2hswords.obj](https://github.com/LostCityRS/Content/blob/274/scripts/skill_combat/configs/melee/2hswords.obj)
- [RS2 2004] A sequence can hide or replace the items in the hands. See `replaceheldleft` and `replaceheldright` in question 2. — [Client-TS SeqType.ts](https://github.com/LostCityRS/Client-TS/blob/274/src/config/SeqType.ts)
- [RS2 2004] Some held items have a second model for the left hand, for example `human_weapons_bannana_left.ob2` and `human_weapons_bottleofrum_left.ob2`. (read) — [Content models/human/weapons](https://github.com/LostCityRS/Content/tree/274/models/human/weapons)

**Other engines**

- [Lyra, UE5] The equipment definition names the actors to spawn, a socket for each, an attachment transform for each, and the ability sets to grant. (read) — [X157 Lyra notes](https://x157.github.io/UE5/LyraStarterGame/Equipment/)
- [Valheim] The player rig keeps named attach objects, for example `LeftHand_Attach` below the `LeftHand` bone. The wiki tells the artist not to delete them. (read) — [Valheim-Modding wiki](https://github-wiki-see.page/m/Valheim-Modding/Wiki/wiki/Attaching-Weapons-and-Armor)
- [General] One indie devlog reports a weapon that sat outside the hand. The rig had no hand socket. The repair was a socket on the model. (snippet) — [itch.io devlog](https://itch.io/devlog/749156/problem-with-asset-attachment.amp)

### Inferences

- A RuneScape weapon has no socket and no offset transform. The artist models it at the hand position of the rest pose and gives its vertices the label of the hand. The research did not read the weapon labels to confirm this.
- OSRS has no sheathed state at all. A camera above the player and a low-poly style make that omission cheap. A solo developer can copy it.
- The minimum weapon data across these games: a model, a hand slot, a flag or a second slot for two hands, a stance animation set, and an attack animation set.
- A socket design adds an offset transform for each item, and a sheath socket if the game shows a sheathed state.
- The WoW flag that mirrors an off-hand weapon, and the RuneScape `_left` models, solve the same problem in two ways.

### Gaps

- The research found no source on how Skyrim, Fallout, FFXIV, or Guild Wars 2 store sheath nodes or grip data.
- The research did not confirm how Lyra links an animation layer to a weapon.
- The research did not read which server code in RS2 sets the seven animation IDs from the weapon.

## 7. What do experienced developers recommend for a small team or a solo developer with a low-poly style?

### Takeaway

The advice agrees on four points. Use one skeleton and never change it. Group gear by slot and hide what a slot covers. Attach rigid items to bones. Do not start texture bakes or mesh merges before a measurement shows a need.

### Cited Findings

- [Unity] A GameDev.tv forum answer (Brian_Trotter) calls a modular armor system "no simple task" and "far into the advanced category". His setup for one pack took about a month. His scripts are "MONTHS of work and fine tuning". (read, forum) — [GameDev.tv](https://community.gamedev.tv/t/equipping-armor/235633)
- [Unity] The same answer: build all modular armor on "the exact same skeleton". Put all chest armor in one object, all gloves in one object, and so on. (read, forum) — [GameDev.tv](https://community.gamedev.tv/t/equipping-armor/235633)
- [Unity] The same answer: use one script that "rebuilds the character from the ground up based on the equipped items" on each equipment change. (read, forum) — [GameDev.tv](https://community.gamedev.tv/t/equipping-armor/235633)
- [Unity] The same answer: most character packs are whole characters, not modular. He rates two such packs at about 1 of 10 for this use. Research a pack before you buy it. (read, forum) — [GameDev.tv](https://community.gamedev.tv/t/equipping-armor/235633)
- [Godot 4, 08/2026] A forum poster says the hide and show method works well for a limited set of clothes. Attachment by code is harder and has no tutorials. (read, forum) — [Godot forum](https://forum.godotengine.org/t/character-customization-in-godot-3d/59840)
- [Godot] Forum advice: do not optimize the skeleton of a part file and do not remove unused bones. (snippet, forum, page not confirmed) — [Godot Forums](https://godotforums.org/d/40518-accessories-for-3d-characters)
- [Godot 4] Forum advice: export each clothing item with the rig but with no animations. (snippet, forum, page not confirmed) — [Godot Forums](https://godotforums.org/d/28258-3d-rigged-animated-characters-and-interchangeable-clothing)
- [Unreal, UE5] Epic recommends the leader pose method as the first setup. It has the lowest setup cost. Mesh merge has the highest setup cost. (read) — [Epic docs](https://dev.epicgames.com/documentation/en-us/unreal-engine/working-with-modular-characters-in-unreal-engine)
- [Polycount] One modular knight project put the pivot of every piece at the same location, so that pieces swap easily. The author warns that more than 60 meshes become hard to manage without order. (snippet, forum) — [Polycount](https://polycount.com/discussion/170951/modular-knight-characters)
- [Polycount] One poster notes a limit of the deform-the-body method: hard plate then deforms the same way as soft cloth, and designs look alike. (snippet, forum, page not confirmed) — [Polycount](https://polycount.com/discussion/comment/1737185)
- [MMO developer] A client must know what each character wears to build it. The developer thought about a cache of player appearances. (snippet) — [GameDev.net blog](https://gamedev.net/blogs/entry/2267803-animations-and-equipment)
- [Guild Wars 2] The team kept dye off weapons because the authoring cost was too high for a small visual gain. (snippet, forum, page not confirmed) — [GW2 forum](https://en-forum.guildwars2.com/discussion/29101/please-make-all-or-most-backpacks-able-to-be-dyed)
- [WoW, 09/2024] Players say helms, 3D shoes, and 3D gloves need a custom fit for each race. Only shoulders and buckles avoid it, through attachment points with a fixed scale. (read, forum) — [Blizzard forum](https://eu.forums.blizzard.com/en/wow/t/armor-fitting-tool-idea/534704)
- [RS2 2004] The reference low-poly MMO ships seven platebody tiers from two meshes for each gender. (read) — [Content platebodies.obj](https://github.com/LostCityRS/Content/blob/274/scripts/skill_combat/configs/melee/platebodies.obj)

### Inferences

The researcher recommends this stack for Blackout. It is a judgment from the findings, not a quoted source.

1. Use one humanoid skeleton for every player model. Freeze the bone list before the first item.
2. Split the body at fixed seams into kit parts: head, torso, arms, hands, legs, feet. Each part is a skinned mesh on the shared skeleton.
3. Make a worn item replace the kit part in its slot. Give each item a model for each body type and a hide list of up to two more slots.
4. Attach weapons, shields, hats, and packs to bones. Give each item one offset transform. Hide the hair with a flag on the helm.
5. Make tiers by recolor. One mesh then gives a full tier ladder.
6. Show no sheathed state at first. Let a two-handed weapon blank the off-hand slot through its data.
7. Keep the server in charge of the slot list, as RuneScape does. The client only draws the parts that the server names.
8. Add a merged mesh with a cache by appearance hash only after a measurement shows a draw call problem.

- The art budget decides the technique more than the engine does. Technique 3 with recolor needs one mesh for each shape, not for each item.
- The largest stated regret is time. Developers report months for the system, and more for each body type.
- Two body types multiply every skinned item by two. Rigid items escape that cost with an offset, as RuneScape weapons do.
- A CC0 pack that is already modular on one rig removes the most expensive step. The Quaternius outfit pack is one candidate.
- Avoid technique 5 and technique 8 as a solo developer. Each one needs a single authored body that all the art obeys.

### Gaps

- The research found no postmortem from an indie MMO that names a regret about its equipment technique. The closest sources are forum threads and one course instructor.
- The research could not read any GDC talk on this topic. The Destiny talk is the best candidate.
- Two pages with likely advice returned errors: the Polycount wiki page on the Skankerzero modular character system, and a GameDev.net blog on a Unity equipment system.
- The research found no advice specific to web export or to many players on screen with low-poly models.
