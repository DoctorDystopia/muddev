"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: The one owner of every moderator-tool literal -- the attribute
             god mode is stored under, the action vocabulary the audit log
             speaks, the bounds each action clamps to, and the message
             templates the egg's menu prints.

             Imports systems/ui/colors.py and nothing else, so that actions.py
             may import this module while this module can never import back.
"""

from systems.ui.colors import (
    ERROR_COLOR,
    HIGHLIGHT_COLOR,
    RESET_COLOR,
    SUCCESS_COLOR,
    TITLE_COLOR,
)


# Public constant definitions

# ─── Persisted state ─────────────────────────────────────────────────────────

# The db Attribute god mode is stored under, ON THE CHARACTER -- not on the
# egg. A moderator who drops the egg, hands it over or logs out stays
# invulnerable until they turn it off. That is deliberate: the flag describes
# a character, and a protection that silently lapses when an item moves is one
# nobody can reason about mid-incident.
GODMODE_ATTR: str = "godmode"


# ─── Action vocabulary ───────────────────────────────────────────────────────

# Every moderator effect names itself here, and the audit line is built from
# that name. One table rather than a literal per call site, for the reason the
# quest system keeps QUEST_ACTIONS: a log you grep is only as good as the
# consistency of the verb you are grepping for, and "godmode" written by hand
# in four places becomes "god_mode" in one of them.
ACTION_SPAWN: str = "spawn"
ACTION_GODMODE: str = "godmode"
ACTION_RESTORE: str = "restore"
ACTION_TELEPORT: str = "teleport"
ACTION_XP: str = "xp"
ACTION_LEVEL: str = "level"
ACTION_BOOT: str = "boot"
ACTION_BAN: str = "ban"
ACTION_UNBAN: str = "unban"

MODERATOR_ACTIONS: frozenset = frozenset((
    ACTION_SPAWN,
    ACTION_GODMODE,
    ACTION_RESTORE,
    ACTION_TELEPORT,
    ACTION_XP,
    ACTION_LEVEL,
    ACTION_BOOT,
    ACTION_BAN,
    ACTION_UNBAN,
))

# Stamped on every audited line so one grep finds every moderator action taken
# on a server, across every effect and both the menu and any future command.
AUDIT_LOG_PREFIX: str = "[MODTOOL]"

# actor and target are both named because they are routinely different people,
# and an audit trail that records only the effect is not an audit trail.
AUDIT_LINE_TEMPLATE: str = "{prefix} {actor} -> {action} on {target}: {detail}"

# Stands in for the target half of an action that has no character target --
# a ban names an account by string, not an object in the room.
AUDIT_NO_TARGET: str = "(none)"


# ─── Bounds ──────────────────────────────────────────────────────────────────

# Spawn quantity. The ceiling only ever bites on a STACKABLE item, where the
# whole request becomes one object carrying a count; a non-stackable request
# is bounded far lower by the 32-slot inventory grid before it gets here. It
# exists so that a fat-fingered extra zero cannot turn into a database write
# the server has to be restarted to escape.
MIN_SPAWN_QUANTITY: int = 1
MAX_SPAWN_QUANTITY: int = 1000

# XP grant. Upward only -- a moderator lowering someone's progress wants
# ACTION_LEVEL, which sets a level outright and says so in the log, rather
# than a negative XP grant whose effect on the curve is not obvious.
MIN_XP_GRANT: int = 1
MAX_XP_GRANT: int = 10000000

# Where a map teleport lands. Both shipped maps define (0, 0) as their
# entrance tile, and world/respawn.py already anchors the death loop there --
# so this restates an existing convention rather than inventing a second one.
# _map_anchor_room degrades to any room on the map when a future map does not
# honour it, so the convention is a preference, not a requirement.
MAP_ANCHOR_XY: tuple = (0, 0)


# ─── Message templates ───────────────────────────────────────────────────────

MSG_NO_TARGET: str = f"{ERROR_COLOR}No such character is online.{RESET_COLOR}"

MSG_SPAWN_UNKNOWN_ITEM: str = (
    f"{ERROR_COLOR}No item '{{item_key}}' exists in the item database."
    f"{RESET_COLOR}"
)

MSG_SPAWN_NO_ROOM: str = (
    f"{ERROR_COLOR}{{target}} has no free inventory slot for that."
    f"{RESET_COLOR}"
)

MSG_SPAWN_DONE: str = (
    f"{SUCCESS_COLOR}Spawned{RESET_COLOR} {HIGHLIGHT_COLOR}{{quantity}}x "
    f"{{item_name}}{RESET_COLOR} {SUCCESS_COLOR}into {{target}}'s inventory."
    f"{RESET_COLOR}"
)

MSG_SPAWN_CLAMPED: str = (
    f"{HIGHLIGHT_COLOR}(Asked for {{asked}}; {{granted}} would fit.)"
    f"{RESET_COLOR}"
)

MSG_GODMODE_ON: str = (
    f"{SUCCESS_COLOR}God mode ON for {{target}}. Incoming damage is ignored."
    f"{RESET_COLOR}"
)

MSG_GODMODE_OFF: str = (
    f"{HIGHLIGHT_COLOR}God mode OFF for {{target}}. Damage applies normally."
    f"{RESET_COLOR}"
)

MSG_GODMODE_STATE_ON: str = f"{SUCCESS_COLOR}ON{RESET_COLOR}"
MSG_GODMODE_STATE_OFF: str = f"{HIGHLIGHT_COLOR}OFF{RESET_COLOR}"

MSG_RESTORE_DONE: str = (
    f"{SUCCESS_COLOR}Restored {{target}}: {{hp}}/{{max_hp}} HP, out of combat."
    f"{RESET_COLOR}"
)

MSG_TELEPORT_UNKNOWN_MAP: str = (
    f"{ERROR_COLOR}No map named '{{zcoord}}' is in the manifest.{RESET_COLOR}"
)

MSG_TELEPORT_NO_ROOM: str = (
    f"{ERROR_COLOR}Map '{{zcoord}}' has no rooms built. Run the map rebuild "
    f"script.{RESET_COLOR}"
)

MSG_TELEPORT_FAILED: str = (
    f"{ERROR_COLOR}The move to {{room}} failed; see the server log."
    f"{RESET_COLOR}"
)

MSG_TELEPORT_DONE: str = (
    f"{SUCCESS_COLOR}Teleported {{target}} to{RESET_COLOR} "
    f"{HIGHLIGHT_COLOR}{{room}}{RESET_COLOR}{SUCCESS_COLOR}.{RESET_COLOR}"
)

MSG_TELEPORT_ARRIVAL: str = (
    f"{TITLE_COLOR}The world folds, and you are somewhere else.{RESET_COLOR}"
)

MSG_UNKNOWN_SKILL: str = (
    f"{ERROR_COLOR}'{{skill_key}}' is not a skill in the registry."
    f"{RESET_COLOR}"
)

MSG_XP_DONE: str = (
    f"{SUCCESS_COLOR}Granted{RESET_COLOR} {HIGHLIGHT_COLOR}{{amount}} XP"
    f"{RESET_COLOR} {SUCCESS_COLOR}to {{target}}'s {{skill_key}}."
    f"{RESET_COLOR}"
)

MSG_LEVEL_DONE: str = (
    f"{SUCCESS_COLOR}Set {{target}}'s {{skill_key}} to level"
    f"{RESET_COLOR} {HIGHLIGHT_COLOR}{{level}}{RESET_COLOR}"
    f"{SUCCESS_COLOR}.{RESET_COLOR}"
)

MSG_ACCOUNT_NOT_NAMED: str = (
    f"{ERROR_COLOR}Name an account first.{RESET_COLOR}"
)

MSG_DELEGATED: str = (
    f"{HIGHLIGHT_COLOR}Running: {{command}}{RESET_COLOR}"
)


# ─── Delegated account commands ──────────────────────────────────────────────

# Booting and banning are NOT reimplemented here. Evennia already owns both,
# including the `server_bans` ServerConfig row the login path reads, and a
# second writer of that row is a second place for a ban to be wrong. These are
# the keys of the stock commands the egg types on the moderator's behalf; see
# actions.delegate_account_command.
ACCOUNT_COMMAND_BOOT: str = "boot"
ACCOUNT_COMMAND_BAN: str = "ban"
ACCOUNT_COMMAND_UNBAN: str = "unban"

# Both stock commands parse an optional reason after a colon:
# `ban thomas : griefing`.
ACCOUNT_REASON_SEPARATOR: str = ":"
