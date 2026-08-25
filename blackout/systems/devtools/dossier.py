"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: The moderator's read-only dossier on one character.

             Named `dossier` rather than `inspect` deliberately: a module
             called inspect.py inside a package is one `import inspect` away
             from shadowing the standard library for anything that ever grows
             a relative import, and systems/summary/registry.py already
             depends on the real one.

             Separate from actions.py because it CHANGES NOTHING. Every
             routine here is a reader, and keeping them out of the module full
             of writers means a reviewer can tell at a glance which of the two
             a moderator screen is calling.

             Most of the report is not written here at all. systems/summary/
             already renders a character's full dossier -- hitpoints, combat
             level, skills, equipment, credits, location, playtime, quests --
             and it is the panel registry that decides what that contains. A
             second rendering of the same facts here would be a second thing
             to update when a panel is added, and it would be the one that
             gets forgotten.

             What this module adds is the half a MODERATOR needs and a player
             does not: dbrefs to paste into a `py` call, who the account
             behind the character really is, whether damage immunity is on,
             and the itemised bag behind the dossier's "12 / 32".
"""

from evennia.utils import logger

from systems.summary.service import render_summary
from systems.ui.colors import DIM_COLOR, RESET_COLOR

from systems.devtools import actions as dev_actions
from systems.devtools import constants as dev_constants


# ─── Private helper routines ─────────────────────────────────────────────────

def _field(label: str, value: str) -> str:
    """Render one 'Label: value' row of the staff addendum."""
    row = dev_constants.INSPECT_FIELD.format(label=label, value=value)

    return row


def _dbref(obj) -> str:
    """Name an object as 'key (#id)', or the empty marker when there is none."""
    if obj is None:
        return dev_constants.INSPECT_NONE

    key = getattr(obj, "key", "?")
    identifier = getattr(obj, "id", "?")

    return f"{key} (#{identifier})"


def _account_rows(target) -> list:
    """
    Purpose: Report who is behind the character.

    Entry:
        target is a Character.

    Exit/Returns:
        Returns the account, permission and connection rows.

    Module Globals:
        dev_constants.INSPECT_LABEL_*, INSPECT_NO_ACCOUNT, INSPECT_NONE read.

    Methodology:
        Permissions are read off the ACCOUNT, not the character, because that
        is what Evennia's `perm` lockfunc actually consults for a puppeted
        object -- the character's own hierarchy permissions are ignored unless
        the account is quelling. Printing the character's would show a number
        that decides nothing.

    Notes/References:
        An unpuppeted character is normal, not an error: every logged-out
        player is one.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    account = getattr(target, "account", None)

    if account is None:
        return [
            _field(dev_constants.INSPECT_LABEL_ACCOUNT,
                   dev_constants.INSPECT_NO_ACCOUNT),
        ]

    permissions = list(account.permissions.all())
    permission_text = ", ".join(permissions) or dev_constants.INSPECT_NONE
    sessions = account.sessions.all()
    connected_text = str(len(sessions))

    return [
        _field(dev_constants.INSPECT_LABEL_ACCOUNT, _dbref(account)),
        _field(dev_constants.INSPECT_LABEL_PERMISSIONS, permission_text),
        _field(dev_constants.INSPECT_LABEL_CONNECTED, connected_text),
    ]


def _carried_rows(target) -> list:
    """
    Purpose: Itemise the inventory grid, slot by slot.

    Entry:
        target is a Character with an inventory handler.

    Exit/Returns:
        Returns one heading row plus one row per carried item.

    Module Globals:
        dev_constants.INSPECT_ITEM_ROW, INSPECT_STACK_SUFFIX,
        INSPECT_LABEL_CARRYING, INSPECT_NONE read.

    Methodology:
        Slot numbers are printed 1-BASED, matching what `inventory` prints and
        what the drop and equip commands parse. The handler's own index is
        0-based and the conversion happens here, the same place
        statefeed/inventory.py does it and for the same reason.

        The dbref is on every row on purpose. The question this screen exists
        to answer is usually "where did that come from", and the answer starts
        with a `py` call that needs the id.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    handler = getattr(target, "inventory", None)

    if handler is None:
        return [_field(dev_constants.INSPECT_LABEL_CARRYING,
                       dev_constants.INSPECT_NONE)]

    carried = handler.all_items()

    if not carried:
        return [_field(dev_constants.INSPECT_LABEL_CARRYING,
                       dev_constants.INSPECT_NONE)]

    rows = [_field(dev_constants.INSPECT_LABEL_CARRYING, str(len(carried)))]

    for slot_index, item in carried:
        quantity = getattr(item, "quantity", 1)
        stack_text = ""

        if quantity > 1:
            stack_text = dev_constants.INSPECT_STACK_SUFFIX.format(quantity=quantity)

        row = dev_constants.INSPECT_ITEM_ROW.format(
            slot=slot_index + 1,
            name=item.key,
            stack=stack_text,
            dim=DIM_COLOR,
            dbref=item.id,
            reset=RESET_COLOR,
        )
        rows.append(row)

    return rows


def _quest_rows(target) -> list:
    """
    Purpose: Report every quest the character has a record of, with the
        active one's step and live objective counters.

    Entry:
        target is a Character with a quest handler.

    Exit/Returns:
        Returns one heading row plus one row per quest, with objective rows
        indented beneath an active one.

    Module Globals:
        dev_constants INSPECT_QUEST_ROW, INSPECT_QUEST_OBJECTIVE,
        INSPECT_NO_STEP, INSPECT_LABEL_QUESTS, INSPECT_NONE read.

    Methodology:
        Read entirely through the handler's read API -- status,
        current_step_key, objective_lines -- and never off db.active_quests.
        Three modules owning that dict directly is how the android's dialogue
        came to print "talk:tester: 0/True" at players, and a staff screen
        reading the raw dict would be the fourth.

        The STEP KEY is what gets printed, not the step's prose. A moderator
        reading this screen is about to type that key into the step-jump node,
        and the description is already on the objective rows beneath it.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    handler = getattr(target, "quests", None)

    if handler is None:
        return [_field(dev_constants.INSPECT_LABEL_QUESTS,
                       dev_constants.INSPECT_NONE)]

    known = sorted(set(handler.active_keys()) | set(handler.completed_keys()))

    if not known:
        return [_field(dev_constants.INSPECT_LABEL_QUESTS,
                       dev_constants.INSPECT_NONE)]

    rows = [_field(dev_constants.INSPECT_LABEL_QUESTS, str(len(known)))]

    for quest_key in known:
        step_key = handler.current_step_key(quest_key)
        row = dev_constants.INSPECT_QUEST_ROW.format(
            quest_key=quest_key,
            status=handler.status(quest_key),
            step_key=step_key or dev_constants.INSPECT_NO_STEP,
        )
        rows.append(row)

        for line in handler.objective_lines(quest_key):
            rows.append(dev_constants.INSPECT_QUEST_OBJECTIVE.format(line=line))

    return rows


def _staff_lines(target) -> list:
    """
    Purpose: Build the moderator-only addendum below the player dossier.

    Entry:
        target is a Character.

    Exit/Returns:
        Returns the heading and every section's rows. A section that raises
        is replaced by a visible marker rather than taking the screen with it.

    Module Globals:
        dev_constants.INSPECT_STAFF_HEADING, INSPECT_SECTION_FAILED,
        INSPECT_LABEL_* read.

    Methodology:
        Section containment, copied from summary/service._panel_lines and for
        the identical reason: the value of a one-screen report is that it is
        one screen, so a character with one corrupt item must not be
        un-inspectable. A failure is SHOWN, not swallowed -- a hole in the
        report that looks like an empty section is worse than one that says
        it is a hole.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    sections = (_account_rows, _carried_rows, _quest_rows)
    lines = [
        "",
        dev_constants.INSPECT_STAFF_HEADING,
        _field(dev_constants.INSPECT_LABEL_CHARACTER, _dbref(target)),
        _field(dev_constants.INSPECT_LABEL_LOCATION, _dbref(target.location)),
    ]
    immune = dev_actions.godmode_enabled(target)

    if immune:
        state = dev_constants.MSG_GODMODE_STATE_ON
    else:
        state = dev_constants.MSG_GODMODE_STATE_OFF

    lines.append(_field(dev_constants.INSPECT_LABEL_GODMODE, state))

    for section in sections:
        # The name is read defensively, not decoratively. This except block is
        # the containment, so it is the one place in the module that must not
        # be able to raise -- and `__name__` is an attribute the block does not
        # own. A callable without one (a functools.partial, a mock, anything
        # wrapped) turned a contained section failure into an AttributeError
        # that took the whole report down, which is precisely the outcome the
        # try/except exists to prevent.
        section_name = getattr(section, "__name__", repr(section))

        try:
            lines.extend(section(target))
        except Exception as exc:
            logger.log_err(
                f"{dev_constants.AUDIT_LOG_PREFIX} dossier section "
                f"{section_name} failed: {exc!r}"
            )
            lines.append(dev_constants.INSPECT_SECTION_FAILED)

    return lines


# ─── Public routines ─────────────────────────────────────────────────────────

def render_report(actor, target) -> str:
    """
    Purpose: Build the whole read-only report on one character.

    Entry:
        actor is the moderator, named in the audit line. target is the
        Character being inspected.

    Exit/Returns:
        Returns the finished screen as one string. Raises nothing: a report
        that cannot be built still returns whatever it managed.

    Module Globals:
        None.

    Methodology:
        The player dossier first, verbatim from systems/summary/, then the
        staff addendum. Verbatim matters: a moderator comparing what they see
        against what the player sees is doing it to answer "is this what they
        are looking at", and a staff-only re-render of the same numbers cannot
        answer that question.

        The dossier is contained the same way its own panels are. If the whole
        summary service fails, the addendum still renders -- the dbrefs and
        the god-mode flag are the part a moderator needs mid-incident, and
        losing them because a skills panel raised would be the wrong trade.

    Notes/References:
        Audited. Who read whose dossier is exactly the question a moderation
        review asks, and a read that leaves no trace is the one nobody can
        account for afterwards.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    try:
        dossier = render_summary(target)
    except Exception as exc:
        logger.log_err(
            f"{dev_constants.AUDIT_LOG_PREFIX} summary render failed: {exc!r}"
        )
        dossier = dev_constants.INSPECT_SECTION_FAILED

    staff_lines = _staff_lines(target)
    report = "\n".join([dossier] + staff_lines)
    dev_actions.audit_inspect(actor, target)

    return report
