"""
Monsters
"""



class Monster:
    """
    base class for monsters.
    """
    key = "Monster"

    def __init__(self, key):
        self.key = key

    def move_around(self):
        print(f"{self.key} is moving around!")



class Dragon(Monster):
    """
    A dragon. Dragons are large, powerful, and fire-breathing.
    """
    key = "Dragon"

    def move_around(self):
        super().move_around()
        print("the world trembles")

    def fire_breath(self):
        """
        Let the dragon breathe fire!
        """
        print(f"{self.key} breathes fire!")