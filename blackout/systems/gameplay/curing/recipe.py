"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: CuringRecipe — a BlackoutRecipe whose output arrives later.

             Why this is still a recipe
             --------------------------
             A cure is two events separated by time, which is not what
             CraftingRecipe models, and the honest alternative was a CuringDef
             dataclass of its own beside GatherableDef. It stayed a recipe for
             one reason that outweighed the awkwardness: BlackoutRecipe is
             already the one owner of a recipe's input, output, level and XP,
             and four readers find recipes through that -- the craft menu,
             crafting_service.get_recipes_for_skill, the skills panel's unlock
             listing, and the craftable check. A parallel table would have had
             to be wired into all four, and the first level that disagreed
             between the two tables would be invisible.

             What this class adds is ONE fact: how long the cure takes. The
             timing itself belongs to CuringHandler, not here, because a
             recipe instance does not outlive the call that made it and a cure
             has to outlive a server restart.
"""



from systems.gameplay.crafting.blackout_recipe import BlackoutRecipe
from systems.gameplay.crafting.constants import CATEGORY_CURING
from systems.gameplay.progression.skills import constants as skill_constants



class CuringRecipe(BlackoutRecipe):
    """
    Purpose: Base class for every recipe worked at a curing chamber.

    Entry:
        Subclasses set name, required_level, xp_reward, cure_seconds, the
        consumable pair and the output.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        Declares no `name`, so the recipe registry's placeholder filter keeps
        it out of the craft menu -- the same way _RenderingRecipe and
        BlackoutRecipe itself are excluded.

        It deliberately does NOT override pre_craft or post_craft. A cure is
        not a craft that takes longer; it is two halves, and CuringHandler
        drives each one explicitly. Overriding the hooks would have hidden
        that split inside a method whose name promises it happens at once, and
        a reader of the craft menu would have no way to tell a curing recipe
        from a rendering one.

    Notes/References:
        systems/gameplay/curing/handler.py owns both halves.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    category = CATEGORY_CURING
    required_skill = skill_constants.CURING_SKILL_KEY
    skill_category = "processing"

    # The attribute that makes a cure a cure. crafting_service reads it and
    # routes execution to character.curing instead of producing the output now
    # -- see BlackoutRecipe.deferred_handler for the protocol. Without this
    # line every recipe below is an ordinary instant craft in a category called
    # Curing, which is a whole mechanic disabled by one missing declaration.
    deferred_handler = "curing"

    tool_tags = ["curing_chamber"]
    tool_names = ["curing chamber"]

    # How long one cure of this recipe takes, in seconds.
    #
    # Per recipe rather than one constant, because the tier IS the wait: a
    # filet is the better cut and the longer commitment. Distinct from
    # BlackoutRecipe.craft_seconds, which paces a "craft all" BATCH and is
    # about the client not being flooded -- this is a game rule.
    #
    # Zero would make a curing recipe an instant one, which is a whole
    # mechanic disabled by a missing declaration, so it has no default worth
    # inheriting and __init_subclass__ below refuses one.
    cure_seconds: float = 0.0


    def __init_subclass__(cls, **kwargs):
        """
        Purpose: Refuse a concrete curing recipe that declares no duration.

        Entry:
            Called by Python for every subclass, abstract ones included.

        Exit/Returns:
            No conditions. Raises ValueError on a named subclass whose
            cure_seconds is not positive.

        Module Globals:
            None.

        Methodology:
            Gated on the subclass having its own `name`, so a further abstract
            base between this class and a recipe is still allowed to omit the
            duration. The check mirrors BlackoutRecipe's own category and
            output_item_keys validation: at IMPORT, where a missing
            declaration is a failed server start rather than a cure that
            finishes the instant it begins.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        super().__init_subclass__(**kwargs)

        is_abstract = "name" not in cls.__dict__
        if is_abstract:
            return

        if cls.cure_seconds <= 0:
            raise ValueError(
                f"{cls.__name__}: cure_seconds must be positive. A curing "
                f"recipe with no duration is an instant recipe in the wrong "
                f"category."
            )
