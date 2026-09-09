"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/08/2026
Description: Tests for skills recovery -- the repair path for a db.skills
             Attribute that Evennia could not unpickle.

             The incident these guard against destroyed two characters'
             progress on 09/08/2026: a pickle naming a moved module came back
             from Evennia as a raw base64 STRING, and a guard that tested
             `isinstance(attr, dict)` overwrote it with a fresh empty dict.
             The data was recoverable the whole time.

             The blob fixtures here are built by pickling against module
             paths that DO NOT EXIST, which is what a pre-reorganisation
             character's Attribute looks like today. That is the only way to
             exercise the real failure -- a fixture that unpickles cleanly
             tests nothing about this module.
"""


import base64
import pickle
import sys
import types
import unittest

from collections.abc import Mapping

from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.progression.skills import recovery


# Two skills' worth of real progress, plus the junk that made the blob
# unreadable. Mirrors the shape actually found in the live database.
_REAL_PROGRESS = {
    "brawn": {"level": 54, "xp": 1499},
    "fortitude": {"level": 48, "xp": 616},
}

# The module path the 09/08/2026 reorganisation retired. Nothing imports it.
_MOVED_MODULE = "systems.progression.skills.skill_defs.combat.brawn"
_CURRENT_MODULE = "systems.gameplay.progression.skills.skill_defs.combat.brawn"


class _UnresolvableClass:
    """
    Purpose: Stand in for the skill class a pre-reorganisation character has
    pinned into its pickled db.skills.

    Notes/References:
        Pickled under _MOVED_MODULE by _build_blob, not under this test
        module. See that function for why.

    Author: Nick Hobar
    Creation date: 09/08/2026
    """


def _build_blob(payload: dict) -> str:
    """
    Purpose: Render `payload` as the base64 text Evennia hands back when it
    fails to unpickle an Attribute.

    Entry:
        payload is the dict to pickle. It may contain _UnresolvableClass.

    Exit/Returns:
        Returns the base64 string.

    Module Globals:
        _MOVED_MODULE read.

    Methodology:
        pickle records a class by MODULE PATH, and refuses to record one it
        cannot look back up. So the retired module is installed in
        sys.modules just long enough to pickle against, then removed -- which
        leaves bytes naming a module that does not exist, exactly like the
        rows sitting in the live database today. Building the fixture any
        other way produces a pickle that loads cleanly and therefore proves
        nothing.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/08/2026
    """
    stand_in = types.ModuleType(_MOVED_MODULE)
    _UnresolvableClass.__module__ = _MOVED_MODULE
    _UnresolvableClass.__qualname__ = "Brawn"
    stand_in.Brawn = _UnresolvableClass
    sys.modules[_MOVED_MODULE] = stand_in

    try:
        raw = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)
    finally:
        del sys.modules[_MOVED_MODULE]

    encoded = base64.b64encode(raw)

    return encoded.decode("ascii")


def _legacy_payload() -> dict:
    """The two-shaped dict a pre-reorganisation character actually carries."""
    payload = {}

    # The junk half: keyed by (skill_key, SkillClass), always level 0. These
    # are what pin an unresolvable module path into the pickle.
    for skill_key in _REAL_PROGRESS:
        payload[(skill_key, _UnresolvableClass)] = {"level": 0, "xp": 0}

    # The real half: keyed by the plain string, carrying the progress.
    for skill_key, record in _REAL_PROGRESS.items():
        payload[skill_key] = dict(record)

    return payload


class TestModuleAliasResolution(unittest.TestCase):
    """The alias table that lets a retired module path still be read."""

    def test_a_retired_prefix_is_rewritten_to_its_current_home(self):
        resolved = recovery._resolve_module(_MOVED_MODULE)
        self.assertEqual(resolved, _CURRENT_MODULE)

    def test_an_unrelated_module_path_is_left_alone(self):
        untouched = "world.item_database"
        resolved = recovery._resolve_module(untouched)
        self.assertEqual(resolved, untouched)

    def test_a_prefix_only_matches_on_a_dot_boundary(self):
        # `systems.combat` must not rewrite `systems.combatant`.
        resolved = recovery._resolve_module("systems.combatant.thing")
        self.assertEqual(resolved, "systems.combatant.thing")

    def test_every_alias_target_is_itself_stable(self):
        # A target that is itself an alias key would make resolution
        # order-dependent. Assert the relationship rather than a census.
        for old, new in recovery._MODULE_ALIASES.items():
            with self.subTest(alias=old):
                self.assertEqual(recovery._resolve_module(new), new)


class TestDecodeLegacyBlob(unittest.TestCase):
    """Reading progress back out of an Attribute that will not unpickle."""

    def setUp(self):
        self.blob = _build_blob(_legacy_payload())

    def test_the_fixture_really_is_unreadable_by_a_plain_unpickler(self):
        # If this ever passes, the fixture stopped reproducing the bug and
        # every other test in this class is testing nothing.
        raw = base64.b64decode(self.blob)
        with self.assertRaises(Exception):
            pickle.loads(raw)

    def test_real_progress_survives_the_decode(self):
        recovered = recovery.decode_legacy_blob(self.blob)

        for skill_key, record in _REAL_PROGRESS.items():
            with self.subTest(skill=skill_key):
                self.assertEqual(recovered[skill_key], record)

    def test_the_junk_tuple_keys_do_not_reach_the_repaired_dict(self):
        recovered = recovery.decode_legacy_blob(self.blob)

        for key in recovered:
            with self.subTest(key=key):
                self.assertIsInstance(key, str)

    def test_junk_never_overwrites_progress_whatever_the_iteration_order(self):
        # The junk entry for a skill is level 0; the real one is not. Feed
        # them in the order that would clobber, and assert it does not.
        payload = {
            "brawn": {"level": 54, "xp": 1499},
            ("brawn", _UnresolvableClass): {"level": 0, "xp": 0},
        }
        recovered = recovery.decode_legacy_blob(_build_blob(payload))
        self.assertEqual(recovered["brawn"]["level"], 54)

    def test_a_value_that_is_not_a_string_recovers_nothing(self):
        self.assertIsNone(recovery.decode_legacy_blob({"brawn": {}}))
        self.assertIsNone(recovery.decode_legacy_blob(None))

    def test_a_string_that_is_not_a_pickle_recovers_nothing(self):
        self.assertIsNone(recovery.decode_legacy_blob("not a pickle at all"))


class TestRepairOnCharacterLoad(EvenniaTest):
    """The handler chokepoint: what happens when a character is loaded."""

    def test_an_unreadable_attribute_is_repaired_not_reset(self):
        self.char1.db.skills = _build_blob(_legacy_payload())

        # Drop the cached handler so the next access rebuilds it, which is
        # what a fresh login does. lazy_property caches into __dict__.
        self.char1.__dict__.pop("skills", None)

        self.assertEqual(self.char1.skills.get_level("brawn"), 54)
        self.assertEqual(self.char1.skills.get_level("fortitude"), 48)

    def test_repair_leaves_a_readable_mapping_behind(self):
        self.char1.db.skills = _build_blob(_legacy_payload())
        self.char1.__dict__.pop("skills", None)
        self.char1.skills

        self.assertIsInstance(self.char1.db.skills, Mapping)

    def test_a_saved_attribute_is_not_a_dict_and_must_not_be_reset(self):
        # The regression that caused the incident. Evennia hands back a
        # _SaverDict, so an `isinstance(attr, dict)` guard is False for a
        # perfectly healthy character and wipes them on login.
        self.char1.skills.set_level("brawn", 31)
        self.char1.__dict__.pop("skills", None)

        stored = self.char1.db.skills
        self.assertNotIsInstance(stored, dict)
        self.assertIsInstance(stored, Mapping)
        self.assertEqual(self.char1.skills.get_level("brawn"), 31)

    def test_a_healthy_dict_is_left_exactly_as_it_was(self):
        healthy = {"brawn": {"level": 7, "xp": 3}}
        self.char1.db.skills = healthy
        self.char1.__dict__.pop("skills", None)
        self.char1.skills

        self.assertEqual(self.char1.db.skills["brawn"]["level"], 7)

    def test_an_unrecoverable_value_is_quarantined_before_reset(self):
        garbage = "this is not recoverable"
        self.char1.db.skills = garbage
        self.char1.__dict__.pop("skills", None)
        self.char1.skills

        quarantined = self.char1.attributes.get(recovery.QUARANTINE_ATTR)
        self.assertEqual(quarantined, garbage)
        self.assertEqual(self.char1.db.skills, {})

    def test_init_all_skills_does_not_discard_recoverable_progress(self):
        # init_all_skills carried its own copy of the destructive guard.
        self.char1.db.skills = _build_blob(_legacy_payload())
        self.char1.__dict__.pop("skills", None)
        self.char1.skills.init_all_skills()

        self.assertEqual(self.char1.db.skills["brawn"]["level"], 54)


class TestStoredAttributeEncoding(EvenniaTest):
    """
    The storage format an operator restore has to reproduce byte for byte.

    These are the tests the 09/08/2026 restore script needed and could not
    have: it wrote a bare pickle into a column holding base64, reported
    success, and left both characters exactly as broken as before. The fact
    now lives in recovery.py precisely so this file can reach it.
    """

    def _row_value(self):
        """The raw db_value sqlite holds for char1's skills Attribute."""
        from django.db import connection

        attribute = self.char1.attributes.get("skills", return_obj=True)

        with connection.cursor() as cursor:
            cursor.execute(
                "select db_value from typeclasses_attribute where id = %s",
                [attribute.id],
            )
            return cursor.fetchone()[0]

    def test_our_encoding_matches_what_evennia_itself_wrote(self):
        payload = {"brawn": {"level": 54, "xp": 1499}}
        self.char1.db.skills = payload

        self.assertEqual(
            self._row_value(),
            recovery.encode_attribute_value(payload),
        )

    def test_a_value_we_encoded_reads_back_through_evennia(self):
        # The end-to-end property a restore depends on: write our bytes into
        # the row, and the GAME must see the value we meant.
        from django.db import connection

        payload = {"brawn": {"level": 54, "xp": 1499},
                   "fortitude": {"level": 48, "xp": 700}}
        attribute = self.char1.attributes.get("skills", return_obj=True)

        with connection.cursor() as cursor:
            cursor.execute(
                "update typeclasses_attribute set db_value = %s where id = %s",
                [recovery.encode_attribute_value(payload), attribute.id],
            )

        # The Attribute MODEL instance is idmapper-cached with its old
        # db_value, so clearing the handler's own cache is not enough to see
        # a row that changed underneath the process.
        from evennia.utils.idmapper.models import flush_cache

        flush_cache()
        self.char1 = type(self.char1).objects.get(id=self.char1.id)
        self.char1.attributes.reset_cache()
        self.char1.__dict__.pop("skills", None)

        self.assertEqual(self.char1.skills.get_level("brawn"), 54)
        self.assertEqual(self.char1.skills.get_level("fortitude"), 48)

    def test_the_encoding_is_text_not_raw_pickle_bytes(self):
        # The exact defect: dbserialize() alone returns pickle BYTES, but the
        # column is TEXT holding base64. A bytes value here is the bug.
        encoded = recovery.encode_attribute_value({"brawn": {"level": 1, "xp": 0}})

        self.assertIsInstance(encoded, str)
        self.assertNotIsInstance(encoded, bytes)
        base64.b64decode(encoded)  # raises if this is not base64
