extends Node
## Unit tests for the fetch settings of ModelLoader. Needs no server: no
## request here joins the tree, so none connects.
##
##     godot --headless --path godot res://tests/test_model_loader.tscn

var _failures := 0


func _ready() -> void:
	_one_read_holds_every_served_model()
	_a_failure_that_can_pass_is_retried()
	_a_missing_file_is_not_retried()
	_the_retries_stop()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: model_loader")
	get_tree().quit(0)


func _one_read_holds_every_served_model() -> void:
	# On the web, a request reads one chunk for each frame. A model that needs
	# many frames hits the timeout when the shader warm-up freezes them.
	var http := ModelLoader.new_request()
	var largest := _largest_served_model()

	_expect(largest > 0, "the served model tree has a model to measure")
	_expect(http.download_chunk_size >= largest,
		"one read holds the largest served model (%d bytes)" % largest)
	_expect(http.timeout == ModelLoader.TIMEOUT_SECONDS,
		"the request has the loader's timeout")

	http.free()


func _a_failure_that_can_pass_is_retried() -> void:
	_expect(ModelLoader._can_retry(HTTPRequest.RESULT_TIMEOUT, 0, 0),
		"a timeout is retried")
	_expect(ModelLoader._can_retry(HTTPRequest.RESULT_CONNECTION_ERROR, 0, 0),
		"a lost connection is retried")
	_expect(ModelLoader._can_retry(HTTPRequest.RESULT_SUCCESS,
		HTTPClient.RESPONSE_BAD_GATEWAY, 0), "a 5xx is retried")


func _a_missing_file_is_not_retried() -> void:
	_expect(not ModelLoader._can_retry(HTTPRequest.RESULT_SUCCESS,
		HTTPClient.RESPONSE_NOT_FOUND, 0), "a 404 fails at once")


func _the_retries_stop() -> void:
	_expect(not ModelLoader._can_retry(HTTPRequest.RESULT_TIMEOUT, 0,
		ModelLoader.RETRIES), "no retry after the last one")


## The size in bytes of the largest `.glb` in the served model tree, or 0.
func _largest_served_model() -> int:
	var root := ProjectSettings.globalize_path("res://").path_join(
		"../blackout/web/static/webclient/models")
	var largest := 0
	var stack: Array[String] = [root]

	while not stack.is_empty():
		var directory: String = stack.pop_back()

		for child: String in DirAccess.get_directories_at(directory):
			stack.append(directory.path_join(child))

		for file: String in DirAccess.get_files_at(directory):
			if file.get_extension() != "glb":
				continue

			var path := directory.path_join(file)
			var size := FileAccess.get_file_as_bytes(path).size()

			largest = maxi(largest, size)

	return largest


func _expect(condition: bool, label: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("  FAIL: " + label)
