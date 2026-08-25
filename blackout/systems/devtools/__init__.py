"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: Moderator tooling -- the effects a superuser or Admin may apply
             to the live world, and the vocabulary describing them.

             The package splits the way systems/quests/ does, and for the same
             reason:

               constants.py  the literals: the god-mode attribute name, the
                             action vocabulary, the bounds, the message
                             templates. Imports systems/ui/colors.py only.
               actions.py    the effects. Imports constants, and whatever
                             system it is reaching into.
               dossier.py    the read-only report. Changes nothing, which is
                             why it is not in actions.py.
               (menu)        systems/menus/dev_egg_menu.py -- presentation
                             only, and NOT part of this package.

             The last line is the load-bearing one. Every effect here is a
             plain function over (actor, target, ...) that returns a
             (succeeded, message) pair, so a future `@spawn` command, a test,
             or a script can call it without standing up an EvMenu. A moderator
             effect that only exists as a menu node is an effect that cannot be
             tested or scripted.
"""
