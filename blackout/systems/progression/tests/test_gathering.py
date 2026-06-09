"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/05/2026
Description: Test harness for generic gathering commands and progression.
"""



from evennia.utils.test_resources import EvenniaCommandTest
from evennia import create_object 
from typeclasses.objects import DefaultObject

from typeclasses.gathering_nodes import RustyPole
from systems.progression.skills.handler import SkillHandler
from commands.gathering_cmds import CmdCutNode, CUTTING_SKILL_KEY



# Public constant definitions
_STARTING_XP = 0
_EXPECTED_XP = 10



class TestCuttingProgression(EvenniaCommandTest):

    def setUp(self) -> None:
        parent_class = super()
        parent_class.setUp()
        
        char_obj = getattr(self, "char1", self.char1)
        room_obj = getattr(self, "room1", self.room1)
        
        char_obj.db.has_cutting_reward = True
        self.handler = SkillHandler(char_obj)
        
        axe_obj = create_object(DefaultObject, key="axe", location=char_obj)
        self.axe = axe_obj
        
        pole_obj = create_object(RustyPole, key="rusty pole", location=room_obj)
        self.pole = pole_obj


    def test_cut_rusty_pole_success(self) -> None:
        char_obj = self.char1
        handler = self.handler
        pole_obj = self.pole
        
        # Inject the full base dictionary for the skill, setting the level to 1
        char_obj.db.skills[CUTTING_SKILL_KEY] = {"level": 1, "xp": _STARTING_XP}
        
        # FIX: Dynamically store the historical XP (which evaluates to 80)
        initial_xp = handler.get_total_xp(CUTTING_SKILL_KEY)
        
        response = self.call(
            CmdCutNode(),        
            " rusty pole",       
            cmdstring="cut",     
            caller=char_obj,     
            obj=pole_obj         
        )
        
        print(f"\n[TEST OUTPUT - SUCCESS]: {response}")
        expected_response = "You begin cutting"
        self.assertIn(expected_response, response)
        
        # FIX: Verify the new total XP equals the initial XP plus the 10 XP reward
        new_xp = handler.get_total_xp(CUTTING_SKILL_KEY)
        expected_total = initial_xp + _EXPECTED_XP
        is_expected = (new_xp == expected_total)
        
        self.assertTrue(is_expected)


    def test_cut_level_requirement_fail(self) -> None:
        char_obj = self.char1
        pole_obj = self.pole
        
        pole_obj.db.required_level = 99
        
        # Apply the exact same formatting and instantiation here
        response = self.call(
            CmdCutNode(),
            " rusty pole",
            cmdstring="cut",
            caller=char_obj,
            obj=pole_obj
        )

        print(f"\n[TEST OUTPUT - FAIL]: {response}")
        expected_error = "You need a Cutting level of 99 to cut this."
        self.assertIn(expected_error, response)