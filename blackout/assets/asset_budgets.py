"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: How large a model of each family is allowed to be. The one owner
             of that fact, for the packer that enforces it and the test that
             checks the served tree still obeys it.

             THE PROBLEM THIS FIXES. `pack_model.py` took the texture ceiling
             as an optional third CLI argument defaulting to a single module
             constant, so the resolution of any given model was decided by
             whoever typed the command. The served tree records the result:
             characters at 1024, npcs and items at 512, world objects at 256 --
             four tiers, none of them written down anywhere, and
             `player_character.glb` carrying FIFTEEN 1024-square textures for
             10.4 MiB. That is more than the whole rest of the art put
             together, for the one model a player sees from furthest away.

             A ceiling that lives in an argument is a ceiling nobody can check.
             This module makes it a table, `pack_model.py` reads the table
             instead of an argument, and a test asserts the served files still
             fit -- so a temp asset dropped in raw during development fails
             loudly instead of quietly costing every player a megabyte.

             WHY BYTES AND NOT JUST PIXELS. Texture edge is the knob that
             usually matters, but it is not the only way a model gets big:
             `floating_eye.glb` is 1.03 MiB at a perfectly correct 512, because
             it carries 10,027 vertices. A pixel ceiling alone would call that
             compliant. Each family therefore carries a byte budget too, and
             the two catch different mistakes.

             WHY A DEFAULT FOR UNKNOWN FAMILIES. Adding `assets/vehicles/`
             should work without editing this file, the same way an unknown
             asset key already draws a generic mesh rather than failing --
             content must never wait on a registry edit. An unlisted family
             gets DEFAULT_BUDGET, which is the tightest tier: a new family is
             small until someone argues otherwise, rather than unbounded until
             someone notices.

             PURE. Importing this touches no file and no database. That is what
             lets the test import it; see CLAUDE.md on `blackout/scripts/`
             being import-unsafe -- `assets/` deliberately is not.
"""

from dataclasses import dataclass


# ─── Public constant definitions ─────────────────────────────────────────────

_BYTES_PER_KIB: int = 1024
_BYTES_PER_MIB: int = 1024 * 1024


@dataclass(frozen=True)
class ModelBudget:
    """
    What one family of model may spend.

    max_texture_edge is the longest edge in pixels any texture keeps; the
    packer resamples anything larger. max_bytes is the ceiling on the finished
    .glb, which catches the mesh-heavy models a pixel ceiling cannot see.
    `reason` is the render size the numbers were chosen for, so the next person
    to change one has to disagree with something specific.
    """

    max_texture_edge: int
    max_bytes: int
    reason: str


# The tightest tier, applied to any family not listed below. See the module
# docstring: an unlisted family must work, and must start small.
DEFAULT_BUDGET: ModelBudget = ModelBudget(
    max_texture_edge=256,
    max_bytes=768 * _BYTES_PER_KIB,
    reason="unlisted family; starts at the tightest tier until argued up",
)


# family -> budget. The family is the first path component under assets/, which
# `pack_model._served_family` already treats as the one owner of the division.
#
# THE TIERS ARE CHOSEN FROM HOW LARGE THE THING ACTUALLY DRAWS, not from what
# the download happened to ship. Every number below is at or under what the
# served tree already used, with ONE deliberate reduction: characters drop from
# the ad-hoc 1024 to 512.
FAMILY_BUDGETS: dict = {
    # The player, and the largest thing on screen -- but it is a diorama figure
    # a few dozen pixels tall on a tile, not a hero shot. 512 is the same
    # ceiling npcs get, and there is no reason the player should cost four
    # times an npc to look at.
    #
    # THE BYTE BUDGET HERE IS A REGRESSION GUARD, NOT A TARGET, and the
    # difference is worth stating so nobody reads 3 MiB as approval. The
    # Spider-Man placeholder this number was first written for packed to
    # 6.3 MiB and was replaced on 08/27/2026 by a Quaternius base character at
    # 2.0 MiB, of which 1.2 MiB is texture. The rest is vertex data for 8,483
    # vertices, and it is carrying attributes the game does not use:
    #
    #     skins: 1, animations: 0
    #     COLOR_0, COLOR_1, TEXCOORD_0..TEXCOORD_3
    #
    # So JOINTS_0 and WEIGHTS_0 -- the skinning attributes -- ship for
    # animations that do not exist, alongside two vertex-colour sets and three
    # spare UV sets nothing samples. Dropping unused attributes is the next
    # lever; it is real glTF surgery (accessors and bufferViews have to be
    # renumbered) rather than a resample, so it is tracked as its own piece of
    # work.
    #
    # Set just above today's packed size so a REGRESSION fails loudly while
    # that work is outstanding. Lower it when the attributes go.
    "characters": ModelBudget(
        max_texture_edge=512,
        max_bytes=3 * _BYTES_PER_MIB,
        reason="diorama figure on a tile; regression guard pending attribute pruning",
    ),

    # Several can share a room, so this multiplies. Mesh budget is the loose
    # one here because floating_eye is legitimately 10k vertices.
    "npcs": ModelBudget(
        max_texture_edge=512,
        max_bytes=2 * _BYTES_PER_MIB,
        reason="several per room; 512 as shipped",
    ),

    # An inventory cell is about 70px and a world-pane item is smaller. 512 is
    # already generous -- kept, because it is headroom for a model inspected
    # close up rather than a size anything resolves today.
    "items": ModelBudget(
        max_texture_edge=512,
        max_bytes=_BYTES_PER_MIB,
        reason="inventory cell is ~70px; 512 is deliberate headroom",
    ),

    # Props standing on a tile. Never inspected close up.
    "world_objects": ModelBudget(
        max_texture_edge=256,
        max_bytes=768 * _BYTES_PER_KIB,
        reason="tile prop; never inspected close up",
    ),

    # Same role as world_objects: something you walk up to and harvest.
    "gathering_nodes": ModelBudget(
        max_texture_edge=256,
        max_bytes=768 * _BYTES_PER_KIB,
        reason="tile prop; same role as world_objects",
    ),
}


# ─── Public routines ─────────────────────────────────────────────────────────

def budget_for(family: str) -> ModelBudget:
    """
    Purpose: Report the budget one model family must fit inside.

    Entry:
        family - the served subdirectory name, as `_served_family` reports it
        (e.g. "items"). An unknown or empty name is not an error.

    Exit/Returns:
        The family's ModelBudget, or DEFAULT_BUDGET when the family is not
        listed.

    Module Globals:
        FAMILY_BUDGETS, DEFAULT_BUDGET read.

    Methodology:
        A lookup with a fallback rather than a raise, because a new family
        directory must be packable the day it is created. The fallback is the
        tightest tier, so the cost of not being listed is a smaller model
        rather than an unbounded one.

    Notes/References:
        Asserted against the served tree by
        systems/statefeed/tests/test_model_budgets.py.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    return FAMILY_BUDGETS.get(family, DEFAULT_BUDGET)


def describe_budget(family: str) -> str:
    """
    Purpose: Render one family's budget as a line fit for CLI output.

    Entry:
        family - the served subdirectory name.

    Exit/Returns:
        A single-line human-readable summary.

    Module Globals:
        None written.

    Methodology:
        Kept here rather than in the packer so the units are spelled once.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    budget = budget_for(family)
    listed = family in FAMILY_BUDGETS
    label = family if listed else "%s (unlisted -> default)" % family

    return "%s: textures <= %dpx, file <= %d KiB -- %s" % (
        label,
        budget.max_texture_edge,
        budget.max_bytes // _BYTES_PER_KIB,
        budget.reason,
    )
