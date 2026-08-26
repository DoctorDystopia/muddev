# Blackout — Godot client

Graphical client for the Blackout MUD. Talks to Evennia's `godotwebsocket`
contrib port (`4008`, set in `blackout/server/conf/settings.py`).

Plan, phases and design decisions:
[docs/2026-08-25-ENG-0006-godot-option-a-plan.md](../docs/2026-08-25-ENG-0006-godot-option-a-plan.md),
with the decision it implements in
[docs/2026-08-25-ENG-0005-godot-vs-webclient.md](../docs/2026-08-25-ENG-0005-godot-vs-webclient.md).

> This used to link `docs/2026-08-08-ENG-0005-godot-client-plan.md`, which was
> never written — checked with `git log --all --diff-filter=A`. ENG-0005 is now
> the decision record and ENG-0006 the plan.

**This project renders through Compatibility (OpenGL 3.3 / WebGL 2.0), not
Forward+.** The web export cannot use Forward+ at all — Forward+ and Mobile are
unsupported on the web platform and Godot has no WebGPU backend as of 4.7 — so
the desktop build and the editor are held to the renderer the browser will
actually use. `renderer/rendering_method="gl_compatibility"`, under
`[rendering]`; the key is *not* `rendering_method`, because the section header
already supplies the `rendering/` prefix. There is no `rendering_method.web`
override and none is needed. See ENG-0006 §4.

> **Do not put explanation in `project.godot`.** It said all of the above in
> `;` comments for about an hour, and opening the editor once rewrote the file
> and stripped every one of them — which the file's own header warns it will
> do. Setting values there is fine; the reasons have to live here.

**Status: all twelve state-feed channels consumed.** Text game on the left, the
3D world and the inventory on the right, a vitals strip above the log and a
character sheet behind a button. The world pane draws tile grids per map, the
links between them, room-kind colours, a marker on the room you are standing
in, the NPCs and items in it, a white flash on anything you land a hit on, and
your aura ring.

| Input | Does |
|---|---|
| **Left-click a tile** | Walks there, if it is adjacent and has an exit |
| **Left-click an NPC** | `attack <name>` |
| **Left-click an item** | `get <name>` |
| **Left-click a gathering node** | `cut <name>` — harvested where it stands, never pocketed |
| **Left-click a player** | Nothing, deliberately — see rule 3 below |
| **Drag an inventory cell** | Swap, equip or unequip — whichever the server named |
| **Right-click an inventory cell** | The item's own actions, as the server listed them |
| **Character button** | Opens the sheet — whatever panels `char_summary` sent |
| **Options button** | Text size and interface scale, saved between runs |
| **Up / Down in the input** | Walks the command history; a half-typed draft is kept |
| **Right-drag** | Orbit the camera |
| **Wheel** | Zoom |

## Running

Start the game server first — the client connects on load and reports the
failure in the feed pane if nothing is listening.

```bash
cd blackout && ../evenv/Scripts/evennia.exe start
```

Then open `godot/` in Godot 4.7 and press F5, or run it headless. Godot is not
on PATH on this machine; the 4.7.1 build lives in an extracted folder that is
itself named `...exe`, so the binary path repeats:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --path godot
```

Log in through the form at the top of the text column, or by typing the same
thing into the input field — they send the identical line:

```
connect <name> <password>
```

The form exists for the password field, which can be masked where a shared
command line cannot be, and for the **Paste** button on web builds. See rule 6
below.

The client does **not** subscribe when the socket opens — that is a race it
loses whenever the Server is still starting. It waits for the server to
announce an empty subscription set at `ServerSession.at_sync`, and answers
that. The same message is what lets it recover from an `evennia reload`, which
wipes the Session ndb subscriptions live on without dropping the socket.

The world snapshot arrives when you puppet a character, pushed by
`Character.at_post_puppet`.

To see the recovery for yourself: with the client connected, run
`evennia reload`, and the feed pane logs `server has no subscription for us;
subscribing` followed by a fresh `subscribed: ...`.

## Tests

All ten are headless and exit non-zero on failure.

> **After adding a `class_name`, run `--headless --path godot --import` once
> before running anything headless.** Global class names live in
> `.godot/global_script_class_cache.cfg`, which is rebuilt by an editor scan and
> is gitignored. A plain `--headless` run does not rebuild it, so a brand-new
> `class_name` fails as `Identifier "..." not declared in the current scope` —
> which reads like a typo and is not one. A fresh clone needs this too.

`test_world_state.tscn` needs **nothing running** — its payloads are hand-built
in the shape Godot's JSON parser produces:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_world_state.tscn
```

`test_char_state.tscn` needs nothing running either:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_char_state.tscn
```

`test_model_registry.tscn` needs nothing running either:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_model_registry.tscn
```

`test_inventory_state.tscn` needs nothing running either:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_inventory_state.tscn
```

`test_inventory_view.tscn` needs nothing running either:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_inventory_view.tscn
```

`test_summary_state.tscn` needs nothing running either:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_summary_state.tscn
```

`test_login_view.tscn` needs nothing running either:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_login_view.tscn
```

`test_command_history.tscn` and `test_client_settings.tscn` need nothing
running either:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_command_history.tscn
```

`smoke_handshake.tscn` needs a running Evennia but no account —
`blackout_subscribe` is answered on an unauthenticated session:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/smoke_handshake.tscn
```

## Layout

| File | Owns |
|---|---|
| `autoload/evennia.gd` | The socket. The only place that knows the `[name, args, kwargs]` wire format. |
| `scenes/console.tscn` `.gd` | The shell: output, input, and the subscription handshake. |
| `scenes/world.tscn` | The 3D scene: environment, light, islands, marker, camera rig. |
| `world/world_state.gd` | The world model. Chunk reassembly and the float boundary. |
| `world/char_state.gd` | YOUR model: entity id, hp, in_combat, skill levels. |
| `world/model_registry.gd` | Which assets have art (fetched) and how each is oriented (not). |
| `world/inventory_state.gd` | Carried grid and worn slots. |
| `scenes/inventory/inventory_view.gd` | Draws the grid and the paper doll; turns a gesture into a command. |
| `scenes/inventory/slot_cell.gd` | One frame. Drag/drop is Godot's engine API, not hand-rolled. |
| `world/summary_state.gd` | The dossier. Knows no panel names and must not learn any. |
| `scenes/summary/summary_view.gd` | The sheet, a native `Window`. Iterates panels, never enumerates them. |
| `scenes/login/login_view.gd` | Name, password, connect/create. Hides itself when vitals arrive. |
| `world/command_history.gd` | The up-arrow. Pure rules, no widget. |
| `world/client_settings.gd` | Font size and UI scale, via ConfigFile under `user://`. |
| `scenes/options/options_view.gd` | The two sliders. Writes through the settings object, applies nothing. |
| `scenes/hud.tscn` `.gd` | Draws char_state above the text pane. Presentation only. |
| `world/world_view.gd` | Drawing tiles, links, islands and the marker. Owns the browser-parity hash and colours. |
| `world/entity_pool.gd` | Whatever is standing in your room, and the hit flash. |
| `world/orbit_camera.gd` | The `SpringArm3D` follow rig. |

Four rules worth not rediscovering:

1. **Decode with `get_string_from_utf8()`.** The contrib's own README example
   uses `get_string_from_ascii()`, which mangles the box-drawing that the
   dossier and every section rule in the game are built from.
2. **Every number in a parsed payload is a float.** `JSON.parse_string` returns
   `{"x": 3.0, "num": 19863.0}` — always. A dictionary keyed on that will not
   match a key written as `3`, and nothing raises. `WorldState` converts at the
   point of use; do the same rather than coercing whole payloads, because the
   first genuinely fractional field the server grows would be corrupted
   silently.
3. **The client acts only through `Evennia.command()`**, which sends the same
   `text` a telnet player types. Clicking a tile sends `north` — never a
   position. There is no privileged client channel, so every lock, cooldown and
   permission keeps working with nothing to re-audit. Clicking another player
   is wired to do nothing on purpose: every other misclick is recoverable, and
   opening combat on a person is not.
4. **The output pane's monospace font is load-bearing**, not cosmetic. Godot's
   default theme font is proportional and the game draws ASCII art constantly.
6. **On the web, Ctrl+V into a LineEdit may not paste, and the failure is
   silent.** Godot's export listens for the DOM `paste` event, but its
   `clipboard_get` reads `navigator.clipboard.readText()` -- the
   permission-gated path -- and swallows a rejection in an empty `catch`, so a
   refused read looks exactly like an empty clipboard. Without user activation
   that read is refused in both engines, and Firefox does not support the
   `clipboard-read` permission at all, so there is nothing to grant once. The
   login form's **Paste button** is the floor: a click IS user activation, so
   the read that fails from a keystroke succeeds from a button. Desktop is
   unaffected -- Ctrl+V is native there.
5. **Anything both panes draw must match.** The two get put side by side on the
   same character, so a difference has to mean a bug. That is why
   `WorldView.stable_hash` reimplements the JS string hash instead of calling
   Godot's, and why the HSL-to-HSV conversion beside it is closed-form rather
   than matched by eye. Both have test vectors computed from the JS directly.
