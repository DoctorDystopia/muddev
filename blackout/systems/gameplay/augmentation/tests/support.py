"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: Shared helpers of the augmentation tests. Since Phase 5, the
             rail shows the socketed augments only, so a test that lights
             an augment through a command sockets it first.
"""

from systems.gameplay.augmentation import constants as aug_const
from systems.gameplay.augmentation import sockets
from systems.gameplay.progression.skills.constants import SKILL_KEY_AUGMENTATION


def open_every_socket(character) -> None:
    """Raise the Augmentation level of a character until every socket is open."""
    top = max(aug_const.SOCKET_UNLOCK_LEVELS.values())

    character.skills.set_level(SKILL_KEY_AUGMENTATION, top)


def one_of_each_group(augments) -> list:
    """The augments with at most one of each conflict group, in order. A
    test that lights every augment at once lights these, because a second
    light of a group puts the first out."""
    seen = set()
    kept = []

    for augment in augments:
        group = augment.conflict_group

        if group and group in seen:
            continue

        if group:
            seen.add(group)

        kept.append(augment)

    return kept


def socket_fitting(character, augments) -> list:
    """
    Purpose: Put each augment into the first open, empty socket that it
             fits, and skip the ones that fit nowhere.

    Entry:
        character has a skills handler.
        augments is an iterable of augment instances.

    Exit/Returns:
        Returns the augments that found a socket, in the order given.

    Module Globals:
        None.

    Methodology:
        Greedy, in the order of the sockets of each augment. The placement
        goes through sockets.place, so the test rig is a real rig.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    placed = []

    for augment in augments:
        for socket_key in augment.sockets:
            done, _message = sockets.place(character, augment, socket_key)

            if done:
                placed.append(augment)
                break

    return placed
