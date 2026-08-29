extends Node
## Guard for the client's one Theme.
##
##     godot --headless --path godot res://tests/test_theme.tscn
##
## The asymmetry this encodes is the same one `test_client_constants.py` states
## for the generated constants, one level down:
##
##     A variation a script NAMES and the theme does not declare is a BUG --
##     the control silently falls back to the default style, which looks like a
##     styling mistake rather than a typo and is exactly how the dead
##     "Pole clearing" room-kind key survived in two clients.
##
##     A variation the theme declares and nothing names yet is FINE. A style may
##     legitimately ship ahead of the screen that uses it, so those are printed
##     rather than failed.
##
## Scripts are read as TEXT rather than instantiated, for the reason the Python
## scanner gives: reading is safe from anywhere, and building the console to ask
## it about its labels would need a socket.

const THEME_PATH := "res://ui/blackout_theme.tres"

## Where a variation may be named. Directories, scanned recursively for `.gd`
## and `.tscn`.
const SEARCH_ROOTS := ["res://scenes", "res://world"]

var _failures := 0


func _ready() -> void:
	var theme: Theme = load(THEME_PATH)

	if theme == null:
		printerr("FAIL: %s did not load" % THEME_PATH)
		get_tree().quit(1)
		return

	var declared := _declared_variations(theme)

	_every_variation_has_a_real_base(theme, declared)
	_every_named_variation_is_declared(declared)

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: theme")
	get_tree().quit(0)


## Every type in the theme that declares a base type -- i.e. every variation.
func _declared_variations(theme: Theme) -> Dictionary:
	var found: Dictionary = {}

	for type_name: String in theme.get_type_list():
		var base := theme.get_type_variation_base(type_name)

		if not String(base).is_empty():
			found[type_name] = String(base)

	return found


## A variation whose base is not a real class styles nothing, silently.
func _every_variation_has_a_real_base(theme: Theme, declared: Dictionary) -> void:
	_expect(not declared.is_empty(), "the theme declares at least one variation")

	for type_name: String in declared:
		var base: String = declared[type_name]
		_expect(ClassDB.class_exists(base),
			"%s is based on the real class %s" % [type_name, base])

		# A variation with a base and no items of its own is a declaration that
		# does nothing -- which reads as "this is styled" at every call site.
		var has_items := (theme.get_color_list(type_name).size()
			+ theme.get_constant_list(type_name).size()
			+ theme.get_font_size_list(type_name).size()
			+ theme.get_stylebox_list(type_name).size()) > 0
		_expect(has_items, "%s actually sets something" % type_name)


## Every variation any script or scene names must exist in the theme.
func _every_named_variation_is_declared(declared: Dictionary) -> void:
	# Every StringName literal, not only `theme_type_variation = &"..."`.
	# Half the variations in this client are PASSED rather than assigned --
	# `_row_label(text, &"RowKey")` -- and a scan that only matched the
	# assignment reported three real variations as unused and would have
	# missed a typo in all four call sites that spell them.
	#
	# This is sound only while a StringName literal in this client is ALWAYS
	# a theme variation, which it is today (checked: the only other `&` is a
	# `split("&")`). If one is ever used for a signal or a node path, narrow
	# the pattern rather than deleting the check.
	#
	# `[ ]*` and not a backslash class: GDScript rejects an unknown escape
	# in a string literal, so the obvious spelling is a PARSE error -- and a
	# script that fails to load leaves a headless run with no output at all,
	# because nothing is ever built to call quit().
	var pattern := RegEx.create_from_string(
		"&\"([A-Za-z0-9_]+)\"")
	var named: Dictionary = {}

	for root: String in SEARCH_ROOTS:
		_collect(root, pattern, named)

	_expect(not named.is_empty(),
		"the scan found at least one named variation (a scan that finds "
		+ "nothing is a scan that has stopped testing)")

	for variation: String in named:
		_expect(declared.has(variation),
			"\"%s\" is declared in the theme (named by %s)"
				% [variation, named[variation]])

	for variation: String in declared:
		if not named.has(variation):
			print("  note %s is declared and unused" % variation)


## Read every .gd and .tscn under `path`, recording which variations each names.
func _collect(path: String, pattern: RegEx, into: Dictionary) -> void:
	var dir := DirAccess.open(path)

	if dir == null:
		return

	dir.list_dir_begin()

	var entry := dir.get_next()

	while not entry.is_empty():
		var full := path.path_join(entry)

		if dir.current_is_dir():
			_collect(full, pattern, into)
		elif entry.ends_with(".gd") or entry.ends_with(".tscn"):
			var text := FileAccess.get_file_as_string(full)

			for hit: RegExMatch in pattern.search_all(text):
				into[hit.get_string(1)] = entry

		entry = dir.get_next()

	dir.list_dir_end()


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
