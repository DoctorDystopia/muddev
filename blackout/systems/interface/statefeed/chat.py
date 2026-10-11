"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/29/2026
Description: Build the chat modes of a character: each place that a typed
             line can go, and the command prefix that sends it there.

             The Godot chat bar draws a mode from each row and wraps a typed
             line in its prefix. Thus, every prefix here is the start of a
             command that a telnet player can type. The key of each command
             comes from the command class, never from a literal.

             Imported LAZILY by events.emit_chat. It reads the comms models,
             and events.py loads at typeclass import time.
"""

from systems.interface.statefeed import constants as const

from .payloads import CharChatPayload


# ─── Public constant definitions ─────────────────────────────────────────────

# The keys of the modes that are not Evennia channels. A client keeps the
# key of the chosen mode between sessions, so a key must never change.
MODE_KEY_SAY: str = "say"
MODE_KEY_YELL: str = "yell"
MODE_KEY_REPLY: str = "reply"

# The start of the key of a channel mode. The rest is the channel key in
# lower case.
MODE_KEY_CHANNEL_PREFIX: str = "channel:"

# The labels that the chat bar shows for the fixed modes.
MODE_LABEL_SAY: str = "Say"
MODE_LABEL_YELL: str = "Yell"
MODE_LABEL_REPLY: str = "Reply"


# ─── Private constant definitions ────────────────────────────────────────────

# The placeholder for the message in Evennia's channel nick replacement,
# "@channel {channelname} = $1". The prefix is the text before it.
_NICK_MESSAGE_ARGUMENT = "$1"


# ─── Private helper routines ─────────────────────────────────────────────────

def _mode(key: str, label: str, message_type: str, prefix: str) -> dict:
    """One row of the payload."""
    row = {"key": key, "label": label, "type": message_type, "prefix": prefix}

    return row


def _speech_modes() -> list:
    """
    The modes of the speech commands: Say for the say range, and Yell for
    the area. A yell line has the `say` type, so both modes go on the tab
    that shows a say.
    """
    from commands.speech_cmds import CmdSay, CmdYell

    say = _mode(MODE_KEY_SAY, MODE_LABEL_SAY, const.MESSAGE_TYPE_SAY,
                f"{CmdSay.key} ")
    yell = _mode(MODE_KEY_YELL, MODE_LABEL_YELL, const.MESSAGE_TYPE_SAY,
                 f"{CmdYell.key} ")

    return [say, yell]


def _reply_mode() -> dict:
    """The mode that pages the last page partner, through `page/reply`."""
    from commands.comms_cmds import PAGE_REPLY_SWITCH, CmdPage

    return _mode(MODE_KEY_REPLY, MODE_LABEL_REPLY, const.MESSAGE_TYPE_PAGE,
                 f"{CmdPage.key}/{PAGE_REPLY_SWITCH} ")


def _channel_mode(channel) -> dict:
    """The mode that sends to one Evennia channel.

    The prefix comes from the nick replacement of the channel class, the
    same string that Evennia uses when a player types `pub hello`. Thus, a
    channel class that changes its command changes this prefix too.
    """
    replacement = channel.channel_msg_nick_replacement.format(
        channelname=channel.key)
    prefix = replacement.partition(_NICK_MESSAGE_ARGUMENT)[0]

    return _mode(MODE_KEY_CHANNEL_PREFIX + channel.key.lower(), channel.key,
                 const.MESSAGE_TYPE_CHANNEL, prefix)


def _channels_of(account) -> list:
    """The channels that the account listens to and can send to, by key."""
    from evennia.comms.models import ChannelDB

    subscribed = ChannelDB.objects.get_subscriptions(account)
    usable = [channel for channel in subscribed
              if channel.access(account, "send")]

    usable.sort(key=lambda channel: channel.key.lower())

    return usable


# ─── Public interface ────────────────────────────────────────────────────────

def chat_modes(observer) -> list:
    """
    Purpose: List the chat modes of a character, in the order that a client
    offers them.

    Entry:
        observer - the puppeted Character. One with no account gets the
                   speech modes only, because page and channels belong to an
                   account.

    Exit/Returns:
        Returns a list of {key, label, type, prefix} rows.

    Module Globals:
        None.

    Methodology:
        Say and Yell first, because they need no account. Then reply, then
        each channel that the account listens to and has the `send` lock for.
        A channel that the player cannot send to is not a mode, because each
        line would get a refusal.

    Notes/References:
        The client adds the typed text to `prefix` and sends it verbatim.

    Author: Nick Hobar
    Creation date: 09/29/2026
    """
    rows = _speech_modes()
    account = getattr(observer, "account", None)

    if account is None:
        return rows

    rows.append(_reply_mode())
    rows.extend(_channel_mode(channel) for channel in _channels_of(account))

    return rows


def build_payload(observer) -> CharChatPayload:
    """
    Purpose: Build the chat modes of the observer as one snapshot.

    Entry:
        observer - the puppeted Character.

    Exit/Returns:
        Returns a CharChatPayload.

    Module Globals:
        None.

    Methodology:
        The speaker is the key of the character, the name that `say` shows
        to the room.

    Notes/References:
        Sent on CHANNEL_CHAR_CHAT.

    Author: Nick Hobar
    Creation date: 09/29/2026
    """
    payload = CharChatPayload(speaker=observer.key, modes=chat_modes(observer))

    return payload
