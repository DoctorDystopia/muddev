"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: The model pipeline. One command turns the model records under
             assets/models/ into the served .glb files, the client manifest
             and the credits.

                 ../evenv/Scripts/python.exe -m assets.pipeline build
                 ../evenv/Scripts/python.exe -m assets.pipeline check

             Run it from blackout/. assets/README.md is the procedure.

             Import-safe, like the rest of assets/. Importing a module here
             reads no file and starts no process. Only the commands do.
"""
