"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Player-written words in the world, and everything that has to be
             true before they are safe to leave there.

             The mechanism is the one signs already use -- a `world_label` on
             an entity, drawn by the client -- so nothing here re-implements
             writing. What a PLAYER writing brings with it, and a builder does
             not, is four things a signpost never needed:

                 a medium,    so writing costs something and is rate-limited
                              by the economy rather than by a cooldown nobody
                              can see
                 an author,   so a moderator acting on a scrawl knows whose it
                              is without asking
                 an expiry,   so the world does not silently fill with a
                              decade of junk that can only be cleared by hand
                 a refusal,   so there is one place to say no, ahead of the
                              writing rather than after it

             Split the way the quest system and the moderator egg are:

                 constants.py  the vocabulary, the bounds, the templates
                 service.py    the effects -- writing, charging, sweeping
                 decay.py      the Script that runs the sweep

             The split is load-bearing at the same seam it is there: `service`
             must stay callable from a test, a script or a future command with
             nothing scheduled anywhere, and `decay` is the only module that
             knows a clock exists.
"""
