class_name CreditsState
extends RefCounted
## The model credits, read from the served `credits.json`.
##
## The model pipeline (`blackout/assets/pipeline`) writes that file from the
## source records: one entry for each download that a served model uses. CC-BY
## asks for a credit that follows the work to the player, and a file on the
## server is not in front of the player. [CreditsView] is.
##
## Pure, so a test can feed it a document with no network. A malformed entry is
## dropped and a malformed document gives an empty list: the credits are a
## courtesy screen, and a bad file must not break the Options pane.

## The fields every entry keeps, with the value an absent field reads as.
const _TEXT_FIELDS := ["title", "author", "url", "license", "license_url"]

## Entries, each {title, author, url, license, license_url, confirmed}.
var _entries: Array[Dictionary] = []

## True once a document has been ingested, whatever it held.
var _loaded := false


## Fold one parsed `credits.json` in, in place of anything held before.
##
## Returns how many entries survived. An entry with no title is dropped,
## because a row with nothing to name credits nobody.
func ingest(document: Variant) -> int:
	_loaded = true
	_entries.clear()

	if typeof(document) != TYPE_ARRAY:
		return 0

	for item: Variant in document:
		if typeof(item) != TYPE_DICTIONARY:
			continue

		var entry := _clean(item)

		if entry["title"].is_empty():
			continue

		_entries.append(entry)

	return _entries.size()


## Every entry, in the order the server sent (sorted by title).
func entries() -> Array[Dictionary]:
	return _entries


## Whether a document has arrived at all, even an empty one.
func loaded() -> bool:
	return _loaded


## One entry with every field present and typed.
##
## `confirmed` defaults to FALSE. A credit whose license the file does not
## vouch for must not be shown as confirmed.
static func _clean(item: Dictionary) -> Dictionary:
	var entry := {}

	for field: String in _TEXT_FIELDS:
		entry[field] = str(item.get(field, "")).strip_edges()

	var confirmed: Variant = item.get("confirmed", false)

	entry["confirmed"] = typeof(confirmed) == TYPE_BOOL and confirmed

	return entry
