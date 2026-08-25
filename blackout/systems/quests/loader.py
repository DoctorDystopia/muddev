"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: QuestRegistry -- auto-discovers quest blueprints from the
             content package.
"""

import importlib
import pkgutil

from evennia.utils import logger

import systems.quests.content as content_package



# Private constant definitions

# The module-level list each content module exposes for discovery.
_QUESTS_ATTRIBUTE = "QUESTS"



class QuestRegistry:
    """
    Purpose: The single catalog of every quest that exists in the game,
             discovered by walking systems/quests/content/.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        _QUESTS_ATTRIBUTE read.

    Methodology:
        Package auto-discovery, the same pattern as
        systems/progression/skills/registry.py: adding a quest means adding
        one file under content/ that declares a module-level QUESTS list.
        There is no dispatch chain to edit and no settings entry to add.

    Notes/References:
        This module must never be imported at the scope of
        systems/quests/quests.py -- see the note at the head of that file.

    Author: Nick Hobar
    Creation date: 07/13/2026
    """

    def __init__(self) -> None:
        self._blueprints = {}
        self.load_errors = []
        self.load_all_quests()


    def load_all_quests(self) -> None:
        """
        Purpose: Import every content module and cache the quests it declares.

        Entry:
            No conditions.

        Exit/Returns:
            No conditions. Populates self._blueprints and self.load_errors.

        Module Globals:
            _QUESTS_ATTRIBUTE read.

        Methodology:
            A module that fails to import is logged at ERROR and recorded in
            load_errors rather than only trace-logged. The distinction is the
            whole point: a swallowed ImportError here is invisible in play but
            leaves the registry empty, and the quest test suite asserts
            load_errors is empty so the failure surfaces as a red test rather
            than as a player unable to accept a quest.

            The server still comes up with the surviving quests -- one broken
            content file must not be a startup failure.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        self._blueprints.clear()
        self.load_errors.clear()

        for _finder, module_name, is_pkg in pkgutil.iter_modules(content_package.__path__):
            if is_pkg:
                continue

            module_path = f"{content_package.__name__}.{module_name}"
            self._load_module(module_path)

        logger.log_info(
            f"[QUEST REGISTRY] Initialized {len(self._blueprints)} quests "
            f"({len(self.load_errors)} module(s) failed)."
        )


    def _load_module(self, module_path: str) -> None:
        """
        Purpose: Import one content module and register its blueprints.

        Entry:
            module_path is a fully-qualified dotted module path.

        Exit/Returns:
            No conditions. Appends to self.load_errors on failure.

        Module Globals:
            _QUESTS_ATTRIBUTE read.

        Methodology:
            A duplicate quest key is recorded as a load error too, not just
            logged: two content files claiming one key means one of them is
            silently absent from the game, which is exactly the class of
            failure this registry is supposed to make impossible.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        try:
            module = importlib.import_module(module_path)
        except Exception as exc:
            self.load_errors.append((module_path, repr(exc)))
            logger.log_err(f"[QUEST REGISTRY] Failed to import {module_path}: {exc!r}")
            return

        quests = getattr(module, _QUESTS_ATTRIBUTE, None)

        if not quests:
            return

        for blueprint in quests:
            if blueprint.key in self._blueprints:
                self.load_errors.append(
                    (module_path, f"duplicate quest key '{blueprint.key}'"))
                logger.log_err(
                    f"[QUEST REGISTRY] Duplicate quest key '{blueprint.key}' "
                    f"in {module_path}; keeping the first definition."
                )
                continue

            self._blueprints[blueprint.key] = blueprint


    def get(self, quest_key: str) -> object:
        """Retrieve a blueprint by key, or None if no such quest exists."""
        return self._blueprints.get(quest_key)


    def all(self) -> dict:
        """
        Purpose: Every registered blueprint, for tests and admin listings.

        Entry:
            No conditions.

        Exit/Returns:
            Returns a shallow dict copy keyed by quest key.

        Module Globals:
            None

        Methodology:
            Copied so a caller iterating the catalog cannot mutate it. The
            blueprints themselves are shared and must be treated as read-only;
            they hold no per-character state.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        return dict(self._blueprints)


    def keys(self) -> list:
        """The key of every registered quest."""
        return list(self._blueprints.keys())


    def __contains__(self, quest_key: str) -> bool:
        return quest_key in self._blueprints


    def __len__(self) -> int:
        return len(self._blueprints)



# Global singleton, shared across the server.
GLOBAL_QUEST_REGISTRY = QuestRegistry()
