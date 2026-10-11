"""
The dialogue modules of the NPCs. Each module is the EvMenu node tree of one
dialogue, and NpcDef.dialogue names it by its module name.

Nothing imports this package as a whole. CmdTalk gives the path of one
module to EvMenu when a player talks, so a module here loads only when it is
in use. world/tests/test_npc_database.py imports each module that a def
names, so a bad name fails a test and not a conversation.

A module here holds dialogue and its flow. A write to game state goes
through the owner of that state: QuestHandler for a quest,
systems/gameplay/shop/shop_service.py for a sale, and
systems/gameplay/exterminator/service.py for a task.

Generic EvMenu helpers stay in systems/interface/menus/: `dialogue.py` for
the NPC helpers and the default conversation, and `base_menu.py` for the
menu.
"""
