@tool
class_name DialogueServerCheck
extends RefCounted
## Runs the server check of the dialogue scripts from the editor
## (DESIGN-0017): `python -m systems.gameplay.dialogue` in the game directory.
##
## The compiler of Dialogue Manager accepts each name that an author types.
## Only the server knows the dialogue vocabulary, the quest keys, and the
## features that the dialogue runner reads. Thus, the plugin runs this check
## after each script export, and the author sees each fault in the Output
## panel with no terminal.
##
## The Python is the one of [FigurePipeline]: the virtualenv of the repo.
## [method OS.execute] has no working directory, so the program goes to the
## game directory first. A run takes some seconds, because it starts Django.
## The plugin runs it on a thread ([FigureJob]). A test calls [method run]
## as it is.

## The module that holds the check, from the game directory.
const MODULE := "systems.gameplay.dialogue"

## The flag that also writes the editor stub ([DialogueStub]) from the
## dialogue vocabulary. Thus, a new vocabulary entry reaches the editor at
## the next save of a script.
const WRITE_STUB_FLAG := "--write-stub"

## Go to the game directory, and run the module as a command with the
## arguments after its name.
const RUN_PROGRAM := "import os, runpy, sys; game = sys.argv[1]; os.chdir(game); " \
	+ "sys.path.insert(0, game); sys.argv = sys.argv[2:]; " \
	+ "runpy.run_module(sys.argv[0], run_name='__main__')"

## What the job says while it runs, as the work of [FigureJob].
const LABEL := "the server check of the dialogue scripts"


## Run the check for the game directory `game`, or for this repo with "".
## Returns `{ok, output}`: true for exit code 0, and the printed lines.
static func run(game := "") -> Dictionary:
	var directory := DialogueScriptExport.game_directory() if game.is_empty() else game
	var output := []
	var code := OS.execute(FigurePipeline.python_of(directory),
		PackedStringArray(["-c", RUN_PROGRAM, directory, MODULE, WRITE_STUB_FLAG]),
		output, true)

	return {"ok": code == 0, "output": "\n".join(output).strip_edges()}
