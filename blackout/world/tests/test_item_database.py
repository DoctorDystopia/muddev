"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/01/2026
Description: Regression tests for ItemDef, which now renders exactly one
             prototype that both the direct-creation and crafting paths spawn
             from.

Run with:
    evennia test --settings settings.py world
"""



from evennia.prototypes.spawner import spawn
from evennia.utils.test_resources import EvenniaTest

from typeclasses.characters import Character as BlackoutCharacter
from world.item_database import ITEM_DB



# Public constant definitions

# An item that stacks, and one that does not. Named rather than discovered so
# a failure points at a specific definition.
STACKABLE_KEY = "credits"
NON_STACKABLE_KEY = "hammer"

# An ItemDef tag is a (key, category) pair. Evennia's TagHandler.batch_add
# reads any third element as tag DATA, not as a second category.
_TAG_TUPLE_LENGTH = 2



class TestCreatePrototypeParity(EvenniaTest):
    """create() must add nothing beyond what the prototype declares.

    The old drift -- create() writing tier/req_level even when zero and a
    quantity to_prototype() never emitted, while to_prototype() dropped
    tier/req_level when falsy -- is now prevented by construction, since
    create() spawns the very prototype to_prototype() returns. So this class
    is a guard rather than a proof: it fails if someone reintroduces a manual
    attributes.add into create(). TestSpawnedAttributesMatchDefinition below
    is what actually checks the rendering is correct.
    """

    character_typeclass = BlackoutCharacter

    def _attrs_of(self, obj):
        """Every attribute on obj as a plain name -> value dict."""
        collected = {}
        for attr in obj.attributes.all():
            collected[attr.key] = attr.value

        return collected

    def test_every_itemdef_creates_and_spawns_identically(self):
        for item_key, item_def in ITEM_DB.items():
            created = item_def.create()
            spawned = spawn(item_def.to_prototype())[0]

            created_attrs = self._attrs_of(created)
            spawned_attrs = self._attrs_of(spawned)

            self.assertEqual(
                created_attrs,
                spawned_attrs,
                msg=f"attribute drift between create() and spawn() for {item_key!r}",
            )
            self.assertEqual(created.key, spawned.key, msg=item_key)
            self.assertEqual(
                created.typeclass_path, spawned.typeclass_path, msg=item_key
            )

    def test_every_itemdef_tags_match(self):
        for item_key, item_def in ITEM_DB.items():
            created = item_def.create()
            spawned = spawn(item_def.to_prototype())[0]

            created_tags = sorted(created.tags.all(return_key_and_category=True))
            spawned_tags = sorted(spawned.tags.all(return_key_and_category=True))

            self.assertEqual(created_tags, spawned_tags, msg=item_key)



class TestSpawnedAttributesMatchDefinition(EvenniaTest):
    """Every ItemDef field must survive the round trip onto a real object.

    This is the non-tautological half: it compares a spawned object against
    the ItemDef's own field values rather than against another spawn. It is
    what catches a value being dropped or mangled in _get_attrs -- the failure
    mode that once silently emptied every prototype when `attrs` was handed
    over as a dict instead of a list of tuples.
    """

    character_typeclass = BlackoutCharacter

    def test_scalar_fields_reach_the_object(self):
        for item_key, item_def in ITEM_DB.items():
            obj = item_def.create()

            self.assertEqual(obj.key, item_def.name, msg=item_key)
            self.assertEqual(
                obj.attributes.get("value"), item_def.value, msg=item_key
            )
            self.assertEqual(
                obj.attributes.get("weight"), item_def.weight, msg=item_key
            )
            self.assertEqual(
                obj.attributes.get("tradeable"), item_def.tradeable, msg=item_key
            )
            self.assertEqual(
                obj.attributes.get("stackable"), item_def.stackable, msg=item_key
            )
            self.assertEqual(
                obj.attributes.get("tier"), item_def.tier, msg=item_key
            )
            self.assertEqual(
                obj.attributes.get("req_level"), item_def.req_level, msg=item_key
            )

    def test_optional_fields_reach_the_object_when_set(self):
        for item_key, item_def in ITEM_DB.items():
            obj = item_def.create()

            if item_def.desc:
                self.assertEqual(obj.db.desc, item_def.desc, msg=item_key)
            if item_def.tool_type is not None:
                self.assertEqual(
                    obj.attributes.get("tool_type"),
                    item_def.tool_type,
                    msg=item_key,
                )
            if item_def.use_slot is not None:
                self.assertEqual(
                    obj.inventory_use_slot, item_def.use_slot, msg=item_key
                )

    def test_combat_fields_reach_weapons(self):
        weapon_defs = [
            (key, defn) for key, defn in ITEM_DB.items() if defn.combat_styles
        ]

        self.assertTrue(weapon_defs, "expected at least one weapon in ITEM_DB")

        for item_key, item_def in weapon_defs:
            obj = item_def.create()

            self.assertEqual(
                obj.attributes.get("attack_speed"),
                item_def.attack_speed,
                msg=item_key,
            )
            self.assertEqual(
                dict(obj.attributes.get("combat_stat_bonuses")),
                item_def.combat_stat_bonuses,
                msg=item_key,
            )
            self.assertEqual(
                obj.attributes.get("default_combat_style"),
                item_def.default_combat_style,
                msg=item_key,
            )

    def test_every_declared_tag_is_a_key_category_pair(self):
        """Tags go straight to Evennia's TagHandler.batch_add, which reads a
        THIRD tuple element as tag *data*, not as a second category. Writing
        ("broken_bit_blade", "bit_blade", "weapon") therefore filed the item
        under category "bit_blade" and silently dropped it out of the "weapon"
        family -- which is what statefeed/serializers._family_of reads to pick
        a mesh, so those weapons rendered as generic props in the 3D client.

        Checked as its own test because the failure is invisible at runtime:
        nothing raises, the item just quietly stops being a weapon.
        """
        for item_key, item_def in ITEM_DB.items():
            for tag in item_def.tags:
                self.assertEqual(
                    len(tag),
                    _TAG_TUPLE_LENGTH,
                    msg=(
                        f"{item_key} declares tag {tag!r}; ItemDef tags must be "
                        f"(key, category) pairs -- a third element becomes tag "
                        f"DATA and pushes the item out of its family category."
                    ),
                )

    def test_declared_tags_reach_the_object(self):
        for item_key, item_def in ITEM_DB.items():
            obj = item_def.create()

            for tag_key, tag_category in item_def.tags:
                self.assertTrue(
                    obj.tags.get(tag_key, category=tag_category),
                    msg=f"{item_key} missing tag {tag_key!r}/{tag_category!r}",
                )



class TestPrototypeContent(EvenniaTest):
    """What a rendered prototype must carry."""

    character_typeclass = BlackoutCharacter

    def test_prototype_key_is_the_itemdef_key(self):
        """Without this the spawned object carries no prototype tag and its
        origin cannot be recovered."""
        item_def = ITEM_DB[NON_STACKABLE_KEY]
        prototype = item_def.to_prototype()

        self.assertEqual(prototype["prototype_key"], NON_STACKABLE_KEY)

    def test_attrs_are_tuples_not_a_dict(self):
        """A dict here iterates keys only and silently drops every value."""
        prototype = ITEM_DB[NON_STACKABLE_KEY].to_prototype()

        self.assertIsInstance(prototype["attrs"], list)
        for entry in prototype["attrs"]:
            self.assertIsInstance(entry, tuple)

    def test_tier_and_req_level_are_always_emitted(self):
        """Both used to be dropped from the prototype when zero, so a crafted
        item lacked attributes its gathered twin had."""
        for item_key, item_def in ITEM_DB.items():
            attr_names = [name for name, _value in item_def.to_prototype()["attrs"]]

            self.assertIn("tier", attr_names, msg=item_key)
            self.assertIn("req_level", attr_names, msg=item_key)

    def test_stackable_carries_quantity_and_others_do_not(self):
        stackable_attrs = dict(ITEM_DB[STACKABLE_KEY].to_prototype()["attrs"])
        plain_attrs = dict(ITEM_DB[NON_STACKABLE_KEY].to_prototype()["attrs"])

        self.assertIn("quantity", stackable_attrs)
        self.assertNotIn("quantity", plain_attrs)

    def test_requested_quantity_reaches_the_prototype(self):
        prototype = ITEM_DB[STACKABLE_KEY].to_prototype(quantity=42)
        attrs = dict(prototype["attrs"])

        self.assertEqual(attrs["quantity"], 42)



class TestCreatePlacement(EvenniaTest):
    """Where create() puts the object, and what the move triggers."""

    character_typeclass = BlackoutCharacter

    def test_detached_when_no_location_given(self):
        obj = ITEM_DB[NON_STACKABLE_KEY].create()

        self.assertIsNone(obj.location)

    def test_placed_in_the_requested_location(self):
        obj = ITEM_DB[NON_STACKABLE_KEY].create(location=self.char1)

        self.assertEqual(obj.location, self.char1)

    def test_home_defaults_to_location(self):
        obj = ITEM_DB[NON_STACKABLE_KEY].create(location=self.char1)

        self.assertEqual(obj.home, self.char1)

    def test_spawned_object_carries_the_prototype_tag(self):
        obj = ITEM_DB[NON_STACKABLE_KEY].create(location=self.char1)
        tag_keys = obj.tags.all()

        self.assertIn(NON_STACKABLE_KEY, tag_keys)

    def test_attributes_exist_before_the_move(self):
        """The reason the prototype carries no `location`. Spawning straight
        into a character runs at_object_receive before the attributes are
        written, and the stack-merge reads `stackable` and `quantity` to
        decide what to do."""
        obj = ITEM_DB[STACKABLE_KEY].create(location=self.char1, quantity=5)

        self.assertTrue(obj.attributes.get("stackable"))

    def test_stackables_merge_into_one_stack(self):
        """create_object assigned db_location directly and never fired
        at_object_receive, so items made this way were not registered in an
        inventory slot and never merged -- a later inventory.sync() had to
        repair it. move_to runs the hook."""
        item_def = ITEM_DB[STACKABLE_KEY]

        item_def.create(location=self.char1, quantity=5)
        item_def.create(location=self.char1, quantity=7)

        stacks = [
            obj
            for obj in self.char1.contents
            if obj.is_typeclass(item_def.typeclass, exact=False)
        ]

        self.assertEqual(len(stacks), 1)
        self.assertEqual(stacks[0].quantity, 12)

    def test_non_stackables_do_not_merge(self):
        item_def = ITEM_DB[NON_STACKABLE_KEY]

        item_def.create(location=self.char1)
        item_def.create(location=self.char1)

        items = [
            obj
            for obj in self.char1.contents
            if obj.is_typeclass(item_def.typeclass, exact=False)
        ]

        self.assertEqual(len(items), 2)
