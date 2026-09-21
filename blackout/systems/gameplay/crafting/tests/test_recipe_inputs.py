"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/21/2026
Description: One test, over every recipe in the game: each input a recipe
             consumes must be something the world can actually produce.

             THIS IS THE TEST THE HIDE CAPES NEEDED. `scrap hide cape` and
             `copper hide cape` both consumed `mutant_raider_prime_cured_hide`,
             which had an ItemDef and no recipe. Both capes were uncraftable
             from the day they were written until 09/21/2026, and every
             existing test passed the whole time -- a recipe that names a tag
             nothing outputs is a perfectly valid recipe class, and the craft
             menu lists it, and the player simply never gathers the material.

             The failure mode is silent by construction, so nothing but a
             whole-catalogue sweep can catch it. Each test below walks EVERY
             recipe rather than a named list, so a new recipe that names a dead
             tag fails on the next run with no edit here.

             It asserts a RELATIONSHIP, never a census and never a balance
             value: "everything a recipe asks for, something gives". A new
             recipe, item, node or drop table changes the two sets and not the
             assertion.

Run with:
    evennia test --settings test_settings.py systems.gameplay.crafting
"""



import unittest

from systems.gameplay.crafting.registry import RECIPE_REGISTRY
from systems.gameplay.progression.skills.gatherables import GATHERABLE_REGISTRY
from world.item_database import ITEM_DB
from world.loot_database import LOOT_DB



# Private routine definitions

def _tags_of(item_key: str) -> set:
    """
    Purpose: Every tag KEY the named item carries.

    Entry:
        item_key is an ITEM_DB key, or a key that is not in ITEM_DB.

    Exit/Returns:
        Returns a set of tag key strings. Empty for an unknown item.

    Module Globals:
        ITEM_DB read.

    Methodology:
        Reads the tag KEY and drops the category, because a recipe names an
        input by key alone. An item declares as many families as it belongs
        to, so one item can satisfy several different consumable_tags -- the
        rusty scrap axe is both `crafting_tool` and `weapon`.

        An unknown key returns empty rather than raising. ITEM_DB completeness
        is a different fact with its own test, and a KeyError here would hide
        the orphan this module exists to find.

    Notes/References:
        CLAUDE.md, "An item may belong to several families".

    Author: Nick Hobar
    Creation date: 09/21/2026
    """
    item_def = ITEM_DB.get(item_key)

    if item_def is None:
        return set()

    return {tag_key for tag_key, _category in (item_def.tags or [])}



def _producible_tags() -> set:
    """
    Purpose: Every tag the world can put into a player's hands.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a set of tag key strings.

    Module Globals:
        RECIPE_REGISTRY, GATHERABLE_REGISTRY, LOOT_DB and ITEM_DB read.

    Methodology:
        Three sources, because there are three ways an item reaches a player:
        a recipe makes it, a gathering node yields it, or a corpse drops it.
        A shop is deliberately NOT a fourth source. A shop sells what the
        world already produces, so counting its stock would let a chain look
        whole while its only route was a merchant's inventory.

        Every source is walked whole. Nothing here names a recipe, a node or a
        table, so new content joins the set without an edit.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/21/2026
    """
    produced = set()

    for recipe in RECIPE_REGISTRY.values():
        for item_key in getattr(recipe, "output_item_keys", None) or []:
            produced |= _tags_of(item_key)

    for gatherable_def in GATHERABLE_REGISTRY.values():
        for entry in gatherable_def.yields:
            produced |= _tags_of(entry.item_key)

    for table in LOOT_DB.values():
        entries = list(table.always or []) + list(table.main or [])

        for entry in entries:
            produced |= _tags_of(entry.item_key)

        for tertiary in table.tertiary or []:
            produced |= _tags_of(tertiary.entry.item_key)

    return produced



class TestEveryRecipeInputHasAProducer(unittest.TestCase):
    """The sweep that would have caught the uncraftable hide capes."""

    def test_every_consumable_tag_is_produced_somewhere(self):
        """A recipe that asks for a tag nothing outputs cannot be crafted."""
        produced = _producible_tags()

        for name, recipe in sorted(RECIPE_REGISTRY.items()):
            for tag in getattr(recipe, "consumable_tags", None) or []:
                with self.subTest(recipe=name, tag=tag):
                    self.assertIn(
                        tag,
                        produced,
                        f"recipe {name!r} consumes {tag!r}, which no recipe, "
                        f"gathering node or drop table produces",
                    )


    # NO TOOL-TAG SWEEP HERE, and it is not an oversight. The same check for
    # `tool_tags` cannot be written statically: a facility stamps its tag
    # inside at_object_creation with `self.tags.add("anvil", ...)`, so nothing
    # on the CLASS names it. Reading it would mean building one of each
    # facility, which turns a plain unittest.TestCase into an EvenniaTestCase
    # and buys a check that belongs beside the facilities instead.
    # A declarative `facility_tag` class attribute would make it free.

    def test_every_output_key_is_a_real_item(self):
        """An output naming a key outside ITEM_DB fails only at the craft."""
        for name, recipe in sorted(RECIPE_REGISTRY.items()):
            for item_key in getattr(recipe, "output_item_keys", None) or []:
                with self.subTest(recipe=name, item_key=item_key):
                    self.assertIn(item_key, ITEM_DB)
