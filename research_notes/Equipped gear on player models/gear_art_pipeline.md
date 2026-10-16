# Art and asset pipeline for character equipment: Blender to glTF, one shared skeleton, and asset packs

Research date: 2026-10-11. The findings paraphrase each source. Open the URL for the exact wording. The note "(search summary)" marks a page that the search tool reported and that I did not open.

## 1. Skeleton standard: bone names, bone count, socket bones, and rest pose

### Takeaway
Godot gives a fixed humanoid name set (`SkeletonProfileHumanoid`, 56 bones) and a fixed reference pose: T-pose, +Z forward, Y up, no node transform. No standard that I found defines socket bones. Unreal, Roblox, and Synty each add their own named attach points to the body bones.

### Cited Findings
- `SkeletonProfileHumanoid` lists 56 bones in the Godot 4.7 docs. The chain starts `Root` > `Hips`. Each leg is `UpperLeg` > `LowerLeg` > `Foot` > `Toes`. The spine is `Spine` > `Chest` > `UpperChest` > `Neck` > `Head`. `Head` holds `Jaw`, `LeftEye`, and `RightEye`. Each arm is `Shoulder` > `UpperArm` > `LowerArm` > `Hand`. Each limb name has a `Left` or `Right` prefix. — [Godot docs, SkeletonProfileHumanoid](https://docs.godotengine.org/en/stable/classes/class_skeletonprofilehumanoid.html)
- Each hand has 15 finger bones: `ThumbMetacarpal`, `ThumbProximal`, `ThumbDistal`, and `Proximal`, `Intermediate`, `Distal` for `Index`, `Middle`, `Ring`, and `Little`. — [Godot docs, SkeletonProfileHumanoid](https://docs.godotengine.org/en/stable/classes/class_skeletonprofilehumanoid.html)
- The profile is a read-only preset for the human form. It has four groups: `Body`, `Face`, `LeftHand`, `RightHand`. The list holds no weapon, back, hip, or shield bone. — [Godot docs, SkeletonProfileHumanoid](https://docs.godotengine.org/en/stable/classes/class_skeletonprofilehumanoid.html)
- Godot states five rules for the humanoid reference pose. The model is in T-pose. It faces +Z in a right-handed Y-up system. The skeleton has no transform as a node. The +Y axis of each bone points from the parent joint to the child joint. A +X rotation bends the joint as a muscle does. — [Godot docs, Retargeting 3D Skeletons](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/retargeting_3d_skeletons.html)
- Equal bone names are not sufficient to share an animation in Godot. The bone rests must also agree. — [Godot docs, Retargeting 3D Skeletons](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/retargeting_3d_skeletons.html)
- The bone rest depends on the export tool. A glTF file from Blender carries the edit bone orientation as the rest rotation. A glTF file from Maya can carry no rest rotation. — [Godot docs, Retargeting 3D Skeletons](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/retargeting_3d_skeletons.html)
- The Godot importer has four rest fixes. "Apply Node Transform" repairs a skeleton that has a node transform, for example a Blender export with no applied transform. "Overwrite Axis" replaces each bone rest with the rest of the profile. "Fix Silhouette" moves an A-pose model toward the T-pose. A T-pose model does not need it. "Normalize Position Tracks" scales position tracks by the height of `Hips`. — [Godot docs, Retargeting 3D Skeletons](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/retargeting_3d_skeletons.html)
- The Godot docs warn that "Overwrite Axis" gives bad results when the original bone rest is important. — [Godot docs, Retargeting 3D Skeletons](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/retargeting_3d_skeletons.html)
- The bone map of Godot matches names by pattern. The docs recommend common English bone names. — [Godot docs, Retargeting 3D Skeletons](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/retargeting_3d_skeletons.html)
- VRM 1.0 requires 15 humanoid bones: `hips`, `spine`, `head`, and the upper leg, lower leg, foot, upper arm, lower arm, and hand of each side. `chest`, `upperChest`, `neck`, the eyes, `jaw`, the shoulders, the toes, and all finger bones are optional. — [VRM 1.0 humanoid specification](https://github.com/vrm-c/vrm-specification/blob/master/specification/VRMC_vrm-1.0/humanoid.md)
- VRM requires a positive scale on each humanoid bone. It states that usually only `hips` moves and the other bones only rotate. — [VRM 1.0 humanoid specification](https://github.com/vrm-c/vrm-specification/blob/master/specification/VRMC_vrm-1.0/humanoid.md)
- Unreal names a set of weapon bones in its IK Retargeter defaults. `hand_r` is the skinned right hand. `hand_attach_r` is an optional bone for a prop in the right hand. `ik_hand_gun` sits at the right hand and is the parent of `ik_hand_l` and `ik_hand_r`. `weapon_l` is the default weapon bone of the left hand. — [Epic docs, IKRetargetWeaponGoalsOpSettings](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/IKRetargetWeaponGoalsOpSettings) (search summary)
- A marketplace rig listing shows the Unreal mannequin names: `root`, `pelvis`, `spine_01` to `spine_05`, `ik_foot_root`, `ik_foot_l`, `ik_foot_r`, `ik_hand_root`, `ik_hand_gun`, `ik_hand_l`, `ik_hand_r`. — [Fab listing](https://www.fab.com/listings/ba808e15-04e6-4b54-ad36-43b02c789003) (search summary, exact listing not confirmed)
- Roblox defines one named attachment point for each accessory type: `HatAttachment`, `HairAttachment`, `FaceFrontAttachment`, `FaceCenterAttachment`, `NeckAttachment`, `LeftShoulderAttachment`, `RightShoulderAttachment`, `LeftCollarAttachment`, `RightCollarAttachment`, `BodyFrontAttachment`, `BodyBackAttachment`, `WaistFrontAttachment`, `WaistCenterAttachment`, `WaistBackAttachment`. A shoulder point moves with the arm. A collar point stays with the torso. — [Roblox docs, Accessory specifications](https://create.roblox.com/docs/art/accessories/specifications)
- glTF 2.0 lets a joint node carry other nodes, and also a full subtree with meshes. The spec gives a sword in a hand as its example. — [glTF 2.0 specification, Skins](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#skins)
- `BoneAttachment3D` in Godot 4.7 attaches to one bone, by `bone_name` or `bone_idx`, and copies the transform of that bone. With `use_external_skeleton`, the node can sit outside the skeleton and point at it through `external_skeleton`. — [Godot docs, BoneAttachment3D](https://docs.godotengine.org/en/stable/classes/class_boneattachment3d.html)
- KayKit uses two rigs for all its characters: `Rig_Medium` for regular characters and `Rig_Large` for large characters. — [KayKit Character Animations](https://kaylousberg.itch.io/kaykit-character-animations)
- Quaternius states that Universal Base Characters and Modular Character Outfits work with the Universal Animation Library. Each of those pages names a humanoid rig for retargeting. The Universal Animation Library 2 page names a universal humanoid rig and says that it complements the first library. — [Quaternius, Universal Base Characters](https://quaternius.com/packs/universalbasecharacters.html), [Quaternius, Modular Character Outfits - Fantasy](https://quaternius.com/packs/modularcharacteroutfitsfantasy.html), [Quaternius, Universal Animation Library 2](https://quaternius.com/packs/universalanimationlibrary2.html)
- A practitioner on Tech-Artists.org describes a studio method: rig and skin in A-pose, and put offsets in the control rig to reach T-pose for retargeting. — [Tech-Artists.org](https://www.tech-artists.org/t/which-is-better-for-rigging-a-pose-or-t-pose/18456) (search summary)
- A blog states that the Unreal Engine 4 mannequin uses T-pose and that the Unreal Engine 5 mannequins use A-pose. The source is a company blog with low authority. — [Neural4D blog](https://blog.neural4d.com/?p=3575) (search summary)

### Inferences
- The Godot humanoid names are the natural standard for this project. The client is Godot, and the two large CC0 animation libraries target a humanoid retarget.
- A T-pose rest that faces +Z with no node transform needs the fewest import fixes in Godot. An A-pose rest gives better shoulders but needs "Fix Silhouette" or an equal step in the build.
- A low-poly body with no fingers can use the 15 required VRM bones plus `Root`, `Neck`, the shoulders, and the toes. That gives about 21 body bones. This count is my estimate, not a sourced rule.
- Socket bones must be extra bones outside the humanoid profile. A workable list is `hand_r`, `hand_l`, `head`, `back`, `hip_l`, `hip_r`, and `shield`. The names follow the Unreal and Roblox pattern of one named point for each attach location.
- A socket must be a real bone in the skin, not an empty child node. Section 4 gives the two reasons: the Blender deform-only option and the glTF Transform `prune` defaults.

### Gaps
- I found no primary source for the Mixamo bone names in this session.
- I found no source that gives a recommended bone count for low-poly characters.
- I found no authoritative rule for the position and the axes of a socket bone. Each engine and pack sets its own.
- I did not confirm the hand slot bone names of the KayKit rigs. The pack pages do not list bone names.
- The Godot docs describe the bone map and the rest fixes as editor import options. I did not confirm that a runtime `GLTFDocument` load can apply them.

## 2. Blender workflow for skinned gear on one base body

### Takeaway
Artists model the gear over the base body, copy the weights from the body with the Data Transfer modifier, and bind the gear to the same armature. I found no confirmed recipe for Godot that binds a gear mesh from a second `.glb` to the skeleton of the body at runtime. Forum users report failures and use show and hide of meshes in one file.

### Cited Findings
- The Data Transfer modifier copies data from a source mesh to the modified mesh. The Blender 5.2 LTS manual lists the vertex mappings: Topology (by index, equal counts only), Nearest Vertex, Nearest Edge Vertex, Nearest Face Vertex, Nearest Face Interpolated, and Projected Face Interpolated. — [Blender manual, Data Transfer modifier](https://docs.blender.org/manual/en/latest/modeling/modifiers/modify/data_transfer.html)
- "Generate Data Layers" adds each vertex group that the source has and the target does not have. The modifier does not make these layers automatically. The layers stay after the artist removes the modifier. — [Blender manual, Data Transfer modifier](https://docs.blender.org/manual/en/latest/modeling/modifiers/modify/data_transfer.html)
- "Max Distance" stops a match between elements that are too far apart. The manual says to clear "Object Transform" when the two meshes do not overlap in world space. — [Blender manual, Data Transfer modifier](https://docs.blender.org/manual/en/latest/modeling/modifiers/modify/data_transfer.html)
- A Godot forum guide (author roboticy3, June 30, 2025, Godot 4.4.1, Blender 4.4) cuts the body mesh into parts. It uses a Data Transfer modifier so that each cut part keeps the normals and the weights of the original body. It exports with "Visible Objects" and "Apply Modifiers" set. — [Godot forum, 3D RPG clothing and inventory system](https://forum.godotengine.org/t/3d-rpg-clothing-and-inventory-system-using-godot-4-and-blender/114842)
- The same guide warns that an Armature modifier left on the original mesh causes lighting faults. It also warns that a new import of a `.glb` can reset the bone map. — [Godot forum, 3D RPG clothing and inventory system](https://forum.godotengine.org/t/3d-rpg-clothing-and-inventory-system-using-godot-4-and-blender/114842)
- A Godot 4.5 user (January 8, 2026) compares two layouts. One `.glb` for each outfit loads less, but each new animation needs a new export of every file. One `.glb` with all outfits keeps each outfit as a `MeshInstance3D` to show or hide, and the node count grows with each outfit. The thread gives no runtime bind method. — [Godot forum, Managing scalability of skeleton, animation and outfits](https://forum.godotengine.org/t/managing-scalability-of-skeleton-animation-and-outfits-for-3d-characters-from-blender-to-godot/130681)
- A Godot 4.4.1 user exported the skeleton as one `.glb` and each gear piece as its own `.glb`. The parent step in Blender worked. The parent step inside Godot failed, and a write to the `skeleton` property seemed to do nothing. — [Godot forum, Parent MeshInstance to skeleton](https://forum.godotengine.org/t/parent-meshinstance-to-skeleton/107687) (search summary)
- A Godot 4.4 thread (August 18 to 20, 2025) found no method that assigns a `Skeleton3D` to a `MeshInstance3D` at runtime. The user went back to show and hide of child meshes. — [Godot forum, How to assign a Skeleton3D to a MeshInstance3D](https://forum.godotengine.org/t/gdscript-how-to-assign-a-skeleton3d-to-a-meshinstance3d/119829)
- `MeshInstance3D.skeleton` is a `NodePath` to the `Skeleton3D` of the instance. Its default is an empty path in the Godot 4.7 docs. The default changed in Godot 4.6. The project setting `animation/compatibility/default_parent_skeleton_in_mesh_instance_3d` restores the old behavior. — [Godot docs, MeshInstance3D](https://docs.godotengine.org/en/stable/classes/class_meshinstance3d.html)
- `MeshInstance3D.skin` holds the `Skin` of the instance. `Skin` has `add_bind(bone, pose)`, `add_named_bind(name, pose)`, `set_bind_name`, `set_bind_bone`, and `set_bind_pose`. The Godot 4.7 class page has no description for the class or for any method. — [Godot docs, Skin](https://docs.godotengine.org/en/stable/classes/class_skin.html)
- One `Skin` can serve meshes under more than one `Skeleton3D`. Godot then keeps one `SkinReference` for each pair. — [Godot docs, SkinReference](https://docs.godotengine.org/fr/4.3/classes/class_skinreference.html) (search summary)
- glTF 2.0 applies only the joint transforms to a skinned mesh. A loader must ignore the transform of the skinned mesh node. — [glTF 2.0 specification, Skins](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#skins)
- The order of `skin.joints` must match the order of the inverse bind matrices. Each matrix brings the skinned coordinates into the space of its joint. — [glTF 2.0 specification, Skins](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#skins)
- In Unreal, a child mesh on the Leader Pose method must match the joint structure of the leader. An extra or a skipped joint renders in the reference pose. — [Epic docs, Working with Modular Characters (UE 5.8)](https://dev.epicgames.com/documentation/en-us/unreal-engine/working-with-modular-characters-in-unreal-engine)
- A Blender 3.4 exporter fix repaired the export of a skinned mesh when "selection only" left the armature out. — [Blender extensions commit list, November 2022](https://lists.blender.org/pipermail/bf-extensions-cvs/2022-November/011197.html) (search summary)
- A blog names unapplied scale on the armature or the mesh as a cause of a skin that tears away from its bones. Its fix is to apply scale on both objects before export. The source has low authority. — [Bugnet blog](https://bugnet.io/blog/how-to-fix-imported-character-mesh-and-skeleton-scale-mismatch-explodes) (search summary)
- Polycount users say that a weight transfer works when the general edge flow of the gear matches the body. They also say that a vest and a shirt clip in a forward bend when their loops do not match. — [Polycount](https://polycount.com/discussion/comment/2636650) (search summary)
- An armor artist on Polycount recommends a well-skinned nude body before any gear, and a straight edge loop at each seam between gear and body. — [Polycount](https://polycount.com/discussion/comment/2228444) (search summary)
- Quaternius fixed two glTF exports in July 2026 that held the meshes of another outfit by error. — [Quaternius itch.io, Modular Character Outfits - Fantasy changelog](https://quaternius.itch.io/modular-character-outfits-fantasy)

### Inferences
- One master `.blend` must own the armature. Each gear file must link or append that armature and must not edit it. Then every export carries equal bone names and an equal rest pose.
- A gear `.glb` that holds the armature and no body is valid glTF. The skin carries its own joint list and its own inverse bind matrices.
- The client must bind a gear mesh to the body skeleton by bone name. `Skin.add_named_bind` exists for this, but the docs do not describe it. A test in Godot 4.7 must prove the method before the standard depends on it.
- The likely causes of a gear mesh that explodes or shifts follow from the cited rules:
  1. The rest pose of the gear file differs from the rest pose of the body file, so the inverse bind matrices disagree.
  2. The mesh or the armature has an unapplied scale or rotation.
  3. The loader binds by joint index, and the two files list the joints in a different order.
  4. The artist moved the gear object in Blender. glTF ignores the node transform of a skinned mesh, so the offset goes away.
  5. One file went through a rest fix such as "Overwrite Axis" and the other file did not.
  6. The `skeleton` path of the `MeshInstance3D` is empty, which is the default since Godot 4.6.
- The prevention is one checklist: same armature, applied transforms at scale 1.0, export at rest, bind by name, and one import path for body and gear.

### Gaps
- I did not open the Blender manual page for the "Transfer Weights" operator. The Data Transfer modifier page is the only primary source here.
- I found no primary source that states the joint order that the Blender exporter writes, or that the order is stable between files.
- I found no working, documented Godot 4.x recipe for a runtime bind of a second `.glb` to an existing `Skeleton3D`. An itch.io product named "Modular 3D Character System - Godot 4.7.x" exists, and I did not open it: [imp0str on itch.io](https://imp0str.itch.io/modular-3d-character-system).

## 3. Blender workflow for rigid gear: origin, axis, and hands

### Takeaway
The common rule is to put the grip of a weapon at the world origin before export, so that the item lands on the hand socket with no offset. I found no shared standard for the forward axis. Each project picks one axis and documents it.

### Cited Findings
- An Unreal forum answer says to put the handle of a sword at the world origin in the modeling tool. That point becomes the pivot at export. Then the sword attaches to the hand socket with no offset. — [Unreal Engine answers](https://answers.unrealengine.com/questions/243098/view.html) (search summary)
- A guide from MoCap Online says that the socket sets the position and the rotation offset of the weapon, and that the weapon follows the hand through every animation. — [MoCap Online, Weapon Animation Systems](https://mocaponline.com/blogs/mocap-news/weapon-animation-systems-guide) (search summary)
- For a two-handed weapon, the dominant hand drives the weapon and the other hand follows a point on the weapon. — [MoCap Online, Weapon Animation Systems](https://mocaponline.com/blogs/mocap-news/weapon-animation-systems-guide) (search summary)
- A Polycount thread describes the same method for animation: parent the weapon to the dominant hand, then constrain the support hand. — [Polycount](https://polycount.com/discussion/comment/1661826) (search summary)
- Unreal keeps the two-hand targets as bones: `ik_hand_gun` at the right hand, with `ik_hand_l` and `ik_hand_r` as its children. — [Epic docs, IKRetargetWeaponGoalsOpSettings](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/IKRetargetWeaponGoalsOpSettings) (search summary)
- A Godot answer says to parent the gun to the bone in Blender, not to the armature. Godot then imports the relation as a bone attachment. Users report an offset after import. — [Godot Q&A](https://ask.godotengine.org/143779/how-to-attach-a-gun-to-a-hand-bone-in-blender-for-import) (search summary)
- Roblox requires a rigid accessory to be one mesh of at most 4,000 triangles. It measures the size limits from the attachment point. — [Roblox docs, Accessory specifications](https://create.roblox.com/docs/art/accessories/specifications)
- KayKit Adventurers ships 25 or more weapons and accessories as items apart from the characters. The helmet of the Knight and the helmet of the Barbarian are removable parts. — [KayKit Adventurers](https://kaylousberg.itch.io/kaykit-adventurers)
- A community project for KayKit in Godot adds bone attachments by the KayKit animation guide. The project dates from Godot 3. — [doctor-g/KayKitAnimationInGodot](https://github.com/doctor-g/KayKitAnimationInGodot) (search summary)
- Synty Sidekick lists its rigid attachment locations: head, face, back, shoulder, elbow, knee, and hip (front, back, left, right). — [Synty Store, Sci-Fi Civilians Sidekick](https://syntystore.com/products/sci-fi-civilians-sidekick-modular-character-pack)

### Inferences
- The build pipeline of this project can bake a rotation, a scale, and an offset into each served file. Thus the standard can demand one result for every rigid item: grip at the origin and one fixed axis.
- A simple rule set follows from the sources. A one-handed item has its grip at the origin. A two-handed item has the grip of the dominant hand at the origin, and the record stores a second point for the support hand. An off-hand item uses the same file on the `hand_l` socket, with a mirror flag if the shape is not symmetric.
- A helmet has its origin at the `head` socket. A backpack has its origin at the `back` socket. Each socket bone then needs one documented axis, and each item agrees with it.
- A sheathed position is a second socket name plus an offset in the item record. The model file does not change.

### Gaps
- I found no authoritative source for a forward axis such as blade along +Y or -Z. The search gave forum posts only.
- No pack page that I read states the origin or the axis of its weapons.
- The sources disagree on whether the support hand uses IK at runtime or a baked animation. This project needs a decision, not a citation.

## 4. glTF export from Blender, the glTF rules for skins, and glTF Transform

### Takeaway
The Blender exporter has a small set of options that decide whether a gear file matches the body: "Apply Modifiers", "+Y Up", "Use Rest Position Armature", the deform-only option, and Draco off. The `optimize` command of glTF Transform is unsafe for this client by default: its default compression is meshopt, and it also simplifies, joins, flattens, and prunes.

### Cited Findings
Blender exporter (Blender 4.5 LTS manual):
- "Apply Modifiers" exports the evaluated mesh. "+Y Up" uses the glTF convention. "Custom Properties" exports custom properties as glTF extras. — [Blender 4.5 manual, glTF 2.0](https://docs.blender.org/manual/en/4.5/addons/import_export/scene_gltf2.html)
- "Use Rest Position Armature" exports the rest position as the joint rest pose. With the option off, the exporter uses the pose of the current frame. — [Blender 4.5 manual, glTF 2.0](https://docs.blender.org/manual/en/4.5/addons/import_export/scene_gltf2.html)
- "Export Deformation Bones Only" exports only the deform bones and bakes their animation. The original commit says that it also keeps the bones that the hierarchy needs. — [Blender 4.5 manual, glTF 2.0](https://docs.blender.org/manual/en/4.5/addons/import_export/scene_gltf2.html), [Blender commit b9b1814a](https://developer.blender.org/rBAb9b1814a4c26f73aae7f306c9ff2e21b7b7bdcee) (commit: search summary)
- "Remove Armature Object" removes the armature object when possible. "Flatten Bone Hierarchy" is for bones with a transform that does not split into translation, rotation, and scale. — [Blender 4.5 manual, glTF 2.0](https://docs.blender.org/manual/en/4.5/addons/import_export/scene_gltf2.html)
- "Bone Influences" sets the joint count for each vertex. The manual warns that a value other than 4 or 8 can show wrongly in many viewers. "Include All Bone Influences" has the same warning. — [Blender 4.5 manual, glTF 2.0](https://docs.blender.org/manual/en/4.5/addons/import_export/scene_gltf2.html)
- Vertex colors have their own options. "Use Vertex Color" takes Material, Active, Name, or None. One option exports all vertex colors as `COLOR_1`, `COLOR_2`, and so on. One option exports the active vertex color when the object has no material. — [Blender 4.5 manual, glTF 2.0](https://docs.blender.org/manual/en/4.5/addons/import_export/scene_gltf2.html)
- The animation mode takes Actions (the default), Active Actions merged, NLA Tracks, or Scene. "Reset pose bones between actions" is necessary when an action does not key every bone. "Use Current Frame as Object Rest Transformations" uses the current frame as the object rest, and frame 0 when off. — [Blender 4.5 manual, glTF 2.0](https://docs.blender.org/manual/en/4.5/addons/import_export/scene_gltf2.html)
- "Optimize Animation Size" removes duplicate keyframes. "Force keeping channel for armature / bones" keeps a minimal animation for a rig whose keyframes are all equal. — [Blender 4.5 manual, glTF 2.0](https://docs.blender.org/manual/en/4.5/addons/import_export/scene_gltf2.html)
- The "Compression" panel enables Draco mesh compression. "GPU Instances" uses the `EXT_mesh_gpu_instancing` extension. — [Blender 4.5 manual, glTF 2.0](https://docs.blender.org/manual/en/4.5/addons/import_export/scene_gltf2.html)
- The manual path `en/latest/addons/import_export/scene_gltf2.html` returned HTTP 404 on 2026-10-11. The `en/4.5` path works. The latest manual calls itself the Blender 5.2 LTS manual. — [Blender 4.5 manual, glTF 2.0](https://docs.blender.org/manual/en/4.5/addons/import_export/scene_gltf2.html)

glTF 2.0 specification:
- A skin has a required `joints` list and an optional `inverseBindMatrices` accessor. The accessor must hold at least one matrix for each joint, in the order of the joints. — [glTF 2.0 specification, Skins](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#skins)
- All joints of a skin must have one common root node. The root can be a joint or not. The optional `skeleton` property points at that root or at one of its parents. The spec says that the skin math does not need it. — [glTF 2.0 specification, Skins](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#skins)
- `JOINTS_n` and `WEIGHTS_n` are `VEC4`, so one set holds four influences. `JOINTS_n` is uint8 or uint16. `WEIGHTS_n` is float32, or normalized uint8 or uint16. — [glTF 2.0 specification, Skins](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#skins)
- A weight must not be negative. One vertex must not name the same joint two times with a weight above zero. The spec recommends that float weights sum to about 1.0. It also recommends index 0 for a joint slot with weight zero. — [glTF 2.0 specification, Skins](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#skins)
- A loader can support only one set of joints and weights. The spec warns that the animation can then look wrong on a mesh with more sets. — [glTF 2.0 specification, Skins](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#skins)
- A node uses a skin through its `mesh` and `skin` properties. Several nodes can use the same mesh with different skins. — [glTF 2.0 specification, Instantiation](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#instantiation)
- A `COLOR_n` accessor of type `VEC3` has an assumed alpha of 1.0. — [glTF 2.0 specification, Meshes](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#meshes)
- I read the spec text from the AsciiDoc source in the Khronos repository. — [Specification.adoc](https://github.com/KhronosGroup/glTF/blob/main/specification/2.0/Specification.adoc)

glTF Transform:
- The `optimize` command runs these steps in order: `dedup`, `instance`, `palette`, `flatten`, `join`, `weld`, `simplify`, `resample`, `prune`, `sparse`, texture compression, then mesh compression. Each step except `dedup` is on by default. — [glTF Transform, cli.ts](https://github.com/donmccurdy/glTF-Transform/blob/main/packages/cli/src/cli.ts)
- The default of `--compress` is `meshopt`. The other values are `draco`, `quantize`, and `false`. The default of `--texture-compress` is `auto`, and the default of `--texture-size` is 2048. — [glTF Transform, cli.ts](https://github.com/donmccurdy/glTF-Transform/blob/main/packages/cli/src/cli.ts)
- The CLI docs warn that the `optimize` defaults do not fit every scene. — [glTF Transform CLI](https://gltf-transform.dev/cli)
- `quantize` needs `KHR_mesh_quantization` support in the loader. It sets the bit depth of indices and `JOINTS_*` automatically. `dequantize` reverses quantization. — [glTF Transform, cli.ts](https://github.com/donmccurdy/glTF-Transform/blob/main/packages/cli/src/cli.ts), [glTF Transform CLI](https://gltf-transform.dev/cli)
- `meshopt` compresses geometry, morph targets, and animation. `draco` compresses geometry. — [glTF Transform CLI](https://gltf-transform.dev/cli)
- `flatten` leaves a skeleton and its descendants in the original node structure. It does not move a node when an animation targets that node or one of its parents. — [glTF Transform, cli.ts](https://github.com/donmccurdy/glTF-Transform/blob/main/packages/cli/src/cli.ts)
- `join` joins primitives of the same mesh, and optionally of sibling nodes. Its page says nothing about skinned meshes. — [glTF Transform, join](https://gltf-transform.dev/modules/functions/functions/join)
- `weld` merges vertices that are bitwise identical. `resample` removes duplicate keyframes with no loss. `dedup` removes duplicate accessors and textures. — [glTF Transform, cli.ts](https://github.com/donmccurdy/glTF-Transform/blob/main/packages/cli/src/cli.ts), [glTF Transform CLI](https://gltf-transform.dev/cli)
- The `prune` defaults are `keepLeaves: false`, `keepAttributes: false`, `keepSolidTextures: false`, and `keepExtras: false`. — [glTF Transform, prune.ts](https://github.com/donmccurdy/glTF-Transform/blob/main/packages/functions/src/prune.ts)
- With `keepLeaves: false`, `prune` deletes a node that has no children and no user. A skin that lists the node as a joint is a user. An animation channel that targets the node is a user. — [glTF Transform, prune.ts](https://github.com/donmccurdy/glTF-Transform/blob/main/packages/functions/src/prune.ts)
- With `keepAttributes: false`, `prune` removes an unused `TEXCOORD_n`, an unused `NORMAL` or `TANGENT`, and each `COLOR_n` above `COLOR_0`. It keeps `COLOR_0`. It does not touch `POSITION`, `JOINTS_0`, or `WEIGHTS_0`. It skips a primitive with no material. — [glTF Transform, prune.ts](https://github.com/donmccurdy/glTF-Transform/blob/main/packages/functions/src/prune.ts)
- `keepExtras` decides whether custom extras stop the removal of a property. `keepSolidTextures: false` turns a one-color texture into a material factor. — [glTF Transform, PruneOptions](https://gltf-transform.dev/modules/functions/interfaces/PruneOptions)
- `palette` builds palette textures from the scalar values of the materials and merges the materials. A material that already uses texture coordinates is not eligible. — [glTF Transform, cli.ts](https://github.com/donmccurdy/glTF-Transform/blob/main/packages/cli/src/cli.ts)
- Godot node name suffixes such as `-col`, `-noimp`, `-loop`, and the material suffix `-vcol` belong to the editor import. The docs recommend a `GLTFDocumentExtension` for a runtime import with explicit behavior. — [Godot docs, Node type customization](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/node_type_customization.html)

### Inferences
- Export settings that follow from the findings: "+Y Up" on, "Apply Modifiers" on, "Use Rest Position Armature" on, "Bone Influences" at 4, Draco off, "GPU Instances" off, and "Custom Properties" on if the pipeline reads extras.
- Each gear file and the body file must export from the same rest pose. "Use Rest Position Armature" makes that independent of the pose on screen.
- "Export Deformation Bones Only" removes a socket bone that is not a deform bone and is not necessary for the hierarchy. The standard must mark each socket bone as a deform bone, or keep the option off.
- An empty socket node is an empty leaf. The default `prune` deletes it unless a skin lists it as a joint. A socket that is a joint in every skin survives. `keepLeaves: true` also protects it.
- Safe steps for this client: `dedup`, `weld`, `resample`, and `prune` with `keepLeaves: true`. Add `keepExtras: true` if a file carries metadata in extras.
- Unsafe steps for this client: `meshopt`, `draco`, `quantize`, and thus the default `optimize`. The `instance` step makes GPU instances, which use `EXT_mesh_gpu_instancing`. The runtime loader possibly cannot read that extension.
- Steps that change the art or the structure, and need a decision: `simplify` (it removes authored low-poly detail), `join` and `flatten` (they can merge or move named nodes), `palette` (it replaces materials), and `sparse`.
- The default `prune` turns a one-color texture into a material factor. That breaks a shared palette texture only if the texture holds one color, so the risk is small.
- The Godot `-vcol` suffix does not act at runtime. The client must set the vertex color flag on its own material.

### Gaps
- I did not find the documented behavior of `join` and `simplify` on skinned primitives.
- I did not confirm that the Godot runtime loader reads sparse accessors.
- I did not find the default values of `JOIN_DEFAULTS.keepNamed` and `keepMeshes`. The CLI source refers to them by name only.

## 5. Body under gear: regions, hidden faces, and masks

### Takeaway
The standard method is to cut the body into regions and to hide or replace each region that an item covers. Old School RuneScape (OSRS), Synty Sidekick, and several packs use a list of six to eight regions. A mask texture is a secondary tool for small gaps.

### Cited Findings
- A Polycount regular describes the usual modular method: split the character into segments and replace the full segment, for example the full torso for each shirt or jacket. — [Polycount](https://polycount.com/discussion/comment/2636650) (search summary)
- A Polycount reply calls a full body under clothing inefficient. It says that the skin then clips through the clothing in some animations. — [Polycount](https://polycount.com/discussion/comment/2774754) (search summary)
- One Polycount user copies the body, deletes all faces except the bare arms, and joins the result with the shirt mesh. Another says to delete geometry that the player never sees, which also gives fewer vertices to animate. — [Polycount](https://polycount.com/discussion/comment/2636650) (search summary)
- A clothing pack on Fab slices its bodies into parts, so that the game can hide the parts under clothes. The listing gives two reasons: no intersection and a lower polygon count. — [Fab listing](https://www.fab.com/listings/445b4519-a04f-4517-a580-498ce208a782) (search summary, exact listing not confirmed)
- A Godot forum reply suggests the deletion of hidden faces at export time, and warns that the deletion can reach the working file. — [Godot forum, How can I hide poly behind clothes](https://forum.godotengine.org/t/how-can-i-hide-poly-behind-clothes/30980) (search summary)
- The Godot body groups guide defines the regions as separate meshes. Each object name is a list of groups, for example `OfficeShirt,Shirt,-Torso`. A `-` prefix means that the object hides that group when it shows. — [Godot forum, 3D RPG clothing and inventory system](https://forum.godotengine.org/t/3d-rpg-clothing-and-inventory-system-using-godot-4-and-blender/114842)
- The guide resolves the hide rules as a graph with no cycles. If item A covers B and B covers C, then A also hides C. The guide notes seams between split meshes in solid view. — [Godot forum, 3D RPG clothing and inventory system](https://forum.godotengine.org/t/3d-rpg-clothing-and-inventory-system-using-godot-4-and-blender/114842)
- The 2004 RuneScape client data, as the 2004Scape project documents it, has six body part types for each sex: hair, jaw, torso, arms, hands, and legs. — [2004Scape wiki, Configs](https://github-wiki-see.page/m/2004Scape/Server/wiki/Configs)
- The same data gives each item three wear slots: `wearpos`, `wearpos2`, and `wearpos3`. The slot values are hat, back, front, righthand, body, lefthand, arms, legs, head, hands, feet, jaw, ring, and quiver. The second and third slots override the primary slot. — [2004Scape wiki, Configs](https://github-wiki-see.page/m/2004Scape/Server/wiki/Configs)
- RuneLite lists the equipment slots of a player composition in OSRS: `HEAD`, `CAPE`, `AMULET`, `WEAPON`, `TORSO`, `SHIELD`, `ARMS`, `LEGS`, `HAIR`, `HANDS`, `BOOTS`, `JAW`. — [RuneLite API, KitType](https://static.runelite.net/runelite-api/apidocs/net/runelite/api/kit/KitType.html)
- Synty Sidekick splits a character into these skinned parts: head, hair, facial hair, eyebrows, eyes, ears, nose, teeth, tongue, torso, upper arms, lower arms, hands, hips, legs, and feet. — [Synty Store, Sci-Fi Civilians Sidekick](https://syntystore.com/products/sci-fi-civilians-sidekick-modular-character-pack)
- An itch.io modular pack splits each character into head, torso, arms, hands, legs, and feet. — [itch.io, Amir modular character pack](https://itch.io/t/5452032/-amir-the-only-modular-character-pack-youll-ever-need-low-poly-game-ready)
- Quaternius splits each character of the Ultimate Modular Men Pack into four models. The page does not name the four parts. — [Quaternius, Ultimate Modular Men Pack](https://quaternius.com/packs/ultimatemodularcharacters.html)
- Version 2.0 of the Quaternius outfits (January 29, 2026) works with only the head of a base character. The outfit parts replace the body. The author reports much less clipping between random parts after that change. — [Quaternius itch.io, Modular Character Outfits - Fantasy](https://quaternius.itch.io/modular-character-outfits-fantasy)
- Second Life users hide skin that shows through sleeves with alpha masks. — [Second Life Marketplace](https://marketplace.secondlife.com/p/Alpha-Magic-Arms-and-sleeves-masks-pack-BoM-only/22789852) (search summary)

### Inferences
- In OSRS an item that takes two or three wear slots replaces the body parts in those slots. A platebody takes the body slot and the arms slot. This reading follows from the slot data. The wiki states only that the extra slots override the primary slot.
- A region list for this project can copy the OSRS model and add the limb split of Synty: head, hair, jaw, torso, upper arms, forearms, hands, thighs, shins, feet.
- The cheapest method for a low-poly body is the "replace the segment" method. Each torso item ships its own torso mesh, and the game hides the body torso. The client then needs no mask texture.
- Each cut must sit on a straight edge loop, and the vertex normals on both sides must match. If not, a seam shows.

### Gaps
- I did not open the Polycount wiki. The Polycount findings come from forum comments through the search tool.
- I found no GDC talk on modular characters in this session.
- The Skyrim "ArmorAddon" page of the Creation Kit wiki returned HTTP 403. Its biped slot list is a known example that I did not confirm.
- The search tool reported a MetaHuman outfit on Fab with a body mask that hides the body under the clothing. I did not tie that report to one URL.

## 6. Low-poly style: palette texture, vertex colors, and item tiers

### Takeaway
The packs that fit this style use one small palette or gradient texture with UV coordinates that point into it, not vertex colors. A color variant is then a texture change. OSRS gets its tiers from one model plus pairs of "find" and "replace" colors in the item data.

### Cited Findings
- KayKit Adventurers uses one gradient atlas texture of 1024 by 1024 pixels. The author says that a user can reduce it to 128 by 128. — [KayKit Adventurers](https://kaylousberg.itch.io/kaykit-adventurers)
- The paid tier of KayKit Adventurers adds three alternative textures for each of the eight characters. The variant is a texture change on the same mesh. — [KayKit Adventurers](https://kaylousberg.itch.io/kaykit-adventurers)
- Quaternius says that most of its packs use an atlas texture, one image with colored squares. Some packs use separate materials, which the author says make color variants easier. — [Quaternius FAQ](https://quaternius.com/faq.html)
- Each Quaternius fantasy outfit has three color textures. — [Quaternius, Modular Character Outfits - Fantasy](https://quaternius.com/packs/modularcharacteroutfitsfantasy.html)
- A Godot forum post lists the benefits of a palette texture over vertex colors. The texture can hold one pixel for each color. UV data is four bytes smaller for each vertex. A texture change is easier than a change of vertex data. — [Godot forum, Vertex Colours is it only for low-poly?](https://forum.godotengine.org/t/vertex-colours-is-it-only-for-low-poly/139778) (search summary)
- A developer of Dino Frontier used one 128 by 128 swatch texture for almost every object. The reasons were consistent color and color edits after the model was done. — [Unity Discussions](https://discussions.unity.com/t/using-one-material-for-nearly-the-whole-world/682877) (search summary)
- A Unity forum answer recommends vertex colors for flat color with no texture. It warns that a swatch texture can shift color with mipmaps at distance. — [Unity Discussions](https://discussions.unity.com/t/what-would-you-suggest-for-some-flat-color-shader-with-baked-lighting/669522) (search summary)
- A Polycount comment notes the cost of hard color edges with vertex colors: the artist must split the model or add support edges, or the colors blend between vertices. — [Polycount](https://polycount.com/discussion/comment/1198300) (search summary, exact comment not opened)
- The OSRS item definition holds `colorFind` and `colorReplace` arrays, and `textureFind` and `textureReplace` arrays. — [RuneLite cache, ItemDefinition.java](https://github.com/runelite/runelite/blob/master/cache/src/main/java/net/runelite/cache/definitions/ItemDefinition.java)
- The 2004Scape config format writes the same data as `recol(n)s` (source color) and `recol(n)d` (destination color) in the RS2 HSL format. The body part configs use the same keys. — [2004Scape wiki, Configs](https://github-wiki-see.page/m/2004Scape/Server/wiki/Configs)
- RuneLite applies a recolor to model data in the Jagex HSL format. Its docs say to clone the colors first, because other objects share the model data. — [RuneLite API, ModelData](https://static.runelite.net/runelite-api/apidocs/net/runelite/api/ModelData.html) (search summary)
- The Blender exporter can write the active vertex color as `COLOR_0`. glTF Transform `prune` keeps `COLOR_0`. — [Blender 4.5 manual, glTF 2.0](https://docs.blender.org/manual/en/4.5/addons/import_export/scene_gltf2.html), [glTF Transform, prune.ts](https://github.com/donmccurdy/glTF-Transform/blob/main/packages/functions/src/prune.ts)
- The Godot editor import enables vertex color as albedo through the material suffix `-vcol`. — [Godot docs, Node type customization](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/node_type_customization.html)

### Inferences
- OSRS stores color on each face, and the item record replaces listed colors. The equal method on a GPU is a palette texture plus a row offset for each item.
- A layout that gives tiers from one mesh: each row of the palette is one material tier (bronze, iron, steel), and each column is one shade. The UV coordinates of the mesh pick the columns. The item record stores the row.
- One shared material for all gear then needs one value for each instance, the row offset. The mesh and the UV data stay equal across tiers.
- Nearest-neighbor sampling with no mipmaps prevents color bleed between palette cells. This follows from the mipmap warning.
- Vertex colors stay useful for a second purpose, such as a mask that marks which faces take the tint.

### Gaps
- I found no source that describes a palette row offset for tiers in a shipped low-poly game. The layout above is an inference.
- I found no primary source that states that the bronze, iron, and steel items of OSRS share one model. The recolor arrays exist. The shared model is common knowledge that I did not confirm.
- I did not find how Synty Sidekick stores its colors.

## 7. Per-item metadata: what a game stores beside each model

### Takeaway
The OSRS item record is the closest real schema to this project. It stores the wear slots, a model for each sex with an offset, extra models, and recolor pairs. Other systems add a named attach point and a hide list.

### Cited Findings
- The OSRS `ItemDefinition` in the RuneLite cache holds these equipment fields: `wearPos1`, `wearPos2`, `wearPos3` (default -1), `maleModel0`, `maleModel1`, `maleModel2`, `maleOffset`, `femaleModel0`, `femaleModel1`, `femaleModel2`, `femaleOffset`, `maleHeadModel`, `maleHeadModel2`, `femaleHeadModel`, `femaleHeadModel2`. — [RuneLite cache, ItemDefinition.java](https://github.com/runelite/runelite/blob/master/cache/src/main/java/net/runelite/cache/definitions/ItemDefinition.java)
- The same record holds the look of the item: `inventoryModel`, `colorFind`, `colorReplace`, `textureFind`, `textureReplace`, `resizeX`, `resizeY`, `resizeZ` (default 128), `ambient`, and `contrast`. It holds the icon view: `zoom2d`, `xan2d`, `yan2d`, `zan2d`, `xOffset2d`, `yOffset2d`. — [RuneLite cache, ItemDefinition.java](https://github.com/runelite/runelite/blob/master/cache/src/main/java/net/runelite/cache/definitions/ItemDefinition.java)
- The 2004Scape text format shows one record. The keys are `model`, `manwear=model,offset`, `manwear2`, `manwear3`, `manhead`, `manhead2`, `womanwear=model,offset`, `womanwear2`, `womanwear3`, `womanhead`, `womanhead2`, `recol1s`, `recol1d`, `wearpos`, `wearpos2`, `wearpos3`. — [2004Scape wiki, Configs](https://github-wiki-see.page/m/2004Scape/Server/wiki/Configs)
- The body part record of the same format has `type` (for example `man_hair`), `model(n)`, `head(n)`, `disable`, and the recolor pairs. — [2004Scape wiki, Configs](https://github-wiki-see.page/m/2004Scape/Server/wiki/Configs)
- Roblox binds each rigid accessory type to one attachment name on one body part. — [Roblox docs, Accessory specifications](https://create.roblox.com/docs/art/accessories/specifications)
- The Godot body groups guide stores the slot and the hide list in the object name. Its `InventoryItem` resource holds `texture`, `display_name`, `description`, `types` (the slots that the item fits), and `single`. The loader finds the gear scene by the file name of the item. — [Godot forum, 3D RPG clothing and inventory system](https://forum.godotengine.org/t/3d-rpg-clothing-and-inventory-system-using-godot-4-and-blender/114842)
- Synty Sidekick sorts each part by body location and each attachment by a named location. Its body types are blend shapes on the parts. — [Synty Store, Sci-Fi Civilians Sidekick](https://syntystore.com/products/sci-fi-civilians-sidekick-modular-character-pack)
- Blender can export custom properties as glTF extras. glTF Transform `prune` has a `keepExtras` option. — [Blender 4.5 manual, glTF 2.0](https://docs.blender.org/manual/en/4.5/addons/import_export/scene_gltf2.html), [glTF Transform, PruneOptions](https://gltf-transform.dev/modules/functions/interfaces/PruneOptions)

### Inferences
- A field list for the model record of this project follows from the OSRS schema and the other examples:
  - `slot`: the equipment slot.
  - `extra_slots`: more slots that the item takes, which is the hide list in OSRS terms.
  - `hides`: body regions that the item hides.
  - `attach`: `skinned`, or the name of a socket bone for a rigid item.
  - `offset`: position, rotation, and scale on the socket. The build can bake it into the file.
  - `sheath`: a second socket and offset for the stowed position.
  - `body_type`: the body that the mesh fits, or one model for each body.
  - `palette_row` or `recolor`: the tier color.
  - `support_hand`: a point for the second hand on a two-handed item.
  - `icon`: the camera values for the inventory picture.
- OSRS keeps this data in the item record, not in the model file. That agrees with the rule of this project that the server owns the facts and the client owns the look. The slot is a fact. The socket and the offset are a look.
- glTF extras can carry art-side data such as the socket name inside the file. The pipeline then needs `keepExtras: true`.

### Gaps
- The Creation Kit wiki page for the Skyrim "ArmorAddon" returned HTTP 403.
- A search for the Unreal Lyra character part struct gave no relevant result.
- I did not check Veloren, Luanti `3d_armor`, or OpenMW in this session.
- I found no schema that stores a sheathed position. The `sheath` field is an inference.

## 8. Asset packs: free and cheap low-poly characters and gear

### Takeaway
KayKit and Kenney state CC0 on every page that I read. Quaternius has a conflict: each pack page and the FAQ say CC0, but the license page shows a new "Quaternius Asset License v1.0" that forbids redistribution of the assets as assets. Synty and JustCreate3D are bought packs that forbid any share of the original files, and their terms put a served `.glb` in a public repository at risk.

### Cited Findings
License pages:
- Kenney states that all game assets on its asset pages have a public domain (CC0) license and that attribution is not required. The page does not discuss redistribution. It forbids use of the Kenney logo. The footer shows 2026. — [Kenney, Support](https://kenney.nl/support)
- KayKit lists CC0 1.0 Universal on each page and asks users not to sell unchanged copies or to claim the work as their own. — [KayKit Adventurers](https://kaylousberg.itch.io/kaykit-adventurers), [KayKit Character Animations](https://kaylousberg.itch.io/kaykit-character-animations)
- The Quaternius license page shows the "Quaternius Asset License (QAL) v1.0", last updated 8/28/2026. It permits free use in personal, educational, and commercial work, with no attribution. — [Quaternius, License](https://quaternius.com/license.html)
- Section 3(a) of the QAL forbids the sale or redistribution of the assets as a standalone asset, asset pack, stock file, or template, with or without payment. It permits the distribution of a finished product that holds the assets. Quaternius keeps all intellectual property rights. — [Quaternius, License](https://quaternius.com/license.html)
- Section 7 of the QAL says that a change does not apply to assets that a user got under an earlier version. The page does not name CC0 and does not list the packs that it covers. — [Quaternius, License](https://quaternius.com/license.html)
- The Quaternius FAQ and each pack page that I read on 2026-10-11 still state CC0. The itch.io pages also list CC0 1.0 Universal. This contradicts the license page. — [Quaternius FAQ](https://quaternius.com/faq.html), [Quaternius, Universal Base Characters](https://quaternius.com/packs/universalbasecharacters.html), [Quaternius itch.io, Universal Base Characters](https://quaternius.itch.io/universal-base-characters)
- Synty has two license types: a one-time purchase with perpetual rights to the bought packs, and a subscription that licenses development while the plan is active. — [Synty, Licences overview](https://syntystore.com/pages/licences-overview)
- The Synty one-time purchase license (as at 9 July 2026) states: "You must not share the source files of any Assets outside your team." It also forbids distribution as stock art, use in generative AI data sets, and NFT use. One purchase includes five seats. A Humble Bundle purchase has one seat. — [Synty, One Time Purchase Licence](https://syntystore.com/pages/one-time-purchase-licence)
- The Synty license permits the buyer to put an asset into a product under the direct control of the buyer and to distribute it as part of that product. The page does not discuss public repositories or open-source projects. — [Synty, One Time Purchase Licence](https://syntystore.com/pages/one-time-purchase-licence)
- JustCreate3D forbids the sale or share of the asset, or a part of it, where users get access to the original files. It says that the game must be compiled. It forbids NFT use. — [JustCreate3D, Low Poly Sci-Fi Characters](https://justcreate3d.itch.io/low-poly-sci-fi-characters)

Pack survey (pages read on 2026-10-11):

| Pack | Author | License on page | Formats | Rig and animation | Gear type | Style |
|---|---|---|---|---|---|---|
| [Universal Base Characters](https://quaternius.com/packs/universalbasecharacters.html) (August 2025) | Quaternius | CC0 on page, see QAL conflict | FBX, OBJ, glTF. `.blend` in the Source tier ($19.99 on itch.io) | Humanoid rig. No animation in the pack. Works with Universal Animation Library | 6 bodies, 20 hair meshes, about 13,000 triangles each. No gear | Neutral base |
| [Modular Character Outfits - Fantasy](https://quaternius.com/packs/modularcharacteroutfitsfantasy.html) (November 2025, v2.1 July 2026) | Quaternius | CC0 on page, see QAL conflict | OBJ, FBX, glTF. `.blend` in the Source tier ($20) | Same humanoid rig | 12 outfits from 62 parts (82 in the Source caption). Parts on the shared rig. Works with only a base head since v2.0. 3 color textures each | Fantasy |
| [Universal Animation Library](https://quaternius.com/packs/universalanimationlibrary.html) (March 2025) | Quaternius | CC0 on page, see QAL conflict | FBX, GLB, Blend | 120 or more animations on the universal humanoid rig | No gear | Any |
| [Universal Animation Library 2](https://quaternius.com/packs/universalanimationlibrary2.html) (January 2026) | Quaternius | CC0 on page, see QAL conflict | FBX, GLB, Blend | 130 or more animations. Complements the first library | No gear | Any |
| [Ultimate Modular Men Pack](https://quaternius.com/packs/ultimatemodularcharacters.html) (February 2022) | Quaternius | CC0 on page | FBX, OBJ, Blend. The text also names glTF | 11 characters, 24 animations | Each character splits into 4 models that swap | Not stated on page |
| [Cyberpunk Game Kit](https://quaternius.com/packs/cyberpunkgamekit.html) (July 2022) | Quaternius | CC0 on page | FBX, OBJ, Blend, glTF | 71 models. One animated character, enemies, turrets, platforms. Not textured | Not modular | Cyberpunk |
| [Sci-Fi Essentials Kit](https://quaternius.com/packs/scifiessentialskit.html) (November 2024) | Quaternius | CC0 on page | FBX, OBJ, glTF, Blend | 65 models. Animated robot enemies | Textured guns and props, rigid | Sci-fi |
| [KayKit Adventurers 2.0](https://kaylousberg.itch.io/kaykit-adventurers) | Kay Lousberg | CC0 | FBX, GLTF. `.blend` in the Source tier ($11.95) | 5 free characters, 3 more for $7.95. Rigged and animated | 25 or more weapons and accessories as separate items, 50 or more in Source. One gradient atlas | Fantasy |
| [KayKit Character Animations 1.1](https://kaylousberg.itch.io/kaykit-character-animations) (December 10, 2025) | Kay Lousberg | CC0 | FBX, GLTF. `.blend` for $14.99 | 161 humanoid animations on `Rig_Medium` and `Rig_Large` | No gear | Any KayKit character |
| [Mini Characters 1.0](https://kenney.nl/assets/mini-characters) (2024) | Kenney | CC0 | Not stated on page | 25 files. The page lists "Animation" | Not stated | Mini series |
| [Blocky Characters 2.0](https://kenney.nl/assets/blocky-characters) | Kenney | CC0 | Not stated on page | 20 files. The page lists "Animation" | Not stated | Blocky |
| [Modular Characters 1.0](https://kenney.nl/assets/modular-characters) (2014) | Kenney | CC0 | Not stated on page | 2D sprites, 425 files | 2D only | 2D |
| [Blaster Kit 2.1](https://kenney.nl/assets/blaster-kit) | Kenney | CC0 | Not stated on page | 40 files. Blasters, silencer, throwables, crates | Rigid | Sci-fi |
| [Sci-Fi Civilians - Sidekick](https://syntystore.com/products/sci-fi-civilians-sidekick-modular-character-pack) | Synty Studios | Bought, 5 seats, $199.99 | Unity 2021.3 package, Unreal plugin 5.3 to 5.8, Unreal content zip. No FBX or glTF on the page | Unity Humanoid rig. Unreal mannequin compatible. Face blend shapes | 103 parts and 90 or more base parts. Skinned parts plus rigid attachments | Dystopian sci-fi |
| [POLYGON Sci-Fi Worlds](https://syntystore.com/products/polygon-sci-fi-worlds) | Synty Studios | Bought | Unreal 5.3 project, Unity 2022.3 package, FBX source files | Mecanim rig. No animation | Characters, guns, vehicles, buildings | Sci-fi (search summary) |
| [Low Poly Sci-Fi Characters](https://justcreate3d.itch.io/low-poly-sci-fi-characters) | JustCreate3D | Bought, $19.99, no share of original files | FBX, Unity package | Humanoid rig. No animation. Works with Mixamo | 2 bodies, 6 male and 5 female outfit sets, 5 heads each | Sci-fi |
| [Amir modular character pack](https://ahmedamirdev.itch.io/amir-the-only-modular-character-pack-youll-ever-need) (October 23, 2025) | Amir | Not stated in the post | Not stated. Free, Plus, and Source tiers | Rigged for Mixamo | Head, torso, arms, hands, legs, feet as parts | Medieval, modern, cyberpunk |
| [Modular RPG Characters](https://opengameart.org/content/modular-rpg-characters) (January 7, 2022) | System G6 | CC0 | Not read | Rigged, modular | Not read | Fantasy (search summary) |

Other pack facts:
- The Standard tier of each recent Quaternius pack is free and holds 60 to 70 percent of the pack. On itch.io the Standard tier of Universal Base Characters holds 2 of the base models and 5 of the hair meshes. — [Quaternius, Universal Base Characters](https://quaternius.com/packs/universalbasecharacters.html), [Quaternius itch.io, Universal Base Characters](https://quaternius.itch.io/universal-base-characters)
- The free Standard tier of the Quaternius outfits holds the Ranger and the Peasant. — [Quaternius itch.io, Modular Character Outfits - Fantasy](https://quaternius.itch.io/modular-character-outfits-fantasy)
- The Quaternius site also lists gun and weapon packs that I did not open: Sci-Fi Modular Gun Pack, Ultimate Guns Pack, Animated Guns Pack, Sci-Fi Gun Pack, Modular Weapons Pack, and Fantasy Props MegaKit. It lists an Ultimate Modular Women Pack. — [Quaternius](https://quaternius.com/)
- The first version of KayKit Adventurers on GitHub lists 4 characters, 2 more in the paid tier, and 75 animations. — [KayKit Adventurers 1.0 on GitHub](https://github.com/KayKit-Game-Assets/KayKit-Character-Pack-Adventures-1.0)
- The Ranger bow of KayKit has a blend shape for the string. — [KayKit Adventurers](https://kaylousberg.itch.io/kaykit-adventurers)
- Synty Sidekick body types are blend shapes: masculine to feminine, skinny to heavy, and muscular. Its runtime API works in Unity only. The page says that Unreal support comes later. — [Synty Store, Sci-Fi Civilians Sidekick](https://syntystore.com/products/sci-fi-civilians-sidekick-modular-character-pack)
- A community Godot tool builds Sidekick characters. It is not a Synty product, and it needs a Sidekick license. Its known issues include attachment positions with blend shapes. — [jgillich, Sidekick Creator](https://jgillich.itch.io/sidekick-creator) (search summary)
- A guide site says that the Kenney "Animated Characters" packs are the rigged and animated packs, and that Mini Characters and Blocky Characters are not animated. This contradicts the Kenney pages, which list "Animation" for both packs. — [Cinevva guide](https://app.cinevva.com/de/guides/free-rigged-3d-character-models) (search summary), [Kenney, Mini Characters](https://kenney.nl/assets/mini-characters)
- A Sketchfab pack by jeebs (April 2020) uses one simple humanoid rig for all its models. I did not confirm its license. — [Sketchfab, Modular character pack](https://sketchfab.com/3d-models/modular-character-pack-c84596b8fa6547a4a570cc3f882ffc3c) (search summary)

Packs that share one skeleton across products:
- Quaternius: Universal Base Characters, Modular Character Outfits, and Universal Animation Library. Universal Animation Library 2 complements the first library on a universal humanoid rig. — [Quaternius, Modular Character Outfits - Fantasy](https://quaternius.com/packs/modularcharacteroutfitsfantasy.html), [Quaternius, Universal Animation Library 2](https://quaternius.com/packs/universalanimationlibrary2.html)
- KayKit: all character packs, through `Rig_Medium` and `Rig_Large`. — [KayKit Character Animations](https://kaylousberg.itch.io/kaykit-character-animations)
- Synty: all Sidekick packs use the Unity Humanoid skeleton and are Unreal mannequin compatible. — [Synty Store, Sci-Fi Civilians Sidekick](https://syntystore.com/products/sci-fi-civilians-sidekick-modular-character-pack)

### Inferences
- The license gate must treat Quaternius as unresolved. The safe step is to read the license file inside each download and to record that text and the download date in the source record.
- If the QAL governs a pack, then that pack is not CC0 and not CC-BY. It needs a new gate category or an exception. Raw Quaternius files in a public repository can also count as redistribution of the assets as assets.
- The Synty and JustCreate3D terms forbid a share of the original files. A served `.glb` in a public repository is a model file that any person can download. That is a risk under both licenses. This is my reading and not legal advice.
- No pack in this survey gives CC0 cyberpunk clothing that is skinned to a shared skeleton. The closest CC0 match is the Quaternius base body plus the fantasy outfits as a rig and topology reference. The cyberpunk gear needs original art.
- KayKit gives the best CC0 example of rigid gear on a shared rig. Quaternius gives the best free example of skinned outfit parts on a shared rig.
- Synty Sidekick ships no FBX or glTF on the page that I read. A Godot pipeline needs an export from Unity or Unreal first, which adds work and license risk.

### Gaps
- I found no Synty pack with "Cyberpunk" in its name. The search gave POLYGON Sci-Fi Worlds, Sci-Fi Space, Sci-Fi Horror, and the Sidekick sci-fi packs. I did not confirm a POLYGON Sci-Fi City pack.
- The Synty Sidekick tool page returned HTTP 404. I did not confirm the price or the contents of a free starter tier.
- The Kenney pages do not state file formats or rig details. I did not open the downloads, as the task forbids it.
- I did not read the Quaternius Ultimate Modular Women Pack page or the gun pack pages.
- I did not confirm the license of the Amir pack or of the Sketchfab pack.
- I did not find the bone names or the bone count of the Quaternius rig or of the KayKit rigs on any page.

## 9. Body types: male, female, and other shapes with one gear set

### Takeaway
The sources show three methods: one model for each sex in the item record (OSRS), separate gear meshes for each body (Quaternius, Polytope), and blend shapes on every part (Synty Sidekick). I found no clear recommendation from solo developers. The evidence that exists points to a late body type as a large cost.

### Cited Findings
- The OSRS item record holds a male model set and a female model set for each worn item, each with its own offset. — [RuneLite cache, ItemDefinition.java](https://github.com/runelite/runelite/blob/master/cache/src/main/java/net/runelite/cache/definitions/ItemDefinition.java), [2004Scape wiki, Configs](https://github-wiki-see.page/m/2004Scape/Server/wiki/Configs)
- Quaternius Universal Base Characters has male and female bodies in three proportions: Superhero, Regular, and Teen. — [Quaternius, Universal Base Characters](https://quaternius.com/packs/universalbasecharacters.html)
- Version 2.0 of the Quaternius outfits added "All_Male" and "All_Female" files. The outfit names in the changelog carry a sex, for example `Peasant_Male`. — [Quaternius itch.io, Modular Character Outfits - Fantasy](https://quaternius.itch.io/modular-character-outfits-fantasy)
- Synty Sidekick changes the body type with blend shapes on the parts: masculine to feminine, skinny to heavy, and muscular. — [Synty Store, Sci-Fi Civilians Sidekick](https://syntystore.com/products/sci-fi-civilians-sidekick-modular-character-pack)
- JustCreate3D ships one male body and one female body, each with its own outfit sets. — [JustCreate3D, Low Poly Sci-Fi Characters](https://justcreate3d.itch.io/low-poly-sci-fi-characters)
- A Polytope armor pack ships 10 armor sets: 5 male and 5 female. — [Unreal forums, Polytope Studio](https://forums.unrealengine.com/t/polytope-studio-low-poly-orc-modular-armors-medieval-fantasy-series/2833880) (search summary, exact listing not opened)
- A Polycount thread on armor for several body types suggests a neutral base mesh with one morph target for each body type. The armor gets its morphs from the body through a skin wrap. A reply warns that the result depends on how different the body types are. — [Polycount](https://polycount.com/discussion/comment/1682029) (search summary)
- The same thread notes that blend shapes need an equal vertex count on each shape. — [Polycount](https://polycount.com/discussion/comment/1682031) (search summary)
- An itch.io developer delayed a female body type to a much later pack. Another developer says that body variants need a plan from the start, because they change the inventory and the content. — [itch.io post](https://itch.io/post/5718907), [itch.io post](https://itch.io/post/13299187) (both: search summary)
- The Unreal Skeletal Mesh Merge method does not support morph targets. The Leader Pose method does. — [Epic docs, Working with Modular Characters (UE 5.8)](https://dev.epicgames.com/documentation/en-us/unreal-engine/working-with-modular-characters-in-unreal-engine)

### Inferences
- Separate meshes for each body double the gear art. Blend shapes keep one mesh but need a morph on every gear mesh and morph support in the loader and the client.
- One unisex body is the cheapest method for one developer. It fits a low-poly style where the gear hides most of the body shape.
- The OSRS method is a middle path. The item record allows a second model for a body type, and an item can use the same model for both. The field must exist from the first item, even if most items leave it empty.
- A rigid item needs only an offset for each body type, not a second mesh. The OSRS `maleOffset` and `femaleOffset` fields show this.

### Gaps
- I found no post from a solo developer that compares the three methods with measured cost.
- I did not confirm that the Godot runtime glTF loader keeps blend shapes on a skinned gear mesh.
- I did not find how Quaternius builds the male and female outfit files, or whether they share topology.
