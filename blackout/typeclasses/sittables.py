


from typeclasses.objects import Object
from commands.sittables import CmdSetSit
from systems.statefeed import constants as feed_const

# Every line this module sends a player is about the room around you, so the
# routing tag is bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/statefeed/constants.py.
_MSG_ROOM = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_ROOM}



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
                sitter.msg(
                    (f"You are already sitting {preposition} {self.key}.", _MSG_ROOM))
            else:
                sitter.msg(
                    (f"You can't sit {preposition} {self.key}. It is already occupied by {current.key}.",
                     _MSG_ROOM))
            return
        
        self.db.sitter = sitter
        sitter.db.is_sitting = self

        sit_msg = self.db.msg_sitting_down or f"You sit {preposition} {self.key}."
        sitter.msg((sit_msg, _MSG_ROOM))


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
            stander.msg((f"You are not sitting {preposition} {self.key}.", _MSG_ROOM))
        else:
            self.db.sitter = None
            del stander.db.is_sitting

            stand_msg = self.db.msg_standing_up or f"You stand up from {self.key}."
            stander.msg((stand_msg, _MSG_ROOM))
