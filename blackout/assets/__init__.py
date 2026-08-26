"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: Marks assets/ as a package so the build tools in it can be
             imported by the test suite as `assets.pack_model`.

             Deliberately empty otherwise. This directory is import-SAFE --
             nothing here touches a database or boots Evennia -- which is what
             separates it from blackout/scripts/, where CLAUDE.md records that
             a bulk import once ran the map cleanup and deleted 347 rooms.
             Keep it that way: a module here may read and write files it is
             told about, and nothing else, at import time or otherwise.
"""
