# The profiling harness

Measures the Blackout pipeline end to end — **Database → Evennia → Statefeed →
Protocol → Web** — and the test suite that exercises it.

Nothing in the game imports this package. That is the design constraint, not an
accident of it being new, and
[`tests/test_isolation.py`](tests/test_isolation.py) fails if it stops being
true.

---

## Running it

From `blackout/`:

```bash
python scripts/profile_pipeline.py
```

```bash
python scripts/profile_pipeline.py --list
```

```bash
python scripts/profile_pipeline.py --layer statefeed --layer database
```

```bash
python scripts/profile_pipeline.py --only serialize_area --show-profile
```

`--layer` and `--only` are repeatable; `--only` matches a case-insensitive
substring, so `--only serialize_area` picks up both radii. Artefacts land in
`blackout/profiling_out/` (gitignored):

| File | What it is |
|---|---|
| `audit_report.txt` | The table, grouped by pipeline layer |
| `audit_report.json` | The same run, machine-readable, with severities |
| `<scenario>.prof` | One `pstats` dump per scenario, for `snakeviz` |

The process exits non-zero when the worst row is `critical`, so CI can gate on
it the way it gates on `export_client_constants.py --check`.

### It cannot touch your data

Every scenario runs inside a Django **test** database that is created for the
run and destroyed after it. That is structural, not careful: the run happens
inside a `TestCase`, so there is no code path from the harness to the
development database at all. CLAUDE.md's first warning is that a loop over this
repo's modules once deleted 347 grid rooms — a tool that spawns characters and
arms combat handlers hundreds of times is exactly that shape, and it does not
go near live data.

---

## Profiling the test suite

Off by default. Arm it with an environment variable:

```bash
BLACKOUT_PROFILE_TESTS=1 ../evenv/Scripts/evennia.exe test --settings test_settings.py systems.banking
```

You get three views on stderr, because they answer three different questions:

- **Slowest tests** — finds one pathological test.
- **Costliest classes** — finds an expensive `setUp` shared by a dozen cheap
  tests, which the per-test view spreads too thin to see.
- **By base class** — says what the suite's *floor* costs. This is how a claim
  like "the fixtures are most of the runtime" is made checkable rather than
  asserted.

For per-test rows as CSV:

```bash
BLACKOUT_PROFILE_TESTS=1 BLACKOUT_PROFILE_TESTS_OUTPUT=run.timings.csv ../evenv/Scripts/evennia.exe test --settings test_settings.py systems
```

An environment variable rather than a setting because `test_settings.py` is
loaded by everyone on every run, and a profiling flag living there is one
somebody commits as `True` and nobody notices for a month.

---

## Adding a scenario

One decorated function in one module under `scenarios/`. Nothing dispatches on
a name and nothing holds a list — the same arrangement `@register_spawner`
makes in `typeclasses/spawners.py`.

```python
@scenario(name="serialize_area radius 3",
          layer=const.LAYER_STATEFEED,
          repeat=10,
          notes="49 tiles, 3 objects each. The move-time area feed.")
def serialize_area_wide(world):
    rooms = world.rooms_within(3)          # setup -- NOT measured
    exclude = (world.character,)

    def work():                            # measured
        serializers.serialize_area(rooms, exclude=exclude)

    return work
```

**A scenario returns the work; it is not the work.** Everything before the
`return` is setup and is excluded from every number. Handing the harness the
work directly would fold fixture construction into the measurement, which makes
a profile blame whichever scenario has the most expensive setup.

The `layer` is **declared, not inferred**. A statefeed scenario that happens to
issue queries is still a statefeed scenario; grouping by what the code touches
would file it under `database` and lose the question being asked.
`constants.PIPELINE_LAYERS` closes the set, and an unknown layer raises at
import rather than mid-run.

---

## How a measurement is taken

`instruments.measure` runs the work **four times over, in four phases**:

1. **Warmup**, discarded — pays lazy imports, idmapper population, connection
   setup.
2. **Timing**, `repeat` passes, nothing else running. This owns the duration.
3. **Profiling**, one pass. This owns the call breakdown; its duration is
   thrown away.
4. **Query capture**, one pass.

Phases 2 and 3 cannot share a pass. `cProfile` costs a Python-level callback on
every call and return, which inflates a call-heavy routine far more than a
loop-heavy one — so a profiled duration does not merely add a constant, it
**reorders the audit**, promoting whichever scenario makes the most function
calls.

Phase 4 goes last because `CaptureQueriesContext` forces `DEBUG` on for its
block, and Django's debug cursor wrapper would otherwise be measured as though
it were the game's own cost.

### Severity

`instruments.py` records facts; `report.py` judges them. The split means
re-rendering a stored run cannot produce a different verdict than the run that
measured it would have.

Duration and query count are banded **separately** and a scenario takes the
worse of the two, because they fail differently: a slow scenario with three
queries is CPU work to optimise, while a fast scenario with three hundred
queries is an N+1 that is fast *only* because the test database is a local file
with no network in front of it.

The duration bands are anchored to `TICK_SECONDS` (0.6s). The tick is the one
place in the codebase where a measured duration converts directly into a
player-facing symptom: twisted's `LoopingCall` schedules on a fixed grid, so an
overrunning tick does not queue — it drifts, and the game stutters for every
player at once.

---

## Layout

| Module | Holds | May import |
|---|---|---|
| `constants.py` | Thresholds, env var names, layer names, output paths | nothing |
| `instruments.py` | `Measurement`, `measure`, `count_queries` | `constants` |
| `report.py` | Rendering and severity. Changes nothing, measures nothing | `constants` |
| `world_fixture.py` | The synthetic grid every scenario runs against | game typeclasses |
| `scenarios/` | The registry and one module per pipeline layer | the game |
| `harness.py` | The runner: test DB up, measure, tear down | all of the above |
| `testrunner.py` | The opt-in per-test instrument, as a **mixin** | `constants` |

`report.py` is split from `instruments.py` on the read/write line, the same
split `systems/devtools/dossier.py` makes against `actions.py`: a reader
looking at a profiling run needs to be able to tell at a glance which module
could have perturbed the numbers, and the answer has to be "not that one".

`testrunner.py` holds a **mixin**, not a runner, because measuring a suite and
configuring one are different jobs. `server/conf/testrunner.py` composes the
mixin over Evennia's runner and owns the run policy; this package owns only the
measurement.

---

## Two traps, both found the hard way

**Evennia's flat API is empty at import time.** `from evennia import
create_object` binds `None` if it runs before `evennia._init()`, and the
failure surfaces as `TypeError: 'NoneType' object is not callable` deep inside
a fixture. Import from the real module — `from evennia.utils.create import
create_object`.

**The test runner is not interchangeable.** `settings.TEST_RUNNER` points at
`EvenniaTestSuiteRunner`, whose `setup_test_environment` calls `evennia._init()`
and puts object #2 in place. A bare `DiscoverRunner` skips that and every
`create_object` dies on `settings.DEFAULT_HOME (= '#2') does not exist` — which
is the same failure CLAUDE.md records against `--parallel`, seen from a
different angle.
