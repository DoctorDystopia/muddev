"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/14/2026
Description: Developer scripts that print tables and draw plots of game
             balance: combat maths, XP curves, and the rules map.

Run each script directly from blackout/, for example:
    ../evenv/Scripts/python.exe analysis/show_max_hit.py

Nothing in the game may import this package. It is not a game system, so it
sits at the top level beside profiling/. Some scripts start Django when you
import them (show_skills_graph.py does), so treat the directory as unsafe to
bulk-import.
"""
