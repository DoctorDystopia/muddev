"""
Characters

Characters are (by default) Objects setup to be puppeted by Accounts.
They are what you "see" in game. The Character class in this module
is setup to be the "default" character type created by the default
creation commands.

"""

from evennia import DefaultCharacter

from .objects import ObjectParent

import random


class Character(ObjectParent, DefaultCharacter):
    """
    The Character just re-implements some of the Object's methods and hooks
    to represent a Character entity in-game.

    See mygame/typeclasses/objects.py for a list of
    properties and methods available on all Object child classes like this.
    """

    def at_object_creation(self):
        self.db.strength = random.randint(3,18)
        self.db.dexterity = random.randint(3,18)
        self.db.intelligence = random.randint(3,18)


    def at_pre_move(self, destination, **kwargs):
        """
        Called by self.move_to when trying to move somewhere.
        If this returns False, the move is cancelled.
        This is a good place to check for things like:
          "is the door locked?" or "is the character too weak to move this heavy object?".
        """

        if self.db.is_sitting:
            self.msg("You need to stand up before you can move.")
            return False
        
        return True


    def get_stats(self):
        """
        Get the main stats of this character.
        """

        str = self.db.strength
        dex = self.db.dexterity
        int = self.db.intelligence

        return print(f"Strength: {str}, Dexterity: {dex}, Intelligence: {int}")

    pass
