@tool
class_name ClientExport
extends RefCounted
## Runs the two Python steps that follow a table file, from the terrain
## editor (10/14/2026). The plugin runs them after each change on the Tables
## tab, so the author uses no terminal:
##
## 1. `scripts/export_client_constants.py` writes the generated constants
##    again. The game reads the tables from them ([TileTables]).
## 2. `world/tests/check_fixture_builder.py` writes the check fixture again.
##    Its names come from the tables, and a test compares the committed
##    files with a fresh build.
##
## The Python is the one of [FigurePipeline]: the virtualenv of the repo.
## [method OS.execute] has no working directory, so the program goes to the
## game directory first, as the program of the pipeline does. The export
## starts Django with the real settings and opens no database. The builder
## then runs in the same process.
##
## A run takes some seconds. The plugin runs it on a thread ([FigureJob]).
## A test calls [method run] as it is.

## The export script, from the game directory.
const SCRIPT := "scripts/export_client_constants.py"

## Go to the game directory, run `main` of the export, and stop on a fault.
## Then write the check fixture.
const RUN_PROGRAM := "import os, runpy, sys; game = sys.argv[1]; os.chdir(game); " \
	+ "sys.path.insert(0, game); " \
	+ "code = runpy.run_path(os.path.join(game, sys.argv[2]))['main']([]); " \
	+ "code and sys.exit(code); " \
	+ "from world.tests import check_fixture_builder as fixture; " \
	+ "fixture.write_fixtures(); " \
	+ "print('  written  the check fixture, ' + fixture.FIXTURE_DIRECTORY)"

## What the job says while it runs, as the work of [FigureJob].
const LABEL := "the client constants and the check fixture"


## Run both steps for the game directory `game`, or for this repo with "".
## Returns `{ok, output}`: true for exit code 0, and the printed lines.
static func run(game := "") -> Dictionary:
	var directory := FigurePipeline.game_directory() if game.is_empty() else game
	var output := []

	if not FileAccess.file_exists(directory.path_join(SCRIPT)):
		return {"ok": false, "output": "%s has no %s." % [directory, SCRIPT]}

	var code := OS.execute(FigurePipeline.python_of(directory),
		PackedStringArray(["-c", RUN_PROGRAM, directory, SCRIPT]), output, true)

	return {"ok": code == 0, "output": "\n".join(output).strip_edges()}
