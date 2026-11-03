"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The composer of the ability rail (DESIGN-0015, Phase 3). It
             puts the rows of each ability system after each other, in one
             fixed order: the auras, then the augments with their set row.

             The feed reads this module, and nothing else composes. Each
             telnet listing still reads its own detail module, because
             `aura` lists auras and `aug` lists augments. The rail shows
             both, so it reads the composer.

             A third ability system is one more line in ability_rows. The
             slot of a row is its index in the result, so the order here is
             the order of the keys on the client.
"""


def ability_rows(character) -> list:
    """
    Purpose: Every ability row of a character, in the order of the rail.

    Entry:
        character - the character.

    Exit/Returns:
        Returns one list: the aura rows, then the augment rows, then the
        set row. Every value survives json.dumps.

    Module Globals:
        None.

    Methodology:
        Imported inside the routine. Each detail module reads its handler
        module, and each handler module imports the statefeed, which reads
        this module through statefeed/abilities.py.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    from systems.gameplay.augmentation import detail as augment_detail
    from systems.gameplay.combat.auras import detail as aura_detail

    rows = []
    rows.extend(aura_detail.ability_rows(character))
    rows.extend(augment_detail.ability_rows(character))

    return rows
