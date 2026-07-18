from evennia.contrib.game_systems.crafting.crafting import (
    CraftingRecipe,
    CraftingValidationError,
)

_CONSUMABLE_TAG_CATEGORY = "crafting_material"
_TOOL_TAG_CATEGORY = "crafting_tool"


class BlackoutRecipe(CraftingRecipe):
    consumable_tag_category = _CONSUMABLE_TAG_CATEGORY
    tool_tag_category = _TOOL_TAG_CATEGORY

    exact_tools = False
    exact_consumables = False

    category = ""
    required_skill = ""
    required_level = 0
    xp_reward = 0
    skill_category = ""

    unlocked = True
    require_confirm = True

    output_item_keys: list[str] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
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

    def pre_craft(self, **kwargs):
        super().pre_craft(**kwargs)

        crafter = self.crafter

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

    def post_craft(self, craft_result, **kwargs):
        result = super().post_craft(craft_result, **kwargs)

        if result and self.xp_reward > 0 and self.required_skill:
            self.crafter.skills.add_xp(self.required_skill, self.xp_reward)
            self.msg(
                self.success_xp_message.format(
                    xp=self.xp_reward, skill=self.required_skill
                )
            )

        return result
