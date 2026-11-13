"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/11/2026
Description: The server check of the dialogue scripts as a command
             (DESIGN-0017). Run it from the game directory:

                 python -m systems.gameplay.dialogue
                 python -m systems.gameplay.dialogue --write-stub

             It prints one line for each fault and exits with 1 if it found
             a fault. With `--write-stub` it first writes the editor stub of
             the dialogue vocabulary. The Godot editor runs it after each script export, so
             an author sees a name that is not in the dialogue vocabulary
             without a terminal.

             The command starts Django with the real settings, because the
             quest registry imports Evennia. It opens no database: the
             check reads files and the registries only.
"""

import os
import sys


# ─── Public constant definitions ─────────────────────────────────────────────

# With this flag, the command also writes the editor stub of the dialogue
# vocabulary (stub.py). The Godot editor gives it, so a new vocabulary entry
# reaches the editor at the next save of a script.
WRITE_STUB_FLAG: str = "--write-stub"


# ─── Private constant definitions ────────────────────────────────────────────

_SETTINGS_ENV_VAR: str = "DJANGO_SETTINGS_MODULE"
_SETTINGS_MODULE: str = "server.conf.settings"

_EXIT_OK: int = 0
_EXIT_PROBLEMS: int = 1


# ─── Private helper routines ─────────────────────────────────────────────────

def _bootstrap() -> None:
    """Start Django and fill the flat API of Evennia. The quest content
    modules read that API when they import."""
    os.environ.setdefault(_SETTINGS_ENV_VAR, _SETTINGS_MODULE)

    import django

    django.setup()

    import evennia

    evennia._init()


# ─── Public routines ─────────────────────────────────────────────────────────

def main(arguments: list) -> int:
    """Check each dialogue script of the game, print each fault, and return
    the exit code. With WRITE_STUB_FLAG, write the editor stub first."""
    _bootstrap()

    from systems.gameplay.dialogue import files, loader, stub

    if WRITE_STUB_FLAG in arguments:
        wrote = stub.write_stub()

        if wrote:
            print(f"written  {stub.stub_path()}")

    problems = files.check_game()

    for problem in problems:
        print(problem)

    if problems:
        print(f"{len(problems)} problem(s) in the dialogue scripts.")

        return _EXIT_PROBLEMS

    print(f"{len(loader.script_keys())} dialogue script(s), no problem.")

    return _EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
