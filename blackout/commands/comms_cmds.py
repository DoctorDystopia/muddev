"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/29/2026
Description: The `page` command, with a routing tag and a reply switch.

             Evennia's CmdPage sends every line with no message type. Thus, a
             graphical client cannot put a page in its Private tab. This
             subclass tags each line with MESSAGE_TYPE_PAGE: the lines to the
             sender, and the line that each target gets.

             `page/reply <message>` sends to the last page partner, whoever
             paged whom. It never reads a target from the message, so the
             first word of a reply cannot page a different account. The Reply
             chat mode of the Godot client sends exactly this line.

             The list and `/last` read paths are Evennia's own. Only the send
             path is written here, because the engine sends each target an
             untagged line with no hook between.
"""

from evennia.commands.default.comms import CmdPage as EvenniaCmdPage
from evennia.comms.models import Msg
from evennia.utils import create

from systems.interface.statefeed import constants as feed_const


# ─── Public constant definitions ─────────────────────────────────────────────

# The switch that pages the last partner.
PAGE_REPLY_SWITCH: str = "reply"


# ─── Private constant definitions ────────────────────────────────────────────

# Evennia's tag on a stored page, as its CmdPage writes it.
_PAGE_TAG = ("page", "comms")

# A message that starts with this is a pose, as in Evennia's CmdPage.
_POSE_MARK = ":"

_HEADER = "|wAccount|n |c{sender}|n |wpages:|n {message}"
_MSG_NO_TARGET = "Who do you want to page?"
_MSG_NO_PARTNER = "You have no page to reply to."
_MSG_NO_MESSAGE = "Reply with what?"
_MSG_REFUSED = "You are not allowed to page {target}."
_MSG_OFFLINE = ("|C{target}|n is offline. They will see your message if they "
                "list their pages later.")
_MSG_SENT = "You paged {targets} with: '{message}'."


# ─── Private helper routines ─────────────────────────────────────────────────

def _tagged(text):
    """Give a plain line the page tag. A tuple already names its own kwargs."""
    if isinstance(text, str):
        return (text, {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_PAGE})

    return text


def _pages(queryset):
    """The pages in a message queryset, the newest first."""
    tag_key, tag_category = _PAGE_TAG
    pages = queryset.filter(db_tags__db_key__iexact=tag_key,
                            db_tags__db_category__iexact=tag_category)

    return pages.order_by("-db_date_created")


def _last_partners(account) -> list:
    """The other side of the newest page that the account sent or got."""
    sent = _pages(Msg.objects.get_messages_by_sender(account)).first()
    got = _pages(Msg.objects.get_messages_by_receiver(account)).first()
    newest = max((page for page in (sent, got) if page is not None),
                 key=lambda page: page.db_date_created, default=None)

    if newest is None:
        return []

    if newest == sent:
        return list(newest.receivers)

    return list(newest.senders)


# ─── Public classes ──────────────────────────────────────────────────────────

class CmdPage(EvenniaCmdPage):
    """
    send a private message to another account

    Usage:
      page <account> <message>
      page[/switches] [<account>,<account>,... = <message>]
      page/reply <message>
      tell        ''
      page <number>

    Switches:
      reply - send to the account you last paged, or that last paged you
      last - shows who you last messaged
      list - show your last <number> of tells/pages (default)

    Send a message to target user (if online). If no argument is given, you
    will get a list of your latest messages. The equal sign is needed for
    multiple targets or if sending to target with space in the name.
    """

    switch_options = EvenniaCmdPage.switch_options + (PAGE_REPLY_SWITCH,)

    def msg(self, text=None, **kwargs):
        """Send a line to the caller with the page tag."""
        super().msg(text=_tagged(text), **kwargs)

    def func(self):
        """
        Purpose: Send a page, or show the page history.

        Entry:
            None. Reads self.args, self.lhslist, self.rhs and self.switches.

        Exit/Returns:
            Returns nothing.

        Module Globals:
            PAGE_REPLY_SWITCH read.

        Methodology:
            A reply goes to the last partner. A line that sends goes through
            _parse and _send. Everything else is a read, and Evennia's own
            func does it with this class's tagged msg.

        Notes/References:
            The parse copies Evennia 6.0.0 CmdPage.func.

        Author: Nick Hobar
        Creation date: 09/29/2026
        """
        if PAGE_REPLY_SWITCH in self.switches:
            self._reply()
            return

        targets, message = self._parse()

        if message is None:
            super().func()
            return

        if targets is not None:
            self._send(targets or self._last_sent_to(), message)

    def _reply(self) -> None:
        """Send the whole argument to the last page partner."""
        message = self.args.strip()

        if not message:
            self.msg(_MSG_NO_MESSAGE)
            return

        partners = _last_partners(self.caller)

        if not partners:
            self.msg(_MSG_NO_PARTNER)
            return

        self._send(partners, message)

    def _parse(self):
        """
        Read the targets and the message, as Evennia's CmdPage does.

        Returns (targets, message). A message of None is a read: no argument,
        `/last`, or a history number. Targets of None means that a search
        failed and said so. An empty target list means the last one paged.
        """
        if not self.args or "last" in self.switches:
            return [], None

        if self.rhs:
            targets = [self.caller.search(name) for name in self.lhslist]

            if not all(targets):
                return None, self.rhs.strip()

            return targets, self.rhs.strip()

        target, *rest = self.args.split(" ", 1)

        if target.isnumeric():
            return [], None

        found = self.caller.search(target, quiet=True) if rest else None

        if found:
            return [found[0]], rest[0].strip()

        return [], self.args.strip()

    def _last_sent_to(self) -> list:
        """The receivers of the newest page that the caller sent."""
        page = _pages(Msg.objects.get_messages_by_sender(self.caller)).first()

        if page is None:
            return []

        return list(page.receivers)

    def _send(self, targets, message) -> None:
        """Store the page, deliver it tagged, and tell the sender."""
        caller = self.caller

        if not targets:
            self.msg(_MSG_NO_TARGET)
            return

        if message.startswith(_POSE_MARK):
            message = f"{caller.key} {message.strip(_POSE_MARK).strip()}"

        readers = " or ".join(f"id({target.id})" for target in targets + [caller])
        create.create_message(
            caller, message, receivers=targets, tags=[_PAGE_TAG],
            locks=(f"read:{readers} or perm(Admin);"
                   f"delete:id({caller.id}) or perm(Admin);"
                   f"edit:id({caller.id}) or perm(Admin)"))

        self._deliver(targets, message)

    def _deliver(self, targets, message) -> None:
        """Give each target the page, and report the result to the sender."""
        line = _HEADER.format(sender=self.caller.key, message=message)
        received = []
        notes = []

        for target in targets:
            if not target.access(self.caller, "msg"):
                notes.append(_MSG_REFUSED.format(target=target))
                continue

            target.msg(text=_tagged(line))
            online = not hasattr(target, "sessions") or target.sessions.count()
            received.append(f"|c{target.name}|n" if online else f"|C{target.name}|n")

            if not online:
                notes.append(_MSG_OFFLINE.format(target=target.name))

        if notes:
            self.msg("\n".join(notes))

        self.msg(_MSG_SENT.format(targets=", ".join(received), message=message))
