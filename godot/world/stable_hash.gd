class_name StableHash
extends RefCounted
## A string hash that gives the same number on every client and every run.
##
## NOT Godot's `hash()`. `EntityPool` turns the ring of figures on a tile by
## this number, so a tile must give the same turn in every session. It came
## from `MapPalette`, which coloured the xyzgrid islands with it, and it moved
## here when DESIGN-0011 Phase 4b removed `MapPalette` (09/25/2026).
##
## It is JS's classic 31-multiply (`(h << 5) - h + c`) with ToInt32 applied
## on each step, which is what `hashString` in the retired blackout3d.js
## implemented. The mask gives that truncation. The fold at the end gives the
## SIGNED result of JS, and `absi` then gives what its Math.abs gave.
##
## A RefCounted with only static members: it is never instantiated.


## The hash of [param text], a non-negative int below 2^31.
static func of(text: String) -> int:
	var value := 0

	for code: int in text.to_utf8_buffer():
		value = ((value << 5) - value + code) & 0xFFFFFFFF

	if value >= 0x80000000:
		value -= 0x100000000

	return absi(value)
