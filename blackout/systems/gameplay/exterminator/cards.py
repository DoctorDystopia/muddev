"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: The cards of the open offer, as the player sees them.

             Three readers share this module: the task pop-up, the `task`
             text, and the pick menu. Thus, the three cannot describe a card
             differently. Each card carries its whole command, `task pick
             <n>`, and its conflict warnings. DESIGN-0012, Phase 4.
"""

from dataclasses import dataclass

from systems.gameplay.exterminator import constants
from systems.gameplay.exterminator.conflicts import seam_conflicts



@dataclass(frozen=True)
class CardView:
    """
    One card of the open offer, ready to show.

    number      - the 1-based number that `task pick` takes.
    buff_key    - the key of the buff.
    name        - the display name of the buff.
    rarity      - the key of the rarity, one of constants.RARITIES.
    rarity_name - the display name of the rarity.
    description - what the buff does.
    warnings    - one line for each seam conflict.
    command     - the whole command that picks this card.
    """

    number: int
    buff_key: str
    name: str
    rarity: str
    rarity_name: str
    description: str
    warnings: tuple
    command: str



def _warning_line(conflict) -> str:
    """One conflict as a line for the player."""
    seam = constants.SEAM_LABELS.get(conflict.seam, conflict.seam)
    template = constants.MSG_CONFLICT_WINS if conflict.buff_wins else constants.MSG_CONFLICT_LOSES

    return template.format(seam=seam, rival=conflict.rival_name)



def card_views(character) -> list:
    """
    Purpose: Give each card of the open offer as a CardView.

    Entry:
        character has an `exterminator` handler.

    Exit/Returns:
        Returns a list of CardView, in offer order. Empty when no offer is
        open. A card whose buff is not in the registry is skipped.

    Module Globals:
        BUFF_REGISTRY, constants.RARITY_NAMES read.

    Methodology:
        1. Read the offer from the handler.
        2. Find each buff, and read its seam conflicts for this character.
        3. Build the view, with the name from the pool of the Preceptor,
           the description at the rarity of the card, and `task pick <n>`.

    Notes/References:
        The registry import is local, because the buff registry imports the
        combat rules package.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """
    from systems.gameplay.exterminator.buffs import BUFF_REGISTRY, buff_name

    handler = character.exterminator
    preceptor_key = handler.preceptor_key()
    views = []

    for number, card in enumerate(handler.offer(), start=1):
        buff = BUFF_REGISTRY.get(card[constants.CARD_KEY])

        if buff is None:
            continue

        conflicts = seam_conflicts(buff, character)
        warnings = tuple(_warning_line(conflict) for conflict in conflicts)
        rarity = card[constants.CARD_RARITY]

        views.append(CardView(
            number=number,
            buff_key=buff.key,
            name=buff_name(buff, preceptor_key),
            rarity=rarity,
            rarity_name=constants.RARITY_NAMES.get(rarity, rarity),
            description=buff.describe(rarity, character),
            warnings=warnings,
            command=f"{constants.TASK_PICK_COMMAND} {number}",
        ))

    return views


def card_lines(character) -> list:
    """
    Purpose: Give the open offer as lines of text, for `task` and the menu.

    Entry:
        character has an `exterminator` handler.

    Exit/Returns:
        Returns a list of strings. Empty when no offer is open. Each card is
        one line, then one line for each warning.

    Module Globals:
        constants.MSG_CARD_LINE read.

    Methodology:
        Reads card_views, so the text matches the pop-up.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """
    lines = []

    for view in card_views(character):
        card_line = constants.MSG_CARD_LINE.format(
            index=view.number, name=view.name, rarity=view.rarity_name,
            description=view.description)
        lines.append(card_line)

        for warning in view.warnings:
            lines.append(f"   {warning}")

    return lines
