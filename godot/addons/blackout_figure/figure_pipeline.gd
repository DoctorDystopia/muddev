@tool
class_name FigurePipeline
extends RefCounted
## Runs the model pipeline of the game directory from the figure workbench
## (DESIGN-0014, requirement A10). The author then uses no terminal.
##
## The workbench runs two commands of `python -m assets.pipeline`:
##
## - `figure-model` brings one model file in as a source and a model record,
##   and it builds the served model. The import button runs it.
## - `figure-set` writes `figure.json` again. A save of a rig or of a worn
##   look runs it, so the served file does not go stale.
##
## ## How the command starts
##
## The pipeline is a Python package of the game directory, and it reads its
## files from there. [method OS.execute] has no working directory. Thus,
## this class starts Python with a short program that goes to the game
## directory first, and then runs the package.
##
## The Python is that of the virtualenv of the repository, because the
## pipeline needs Python 3.11. With no virtualenv, it is the `python` of
## the PATH.
##
## A command blocks until it ends. A build of one model takes some
## seconds, so the plugin runs it on a thread ([FigureJob]). A test calls
## the routines as they are.

## The virtualenv of the repository, from the game directory. The first
## path that is there gives the Python.
const PYTHON_PATHS := ["../evenv/Scripts/python.exe", "../evenv/bin/python"]

const PATH_PYTHON := "python"

## The program that Python runs: go to the game directory, then run the
## pipeline package with the arguments after the directory.
const RUN_PROGRAM := "import os, runpy, sys; game = sys.argv[1]; os.chdir(game); " \
	+ "sys.path.insert(0, game); sys.argv = ['assets.pipeline'] + sys.argv[2:]; " \
	+ "runpy.run_module('assets.pipeline', run_name='__main__')"

const COMMAND_MODEL := "figure-model"
const COMMAND_SET := "figure-set"
const AUTHOR_FLAG := "--author"

## The family of a figure model that is no item: `FIGURE_FAMILY` of
## `assets/pipeline/figure.py`. The model of an item is in the `items`
## family, where the inventory finds it.
const FAMILY_FIGURE := "figure"
const FAMILY_ITEMS := "items"

## The package directory of the pipeline, under the game directory.
const PIPELINE_DIRECTORY := "assets/pipeline"


## The game directory of this repository: `blackout/`.
static func game_directory() -> String:
	var project := ProjectSettings.globalize_path("res://")

	return project.path_join(ChunkFile.GAME_DIRECTORY_FROM_PROJECT).simplify_path()


## True when the game directory has the model pipeline.
static func is_there(game := "") -> bool:
	var directory := game_directory() if game.is_empty() else game

	return DirAccess.dir_exists_absolute(directory.path_join(PIPELINE_DIRECTORY))


## The Python that runs the pipeline of one game directory.
static func python_of(game: String) -> String:
	for relative: String in PYTHON_PATHS:
		var path := game.path_join(relative).simplify_path()

		if FileAccess.file_exists(path):
			return path

	return PATH_PYTHON


## Run one command of the pipeline. Returns `{ok, output}`: true for exit
## code 0, and each line that the command printed.
static func run(arguments: PackedStringArray, game := "") -> Dictionary:
	var directory := game_directory() if game.is_empty() else game
	var output := []
	var full := PackedStringArray(["-c", RUN_PROGRAM, directory])

	if not is_there(directory):
		return {"ok": false, "output": "%s has no model pipeline." % directory}

	full.append_array(arguments)

	var code := OS.execute(python_of(directory), full, output, true)

	return {"ok": code == 0, "output": "\n".join(output).strip_edges()}


## Bring one model file in, and build it. `path` is an OS path. See
## [method run] for the result.
static func import_model(family: String, model_key: String, path: String,
		author := "", game := "") -> Dictionary:
	var arguments := PackedStringArray([COMMAND_MODEL, family, model_key, path])

	if not author.is_empty():
		arguments.append_array(PackedStringArray([AUTHOR_FLAG, author]))

	return run(arguments, game)


## Write `figure.json` again. See [method run] for the result.
static func write_figure_set(game := "") -> Dictionary:
	return run(PackedStringArray([COMMAND_SET]), game)
