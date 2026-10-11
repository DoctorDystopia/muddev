"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/09/2026
Description: NpcDefined, the mixin of every NPC typeclass that reads its
             facts from its NpcDef.

             An NPC stores one fact: db.npc_key. Its description, its model,
             its dialogue and its role data come from the NpcDef that the key
             names, read live on each use. Thus, an edit to a def reaches the
             NPCs that already stand in the world, with no tile sync and no
             migration. CLAUDE.md, "An import path belongs in the code, never
             in a database row", gives the reason.

             An NPC with no def (a test object, or a hand-built NPC) falls
             back to its class: `fallback_asset_key` and the inherited
             description.
"""


class NpcDefined:
    """
    Purpose: Give an NPC typeclass its NpcDef, and read its facts from it.

    Entry:
        A typeclass that lists this mixin before DefaultObject, so its
        get_display_desc runs first.

    Exit/Returns:
        Not applicable. A mixin.

    Module Globals:
        None.

    Methodology:
        Each read imports world.npc_database inside the routine.
        world.npc_database imports Evennia's create_object, and the def
        modules import system constants. A module-level import here would
        load all of it with the typeclass layer.

    Notes/References:
        world/npc_database.py, npc_def_of.

    Author: Nick Hobar
    Creation date: 10/09/2026
    """

    # The model of an NPC with no def. A role overrides it.
    fallback_asset_key = "talkative_npc"


    @property
    def npc_def(self):
        """The NpcDef that db.npc_key names, or None."""
        from world.npc_database import npc_def_of

        return npc_def_of(self)


    @property
    def asset_key(self) -> str:
        """The model record key, from the def, else the class fallback."""
        npc_def = self.npc_def

        if npc_def is None:
            return self.fallback_asset_key

        return npc_def.resolved_asset_key()


    def get_display_desc(self, looker, **kwargs) -> str:
        """
        Purpose: Give the description that `look` shows.

        Entry:
            looker is the object that looks.

        Exit/Returns:
            Returns the desc of the def. Returns the inherited description
            for an NPC with no def, or a def with no desc.

        Module Globals:
            None.

        Methodology:
            The def wins over db.desc. Until 10/09/2026 each spawner stamped
            db.desc on each tile sync, and three places held three different
            texts for the shopkeep. A stamp that a def overrides cannot go
            stale.

        Notes/References:
            DefaultObject.get_display_desc, which return_appearance calls.

        Author: Nick Hobar
        Creation date: 10/09/2026
        """
        npc_def = self.npc_def

        if npc_def is not None and npc_def.desc:
            return npc_def.desc

        return super().get_display_desc(looker, **kwargs)


    def refresh_from_def(self) -> None:
        """
        Purpose: Bring the row of this NPC in step with its def, at a tile
                 sync.

        Entry:
            No conditions.

        Exit/Returns:
            Returns nothing.

        Module Globals:
            None.

        Methodology:
            Only the object key needs this. Evennia stores the key in a
            database field, and a search, `look`, and the client all read the
            field. A role with more upkeep (the shop cmdset of a shopkeep)
            extends this method.

        Notes/References:
            typeclasses/npc_spawners.py calls this on each tile sync.

        Author: Nick Hobar
        Creation date: 10/09/2026
        """
        npc_def = self.npc_def

        if npc_def is not None and self.key != npc_def.name:
            self.key = npc_def.name
