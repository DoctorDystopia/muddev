"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/08/2026
Description: Tests for which dialogue module an NPC speaks from, and for the
             stale-path failure that made the code the owner of that path.

The dialogue module was a db attribute, stamped once at at_object_creation,
until 09/08/2026. The repo-wide directory reorganization moved every menu
under systems/interface/ and updated the constants in typeclasses/npcs.py with
it -- but every shopkeep already standing on the grid kept the row it was
stamped with, naming `systems.menus.npc_dialogues.npc_shopkeep`. `talk` handed
that path to EvMenu, mod_import returned None, and _parse_menudata read
__dict__ off it: an untrapped AttributeError at whoever typed the verb.

An import path in a database row is one no rename can reach. Since 10/09/2026
the NpcDef names the dialogue. These tests hold the two halves of the fix:
the def wins over the row, and a path that names nothing is refused rather
than tracebacked. world/tests/test_npc_database.py checks that each def names
a module that imports.
"""

from evennia import create_object
from evennia.utils.test_resources import EvenniaTest

from typeclasses.npcs import TalkativeNPC, _dialogue_module_for
from world.npc_database import NPC_DB

# A path in the shape the reorganization left behind: importable-looking,
# stamped into a live row, naming a module that has since moved.
STALE_DIALOGUE_PATH = "systems.menus.npc_dialogues.npc_shopkeep"

# The NpcDefs these tests stand up.
_SHOPKEEP_KEY = "shopkeeper_oasis"
_ANDROID_KEY = "lone_android"


class TestDialogueModuleResolution(EvenniaTest):
    """What an NPC speaks from, and which source wins."""

    def test_the_def_beats_a_stale_persisted_path(self):
        """The bug, exactly: a shopkeep stamped before the directory move.

        Reading the row first would leave every such NPC broken forever,
        because nothing rewrites it and no rename can reach it.
        """
        shopkeep = NPC_DB[_SHOPKEEP_KEY].create(location=self.room1)
        shopkeep.db.menu_module = STALE_DIALOGUE_PATH

        speaks_from = _dialogue_module_for(shopkeep)

        self.assertEqual(speaks_from, NPC_DB[_SHOPKEEP_KEY].dialogue_module())

    def test_a_plain_npc_may_still_name_its_module_in_a_row(self):
        """The fallback is what a prototype or a script-built NPC uses.

        A one-off talker with no def has nowhere else to declare, so
        db.menu_module stays a supported way to name a dialogue module -- it
        just no longer shadows a def that names one.
        """
        npc = create_object(TalkativeNPC, key="test talker", location=self.room1)
        android_module = NPC_DB[_ANDROID_KEY].dialogue_module()
        npc.db.menu_module = android_module

        speaks_from = _dialogue_module_for(npc)

        self.assertEqual(speaks_from, android_module)

    def test_an_npc_with_nothing_to_say_resolves_to_nothing(self):
        """CmdTalk's own guard reads this, so None has to survive the lookup."""
        npc = create_object(TalkativeNPC, key="test mute", location=self.room1)

        speaks_from = _dialogue_module_for(npc)

        self.assertFalse(speaks_from)

    def test_the_dialogue_module_is_not_persisted(self):
        """Read from the def, or the migration has to be run again next move."""
        shopkeep = NPC_DB[_SHOPKEEP_KEY].create(location=self.room1)

        persisted = shopkeep.attributes.get("menu_module", default=None)

        self.assertFalse(persisted)


class TestTalkingWithAStalePath(EvenniaTest):
    """`talk` itself, end to end, on the NPC the reorganization broke."""

    def test_talking_to_a_stale_shopkeep_opens_the_menu(self):
        """The reported traceback, as a test: talk to it and get a menu."""
        shopkeep = NPC_DB[_SHOPKEEP_KEY].create(location=self.room1)
        shopkeep.db.menu_module = STALE_DIALOGUE_PATH

        self.char1.execute_cmd("talk", session=self.session)

        self.assertTrue(self.char1.ndb._evmenu)

        self.char1.ndb._evmenu.close_menu()
