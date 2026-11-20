# Dialogue scripts

A dialogue script is what an NPC says, as one `.dialogue` file in this
directory. You write it in the **Dialogue** tab of the Godot editor
(Dialogue Manager). The server runs it. The design note is
`docs/2026-11-11-DESIGN-0017-dialogue-scripts.md`.

## Write a new dialogue

1. Open the **Dialogue** tab at the top of the editor.
2. Make a new file in `res://dialogue/`. The file name is the key of the
   script, for example `gate_guard.dialogue`.
3. Write the script. Start with a `~ start` cue.
4. Save. The Output panel shows `[dialogue] written  gate_guard.json`, and
   then the result of the server check.
5. Name the script in the `NpcDef` of the NPC: `dialogue_script="gate_guard"`.

A save reaches a running game with no reload. The next `talk` uses the new
script. A new `NpcDef` field needs a reload, as each Python change does.

## A short script

```
~ start
if quest.is_complete("augmentation_intro")
	=> done
{{npc.header}}
Guard: Halt, {{player.name}}.
- Who are you? => who
- Leave => END

~ who
Guard: The guard of this gate.
- Back => start

~ done
Guard: You may pass.
=> END

~ farewell
Guard: Move along.
```

## The rules

- **A cue is a start point:** `~ name`. Each script has a `~ start` cue.
- **`Name: text` is speech.** The server shows it in the speech colour. A
  line with no name is narration, and it stays plain.
- **Use `{{npc.name}}:` for the NPC of the conversation.** The game shows no
  name in front of its lines, because the pop-up title names it. A line of
  each other speaker shows the name in front. A new name of the NPC needs no
  edit here.
- **Write plain text.** The server applies the colours.
- **A line with one more tab continues the line above it.** The two show
  with no empty line between them. Two lines at the same indent show with
  one empty line between them.
- **A response starts with `- `.** A jump can follow it on the same line
  (`- Leave => END`), or lines can follow it with one more tab.
- **One beat is the lines up to the next responses.** The player reads them
  as one text and then picks a response.
- **`=> cue` jumps. `=> END` ends the conversation.** `=>< cue` jumps and
  comes back when that cue ends.
- **End each cue with `=> END` or a jump.** A cue with no end continues into
  the cue below it. The server check refuses that.
- **`do` runs an action,** for example `do quest.accept("key")`. It runs when
  the server reaches the line. Put it under a response to run it after the
  player picked that response.
- **`if`, `elif`, `else`, and `match` / `when` choose a path.** A response
  can have a condition: `- Bribe [if quest.is_active("key") /]`.
- **The `~ farewell` cue is the parting line.** The game says it when the
  conversation ends, by a response or by a walk away. A script with no
  farewell cue gets the generic farewell.
- **A colon splits a line.** `Note: read this` is speech by "Note". Write
  `Note\: read this` for narration with a colon. A response keeps its colon.

## The dialogue vocabulary

A script can call only these names. A name that is not here is a fault of
the server check.

| Name | Kind | What it gives or does |
|---|---|---|
| `player.name` | value | The name of the player character |
| `npc.name` | value | The name of the NPC |
| `npc.description` | value | The description of the NPC, as `look` shows it |
| `npc.heading` | value | The name of the NPC as a heading |
| `npc.header` | value | The name as a heading, and the description below it |
| `quest.is_available(quest)` | query | True if the player can take the quest now |
| `quest.is_active(quest)` | query | True while the player has the quest |
| `quest.is_complete(quest)` | query | True after the player completed the quest |
| `quest.on_step(quest, step)` | query | True while the player is on this step |
| `quest.reported(quest, action, target)` | query | True if the current step already has this target |
| `quest.title(quest)` | query | The title of the quest |
| `quest.accept_prompt(quest)` | query | The line that asks the player to take the quest |
| `quest.objectives(quest)` | query | The objective lines, under a heading |
| `recipe.name(recipe)` | query | The name of a recipe |
| `memory.recall(key, default)` | query | The value that the player keeps under a memory key, or the default if none |
| `quest.accept(quest)` | action | The player takes the quest |
| `quest.talk(quest, target)` | action | Report a talk target to the quest |
| `quest.report(quest, action, target)` | action | Report a target of any quest action, for example a chore with no system yet |
| `message.success(text)` | action | Send one line to the log of the player, in the success colour |
| `memory.remember(key, value)` | action | Keep a value for the player under a memory key |

A value has no brackets. A query and an action have brackets. Only a `do`
line can call an action.

## Keep a choice of the player

A script cannot change a variable. To keep what the player chose, write the
value into the dialogue memory. A later cue or a later talk reads it back:

```
~ analysis_raider
do memory.remember("human_reading", 72)
...

~ post_quest
{{npc.name}}: "East, [{{memory.recall("human_reading", 82)}}% human]."
```

- **The server keeps the value on the player character.** It stays after a
  logout.
- **A memory key is snake_case.** Each script reads and writes the same
  memory. Thus, a different NPC can recall a key that the android
  remembered.
- **Each argument is a literal:** a text, a number, or `true` / `false`.
- **A recall gives its default** to a player with no value under the key,
  for example a player who talked to the NPC before the script kept it.
- **A second remember of the same key replaces the value.**
- **A recall can choose a path too:** `if memory.recall("opener", "polite") == "raider"`,
  or `match memory.recall("opener", "polite")`.
- **The server check refuses a recall of a key that no script remembers.**
  Such a recall always gives its default.

A new name is one decorated function in
`blackout/systems/gameplay/dialogue/vocab_defs/`. Add its row to this table.
The next save of a script writes the editor stub again
(`addons/blackout_dialogue/dialogue_stub.gd`), so the test run knows the
name.

## What the server refuses

The editor accepts more than the server runs. The server check finds each
difference and names the line:

- A `while` loop, a random line (`%`), and `[[a|b]]` in a text
- `[wait=1]`, `[speed=2]`, `[next]`, and `[if ...]` inside a text
- A tag (`[#mood]`), a concurrent line (`| Name: text`), and an import
- `set`, arithmetic, an array, and a dictionary in an expression. To keep
  a value, use `memory.remember`
- A jump to an expression (`=> {{...}}`)
- A quest key, a step key, a quest target, or a recipe that names nothing
- A memory key that is not snake_case, and a recall of a key that no script
  remembers

The order of `and` and `or` is the order of the addon: the server splits an
expression at its last `and` or `or`. Thus, `a or b and c` is
`(a or b) and c`. Use brackets when a condition has both.

## The test run in the editor

The **Run** button of the Dialogue tab runs the script with no game behind
it. It opens the test scene of this project
(`addons/blackout_dialogue/dialogue_test_scene.tscn`):

- **One switch for each yes or no query** of the script, for example
  `quest.is_active("augmentation_intro")`. Each query is false until you set
  its switch. The scene keeps the switches of each script between runs.
- **Restart** starts the script again with the switches as they are.
- **A text shows its call in angle brackets,** for example `<npc.name>`. The
  scene knows no NPC, no quest, and no dialogue memory. A `memory.recall`
  also shows its call.
- **An action only goes into the list** at the bottom of the panel. It
  changes no switch. After `do quest.accept(...)`, set the switch yourself.

The test run shows the flow. It does not run the server check, and it does
not show the colours of the game. For those, save the script and use `talk`
in a running game.

## Without the editor

```bash
# Write each compiled script again:
godot --headless --path godot -s res://addons/blackout_dialogue/export_cli.gd

# Check only. Exit code 1 if a compiled script is out of date:
godot --headless --path godot -s res://addons/blackout_dialogue/export_cli.gd -- --check

# The server check, from blackout/:
python -m systems.gameplay.dialogue

# The server check, and the editor stub of the vocabulary:
python -m systems.gameplay.dialogue --write-stub
```

The compiled scripts are in `blackout/world/npc_dialogues/compiled/`. Never
edit one by hand. A test fails if a compiled script is out of date.
