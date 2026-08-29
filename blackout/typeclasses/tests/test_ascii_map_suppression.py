"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/28/2026
Description: Cases for who is sent the ASCII map on look.

             `XYZRoom.return_appearance` msg's the map on every `look`, and
             `look` runs on every room change -- so on a 95-node map it was the
             dominant content of the text pane. A Godot session draws its own
             minimap from `blackout_map`, so printing it there is thirty lines
             of box characters nothing reads.

             The decision has exactly one reader,
             `GridTile._wants_ascii_map`, and these are its cases. The
             MAP-BUILDING half is not exercised here: it needs a live xyzgrid,
             it is the contrib's, and it is covered where the aura overlay is.
             What is worth testing is the policy, which is ours and is the part
             that can quietly blank a telnet player's map.
"""

import inspect
import unittest

from systems.statefeed import constants as feed_const
from typeclasses.rooms import GridTile


class _Session:
    """The one attribute the policy reads off a session."""

    def __init__(self, protocol_key):
        self.protocol_key = protocol_key


class _Sessions:
    """Stands in for Evennia's SessionHandler."""

    def __init__(self, sessions):
        self._sessions = sessions

    def get(self):
        return self._sessions


class _Attributes:
    """Stands in for AttributeHandler, for the one key that matters."""

    def __init__(self, stored):
        self._stored = stored

    def get(self, key, default=None):
        return self._stored.get(key, default)


class _Looker:
    """A character, as much of one as the policy touches.

    A stub rather than an EvenniaTest character: the policy reads two handlers
    and nothing else, and building two accounts and a script per method to
    supply them would be paying 0.2s a case for nothing.
    """

    def __init__(self, protocols=(), override=None):
        self.sessions = _Sessions([_Session(key) for key in protocols])

        stored = {}

        if override is not None:
            stored[feed_const.ASCII_MAP_ATTR] = override

        self.attributes = _Attributes(stored)


class _Room:
    """Just enough GridTile to ask it the two questions.

    The real methods, bound onto a bare object rather than onto a built room:
    neither reads anything off `self` except the other, and constructing an
    XYZRoom would mean a database, a grid and a spawned map for a decision that
    is two attribute reads.
    """

    _wants_ascii_map = GridTile._wants_ascii_map
    _appearance_kwargs = GridTile._appearance_kwargs


def _wants(looker):
    """The policy: should this looker be sent the map at all."""
    return _Room()._wants_ascii_map(looker)


def _kwargs(looker, given=None):
    """The wiring: what the contrib is actually told."""
    return _Room()._appearance_kwargs(looker, dict(given or {}))


class AsciiMapPolicyTests(unittest.TestCase):
    """Who gets the text map, and who has stopped needing it."""

    def test_a_telnet_session_still_gets_the_map(self):
        """The whole point of suppressing it for one client is not to take it
        from the others."""
        self.assertTrue(_wants(_Looker(protocols=("telnet",))))

    def test_a_godot_session_does_not(self):
        """It is already drawing the same map from blackout_map."""
        self.assertFalse(
            _wants(_Looker(protocols=(feed_const.GODOT_PROTOCOL_KEY,))))

    def test_a_browser_websocket_session_still_gets_it(self):
        """The webclient's 3D pane is a MIRROR, not a replacement -- its own
        header says closing it changes nothing about play, because the text
        channel is the authoritative view."""
        self.assertTrue(_wants(_Looker(protocols=("websocket",))))

    def test_a_mixed_pair_of_sessions_gets_it(self):
        """ALL sessions must be graphical, not any.

        Under a multisession mode that allowed two clients on one character,
        suppressing because one of them draws a map would blank it in the
        telnet window beside it.
        """
        looker = _Looker(protocols=(feed_const.GODOT_PROTOCOL_KEY, "telnet"))

        self.assertTrue(_wants(looker))

    def test_a_character_with_no_session_gets_it(self):
        """There is nobody there to have a preference, and answering False
        would suppress the map for anything looking on a puppet's behalf."""
        self.assertTrue(_wants(_Looker(protocols=())))

    def test_an_explicit_true_beats_the_client(self):
        """A Godot player who wants the text map keeps it."""
        looker = _Looker(
            protocols=(feed_const.GODOT_PROTOCOL_KEY,), override=True)

        self.assertTrue(_wants(looker))

    def test_an_explicit_false_beats_the_client(self):
        """And a telnet player tired of it can turn it off."""
        self.assertFalse(_wants(_Looker(protocols=("telnet",), override=False)))

    def test_the_attribute_is_the_one_the_constant_names(self):
        """The reader and the vocabulary cannot drift apart.

        The attribute name is read in exactly one place, so a rename that
        missed it would silently stop honouring every override that had ever
        been set -- with no error and no failing case anywhere else.
        """
        looker = _Looker(protocols=("telnet",))
        looker.attributes = _Attributes({feed_const.ASCII_MAP_ATTR: False})

        self.assertFalse(_wants(looker))


class AppearanceWiringTests(unittest.TestCase):
    """The policy reaching the thing that actually prints the map.

    THIS IS THE HALF THAT WAS MISSING, and it is why it exists. The policy
    above was right from the first commit and the suppression still did nothing
    for nearly every player: it was applied inside `_send_tinted_map`, which
    only runs when the looker has a damage aura, while the ordinary path lets
    the xyzgrid contrib msg the map itself. `automap off` reported success and
    the map kept appearing on every step.

    A policy nothing consults is not a policy, so these cases assert the
    consulting rather than the deciding.
    """

    def test_a_telnet_looker_is_left_alone(self):
        """The contrib's own default must keep applying to everyone else."""
        self.assertNotIn("map_display", _kwargs(_Looker(protocols=("telnet",))))

    def test_a_godot_looker_has_the_contrib_map_turned_off(self):
        """`map_display` is the contrib's own switch, and setting it False is
        the only way to stop it -- it msg's the map rather than returning it."""
        prepared = _kwargs(_Looker(protocols=(feed_const.GODOT_PROTOCOL_KEY,)))

        self.assertIs(prepared["map_display"], False)

    def test_the_players_setting_beats_a_caller_asking_for_a_map(self):
        """`automap` is the player's, and a caller asking on their behalf is
        asking wrongly. Nothing in the game passes this except GridTile."""
        looker = _Looker(protocols=(feed_const.GODOT_PROTOCOL_KEY,))
        prepared = _kwargs(looker, {"map_display": True})

        self.assertIs(prepared["map_display"], False)

    def test_automap_on_beats_the_client_default(self):
        """The whole point of the override: a Godot player can have the text
        map back, and this is the path that has to honour it."""
        looker = _Looker(
            protocols=(feed_const.GODOT_PROTOCOL_KEY,), override=True)

        self.assertNotIn("map_display", _kwargs(looker))

    def test_other_kwargs_are_carried_through(self):
        """It sits in front of every `look`, so dropping a kwarg here would
        break room display in ways nothing else would explain."""
        prepared = _kwargs(_Looker(protocols=("telnet",)),
                           {"map_visual_range": 3})

        self.assertEqual(prepared["map_visual_range"], 3)

    def test_the_callers_dictionary_is_never_mutated(self):
        """The aura branch writes `map_display` into what this returns, and
        `return_appearance` was given that dict by somebody else."""
        given = {"map_visual_range": 3}

        _kwargs(_Looker(protocols=(feed_const.GODOT_PROTOCOL_KEY,)), given)

        self.assertEqual(given, {"map_visual_range": 3})

    def test_the_suppression_lives_in_one_place(self):
        """`_send_tinted_map` must NOT re-check.

        It did, and the redundancy hid the real bug: with two owners it looked
        as though the decision was being made, so nobody asked which paths
        reached it.
        """
        source = inspect.getsource(GridTile._send_tinted_map)

        self.assertNotIn("_wants_ascii_map", source)

    def test_every_appearance_path_goes_through_the_seam(self):
        """A second `super().return_appearance` added without it would restore
        exactly the bug this file was written for."""
        source = inspect.getsource(GridTile.return_appearance)

        self.assertIn("_appearance_kwargs", source)
        self.assertNotIn("super().return_appearance(looker, map_display=",
                         source)
