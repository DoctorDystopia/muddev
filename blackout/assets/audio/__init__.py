"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/26/2026
Description: The sound wizard. One command adds one sound clip to the Godot
             client: the copy, its .import file, its row in the cue table,
             and its row in the credits.

                 ../evenv/Scripts/python.exe -m assets.audio add
                 ../evenv/Scripts/python.exe -m assets.audio check

             Run it from blackout/. godot/README.md, "Sound is the client's",
             is the procedure.

             It shares the questions and the license gate with the model
             pipeline (assets/pipeline/questions.py, licenses.py).

             Import-safe, like the rest of assets/. Importing a module here
             reads no file and starts no process. Only the commands do.
"""
