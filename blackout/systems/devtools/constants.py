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
    DIM_COLOR,
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

# The tag CATEGORY every staff item declares, and the thing that makes a staff
# item recognisable without importing its typeclass.
#
# It lives here rather than in world/item_defs/dev_tools.py because two very
# different modules need it and neither should own it: the ItemDef stamps it,
# and clear_inventory refuses to delete anything carrying it. A moderator
# emptying their OWN inventory would otherwise destroy the egg they were
# holding to do it with, and the only way back is a `py` call.
#
# Deliberately NOT one of statefeed's ITEM_FAMILIES -- the 3D pane falls an
# unknown family through to a generic mesh, which is right for an object no art
# was commissioned for.
DEV_TOOL_TAG_CATEGORY: str = "dev_tool"


# ─── Action vocabulary ───────────────────────────────────────────────────────

# Every moderator effect names itself here, and the audit line is built from
# that name. One table rather than a literal per call site, for the reason the
# quest system keeps QUEST_ACTIONS: a log you grep is only as good as the
# consistency of the verb you are grepping for, and "godmode" written by hand
# in four places becomes "god_mode" in one of them.
ACTION_SPAWN: str = "spawn"

# Its own verb rather than ACTION_SPAWN with a different detail. An item lands
# in a bag and a hostile lands in a ROOM, next to whoever is standing there --
# reviewing "what did staff put into the world" is a different question from
# "what did staff hand out", and one grep should answer each.
ACTION_SPAWN_NPC: str = "spawn_npc"

# Destroying a character's belongings. Its own verb because it is the only
# irreversible thing on the tool: a spawn can be purged and a level can be set
# back, but a deleted item is gone.
ACTION_CLEAR: str = "clear"

ACTION_GODMODE: str = "godmode"
ACTION_RESTORE: str = "restore"
ACTION_TELEPORT: str = "teleport"
ACTION_XP: str = "xp"
ACTION_LEVEL: str = "level"
ACTION_BOOT: str = "boot"
ACTION_BAN: str = "ban"
ACTION_UNBAN: str = "unban"

# One verb for every quest write, with the operation in the audit line's
# detail field -- "quest on Char: complete oasis_in_the_wastes". Same shape as
# ACTION_SPAWN, whose detail carries "3x hammer". Five separate verbs would
# make the vocabulary longer without making one grep any easier.
ACTION_QUEST: str = "quest"

# Reading someone's dossier is audited too. Who looked at whom is exactly the
# question a moderation review asks, and a read that leaves no trace is the
# one nobody can account for afterwards.
ACTION_INSPECT: str = "inspect"

MODERATOR_ACTIONS: frozenset = frozenset((
    ACTION_SPAWN,
    ACTION_SPAWN_NPC,
    ACTION_CLEAR,
    ACTION_GODMODE,
    ACTION_RESTORE,
    ACTION_TELEPORT,
    ACTION_XP,
    ACTION_LEVEL,
    ACTION_BOOT,
    ACTION_BAN,
    ACTION_UNBAN,
    ACTION_QUEST,
    ACTION_INSPECT,
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

# NPC spawn count. Two orders of magnitude below the item ceiling on purpose.
# Every hostile spawned is a live combatant that joins the tick, picks targets
# and swings, so the cost of a fat-fingered zero is not a wasted database row
# -- it is a room nobody in it can survive or leave.
MIN_NPC_SPAWN: int = 1
MAX_NPC_SPAWN: int = 20

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

MSG_SPAWN_NPC_UNKNOWN: str = (
    f"{ERROR_COLOR}No NPC '{{npc_key}}' exists in the NPC database."
    f"{RESET_COLOR}"
)

MSG_SPAWN_NPC_NOWHERE: str = (
    f"{ERROR_COLOR}{{target}} is nowhere -- there is no room to spawn into."
    f"{RESET_COLOR}"
)

MSG_SPAWN_NPC_DONE: str = (
    f"{SUCCESS_COLOR}Spawned{RESET_COLOR} {HIGHLIGHT_COLOR}{{quantity}}x "
    f"{{npc_name}}{RESET_COLOR} {SUCCESS_COLOR}in {{room}}.{RESET_COLOR}"
)

MSG_TELEPORT_NO_DESTINATION: str = (
    f"{ERROR_COLOR}{{other}} is nowhere -- there is nothing to teleport to."
    f"{RESET_COLOR}"
)

MSG_TELEPORT_ALREADY_THERE: str = (
    f"{HIGHLIGHT_COLOR}{{target}} is already in {{room}}.{RESET_COLOR}"
)

MSG_CLEAR_NOTHING: str = (
    f"{HIGHLIGHT_COLOR}{{target}} is carrying nothing to clear."
    f"{RESET_COLOR}"
)

MSG_CLEAR_DONE: str = (
    f"{SUCCESS_COLOR}Destroyed{RESET_COLOR} {HIGHLIGHT_COLOR}{{carried}} "
    f"carried{RESET_COLOR}{SUCCESS_COLOR} and{RESET_COLOR} "
    f"{HIGHLIGHT_COLOR}{{equipped}} equipped{RESET_COLOR}"
    f"{SUCCESS_COLOR} items from {{target}}.{RESET_COLOR}"
)

MSG_CLEAR_KEPT: str = (
    f"{HIGHLIGHT_COLOR}({{kept}} staff item(s) left alone.){RESET_COLOR}"
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


# ─── Quest messages ──────────────────────────────────────────────────────────

MSG_QUEST_UNKNOWN: str = (
    f"{ERROR_COLOR}No quest '{{quest_key}}' is in the registry.{RESET_COLOR}"
)

# The handler's write methods return a bare bool, so the egg has to say why a
# False came back. Each of these names the precondition that was not met,
# rather than a generic "that did not work" -- there are four of them and they
# are not interchangeable.
MSG_QUEST_NOT_ACTIVE: str = (
    f"{ERROR_COLOR}{{target}} is not on '{{quest_key}}'. Accept it first."
    f"{RESET_COLOR}"
)

MSG_QUEST_UNAVAILABLE: str = (
    f"{ERROR_COLOR}{{target}} cannot take '{{quest_key}}' -- already active, "
    f"already complete, or a prerequisite is unmet.{RESET_COLOR}"
)

MSG_QUEST_ALREADY_COMPLETE: str = (
    f"{ERROR_COLOR}{{target}} has already completed '{{quest_key}}'."
    f"{RESET_COLOR}"
)

MSG_QUEST_NOTHING_TO_RESET: str = (
    f"{ERROR_COLOR}{{target}} has no record of '{{quest_key}}'.{RESET_COLOR}"
)

MSG_QUEST_UNKNOWN_STEP: str = (
    f"{ERROR_COLOR}'{{quest_key}}' has no step named '{{step_key}}'."
    f"{RESET_COLOR}"
)

MSG_QUEST_ACCEPTED: str = (
    f"{SUCCESS_COLOR}{{target}} is now on{RESET_COLOR} "
    f"{HIGHLIGHT_COLOR}{{quest_key}}{RESET_COLOR}{SUCCESS_COLOR}.{RESET_COLOR}"
)

MSG_QUEST_ABANDONED: str = (
    f"{HIGHLIGHT_COLOR}Dropped '{{quest_key}}' for {{target}}. The completion "
    f"record, if any, is untouched.{RESET_COLOR}"
)

MSG_QUEST_COMPLETED: str = (
    f"{SUCCESS_COLOR}Completed '{{quest_key}}' for {{target}}. Rewards paid."
    f"{RESET_COLOR}"
)

MSG_QUEST_RESET: str = (
    f"{SUCCESS_COLOR}Reset '{{quest_key}}' for {{target}}. They may take it "
    f"again.{RESET_COLOR}"
)

MSG_QUEST_STEP_SET: str = (
    f"{SUCCESS_COLOR}{{target}} is now on step{RESET_COLOR} "
    f"{HIGHLIGHT_COLOR}{{step_key}}{RESET_COLOR}{SUCCESS_COLOR} of "
    f"'{{quest_key}}'.{RESET_COLOR}"
)


# ─── Inspect report ──────────────────────────────────────────────────────────

# The dossier systems/summary/ already renders is the body of the report. What
# follows it is the half a MODERATOR needs and a player does not: dbrefs to
# paste into a `py` call, who the account really is, and the itemised bag
# behind the dossier's "12 / 32".
INSPECT_STAFF_HEADING: str = f"{TITLE_COLOR}--- STAFF ---{RESET_COLOR}"

INSPECT_FIELD: str = f"{TITLE_COLOR}{{label}}:{RESET_COLOR} {{value}}"

INSPECT_LABEL_CHARACTER: str = "Character"
INSPECT_LABEL_ACCOUNT: str = "Account"
INSPECT_LABEL_PERMISSIONS: str = "Permissions"
INSPECT_LABEL_CONNECTED: str = "Connected"
INSPECT_LABEL_LOCATION: str = "Location"
INSPECT_LABEL_GODMODE: str = "God mode"
INSPECT_LABEL_CARRYING: str = "Carrying"
INSPECT_LABEL_QUESTS: str = "Quests"

INSPECT_NONE: str = f"{DIM_COLOR}(none){RESET_COLOR}"
INSPECT_NO_ACCOUNT: str = f"{DIM_COLOR}(unpuppeted){RESET_COLOR}"
INSPECT_SECTION_FAILED: str = (
    f"{ERROR_COLOR}(this section could not be rendered; see the server log)"
    f"{RESET_COLOR}"
)

# One carried item: "  4. rusty metal chunk (x12)  #1873".
INSPECT_ITEM_ROW: str = "  {slot}. {name}{stack} {dim}#{dbref}{reset}"
INSPECT_STACK_SUFFIX: str = " (x{quantity})"

# One quest: "  oasis_in_the_wastes  active  step=repel_raiders".
INSPECT_QUEST_ROW: str = "  {quest_key}  {status}  step={step_key}"
INSPECT_QUEST_OBJECTIVE: str = "      {line}"
INSPECT_NO_STEP: str = "-"
