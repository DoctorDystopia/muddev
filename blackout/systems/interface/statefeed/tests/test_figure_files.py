"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/12/2026
Description: Guard the server names in the figure files.

             The figure workbench (godot/addons/blackout_figure/) writes the
             rigs and the worn looks into assets/figure/. A rig holds a slot
             table: the default bone of each equipment slot. The slot names
             are the values of WieldLocation, and only Python knows them.
             GDScript cannot import the enum, so the workbench types the
             names again. This module compares the two.

             DESIGN-0014 section 7.3 gives this half of the checks to Python:
             rules C10, C1, and C7.
             The workbench owns each other rule, and its own tests
             (godot/tests/test_figure_*.gd) check the form of each file.

             NO CENSUS. Per CLAUDE.md, no case names a rig, a slot, or a
             bone. Each case is a relationship: between a slot table and the
             enum, a slot and the bones of its rig, a file and its key.

             A clip list (assets/figure/clips/, Phase W2) names a source of
             the model pipeline. Only Python reads a source record, so this
             module makes sure that the source is there and that its license
             passes the gate.

             The item catalog (godot/addons/blackout_figure/item_catalog.json,
             Phase W3) is a generated file. This module compares the file in
             git with a new render, and it compares the render with ITEM_DB.

             The figure set (web/static/webclient/models/figure.json, Phase
             W4) is a generated file also. test_model_pipeline.py runs the
             check that compares the file in git with a new render. This
             module compares the render with the figure files, and it tests
             `figure-model`, the command that brings a model file in. Those
             cases write only into a temporary directory.

             A worn look names a model by its asset key (Phase W4). Only
             Python reads the model records, so this module makes sure that
             each such key has a model.

             The palette (assets/figure/palette.json, Phase W5) gives each
             named color its color. This module makes sure that each color
             that a worn look or a color role names is in it. A tier is a
             worn look with a base, and this module makes sure that no two
             bases name each other: the second half of rule C9.

             The stance table (godot/world/figure/stances.json, Phase W5)
             has a tool type as the key of each stance. Only Python knows
             the tool types, so rule C7 is here.

             A kit part (Phase W6) is a worn look with a `kit` group: one
             hair shape, one head. Its key names no item, so rule C1 lets
             it through by its group.

             The outfit of an NPC def (Phase W6) is a server fact that the
             workbench shows. This module makes sure that a character can
             wear each outfit, and that the catalog has each one.

             Reads JSON, source records, model records, the skill maps,
             NPC_DB, and ITEM_DB only. It starts no Godot and touches no
             database.
"""

import json
import os
import tempfile
import unittest
from unittest import mock

from assets.pipeline import (figure, licenses, outputs, paths, records,
                             sources)
from items.equipment.constants import (SLOT_CONFLICTS, SLOT_DISPLAY_ORDER,
                                       WieldLocation)
from items.equipment.skill_requirements import (ARMOR_SKILL_MAP,
                                                WEAPON_SKILL_MAP)
from world.item_database import ITEM_DB
from world.npc_database import NPC_DB

from .. import constants as const
from .. import figure_catalog


def _read_files(folder):
    """
    Purpose: Read each figure file of one directory.

    Entry:
        folder is a path. It does not need to exist.

    Exit/Returns:
        Returns a dict of file stem -> parsed JSON content. A directory that
        does not exist gives an empty dict.

    Author: Nick Hobar
    Creation date: 10/12/2026
    """
    found = {}

    if not os.path.isdir(folder):
        return found

    for file_name in sorted(os.listdir(folder)):
        if not file_name.endswith(paths.FIGURE_FILE_SUFFIX):
            continue

        stem = file_name[:-len(paths.FIGURE_FILE_SUFFIX)]
        path = os.path.join(folder, file_name)

        with open(path, encoding="utf-8") as handle:
            found[stem] = json.load(handle)

    return found


class RigSlotTableTests(unittest.TestCase):
    """The slot table of each rig agrees with WieldLocation."""

    @classmethod
    def setUpClass(cls):
        cls.rigs = _read_files(paths.FIGURE_RIGS_DIR)
        cls.slots = {location.value for location in WieldLocation}

    def test_at_least_one_rig_was_found(self):
        """
        The vacuity guard. With no rig, each loop below passes with no
        subTest, and "found nothing" would read as "passed".
        """
        self.assertTrue(self.rigs, "no rig file in %s" % paths.FIGURE_RIGS_DIR)

    def test_the_slot_table_names_only_real_slots(self):
        """
        Rule C10: a slot that WieldLocation does not have is a typed name
        that nothing equips into.
        """
        for key, rig in self.rigs.items():
            for slot in rig["slots"]:
                with self.subTest(rig=key, slot=slot):
                    self.assertIn(slot, self.slots)

    def test_each_slot_has_a_row(self):
        """
        Nick's answer 2 (10/12/2026): the figure shows each slot. A new
        WieldLocation value with no row has no default bone.
        """
        for key, rig in self.rigs.items():
            for slot in sorted(self.slots):
                with self.subTest(rig=key, slot=slot):
                    self.assertIn(slot, rig["slots"])

    def test_each_slot_names_a_bone_of_its_rig(self):
        for key, rig in self.rigs.items():
            bones = {bone["name"] for bone in rig["bones"]}

            for slot, bone in rig["slots"].items():
                with self.subTest(rig=key, slot=slot):
                    self.assertIn(bone, bones)


class FigureFileKeyTests(unittest.TestCase):
    """Each figure file has its key as its name."""

    def test_each_file_has_its_key_as_its_name(self):
        for folder in (paths.FIGURE_RIGS_DIR, paths.FIGURE_LOOKS_DIR,
                       paths.FIGURE_CLIPS_DIR):
            for stem, content in _read_files(folder).items():
                with self.subTest(folder=os.path.basename(folder), file=stem):
                    self.assertEqual(content["key"], stem)

    def test_each_body_type_has_a_body(self):
        """
        A body is the worn look with the key of its body type. A rig with
        no body stands bare in the client.
        """
        looks = _read_files(paths.FIGURE_LOOKS_DIR)

        for key in _read_files(paths.FIGURE_RIGS_DIR):
            with self.subTest(rig=key):
                self.assertIn(key, looks)


class ClipListSourceTests(unittest.TestCase):
    """
    Each clip list names a source that the license gate lets through.

    A clip list is assets/figure/clips/<source_id>.json. The figure
    workbench builds the clip files of the client from it. Only Python
    reads a source record, so this half of the check is here.
    """

    @classmethod
    def setUpClass(cls):
        cls.clip_lists = _read_files(paths.FIGURE_CLIPS_DIR)

    def test_each_clip_list_names_a_source(self):
        """The key of a clip list is a source id, and a typed id finds none."""
        source_ids = set(sources.list_source_ids())

        for key in self.clip_lists:
            with self.subTest(clip_list=key):
                self.assertIn(key, source_ids)

    def test_each_clip_list_names_a_file_of_its_source(self):
        for key, clip_list in self.clip_lists.items():
            with self.subTest(clip_list=key):
                source = sources.load_source(key)

                self.assertIn(clip_list["file"], source.files)

    def test_the_license_gate_lets_each_source_through(self):
        """
        A clip of a source goes into the client. Thus, its license must be
        one that the model pipeline permits for a served model.
        """
        for key in self.clip_lists:
            with self.subTest(clip_list=key):
                problem = sources.gate_problem(sources.load_source(key))

                self.assertEqual(problem, "")


class ItemCatalogTests(unittest.TestCase):
    """
    The item catalog of the figure workbench agrees with ITEM_DB.

    The catalog is a generated file in git. The workbench reads it to dress
    a figure, because GDScript cannot import ITEM_DB.
    """

    @classmethod
    def setUpClass(cls):
        cls.catalog = figure_catalog.build()
        cls.rows = {row["key"]: row for row in cls.catalog["items"]}

    def test_the_file_in_git_matches_a_new_render(self):
        """A stale catalog shows the author an item list of the past."""
        path = figure_catalog.output_path()

        self.assertTrue(
            os.path.isfile(path),
            "%s is not there. Run:\n"
            "    python scripts/export_client_constants.py" % path)

        with open(path, "r", encoding="utf-8", newline="") as handle:
            committed = handle.read().replace("\r\n", "\n")

        self.assertEqual(
            committed, figure_catalog.render(),
            "%s is stale. Run:\n"
            "    python scripts/export_client_constants.py"
            % os.path.basename(path))

    def test_the_catalog_has_items(self):
        """The vacuity guard of the loops below."""
        self.assertTrue(self.rows, "the item catalog has no item")

    def test_each_item_with_a_slot_has_a_row(self):
        for key, item_def in ITEM_DB.items():
            with self.subTest(item=key):
                self.assertEqual(key in self.rows,
                                 item_def.use_slot is not None)

    def test_each_row_gives_the_facts_of_its_item(self):
        for key, row in self.rows.items():
            item_def = ITEM_DB[key]

            with self.subTest(item=key):
                self.assertEqual(row["name"], item_def.name)
                self.assertEqual(row["slot"], item_def.use_slot.value)
                self.assertEqual(row["tier"], item_def.tier)
                self.assertEqual(row["tool_type"], item_def.tool_type or "")

    def test_each_row_names_a_family_of_the_client(self):
        families = set(const.ITEM_FAMILIES) | {const.ITEM_FAMILY_GENERIC}

        for key, row in self.rows.items():
            with self.subTest(item=key):
                self.assertIn(row["family"], families)

    def test_the_slot_rows_are_the_display_order(self):
        """
        One row for each slot, in the order of the equipment screens. A new
        WieldLocation value with no display position has no cell on the
        outfit bar.
        """
        keys = [row["key"] for row in self.catalog["slots"]]

        self.assertEqual(keys, [slot.value for slot in SLOT_DISPLAY_ORDER])
        self.assertEqual(set(keys), {slot.value for slot in WieldLocation})

    def test_each_cleared_slot_is_a_slot(self):
        slots = {slot.value for slot in WieldLocation}

        for row in self.catalog["slots"]:
            for cleared in row["clears"]:
                with self.subTest(slot=row["key"], cleared=cleared):
                    self.assertIn(cleared, slots)
                    self.assertNotEqual(cleared, row["key"])

    def test_the_tool_types_are_those_of_the_server(self):
        """
        The workbench checks a stance against this list. Thus, the list has
        each tool type that the two skill maps and the items have.
        """
        listed = set(self.catalog["tool_types"])

        for tool_type in set(WEAPON_SKILL_MAP) | set(ARMOR_SKILL_MAP):
            with self.subTest(tool_type=tool_type):
                self.assertIn(tool_type, listed)

        for key, item_def in ITEM_DB.items():
            if item_def.tool_type:
                with self.subTest(item=key):
                    self.assertIn(item_def.tool_type, listed)

    def test_each_npc_def_with_an_outfit_has_a_row(self):
        rows = {row["key"]: row for row in self.catalog["npcs"]}

        for key, npc_def in NPC_DB.items():
            with self.subTest(npc=key):
                self.assertEqual(key in rows, bool(npc_def.outfit))

        for key, row in rows.items():
            outfit = {slot.value: item_key
                      for slot, item_key in NPC_DB[key].outfit.items()}

            with self.subTest(npc=key):
                self.assertEqual(row["name"], NPC_DB[key].name)
                self.assertEqual(row["outfit"], outfit)


def _item_for(slot):
    """The key of the first item that goes in `slot`, or None."""
    for key in sorted(ITEM_DB):
        if ITEM_DB[key].use_slot is slot:
            return key

    return None


class NpcOutfitTests(unittest.TestCase):
    """
    A character can wear the outfit of each NPC def.

    The figure of an NPC is the figure of a player. An outfit with an item
    in a wrong slot, or with two items that cannot be worn together, shows
    gear that no character can have.
    """

    def test_each_outfit_of_a_def_is_one_that_a_character_can_wear(self):
        for key, npc_def in NPC_DB.items():
            with self.subTest(npc=key):
                self.assertEqual(
                    figure_catalog.outfit_problems(npc_def.outfit), [])

    def test_no_outfit_and_an_outfit_of_real_items_have_no_problem(self):
        outfit = {slot: _item_for(slot) for slot in SLOT_DISPLAY_ORDER[:1]
                  if _item_for(slot)}

        self.assertEqual(figure_catalog.outfit_problems(None), [])
        self.assertEqual(figure_catalog.outfit_problems(outfit), [])

    def test_an_item_in_a_wrong_slot_is_a_problem(self):
        filled = [slot for slot in WieldLocation if _item_for(slot)]

        self.assertGreater(len(filled), 1, "the item database has one slot")

        outfit = {filled[0]: _item_for(filled[1])}

        self.assertTrue(figure_catalog.outfit_problems(outfit))

    def test_an_unknown_item_and_an_unknown_slot_are_problems(self):
        slot = next(iter(WieldLocation))

        self.assertTrue(
            figure_catalog.outfit_problems({slot: "no_such_item_key"}))
        self.assertTrue(
            figure_catalog.outfit_problems({slot.value: _item_for(slot)}))

    def test_two_slots_that_one_item_clears_are_a_problem(self):
        """The outfit bar of the workbench empties a slot that an item clears."""
        for slot, cleared_slots in SLOT_CONFLICTS.items():
            for cleared in cleared_slots:
                if not _item_for(slot) or not _item_for(cleared):
                    continue

                outfit = {slot: _item_for(slot), cleared: _item_for(cleared)}

                with self.subTest(slot=slot.value, cleared=cleared.value):
                    self.assertTrue(figure_catalog.outfit_problems(outfit))


class WornLookKeyTests(unittest.TestCase):
    """
    Rule C1: each worn look names something that the server has.

    The key of a worn look is one of three names: the key of an ItemDef, a
    slot (a slot shape), or a body type (a body). A look with another key
    dresses nothing, and nothing in the client reports it.
    """

    @classmethod
    def setUpClass(cls):
        cls.looks = _read_files(paths.FIGURE_LOOKS_DIR)
        cls.slots = {slot.value for slot in WieldLocation}
        cls.body_types = set(_read_files(paths.FIGURE_RIGS_DIR))

    def test_each_look_names_an_item_a_slot_or_a_body_type(self):
        """A kit part names none of the three. Its `kit` group lets it in."""
        known = set(ITEM_DB) | self.slots | self.body_types

        for key, look in self.looks.items():
            if look.get("kit"):
                continue

            with self.subTest(look=key):
                self.assertIn(key, known)

    def test_no_kit_part_takes_the_key_of_an_item(self):
        """
        A kit part and the look of an item share one directory. A kit part
        with the key of an item would dress each character that wears the
        item.
        """
        taken = set(ITEM_DB) | self.slots | self.body_types

        for key, look in self.looks.items():
            if look.get("kit"):
                with self.subTest(look=key):
                    self.assertNotIn(key, taken)

    def test_no_item_has_the_name_of_a_slot_or_of_a_body_type(self):
        """
        The three kinds of key share one directory. An item with the key of
        a slot would take the file of that slot shape.
        """
        for key in self.slots | self.body_types:
            with self.subTest(name=key):
                self.assertNotIn(key, ITEM_DB)

    def test_each_base_is_a_look(self):
        """The first half of rule C9. A tier names the look of its parts."""
        for key, look in self.looks.items():
            if "base" in look:
                with self.subTest(look=key):
                    self.assertIn(look["base"], self.looks)

    def test_no_bases_name_each_other(self):
        """
        The second half of rule C9. A walk from a tier along its bases must
        end at a look with no base. A walk that comes back to a look finds
        no parts, and the figure then draws nothing for that item.
        """
        for key in self.looks:
            seen = []
            walk = key

            while walk in self.looks and walk not in seen:
                seen.append(walk)
                walk = self.looks[walk].get("base", "")

            with self.subTest(look=key):
                self.assertNotIn(walk, seen)

    def test_a_tier_has_no_part_of_its_own(self):
        """
        Requirement D4: a look with a base takes the parts of that base. The
        Godot reader refuses a tier with parts or with a fit, and the look
        then stays out of the figure set.
        """
        for key, look in self.looks.items():
            if "base" not in look:
                continue

            with self.subTest(look=key):
                self.assertNotIn("parts", look)
                self.assertNotIn("fit", look)

    def test_each_model_of_a_part_is_a_served_model(self):
        """
        The first half of rule C3. A part names its model by an asset key,
        and the manifest is the list of those keys. A part with a key that
        the manifest does not have draws its shape list for good.
        """
        manifest = outputs.render_manifest(records.load_all())

        for key, look in self.looks.items():
            for part in look.get("parts", []):
                if "model" not in part:
                    continue

                with self.subTest(look=key, part=part["name"]):
                    self.assertIn(part["model"], manifest)

    def test_each_fit_names_a_body_type_and_a_part(self):
        """
        A fit row gives one part another place on one body type. A row for
        a body type with no rig, or for a part that the look does not have,
        places nothing.
        """
        for key, look in self.looks.items():
            names = {part["name"] for part in look.get("parts", [])}

            for body_type, rows in look.get("fit", {}).items():
                with self.subTest(look=key, body_type=body_type):
                    self.assertIn(body_type, self.body_types)

                for row in rows:
                    with self.subTest(look=key, part=row["part"]):
                        self.assertIn(row["part"], names)


def _read_json(path):
    """
    Purpose: Read one JSON file.

    Entry:
        path is a path. It does not need to exist.

    Exit/Returns:
        Returns the parsed content, or an empty dict for no file.

    Author: Nick Hobar
    Creation date: 10/13/2026
    """
    if not os.path.isfile(path):
        return {}

    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


class PaletteTests(unittest.TestCase):
    """
    Each color name of the figure files is a named color of the palette.

    A worn look gives a color role a named color, and the palette gives
    the named color its color. A name that the palette does not have draws
    in a start color of the client, or in the loud color of a missing one.
    Nothing in the client reports it.
    """

    @classmethod
    def setUpClass(cls):
        cls.palette = _read_json(paths.FIGURE_PALETTE_PATH)
        cls.colors = cls.palette.get("colors", {})
        cls.looks = _read_files(paths.FIGURE_LOOKS_DIR)

    def test_the_palette_has_colors(self):
        """The vacuity guard of the loops below."""
        self.assertTrue(self.colors,
                        "no named color in %s" % paths.FIGURE_PALETTE_PATH)

    def test_each_color_role_names_a_color_of_the_palette(self):
        for role, color in self.palette.get("roles", {}).items():
            with self.subTest(role=role):
                self.assertIn(color, self.colors)

    def test_each_color_of_a_look_is_a_color_of_the_palette(self):
        for key, look in self.looks.items():
            for role, color in look.get("colors", {}).items():
                with self.subTest(look=key, role=role):
                    self.assertIn(color, self.colors)

    def test_each_shape_names_a_color_role_or_a_color(self):
        """
        A shape names a color role of its look, a color role of the
        palette, or a named color. A tier has no shape, so only a look
        with parts is in this loop.
        """
        known = set(self.colors) | set(self.palette.get("roles", {}))

        for key, look in self.looks.items():
            own = set(look.get("colors", {}))

            for part in look.get("parts", []):
                for shape in part.get("shapes", []):
                    if "color" not in shape:
                        continue

                    with self.subTest(look=key, part=part["name"]):
                        self.assertIn(shape["color"], known | own)


class StanceTableTests(unittest.TestCase):
    """
    Rule C7: each stance names a tool type of the server and a clip file.

    The stance table is godot/world/figure/stances.json. The figure
    workbench writes it, and the client reads it. A stance with a typed
    tool type selects nothing, and an action with a clip that is not there
    leaves the figure in its rest pose.
    """

    _CLIP_SUFFIX = ".res"

    @classmethod
    def setUpClass(cls):
        cls.path = figure_catalog.stances_path()
        cls.table = _read_json(cls.path)
        cls.tool_types = set(figure_catalog.tool_types())
        cls.clips = {name[:-len(cls._CLIP_SUFFIX)]
                     for name in os.listdir(figure_catalog.clips_directory())
                     if name.endswith(cls._CLIP_SUFFIX)}

    def _clip_sets(self):
        """Give (name, clip set) for the default set and for each stance."""
        sets = [("default", self.table.get("default", {}))]
        sets.extend(sorted(self.table.get("stances", {}).items()))

        return sets

    def test_the_stance_table_is_there(self):
        """The vacuity guard of the loops below."""
        self.assertTrue(self.table, "no stance table at %s" % self.path)

    def test_each_stance_names_a_tool_type_of_the_server(self):
        for tool_type in self.table.get("stances", {}):
            with self.subTest(tool_type=tool_type):
                self.assertIn(tool_type, self.tool_types)

    def test_each_clip_of_a_stance_is_a_clip_file(self):
        for name, clip_set in self._clip_sets():
            for action, clip in clip_set.items():
                with self.subTest(stance=name, action=action):
                    self.assertIn(clip, self.clips)


class FigureSetTests(unittest.TestCase):
    """
    The figure set is the figure files, in one served file.

    The build writes figure.json from the rigs, the worn looks, and the
    palette. The check of the model pipeline fails on a stale one, and
    test_model_pipeline.py runs that check.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = figure.render_figure_set()
        cls.document = json.loads(cls.text)

    def test_the_set_has_each_rig_and_each_worn_look(self):
        self.assertEqual(self.document["rigs"],
                         _read_files(paths.FIGURE_RIGS_DIR))
        self.assertEqual(self.document["looks"],
                         _read_files(paths.FIGURE_LOOKS_DIR))

    def test_the_set_has_the_palette(self):
        self.assertEqual(self.document["palette"],
                         _read_json(paths.FIGURE_PALETTE_PATH))

    def test_a_set_with_no_palette_file_has_an_empty_palette(self):
        """The client then takes each named color from its start table."""
        with tempfile.TemporaryDirectory() as folder:
            missing = os.path.join(folder, "palette.json")

            with mock.patch.object(paths, "FIGURE_PALETTE_PATH", missing):
                document = json.loads(figure.render_figure_set())

        self.assertEqual(document["palette"], {})

    def test_a_palette_that_does_not_read_is_refused(self):
        for body in ("{ this is not JSON", "[]"):
            with self.subTest(body=body):
                with tempfile.TemporaryDirectory() as folder:
                    path = os.path.join(folder, "palette.json")

                    with open(path, "w", encoding="utf-8") as handle:
                        handle.write(body)

                    with mock.patch.object(paths, "FIGURE_PALETTE_PATH", path):
                        with self.assertRaises(figure.FigureError):
                            figure.render_figure_set()

    def test_the_set_has_a_format_number(self):
        """The Godot reader refuses a file with no format number."""
        self.assertEqual(self.document["format"], figure.FIGURE_SET_FORMAT)

    def test_the_text_is_one_line_with_one_final_newline(self):
        """A client downloads the file, so it has no indent."""
        self.assertTrue(self.text.endswith("\n"))
        self.assertNotIn("\n", self.text[:-1])

    def test_the_same_files_give_the_same_text(self):
        self.assertEqual(figure.render_figure_set(), self.text)

    def test_the_generated_files_have_the_figure_set(self):
        """
        The check compares each file that outputs.render_all gives with the
        file in git. A set that is not in that table can go stale.
        """
        self.assertEqual(outputs.render_all()[paths.FIGURE_SET_PATH],
                         self.text)

    def test_a_figure_file_that_does_not_read_is_refused(self):
        bodies = {"not_json": "{ this is not JSON",
                  "wrong_key": '{"format": 1, "key": "another_name"}',
                  "a_list": "[]"}

        for stem, body in bodies.items():
            with self.subTest(file=stem):
                with tempfile.TemporaryDirectory() as folder:
                    name = stem + paths.FIGURE_FILE_SUFFIX
                    path = os.path.join(folder, name)

                    with open(path, "w", encoding="utf-8") as handle:
                        handle.write(body)

                    with mock.patch.object(paths, "FIGURE_LOOKS_DIR", folder):
                        with self.assertRaises(figure.FigureError):
                            figure.render_figure_set()


class FigureModelImportTests(unittest.TestCase):
    """
    `figure-model` brings one model file in as a source and a model record.

    Each case runs in a temporary sources directory and a temporary models
    directory. No case builds a model, so no case needs Node.
    """

    _KEY = "test_helm"
    _FAMILY = "items"
    _AUTHOR = 'An "Author"'

    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.addCleanup(self._folder.cleanup)
        self._sources = os.path.join(self._folder.name, "sources")
        self._models = os.path.join(self._folder.name, "models")
        os.makedirs(self._sources)
        os.makedirs(self._models)

        for name, value in (("SOURCES_DIR", self._sources),
                            ("MODELS_DIR", self._models)):
            patch = mock.patch.object(paths, name, value)
            patch.start()
            self.addCleanup(patch.stop)

    def _download(self, name, body=b"art"):
        """Write one model file outside the pipeline, and return its path."""
        path = os.path.join(self._folder.name, name)

        with open(path, "wb") as handle:
            handle.write(body)

        return path

    def _import(self, name="helm.glb", body=b"art"):
        """Import one model file under the test key, with the test author."""
        path = self._download(name, body)

        return figure.import_model(self._FAMILY, self._KEY, path,
                                   self._AUTHOR)

    def test_an_import_writes_a_source_that_passes_the_license_gate(self):
        self._import()
        source = sources.load_source(figure.source_id_for(self._KEY))

        self.assertEqual(source.license, licenses.OWNED_LICENSE)
        self.assertEqual(source.author, self._AUTHOR)
        self.assertEqual(sources.gate_problem(source), "")

    def test_an_import_seals_its_one_file(self):
        """The file has the model key as its name, whatever it was."""
        self._import("some download.GLB")
        source = sources.load_source(figure.source_id_for(self._KEY))

        self.assertEqual(list(source.files), [self._KEY + ".glb"])
        self.assertEqual(sources.hash_problems(source), [])

    def test_an_import_writes_a_record_that_keeps_the_color_roles(self):
        record_path = self._import()
        record = records.load_record(record_path)

        self.assertEqual(record.asset_key, self._KEY)
        self.assertEqual(record.family, self._FAMILY)
        self.assertEqual(record.source_id, figure.source_id_for(self._KEY))
        self.assertEqual(record.file, self._KEY + ".glb")
        self.assertTrue(record.color_roles)

    def test_a_second_import_puts_the_new_file_in_the_place_of_the_old(self):
        """
        A new export of the same art is a new download. The source keeps
        one file, and the record keeps each line that its author wrote.
        """
        record_path = self._import("helm.glb", b"first")

        with open(record_path, "a", encoding="utf-8") as handle:
            handle.write("\n[fix]\nrotate = [0, 90, 0]\n")

        self._import("helm.gltf", b"second")
        source = sources.load_source(figure.source_id_for(self._KEY))
        record = records.load_record(record_path)

        self.assertEqual(list(source.files), [self._KEY + ".gltf"])
        self.assertEqual(sources.hash_problems(source), [])
        self.assertEqual(record.file, self._KEY + ".gltf")
        self.assertEqual(record.rotate, (0.0, 90.0, 0.0))
        self.assertTrue(record.color_roles)

    def test_a_key_that_another_model_has_is_refused(self):
        """
        An item key can be an alias of another model. The import must not
        take the key from art that it did not bring.
        """
        other = os.path.join(self._models, self._FAMILY)
        os.makedirs(other)

        with open(os.path.join(other, "other_model.toml"), "w",
                  encoding="utf-8") as handle:
            handle.write('source = "s"\nfile = "f.glb"\naliases = ["%s"]\n'
                         % self._KEY)

        with self.assertRaises(figure.FigureError) as caught:
            self._import()

        self.assertIn("other_model", str(caught.exception))
        self.assertEqual(sources.list_source_ids(), [])

    def test_a_source_that_is_not_art_of_blackout_is_refused(self):
        directory = os.path.join(self._sources,
                                 figure.source_id_for(self._KEY))
        os.makedirs(directory)
        text = ('title = "t"\nauthor = "a"\nurl = "u"\nsite = "s"\n'
                'license = "CC0-1.0"\nretrieved = 2026-10-12\n\n[files]\n')
        record_path = os.path.join(directory, paths.SOURCE_RECORD_NAME)

        with open(record_path, "w", encoding="utf-8") as handle:
            handle.write(text)

        with self.assertRaises(figure.FigureError):
            self._import()

        with open(record_path, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), text)

    def test_a_bad_key_and_a_missing_file_are_refused(self):
        path = self._download("helm.glb")
        missing = os.path.join(self._folder.name, "no_such_file.glb")
        calls = (("items", "Bad Key", path), ("Bad Family", "helm", path),
                 ("items", "helm", missing))

        for family, key, filename in calls:
            with self.subTest(family=family, key=key):
                with self.assertRaises(figure.FigureError):
                    figure.import_model(family, key, filename)
