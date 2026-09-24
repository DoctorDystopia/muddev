extends Node
## Unit tests for PanelView -- the control-panel tab strip.
##
##     godot --headless --path godot res://tests/test_panel_view.tscn
##
## Needs nothing running. The bodies are bare Controls: this file is about
## where a tab is and what it is called, never about what is drawn in it.

var _failures := 0
var _panel: PanelView


func _ready() -> void:
	_a_panel_is_added_under_its_title()
	_a_tab_is_selected_by_title_not_by_index()
	_an_index_shift_does_not_move_the_wrong_tab()
	_an_unknown_title_changes_nothing()
	_a_hidden_tab_keeps_its_body()
	_the_strip_never_takes_the_keyboard()
	_every_tab_fits_with_no_scroll_arrows()
	_a_narrow_strip_keeps_the_current_label()
	_every_tab_has_an_icon_a_tooltip_and_a_credit()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: panel_view")
	get_tree().quit(0)


## A fresh panel, in the tree. TabContainer does its bookkeeping on entering
## one; a detached panel reports no tabs and every case below would pass for
## the wrong reason.
func _fresh() -> void:
	if _panel != null:
		_panel.queue_free()

	_panel = PanelView.new()
	add_child(_panel)


func _body() -> Control:
	return Control.new()


func _a_panel_is_added_under_its_title() -> void:
	_fresh()
	var body := _body()
	_panel.add_panel(PanelView.TAB_CHARACTER, body)

	_expect(_panel.get_tab_count() == 1, "the tab exists")
	_expect(_panel._title_at(0) == PanelView.TAB_CHARACTER,
		"and carries the title it was given")
	_expect(body.get_parent() == _panel,
		"and the panel reparented the body itself")


func _a_tab_is_selected_by_title_not_by_index() -> void:
	_fresh()
	_panel.add_panel(PanelView.TAB_INVENTORY, _body())
	_panel.add_panel(PanelView.TAB_CHARACTER, _body())
	_panel.add_panel(PanelView.TAB_OPTIONS, _body())

	_panel.select_panel(PanelView.TAB_OPTIONS)
	_expect(_panel.current_tab == 2, "the named tab comes to the front")

	_panel.select_panel(PanelView.TAB_INVENTORY)
	_expect(_panel.current_tab == 0, "and so does an earlier one")


func _an_index_shift_does_not_move_the_wrong_tab() -> void:
	# The whole reason tabs are addressed by title. An index is a number two
	# files have to agree on, and they agree until somebody inserts a tab --
	# at which point the Character button opens Options and nothing errors.
	_fresh()
	_panel.add_panel(PanelView.TAB_CHARACTER, _body())
	_panel.add_panel(PanelView.TAB_OPTIONS, _body())

	_panel.select_panel(PanelView.TAB_OPTIONS)
	var before := _panel.current_tab

	# A tab arrives in the middle, as one would if the scene grew a child.
	var inserted := _body()
	_panel.add_panel(PanelView.TAB_HELP, inserted)
	_panel.move_child(inserted, 0)

	_panel.select_panel(PanelView.TAB_OPTIONS)
	_expect(_panel.current_tab != before,
		"the index of Options moved, as the setup intended")
	_expect(_panel._title_at(_panel.current_tab) == PanelView.TAB_OPTIONS,
		"and selecting it by title still lands on Options")


func _an_unknown_title_changes_nothing() -> void:
	# A miss here is a programming error, not a player one. Moving the player
	# to an arbitrary tab would be a worse answer than doing nothing.
	_fresh()
	_panel.add_panel(PanelView.TAB_CHARACTER, _body())
	_panel.add_panel(PanelView.TAB_OPTIONS, _body())
	_panel.select_panel(PanelView.TAB_OPTIONS)

	_panel.select_panel("Spellbook")

	_expect(_panel.current_tab == 1, "the player stays where they were")
	_expect(_panel.get_tab_count() == 2, "and no tab was invented")


func _a_hidden_tab_keeps_its_body() -> void:
	# set_tab_hidden and not `visible`: a TabContainer owns its children's
	# visibility, so hiding a body directly leaves the tab in the strip
	# pointing at nothing.
	_fresh()
	_panel.add_panel(PanelView.TAB_INVENTORY, _body())
	_panel.add_panel(PanelView.TAB_CHARACTER, _body())

	_panel.set_panel_hidden(PanelView.TAB_INVENTORY, true)

	_expect(_panel.is_tab_hidden(0), "the tab is hidden")
	_expect(_panel.get_tab_count() == 2, "but it is still a tab")

	_panel.set_panel_hidden(PanelView.TAB_INVENTORY, false)
	_expect(not _panel.is_tab_hidden(0), "and it comes back")

	# An unknown title is a no-op here too, rather than an index error.
	_panel.set_panel_hidden("Spellbook", true)
	_expect(_panel.get_tab_count() == 2, "hiding a tab nothing carries is safe")


## Same rule as the chat strip: opening the character sheet must not turn the
## player's next keystroke into a movement command.
func _the_strip_never_takes_the_keyboard() -> void:
	_fresh()

	_expect(_panel.focus_mode == Control.FOCUS_NONE,
		"the container refuses focus")
	_expect(_panel.get_tab_bar().focus_mode == Control.FOCUS_NONE,
		"and so does the tab bar")


## Every tab the console adds, in the console's order.
func _full_strip() -> void:
	_fresh()

	for title: String in PanelView.TAB_ICONS:
		_panel.add_panel(title, _body())


## The bug this mode table fixed: eight labels need more width than the
## shipped box, and the strip showed scroll arrows. At ANY width, the mode
## that the panel picks must fit, except at a width too narrow for icons.
func _every_tab_fits_with_no_scroll_arrows() -> void:
	_full_strip()
	var icons_only := _panel._strip_width(PanelView.LABELS_NONE)

	for width: float in [icons_only, PanelDock.DEFAULT_SIZE.x, 2000.0]:
		_panel.size = Vector2(width, 300)
		_expect(_panel._strip_width(_panel.label_mode) <= width,
			"at %d px the strip fits in mode %s" % [width, _panel.label_mode])

	_panel.size = Vector2(2000, 300)
	_expect(_panel.label_mode == PanelView.LABELS_ALL,
		"a wide strip shows every label")

	for index: int in _panel.get_tab_count():
		_expect(_panel.get_tab_title(index) == _panel._title_at(index),
			"and tab %d shows its title" % index)


func _a_narrow_strip_keeps_the_current_label() -> void:
	_full_strip()
	# The widest label decides the width, so the mode holds on every tab.
	var current := 0.0

	for index: int in _panel.get_tab_count():
		_panel.current_tab = index
		current = maxf(current, _panel._strip_width(PanelView.LABELS_CURRENT))

	_panel.current_tab = 0
	_panel.size = Vector2(current, 300)
	_expect(_panel.label_mode == PanelView.LABELS_CURRENT,
		"a strip too narrow for every label keeps the current one")
	_expect(_panel.get_tab_title(_panel.current_tab) != "",
		"so the current tab shows its title")

	var other := (_panel.current_tab + 1) % _panel.get_tab_count()
	_expect(_panel.get_tab_title(other) == "", "and the others show icons")

	# A tab change moves the label, and the new strip must still fit.
	_panel.current_tab = other
	_expect(_panel.get_tab_title(other) != "", "the label follows the tab")
	_expect(_panel._strip_width(_panel.label_mode) <= _panel.size.x,
		"and the strip still fits")

	_panel.size = Vector2(_panel._strip_width(PanelView.LABELS_NONE), 300)
	_expect(_panel.label_mode == PanelView.LABELS_NONE,
		"a very narrow strip shows icons only")


## A tab with no icon shows a blank tab in the icon modes, so every tab the
## console adds must have a row. The Credits box reads the same rows, so an
## icon with no credit is not possible.
func _every_tab_has_an_icon_a_tooltip_and_a_credit() -> void:
	_full_strip()

	for index: int in _panel.get_tab_count():
		var title := _panel._title_at(index)

		_check_tab(title, index)

	var credits := PanelView.icon_credits()
	_expect(credits.size() == PanelView.TAB_ICONS.size(),
		"every icon has one credit row")

	for credit: Dictionary in credits:
		_expect(not str(credit["author"]).is_empty()
			and str(credit["url"]).begins_with("https://game-icons.net/"),
			"the credit %s names its author and its page" % credit["title"])


func _check_tab(title: String, index: int) -> void:
	_expect(_panel.get_tab_icon(index) != null, "%s has an icon" % title)
	_expect(_panel.get_tab_bar().get_tab_tooltip(index) == title,
		"%s has its title as a tooltip" % title)


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
