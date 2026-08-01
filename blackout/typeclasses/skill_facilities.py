from evennia import create_object
from systems.crafting.constants import CATEGORY_FOUNDRY, CATEGORY_METALSMITHING
from typeclasses.crafting_facilities import CraftingFacility
from .spawners import register_spawner


# ------------------------------------
# --- PROCESSING SKILLS FACILITIES ---
# ------------------------------------
class FoundryBaseFacility(CraftingFacility):
    """
    The base crafting facility for Foundry-skill processing.
    Specific facility types (FurnaceFacility, etc.) inherit from this
    and add their own tool tags for recipe tool requirements.
    """
    allowed_categories = [CATEGORY_FOUNDRY]

    def at_object_creation(self):
        parent_class = super()
        parent_class.at_object_creation()
        self.locks.add("get:false()")
        self.db.desc = "A Foundry facility for processing raw materials into crafting components."


class FurnaceFacility(FoundryBaseFacility):
    """
    A furnace where players smelt raw materials via the Foundry skill.
    Only Foundry-category recipes are shown in the craft menu.
    Tagged as a 'furnace' tool so it satisfies recipe tool requirements.
    """
    def at_object_creation(self):
        parent_class = super()
        parent_class.at_object_creation()
        self.tags.add("furnace", category="crafting_tool")
        self.db.desc = "A roaring foundry furnace, hot enough to smelt scrap metal into something usable."


# ------------------------------------
# --- PRODUCTION SKILLS FACILITIES ---
# ------------------------------------
class MetalsmithBaseFacility(CraftingFacility):
    """
    The base crafting facility for Metalsmith-skill producing.
    Specific facility types (AnvilFacility, etc.) inherit from this
    and add their own tool tags for recipe tool requirements.
    """
    allowed_categories = [CATEGORY_METALSMITHING]

    def at_object_creation(self):
        parent_class = super()
        parent_class.at_object_creation()
        self.locks.add("get:false()")
        self.db.desc = "A Metalsmith facility for processing crafting components into finished goods."


class AnvilFacility(MetalsmithBaseFacility):
    """
    An anvil where players forge items via the Metalsmith skill.
    Only Metalsmithing-category recipes are shown in the craft menu.
    Also tagged as a crafting_tool so it satisfies recipe tool requirements.
    """
    def at_object_creation(self):
        parent_class = super()
        parent_class.at_object_creation()
        self.tags.add("anvil", category="crafting_tool")
        self.db.desc = "A solid steel anvil, scarred from years of use. Perfect for shaping metal."


# -------------------------
# --- SPAWNER FUNCTIONS ---
# -------------------------
@register_spawner("Foundry Furnace Facility")
def spawn_foundry_facility(room):
    if not any(
        obj.is_typeclass("typeclasses.skill_facilities.FurnaceFacility", exact=True)
        for obj in room.contents
    ):
        create_object(
            "typeclasses.skill_facilities.FurnaceFacility",
            key="Foundry Furnace",
            location=room,
        )


@register_spawner("Metalsmith Anvil Facility")
def spawn_anvil_facility(room):
    if not any(
        obj.is_typeclass("typeclasses.skill_facilities.AnvilFacility", exact=True)
        for obj in room.contents
    ):
        create_object(
            "typeclasses.skill_facilities.AnvilFacility",
            key="Metalsmith Anvil",
            location=room,
        )
