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

# Evennia's own runner, plus this project's gc policy and an opt-in per-test
# instrument. The runner EXTENDS EvenniaTestSuiteRunner rather than replacing
# it, because that class's setup_test_environment is what calls evennia._init()
# and puts object #2 in place -- replacing it is how a suite ends up failing
# every create_object with "settings.DEFAULT_HOME (= '#2') does not exist".
#
# The gc policy is the second-largest saving in this file after the hasher
# above: gc.freeze() after setup takes ~41 ms off every test, roughly 77s of a
# 604s suite. See server/conf/testrunner.py for the measurement and the reason
# it is safe.
#
# The instrument is INERT unless BLACKOUT_PROFILE_TESTS is set in the
# environment, which is why it is safe to point at unconditionally rather than
# asking every developer to remember a second --settings file. See
# systems/profiling/testrunner.py for what it records.
TEST_RUNNER = "server.conf.testrunner.BlackoutTestSuiteRunner"
