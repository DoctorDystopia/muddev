"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: The typeclasses of the NPCs that do not fight, one for each
             role (talkative, shopkeep, Preceptor), plus the talk command.

             ONE TYPECLASS FOR EACH ROLE, NEVER ONE FOR EACH NPC (Nick,
             10/09/2026). What one NPC is -- its name, description, model,
             dialogue, shop and Preceptor row -- is its NpcDef in
             world/npc_defs/. Until then, each named NPC had a subclass, a
             set of constants, and a spawner here. typeclasses/npc_spawners.py
             now stands up every NPC from its def.
"""



from evennia import Command, CmdSet
from evennia import DefaultObject
from evennia.utils import logger

from commands.constants import HELP_CATEGORY_GENERAL
from systems.interface.statefeed.constants import ASSET_KIND_NPC, COMMERCE_ROLE_SHOP
from typeclasses.npc_defined import NpcDefined
from typeclasses.objects import ObjectParent, Unpocketable
from .scripts import Script
from systems.interface.menus.base_menu import start_blackout_menu
from systems.interface.statefeed import constants as feed_const
from systems.gameplay.exterminator import constants as ext_const



# Every line this module sends a player is about the room around you, so the
# routing tag is bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/interface/statefeed/constants.py.
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
BUY_COMMAND_KEY = "buy"
TRADE_COMMAND_KEY = "trade"
# OSRS's name for the shop slot option that tells the price. It also tells
# what the ware is, because `inspect` on this cmdset would replace the
# character's own `inspect <slot>` near every shopkeeper.
VALUE_COMMAND_KEY = "value"
SHOPKEEP_CMD_SET_KEY = "npc_shopkeep_cmdset"
SHOPKEEP_CMD_SET_PRIORITY = 10

# The model of a shopkeep with no def. ShopkeepNPC.fallback_asset_key.
SHOPKEEP_FALLBACK_ASSET_KEY = "shopkeeper"

# The label of the `task new` action on a Preceptor. TBD.
PRECEPTOR_TASK_LABEL = "Get task"
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



def _dialogue_module_for(npc: object) -> object:
    """
    Purpose: Report which dialogue module an NPC speaks from.

    Entry:
        npc is the object CmdTalk is attached to.

    Exit/Returns:
        Returns a python path string, or None for an NPC with nothing to say.

    Module Globals:
        None.

    Methodology:
        Three sources, in a fixed order:
        1. The NpcDef that db.npc_key names. Every NPC that a spawner stands
           up has one.
        2. The `dialogue_module` class attribute, for a typeclass that
           declares one.
        3. db.menu_module, for an NPC built by a script or a prototype with
           no def and no typeclass of its own.

        The code wins over a database row. Thus, when a module moves, one
        edit of the def corrects every NPC in the database.

    Notes/References:
        The order is the fix. If this read the row first, the stale
        `systems.menus....` path of a 09/08/2026 shopkeep would hide the
        correct path forever. The dialogue modules moved again on
        10/09/2026, to world/npc_dialogues/. The def made that move a change
        of one line.

    Author: Nick Hobar
    Creation date: 09/08/2026
    """
    npc_def = getattr(npc, "npc_def", None)

    if npc_def is not None and npc_def.dialogue:
        return npc_def.dialogue_module()

    declared = getattr(npc, "dialogue_module", None)

    if declared:
        return declared

    persisted = npc.attributes.get("menu_module", default=None)

    return persisted



class CmdTalk(Command):
    """
    Purpose: Initiates a menu-driven conversation with an NPC.

    Entry:
        self.caller is a valid Evennia Character object
        self.obj is the NPC naming a dialogue module -- see
        _dialogue_module_for

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
            Asks _dialogue_module_for which module this NPC speaks from.
            Passes npc=self.obj as a kwarg for dialogue node access.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        caller = self.caller
        npc = self.obj
        menu_module_path = _dialogue_module_for(npc)

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



class TalkativeNPC(NpcDefined, Unpocketable, ObjectParent, DefaultObject):
    """
    Purpose: An NPC that can engage in menu-driven conversations.

    Entry:
        No conditions

    Exit/Returns:
        No conditions

    Module Globals:
        None

    Methodology:
        At creation, adds the TalkCmdSet persistently. The NpcDef of the NPC
        names its dialogue module. A one-off NPC with no def may set
        db.menu_module instead. NpcDefined gives the description and the
        model from the def.

    Notes/References:
        _dialogue_module_for gives the order of the three sources.

    Author: Nick Hobar
    Creation date: 07/13/2026
    """

    # A dialogue module that a typeclass declares -- a python path to a module
    # of EvMenu node functions. No role declares one now: the NpcDef names the
    # dialogue. It stays for a typeclass of a later role that speaks one fixed
    # dialogue with no def.
    #
    # It was a db attribute until 09/08/2026, stamped once at creation. The
    # repo-wide directory reorganization moved every menu under
    # systems/interface/, and every shopkeep already standing on the grid kept
    # its `systems.menus....` row -- so `talk` handed EvMenu a path that no
    # longer imported and tracebacked at the player.
    dialogue_module = None

    # How a graphical client draws this and what it may send to use it. Read
    # by systems/interface/statefeed/serializers.py through getattr.
    #
    # `asset_kind` is declared because the statefeed must know the family of
    # a talkative NPC with no def too. NpcDefined gives `asset_key` from the
    # def.
    #
    # `talk` rather than `attack` is the whole point of declaring the verb here
    # instead of letting a client infer one from the kind: both are NPCs, and
    # only one of them is a fight.
    asset_kind = ASSET_KIND_NPC
    interact_verb = TALK_COMMAND_KEY


    # Refused by Unpocketable.at_pre_get. A pocketed shopkeep takes the shop
    # with it, and nothing on the tile brings either back.
    cannot_get_message = "{name} declines to be picked up."


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
        from systems.gameplay.shop.shop_service import perform_sell

        perform_sell(self.caller, self.obj, self.args)


class CmdBuy(Command):
    """
    Buy something from the shopkeeper standing here.

    Usage:
        buy <item>
        buy <item> <quantity>
        buy <item> all

    Without a quantity you buy one. `all` buys as many as the shop has and
    you can pay for. A quantity you cannot pay for in full buys as many as
    you can. The reply names what you paid.
    """
    key = BUY_COMMAND_KEY
    locks = SELL_COMMAND_LOCKS
    help_category = HELP_CATEGORY_GENERAL

    def func(self) -> None:
        """Hand the raw argument to the shared buy routine, as CmdSell does.

        The shop pop-up sends this line from each stock slot. The import is
        function-level for the reason CmdSell.func gives.
        """
        from systems.gameplay.shop.shop_service import perform_buy

        perform_buy(self.caller, self.obj, self.args)


class CmdValue(Command):
    """
    Look at something the shopkeeper standing here sells.

    Usage:
        value <item>

    Shows what the item is, what it costs, and how many the shop has.
    """
    key = VALUE_COMMAND_KEY
    locks = SELL_COMMAND_LOCKS
    help_category = HELP_CATEGORY_GENERAL

    def func(self) -> None:
        """Hand the raw argument to the shared value routine, as CmdBuy does.

        The shop pop-up sends this line from the Inspect action of each stock
        slot. The import is function-level for the reason CmdSell.func gives.
        """
        from systems.gameplay.shop.shop_service import perform_value

        perform_value(self.caller, self.obj, self.args)


class CmdTrade(Command):
    """
    Open the shop of the shopkeeper standing here.

    Usage:
        trade

    A graphical client shows the shop as a pop-up: the stock on the left and
    your inventory on the right. Every other client gets the shop menu.
    """
    key = TRADE_COMMAND_KEY
    aliases = ["shop"]
    locks = SELL_COMMAND_LOCKS
    help_category = HELP_CATEGORY_GENERAL

    def func(self) -> None:
        """
        Purpose: Open the shop as a pop-up, or as the dialogue menu.

        Entry:
            self.obj is the shopkeeper this cmdset hangs on.

        Exit/Returns:
            Returns nothing.

        Module Globals:
            None.

        Methodology:
            1. If a session of the caller draws pop-ups, open the shop pop-up.
            2. Else, or if the pop-up refuses, start the NPC's dialogue menu.

        Notes/References:
            CmdBank.func makes the same choice, for the reason it gives: the
            pop-up must not open beside a menu, because the menu takes every
            line the pop-up sends.

        Author: Nick Hobar
        Creation date: 09/18/2026
        """
        from systems.interface.popups import service
        from systems.interface.popups.popup_defs.shop import SHOP_POPUP_KEY

        caller = self.caller
        wants = service.wants_popup(caller)

        if wants:
            opened = service.open_popup(caller, SHOP_POPUP_KEY, self.obj)

            if opened:
                return

        start_blackout_menu(
            caller, _dialogue_module_for(self.obj), startnode="start",
            npc=self.obj)


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
        """Populate the cmdset with the sell, buy, trade and value commands.

        A cmdset rebuilds from this class on every load, so a shopkeeper
        already in the database gains `buy`, `trade` and `value` with no
        migration.
        """
        self.add(CmdSell())
        self.add(CmdBuy())
        self.add(CmdTrade())
        self.add(CmdValue())


class ShopkeepNPC(TalkativeNPC):
    """
    An NPC that buys and sells items. Extends TalkativeNPC with
    shop-specific attributes and auto-attaches the cleanup script.

    The NpcDef names the shop (`shop_key`). world/shop_defs.shop_def_for
    reads it there, and falls back to db.shopdef_key only for a shopkeep
    with no def.
    """

    fallback_asset_key = SHOPKEEP_FALLBACK_ASSET_KEY
    interact_verb = TRADE_COMMAND_KEY

    # What standing near this NPC lets you do with what you are carrying. Read
    # by systems/interface/statefeed/commerce.py through getattr, the same route
    # `asset_kind` and `interact_verb` above take -- so every shopkeeper
    # already in the database gains the Sell action with no migration and no
    # respawn.
    commerce_role = COMMERCE_ROLE_SHOP

    def at_object_creation(self) -> None:
        super().at_object_creation()
        self.ensure_shop_cmdset()
        self.db.max_held_items = SHOPKEEP_MAX_HELD_ITEMS
        self.ensure_cleanup_script()

    def refresh_from_def(self) -> None:
        """
        Purpose: Bring this shopkeep in step with its def and its role, at a
                 tile sync.

        Entry:
            No conditions.

        Exit/Returns:
            Returns nothing.

        Module Globals:
            None.

        Methodology:
            The name comes from NpcDefined. Then the two ensure methods
            run. at_object_creation runs one time, so a shopkeep placed
            before ShopkeepCmdSet existed carries `talk` and no `sell`.
            Neither cmdset.add nor scripts.add is idempotent, so each ensure
            method also removes the extra copies of old rebuilds. The
            cleanup ensure also moves a script persisted under the old
            blackout/scripts/ typeclass path.

        Notes/References:
            spawn_shopkeep did this until 10/09/2026.
            typeclasses/npc_spawners.py calls this now, for every NPC.

        Author: Nick Hobar
        Creation date: 10/09/2026
        """
        super().refresh_from_def()
        self.ensure_shop_cmdset()
        self.ensure_cleanup_script()

    def extra_actions(self, observer=None) -> list:
        """
        Purpose: Both things a player may do with a shopkeeper, for a right
                 click.

        Entry:
            No conditions.

        Exit/Returns:
            Returns `trade` first and `talk` second, as {"command"} dicts.

        Module variables:
            None.

        Methodology:
            `trade` leads, so a left click opens the shop directly, as it does
            for the bank. A right click offers `Trade` first and `Talk` second.
            Neither row names a label: _action_label capitalises the verb, and
            both verbs are read from their commands here.

        Notes/References:
            systems/interface/statefeed/serializers.py interact_actions
            consumes this.

        Author: Nick Hobar
        Creation date: 09/18/2026
        """
        return [{"command": TRADE_COMMAND_KEY}, {"command": TALK_COMMAND_KEY}]

    def ensure_shop_cmdset(self) -> None:
        """
        Purpose: Make sure this shopkeep carries exactly one ShopkeepCmdSet.

        Entry:
            No conditions.

        Exit/Returns:
            Returns nothing. Removes every extra copy, and adds the cmdset if
            it is missing.

        Module Globals:
            SHOPKEEP_CMD_SET_KEY read.

        Methodology:
            1. Count the copies on the cmdset stack, by key.
            2. If the count is one, stop. Nothing touches the database.
            3. Else remove every copy, then add one.

        Notes/References:
            CmdSetHandler.add has no presence check. It appends to the stack
            and to cmdset_storage on every call. The cmdset is
            `duplicates = True`, so two copies give two `trade` commands on
            one shopkeep, and the player gets "More than one match".
            at_object_creation and the old spawn_shopkeep each added one, so
            every spawned shopkeep had two, and each map rebuild added one
            more. refresh_from_def calls this on each tile sync, so the sync
            heals the shopkeeps already in the database.

        Author: Nick Hobar
        Creation date: 09/18/2026
        """
        copies = [cmdset for cmdset in self.cmdset.all()
                  if cmdset.key == SHOPKEEP_CMD_SET_KEY]

        if len(copies) == 1:
            return

        if copies:
            self.cmdset.remove(SHOPKEEP_CMD_SET_KEY)

        self.cmdset.add(ShopkeepCmdSet, persistent=True)

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
            operator script means it rides the tile sync the operator is
            already running, through refresh_from_def.

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


class PreceptorNPC(TalkativeNPC):
    """
    Purpose: An NPC that gives Exterminator tasks and teaches buffs.

    Entry:
        The NpcDef of the NPC names `preceptor_key`, a key of PRECEPTOR_DB,
        and its dialogue.

    Exit/Returns:
        No conditions.

    Module Globals:
        TALK_COMMAND_KEY, PRECEPTOR_TASK_LABEL read.

    Methodology:
        The rules of the Preceptor live in its PreceptorDef. This class
        reads the key of that row from the NpcDef on each use, never from a
        db row. Thus, a change to the def reaches the NPC that already
        stands in the world.

        No cmdset of its own. `task new` is on every character and finds a
        Preceptor in the room. That avoids the duplicate-cmdset trap of
        ensure_shop_cmdset.

    Notes/References:
        DESIGN-0012, Phase 2. Nick, 10/06/2026: a player can talk, or go
        straight to the assignment. One subclass for each Preceptor until
        10/09/2026.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """

    @property
    def preceptor_key(self) -> str:
        """The PRECEPTOR_DB key that the def names, or "" with no def."""
        npc_def = self.npc_def

        if npc_def is None or not npc_def.preceptor_key:
            return ""

        return npc_def.preceptor_key

    def extra_actions(self, observer=None) -> list:
        """
        Purpose: Both things a player can do with a Preceptor, for a right
                 click.

        Entry:
            No conditions.

        Exit/Returns:
            Returns `talk` first and `task new <name>` second.

        Module Globals:
            TALK_COMMAND_KEY, PRECEPTOR_TASK_LABEL read.

        Methodology:
            `talk` leads, so a left click talks, as on an OSRS Slayer
            master. The task command names this Preceptor, so a room with
            two Preceptors still sends the right one.

        Notes/References:
            systems/interface/statefeed/serializers.py interact_actions
            reads this.

        Author: Nick Hobar
        Creation date: 10/06/2026
        """
        task_command = f"{ext_const.TASK_NEW_COMMAND} {self.key}"

        return [
            {"command": TALK_COMMAND_KEY},
            {"command": task_command, "label": PRECEPTOR_TASK_LABEL},
        ]
