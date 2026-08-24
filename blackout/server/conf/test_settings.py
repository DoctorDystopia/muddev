r"""
Purpose:
    Settings overlay used only when running the test suite. Imports the real
    game settings, then replaces the parts that are slow or non-deterministic
    under test.

Entry:
    Selected on the command line, e.g.
    `evennia test --settings test_settings.py systems.banking.tests`.

Exit-Returns:
    Module-level settings names, same contract as `settings.py`.

Module Globals:
    PASSWORD_HASHERS -- single fast hasher, see Methodology.

Methodology:
    `EvenniaTest.setUp` creates two accounts per *test method*, and each
    account creation runs the Django default PBKDF2 hasher at 1,200,000
    iterations -- measured at 0.46s per hash on this machine. With 930 of the
    1273 tests deriving from `EvenniaTest`/`EvenniaCommandTest` that is ~14
    minutes of the ~20 minute suite spent proving a hardcoded password
    hashes correctly. MD5 is cryptographically worthless and that is fine:
    no test asserts on hash strength, and this module is never loaded by a
    running server.

Notes-References:
    Keep this file thin. Anything that changes game *behaviour* belongs in
    settings.py so tests exercise what production runs.

Author & Date:
    Blackout, 2026-08-23
"""

from server.conf.settings import *

# See Methodology. This is the single largest cost in the suite.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
