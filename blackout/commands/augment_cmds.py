"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The `aug` command (DESIGN-0015, Phase 2). It lists the augments
             and lights one at a power level. It also moves a lit one to a
             new power level, puts one out, or puts every augment out. The shape of CmdAura in combat_cmds.py.
             The rows of the listing come from the handler and the
             registry, so the listing and the rail (Phase 3) read one fact.

             `graft` (Phase 4) consumes a sample for Augmentation XP. The
             command resolves the item, and augmentation/graft.py does the
             rest. Since 11/09/2026, `graft` takes a count. The graft
             channel (augmentation/graft_channel.py) paces it, and a bare
             `graft` at a Locus opens the Locus pop-up.

             `socket`, `unsocket`, and `rig` (Phase 5) change and show the
             rig. augmentation/sockets.py does the work, and the rig pop-up
             (popups/popup_defs/rig.py) sends the same lines.
"""

from evennia import CmdSet, Command

from commands.constants import HELP_CATEGORY_AUGMENTATION
from commands.inventory_cmds import resolve_carried_item, split_item_and_count
from systems.gameplay.augmentation import constants as aug_const
from systems.gameplay.augmentation import detail
from systems.gameplay.augmentation import graft as graft_service
from systems.gameplay.augmentation import graft_channel
from systems.gameplay.augmentation import pool
from systems.gameplay.augmentation import sockets
from systems.gameplay.augmentation.handler import (
    ensure_augment_handler,
    get_augment_handler_for,
)
from systems.gameplay.augmentation.registry import (
    AUGMENT_REGISTRY,
    augments_in_order,
    find_augment,
)
from systems.interface.statefeed import constants as feed_const


# Every line that `aug` sends a player is combat, so the routing tag is
# bound one time here. A graft is progression.
_MSG_COMBAT = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_COMBAT}
_MSG_PROGRESSION = {
    feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_PROGRESSION}


def _parse_power_level(token: str):
    """
    Purpose: Read a power level from the last word of the argument.

    Entry:
        token is one word. May be empty.

    Exit/Returns:
        Returns the power level as an int in [AUG_POWER_LEVEL_MIN,
        AUG_POWER_LEVELS], or None when the word is not a power level in
        that range.

    Module Globals:
        aug_const.AUG_POWER_LEVEL_MIN, AUG_POWER_LEVELS read.

    Methodology:
        One int parse, then one bounds check.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    if not token.isdigit():
        return None

    power_level = int(token)

    low = aug_const.AUG_POWER_LEVEL_MIN
    high = aug_const.AUG_POWER_LEVELS

    if power_level < low or power_level > high:
        return None

    return power_level


def _split_argument(argument: str) -> tuple:
    """
    Purpose: Split `<name> [<power level>|off]` into its name and its tail.

    Entry:
        argument is the stripped argument of the command.

    Exit/Returns:
        Returns (name, tail). The tail is the last word when it is a number
        or the off word, else an empty string. The name is the rest.

    Module Globals:
        aug_const.AUG_OFF_ARG read.

    Methodology:
        1. Split on the last space.
        2. If the last word is "off" or a number, it is the tail. A number
           out of the power level range is still a tail, so the caller
           refuses it as a bad power level, not as a bad name.
        3. Else, the whole argument is the name.

    Notes/References:
        A name holds no digits today. A two-word name such as "righteous
        fire" still works, because only the last word is tested.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    head, _sep, last = argument.rpartition(" ")

    if not head:
        return argument, ""

    is_off = last.lower() == aug_const.AUG_OFF_ARG

    if is_off or last.isdigit():
        return head, last

    return argument, ""


class CmdAug(Command):
    """Command aug [<name> [<power level>|off]|off] — light an augment, or list them.

    An augment boosts one axis of your fights while it burns, and it drains
    your Grit on each tick. At 0 Grit, every augment goes dark. An AugBot
    refills your Grit.

    Usage:
        aug                 list your augments and which ones burn
        aug reflex          light Reflex at the top power level
        aug reflex 1        light Reflex at power level 1: a third of the
                            strength for a third of the drain
        aug reflex off      put Reflex out
        aug set             light every augment you can use
        aug off             put every augment out
    """

    key = aug_const.AUG_COMMAND_KEY
    aliases = ["augs", "augment", "augments"]
    help_category = HELP_CATEGORY_AUGMENTATION

    def func(self) -> None:
        caller = self.caller
        argument = self.args.strip()

        if not argument:
            self._list()
            return

        if argument.lower() == aug_const.AUG_OFF_ARG:
            self._put_out_all()
            return

        if argument.lower() == aug_const.AUG_SET_ARG:
            self._light_set()
            return

        name, tail = _split_argument(argument)
        augment = find_augment(name)

        if augment is None:
            caller.msg((aug_const.AUG_UNKNOWN_MESSAGE.format(name=name), _MSG_COMBAT))
            return

        if tail.lower() == aug_const.AUG_OFF_ARG:
            self._put_out(augment)
            return

        power_level = aug_const.AUG_POWER_LEVEL_DEFAULT

        if tail:
            power_level = _parse_power_level(tail)

        self._light(augment, power_level)

    def _list(self) -> None:
        """Show every augment, its state, and its power level.

        The rows come from augmentation/detail.py, which the ability rail
        of the Godot client reads too. Thus, the listing and the rail
        cannot disagree on what burns and what a level locks.
        """
        caller = self.caller

        if not AUGMENT_REGISTRY:
            caller.msg((aug_const.AUG_LIST_EMPTY, _MSG_COMBAT))
            return

        held = pool.current(caller)
        cap = pool.maximum(caller)
        lines = [f"{aug_const.AUG_LIST_TITLE} (Grit {held}/{cap})"]
        rows = detail.ability_rows(caller)
        toggles = [row for row in rows if row["kind"] == feed_const.ABILITY_KIND_TOGGLE]

        if not toggles:
            lines.append(aug_const.AUG_LIST_NO_SOCKETS)

        for row in rows:
            if row["kind"] != feed_const.ABILITY_KIND_TOGGLE:
                continue

            if row["state"] == feed_const.ABILITY_STATE_LOCKED:
                status = f"|r{row['reason']}|n"
            elif row["state"] == feed_const.ABILITY_STATE_ACTIVE:
                status = aug_const.AUG_LIST_LIT.format(
                    power_level=row[feed_const.ABILITY_POWER_LEVEL_KEY])
            else:
                status = aug_const.AUG_LIST_READY

            lines.append(f"  |y{row['name']}|n — {status}")

        caller.msg(("\n".join(lines), _MSG_COMBAT))

    def _light_set(self) -> None:
        """Light every socketed augment that can come online, at the
        default power level. The rig decides the set (Phase 5)."""
        caller = self.caller
        held = pool.current(caller)

        if held <= aug_const.GRIT_EMPTY:
            caller.msg((aug_const.AUG_NO_GRIT_MESSAGE, _MSG_COMBAT))
            return

        able = []

        for augment in sockets.socketed_augments(caller):
            allowed, _reason = augment.can_activate(caller)

            if allowed:
                able.append(augment)

        if not able:
            caller.msg((aug_const.AUG_SET_NONE_MESSAGE, _MSG_COMBAT))
            return

        handler = ensure_augment_handler(caller)

        for augment in able:
            handler.light(augment, aug_const.AUG_POWER_LEVEL_DEFAULT)

        # Counted after the lights: a conflict group puts one out as the
        # next one comes on.
        count = len(handler.lit_augments())

        caller.msg((aug_const.AUG_SET_MESSAGE.format(count=count), _MSG_COMBAT))

    def _light(self, augment, power_level) -> None:
        """Light an augment at a power level, or move a lit one to that
        power level."""
        caller = self.caller

        if power_level is None:
            caller.msg((aug_const.AUG_BAD_POWER_LEVEL_MESSAGE.format(
                low=aug_const.AUG_POWER_LEVEL_MIN,
                high=aug_const.AUG_POWER_LEVELS), _MSG_COMBAT))
            return

        allowed, reason = augment.can_activate(caller)

        if not allowed:
            caller.msg((f"|r{reason}|n", _MSG_COMBAT))
            return

        in_rig = sockets.is_socketed(caller, augment.key)

        if not in_rig:
            caller.msg((aug_const.AUG_NOT_SOCKETED_MESSAGE.format(name=augment.name),
                        _MSG_COMBAT))
            return

        held = pool.current(caller)

        if held <= aug_const.GRIT_EMPTY:
            caller.msg((aug_const.AUG_NO_GRIT_MESSAGE, _MSG_COMBAT))
            return

        handler = ensure_augment_handler(caller)
        was_lit = handler.light(augment, power_level)
        template = (aug_const.AUG_POWER_SHIFT_MESSAGE if was_lit
                    else aug_const.AUG_LIGHT_MESSAGE)
        text = template.format(name=augment.name, power_level=power_level)

        caller.msg((text, _MSG_COMBAT))

    def _put_out(self, augment) -> None:
        """Put one augment out."""
        caller = self.caller
        handler = get_augment_handler_for(caller)
        was_lit = False

        if handler is not None:
            was_lit = handler.put_out(augment.key)

        if not was_lit:
            caller.msg((aug_const.AUG_NOT_LIT_MESSAGE.format(name=augment.name), _MSG_COMBAT))
            return

        caller.msg((aug_const.AUG_OUT_MESSAGE.format(name=augment.name), _MSG_COMBAT))

        if handler is not None and not handler.lit_augments():
            handler.stop_handler()

    def _put_out_all(self) -> None:
        """Put every augment out."""
        caller = self.caller
        handler = get_augment_handler_for(caller)

        if handler is None:
            caller.msg((aug_const.AUG_NONE_LIT_MESSAGE, _MSG_COMBAT))
            return

        was_lit = handler.put_out_all()
        handler.stop_handler()

        if not was_lit:
            caller.msg((aug_const.AUG_NONE_LIT_MESSAGE, _MSG_COMBAT))
            return

        caller.msg((aug_const.AUG_ALL_OUT_MESSAGE, _MSG_COMBAT))


def _graft_count(count, units: int) -> int:
    """
    Purpose: Map a parsed count to the number of grafts to queue.

    Entry:
        count is what split_item_and_count gives: None, an int, or the
        "all" keyword.
        units is the number of units that the player carries, at least 1.

    Exit/Returns:
        Returns an int in [GRAFT_COUNT_MIN, units].

    Module Globals:
        aug_const.GRAFT_COUNT_MIN read.

    Methodology:
        An omitted count is one graft, and "all" is every unit carried. A
        larger count clamps to the units, as a craft batch clamps.

    Notes/References:
        _craft_count in typeclasses/crafting_facilities.py is the model.

    Author: Nick Hobar
    Creation date: 11/09/2026
    """
    from systems.interface.menus.base_menu import QUANTITY_ALL_KEYWORD

    if count is None:
        return aug_const.GRAFT_COUNT_MIN

    if count == QUANTITY_ALL_KEYWORD:
        return units

    wanted = max(aug_const.GRAFT_COUNT_MIN, int(count))

    return min(wanted, units)


def _resolve_sample(caller, text: str):
    """
    Purpose: Resolve the name part of a `graft` argument to one sample.

    Entry:
        caller is the grafter. text is not empty.

    Exit/Returns:
        Returns (group name, display name), or None after one line to the
        caller.

    Module Globals:
        aug_const.GRAFT_NOT_A_SAMPLE_MESSAGE read.

    Methodology:
        1. A sample key or a full sample name matches the ItemDef. The
           Locus pop-up sends the key.
        2. Else, resolve the text as `eat` does: a slot number first, then
           a name over the contents. resolve_carried_item sends its own
           refusal.
        3. Refuse a thing that is no sample.

    Notes/References:
        A sample with no unit carried still resolves in step 1. The caller
        then says that the player carries none.

    Author: Nick Hobar
    Creation date: 11/09/2026
    """
    item_def = graft_service.sample_def_for(text)

    if item_def is not None:
        return item_def.name.lower(), item_def.name

    _index, item = resolve_carried_item(caller, text)

    if item is None:
        return None

    is_a_sample = graft_service.is_sample(item)

    if not is_a_sample:
        caller.msg((aug_const.GRAFT_NOT_A_SAMPLE_MESSAGE.format(
            name=item.get_display_name(caller)), _MSG_PROGRESSION))
        return None

    return graft_service.group_name(item), str(item.key)


class CmdGraft(Command):
    """Command graft <sample> [<count>|all] — consume samples for Augmentation XP.

    A sample is a part of a body or a machine that your own body can take.
    A graft anywhere pays the XP of the sample. A graft on the tile of an
    Augmentation Locus pays more. One graft takes three ticks, and a walk
    or a fight stops a count.

    Usage:
        graft                   list the samples you carry, or open the
                                Locus when you stand at one
        graft mutant gland      graft one mutant gland
        graft mutant gland 5    graft five, one after another
        graft mutant gland all  graft every mutant gland you carry
        graft 7                 graft the sample in bag slot 7
        graft stop              stop grafting
    """

    key = aug_const.GRAFT_COMMAND_KEY
    help_category = HELP_CATEGORY_AUGMENTATION

    def func(self) -> None:
        """
        Purpose: Queue grafts of the named sample, stop them, or show the
                 samples.

        Entry:
            self.caller is a puppeted Character. self.args may be empty.

        Exit/Returns:
            No conditions.

        Module Globals:
            aug_const.GRAFT_* read.

        Methodology:
            1. With no argument, open the Locus pop-up when the caller
               stands at a Locus and draws pop-ups. Else, list the samples.
            2. `graft stop` ends the running count.
            3. Else, split the count off, resolve the sample, and clamp the
               count to the units carried.
            4. Queue the count on the graft channel. The channel grafts the
               first unit at once when no graft is in its wait.

        Notes/References:
            The Locus pop-up sends `graft <sample key> <count>` and
            `graft stop`. A telnet player types the same lines.

        Author: Nick Hobar
        Creation date: 11/09/2026 (count and channel), 10/30/2026
        """
        caller = self.caller
        argument = self.args.strip()

        if not argument:
            self._open_or_list()
            return

        if argument.lower() == aug_const.GRAFT_STOP_ARG:
            graft_channel.stop_grafting(caller)
            return

        text, count = split_item_and_count(argument)
        resolved = _resolve_sample(caller, text)

        if resolved is None:
            return

        name, display = resolved
        units = graft_service.units_carried(caller, name)

        if units <= 0:
            caller.msg((aug_const.GRAFT_NONE_CARRIED_MESSAGE.format(name=display),
                        _MSG_PROGRESSION))
            return

        grafts = _graft_count(count, units)

        graft_channel.start_grafting(caller, name, display, grafts)

    def _open_or_list(self) -> None:
        """Open the Locus pop-up, or list the samples in the bag.

        The imports are local, as in CmdRig.func: the pop-up registry
        imports every pop-up definition, and the Locus typeclass imports
        the package of this command's services.
        """
        from systems.interface.popups import service as popup_service
        from systems.interface.popups.popup_defs.locus import LOCUS_POPUP_KEY
        from typeclasses.loci import locus_here

        caller = self.caller
        locus = locus_here(caller)
        wants = popup_service.wants_popup(caller)

        if locus is not None and wants:
            opened = popup_service.open_popup(caller, LOCUS_POPUP_KEY, locus)

            if opened:
                return

        self._list_samples()

    def _list_samples(self) -> None:
        """Name every sample in the bag, or say that there is none."""
        caller = self.caller
        samples = graft_service.samples_carried(caller)

        if not samples:
            caller.msg((aug_const.GRAFT_NO_SAMPLES_MESSAGE, _MSG_PROGRESSION))
            return

        names = aug_const.GRAFT_LIST_SEPARATOR.join(
            item.get_display_name(caller) for item in samples)

        caller.msg((aug_const.GRAFT_NOTHING_NAMED_MESSAGE.format(names=names),
                    _MSG_PROGRESSION))


def _socket_usage(template: str) -> str:
    """A usage line with the socket labels filled in."""
    return template.format(sockets=sockets.socket_labels())


def _split_socket_argument(argument: str) -> tuple:
    """
    Purpose: Split `<augment> <socket>` into the augment name and the socket
             key. A socket label may hold a space ("right arm"), so the
             split tries the longest socket tail first.

    Entry:
        argument is the stripped argument of the command.

    Exit/Returns:
        Returns (name, socket_key). Either is "" when the split fails.

    Module Globals:
        None.

    Methodology:
        Walk the words from the right. The tail of one word, then of two,
        is tried as a socket. The first tail that names a socket wins, and
        the head is the augment name.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    words = argument.split()

    for tail_length in (1, 2):
        if len(words) <= tail_length:
            break

        head = " ".join(words[:-tail_length])
        tail = " ".join(words[-tail_length:])
        socket_key = sockets.find_socket(tail)

        if socket_key:
            return head, socket_key

    return "", ""


# The switches that `socket` reads. "" is the plain form.
_SOCKET_SWITCHES: tuple = ("", aug_const.SOCKET_SWAP_SWITCH)


def _split_switch(argument: str) -> tuple:
    """
    Split `/swap reflex head` into ("swap", "reflex head").

    An argument with no switch mark gives ("", argument). Evennia gives a
    plain Command the switch as the start of its argument, as `goto/run`
    shows in commands/movement_cmds.py.
    """
    if not argument.startswith(aug_const.SOCKET_SWITCH_MARK):
        return "", argument

    switch, _space, rest = argument[len(aug_const.SOCKET_SWITCH_MARK):].partition(" ")

    return switch.strip().lower(), rest.strip()


class CmdSocket(Command):
    """Command socket <augment> <socket> — put an augment into your rig.

    Your rig has eight sockets, the parts of your body. Each augment fits
    some of them, and your Augmentation level opens them one by one. The
    ability rail shows the socketed augments only. A swap happens anywhere,
    out of a fight.

    A plain socket refuses a socket that holds another augment. With
    /swap, the held augment moves to the socket that the new one left,
    if it fits there. Otherwise it leaves your rig. A drag onto a socket
    in the rig window does the same.

    Usage:
        socket reflex head        put Reflex in your head socket
        socket surge right arm    put Surge in your right arm socket
        socket/swap surge head    put Surge in your head, swap out its augment
    """

    key = aug_const.SOCKET_COMMAND_KEY
    help_category = HELP_CATEGORY_AUGMENTATION

    def func(self) -> None:
        caller = self.caller
        switch, argument = _split_switch(self.args.strip())
        name, socket_key = _split_socket_argument(argument)

        if switch not in _SOCKET_SWITCHES or not name or not socket_key:
            caller.msg((_socket_usage(aug_const.SOCKET_USAGE_MESSAGE), _MSG_COMBAT))
            return

        augment = find_augment(name)

        if augment is None:
            caller.msg((aug_const.AUG_UNKNOWN_MESSAGE.format(name=name), _MSG_COMBAT))
            return

        swap = switch == aug_const.SOCKET_SWAP_SWITCH
        _placed, message = sockets.place(caller, augment, socket_key, swap=swap)

        caller.msg((message, _MSG_COMBAT))


class CmdUnsocket(Command):
    """Command unsocket <socket> — take the augment out of a socket.

    A lit augment goes dark when it leaves your rig. A swap happens
    anywhere, out of a fight.

    Usage:
        unsocket head
        unsocket right arm
    """

    key = aug_const.UNSOCKET_COMMAND_KEY
    help_category = HELP_CATEGORY_AUGMENTATION

    def func(self) -> None:
        caller = self.caller
        argument = self.args.strip()

        if not argument:
            caller.msg((_socket_usage(aug_const.UNSOCKET_USAGE_MESSAGE), _MSG_COMBAT))
            return

        socket_key = sockets.find_socket(argument)

        if not socket_key:
            caller.msg((aug_const.SOCKET_UNKNOWN_MESSAGE.format(
                socket=argument, sockets=sockets.socket_labels()), _MSG_COMBAT))
            return

        _removed, message = sockets.remove(caller, socket_key)

        caller.msg((message, _MSG_COMBAT))


def _rig_lines(caller) -> list:
    """The rig as text: one line for each socket, then each augment."""
    level = pool.level(caller)
    held = sockets.assignments(caller)
    opened = sockets.open_sockets(caller)
    lines = [aug_const.RIG_LIST_TITLE]

    for socket_key in aug_const.SOCKETS:
        label = aug_const.SOCKET_NAMES[socket_key]

        if socket_key not in opened:
            holds = aug_const.RIG_SOCKET_LOCKED.format(level=sockets.unlock_level(socket_key))
        elif socket_key in held:
            holds = AUGMENT_REGISTRY[held[socket_key]].name
        else:
            holds = aug_const.RIG_SOCKET_EMPTY

        lines.append(aug_const.RIG_SOCKET_LINE.format(socket=label, holds=holds))

    lines.append(f"|w{aug_const.RIG_AUGMENTS_TITLE}|n (Augmentation {level})")

    for augment in augments_in_order():
        lines.append(aug_const.RIG_AUGMENT_LINE.format(
            name=augment.name, fits=augment.socket_labels()))

    return lines


class CmdRig(Command):
    """Command rig — show your rig: the sockets, and the augments you know.

    A graphical client opens the rig as a pop-up. A telnet client gets the
    same facts as text.

    Usage:
        rig
    """

    key = aug_const.RIG_COMMAND_KEY
    help_category = HELP_CATEGORY_AUGMENTATION

    def func(self) -> None:
        """Open the rig pop-up, or print the rig."""
        from systems.interface.popups import service as popup_service
        from systems.interface.popups.popup_defs.rig import RIG_POPUP_KEY

        caller = self.caller
        wants = popup_service.wants_popup(caller)

        if wants:
            opened = popup_service.open_popup(caller, RIG_POPUP_KEY, caller)

            if opened:
                return

        caller.msg(("\n".join(_rig_lines(caller)), _MSG_COMBAT))


class AugmentCmdSet(CmdSet):
    """The augment commands, on every character."""

    key = "AugmentCmdSet"

    def at_cmdset_creation(self):
        self.add(CmdAug())
        self.add(CmdGraft())
        self.add(CmdSocket())
        self.add(CmdUnsocket())
        self.add(CmdRig())
