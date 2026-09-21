"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: Marks assets/ as a package, so the test suite can import the
             model pipeline as `assets.pipeline`.

             Empty otherwise. This directory is import-SAFE: nothing here
             touches a database or starts Evennia. That makes it different
             from blackout/scripts/, where CLAUDE.md records that a bulk import
             once ran the map cleanup and deleted 347 rooms. Keep it that
             way. A module here reads and writes only the files that it is
             told about, at import time or at any other time.
"""
