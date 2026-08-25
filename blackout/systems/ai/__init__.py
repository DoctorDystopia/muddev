"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/23/2026
Description: NPC behaviour package — the "what does this entity want to do
             next" half of combat, kept apart from the "how does an action
             resolve" half that lives in systems/combat/.

The split is deliberate. BlackoutCombatHandler.tick consults a behaviour from
here whenever a combatant has no pending action; a player's combatant names no
behaviour and so waits for a command, and an NPC's names one and acts. That
seam is the only thing standing between "hostiles are inert" and "hostiles
fight back" -- see docs/2026-08-23-DESIGN-0003 §3.1.

Behaviours live behind their own decorator registry (registry.py) rather than a
dispatch chain, so a new one is a new function with a decorator on it. That is
also the escape hatch for driving them from somewhere other than the combat
handler later: out-of-combat AI would change the DRIVER, not this package.
"""
