"""
Monsters
"""



from typeclasses.objects import Object



class Monster(Object):
    """
    base class for monsters.
    """

    def move_around(self):
        print(f"{self.key} is moving around!")



class Dragon(Monster):
    """
    A dragon. Dragons are large, powerful, and fire-breathing.
    """

    def move_around(self):
        super().move_around()
        print("the world trembles")

    def fire_breath(self):
        """
        Let the dragon breathe fire!
        """
        print(f"{self.key} breathes fire!")