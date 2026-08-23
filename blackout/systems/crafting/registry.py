"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/01/2026
Description: Master catalog of all craftable recipe classes, discovered from the
             modules named in settings.CRAFT_RECIPE_MODULES.
"""



import importlib
import inspect

from django.conf import settings
from evennia.contrib.game_systems.crafting.crafting import (
    CraftingRecipe,
    CraftingRecipeBase,
)
from evennia.utils import logger



# Private constant definitions

# Recipe `name` values inherited from the contrib base classes. A subclass that
# still carries one of these never set its own name and is not a real recipe --
# BlackoutRecipe itself is the case that matters here.
_PLACEHOLDER_RECIPE_NAMES = frozenset(
    {CraftingRecipeBase.name, CraftingRecipe.name}
)



def _iter_recipe_modules():
    """
    Purpose: Yield the dotted path of every module declared as holding recipes.

    Entry:
        No conditions.

    Exit/Returns:
        Yields fully-qualified module path strings. Yields nothing if the
        setting is absent.

    Module Globals:
        None

    Methodology:
        Unlike the skill registry, which walks a package tree, recipe modules
        are named explicitly in settings.CRAFT_RECIPE_MODULES -- the same
        setting the crafting contrib reads. Keeping that as the single source
        means adopting a new recipe module needs one settings edit and no
        change here.

    Notes/References:
        See systems/progression/skills/registry.py for the package-walk
        variant of this pattern.

    Author: Nick Hobar
    Creation date: 08/01/2026
    """
    configured = getattr(settings, "CRAFT_RECIPE_MODULES", None)
    if not configured:
        logger.log_err(
            "[RECIPE REGISTRY] settings.CRAFT_RECIPE_MODULES is unset; no "
            "recipes will be available."
        )
        return

    if isinstance(configured, str):
        yield configured
        return

    yield from configured



def _is_registrable_recipe(obj, module_path: str) -> bool:
    """
    Purpose: Decide whether a class found in a recipe module is a real recipe.

    Entry:
        obj is a class object.
        module_path is the dotted path of the module it was found in.

    Exit/Returns:
        Returns True if obj should be added to the registry.

    Module Globals:
        _PLACEHOLDER_RECIPE_NAMES read.

    Methodology:
        Three filters, in order of cost. It must subclass the contrib base
        without being one of the bases; it must be DEFINED in this module
        rather than merely imported into it; and it must have set its own
        `name`. The middle filter matters because recipe modules do
        `from ..blackout_recipe import BlackoutRecipe`, and a plain
        inspect.getmembers scan counts that import as a recipe.

    Notes/References:
        The contrib's own _load_recipes reaches the same outcome by a
        different route: callables_from_module filters on
        getmodule(obj) == mod, which is the same defining-module test. This
        function is not fixing a contrib bug -- it exists so the registry
        does not depend on contrib-private symbols.

    Author: Nick Hobar
    Creation date: 08/01/2026
    """
    if not issubclass(obj, CraftingRecipeBase):
        return False

    if obj in (CraftingRecipeBase, CraftingRecipe):
        return False

    if obj.__module__ != module_path:
        return False

    recipe_name = getattr(obj, "name", None)
    if not recipe_name or recipe_name in _PLACEHOLDER_RECIPE_NAMES:
        return False

    return True



def _discover_recipes() -> dict:
    """
    Purpose: Build the master recipe registry by importing every recipe module.

    Entry:
        No conditions.

    Exit/Returns:
        Returns dict mapping recipe name -> recipe class. Duplicate names are
        logged and the first definition wins.

    Module Globals:
        None

    Methodology:
        Import each configured module, then collect every class that passes
        _is_registrable_recipe. A failed import is logged and skipped so one
        broken recipe file cannot take the whole crafting system down.

    Notes/References:
        Replaces crafting_service's direct use of the contrib's private
        _load_recipes and _RECIPE_CLASSES. Two behavioural gains beyond
        dropping the private dependency: the contrib's _RECIPE_CLASSES is a
        process-lifetime cache that is never invalidated, and holding the
        class here lets perform_craft skip craft()'s fuzzy name matching.

    Author: Nick Hobar
    Creation date: 08/01/2026
    """
    registry = {}

    for module_path in _iter_recipe_modules():
        try:
            module = importlib.import_module(module_path)
        except Exception as exc:
            logger.log_trace(
                f"[RECIPE REGISTRY] Failed to import {module_path}: {exc}"
            )
            continue

        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if not _is_registrable_recipe(obj, module_path):
                continue

            recipe_name = obj.name
            if recipe_name in registry:
                logger.log_err(
                    f"[RECIPE REGISTRY] Duplicate recipe name '{recipe_name}' in "
                    f"{module_path}; keeping {registry[recipe_name].__name__}."
                )
                continue

            registry[recipe_name] = obj

    return registry



RECIPE_REGISTRY: dict = _discover_recipes()
