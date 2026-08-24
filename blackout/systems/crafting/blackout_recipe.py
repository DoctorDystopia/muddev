"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: BlackoutRecipe — the project's CraftingRecipe subclass, adding
             a skill gate and an XP award on top of the Evennia contrib.
"""



from evennia.contrib.game_systems.crafting.crafting import (
    CraftingRecipe,
    CraftingValidationError,
)
from evennia.utils.utils import inherits_from

from .constants import (
    CONSUMABLE_TAG_CATEGORY,
    CRAFTING_CATEGORIES,
    DEFAULT_CRAFT_SECONDS,
    TOOL_TAG_CATEGORY,
)



class BlackoutRecipe(CraftingRecipe):
    consumable_tag_category = CONSUMABLE_TAG_CATEGORY
    tool_tag_category = TOOL_TAG_CATEGORY

    exact_tools = False
    exact_consumables = False

    category = ""
    required_skill = ""
    required_level = 0
    xp_reward = 0
    skill_category = ""

    unlocked = True
    require_confirm = True

    # Seconds one craft of this recipe takes. Paces the "craft X"/"craft all"
    # batch loop in systems/crafting/craft_batch.py -- the first item in a
    # batch completes immediately, then this is how long each subsequent one
    # is spaced by. Irrelevant to a single "craft 1".
    craft_seconds = DEFAULT_CRAFT_SECONDS

    output_item_keys: list[str] = []


    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        # Fail at import time on an unknown category. Facilities match
        # allowed_categories against this string exactly, so a typo silently
        # hides every recipe in the category from the craft menu instead of
        # raising anything.
        if cls.category and cls.category not in CRAFTING_CATEGORIES:
            raise ValueError(
                f"{cls.__name__}: category {cls.category!r} is not one of "
                f"{CRAFTING_CATEGORIES}. Add it to systems/crafting/constants.py."
            )

        if cls.output_item_keys:
            from world.item_database import ITEM_DB
            missing = [k for k in cls.output_item_keys if k not in ITEM_DB]
            if missing:
                raise KeyError(
                    f"{cls.__name__}: output_item_keys not found in ITEM_DB: {missing}"
                )
            cls.output_prototypes = [
                ITEM_DB[key].to_prototype() for key in cls.output_item_keys
            ]

    error_skill_too_low = "You need {skill} level {level} to craft this."
    error_locked = "You have not yet learned this recipe."
    success_xp_message = "You gain {xp} {skill} XP."



    def unlock_requirement_check(self, crafter):
        return self.unlocked



    def _tag_map(self, tag_category):
        """Map each input object to the tags it carries under tag_category.

        Mirrors the contrib's input classification: only tagged Objects that
        subclass ObjectDB qualify, so characters and accounts can never be
        consumed as materials.
        """
        return {
            obj: obj.tags.get(category=tag_category, return_list=True)
            for obj in self.inputs
            if obj
            and hasattr(obj, "tags")
            and inherits_from(obj, "evennia.objects.models.ObjectDB")
        }



    def _validate_tools(self):
        """Match one object per required tool_tag entry, extras ignored.

        Raises CraftingValidationError (after messaging the crafter) if any
        required tool is unavailable. Populates self.validated_tools.
        """
        tool_map = {
            obj: tags
            for obj, tags in self._tag_map(self.tool_tag_category).items()
            if tags
        }

        validated = []
        for itag, tagkey in enumerate(self.tool_tags):
            found_obj = None
            for obj, objtags in tool_map.items():
                if tagkey in objtags:
                    found_obj = obj
                    break
            match = tool_map.pop(found_obj, None) if found_obj else None
            if match:
                validated.append(found_obj)
            else:
                err = self._format_message(
                    self.error_tool_missing_message,
                    missing=(
                        self.tool_names[itag]
                        if self.tool_names
                        else tagkey.capitalize()
                    ),
                )
                self.msg(err)
                raise CraftingValidationError(err)

        self.validated_tools = validated



    def _validate_consumables(self):
        """Match one unit per required consumable_tag entry, extras ignored.

        A stackable object (quantity > 1) can satisfy multiple entries, one
        unit each -- the contrib's object-per-entry matching cannot express
        that. Raises CraftingValidationError (after messaging the crafter) if
        any required unit is unavailable.

        Populates self.validated_consumables (one entry per required unit,
        stackables repeated) and self._consumption_plan (object -> units to
        consume from it).
        """
        consumable_map = {
            obj: tags
            for obj, tags in self._tag_map(self.consumable_tag_category).items()
            if tags
        }
        units_left = {obj: getattr(obj, "quantity", 1) for obj in consumable_map}

        validated = []
        plan = {}
        for itag, tagkey in enumerate(self.consumable_tags):
            found_obj = None
            for obj, objtags in consumable_map.items():
                if tagkey in objtags and units_left[obj] > 0:
                    found_obj = obj
                    break
            if found_obj is not None:
                units_left[found_obj] -= 1
                validated.append(found_obj)
                plan[found_obj] = plan.get(found_obj, 0) + 1
            else:
                err = self._format_message(
                    self.error_consumable_missing_message,
                    missing=(
                        self.consumable_names[itag]
                        if self.consumable_names
                        else tagkey.capitalize()
                    ),
                )
                self.msg(err)
                raise CraftingValidationError(err)

        self.validated_consumables = validated
        self._consumption_plan = plan



    def _consume_inputs(self):
        """Decrement or delete every object in the consumption plan."""
        for obj, units in self._consumption_plan.items():
            if getattr(obj, "is_stackable", False):
                obj.quantity -= units
                if obj.quantity <= 0:
                    obj.delete()
            else:
                obj.delete()



    def pre_craft(self, **kwargs):
        crafter = self.crafter
        self._consumption_plan = {}

        if not self.unlock_requirement_check(crafter):
            self.msg(self.error_locked)
            raise CraftingValidationError

        if self.required_skill:
            meets_req = crafter.skills.meets_prerequisite(
                self.required_skill, self.required_level
            )
            if not meets_req:
                self.msg(
                    self.error_skill_too_low.format(
                        skill=self.required_skill, level=self.required_level
                    )
                )
                raise CraftingValidationError

        self._validate_tools()
        self._validate_consumables()



    def post_craft(self, craft_result, **kwargs):
        if craft_result:
            self.msg(self._format_message(self.success_message))
        elif self.failure_message:
            self.msg(self._format_message(self.failure_message))

        if craft_result or self.consume_on_fail:
            self._consume_inputs()

        if craft_result and self.xp_reward > 0 and self.required_skill:
            self.crafter.skills.add_xp(self.required_skill, self.xp_reward)
            self.msg(
                self.success_xp_message.format(
                    xp=self.xp_reward, skill=self.required_skill
                )
            )

        return craft_result
