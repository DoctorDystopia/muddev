class_name HitsplatStyle
extends Resource
## The look of one kind of hitsplat: the number over a figure that a swing hit.
##
## **Edit the look here, not in code.** Each kind is one `.tres` file in
## `res://world/hitsplats/styles/`. Double-click the file in the FileSystem
## dock, and the Inspector shows every field below in four groups. Save the
## file, and the next hitsplat uses the new values. No script changes.
##
## | File | Shows on |
## |---|---|
## | `hit.tres` | a swing that connected, 0 included |
## | `max_hit.tres` | a swing that rolled the top face of its damage die |
## | `miss.tres` | a swing that missed |
##
## [HitsplatLayer] picks the file. The SERVER decides which kind a swing is
## (`max_hit` in `blackout_combat`). This file decides only what it looks like.
##
## **Glow.** A colour channel above 1.0 is HDR. It glows only when the
## WorldEnvironment of `scenes/world.tscn` has glow on.


@export_group("Number")

## The font of the number. Empty uses the project default font.
@export var font: Font

## The size of the number, in font pixels. [member pixel_size] sets how large
## a font pixel is on the screen.
@export_range(8, 256, 1) var font_size := 48

## The colour of the number.
@export var color := Color(1.0, 1.0, 1.0)

## The width of the outline around each glyph, in font pixels. 0 is no outline.
@export_range(0, 64, 1) var outline_size := 12

## The colour of the outline.
@export var outline_color := Color(0.0, 0.0, 0.0)

## The text of the number. `{damage}` is the damage of the swing. Text with no
## `{damage}` shows as it is, for example "MISS".
@export var text_format := "{damage}"


@export_group("Detail line")

## The small line under the number. It shows only on a max hit that the damage
## channel changed: a bonus or a penalty after the roll. It tells the player
## why the number is not the max hit. `{max_hit}` is the roll, and `{change}`
## is the size of the change.
@export var detail_bonus_format := "MAX {max_hit} +{change} BONUS"

## The detail line for a penalty. See [member detail_bonus_format].
@export var detail_penalty_format := "MAX {max_hit} -{change} PENALTY"

## The size of the detail line, in font pixels.
@export_range(8, 256, 1) var detail_font_size := 22

## The colour of the detail line.
@export var detail_color := Color(1.0, 1.0, 1.0)

## How far the number stands above the detail line: the distance between
## their bottom edges, in font pixels. Pixels and not world units, so the gap
## keeps its size on the screen at every camera zoom.
@export_range(0, 256, 1) var detail_gap := 48


@export_group("Motion")

## The scale at the first frame. Above 1 starts large and shrinks: a "pop".
## 1 is no pop.
@export_range(0.1, 5.0, 0.05) var pop_scale := 1.0

## How long the pop takes to reach scale 1, in seconds.
@export_range(0.0, 2.0, 0.01) var pop_seconds := 0.1

## How far the hitsplat moves up over its life, in world units.
@export_range(0.0, 3.0, 0.01) var rise := 0.35

## How long the hitsplat stays fully visible after the pop, in seconds.
@export_range(0.0, 5.0, 0.01) var hold_seconds := 0.45

## How long the fade out takes, in seconds.
@export_range(0.0, 5.0, 0.01) var fade_seconds := 0.3


@export_group("Placement")

## The height above the top of the figure, in world units.
@export_range(0.0, 3.0, 0.01) var height := 0.15

## The largest random step sideways, in world units. It stops two quick
## hitsplats on one figure from covering each other. 0 is no step.
@export_range(0.0, 1.0, 0.01) var jitter := 0.12

## The size of one font pixel. A larger value gives larger text. With
## [member fixed_size] on, it is a fraction of the screen, so it is a much
## smaller number than with the option off.
@export_range(0.0001, 0.05, 0.0001) var pixel_size := 0.0008

## True keeps the text one size on the screen at every camera zoom, as OSRS
## does. False makes the text a thing in the world: small when far, large
## when near, as the sign labels are.
@export var fixed_size := true

## True draws the hitsplat over walls and figures. False lets them hide it.
@export var draw_on_top := true


## The full time that one hitsplat is on screen, in seconds.
func lifetime() -> float:
	return pop_seconds + hold_seconds + fade_seconds
