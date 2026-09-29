"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/29/2026
Description: Tests for `attack` on a target out of reach. The player walks to
             the target, and the arrival starts the attack.

The defect: a click on a raider walked the player to its tile. The game then
said "You begin attacking" and, in the same tick, "The combat is over. You
won!" A second click worked.

The walk moves on the tick, at PHASE_START. The arrival runs the follow-up
`attack` in that phase, and `attack` makes a handler. The engine took its
snapshot of the rotation AFTER the START hooks. Thus, the new handler ticked
in the same pass, before the INPUT phase gave it a target. It saw no enemy,
ended its own combat, and deleted itself with the queued attack.
"""

from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from systems.core.tick.engine import PHASE_FEED, PHASE_START, get_tick_engine
from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import movement
from systems.core.tilegrid.world import TileWorld, set_world
from systems.gameplay.combat import pvp
from systems.gameplay.combat.combat import ensure_combat_handler
from systems.gameplay.movement import walk
from typeclasses.npc_combat import spawn_mutant_raider


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = tile_const.CHUNK_SIZE

_START = (10, 10)
_NEXT_TO_START = (11, 10)

# The text of the message that the defect sent.
_WON_KEYWORD = "you won"


# ─── Private helper routines ─────────────────────────────────────────────────

def _open_world() -> TileWorld:
    tile_count = _SIZE * _SIZE
    chunk_file = chunkfile.ChunkFile(
        cx=0, cy=0, plane=0, floor_names=["sand"], area_names=["oasis"],
        heights=[0] * tile_const.CORNERS_PER_SIDE ** 2,
        floors=[0] * tile_count, flags=[0] * tile_count,
        areas=[0] * tile_count, objects=[])
    world = TileWorld([chunk_file])
    world.rooms.load()

    return world


def _texts(seen: list) -> list:
    """The plain text of every line that `msg` received, lower case."""
    texts = []

    for entry in seen:
        text = entry[0] if isinstance(entry, tuple) else entry
        texts.append(str(text).lower())

    return texts


# ─── Tests ───────────────────────────────────────────────────────────────────

class AHandlerMadeInTheStartPhaseTests(EvenniaTest):
    """The engine rule under the defect. A handler made in a tick first ticks
    in the next tick. The phase that made it does not matter."""

    def setUp(self):
        super().setUp()
        pvp.set_pvp(self.char1, True)
        pvp.set_pvp(self.char2, True)

        self.engine = get_tick_engine()
        self.engine.ndb._handler_ids = {}
        self.engine.ndb._handler_strikes = {}
        self.engine.ndb._inbound_actions = []

        self.seen = []
        self.char1.msg = lambda text=None, **kwargs: self.seen.append(text)

    def _start_an_attack(self):
        """What a walk arrival does: make a handler and queue an attack."""
        handler = ensure_combat_handler(self.char1)
        handler.queue_action({"kind": "attack", "target": self.char2})
        self.handler = handler

    def _tick_with_start_hook(self, count: int = 1):
        hooks = {PHASE_START: [self._start_an_attack], PHASE_FEED: []}

        with mock.patch("systems.core.tick.engine._PHASE_HOOKS", hooks):
            self.engine._tick()

            for _ in range(count - 1):
                hooks[PHASE_START].clear()
                self.engine._tick()

    def test_the_new_handler_survives_its_first_tick(self):
        self._tick_with_start_hook()

        self.assertIsNotNone(self.handler.pk)

    def test_the_new_handler_does_not_announce_a_win(self):
        self._tick_with_start_hook()

        for text in _texts(self.seen):
            self.assertNotIn(_WON_KEYWORD, text)

    def test_the_attack_lands_on_the_second_tick(self):
        self._tick_with_start_hook(count=2)

        self.assertEqual(self.handler.ndb.target_id, self.char2.id)


class AttackWalkTests(EvenniaTest):
    """The report: `attack` on a raider that stands on the next tile. The
    test uses the real command, the real walk, and the real tick."""

    def setUp(self):
        super().setUp()
        self.engine = get_tick_engine()
        self.engine.ndb._handler_ids = {}
        self.engine.ndb._handler_strikes = {}
        self.engine.ndb._inbound_actions = []

        world = _open_world()
        set_world(world)
        movement.place(world.rooms, self.char1, *_START, quiet=True)
        self.raider = spawn_mutant_raider(world.rooms.ensure_room(*_NEXT_TO_START))

        self.seen = []
        self.char1.msg = lambda text=None, **kwargs: self.seen.append(text)

    def tearDown(self):
        walk.forget_all()
        set_world(None)
        super().tearDown()

    def _click_the_raider(self):
        self.char1.execute_cmd(f"attack #{self.raider.id}")

    def test_the_attack_starts_a_walk(self):
        self._click_the_raider()

        self.assertIsNotNone(walk.current(self.char1))

    def test_the_arrival_does_not_end_the_fight_it_starts(self):
        self._click_the_raider()

        self.engine._tick()  # the walk arrives and queues the attack

        for text in _texts(self.seen):
            self.assertNotIn(_WON_KEYWORD, text)

    def test_the_fight_holds_a_handler_after_the_arrival(self):
        self._click_the_raider()

        self.engine._tick()

        handler = self.char1.combat
        self.assertIsNotNone(handler)

    def test_the_second_tick_aims_the_attack_at_the_raider(self):
        self._click_the_raider()

        self.engine._tick()
        self.engine._tick()

        self.assertEqual(self.char1.combat.ndb.target_id, self.raider.id)
