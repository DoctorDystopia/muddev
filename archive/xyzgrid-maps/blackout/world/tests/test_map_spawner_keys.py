"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/20/2026
Description: Drift guard for the room KEY that joins a map to its spawner.

             Run from blackout/:
                 ../evenv/Scripts/evennia.exe test --settings test_settings.py world

             A tile stands up its occupant through one string. The map writes
             it as a prototype `key`, and `SPAWNER_REGISTRY` is keyed on the
             same string. Nothing compares the two. A typo therefore gives a
             tile that looks like a clearing, reads like a clearing, colours
             like a clearing and has no pole on it, with no error on either
             side.

             The copper pole is what this module was written for. The azm_plains
             clearings began as a copy of the oasis rusty poles, so every
             string had to be retyped -- the node class, the prototype key, the
             spawner key and the client colour. Four copies of one fact is the
             shape CLAUDE.md names.

             NO CENSUS HERE. The suite must not say which maps exist, which
             clearings exist, or how many. A new map, a new clearing and a
             retuned yield are all intended content, and a test that failed on
             them would train the reader to edit it. Every case below is
             derived from the manifest, the registries and the map modules
             themselves.

             The guard is a NEAR MISS detector, and that is deliberate. It
             cannot read a map author's intent from a string, so it never says
             "this key should have a spawner". It says "this key is one space,
             one capital or one letter away from a spawner key", which no map
             ever means on purpose.
"""

import unittest

from systems.gameplay.progression.skills.gatherables import GATHERABLE_REGISTRY
from typeclasses.gathering_nodes import GatheringNode
from typeclasses.spawners import SPAWNER_REGISTRY, load_all_spawners
from world.maps.manifest import load_entries
from evennia.utils.utils import class_from_module


# ─── Private constant definitions ────────────────────────────────────────────

# The prototype field that a key spawner dispatches on. Named once, because
# three helpers below read it out of raw prototype dicts.
_PROTOTYPE_KEY_FIELD = "key"

# The table of coordinate overrides every map module declares.
_PROTOTYPES_ATTR = "PROTOTYPES"


def _normalise(room_key):
    """
    Purpose: Reduce a room key to the form a near-miss is measured in.

    Entry:
        room_key - a prototype key or a spawner key.

    Exit/Returns:
        Returns a lowercase string with the outer whitespace removed and every
        inner run of whitespace collapsed to one space.

    Module Globals:
        None

    Methodology:
        Case and spacing are the two ways a retyped key goes wrong, and both
        are invisible in a diff. Everything else -- a different noun, a
        different facility -- is a different key on purpose.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/20/2026
    """
    return " ".join(str(room_key).split()).lower()


def _map_modules():
    """
    Purpose: Import every map the manifest ships and give back its module.

    Entry:
        None.

    Exit/Returns:
        Returns a list of (zcoord, module) pairs, in manifest order.

    Module Globals:
        None

    Methodology:
        Reads `world.maps.manifest`, which is the importable half of the map
        pipeline. `blackout/scripts/` is import-unsafe and is never touched
        here.

    Notes/References:
        CLAUDE.md, "Danger: blackout/scripts/".

    Author: Nick Hobar
    Creation date: 09/20/2026
    """
    import importlib

    modules = []

    for entry in load_entries():
        modules.append((entry.zcoord, importlib.import_module(entry.module)))

    return modules


def _prototype_keys(module):
    """
    Purpose: Every room key a map module declares.

    Entry:
        module - an imported map module.

    Exit/Returns:
        Returns a list of (coordinate, room_key) pairs. A prototype with no
        key, and every exit prototype, is left out.

    Module Globals:
        _PROTOTYPES_ATTR and _PROTOTYPE_KEY_FIELD read.

    Methodology:
        An exit row is told apart by the length of its coordinate tuple: a
        room is (x, y) and an exit is (x, y, direction). The wildcard row
        ('*', '*') is a room and is included, because a map-wide default is a
        key like any other.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/20/2026
    """
    prototypes = getattr(module, _PROTOTYPES_ATTR, {})
    found = []

    for coordinate, prototype in prototypes.items():
        if len(coordinate) != 2:
            continue

        room_key = prototype.get(_PROTOTYPE_KEY_FIELD)

        if room_key:
            found.append((coordinate, room_key))

    return found


class MapSpawnerKeyTest(unittest.TestCase):
    """The string a map writes against the string a spawner answers to."""

    def setUp(self):
        load_all_spawners()

    def test_no_map_key_is_a_near_miss_of_a_spawner_key(self):
        """
        A key that differs from a spawner key only in case or spacing is a
        retyping error. The tile spawns nothing and says nothing.
        """
        spawners = {_normalise(key): key for key in SPAWNER_REGISTRY}

        for zcoord, module in _map_modules():
            for coordinate, room_key in _prototype_keys(module):
                if room_key in SPAWNER_REGISTRY:
                    continue

                with self.subTest(map=zcoord, coordinate=coordinate,
                                  room_key=room_key):
                    self.assertNotIn(
                        _normalise(room_key),
                        spawners,
                        "%r on %s at %s differs from the registered %r only "
                        "in case or spacing" % (
                            room_key,
                            zcoord,
                            coordinate,
                            spawners.get(_normalise(room_key)),
                        ),
                    )

    def test_every_map_glyph_with_a_spawner_key_stands_something_up(self):
        """
        A prototype whose key IS registered must reach a spawner that imports
        and runs. The registry holds callables, so this is what proves the
        decorator ran in the module the map depends on.
        """
        for zcoord, module in _map_modules():
            for coordinate, room_key in _prototype_keys(module):
                if room_key not in SPAWNER_REGISTRY:
                    continue

                with self.subTest(map=zcoord, coordinate=coordinate,
                                  room_key=room_key):
                    self.assertTrue(callable(SPAWNER_REGISTRY[room_key]))


class GatheringNodeChainTest(unittest.TestCase):
    """The node class between a spawner and the yield table."""

    def setUp(self):
        load_all_spawners()

    def test_every_gathering_node_class_names_a_registered_gatherable(self):
        """
        `at_object_creation` raises on an unregistered key, which is the wrong
        time to find out. Walking the subclasses says it without a database.
        """
        subclasses = GatheringNode.__subclasses__()

        for node_class in subclasses:
            with self.subTest(node_class=node_class.__name__):
                self.assertIn(node_class.gatherable_key, GATHERABLE_REGISTRY)

    def test_the_registry_and_the_subclasses_agree(self):
        """
        Vacuity guard. `__subclasses__` gives nothing until the module that
        defines them is imported, and an empty loop above would read as a
        pass.
        """
        self.assertTrue(GatheringNode.__subclasses__())


class GatheringSpawnerChainTest(unittest.TestCase):
    """
    A spawner names its node by a dotted path. That path is the last copy of
    the fact, and it is the one an import check reaches.
    """

    def setUp(self):
        load_all_spawners()

    def test_every_gathering_spawner_builds_a_registered_node(self):
        """
        Reads each spawner's own source for the typeclass path it passes to
        `spawn_once`, imports it, and asserts the class carries a registered
        gatherable key.
        """
        import inspect
        import re

        path_pattern = re.compile(r'"(typeclasses\.gathering_nodes\.\w+)"')
        checked = 0

        for room_key, spawner in SPAWNER_REGISTRY.items():
            source = inspect.getsource(spawner)
            match = path_pattern.search(source)

            if not match:
                continue

            with self.subTest(room_key=room_key):
                node_class = class_from_module(match.group(1))
                self.assertIn(node_class.gatherable_key, GATHERABLE_REGISTRY)

            checked += 1

        self.assertTrue(checked, "no gathering spawner was found to check")
