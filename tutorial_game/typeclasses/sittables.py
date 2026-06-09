


from typeclasses.objects import Object
from commands.sittables import CmdSetSit



class Sittable(Object):

    # def at_object_creation(self):
    #     self.cmdset.add_default(CmdSetSit)


    def do_sit(self, sitter):
        """
        Called when trying to sit on/in an object. This is a good place to check for things like:
        "is the chair broken?" or "is the bed too small for you?".
        
        Args:
            sitter (Object): The object (Character) trying to sit on this object.
        """

        preposition = self.db.preposition or "on"
        current = self.db.sitter

        if current:
            if current == sitter:
                sitter.msg(f"You are already sitting {preposition} {self.key}.")
            else:
                sitter.msg(f"You can't sit {preposition} {self.key}. It is already occupied by {current.key}.")
            return
        
        self.db.sitter = sitter
        sitter.db.is_sitting = self

        sit_msg = self.db.msg_sitting_down or f"You sit {preposition} {self.key}."
        sitter.msg(sit_msg)


    def do_stand(self, stander):
        """
        Called when trying to stand up from an object. This is a good place to check for things like:
        "are you actually sitting on this object?" or "is there something preventing you from standing up?".
        
        Args:
            stander (Object): The object (Character) trying to stand up from this object.
        """

        preposition = self.db.preposition or "on"
        current = self.db.sitter

        if not stander == current:
            stander.msg(f"You are not sitting {preposition} {self.key}.")
        else:
            self.db.sitter = None
            del stander.db.is_sitting

            stand_msg = self.db.msg_standing_up or f"You stand up from {self.key}."
            stander.msg(stand_msg)