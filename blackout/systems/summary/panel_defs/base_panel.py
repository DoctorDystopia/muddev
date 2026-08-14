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
        the same discipline systems/statefeed/ applies to combat: the prose and
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

    # Heading for the public view, when narrowing the panel's content also
    # changes what the band honestly IS. Empty means "reuse `title`", which is
    # the right answer for most panels. Vitals is the case that needs it: with
    # hitpoints and combat state removed, what remains is progression standing,
    # and a heading reading "VITALS" over three level totals is a small lie.
    public_title: str = ""

    # Sort position. See constants.PANEL_ORDER_* for the assigned values.
    order: int = 0

    # Whether this panel appears at all in another player's view of this
    # character. Defaults to False so a NEW panel is private until its author
    # decides otherwise -- the safe direction for a flag that gates what
    # strangers can read about you.
    public: bool = False


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
    def render_public(cls, character: object) -> list:
        """
        Purpose: Build this panel's display lines for someone ELSE looking at
        `character`.

        Entry:
            character is the Character being looked at, not the viewer.

        Exit/Returns:
            Returns a list of display strings, same contract as render.

        Module Globals:
            None.

        Methodology:
            Defaults to the full render. Two separate controls, because
            "should strangers see this band at all" and "how much of it should
            they see" are different questions and collapsing them into one flag
            forces every partly-public panel to be all or nothing:

              public = False        -> the band never appears. Holdings.
              public = True, no
                override            -> strangers see exactly what you see.
                                       Identity, Skills.
              public = True, with
                an override         -> strangers see a subset. Vitals shows
                                       combat level but not current HP; World
                                       shows playtime but not where you are
                                       standing.

            A panel is only reachable here when `public` is True, so an
            override is about narrowing content, never about access.

        Notes/References:
            OSRS makes the same split: combat level and skill levels are public
            on the hiscores and above a player's head, current hitpoints are
            not.

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        lines = cls.render(character)

        return lines


    @classmethod
    def data(cls, character: object) -> dict:
        """
        Purpose: Build this panel's values as plain JSON-safe types.

        Entry:
            character is a Character with its handlers available.

        Exit/Returns:
            Returns a dict of plain values. No Evennia objects, no SaverDict,
            no Decimal -- the same constraint systems/statefeed/payloads.py
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
