"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: The interface every summary panel implements.
"""


class BasePanel:
    """
    Purpose: Contract for one band of the player summary screen.

    Entry:
        Subclasses set `key`, `title` and `order`, and override `render`.
        `data` is optional but strongly encouraged -- see Methodology.

    Exit/Returns:
        Not applicable -- a base class.

    Module Globals:
        None.

    Methodology:
        Panels are pure READERS. A panel must never write to the character,
        and must never persist a number of its own: every value on the dossier
        is fetched live from the handler that owns it. That is what stops this
        screen from becoming a second, staler copy of the game state. Combat
        level is the model -- it is computed on every read from skill levels,
        so there is nothing to keep in sync.

        Two output methods, deliberately:

          render(character) -> list of display lines, for the telnet screen.
          data(character)   -> plain JSON-safe dict, for a graphical client.

        Both are built from the same handler reads in the same module, which is
        the same discipline systems/interface/statefeed/ applies to combat: the prose and
        the structured feed cannot drift because neither is derived from the
        other. `data` has no consumer yet -- the `char_summary` channel is
        phase 2 -- but writing it alongside `render` costs a few lines now and
        avoids re-deriving all six panels later.

        Class methods rather than instances: a panel holds no state, so there
        is nothing for an instance to carry.

    Notes/References:
        Mirrors skill_defs/base_skill.py, which is the same shape for the same
        reason (auto-discovered class-attribute definitions).

    Author: Nick Hobar
    Creation date: 08/08/2026
    """

    # Registry key. Must be unique across panel_defs/ and must be set --
    # registry.py skips any subclass still carrying the placeholder below.
    key: str = ""

    # Plain-text heading rendered above the panel's rows. An empty title means
    # the panel draws no heading at all, which is how the identity band gets to
    # be the screen's title bar instead of a section like the others.
    title: str = ""

    # Sort position. See constants.PANEL_ORDER_* for the assigned values.
    order: int = 0

    # There is no `public` flag. Until 09/18/2026 a panel declared whether
    # another player could read it, and `profile` showed a narrower view. The
    # game now treats the whole dossier as public, so `profile <name>` renders
    # every panel through `render`. A panel that must stay private needs a
    # viewer argument, and no panel has a reason for one yet.


    @classmethod
    def render(cls, character: object) -> list:
        """
        Purpose: Build this panel's display lines for `character`.

        Entry:
            character is a Character with its handlers available.

        Exit/Returns:
            Returns a list of display strings, WITHOUT the section heading --
            service.py draws that from `title`. An empty list means the panel
            has nothing to show and is skipped entirely, heading included.

        Module Globals:
            None.

        Methodology:
            Subclass responsibility. Draw every row through layout.py.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        return []


    @classmethod
    def data(cls, character: object) -> dict:
        """
        Purpose: Build this panel's values as plain JSON-safe types.

        Entry:
            character is a Character with its handlers available.

        Exit/Returns:
            Returns a dict of plain values. No Evennia objects, no SaverDict,
            no Decimal -- the same constraint systems/interface/statefeed/payloads.py
            documents, because that is where this output is headed.

        Module Globals:
            None.

        Methodology:
            Subclass responsibility. Default is an empty dict so a panel that
            has not implemented it yet contributes nothing rather than raising.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        return {}
