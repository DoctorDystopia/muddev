"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: QuestRegistry — auto-discovers quest blueprints from the
             content package.
"""

# systems/quests/loader.py



import importlib
import pkgutil
from evennia.utils import logger
import systems.quests.content as content_package



class QuestRegistry:
    """
    A unified, global registry that automatically discovers and caches 
    all quest blueprints inside the content/ package directory.
    """

    def __init__(self):
        self._blueprints = {}
        self.load_all_quests()


    def load_all_quests(self):
        """
        Walks the content directory and loads all 'QUESTS' arrays.
        """

        self._blueprints.clear()
        
        # Walk through all submodules inside systems.quests.content
        for _, module_name, is_pkg in pkgutil.iter_modules(content_package.__path__):
            if is_pkg:
                continue
                
            full_module_path = f"systems.quests.content.{module_name}"
            try:
                module = importlib.import_module(full_module_path)
                
                # Look for the standard QUESTS variable in the imported module
                if hasattr(module, "QUESTS"):
                    for quest in module.QUESTS:
                        if quest.key in self._blueprints:
                            logger.log_err(f"[QUEST ERROR] Duplicate quest key detected: '{quest.key}' in {module_name}")
                            continue

                        self._blueprints[quest.key] = quest
                
            except Exception as e:
                logger.log_trace(f"[QUEST ERROR] Failed to load quest module {full_module_path}: {e}")

        logger.log_info(f"[QUEST REGISTRY] Successfully initialized {len(self._blueprints)} game quests.")


    def get(self, quest_key):
        """
        Retrieves a cached blueprint safely by its unique string ID.
        """

        return self._blueprints.get(quest_key)


# Global Singleton instance to point to across your game server
GLOBAL_QUEST_REGISTRY = QuestRegistry()