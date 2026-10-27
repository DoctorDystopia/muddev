# Audio credits

Every clip under `audio/`, where it came from, and the licence it arrived
under. Add a row in the same commit as the clip — a file with no row is
indistinguishable from one whose licence nobody checked.

The sound wizard (`python -m assets.audio add`, see "To add a sound" in
`godot/README.md`) adds the row, or a new pack section at the end. It
changes no other line. The check of `assets.audio` fails for a clip of the
cue table with no row here.

**Source packs never live in this repo.** Only the clips the client actually
plays are copied in; the packs themselves stay in
`C:\Users\NickR\Games\Projects\Godot\Assets\`. See "Sound is the client's" in
`godot/README.md` for why.

---

## Ovani Sound — Sound FX Starter Pack Vol. 1

Royalty-free licence: https://ovanisound.com/policies/terms-of-service

- Commercial use in a game is permitted.
- Credit for Sound FX packs is not required.
- The content may **not** be distributed, sold or sublicensed on its own,
  separated from the game it is part of — which is what committing the pack
  here would do.

| Clip | Source file in the pack | Changes |
|---|---|---|
| `sfx/level_up.wav` | `Jingles & Stingers/Level Up.wav` | Renamed. Imported as mono (Force → Mono); the source file is unmodified. |
| `sfx/task_complete.wav` | `Hollywood/Knife Kills.wav` | Renamed. The source file is unmodified. |
| `sfx/metalsmith_craft.wav` | `Medieval/Metal Twang.wav` | Renamed. Imported as mono (Force → Mono). The source file is unmodified. |
| `sfx/foundry_craft.wav` | `Steampunk/Steampunk Gas Ignite.wav` | Renamed. Imported as mono (Force → Mono). The source file is unmodified. |
| `sfx/transition.wav` | `Motions and Impacts/Whoosh Cyberwave.wav` | Renamed. Imported as mono (Force → Mono). The source file is unmodified. |
| `sfx/guns_shot.wav` | `Hollywood/Titan Handgun.wav` | Renamed. Imported as mono (Force → Mono). The source file is unmodified. |

## Enzo — Flesh and Fracture - Lite

Bought by Nick. The pack holds no licence file, only a thank-you note to the
buyer. Thus, this repo holds only the clips that the client plays, and not
the pack.

| Clip | Source file in the pack | Changes |
|---|---|---|
| `sfx/butcher_attempt.wav` | `Flesh Tearing/Flesh Tearing_T.Bone  (1).wav` | Renamed. Imported as mono (Force → Mono). The source file is unmodified. |
| `sfx/cut_attempt.wav` | `Axe Chops/Axe Chop_MKE 600  (1).wav` | Renamed. Imported as mono (Force → Mono). The source file is unmodified. |

## Hove Audio — Sword Combat Sound Effects Pack Free Version

License: LicenseRef-Unconfirmed.

Exception to the license gate: The itch.io page states no license (checked 10/26/2026). It tags the pack Royalty Free, and the author says in a comment that no credit is necessary. Name-your-own-price is a price, not a grant. Ask the author, or replace the clip, before a public release.

Store page: https://hoveaudio.itch.io/sword-combat-sound-effects-pack-free-version

| Clip | Source file in the pack | Changes |
|---|---|---|
| `sfx/melee_swing.wav` | `Main Sounds/Sword Stabs/w_Whoosh/WEAPSwrd_SwordStabwWhoosh_HoveAud_SwordCombat_01.wav` | Renamed. Imported as mono (Force → Mono). The source file is unmodified. |
