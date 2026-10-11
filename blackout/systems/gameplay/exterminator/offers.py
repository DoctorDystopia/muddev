"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: The pick milestones and the draw of an offer, as plain
             functions. ExterminatorHandler calls them and stores the
             result. Nothing here reads or writes a character.

             DESIGN-0012, Phase 4. Nick, 10/06/2026: the count of pick
             milestones is one constant, the picks come at 0%, 33%, and 66%,
             and each card rolls a rarity that sets the strength of the buff.
"""

from systems.gameplay.exterminator import constants
from systems.gameplay.exterminator.conflicts import contested_seams



# ─── Public routines ────────────────────────────────────────────────────────

def picks_due(kills: int, total: int, milestone_count: int) -> int:
    """
    Purpose: Count the pick milestones that a task progress reaches.

    Entry:
        kills >= 0. total >= 1. milestone_count >= 0.

    Exit/Returns:
        Returns the count of milestones i, from 0 to milestone_count - 1,
        with kills * milestone_count >= i * total.

    Module Globals:
        None.

    Methodology:
        Integer math, never a float 1/3. Milestone 0 is due at 0 kills, so a
        new task has one pick at once. A task smaller than the milestone
        count makes several milestones due on one kill.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """
    due = 0

    for milestone in range(milestone_count):
        if kills * milestone_count >= milestone * total:
            due += 1

    return due


def roll_rarity(rng) -> str:
    """Draw one rarity by RARITY_WEIGHTS."""
    rarities = list(constants.RARITIES)
    weights = [constants.RARITY_WEIGHTS[rarity] for rarity in rarities]
    drawn = rng.choices(rarities, weights=weights)

    return drawn[0]


def _blocked_seams(held_keys, registry) -> frozenset:
    """Every seam that a held buff owns, without the modifier seam."""
    blocked = set()

    for held_key in held_keys:
        held = registry.get(held_key)

        if held is not None:
            blocked |= contested_seams(held)

    return frozenset(blocked)


def _candidates(pool, held_keys, registry) -> list:
    """
    The pool entries that an offer can show: a known buff, not held, and
    with no seam that a held buff owns.
    """
    blocked = _blocked_seams(held_keys, registry)
    candidates = []

    for entry in pool:
        buff = registry.get(entry.buff_key)

        if buff is None or entry.buff_key in held_keys:
            continue

        if contested_seams(buff) & blocked:
            continue

        candidates.append(entry)

    return candidates


def draw_offer(pool, held_keys, card_count: int, registry, rng) -> list:
    """
    Purpose: Draw the cards of one offer.

    Entry:
        pool is a tuple of PoolEntry. held_keys is the tuple of held buff
        keys. card_count >= 0. registry is BUFF_REGISTRY. rng is a
        random.Random.

    Exit/Returns:
        Returns a list of card dicts {CARD_KEY, CARD_RARITY}, at most
        card_count long. Empty when no entry can show.

    Module Globals:
        None.

    Methodology:
        1. Keep the entries that can show (see _candidates).
        2. Draw one entry by weight, with no repeat, until the offer is full
           or no entry is left.
        3. Roll a rarity for each card.

    Notes/References:
        A buff on a seam that a held buff owns does not show. A buff that
        clashes only with a weapon still shows, with its warning (Nick,
        10/06/2026).

    Author: Nick Hobar
    Creation date: 10/06/2026
    """
    left = _candidates(pool, held_keys, registry)
    cards = []

    while left and len(cards) < card_count:
        weights = [entry.weight for entry in left]
        draws = rng.choices(left, weights=weights)
        drawn = draws[0]
        left.remove(drawn)
        rarity = roll_rarity(rng)
        cards.append({constants.CARD_KEY: drawn.buff_key, constants.CARD_RARITY: rarity})

    return cards
