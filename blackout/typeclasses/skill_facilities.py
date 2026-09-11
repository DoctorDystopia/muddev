"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: Per-skill crafting facility typeclasses (furnace, anvil) and
             their room spawners.
"""

from evennia import Command, CmdSet

from commands.constants import HELP_CATEGORY_CRAFTING
from systems.gameplay.crafting.constants import (
    CATEGORY_CURING,
    CATEGORY_FOUNDRY,
    CATEGORY_METALSMITH,
    CATEGORY_RENDERING,
)
from systems.gameplay.curing import constants as curing_constants
from systems.interface.statefeed import constants as feed_const
from typeclasses.crafting_facilities import CraftingFacility
from .spawners import register_spawner, spawn_once


# Every line `collect` sends a player is crafting, so the routing tag is bound
# once here. Same value CraftingFacility and BlackoutRecipe use -- a cure's
# lines must land in the same tab as every other crafting line.
_MSG_CRAFTING = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_CRAFTING}


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
    asset_key = "furnace"

    def at_object_creation(self):
        parent_class = super()
        parent_class.at_object_creation()
        self.tags.add("furnace", category="crafting_tool")
        self.db.desc = "A roaring foundry furnace, hot enough to smelt scrap metal into something usable."


class RenderingBaseFacility(CraftingFacility):
    """
    The base crafting facility for Rendering-skill processing.
    Specific facility types (RenderingCookerFacility, etc.) inherit from this
    and add their own tool tags for recipe tool requirements.
    """
    allowed_categories = [CATEGORY_RENDERING]

    def at_object_creation(self):
        parent_class = super()
        parent_class.at_object_creation()
        self.locks.add("get:false()")
        self.db.desc = "A Rendering facility for cooking carcass cuts down into fat and lean meat."


class RenderingCookerFacility(RenderingBaseFacility):
    """
    A cooker where players render cuts of meat via the Rendering skill.
    Only Rendering-category recipes are shown in the craft menu.
    Tagged as a 'rendering_cooker' tool so it satisfies recipe tool
    requirements.

    The asset_key is its own rather than borrowed from the furnace. Neither
    has art today, so both draw the same procedural station mesh and the
    client needs no edit either way -- but a borrowed key would mean the day a
    cooker model is packed, the furnace silently becomes a cooker too.
    """
    asset_key = "rendering_cooker"

    def at_object_creation(self):
        parent_class = super()
        parent_class.at_object_creation()
        self.tags.add("rendering_cooker", category="crafting_tool")
        self.db.desc = "A squat rendering cooker, its vat crusted with old fat and smelling of every animal that went into it."


class CmdCollect(Command):
    """
    Purpose: Take every finished cure out of the chamber.

    Entry:
        self.caller is a Character with a curing handler. self.obj is the
        chamber the command hangs on.

    Exit/Returns:
        No conditions.

    Module Globals:
        curing_constants read.

    Methodology:
        Reports and delegates, nothing more. The handler owns which slots are
        ready, what they make and when a slot frees -- this command's whole job
        is being the reason the player has to come back to a chamber, which is
        what makes the facility more than a place cures are started.

        It messages the two empty cases itself rather than letting the handler
        return an empty list silently, because "nothing curing" and "nothing
        ready yet" are different things to be told and only one of them means
        come back later.

    Notes/References:
        The per-item lines are the handler's (MSG_CURE_READY), so a collection
        of three says three things and this says none of them.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    key = "collect"
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_CRAFTING


    def func(self) -> None:
        caller = self.caller
        handler = caller.curing

        pending = handler.pending()
        if not pending:
            caller.msg((curing_constants.MSG_NOTHING_CURING, _MSG_CRAFTING))
            return

        collected = handler.collect()
        if not collected:
            self._report_waiting()
            return


    def _report_waiting(self) -> None:
        """Tell the player what is in the chamber and how long it needs.

        The refusal, then the handler's own slot block -- the same block the
        craft menu and the dossier's Processing band print. Assembling the
        per-slot lines here as well would make this the third owner of how a
        slot reads, and the first copy edit to any of them would be the one
        that made them disagree.
        """
        caller = self.caller
        lines = [curing_constants.MSG_NOTHING_READY]
        lines.extend(caller.curing.status_lines())

        report = "\n".join(lines)
        caller.msg((report, _MSG_CRAFTING))



class CollectCmdSet(CmdSet):
    """Stores the collect command for curing chambers."""

    key = "curing_chamber_cmdset"
    priority = 10


    def at_cmdset_creation(self) -> None:
        collect_command = CmdCollect()
        self.add(collect_command)



class CuringBaseFacility(CraftingFacility):
    """
    The base crafting facility for Curing-skill processing.
    Specific facility types (CuringChamberFacility, etc.) inherit from this
    and add their own tool tags for recipe tool requirements.
    """
    allowed_categories = [CATEGORY_CURING]

    def at_object_creation(self):
        parent_class = super()
        parent_class.at_object_creation()
        self.locks.add("get:false()")
        self.db.desc = "A Curing facility for preserving cuts of meat."


class CuringChamberFacility(CuringBaseFacility):
    """
    A chamber where players cure meat via the Curing skill.
    Only Curing-category recipes are shown in the craft menu.
    Tagged as a 'curing_chamber' tool so it satisfies recipe tool
    requirements.

    The one facility in the game carrying a SECOND cmdset beside `craft`.
    Curing is the only stage whose output arrives later, so it is the only one
    with anything to come back for -- `collect` is that, and it hangs here
    rather than on the character because standing at a chamber is the point.
    """
    asset_key = "curing_chamber"


    def extra_actions(self) -> list:
        """
        Purpose: Both things a player may do at a chamber, for a right click.

        Entry:
            No conditions.

        Exit/Returns:
            Returns a list of {"command", "label"} dicts: `craft` first,
            `collect` second.

        Module variables:
            None.

        Methodology:
            The one facility in the game that affords TWO verbs, which is
            exactly the case serialize_entity grew an action list for. A
            chamber offering only `craft` -- which is what interact_verb alone
            can say -- left the Godot client with no way to reach `collect` at
            all, and the whole point of the stage is coming back for it.

            `craft` leads because starting a cure is what brings a player to a
            chamber the first time; the list's head is also what `interact`
            carries, so a left click still opens the menu it always did. The
            menu's own Collect row is what makes the second verb reachable
            from inside, so neither client has to be the one that knows.

            Neither command is filtered on whether anything is ready. The feed
            has no observer to filter against -- serialize_entity draws one
            chamber for every player who can see it -- and `collect` refuses
            with a countdown, which tells the player something a missing row
            does not. That is the same call corpses.extra_actions makes about
            gathering levels.

            The verbs take no target because both cmdsets hang on this object,
            which is what interact_command documents about a facility's own
            commands.

            Neither row names a label. _action_label capitalises the command's
            own verb when none is given, and a label typed here would be a
            second spelling of a word this class already has -- `craft` is
            CraftingFacility's interact_verb and `collect` is CmdCollect.key,
            both read rather than retyped for the same reason.

        Notes/References:
            systems/interface/statefeed/serializers.py interact_actions
            consumes this.

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        return [
            {"command": self.interact_verb},
            {"command": CmdCollect.key},
        ]


    def at_object_creation(self):
        parent_class = super()
        parent_class.at_object_creation()
        self.tags.add("curing_chamber", category="crafting_tool")
        # add(), NOT add_default(). An object has exactly ONE default cmdset,
        # and CraftingFacility.at_object_creation has already spent it on
        # CraftCmdSet -- calling add_default again would REPLACE `craft` with
        # `collect` rather than joining them, leaving a chamber nothing could
        # be started at.
        self.cmdset.add(CollectCmdSet, persistent=True)
        self.db.desc = "A sealed curing chamber, cold and dry inside, hung with hooks and smelling of salt."


# ------------------------------------
# --- PRODUCTION SKILLS FACILITIES ---
# ------------------------------------
class MetalsmithBaseFacility(CraftingFacility):
    """
    The base crafting facility for Metalsmith-skill producing.
    Specific facility types (AnvilFacility, etc.) inherit from this
    and add their own tool tags for recipe tool requirements.
    """
    allowed_categories = [CATEGORY_METALSMITH]

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
    asset_key = "anvil"

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
    spawn_once(
        room,
        "typeclasses.skill_facilities.FurnaceFacility",
        key="Foundry Furnace",
    )


@register_spawner("Metalsmith Anvil Facility")
def spawn_anvil_facility(room):
    spawn_once(
        room,
        "typeclasses.skill_facilities.AnvilFacility",
        key="Metalsmith Anvil",
    )


@register_spawner("Rendering Cooker Facility")
def spawn_rendering_cooker_facility(room):
    spawn_once(
        room,
        "typeclasses.skill_facilities.RenderingCookerFacility",
        key="Rendering Cooker",
    )


@register_spawner("Curing Chamber Facility")
def spawn_curing_chamber_facility(room):
    spawn_once(
        room,
        "typeclasses.skill_facilities.CuringChamberFacility",
        key="Curing Chamber",
    )
