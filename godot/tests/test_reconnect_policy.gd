extends Node
## Unit tests for ReconnectPolicy.
##
##     godot --headless --path godot res://tests/test_reconnect_policy.tscn

var _failures := 0


func _ready() -> void:
	_the_first_retry_is_quick()
	_the_wait_doubles_per_failure()
	_the_wait_is_capped()
	_it_never_gives_up()
	_a_successful_connection_forgets_the_failures()
	_the_ceiling_is_reported()
	_delay_for_tolerates_a_zeroth_attempt()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: reconnect_policy")
	get_tree().quit(0)


## The common drop is a brief one, so the player should rarely read the message.
func _the_first_retry_is_quick() -> void:
	var policy := ReconnectPolicy.new()

	_expect(is_equal_approx(policy.next_delay(), 1.0),
		"the first retry waits one second")
	_expect(policy.attempts == 1, "and counts as one attempt")


## Asserted as a table, which is the whole reason delay_for is pure and static.
func _the_wait_doubles_per_failure() -> void:
	var expected := {1: 1.0, 2: 2.0, 3: 4.0, 4: 8.0, 5: 16.0}

	for attempt: int in expected:
		_expect(is_equal_approx(ReconnectPolicy.delay_for(attempt), expected[attempt]),
			"attempt %d waits %.0fs" % [attempt, expected[attempt]])


## Without a ceiling, a client left running through an outage waits hours after
## the server comes back.
func _the_wait_is_capped() -> void:
	for attempt: int in [6, 7, 20, 500]:
		_expect(ReconnectPolicy.delay_for(attempt) <= ReconnectPolicy.MAX_DELAY_SECONDS,
			"attempt %d does not exceed the cap" % attempt)

	_expect(is_equal_approx(ReconnectPolicy.delay_for(500),
		ReconnectPolicy.MAX_DELAY_SECONDS),
		"a long outage settles exactly on the cap")


## There is no attempt limit; the alternative is a client that decides for the
## player that the game is not coming back.
func _it_never_gives_up() -> void:
	var policy := ReconnectPolicy.new()

	for _i: int in 100:
		policy.next_delay()

	_expect(policy.attempts == 100, "it keeps counting")
	_expect(policy.next_delay() > 0.0, "and still offers a delay")


func _a_successful_connection_forgets_the_failures() -> void:
	var policy := ReconnectPolicy.new()

	policy.next_delay()
	policy.next_delay()
	policy.next_delay()
	policy.reset()

	_expect(policy.attempts == 0, "reset clears the count")
	_expect(is_equal_approx(policy.next_delay(), 1.0),
		"so the next drop is quick again rather than resuming the backoff")


## The console says "retrying every 30s" past this point instead of counting.
func _the_ceiling_is_reported() -> void:
	var policy := ReconnectPolicy.new()

	_expect(not policy.at_ceiling(), "a fresh policy is not at the ceiling")

	for _i: int in 20:
		policy.next_delay()

	_expect(policy.at_ceiling(), "twenty failures is well past it")


## A caller that has not recorded a failure yet still gets a usable number.
func _delay_for_tolerates_a_zeroth_attempt() -> void:
	for attempt: int in [0, -1, -99]:
		_expect(is_equal_approx(ReconnectPolicy.delay_for(attempt),
			ReconnectPolicy.FIRST_DELAY_SECONDS),
			"attempt %d is treated as the first" % attempt)


func _expect(condition: bool, what: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("  not true: %s" % what)
