"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: Test doubles for the quest engine -- a character-shaped object
             and a registry-shaped object, so the engine can be exercised
             without a database.
"""



class FakeDb:
    """
    Purpose: Stand in for an Evennia object's `.db` Attribute namespace.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        None

    Methodology:
        Any unset attribute reads as None, which is exactly what Evennia's
        AttributeHandler does and is what QuestHandler.__init__ relies on to
        detect a character that has never held a quest.

    Notes/References:
        Deliberately NOT a _SaverDict: these tests are about the engine's
        logic, not about persistence, and a plain dict makes an assertion
        failure readable.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """

    def __getattr__(self, name: str) -> object:
        # Only reached for attributes not in __dict__, so a value that has
        # been set is returned normally and never routed through here.
        return None



class FakeCharacter:
    """
    Purpose: The smallest object QuestHandler will accept -- a `.db` and a
             `.msg`.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        None

    Methodology:
        Collects every message sent to it so a test can assert on what the
        player was told. QuestHandler is the only part of the quest system
        that speaks to a player, and the announcements are part of its
        contract.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/25/2026
    """

    def __init__(self) -> None:
        self.db = FakeDb()
        self.messages = []


    def msg(self, text: str = "", **kwargs) -> None:
        """Record a message that would have gone to the player."""
        self.messages.append(str(text))


    def said(self, fragment: str) -> bool:
        """True if any message so far contains this fragment."""
        return any(fragment in message for message in self.messages)



class FakeRegistry:
    """
    Purpose: A quest registry holding exactly the blueprints a test declares.

    Entry:
        blueprints is an iterable of QuestBlueprint.

    Exit/Returns:
        No conditions.

    Module Globals:
        None

    Methodology:
        Patched over systems.quests.handler.GLOBAL_QUEST_REGISTRY so engine
        tests neither depend on nor disturb the real game content. Testing the
        engine against the shipped quests would mean every content edit could
        break an engine test.

    Notes/References:
        The real registry IS the subject of test_quest_registry.py; this
        double is for the engine tests only.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """

    def __init__(self, blueprints: list = None) -> None:
        self._blueprints = {bp.key: bp for bp in (blueprints or [])}


    def get(self, quest_key: str) -> object:
        return self._blueprints.get(quest_key)


    def all(self) -> dict:
        return dict(self._blueprints)


    def keys(self) -> list:
        return list(self._blueprints.keys())


    def __contains__(self, quest_key: str) -> bool:
        return quest_key in self._blueprints


    def __len__(self) -> int:
        return len(self._blueprints)
