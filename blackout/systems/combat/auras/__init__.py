"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/03/2026
Description: Damage auras — persistent, toggled radius effects that pulse
             damage onto every hostile around their caster on the global
             combat tick.

Deliberately empty of imports. `registry.py` walks the whole `aura_defs/` tree
on first import, and this package is reachable from the combat modules that
typeclasses pull in at startup; re-exporting the registry here would drag that
walk into server boot.
"""
