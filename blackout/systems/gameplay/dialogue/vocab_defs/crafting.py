"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/11/2026
Description: The `recipe.*` names of the dialogue vocabulary (DESIGN-0017).

             A dialogue that names a recipe types its key as a literal. The
             argument check refuses a key that the recipe registry does not
             hold. Thus, a renamed recipe fails the content check, and the
             dialogue does not keep the old name in silence.
"""

from systems.gameplay.crafting.registry import RECIPE_REGISTRY
from systems.gameplay.dialogue.vocabulary import query


# ─── Private helper routines ─────────────────────────────────────────────────

def _check_recipe_key(arguments: list) -> str | None:
    """The problem with the recipe key of a call, or None."""
    recipe_key = arguments[0]

    if recipe_key is None or recipe_key in RECIPE_REGISTRY:
        return None

    return f"no recipe has the name '{recipe_key}'"


# ─── The queries ─────────────────────────────────────────────────────────────

@query("recipe.name", "The name of a recipe, as the craft menu shows it.",
       argument_check=_check_recipe_key)
def _name(context: object, recipe_key: str) -> str:
    recipe = RECIPE_REGISTRY.get(recipe_key)

    if recipe is None:
        return recipe_key

    return str(recipe.name)
