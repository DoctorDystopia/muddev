# Visible equipment on an animated character in Godot 4 (runtime .glb)

Scope notes for the report writer:

- "Docs 4.7" means the `stable` class reference at docs.godotengine.org. Its page header said "Godot Engine 4.7" on 2026-10-11.
- "Source (master)" means the `master` branch of godotengine/godot, read on 2026-10-11. Open pull requests carry the 4.8 milestone, so master is 4.8-dev. I did not compare master with the 4.7 tag. Treat each source fact as "confirmed for master, probable for 4.3 to 4.7".
- A GDScript block under "Inferences" is my sketch. No source supplied it, and nobody ran it.
- "Search summary" marks a fact that came from a search result summary. I did not read that page in full.

## 1. Rigid items: BoneAttachment3D, its alternatives, socket bones, grip offsets

### Takeaway

`BoneAttachment3D` is the standard node for a rigid item. It copies `Skeleton3D.get_bone_global_pose(bone_idx)` into its own transform each time the skeleton emits `skeleton_updated`. A socket bone needs no special tool: the glTF importer turns each non-joint node inside a skeleton subtree into a bone, so an Empty that Blender parents to the hand bone arrives as a named bone.

### Cited Findings

**BoneAttachment3D (Docs 4.7)**

- The node "dynamically copies or overrides the 3D transform of a bone in its parent Skeleton3D." It selects one bone and attaches to it. — [BoneAttachment3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_boneattachment3d.html)
- Properties and defaults: `bone_idx: int = -1`, `bone_name: String = ""`, `external_skeleton: NodePath`, `override_pose: bool = false`, `use_external_skeleton: bool = false`. The page also overrides `physics_interpolation_mode` to `2` (off). — [BoneAttachment3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_boneattachment3d.html)
- `override_pose = false`: the node always follows the bone. `override_pose = true`: the node writes its own transform into the bone. The docs warn that this override "runs interruptively" during the skeleton update through signals, and that it can behave unexpectedly together with a `SkeletonModifier3D`. — [BoneAttachment3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_boneattachment3d.html)
- `use_external_skeleton = true` makes the node use the `Skeleton3D` at `external_skeleton`, not its parent. Thus the attachment does not need to be a child of the skeleton. — [BoneAttachment3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_boneattachment3d.html)
- Methods: `get_skeleton() -> Skeleton3D` returns the parent or external skeleton, or `null`. `on_skeleton_update()` is the callback that the skeleton update calls. — [BoneAttachment3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_boneattachment3d.html)

**BoneAttachment3D (Source, master)**

- The node connects to the `skeleton_updated` signal of the skeleton, not to `pose_updated`: `sk->connect(SceneStringName(skeleton_updated), callable_mp(this, &BoneAttachment3D::on_skeleton_update));` — [bone_attachment_3d.cpp](https://raw.githubusercontent.com/godotengine/godot/master/scene/3d/bone_attachment_3d.cpp)
- Parent skeleton mode sets the LOCAL transform: `set_transform(sk->get_bone_global_pose(bone_idx));`. External skeleton mode sets the GLOBAL transform: `set_global_transform(sk->get_global_transform() * sk->get_bone_global_pose(bone_idx));`. The external branch runs only when the skeleton is inside the tree. — [bone_attachment_3d.cpp](https://raw.githubusercontent.com/godotengine/godot/master/scene/3d/bone_attachment_3d.cpp)
- `set_bone_name` stores the name and calls `set_bone_idx(sk->find_bone(...))` when a skeleton exists. `set_bone_idx` with an index out of range resets the index to -1 and prints a warning. — [bone_attachment_3d.cpp](https://raw.githubusercontent.com/godotengine/godot/master/scene/3d/bone_attachment_3d.cpp)
- With `override_pose` on, `_transform_changed()` writes the bone with `set_bone_global_pose`, then calls `force_update_all_dirty_bones()`. The file does not use `set_bone_global_pose_override`. When `override_pose` goes off, the node calls `sk->reset_bone_pose(bone_idx)`. — [bone_attachment_3d.cpp](https://raw.githubusercontent.com/godotengine/godot/master/scene/3d/bone_attachment_3d.cpp)
- The constructor sets `PHYSICS_INTERPOLATION_MODE_OFF`. A configuration warning says "BoneAttachment3D should have physics_interpolation_mode set to OFF in order to avoid jitter." Other warnings: no external skeleton set, parent is not a `Skeleton3D`, and "BoneAttachment3D node is not bound to any bones!" — [bone_attachment_3d.cpp](https://raw.githubusercontent.com/godotengine/godot/master/scene/3d/bone_attachment_3d.cpp)
- Bind and unbind happen on `NOTIFICATION_ENTER_TREE` and `NOTIFICATION_EXIT_TREE`. — [bone_attachment_3d.cpp](https://raw.githubusercontent.com/godotengine/godot/master/scene/3d/bone_attachment_3d.cpp)

**Skeleton3D calls for the "do it in code" alternative (Docs 4.7)**

- `get_bone_global_pose(bone_idx) -> Transform3D` returns the pose relative to the SKELETON, not to the world. A modifier can still change the final value later. Read `SkeletonModifier3D.modification_processed` or `skeleton_updated` for the final value. — [Skeleton3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_skeleton3d.html)
- `find_bone(name) -> int` returns -1 when no bone has that name. `get_bone_global_rest(bone_idx)` returns the global rest. — [Skeleton3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_skeleton3d.html)
- Signal `skeleton_updated`: emitted when the final pose is calculated and applied to the skin. All modifier work is complete at that time. Signal `pose_updated` does not see modifier changes. — [Skeleton3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_skeleton3d.html)
- `force_update_all_bone_transforms()` and `get_bone_global_pose_no_override()` are deprecated. `force_update_bone_child_transform(bone_idx)` is not. — [Skeleton3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_skeleton3d.html)
- `modifier_callback_mode_process` (default `1`, idle frames) sets when the modifiers run: physics frames, idle frames, or manual. — [Skeleton3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_skeleton3d.html)

**SkeletonModifier3D (since 4.3)**

- Godot 4.3 added `SkeletonModifier3D` as the base class for bone changes outside `AnimationMixer`. It replaces the old `global_pose_override` design, whose process order depended on the scene tree. — [Design of the Skeleton Modifier 3D, godotengine.org, August 2024](https://godotengine.org/article/design-of-the-skeleton-modifier-3d/)
- Order of one frame: `AnimationMixer` applies the animation. The `Skeleton3D` update (a deferred call) stores the pose, runs each modifier in child order, applies the result to the skin, then rolls the pose back. The update happens one time per frame. — [Design of the Skeleton Modifier 3D](https://godotengine.org/article/design-of-the-skeleton-modifier-3d/)
- Because the pose rolls back, a script cannot see a modified pose in `_process()`. It must connect to `Skeleton3D.skeleton_updated` or `SkeletonModifier3D.modification_processed`. — [Design of the Skeleton Modifier 3D](https://godotengine.org/article/design-of-the-skeleton-modifier-3d/)
- Deprecated since 4.3, not removed: `set_bone_global_pose_override()`, `get_bone_global_pose_override()`, `get_bone_global_pose_no_override()`, `clear_bones_global_pose_override()`. — [Design of the Skeleton Modifier 3D](https://godotengine.org/article/design-of-the-skeleton-modifier-3d/)
- Docs 4.7 API: properties `active: bool = true`, `influence: float = 1.0`. Virtuals `_process_modification_with_delta(delta: float)`, `_skeleton_changed(old, new)`, `_validate_bone_names()`. `_process_modification()` is deprecated in favour of the `_with_delta` form. `get_skeleton()` returns the parent `Skeleton3D`. Signal `modification_processed`. — [SkeletonModifier3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_skeletonmodifier3d.html)
- Docs 4.7 lists these subclasses: `BoneConstraint3D`, `BoneTwistDisperser3D`, `IKModifier3D`, `LimitAngularVelocityModifier3D`, `LookAtModifier3D`, `ModifierBoneTarget3D`, `PhysicalBoneSimulator3D`, `RetargetModifier3D`, `SkeletonIK3D`, `SpringBoneSimulator3D`, `XRBodyModifier3D`, `XRHandModifier3D`. — [SkeletonModifier3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_skeletonmodifier3d.html)
- The article says a modifier suits temporary effects such as IK. It says a permanent change should not use one. — [Design of the Skeleton Modifier 3D](https://godotengine.org/article/design-of-the-skeleton-modifier-3d/)

**RemoteTransform3D (Docs 4.7)**

- `RemoteTransform3D` copies its own transform onto another node. Properties: `remote_path: NodePath = NodePath("")`, `update_position = true`, `update_rotation = true`, `update_scale = true`, `use_global_coordinates = true`. `force_update_cache()` refreshes the cached target, because the node "may not notice if the remote node disappears." — [RemoteTransform3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_remotetransform3d.html)

**Socket bones**

- The glTF importer makes each non-joint node inside a skeleton subtree a joint. `_reparent_non_joint_skeleton_subtrees` sets `node->joint = true` and adds the node to the joints of the skeleton. — [skin_tool.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/skin_tool.cpp)
- A Godot 4.4.1 user saw exactly this: an attachment exported inside a GLB came back with "a new bone ... created in the rig using its name". The thread has no reply. — [Godot Forum, June 2025](https://forum.godotengine.org/t/boneattachment3d-when-imported-from-a-glb-file-creates-a-new-bone-in-the-rig-with-its-name/112707)
- Issue #91132 has the same subject: "BoneAttachment3D nodes generated from blend file are assigned to their own new distinct bone rather than bones defined on the skeleton originally." It closed on 2024-04-25 with no milestone. — [godot#91132](https://github.com/godotengine/godot/issues/91132)
- A Q&A answer says that an object parented to a BONE in Blender (not to the armature) exports as a bone attachment in the Godot scene (search summary, old Q&A site, Godot version not stated). — [ask.godotengine.org 143779](https://ask.godotengine.org/143779/how-to-attach-a-gun-to-a-hand-bone-in-blender-for-import)
- A socket bone can also be made in code. `add_bone(name) -> int` adds a bone. The name must be unique and must not contain `:` or `/`. `set_bone_parent(bone_idx, parent_idx)` needs `parent_idx < bone_idx`. `set_bone_rest(bone_idx, rest)` sets the rest. — [Skeleton3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_skeleton3d.html)
- Why developers want one fixed hand basis: a Godot 4.7 user attached a weapon with `BoneAttachment3D` plus a per-weapon offset `Transform3D`. Animations from different Mixamo downloads gave the hand bone a different local basis, "up to about 130°" apart. One offset was correct in one clip and twisted in the next. The fix was import-time retargeting (`BoneMap` to `SkeletonProfileHumanoid`, Rest Fixer "Overwrite Axis") on every model and every animation file. The post asks about "sockets, a dedicated hold bone, or a Marker3D on the mesh" and got no reply. — [Godot Forum, July 2026](https://forum.godotengine.org/t/best-practice-for-attaching-weapons-items-to-a-characters-hand-across-many-animations-godot-4/141270)

**What developers do in practice**

- A Godot 4.4 user equipped weapons by show and hide of children on the rig, and wanted to avoid bone attachments. The thread has no accepted answer. — [Godot Forum, August 2025](https://forum.godotengine.org/t/gdscript-how-to-assign-a-skeleton3d-to-a-meshinstance3d/119829)
- A forum answer for Godot 4.4.1 recommends to skip `BoneAttachment3D` and apply the bone transform to the node directly when the attachment trails the bone. — [Godot Forum, June 2025](https://forum.godotengine.org/t/boneattachment3d-trailing-behind-why/112929)

### Inferences

- A socket bone moves the grip decision from code to the art. The animator can key the socket (a two-hand grip, a sheath move), and every item then needs only its own small grip offset. The Mixamo thread shows the failure of the other path: an offset in code is correct only while every clip shares one hand basis.
- For this project the cheapest socket path is in the model pipeline, not in the client. Add `hand_r_socket`, `hand_l_socket`, `head_socket`, `back_socket` as Empties parented to bones in the body source. The runtime importer then gives them as bones, and `bone_name` finds them.
- Store the grip offset as data for each item, as one `Transform3D` (or position plus Euler angles) in the model record. Apply it to the item node, which is a child of the attachment. A second option is a named child node in the item `.glb` (for example `grip`), and the client applies the inverse of its transform. No source prescribes either. Both keep the offset out of code branches.
- `use_external_skeleton` lets the item stay outside the body subtree. Parent mode is simpler at runtime, because the attachment and the item die with the body.
- Sketch, parent mode (not from a source, not run):

```gdscript
func attach_rigid(skeleton: Skeleton3D, socket: StringName, item: Node3D, grip: Transform3D) -> BoneAttachment3D:
    var att := BoneAttachment3D.new()
    att.name = "Socket_%s" % socket
    skeleton.add_child(att)          # enter the tree first, then bind
    att.bone_name = socket           # set_bone_name -> find_bone -> bone_idx
    if att.bone_idx == -1:
        push_warning("no bone named %s" % socket)
    att.add_child(item)
    item.transform = grip            # per-item offset, read from data
    return att
```

- Sketch, no attachment node (not from a source, not run). It follows the forum advice and the `skeleton_updated` rule:

```gdscript
func _ready() -> void:
    _bone = skeleton.find_bone(&"hand_r_socket")
    skeleton.skeleton_updated.connect(_follow)

func _follow() -> void:
    item.global_transform = skeleton.global_transform * skeleton.get_bone_global_pose(_bone) * grip
```

### Gaps

- I did not read the `ModifierBoneTarget3D` page. Docs 4.7 lists the class. It can be a second way to follow a bone inside the modifier order. Its first version is unknown to me.
- I found no official manual page that recommends socket bones, and no reply from a maintainer on the "best practice" question.
- No source states the frame cost of many `BoneAttachment3D` nodes. Issue #92775 ("Animated BoneAttachment3D Performance Impact") is open. I did not read its numbers. — [godot#92775](https://github.com/godotengine/godot/issues/92775)
- The old Q&A answer about "Parent to Bone" is from a search summary. I did not confirm it for Blender 4.x plus Godot 4.7.

## 2. Skinned gear: bind a MeshInstance3D from one .glb to the Skeleton3D of another character

### Takeaway

A skinned mesh needs three things: `MeshInstance3D.mesh`, `MeshInstance3D.skin` (a `Skin` with one bind for each joint), and `MeshInstance3D.skeleton` (a `NodePath` to a `Skeleton3D`). To move gear onto another body, keep the mesh and its `Skin`, give the `Skin` NAMED binds, and point `skeleton` at the body. The engine then resolves each bind by bone name. The inverse bind matrices in the `Skin` must come from the same rest pose as the body.

### Cited Findings

**MeshInstance3D (Docs 4.7 and source)**

- `skeleton: NodePath`, default `NodePath("")`. "The default value of this property has changed in Godot 4.6." The project setting `animation/compatibility/default_parent_skeleton_in_mesh_instance_3d` restores the old default. — [MeshInstance3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_meshinstance3d.html)
- The old default was `NodePath("..")`. PR #112267 "Remove default skeleton path in MeshInstance3D" merged on 2025-11-01 for 4.6. Its reason: the parent default "often assigned unrelated nodes as the skeleton". It fixes #101206 and #63210. — [godot PR #112267](https://github.com/godotengine/godot/pull/112267), [Upgrading to Godot 4.6](https://docs.godotengine.org/en/stable/tutorials/migrating/upgrading_to_godot_4.6.html)
- `skin`: "The Skin to be used by this instance." `get_skin_reference()` returns the internal `SkinReference` that holds the skeleton RID. — [MeshInstance3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_meshinstance3d.html)
- `_resolve_skeleton_path()` resolves the path with `get_node_or_null(skeleton_path)` on the mesh instance, so the path is relative to the `MeshInstance3D`. — [mesh_instance_3d.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/scene/3d/mesh_instance_3d.cpp)
- If the path is empty, or the node is missing, or the node is not a `Skeleton3D`, the function calls `instance_attach_skeleton(get_instance(), RID())`. That detaches the skeleton, and the code prints no error. — [mesh_instance_3d.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/scene/3d/mesh_instance_3d.cpp)
- If a skeleton exists and `skin` is null, the mesh instance makes one: `skeleton->register_skin(skeleton->create_skin_from_rest_transforms())`. If `skin` is set, it calls `skeleton->register_skin(skin_internal)`. — [mesh_instance_3d.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/scene/3d/mesh_instance_3d.cpp)
- `set_skin()` and `set_skeleton_path()` store the value. They resolve at once only when the node is inside the tree. Outside the tree, the resolve runs at `NOTIFICATION_ENTER_TREE`. — [mesh_instance_3d.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/scene/3d/mesh_instance_3d.cpp)

**Skin (Docs 4.7 and source)**

- The `Skin` class page has no description text. The method list is: `add_bind(bone: int, pose: Transform3D)`, `add_named_bind(name: String, pose: Transform3D)`, `clear_binds()`, `get_bind_bone(i) -> int`, `get_bind_count() -> int`, `get_bind_name(i) -> StringName`, `get_bind_pose(i) -> Transform3D`, `set_bind_bone(i, bone)`, `set_bind_count(n)`, `set_bind_name(i, name)`, `set_bind_pose(i, pose)`. — [Skin, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_skin.html)
- `Skeleton3D.register_skin(skin) -> SkinReference` "binds the given Skin to this skeleton". With a null skin it fails: `ERR_FAIL_COND_V(p_skin.is_null(), Ref<SkinReference>());`. — [Skeleton3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_skeleton3d.html), [skeleton_3d.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/scene/3d/skeleton_3d.cpp)
- Bind resolution, inside `NOTIFICATION_UPDATE_SKELETON`: for each bind with a non-empty name, the skeleton searches its bones for that name and stores the index. The name wins over the bone index. — [skeleton_3d.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/scene/3d/skeleton_3d.cpp)
- A named bind with no matching bone prints an error that starts "Skin bind #" and ends "but Skeleton3D has no bone by that name." The bind then uses bone 0. — [skeleton_3d.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/scene/3d/skeleton_3d.cpp)
- An unnamed bind whose bone index is at or over the bone count prints an error with "contains bone index bind" and uses bone 0. A bind with no name and a negative index prints "does not contain a name nor a bone index." and uses bone 0. — [skeleton_3d.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/scene/3d/skeleton_3d.cpp)
- The resolve runs again when the skeleton version changes. `add_bone`, `set_bone_name`, and `clear_bones` increment the version. — [skeleton_3d.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/scene/3d/skeleton_3d.cpp)
- The skinning matrix for bind `i` is `bone.global_pose * bind_pose`: `rs->skeleton_bone_set_transform(skeleton, i, bonesptr[bone_index].global_pose * bind_pose_transform)`. The index `i` is the BIND index. — [skeleton_3d.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/scene/3d/skeleton_3d.cpp)
- `create_skin_from_rest_transforms()` makes one bind for each bone, with `set_bind_bone(i, i)` and a bind pose equal to the inverse of the global rest of the bone. — [skeleton_3d.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/scene/3d/skeleton_3d.cpp)
- One `Skeleton3D` can hold several `SkinReference` objects, one for each different `Skin` on its mesh instances (search summary of the 4.3 class page). — [SkinReference, Docs 4.3](https://docs.godotengine.org/fr/4.3/classes/class_skinreference.html)

**What the glTF importer puts in the Skin**

- `SkinTool::_create_skins` stores each glTF inverse bind matrix directly as the bind pose: `xform = gltf_skin->inverse_binds[joint_i];`. — [skin_tool.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/skin_tool.cpp)
- With named binds on, it calls `skin->add_named_bind(bone_name, xform);`. With named binds off, it calls `skin->add_bind(bone_i, xform);` with the bone index. — [skin_tool.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/skin_tool.cpp)
- The bone REST comes from the node transform (`GODOT_rest_transform`), not from the inverse bind matrix. — [skin_tool.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/skin_tool.cpp)
- The importer attaches the mesh like this: `skeleton->add_child(mi, true);`, `mi->set_skin(...)`, `mi->set_skeleton_path(mi->get_path_to(skeleton));`, `mi->set_transform(Transform3D());`. A skinned mesh instance must be a leaf node. — [gltf_document.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/gltf_document.cpp)

**Same names and same rest**

- The retargeting manual says that to share animations "it is necessary to match Bone Rests as well as Bone Names". — [Retargeting 3D Skeletons, Docs 4.7](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/retargeting_3d_skeletons.html)

**Tutorials and forum answers for "modular character" or "swap clothing"**

- The most complete Godot 4 tutorial I found is "3d RPG clothing (and inventory) system using Godot 4 and Blender" by Pablo Ibarz (roboticy3), 2025-06-30, Godot 4.4.1 and Blender 4.4, CC BY-NC 4.0. Each clothing item is a separate mesh in Blender and a separate `PackedScene` in Godot. A loader node calls `add_child` on equip and `remove_child` on unequip. A Data Transfer modifier copies normals and vertex weights from the original body onto the split pieces, so the seams stay closed. — [Godot Forum tutorial](https://forum.godotengine.org/t/3d-rpg-clothing-and-inventory-system-using-godot-4-and-blender/114842), [Roboticy3/body-groups](https://github.com/Roboticy3/body-groups)
- Godot 4.0.2: a user rigged head, body, legs, and hair as four meshes on one skeleton, and swapped the `MeshInstance3D` child under the `Skeleton3D` (`RemoveChild` then `AddChild`). A part exported as OBJ lost its rigging. The thread has no reply. — [Godot Forum, "Skeletal animations with interchangeable meshes"](https://forum.godotengine.org/t/skeletal-animations-with-interchangeable-meshes/55548)
- Godot 4.4: a forum answer gives the usual workflow as "a mesh bound to a rig in Blender is imported, the mesh is swapped via code, and the rig stays unchanged". The asker found no documentation for runtime assignment of `skeleton`. No accepted answer. — [Godot Forum, August 2025](https://forum.godotengine.org/t/gdscript-how-to-assign-a-skeleton3d-to-a-meshinstance3d/119829)
- Godot 4.5: a user compared one GLB for each outfit (less memory, but each new animation needs a new export for each outfit) with one GLB that holds all outfits as `MeshInstance3D` nodes that toggle on and off (unused outfits still use VRAM). The one answer covers only how to split a GLB into saved scenes in the editor. The question about outfits "pinned" onto a shared character at runtime got no answer. — [Godot Forum, January 2026](https://forum.godotengine.org/t/managing-scalability-of-skeleton-animation-and-outfits-for-3d-characters-from-blender-to-godot/130681)
- A forum answer says clothing must be prepared in Blender and linked to the rig before import (search summary). — [Godot Forum, "Character customization in Godot [3D]"](https://forum.godotengine.org/t/character-customization-in-godot-3d/59840)
- An older thread reports that `self.mesh = newMesh` on a skinned mesh instance made the part invisible (search summary, Godot version not stated, probably Godot 3). — [godotforums.org 26026](https://godotforums.org/d/26026-how-to-correctly-swap-the-mesh-of-a-meshinstance-when-it-s-also-parented-to-a-skeleton-node)

### Inferences

- The vertex bone indices of a mesh point into the bind list of its `Skin`, not into the bone list of the skeleton. The source supports this: the server call uses the bind index `i`. Thus the bone ORDER of the body does not matter when the binds are named. Only bone NAMES and rest poses matter.
- A swap of `mesh` alone can fail for this reason. The old `skin` stays, and its bind list can have a different joint order or count than the new mesh. That fits the "part goes invisible or wrong" reports. Always move `mesh` and `skin` as a pair.
- Do not leave `skin` null on gear. A null skin makes the engine call `create_skin_from_rest_transforms()`, which binds bind `i` to bone `i`. That is correct only if the joint order of the gear file equals the bone order of the body.
- What goes wrong when rests differ: at the rest pose, the skinning matrix is `body_global_rest * gear_inverse_bind`. It is the identity only when the gear was bound at the same global rest. If not, each vertex of that joint moves by the difference, at every frame. The symptom is gear that sits offset, twisted, or scaled on some bones while the animation itself plays correctly. A missing bone name is a different symptom: an error line, and those vertices collapse toward bone 0 (usually the root).
- A gear file that carries only the bones it uses is fine. Named binds need each bind name to exist on the body. Extra body bones do no harm.
- Since 4.6 a `MeshInstance3D` made in code does not bind to its parent by default. Set `skeleton` explicitly. On 4.3 to 4.5 the default `..` hid this step.
- Sketch (not from a source, not run). It moves each skinned mesh of a loaded gear scene onto a body skeleton:

```gdscript
func attach_skinned(gear_root: Node, body: Skeleton3D) -> Array[MeshInstance3D]:
    var moved: Array[MeshInstance3D] = []
    for node in gear_root.find_children("*", "MeshInstance3D", true, false):
        var mi := node as MeshInstance3D
        if mi.skin == null:
            continue                               # rigid part, use a socket
        var src := mi.get_node_or_null(mi.skeleton) as Skeleton3D
        var skin := mi.skin.duplicate() as Skin
        for i in skin.get_bind_count():            # index bind -> named bind
            if skin.get_bind_name(i) == &"" and src != null:
                skin.set_bind_name(i, src.get_bone_name(skin.get_bind_bone(i)))
            if body.find_bone(skin.get_bind_name(i)) == -1:
                push_warning("body has no bone %s" % skin.get_bind_name(i))
        mi.get_parent().remove_child(mi)
        mi.owner = null
        body.add_child(mi)
        mi.transform = Transform3D.IDENTITY
        mi.skin = skin
        mi.skeleton = mi.get_path_to(body)         # required since 4.6
        moved.append(mi)
    gear_root.queue_free()                         # drops the duplicate skeleton
    return moved
```

- With `IMPORT_FLAG_USE_NAMED_SKIN_BINDS` at load (section 3), the rename loop is not necessary. The check against `find_bone` is still a cheap guard.

### Gaps

- I found no official manual page, and no tutorial by KidsCanCode or GDQuest, that shows a runtime rebind of a mesh from one `.glb` onto the skeleton of another. The recipe above comes from the engine source, not from a tutorial.
- The `Skin` class has no documentation text in 4.7. Each statement about its behaviour comes from `skeleton_3d.cpp` and `skin_tool.cpp` on master.
- I did not test whether a `Skin` shared by many mesh instances on different skeletons causes a fault. The sketch duplicates the skin to stay safe.
- The godotforums.org thread 26026 did not state its Godot version.

## 3. Runtime glTF: what GLTFDocument returns, how to take only the mesh and Skin, flags, extensions

### Takeaway

`GLTFDocument.generate_scene()` returns a normal node tree: a root, one `Skeleton3D` that is always named `Skeleton3D`, each skinned `MeshInstance3D` as a leaf child of that skeleton with `skin` and `skeleton` set, and one `AnimationPlayer` when the file has animations. Named binds survive runtime import only when the caller passes `GLTFDocument.IMPORT_FLAG_USE_NAMED_SKIN_BINDS` (16). The default `flags = 0` gives index binds. A file that REQUIRES an extension outside the supported list fails with `ERR_UNAVAILABLE`.

### Cited Findings

**API (Docs 4.7)**

- The manual sample: make a `GLTFDocument` and a `GLTFState`, call `append_from_file(path, state)`, check the `Error`, call `generate_scene(state)`, then `add_child()` the result. Runtime load covers `.gltf` and `.glb`. — [Runtime file loading and saving, Docs 4.7](https://docs.godotengine.org/en/stable/tutorials/io/runtime_file_loading_and_saving.html)
- "Since Godot 4.3, FBX scenes can also be loaded (but not saved) at runtime" with `FBXDocument` and `FBXState`. — [Runtime file loading and saving](https://docs.godotengine.org/en/stable/tutorials/io/runtime_file_loading_and_saving.html)
- "When loading from a buffer, this base path must be manually set as there is no way for Godot to infer this path." External textures need it. — [Runtime file loading and saving](https://docs.godotengine.org/en/stable/tutorials/io/runtime_file_loading_and_saving.html)
- Signatures: `append_from_file(path: String, state: GLTFState, flags: int = 0, base_path: String = "") -> Error`. `append_from_buffer(bytes: PackedByteArray, base_path: String, state: GLTFState, flags: int = 0) -> Error`. `generate_scene(state: GLTFState, bake_fps: float = 30, trimming: bool = false, remove_immutable_tracks: bool = true) -> Node`. The argument order of the two append calls differs. — [GLTFDocument, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_gltfdocument.html)
- Enum `ImportFlags`: `IMPORT_FLAG_GENERATE_TANGENT_ARRAYS = 8`, `IMPORT_FLAG_USE_NAMED_SKIN_BINDS = 16`, `IMPORT_FLAG_DISCARD_MESHES_AND_MATERIALS = 32`, `IMPORT_FLAG_FORCE_DISABLE_MESH_COMPRESSION = 64`. — [GLTFDocument, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_gltfdocument.html)
- `GLTFDocument.get_supported_gltf_extensions() -> PackedStringArray` (static) lists the extensions that the engine and each registered `GLTFDocumentExtension` support. `register_gltf_document_extension(extension, first_priority = false)` (static) adds one. — [GLTFDocument, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_gltfdocument.html)
- `GLTFState` properties: `base_path = ""`, `bake_fps = 30.0`, `create_animations = true`, `import_as_skeleton_bones = false` (true forces every glTF node to become a bone of one skeleton), `use_named_skin_binds = false`, `handle_binary_image_mode = 1`, `json`, `glb_data`, `filename`, `scene_name`. — [GLTFState, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_gltfstate.html)
- `HANDLE_BINARY_IMAGE_MODE_EXTRACT_TEXTURES = 1` is the default. It is editor-only, and at runtime it acts like the uncompressed embed mode. `DISCARD_TEXTURES = 0`, `EMBED_AS_BASISU = 2`, `EMBED_AS_UNCOMPRESSED = 3`. — [GLTFState, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_gltfstate.html)
- `GLTFState.get_scene_node(gltf_node_index) -> Node` returns the Godot node made from a glTF node. `get_skins()`, `get_skeletons()`, `get_meshes()`, `get_nodes()` give the parsed tables. — [GLTFState, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_gltfstate.html)

**What the source does (master)**

- Both append calls OVERWRITE the state flags from `flags`: `p_state->use_named_skin_binds = p_flags & ImportFlags::IMPORT_FLAG_USE_NAMED_SKIN_BINDS;`, and the same for `discard_meshes_and_materials`, `force_generate_tangents`, and `force_disable_compression`. — [gltf_document.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/gltf_document.cpp)
- `append_from_buffer` sets `p_state->set_base_path(p_base_path.get_base_dir());`. It takes the DIRECTORY PART of the string that the caller passes. — [gltf_document.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/gltf_document.cpp)
- `append_from_file` sets the state file name from the path. It uses `p_path.get_base_dir()` when `base_path` is empty. — [gltf_document.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/gltf_document.cpp)
- The skeleton node name is always `Skeleton3D`: `skeleton->set_name("Skeleton3D");`. A comment says that no glTF node represents the skeleton. The parser reserves the name. — [skin_tool.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/skin_tool.cpp), [gltf_document.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/gltf_document.cpp)
- Bone names: an empty name becomes `bone`. `_sanitize_bone_name` replaces `:` and `/` with `_`. `_gen_unique_bone_name` adds `_2`, `_3`, and so on for a duplicate inside one skeleton. — [skin_tool.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/skin_tool.cpp)
- Skins: one `Skin` resource for each glTF skin, named `Skin`, `Skin2`, and so on. `_remove_duplicate_skins` points equal skins at the first one. Equality compares bind count, bind bone, bind name, and bind pose. — [skin_tool.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/skin_tool.cpp)
- Skeleton grouping: `_determine_skeletons` merges skin joints that link by parent and child, and merges sibling groups. Each final group becomes one `GLTFSkeleton`. — [skin_tool.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/skin_tool.cpp)
- The `AnimationPlayer` exists only `if (p_state->get_create_animations() && p_state->animations.size())`. It becomes a child of the root: `godot_root_node->add_child(anim_player, true);`. — [gltf_document.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/gltf_document.cpp)
- Animations go into the library with the empty name: `add_animation_library("", library)`, then `add_animation(anim_name, animation)`. An unnamed animation gets the name `Animation` (made unique). — [gltf_document.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/gltf_document.cpp)
- A bone track path is `path + ":" + bone`. `path` is the path of the skeleton from the parent of the player, and `bone` is the node name. A blend shape track path is the mesh instance path plus `:` plus the blend shape name. — [gltf_document.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/gltf_document.cpp)
- `remove_immutable_tracks = true` drops a TRS track when every key equals the base value of the node. `trimming = true` starts the clip at the first key. The animation step is `1.0 / bake_fps`. — [gltf_document.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/gltf_document.cpp)

**Extensions**

- The built-in set in `get_supported_gltf_extensions_hashset()` is: `GODOT_single_root`, `KHR_animation_pointer`, `KHR_lights_punctual`, `KHR_materials_emissive_strength`, `KHR_materials_pbrSpecularGlossiness`, `KHR_materials_unlit`, `KHR_node_visibility`, `KHR_texture_transform`. The function then adds the list of each registered `GLTFDocumentExtension`. — [gltf_document.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/gltf_document.cpp)
- `_parse_gltf_extensions` checks each entry of `extensionsRequired`. For an unsupported one it prints "glTF: Can't import file '…', required extension '…' is not supported. Are you missing a GLTFDocumentExtension plugin?" and returns `ERR_UNAVAILABLE`. — [gltf_document.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/gltf_document.cpp)
- The strings "draco" and "meshopt" do not appear in the parts of `gltf_document.cpp` that I read (characters 0 to 100,000 and 200,000 to 313,000). — [gltf_document.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/gltf_document.cpp)
- Proposal #8576, "Add additional hooks to GLTFDocument to support draco decompression via GDExtension", is open since 2023-12-03. It was the only proposal that matched draco, meshopt, or `KHR_mesh_quantization` in its title. — [godot-proposals#8576](https://github.com/godotengine/godot-proposals/issues/8576)

### Inferences

- Named binds at runtime need the flag in the call. A write of `state.use_named_skin_binds = true` before `append_from_*` has no effect, because the call overwrites the field from `flags`.

```gdscript
var doc := GLTFDocument.new()
var state := GLTFState.new()
var err := doc.append_from_buffer(bytes, "", state, GLTFDocument.IMPORT_FLAG_USE_NAMED_SKIN_BINDS)
if err != OK:
    return null            # ERR_UNAVAILABLE = a required extension is missing
var root := doc.generate_scene(state)
```

- Expected tree for a skinned character from Blender (inferred from the source lines above, not from a printed tree): `Root (Node3D)` > `Armature (Node3D)` > `Skeleton3D` > `Body (MeshInstance3D)`, plus `Root/AnimationPlayer`. Track paths then read `Armature/Skeleton3D:bone_name`. A rigid mesh with no skin stays where its glTF node is. If that node is inside the skeleton subtree, it becomes a bone (section 1).
- To take only the mesh and its `Skin` from a gear `.glb`: find each `MeshInstance3D` with a non-null `skin`, detach it, and free the rest of the tree (sketch in section 2). Set `state.create_animations = false` first, so a gear file makes no `AnimationPlayer`.
- For a `.glb` with embedded textures, `base_path` can be empty. For `append_from_buffer`, pass a string whose directory part is the wanted base, because the engine calls `get_base_dir()` on it.
- `IMPORT_FLAG_DISCARD_MESHES_AND_MATERIALS` fits an animation-only `.glb`: the client gets the skeleton and the `AnimationPlayer` with no mesh cost.
- The project rule "no Draco, no meshopt, no quantized meshes" agrees with the built-in list: none of `KHR_draco_mesh_compression`, `EXT_meshopt_compression`, `KHR_mesh_quantization` is in it. Call `GLTFDocument.get_supported_gltf_extensions()` in the 4.7 client one time to print the real list for that build.

### Gaps

- I did not read characters 100,000 to 200,000 of `gltf_document.cpp`. That part holds the mesh and accessor parse code. I cannot state from the source how the 4.7 loader treats a quantized accessor that a file does not mark as required.
- I did not read the extension lists of the built-in `GLTFDocumentExtension` classes (texture WebP, KTX, physics, and others).
- The source shows a function `_generate_scene_node_compat_4pt4`. Thus node generation changed after 4.4. I did not find what changed in the node tree, so the tree above can differ between 4.4 and 4.5 or later.
- No source states the load time or the memory cost of `generate_scene` on a web export.

## 4. Animations: one set for many characters, retargeting at runtime

### Takeaway

An `AnimationLibrary` is a resource, and many `AnimationPlayer` nodes can hold the same one through `add_animation_library()`. A track path resolves from `AnimationMixer.root_node` (default `..`), so one library drives every character whose tree has the same path to `Skeleton3D` and the same bone names. The `BoneMap` retarget options are import settings of the editor. I found no runtime API for them. The runtime tool for different rests is `RetargetModifier3D`.

### Cited Findings

- `AnimationMixer.root_node`, default `NodePath("..")`: "The node which node path references will travel from." — [AnimationMixer, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_animationmixer.html)
- `add_animation_library(name, library) -> Error` stores a library under a key. The empty string is the key of the global library. Also: `remove_animation_library(name)`, `get_animation_library(name)`, `get_animation_library_list()`, `has_animation(name)`, `get_animation(name)`, `find_animation_library(animation)`, `advance(delta)`. — [AnimationMixer, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_animationmixer.html)
- `callback_mode_process` default is `1` (idle frames). Signal `mixer_applied` fires when the blended result is on the targets. — [AnimationMixer, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_animationmixer.html)
- The runtime importer puts every clip of a file in the `""` library of the generated `AnimationPlayer`, with bone tracks of the form `<path to Skeleton3D>:<bone name>`. — [gltf_document.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/gltf_document.cpp)
- Retargeting is set up "in the advanced scene import menu": select the `Skeleton3D` node, and a Retarget section appears with the property `bone_map`. The preset `SkeletonProfileHumanoid` maps bones automatically. — [Retargeting 3D Skeletons, Docs 4.7](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/retargeting_3d_skeletons.html)
- Import options on that page: Remove Tracks (Except Bone Transform, Unimportant Positions, Unmapped Bones), Bone Renamer (Rename Bones, Unique Node with `skeleton_name`), Rest Fixer (Apply Node Transform, Normalize Position Tracks, Overwrite Axis, Fix Silhouette, `base_height_adjustment`). — [Retargeting 3D Skeletons, Docs 4.7](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/retargeting_3d_skeletons.html)
- "Overwrite Axis" unifies the bone rests to the reference poses of the profile. The page calls it "the most important option" for sharing in Godot 4, and warns of "horrible results" when the original rest matters. — [Retargeting 3D Skeletons, Docs 4.7](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/retargeting_3d_skeletons.html)
- "Unique Node" makes the skeleton a unique node, so track paths do not depend on the scene hierarchy. — [Retargeting 3D Skeletons, Docs 4.7](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/retargeting_3d_skeletons.html)
- Normalize Position Tracks stores the height of the scale-base bone in `Skeleton3D.motion_scale`. Playback multiplies position values by it. With the option off, `motion_scale` is `1.0`. — [Retargeting 3D Skeletons, Docs 4.7](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/retargeting_3d_skeletons.html)
- The page names an external "Realtime Retarget Module" (TokageItLab) for the case that must keep the original rest. — [Retargeting 3D Skeletons, Docs 4.7](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/retargeting_3d_skeletons.html)
- Godot 3 against Godot 4: a bone pose in Godot 3 is relative to the bone rest. A bone pose in Godot 4 includes the rest. — [Retargeting 3D Skeletons, Docs 4.7](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/retargeting_3d_skeletons.html)
- `RetargetModifier3D` (a `SkeletonModifier3D`) transfers poses from a parent skeleton to child skeletons "that have different rests". It works in model space. It "rewrites the pose of the child skeleton directly in the parent skeleton's update process." Properties: `profile: SkeletonProfile`, `enable: BitField[TransformFlag] = 7` (position 1, rotation 2, scale 4), `use_global_pose: bool = false`. With `use_global_pose` on, bone lengths must match exactly. — [RetargetModifier3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_retargetmodifier3d.html)
- A Godot 4.7 user solved mixed Mixamo sources with import-time retargeting on every model and every animation file. — [Godot Forum, July 2026](https://forum.godotengine.org/t/best-practice-for-attaching-weapons-items-to-a-characters-hand-across-many-animations-godot-4/141270)
- The body-groups tutorial drives its character with an `AnimationTree` (a `BlendSpace2D`) plus root motion from `get_root_motion_position()` and `get_root_motion_rotation()`. It warns that a re-import of a `.glb` can clear the `BoneMap` import setting. — [Godot Forum tutorial](https://forum.godotengine.org/t/3d-rpg-clothing-and-inventory-system-using-godot-4-and-blender/114842)
- 4.6 changed `AnimationPlayer.assigned_animation`, `autoplay`, and `current_animation` from `String` to `StringName` (GH-110767). GDScript stays compatible. — [Upgrading to Godot 4.6](https://docs.godotengine.org/en/stable/tutorials/migrating/upgrading_to_godot_4.6.html)

### Inferences

- Retargeting with `BoneMap` and `SkeletonProfileHumanoid` does not apply to a runtime-loaded file. The evidence: the manual describes only import-dock settings, and neither `GLTFDocument` nor `GLTFState` has a `BoneMap` argument or property in Docs 4.7. A file that the client loads with `GLTFDocument` gets its bone names and rests exactly as the file has them.
- Options to play a clip from file A on the skeleton of file B at runtime, cheapest first:
  1. Same rig in both files (same bone names, same rests, same node path to `Skeleton3D`). Take `player_a.get_animation_library("")` and call `player_b.add_animation_library(&"shared", lib)`. Keep the library in a cache, and give it to each new character.
  2. Same rig, different node path. Set `root_node` on the target player so that the track paths resolve, or build each character under the same node names.
  3. Different rests, same proportions. Put the target skeleton under the source skeleton with a `RetargetModifier3D` and a `SkeletonProfile`.
  4. Do the retarget offline. This project already has a build step with Blender and glTF Transform, so the pipeline can bake every body, every gear piece, and every clip to one canonical rig. The client then needs only option 1.
- Skinned gear needs no animation of its own. It deforms from the body `Skeleton3D`. A rigid item follows its `BoneAttachment3D`. Thus one `AnimationPlayer` for each character is enough.
- An animation-only `.glb` (loaded with `IMPORT_FLAG_DISCARD_MESHES_AND_MATERIALS`) is a natural container for the shared clip set.

### Gaps

- I did not read the `AnimationLibrary`, `AnimationTree`, `Animation`, `BoneMap`, or `SkeletonProfileHumanoid` class pages. I cannot cite the exact call that rewrites a track path, or state whether a script can use `BoneMap` outside the importer.
- No source states the version that added `RetargetModifier3D`. The 4.3 design article says built-in modifiers were planned for 4.4. Docs 4.7 has the class.
- I found no measured cost of `RetargetModifier3D` for many characters, and no report of it on the Compatibility renderer or on web.
- I found no GodotCon talk on this subject.

## 5. Hiding body parts under gear

### Takeaway

The approach with the most Godot 4 evidence is the simplest: split the body into regions as separate `MeshInstance3D` nodes on one skeleton, and set `visible` on the regions that an item covers. The one Godot 4 tutorial I found builds a small data scheme for it (an item names the body groups that it hides). I found no Godot 4 source for a mask shader or a blend shape approach.

### Cited Findings

- The body-groups tutorial (Godot 4.4.1) names each Blender object with a comma-separated list of groups. A `-` prefix means "this object hides that group". Example: `WornPants,Pants,-Legs,-Pelvis`, and `OfficeShirt,Shirt,-Torso`. — [Godot Forum tutorial](https://forum.godotengine.org/t/3d-rpg-clothing-and-inventory-system-using-godot-4-and-blender/114842)
- Its controller sets `visible` on each node of a group, then runs `resolve()` in two passes: show the nodes of equipped groups, then hide the nodes of each group that an equipped group covers. The key function as posted:

```gdscript
func get_covered_group(g:StringName):
	if g.begins_with("-"): return g.substr(1)
	return null
```

  — [Godot Forum tutorial, tail section](https://forum.godotengine.org/t/3d-rpg-clothing-and-inventory-system-using-godot-4-and-blender/114842)
- Limits that the author states: a cycle in the group graph gives unbounded recursion. A coat hid the whole torso after the shirt was split in two, because of the group graph. Commenters said a hard-coded layer order can suit a game with fixed armor sets. — [Godot Forum tutorial, tail section](https://forum.godotengine.org/t/3d-rpg-clothing-and-inventory-system-using-godot-4-and-blender/114842)
- The same tutorial keeps the seams of a split body closed with a Blender Data Transfer modifier that copies normals and weights from the original mesh. — [Godot Forum tutorial](https://forum.godotengine.org/t/3d-rpg-clothing-and-inventory-system-using-godot-4-and-blender/114842)
- A godotforums.org thread recommends each clothing item as a separate mesh on the same skeleton with show and hide, and a body split into head, chest, arms, and legs, with the covered parts hidden for each item by hand (search summary, the page did not load for me). — [godotforums.org 28258](https://godotforums.org/d/28258-3d-rigged-animated-characters-and-interchangeable-clothing)
- An old Godot forum thread (before Godot 3, search summary) lists two more ideas: delete the hidden body faces in Blender, or use a clothing shader that moves vertices a little toward the camera. — [Godot Forum, "How can I hide poly behind clothes"](https://forum.godotengine.org/t/how-can-i-hide-poly-behind-clothes/30980)
- Not Godot: MakeHuman clothing has a "Delete" vertex group. The tool can delete those body vertices when the item goes on. A deleted vertex removes each face that uses it. — [MakeHuman, MakeClothes](https://static.makehumancommunity.org/assets/creatingassets/makeclothes/clothes.html)
- Not Godot: Reallusion Character Creator hides the inner mesh with a grayscale mask texture on the UV map of the body (search summary). — [Reallusion manual](https://manual.reallusion.com/Character_Creator/ENU/1/08_Cloth/Conforming_Clothing_Basic.htm)
- Godot API for the surface route: `set_surface_override_material(surface, material)` sets a material for one surface of one `MeshInstance3D`. It does not change the `Mesh` resource. — [MeshInstance3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_meshinstance3d.html)
- Godot API for the blend shape route: `find_blend_shape_by_name(name) -> int` (-1 when absent) and `set_blend_shape_value(blend_shape_idx, value)`. — [MeshInstance3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_meshinstance3d.html)
- The one-GLB route keeps each outfit as a `MeshInstance3D` that toggles on and off. The asker notes that unused outfits still use VRAM, and that the node count grows. — [Godot Forum, January 2026](https://forum.godotengine.org/t/managing-scalability-of-skeleton-animation-and-outfits-for-3d-characters-from-blender-to-godot/130681)

### Inferences

- Options and my judgement for an Old School RuneScape style low-poly client on the Compatibility renderer:

| Option | How | For | Against |
|---|---|---|---|
| Region meshes | Body is N `MeshInstance3D` nodes (head, torso, arms, hands, legs, feet). Item data lists the regions that it hides. Set `visible`. | No shader. Hidden regions cost nothing. Has Godot 4 evidence. | Hard cut at each region edge. More draw calls for each character. |
| Region surfaces | One body mesh, one surface for each region. Hide a region with a fully transparent or discard material through `set_surface_override_material`. | One node. | The hidden surface still goes through the pipeline. Same hard edges. |
| Item replaces region | The gear mesh includes the skin that still shows (a glove mesh includes the wrist). Hide the whole region. | Matches low-poly art, where the item IS the body part. | Each item must model the visible skin. |
| Mask in a shader | Paint a region id into vertex color or UV2. The body shader discards a fragment whose region bit is set in a uniform. | One mesh, one material, fine regions. | Custom shader on every body. No Godot 4 source found. Discard has a cost on mobile GPUs. |
| Blend shapes | A "shrink torso" shape pulls the body in under the item. | Fixes poke-through with no cut. | Each body needs the shapes. Extra vertex work. Does not remove overdraw. |
| Delete faces at build | The pipeline cuts hidden faces for each body and item pair. | Smallest runtime cost. | One baked mesh for each pair. Not practical with many items. |

- The item should name the regions that it hides, as data. The body-groups naming scheme is one working model. That fits the "server names, client draws" rule of this project: the hide list can travel with the model record.
- A per-instance uniform is a poor carrier for a region mask on web with this renderer (section 6). A material parameter on a material that the character owns is safer.

### Gaps

- I found no Godot 4 tutorial, forum answer, or sample project that uses an alpha mask, a vertex colour mask, or a UV mask in a shader to hide body regions. The table rows for those are my own analysis.
- I found no source on the cost of blend shapes together with skinning on the Compatibility renderer or on WebGL2.
- The godotforums.org thread 28258 did not load. Its content here comes from a search summary only.

## 6. Recolor of one mesh to make many items

### Takeaway

`set_surface_override_material()` with a small cache of duplicated materials is the safe path on Godot 4.7 with the Compatibility renderer on web. Per-instance uniforms work in the Compatibility renderer since 4.4, but on that renderer they share one small uniform buffer. An open issue shows black colours on web export after roughly 20 instances, and the fix is still an open pull request for 4.8.

### Cited Findings

- `set_surface_override_material(surface, material)`: the material belongs to this `MeshInstance3D`, not to the `Mesh`. `Mesh.surface_set_material()` changes the resource itself. — [MeshInstance3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_meshinstance3d.html)
- `get_active_material(surface)` returns the material that draws: `GeometryInstance3D.material_override` first, then the surface override, then the surface material of the mesh. — [MeshInstance3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_meshinstance3d.html)
- `material_override` takes precedence over every material slot of the mesh. `material_overlay` draws on top of every surface. — [GeometryInstance3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_geometryinstance3d.html)
- `set_instance_shader_parameter(name: StringName, value: Variant)` sets a uniform for one instance. The shader must declare it with `instance uniform`. The name is case-sensitive. It works only in spatial and canvas item shaders. — [GeometryInstance3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_geometryinstance3d.html)
- Shader side: `instance uniform vec4 my_color : source_color = vec4(1.0, 0.5, 0.0, 1.0);`. — [Shading language, Docs 4.7](https://docs.godotengine.org/en/stable/tutorials/shaders/shader_reference/shading_language.html)
- "Per-instance uniforms do not support textures or arrays, only regular scalar and vector types." "There is a practical maximum limit of 16 instance uniforms per shader." The hint `instance_index(n)` (0 to 15) sets the slot by hand. — [Shading language, Docs 4.7](https://docs.godotengine.org/en/stable/tutorials/shaders/shader_reference/shading_language.html)
- If one mesh uses several materials, the parameters of the first material "win" on a clash. — [Shading language, Docs 4.7](https://docs.godotengine.org/en/stable/tutorials/shaders/shader_reference/shading_language.html)
- Compatibility renderer limit in the manual: in GLSL 3.3 and lower "you cannot directly index a texture array using a per-instance uniform." The manual tells such a shader to select the texture with a `switch`. — [Shading language, Docs 4.7](https://docs.godotengine.org/en/stable/tutorials/shaders/shader_reference/shading_language.html)
- PR #96819 "Implement instance uniforms in Compatibility renderer" merged on 2024-10-07 with the 4.4 milestone. It closes godot-proposals#6909. A docs PR (godot-docs#9939) removed the note that said the Compatibility backend did not support them. Thus Godot 4.3 and earlier do NOT have them on this renderer. — [godot PR #96819](https://github.com/godotengine/godot/pull/96819)
- Issue #100080 "Shader with instance uniforms fails in compatibility" closed on 2024-12-14 for 4.4. — [godot#100080](https://github.com/godotengine/godot/issues/100080)
- Issue #112674 (open, Godot 4.5.1): "Shader instance uniform colors black on web export but not otherwise using compatibility rederer". With more than about 20 instances, the last ones draw correctly and the earlier ones draw black. Reproduced in Chrome and Firefox on Linux and in Firefox on Android. A commenter reports that invisible nodes count toward the limit, and that an unrelated material also went black. — [godot#112674](https://github.com/godotengine/godot/issues/112674)
- PR #124336 (open, created 2026-10-09, milestone 4.8) gives the cause: instance shader parameters share the global shader parameter uniform buffer. OpenGL guarantees only 16,384 bytes for it. Each node uses about 256 bytes. That allows roughly 64 nodes at the minimum size and 256 on common desktop hardware. The PR moves the storage to a texture and says it fixes #114949, #112674, and #108151. — [godot PR #124336](https://github.com/godotengine/godot/pull/124336)
- A comment on PR #96819 from August 2025 reports that instance uniforms do not work on Galaxy S25 devices with an Adreno 830 GPU. — [godot PR #96819](https://github.com/godotengine/godot/pull/96819)

### Inferences

- On Godot 4.7, web export, Compatibility renderer: do not use `instance uniform` for item tint or character tint when a scene can hold more than a few tens of such nodes. The fix is not in 4.7, because the pull request is open with the 4.8 milestone.
- The safe recolor paths on this renderer are ordinary material state:
  1. A material for each colour variant, made one time and cached by key (`"<base material id>:<colour>"`). Assign it with `set_surface_override_material`. Characters with the same item and colour share one material.
  2. A palette texture: the mesh UVs point into a small palette image. A recolor is a swap of that one texture on a duplicated material. This fits flat-shaded low-poly art.
  3. Vertex colours that the pipeline bakes for each variant. This costs one mesh for each variant, so it suits a fixed set of variants only.
- `material_override` replaces every surface at once. It suits a whole-item effect (ghost, hit flash), not a recolor of one surface.
- Sketch (not from a source, not run):

```gdscript
var _tints: Dictionary = {}   # key -> Material

func tinted(base: BaseMaterial3D, colour: Color) -> Material:
    var key := "%d:%s" % [base.get_instance_id(), colour.to_html()]
    if not _tints.has(key):
        var m := base.duplicate() as BaseMaterial3D
        m.albedo_color = colour
        _tints[key] = m
    return _tints[key]

# mi.set_surface_override_material(0, tinted(mi.mesh.surface_get_material(0), colour))
```

### Gaps

- I did not read the `BaseMaterial3D` page. The sketch uses `albedo_color` from my own knowledge. The flag that makes vertex colour act as albedo is also not cited here.
- I found no Godot-specific source on palette textures for item variants.
- No source gives the exact instance limit on WebGL2. The "about 20" figure is one report, and the "64" figure is an estimate in an open pull request.
- I did not read issues #114949 and #108151.

## 7. Known bugs and limits in Godot 4.x

### Takeaway

Most `BoneAttachment3D` faults that matter for runtime-built characters were fixed in 4.5: attachments stuck at the skeleton origin, and lag with physics interpolation. The open risks on 4.7 are: `reparent()` of an attachment, a changed external skeleton at runtime, wrong bounds on skinned meshes (#85171, open), and per-instance uniforms on web (#112674, open).

### Cited Findings

**BoneAttachment3D**

| Issue | State and version | Subject |
|---|---|---|
| [#103683](https://github.com/godotengine/godot/issues/103683) | Closed 2025-04-28, milestone 4.5 | "[4.4] BoneAttachment3D is lagging behind bone (regression from 4.3) if physics interpolation is enabled" |
| [#95751](https://github.com/godotengine/godot/issues/95751) | Closed 2025-10-24, milestone 4.5 | "All BoneAttachment3D stays in Skeleton3D's origin until pose is updated" |
| [#100655](https://github.com/godotengine/godot/issues/100655) | Closed 2026-08-18, milestone 4.8 | "BoneAttachment3D doesn't update position / rotation of attachment correctly" |
| [#118218](https://github.com/godotengine/godot/issues/118218) | Closed 2026-05-15, milestone 4.7 | Error `Condition "!is_inside_tree()" is true` when an instanced attachment has an external skeleton |
| [#109366](https://github.com/godotengine/godot/issues/109366) | Closed 2025-08-11, milestone 4.5 | The attachment read the global transform of an external skeleton before the skeleton was in the tree |
| [#109110](https://github.com/godotengine/godot/issues/109110) | Closed 2025-08-22, milestone 4.5 | `LookAtModifier3D` plus an attachment with override pose and external skeleton stopped on pause |
| [#105616](https://github.com/godotengine/godot/issues/105616) | Closed 2025-06-21, milestone 4.5 | "BoneAttachment3D snaps to bone position only after reloading the scene window" |
| [#92813](https://github.com/godotengine/godot/issues/92813) | Closed 2024-08-16, no milestone | "Add BoneAttachment3D programmatically gives wrong GlobalPosition" |
| [#92098](https://github.com/godotengine/godot/issues/92098) | Closed 2024-05-19, milestone 4.3 | With `override_pose`, the bone updated only when the local transform changed |
| [#81552](https://github.com/godotengine/godot/issues/81552) | Closed 2023-09-14 | Errors when an attachment left the tree and entered again |
| [#98204](https://github.com/godotengine/godot/issues/98204) | OPEN | "BoneAttachment3D signal error after re-set the external skeleton during gameplay" |
| [#91864](https://github.com/godotengine/godot/issues/91864) | OPEN | "Using .reparent() on a BoneAttachment3D during runtime breaks it." |
| [#87804](https://github.com/godotengine/godot/issues/87804) | OPEN | "Queue_free()'ing a BoneAttachment3D in an exported build throws a signal error" |
| [#92775](https://github.com/godotengine/godot/issues/92775) | OPEN | "Animated BoneAttachment3D Performance Impact" |

- #103683 detail: reproduced on 4.4.stable, not on 4.3.stable. The attached object trails the bone, and hair or equipment clips constantly. The lag "happens only during physics interpolation". Workaround from a maintainer (lawnjelly): turn physics interpolation off on the attachment in the inspector. Closed by PR #104269 "Physics Interpolation - Move 3D FTI to SceneTree", merged 2025-04-28 for 4.5. The page shows no cherry-pick to 4.4.x. Issue #107317 is a duplicate. — [godot#103683](https://github.com/godotengine/godot/issues/103683), [godot PR #104269](https://github.com/godotengine/godot/pull/104269)
- In 4.7 the attachment defaults to interpolation off: Docs 4.7 shows `physics_interpolation_mode` overridden to `2`, and the constructor on master sets `PHYSICS_INTERPOLATION_MODE_OFF`. — [BoneAttachment3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_boneattachment3d.html), [bone_attachment_3d.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/scene/3d/bone_attachment_3d.cpp)
- #95751 detail: reproduced on 4.3.stable, not on 4.2.2. An attachment added at runtime stayed at the origin of the skeleton "until very first bone pose update". Workarounds: call `reset_bone_poses()` on the skeleton after the add, then run the placement code with `call_deferred()`. `ForceUpdateBoneChildTransform()` did not help. The reporter confirmed the fix on 4.5 after PR #104209. — [godot#95751](https://github.com/godotengine/godot/issues/95751)
- #91864 detail: tested on 4.3.dev6 and 4.2.2. After `reparent()`, an attachment with external skeleton and override pose "will stop having any effects". A new assignment of the external skeleton at runtime did not repair it. No pull request. — [godot#91864](https://github.com/godotengine/godot/issues/91864)
- One-frame trail of nodes that READ an attachment: a Godot 4.4.1 user saw hurtbox shapes on attachments draw in the pose of the previous frame. A forum user (not a maintainer) explained that the attachment updates after the skeleton pose is calculated, and recommended a manual update or direct use of the bone transform. No GitHub issue is linked. — [Godot Forum, June 2025](https://forum.godotengine.org/t/boneattachment3d-trailing-behind-why/112929)
- The engine side of that: the skeleton update is a deferred call, and it runs one time per frame after the animation. The attachment moves inside the `skeleton_updated` signal of that update. — [Design of the Skeleton Modifier 3D](https://godotengine.org/article/design-of-the-skeleton-modifier-3d/), [bone_attachment_3d.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/scene/3d/bone_attachment_3d.cpp)
- `override_pose` can behave unexpectedly together with a `SkeletonModifier3D`. — [BoneAttachment3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_boneattachment3d.html)

**Skin and skeleton mismatch**

- A named bind with no bone of that name prints "Skin bind #… but Skeleton3D has no bone by that name." and binds to bone 0. An index bind out of range prints "contains bone index bind" and binds to bone 0. The mesh still draws. — [skeleton_3d.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/scene/3d/skeleton_3d.cpp)
- A `skeleton` path that does not reach a `Skeleton3D` detaches the mesh with no error. — [mesh_instance_3d.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/scene/3d/mesh_instance_3d.cpp)
- 4.6 changed the default of `MeshInstance3D.skeleton` from `..` to empty (PR #112267). Code that relied on "child of the skeleton binds by itself" stops skinning on 4.6 or later unless the project setting is on. — [godot PR #112267](https://github.com/godotengine/godot/pull/112267), [Upgrading to Godot 4.6](https://docs.godotengine.org/en/stable/tutorials/migrating/upgrading_to_godot_4.6.html)

**Bounds and culling of skinned meshes**

- Issue #85171 "AABB broken on imported meshes with skeletons" is OPEN, with no milestone and no confirmed cause. First seen on 4.2 RC1. The bounds do not match the visible mesh and do not follow the animation. Deleting the skeleton gives correct bounds. — [godot#85171](https://github.com/godotengine/godot/issues/85171)
- Workarounds in that issue: set `custom_aabb` (the commenter smix8 calls this "an expected step" for animated assets), apply transforms on the armature in Blender (works for some models only), or compute the bounds in GDScript from the skinned vertices. Related issue numbers: #80306, #84451, #85018. — [godot#85171](https://github.com/godotengine/godot/issues/85171)
- `custom_aabb: AABB` replaces the automatic bounds. The all-zero default means automatic. A very large box avoids frustum culling. `extra_cull_margin: float = 0.0` adds distance to the bounds. — [GeometryInstance3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_geometryinstance3d.html)
- A Godot 4.6 forum thread on an active ragdoll: a larger `extra_cull_margin` kept the mesh visible but did not fix the LOD switch (search summary). — [Godot Forum, "Culling issue on active ragdoll"](https://forum.godotengine.org/t/culling-issue-on-active-ragdoll/139288)
- Issue #72998: animated meshes disappeared because automatic LODs switched too early. Workaround: no LOD generation at import, or a higher LOD bias. A maintainer said AABB changes in 4.1 possibly fixed it (search summary). — [godot#72998](https://github.com/godotengine/godot/issues/72998)
- `lod_bias: float = 1.0` on `GeometryInstance3D` controls the switch distance. — [GeometryInstance3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_geometryinstance3d.html)

**Runtime glTF**

- A file with an unsupported entry in `extensionsRequired` returns `ERR_UNAVAILABLE` from the append call. — [gltf_document.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/gltf_document.cpp)
- `flags` overwrites `GLTFState.use_named_skin_binds`. The runtime default is index binds. — [gltf_document.cpp, master](https://raw.githubusercontent.com/godotengine/godot/master/modules/gltf/gltf_document.cpp)
- `bake_mesh_from_current_skeleton_pose()` reads mesh data back from the GPU and stalls the `RenderingServer`. It ignores blend shapes and does not copy materials. — [MeshInstance3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_meshinstance3d.html)

**Compatibility renderer and web export**

- Per-instance uniforms: not available on this renderer before 4.4 (PR #96819). On 4.5.1 web export they can draw black past a small instance count (#112674, open). The fix PR #124336 is open for 4.8. — [godot PR #96819](https://github.com/godotengine/godot/pull/96819), [godot#112674](https://github.com/godotengine/godot/issues/112674), [godot PR #124336](https://github.com/godotengine/godot/pull/124336)
- `GeometryInstance3D` visibility range fade modes (Fade Self, Fade Dependencies) work only in Forward+. `transparency` is ignored in Mobile and Compatibility. — [GeometryInstance3D, Docs 4.7](https://docs.godotengine.org/en/stable/classes/class_geometryinstance3d.html)
- A title search for skinned, skeleton, skinning, compatibility, and web in rendering issues gave four hits. None is about skinned meshes: #112674 (instance uniforms), #93537 (shadows on Mac browsers, fixed 4.3), #82564 and #82565 (light crashes, fixed 4.2). — [GitHub search API](https://api.github.com/search/issues?q=skinned+OR+skeleton+OR+skinning+compatibility+web+repo:godotengine/godot+is:issue+in:title+label:topic:rendering&per_page=40)

### Inferences

- The trail in the hurtbox thread and the lag in #103683 are two different things. #103683 was a real fault with physics interpolation, fixed in 4.5. The hurtbox trail is an order effect: a script that reads the transform of an attachment in `_process()` or `_physics_process()` runs before the deferred skeleton update of that frame, so it reads the pose of the previous frame. The mesh on the attachment draws in step with the skin, because both come from the same update. To read the current pose, connect to `Skeleton3D.skeleton_updated`.
- For a character built at runtime on 4.7: add the attachment to the tree, then set `bone_name`. Do not `reparent()` an attachment. Free it and make a new one (#91864 is open). Avoid a change of `external_skeleton` on a live attachment (#98204 is open).
- Gear that moves to a body skeleton keeps the bounds data of its own mesh. Because #85171 is open, give each skinned body and gear `MeshInstance3D` a generous `custom_aabb` (or `extra_cull_margin`) at attach time. For a low-poly game the cost of a loose box is small.
- The runtime loader does not run the editor import step that generates LODs, so the LOD fault of #72998 probably cannot occur for a runtime-loaded mesh. I did not confirm this.

### Gaps

- I did not read #100655 (fix in 4.8). I do not know its trigger, so I cannot say whether a 4.7 client meets it.
- The first three items of the GitHub title search for "BoneAttachment3D" (21 hits) were cut from the response. The table can miss up to three issues.
- I found no confirmed root cause for #85171, and no statement on whether a mesh bound to an EXTERNAL skeleton (not its parent) has worse bounds. The mirror commit "Transform mesh's AABB to skeleton's space when calculate mesh's bounds" appeared in a search result. I could not tie it to a version. — [commit mirror](https://remotebranch.eu/Stowage/godot/commit/27f71c4e78db2f502d730f5e34a540665c45af27)
- I found no issue about skinned meshes or bone count that is specific to WebGL2. That is a lack of evidence, not proof of no limit.
- Several results from bugnet.io matched these subjects. They read like generated text, and I did not use them.

## 8. Maintained add-ons and open-source sample projects

### Takeaway

I found no maintained Asset Library add-on that equips runtime-loaded `.glb` gear on a shared skeleton. The useful references are one tutorial with a repository (body-groups), one large character generator (Humanizer), and one game template. Each of them works with scenes that the editor imports, not with runtime `GLTFDocument` loads.

### Cited Findings

- **Roboticy3/body-groups** (with the forum tutorial, 2025-06-30, Godot 4.4.1, Blender 4.4, CC BY-NC 4.0). Approach: each clothing item is a `PackedScene`. Loader nodes (`HelmetLoader`, `ChestplateLoader`) call `add_child` on equip. Blender object names carry group lists, and a `-` prefix hides a body group. Custom `NodeGroup` and `NodeGroupSet` resources replace scene-local groups, which Godot lacks. Equipment slots call `equip()` and `unequip()` on nodes in the `"Equip"` group. — [Godot Forum tutorial](https://forum.godotengine.org/t/3d-rpg-clothing-and-inventory-system-using-godot-4-and-blender/114842), [Roboticy3/body-groups](https://github.com/Roboticy3/body-groups)
- **NitroxNova/humanizer**: "3D Character Creator" plugin for Godot 4.3 that converts MakeHuman content to Godot 4. 293 stars, 1,067 commits. The wiki says the plugin includes "Base clothing and body part assets from MakeHuman", has pages named Equipment, Rigging Equipment, and Working with Equipment, lets clothing and body parts have bones, changes eye, hair, and skin colour with an overlay approach, and accepts Mixamo animations on its retargeted rigs. — [NitroxNova/humanizer](https://github.com/NitroxNova/humanizer), [humanizer wiki](https://github.com/NitroxNova/humanizer/wiki)
- Humanizer license: the GitHub sidebar shows AGPL-3.0. The Asset Library listing shows CC0 and version 2.2.0 (search summary). The two sources conflict. — [NitroxNova/humanizer](https://github.com/NitroxNova/humanizer); contradicted by [Godot Asset Library 3699](https://godotengine.org/asset-library/asset/3699)
- **catprisbrey/Cats-Godot4-Modular-Souls-like-Template**: Unlicense, version 2.0.0, 430 stars, last push 2025-12-21. Features: "Primary weapon", "Offhand gadgets", "Consumable items", root motion. It "uses an animation library to drive its animations", and it accepts a model with a standard skeleton "mapped into Godot at import". The README announces a 3.0 with a different codebase. The README does not explain how the weapon attaches. — [Cats-Godot4-Modular-Souls-like-Template](https://github.com/catprisbrey/Cats-Godot4-Modular-Souls-like-Template)
- **imp0str "Modular 3D Character System - Godot 4.7.x"** on itch.io: a paid add-on in beta that advertises a character switch at runtime with no loss of controller, camera, animation, or customization state (search summary). — [itch.io](https://imp0str.itch.io/modular-3d-character-system)
- **TokageItLab realtime_retarget**: an engine module that the retargeting manual names, for shared animations that keep the original bone rest. — [Retargeting 3D Skeletons, Docs 4.7](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/retargeting_3d_skeletons.html)
- **Flynsarmy/gd-synty-fantasy-heroes-import-scripts**: helper scripts to import the Synty Modular Fantasy Hero pack. 31 stars, last push 2023-10-01. — [GitHub](https://github.com/Flynsarmy/gd-synty-fantasy-heroes-import-scripts)
- **thowsenmedia "Godot Character Creation Suite"** on itch.io: early access, and its own page admits a lack of clothing (search summary). — [itch.io](https://thowsenmedia.itch.io/godot-character-creation-suite)
- Not relevant in spite of the name: `expressobits/character-controller` (435 stars) and `PantheraDigital/Modular-Character-Controller-for-Godot` (53 stars) are movement and logic controllers. They do not handle meshes or skeletons. — [expressobits/character-controller](https://github.com/expressobits/character-controller), [PantheraDigital](https://github.com/PantheraDigital/Modular-Character-Controller-for-Godot)

### Inferences

- No project found here loads gear with `GLTFDocument` at runtime and rebinds it. The Blackout client must write that step itself (sections 2 and 3). The data scheme of body-groups (an item lists what it hides) is the part most worth copying.
- Humanizer is a poor fit for an Old School RuneScape look: it builds MakeHuman bodies. Its license is also unclear until someone reads the repository license file.
- A repository search sorted by stars gave mostly unrelated "modular" projects. The equipment niche has few open projects, and none is a standard.

### Gaps

- I did not read the source of any of these projects. I cannot state whether Humanizer deletes body vertices under clothing, bakes meshes together, or works in an exported game. The wiki home page did not say.
- I did not read the `player` scenes of the souls-like template, so its attach method is unknown.
- The GitHub repository search response was cut after 18 results. Relevant projects further down the list can be missing.
- I did not search the Godot Asset Library directly by category. Its search pages did not come up in my results.
- I found no KidsCanCode or GDQuest tutorial on equipment or modular characters for Godot 4, and no GodotCon talk. I did not search each site directly, so this is "not found", not "does not exist".
