class_name CommandHistory
extends RefCounted
## The up-arrow. What was typed, and where in it the player currently is.
##
## Pure logic with no widget in it, so the rules can be tested without a
## keyboard — which matters because most of them are the sort that feel obvious
## and are wrong in half the clients that implement them.
##
## The rules, and why each is here:
##
## **Submitting always returns to the end.** Typing a command and pressing enter
## puts you back at a blank line, not two-thirds of the way up where you were
## browsing. Anything else means the next up-arrow jumps somewhere unrelated.
##
## **A draft is preserved.** Half-typing something, pressing up to check an old
## command, then pressing down again gives the half-typed text back. Losing it
## is the single most irritating bug this class can have.
##
## **Consecutive duplicates collapse.** `look` five times is one entry, because
## a history that makes you press up five times to get past your own repetition
## is worse than no history.
##
## **Empty lines are not stored.** Pressing enter on a blank line is not a
## command and must not push the real history down.

## How many commands to keep. Generous -- these are short strings -- but bounded,
## because a client left running for a week should not grow without limit.
const CAPACITY := 200

## Oldest first. The most recent command is the last entry.
var _entries: PackedStringArray = []

## Where the player is looking. `_entries.size()` means "at the end, in the
## draft"; anything lower is an index into `_entries`.
var _cursor := 0

## What was being typed before browsing started. Restored on arriving back.
var _draft := ""


## Record a submitted command and return to the end.
func push(line: String) -> void:
	var trimmed := line.strip_edges()

	if not trimmed.is_empty():
		var last := "" if _entries.is_empty() else _entries[_entries.size() - 1]

		if trimmed != last:
			_entries.append(trimmed)

		if _entries.size() > CAPACITY:
			_entries = _entries.slice(_entries.size() - CAPACITY)

	_cursor = _entries.size()
	_draft = ""


## Step back. Returns the line to show, or "" when there is nothing older.
##
## `current` is what is in the field right now, so a half-typed draft can be
## kept before browsing away from it.
func previous(current: String) -> String:
	if _entries.is_empty():
		return current

	if _cursor == _entries.size():
		_draft = current

	if _cursor > 0:
		_cursor -= 1

	return _entries[_cursor]


## Step forward. Returns the line to show, which at the end is the draft.
func next(_current: String) -> String:
	if _entries.is_empty():
		return _draft

	if _cursor < _entries.size():
		_cursor += 1

	if _cursor == _entries.size():
		return _draft

	return _entries[_cursor]


## True while the player is browsing rather than typing fresh.
func is_browsing() -> bool:
	return _cursor < _entries.size()


## How many commands are remembered.
func size() -> int:
	return _entries.size()
