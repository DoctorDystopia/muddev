class_name ScrollbackFind
extends RefCounted
## Finding a word in the game log: which matches exist, and which one you are on.
##
## The browser gave `Ctrl+F` away for free and a canvas does not, so this is one
## of the affordances ENG-0006 §3.1 says to rebuild rather than drop — a MUD log
## is the transcript of everything that has happened to you, and not being able
## to search it is a real loss.
##
## Pure. It is handed a haystack and a needle and answers with offsets; nothing
## here knows about a RichTextLabel, a scrollbar or a widget. That is what makes
## the cycling rules — which are the part that gets fiddly — testable without a
## screen.
##
## ## The rules
##
## **Case-insensitive.** Players type `raider`, the log says `Mutant Raider`.
## A case-sensitive default would find nothing and look broken.
##
## **Wraps at both ends.** Past the last match goes to the first; back past the
## first goes to the last. A find that stops dead at the end makes the player
## wonder whether it is still working.
##
## **Overlapping matches count once each, left to right.** Searching `aa` in
## `aaaa` finds matches at 0 and 2, not 0, 1 and 2 — stepping forward should
## move past what is highlighted, not one character.

## The needle, as last searched. Empty means no active search.
var query := ""

## Character offsets into the haystack, ascending.
var _matches: PackedInt32Array = []

## Index into `_matches`. -1 when there is no current match.
var _current := -1


## Search `haystack` for `needle` and select the first match.
##
## Returns the number of matches. An empty needle clears the search rather than
## matching everywhere, which is what an emptied find box should do.
func search(haystack: String, needle: String) -> int:
	query = needle
	_matches = PackedInt32Array()
	_current = -1

	if needle.is_empty() or haystack.is_empty():
		return 0

	var lowered := haystack.to_lower()
	var target := needle.to_lower()
	var from := 0

	while true:
		var found := lowered.find(target, from)

		if found < 0:
			break

		_matches.append(found)
		# Step past the whole match, not one character: stepping forward should
		# move past what is highlighted.
		from = found + target.length()

	if not _matches.is_empty():
		_current = 0

	return _matches.size()


## Move to the next match and return its offset, or -1 when there are none.
func next() -> int:
	if _matches.is_empty():
		return -1

	_current = (_current + 1) % _matches.size()

	return _matches[_current]


## Move to the previous match and return its offset, or -1 when there are none.
func previous() -> int:
	if _matches.is_empty():
		return -1

	_current = (_current - 1 + _matches.size()) % _matches.size()

	return _matches[_current]


## The offset of the match currently selected, or -1.
func current() -> int:
	if _current < 0 or _current >= _matches.size():
		return -1

	return _matches[_current]


func match_count() -> int:
	return _matches.size()


## Which match is selected, 1-based for display. 0 when there is none.
func current_number() -> int:
	if _current < 0:
		return 0

	return _current + 1


## A label for the find bar: "3 / 12", or what went wrong.
##
## Rendered here rather than in the widget so the empty and no-match wordings
## have one place and one test — they are the two states a player actually
## reads, and the widget would otherwise grow branches for both.
func status_text() -> String:
	if query.is_empty():
		return ""

	if _matches.is_empty():
		return "no matches"

	return "%d / %d" % [current_number(), match_count()]
