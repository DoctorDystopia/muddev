"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The `aug` command (DESIGN-0015, Phase 2). It lists the augments,
             lights one at a step, re-steps a lit one, puts one out, or
             puts every augment out. The shape of CmdAura in combat_cmds.py.
             The rows of the listing come from the handler and the
             registry, so the listing and the rail (Phase 3) read one fact.

             `graft` (Phase 4) consumes a sample for Augmentation XP. The
             command resolves the item, and augmentation/graft.py does the
             rest.

             `socket`, `unsocket`, and `rig` (Phase 5) change and show the
             rig. augmentation/sockets.py does the work, and the rig pop-up
             (popups/popup_defs/rig.py) sends the same lines.
"""

from evennia import CmdSet, Command

from commands.constants import HELP_CATEGORY_AUGMENTATION
from commands.inventory_cmds import resolve_carried_item
from systems.gameplay.augmentation import constants as aug_const
from systems.gameplay.augmentation import detail
from systems.gameplay.augmentation import graft as graft_service
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


def _parse_step(token: str):
    """
    Purpose: Read a step from the last word of the argument.

    Entry:
        token is one word. May be empty.

    Exit/Returns:
        Returns the step as an int in [AUG_STEP_MIN, AUG_STEPS], or None
        when the word is not a step in that range.

    Module Globals:
        aug_const.AUG_STEP_MIN, AUG_STEPS read.

    Methodology:
        One int parse, then one bounds check.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    if not token.isdigit():
        return None

    step = int(token)

    if step < aug_const.AUG_STEP_MIN or step > aug_const.AUG_STEPS:
        return None

    return step


def _split_argument(argument: str) -> tuple:
    """
    Purpose: Split `<name> [<step>|off]` into its name and its tail.

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
           out of the step range is still a tail, so the caller refuses it
           as a bad step, not as a bad name.
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
    """Command aug [<name> [<step>|off]|off] — light an augment, or list them.

    An augment boosts one axis of your fights while it burns, and it drains
    your Grit on each tick. At 0 Grit, every augment goes dark. An AugBot
    refills your Grit.

    Usage:
        aug                 list your augments and which ones burn
        aug reflex          light Reflex at the top step
        aug reflex 1        light Reflex at step 1: a third of the strength
                            for a third of the drain
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

        step = aug_const.AUG_STEP_DEFAULT

        if tail:
            step = _parse_step(tail)

        self._light(augment, step)

    def _list(self) -> None:
        """Show every augment, its state, and its step.

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
                    step=row[feed_const.ABILITY_STEP_KEY])
            else:
                status = aug_const.AUG_LIST_READY

            lines.append(f"  |y{row['name']}|n — {status}")

        caller.msg(("\n".join(lines), _MSG_COMBAT))

    def _light_set(self) -> None:
        """Light every socketed augment that can come online, at the
        default step. The rig decides the set (Phase 5)."""
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
            handler.light(augment, aug_const.AUG_STEP_DEFAULT)

        # Counted after the lights: a conflict group puts one out as the
        # next one comes on.
        count = len(handler.lit_augments())

        caller.msg((aug_const.AUG_SET_MESSAGE.format(count=count), _MSG_COMBAT))

    def _light(self, augment, step) -> None:
        """Light an augment at a step, or move a lit one to the step."""
        caller = self.caller

        if step is None:
            caller.msg((aug_const.AUG_BAD_STEP_MESSAGE.format(
                low=aug_const.AUG_STEP_MIN, high=aug_const.AUG_STEPS), _MSG_COMBAT))
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
        was_lit = handler.light(augment, step)
        template = aug_const.AUG_RESTEP_MESSAGE if was_lit else aug_const.AUG_LIGHT_MESSAGE

        caller.msg((template.format(name=augment.name, step=step), _MSG_COMBAT))

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


class CmdGraft(Command):
    """Command graft <sample> — consume a sample for Augmentation XP.

    A sample is a part of a body or a machine that your own body can take.
    A graft anywhere pays the XP of the sample. A graft on the tile of an
    Augmentation Locus pays more.

    Usage:
        graft                 list the samples you carry
        graft mutant gland    graft one mutant gland
        graft 7               graft the sample in bag slot 7
    """

    key = aug_const.GRAFT_COMMAND_KEY
    help_category = HELP_CATEGORY_AUGMENTATION

    def func(self) -> None:
        """
        Purpose: Resolve the named sample and graft it, or list the samples.

        Entry:
            self.caller is a puppeted Character. self.args may be empty.

        Exit/Returns:
            No conditions.

        Module Globals:
            aug_const.GRAFT_* read.

        Methodology:
            1. With no argument, list the samples in the bag, or say that
               there are none.
            2. Else, resolve the argument as `eat` does: a slot number
               first, then a name over the contents.
            3. Hand the object to graft_service.graft, which refuses a
               thing that is no sample.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 10/30/2026
        """
        caller = self.caller
        argument = self.args.strip()

        if not argument:
            self._list_samples()
            return

        _index, item = resolve_carried_item(caller, argument)

        if item is None:
            return

        graft_service.graft(caller, item)

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


class CmdSocket(Command):
    """Command socket <augment> <socket> — put an augment into your rig.

    Your rig has eight sockets, the parts of your body. Each augment fits
    some of them, and your Augmentation level opens them one by one. The
    ability rail shows the socketed augments only. A swap happens anywhere,
    out of a fight.

    Usage:
        socket reflex head       put Reflex in your head socket
        socket surge right arm   put Surge in your right arm socket
    """

    key = aug_const.SOCKET_COMMAND_KEY
    help_category = HELP_CATEGORY_AUGMENTATION

    def func(self) -> None:
        caller = self.caller
        argument = self.args.strip()
        name, socket_key = _split_socket_argument(argument)

        if not name or not socket_key:
            caller.msg((_socket_usage(aug_const.SOCKET_USAGE_MESSAGE), _MSG_COMBAT))
            return

        augment = find_augment(name)

        if augment is None:
            caller.msg((aug_const.AUG_UNKNOWN_MESSAGE.format(name=name), _MSG_COMBAT))
            return

        _placed, message = sockets.place(caller, augment, socket_key)

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
