"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: Talkative and shopkeeper NPC typeclasses, plus the talk command.
"""

from evennia import Command, CmdSet
from evennia import DefaultObject
from evennia.utils import logger

from commands.constants import HELP_CATEGORY_GENERAL
from systems.statefeed.constants import ASSET_KIND_NPC, COMMERCE_ROLE_SHOP
from typeclasses.objects import ObjectParent
from .scripts import Script
from .spawners import register_spawner, spawn_once
from systems.menus.base_menu import start_blackout_menu
from systems.statefeed import constants as feed_const

# Every line this module sends a player is about the room around you, so the
# routing tag is bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/statefeed/constants.py.
_MSG_ROOM = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_ROOM}


# Public constant definitions
TALK_COMMAND_KEY = "talk"
TALK_COMMAND_LOCKS = "cmd:all()"
TALK_CMD_SET_KEY = "npc_talk_cmdset"
TALK_CMD_SET_PRIORITY = 10

# The shopkeeper's own verb, on the shopkeeper's own cmdset, for the reason
# CmdBank sits on the bank terminal: the object the cmdset hangs on IS the
# counterparty, so there is no shop to name and none to disambiguate.
SELL_COMMAND_KEY = "sell"
SELL_COMMAND_LOCKS = "cmd:all()"
SHOPKEEP_CMD_SET_KEY = "npc_shopkeep_cmdset"
SHOPKEEP_CMD_SET_PRIORITY = 10

SHOPKEEP_DIALOGUE_MODULE = "systems.menus.npc_dialogues.npc_shopkeep"
LONE_ANDROID_DIALOGUE_MODULE = "systems.menus.npc_dialogues.npc_oasis_lone_android"

# The oasis quest giver. The key must match the room key of the "Lone Android"
# prototype in world/maps/oasis.py, because that key is what SPAWNER_REGISTRY
# dispatches on.
LONE_ANDROID_KEY = "Lone Android"
LONE_ANDROID_DESC = (
    "A farm-hand android, alone. Its chassis is sand-scoured down to the "
    "primer and one knee joint whines when it moves. It is bent over a "
    "datapad, writing, and does not appear to have noticed you."
)
# The periodic trim that keeps player sales from filling a shopkeep's pockets
# forever, and how much it leaves behind.
#
# The class lives in THIS module rather than in blackout/scripts/, where it sat
# until 08/28/2026. That directory acts on the live database and CLAUDE.md
# calls it import-unsafe -- yet this path was persisted in 34 ScriptDB rows, so
# every server start imported out of it. It has one user, twenty lines below
# it, and belongs beside that user.
SHOPKEEP_CLEANUP_SCRIPT = "typeclasses.npcs.ShopkeepCleanup"
SHOPKEEP_CLEANUP_KEY = "shopkeep_cleanup"
SHOPKEEP_CLEANUP_DESC = "Periodically removes excess items from this shopkeep"
SHOPKEEP_CLEANUP_INTERVAL = 86400
SHOPKEEP_MAX_HELD_ITEMS = 20

# Paths this script has been persisted under before. A shopkeep carrying one is
# re-pointed the next time its tile is spawned; see ensure_cleanup_script.
LEGACY_SHOPKEEP_CLEANUP_SCRIPTS = (
    "scripts.shopkeep_inventory_cleanup.ShopkeepCleanup",
)



class CmdTalk(Command):
    """
    Purpose: Initiates a menu-driven conversation with an NPC.

    Entry:
        self.caller is a valid Evennia Character object
        self.obj is the NPC with a db.menu_module path

    Exit/Returns:
        No conditions. Launches an EvMenu on the caller.

    Module Globals:
        TALK_COMMAND_KEY read
        TALK_COMMAND_LOCKS read

    Methodology:
        Sends a brief introduction message to the caller, then opens the
        NPC's stored dialogue module through start_blackout_menu. Every NPC
        goes through the same launcher -- the shopkeep used to be branched
        out to a styled menu while everyone else got a bare EvMenu, which is
        why only the shopkeep had the shared look.

        Passes the NPC itself as a keyword argument. EvMenu assigns leftover
        keywords onto the menu INSTANCE, so nodes read it back with
        dialogue.menu_npc rather than out of their own kwargs.

    Notes/References:
        Pattern from evennia.contrib.tutorials.talking_npc.

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    key = TALK_COMMAND_KEY
    locks = TALK_COMMAND_LOCKS
    help_category = HELP_CATEGORY_GENERAL


    def func(self) -> None:
        """
        Purpose: Executes the talk command, launching the dialogue menu.

        Entry:
            self.caller is a valid Character
            self.obj is the NPC object

        Exit/Returns:
            No conditions (menu lifecycle managed by EvMenu)

        Module Globals:
            None

        Methodology:
            Retrieves the menu module path from the NPC's db attribute.
            Passes npc=self.obj as a kwarg for dialogue node access.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        caller = self.caller
        npc = self.obj
        menu_module_path = npc.db.menu_module

        menu_module_is_valid = bool(menu_module_path)

        if not menu_module_is_valid:
            caller.msg((f"{npc.key} has nothing to say right now.", _MSG_ROOM))
            return

        caller.msg((f"(You walk up and talk to {npc.key}.)", _MSG_ROOM))

        start_blackout_menu(
            caller,
            menu_module_path,
            startnode="start",
            npc=npc,
        )



class TalkCmdSet(CmdSet):
    """
    Purpose: Stores the talk command for an NPC.

    Entry:
        No conditions

    Exit/Returns:
        No conditions

    Module Globals:
        TALK_CMD_SET_KEY read
        TALK_CMD_SET_PRIORITY read

    Methodology:
        Adds CmdTalk to the cmdset during creation.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    key = TALK_CMD_SET_KEY
    priority = TALK_CMD_SET_PRIORITY


    def at_cmdset_creation(self) -> None:
        """
        Purpose: Populates the cmdset with the talk command.

        Entry:
            No conditions

        Exit/Returns:
            No conditions

        Module Globals:
            None

        Methodology:
            Instantiates and adds CmdTalk to this cmdset.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        talk_command = CmdTalk()
        self.add(talk_command)



class TalkativeNPC(ObjectParent, DefaultObject):
    """
    Purpose: An NPC that can engage in menu-driven conversations.

    Entry:
        No conditions

    Exit/Returns:
        No conditions

    Module Globals:
        None

    Methodology:
        At creation, adds the TalkCmdSet persistently.
        Expects db.menu_module to be set (string path to
        a dialogue module containing EvMenu node functions).

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """

    # How a graphical client draws this and what it may send to use it. Read
    # by systems/statefeed/serializers.py through getattr.
    #
    # `asset_kind` has to be declared because nothing else identifies this as
    # an NPC: it is not an Evennia character, and `db.npc_key` belongs to the
    # hostile NPC_DB stat blocks, which a shopkeeper has no business carrying.
    # Without it a shopkeeper served as a generic item, and the 3D pane offered
    # to pick one up.
    #
    # `talk` rather than `attack` is the whole point of declaring the verb here
    # instead of letting a client infer one from the kind: both are NPCs, and
    # only one of them is a fight.
    asset_kind = ASSET_KIND_NPC
    asset_key = "talkative_npc"
    interact_verb = TALK_COMMAND_KEY


    def at_object_creation(self) -> None:
        """
        Purpose: Called once when the NPC is first created.

        Entry:
            No conditions

        Exit/Returns:
            No conditions

        Module Globals:
            None

        Methodology:
            Calls the parent creation hook. Adds the TalkCmdSet
            persistently so the talk command is always available.
            Sets default description and initializes the menu
            module path to None.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        parent_class = super()
        parent_class.at_object_creation()

        self.cmdset.add_default(TalkCmdSet, persistent=True)

        self.db.desc = "A mysterious figure in the wastes."
        self.db.menu_module = None


class ShopkeepCleanup(Script):
    """
    Purpose: Trim a shopkeep's holdings back to its cap, so that items sold to
             it by players do not accumulate without bound.

    Entry:
        Attached to a ShopkeepNPC. `self.obj` is that NPC.

    Exit/Returns:
        No conditions.

    Module Globals:
        SHOPKEEP_CLEANUP_KEY, SHOPKEEP_CLEANUP_DESC read.
        SHOPKEEP_CLEANUP_INTERVAL, SHOPKEEP_MAX_HELD_ITEMS read.

    Methodology:
        Once a day, drop the oldest holdings until the cap is met.

    Notes/References:
        The cap falls back to SHOPKEEP_MAX_HELD_ITEMS, the same constant
        at_object_creation stamps on the NPC -- previously both this fallback
        and that stamp were a literal 20 in two files, which is the
        "Metalsmith vs Metalsmithing" shape CLAUDE.md warns about.

    Author: Nick Hobar
    Creation date: 07/13/2026
    """

    def at_script_creation(self) -> None:
        """Name the script and set it repeating once a day, persistently."""
        self.key = SHOPKEEP_CLEANUP_KEY
        self.desc = SHOPKEEP_CLEANUP_DESC
        self.interval = SHOPKEEP_CLEANUP_INTERVAL
        self.persistent = True

    def at_repeat(self) -> None:
        """Delete the oldest holdings above the cap, or stop if orphaned."""
        shopkeep = self.obj

        if not shopkeep:
            self.stop()
            return

        max_items = shopkeep.db.max_held_items or SHOPKEEP_MAX_HELD_ITEMS
        contents = list(shopkeep.contents)
        excess = len(contents) - max_items

        if excess <= 0:
            return

        for item in contents[:excess]:
            try:
                item.delete()
            except Exception:
                logger.log_trace()


class CmdSell(Command):
    """
    Sell something you are carrying to the shopkeeper standing here.

    Usage:
        sell <slot>
        sell <slot> <quantity>
        sell <slot> all
        sell <item name> [quantity|all]

    Slot numbers are the ones `inventory` prints. Without a quantity the whole
    stack in that slot is sold. There is no confirmation: a slot is one stack,
    and the reply names what you were paid.
    """
    key = SELL_COMMAND_KEY
    locks = SELL_COMMAND_LOCKS
    help_category = HELP_CATEGORY_GENERAL

    def func(self) -> None:
        """
        Purpose: Hand the raw argument to the shared sell routine.

        Entry:
            self.caller is a puppeted Character; self.obj is the shopkeeper
            this cmdset hangs on.

        Exit/Returns:
            None. shop_service.perform_sell messages every outcome.

        Module Globals:
            None.

        Methodology:
            No parsing, no pricing and no reporting happen here, because none
            of them may differ between this command and the sell node's
            `_default` option -- see perform_sell on why there are two ways
            in. This method exists to name the counterparty, which is the one
            thing the cmdset's owner knows and the menu reads off the menu
            instance.

        Notes/References:
            The import is function-level to keep the shop service out of the
            typeclass module's import graph at load time; shop_service pulls
            in ITEM_DB and SHOP_DB, and this module is imported to resolve a
            persisted typeclass path on every server start.

        Author: Nick Hobar
        Creation date: 09/02/2026
        """
        from systems.shop.shop_service import perform_sell

        perform_sell(self.caller, self.obj, self.args)


class ShopkeepCmdSet(CmdSet):
    """
    Purpose: Stores the sell command for a shopkeeper.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        SHOPKEEP_CMD_SET_KEY read.
        SHOPKEEP_CMD_SET_PRIORITY read.

    Methodology:
        A cmdset of its own rather than more commands on TalkCmdSet, because
        TalkCmdSet is what every TalkativeNPC carries and the quest-giving
        android has nothing to sell.

    Notes/References:
        Added with `add`, not `add_default`: TalkativeNPC already claims the
        default slot for TalkCmdSet, and a second add_default would displace
        `talk` on every shopkeeper.

    Author: Nick Hobar
    Creation date: 09/02/2026
    """
    key = SHOPKEEP_CMD_SET_KEY
    priority = SHOPKEEP_CMD_SET_PRIORITY
    duplicates = True


    def at_cmdset_creation(self) -> None:
        """Populate the cmdset with the sell command."""
        sell_command = CmdSell()
        self.add(sell_command)


class ShopkeepNPC(TalkativeNPC):
    """
    An NPC that buys and sells items. Extends TalkativeNPC with
    shop-specific attributes and auto-attaches the cleanup script.
    """

    asset_key = "shopkeeper"

    # What standing near this NPC lets you do with what you are carrying. Read
    # by systems/statefeed/commerce.py through getattr, the same route
    # `asset_kind` and `interact_verb` above take -- so every shopkeeper
    # already in the database gains the Sell action with no migration and no
    # respawn.
    commerce_role = COMMERCE_ROLE_SHOP

    def at_object_creation(self) -> None:
        super().at_object_creation()
        self.cmdset.add(ShopkeepCmdSet, persistent=True)
        self.db.menu_module = SHOPKEEP_DIALOGUE_MODULE
        self.db.shopdef_key = "oasis_shop"
        self.db.desc = "A shopkeeper attending a stall of salvaged goods."
        self.db.max_held_items = SHOPKEEP_MAX_HELD_ITEMS
        self.ensure_cleanup_script()

    def ensure_cleanup_script(self) -> None:
        """
        Purpose: Guarantee this shopkeep carries exactly one cleanup script,
                 under the current typeclass path.

        Entry:
            No conditions.

        Exit/Returns:
            Returns nothing. Stops any script found under a legacy path and
            adds the current one if it is missing.

        Module Globals:
            SHOPKEEP_CLEANUP_SCRIPT, LEGACY_SHOPKEEP_CLEANUP_SCRIPTS read.

        Methodology:
            Walk the attached scripts once, classifying each as legacy,
            current, or neither; delete the legacy ones and add the current
            one only if the walk did not find it.

        Notes/References:
            This is the migration for the 34 rows persisted under the old
            blackout/scripts/ path. Doing it here rather than in a one-shot
            operator script means it rides the map rebuild the operator is
            already running, in the same shape spawn_shopkeep uses to re-stamp
            `desc` and `shopdef_key` on an NPC that already exists.

            It is also a dedupe. ScriptHandler.add creates unconditionally --
            it has no presence check -- so anything that called it twice on
            one NPC would leave two daily timers trimming the same pockets.

            `delete()`, not `stop()`. In Evennia 6 `stop()` only halts the
            timer component and leaves the row standing
            (evennia/scripts/scripts.py:582), so a migration written with it
            would faithfully re-point every shopkeep and leave the stale row
            behind for the boot log to complain about anyway.

            A legacy row's typeclass no longer imports, so Evennia has already
            fallen the instance back to DefaultScript by the time this reads
            it. `typeclass_path` is a plain database field and still reports
            the stale path, which is exactly what makes it matchable.

        Author: Nick Hobar
        Creation date: 08/28/2026
        """
        found_current = False
        attached = list(self.scripts.all())

        for script in attached:
            path = script.typeclass_path

            if path in LEGACY_SHOPKEEP_CLEANUP_SCRIPTS:
                script.delete()
                continue

            if path == SHOPKEEP_CLEANUP_SCRIPT:
                if found_current:
                    script.delete()
                    continue
                found_current = True

        if not found_current:
            self.scripts.add(SHOPKEEP_CLEANUP_SCRIPT)


@register_spawner("Shopkeeper")
def spawn_shopkeep(room):
    shopkeep = spawn_once(
        room,
        "typeclasses.npcs.ShopkeepNPC",
        key="Shopkeeper",
    )

    # Stamped unconditionally, not just on first creation: spawn_once returns
    # the pre-existing shopkeep on a map rebuild, and re-applying the def keeps
    # an already-placed NPC in step with edits to these values.
    shopkeep.db.desc = "A tiny robot with a stall full of salvaged goods."
    shopkeep.db.shopdef_key = "oasis_shop"

    # Same reasoning, applied to the cmdset rather than an attribute:
    # at_object_creation runs once, so a shopkeep placed before ShopkeepCmdSet
    # existed carries `talk` and no `sell`. Adding an already-present cmdset is
    # a no-op, so this is safe to run on every rebuild.
    shopkeep.cmdset.add(ShopkeepCmdSet, persistent=True)

    # Same reasoning, applied to the cleanup script rather than an attribute:
    # this is what re-points a shopkeep persisted under the old
    # blackout/scripts/ typeclass path.
    shopkeep.ensure_cleanup_script()

    return shopkeep


class LoneAndroidNPC(TalkativeNPC):
    """
    Purpose: The android that tends the oasis farm -- the giver of "Oasis in
             the Wastes", the game's opening quest.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        LONE_ANDROID_DIALOGUE_MODULE read.

    Methodology:
        A TalkativeNPC that knows which dialogue module it speaks from. It
        needs its own typeclass rather than a bare TalkativeNPC only so the
        spawner below can identify one already standing on the tile -- and so
        the 3D pane can draw it as something other than a shopkeeper.

    Notes/References:
        Design lives in the Obsidian vault, "Oasis in the Wastes"; the quest
        blueprint is systems/quests/content/quest_oasis.py.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """

    asset_key = "lone_android"


    def at_object_creation(self) -> None:
        """Point the NPC at its dialogue module and describe it."""
        parent_class = super()
        parent_class.at_object_creation()

        self.db.menu_module = LONE_ANDROID_DIALOGUE_MODULE
        self.db.desc = LONE_ANDROID_DESC


@register_spawner("Lone Android")
def spawn_lone_android(room):
    """
    Purpose: Place the oasis quest giver on its map tile.

    Entry:
        room is the GridTile built from the "Lone Android" prototype in
        world/maps/oasis.py.

    Exit/Returns:
        Returns the NPC standing on the tile.

    Module Globals:
        LONE_ANDROID_KEY, LONE_ANDROID_DESC read.
        LONE_ANDROID_DIALOGUE_MODULE read.

    Methodology:
        world/maps/oasis.py has carried a "Lone Android" tile at (2, 0) since
        the map was written, but no spawner was ever registered for that room
        key -- so the tile built an empty room NAMED "Lone Android" and the
        quest giver did not exist. npc_oasis_guide.py was unreachable and the
        opening quest could not be started by any means.

        Stamps the description and dialogue module unconditionally, matching
        spawn_shopkeep: spawn_once returns the pre-existing NPC on a map
        rebuild, and re-applying keeps an already-placed android in step with
        edits here.

    Notes/References:
        Maps are rebuilt with scripts/clean_and_reload_all_maps.ps1.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    android = spawn_once(
        room,
        "typeclasses.npcs.LoneAndroidNPC",
        key=LONE_ANDROID_KEY,
    )

    android.db.desc = LONE_ANDROID_DESC
    android.db.menu_module = LONE_ANDROID_DIALOGUE_MODULE

    return android
