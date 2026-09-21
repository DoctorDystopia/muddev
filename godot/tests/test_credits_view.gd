extends Node
## Unit tests for CreditsView.
##
##     godot --headless --path godot res://tests/test_credits_view.tscn
##
## Needs nothing running. The view is bound to no URL, so it never fetches,
## and each case gives it a document by hand.

var _failures := 0


func _ready() -> void:
	_it_starts_hidden_and_opens_on_request()
	_every_credit_gets_a_row_and_an_unconfirmed_one_says_so()
	_the_close_button_hides_it_with_no_server_round_trip()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: credits_view")
	get_tree().quit(0)


func _fresh() -> CreditsView:
	var view := CreditsView.new()
	add_child(view)
	view.bind("")

	return view


func _texts(node: Node, into: PackedStringArray) -> PackedStringArray:
	if node is Label:
		into.append((node as Label).text)

	if node is LinkButton:
		into.append((node as LinkButton).text)

	for child: Node in node.get_children():
		_texts(child, into)

	return into


func _it_starts_hidden_and_opens_on_request() -> void:
	var view := _fresh()

	_expect(not view.visible, "the box starts hidden")
	view.open()
	_expect(view.visible, "open shows it")
	view.queue_free()


func _every_credit_gets_a_row_and_an_unconfirmed_one_says_so() -> void:
	var view := _fresh()
	view.open()
	view.show_document([
		{"title": "Rusty sword", "author": "Leoskateman", "url": "https://a",
			"license": "CC BY 4.0", "license_url": "https://b",
			"confirmed": true},
		{"title": "Robot", "author": "Modo", "url": "https://c",
			"license": "License not confirmed", "license_url": "",
			"confirmed": false},
	])

	var texts := _texts(view, PackedStringArray())

	_expect(texts.has("Rusty sword") and texts.has("Robot"),
		"every credit is drawn")
	_expect(texts.has("by Leoskateman"), "the author is named")
	_expect(texts.has("CC BY 4.0"), "the license is named")
	_expect(texts.has(CreditsView.UNCONFIRMED_TEXT),
		"an unconfirmed license is marked")
	_expect(texts.count(CreditsView.UNCONFIRMED_TEXT) == 1,
		"and only the unconfirmed one")
	view.queue_free()


func _the_close_button_hides_it_with_no_server_round_trip() -> void:
	var view := _fresh()
	view.open()

	for button: Node in view.find_children("*", "Button", true, false):
		if (button as Button).text == CreditsView.CLOSE_TEXT:
			(button as Button).pressed.emit()

	_expect(not view.visible, "the close button hides the box at once")
	view.queue_free()


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
