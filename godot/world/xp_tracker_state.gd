class_name XpTrackerState
extends RefCounted
## Every XP award this session, from `blackout_xp`: what the XP drops and the
## session tracker draw.
##
## ## The server says what was earned; the SESSION is this client's
##
## Each `blackout_xp` message is one award as the player earned it -- every
## skill one action taught, with where each skill's curve stood afterwards.
## That is a fact about the game and the server owns it. How much of it has
## happened "this session", and how fast, is not: it is a reading taken by the
## client watching, the way RuneLite's XP tracker is a plugin rather than a
## game feature. So the totals and the clock live here, and nothing about them
## is ever sent back.
##
## A session starts at the first award and ends at [method reset] -- a dropped
## socket, or the player asking from Options. A drop ends it for the reason
## every other model clears on one: a websocket close ends the Evennia
## Session, so a tracker still counting afterwards would be timing a character
## nobody is puppeting.
##
## ## Why XP per hour waits
##
## A rate is XP over elapsed time, and elapsed time starts at the first award.
## Two seconds into a fight one swing reads as tens of thousands an hour, which
## is a number a player will quote and is wrong. [method rate_per_hour] answers
## [constant NO_RATE] until [constant RATE_WARMUP_SECONDS] have passed, and a
## view draws that as "--" rather than as a guess.
##
## ## It knows no skill keys
##
## Rows, names and categories arrive on every award. A skill added on the
## server is tracked the first time it pays anything, with no client edit --
## the same contract [SkillsState] keeps for the roster.
##
## **Every number in a parsed payload is a float.** Converted at ingest, as
## every other model here does it.

## Server-owned names, generated from blackout/systems/interface/statefeed/constants.py.
const _Const := preload("res://autoload/blackout_constants.gd")

## How long a session must have run before a rate is shown at all.
const RATE_WARMUP_SECONDS := 30.0

const SECONDS_PER_HOUR := 3600.0

## What a rate reads as before it means anything. Not zero: zero XP an hour is
## a real reading, and a player idling in a bank should be able to see it.
const NO_RATE := -1

## Fired after an award is folded in, so a view redraws the totals first.
signal changed

## One award landed. Fired once per `blackout_xp` message, AFTER [signal
## changed], with the message's `kind` and its parsed rows -- so a drop can be
## drawn against a tracker that already includes it.
signal dropped(kind: String, awards: Array)

## True once anything has been earned this session.
var has_data := false

## Every XP point earned this session, across every skill.
var total_xp := 0

## [member clock] reading at the session's first award.
var started_at := 0.0

## The skill the progress bar follows: the first row of the latest award,
## which is the primary skill of whatever the player just did.
var focus_key := ""

## Seconds, monotonic. A Callable so a test can move time without waiting --
## the only way a rate over an hour gets a test that runs in milliseconds.
var clock: Callable

## skill_key -> {skill_key, name, category, xp, started_at, level, current_xp,
## needed_xp}. `xp` and `started_at` are this session's; the rest is the latest
## award's reading.
var _skills: Dictionary = {}

## Skill keys in the order they were first trained this session.
var _order: Array[String] = []


func _init() -> void:
	clock = func() -> float: return Time.get_ticks_msec() / 1000.0


## Fold one feed message into this model.
##
## Returns true when the payload was one of ours, so the console can route
## without restating the channel name. A message of ours with nothing usable in
## it is still ours: it is consumed and changes nothing.
func ingest(channel: String, payload: Dictionary) -> bool:
	if channel != _Const.CH_XP_DROP:
		return false

	var awards := _awards(payload.get("awards", []))

	if awards.is_empty():
		return true

	var now: float = clock.call()

	if not has_data:
		started_at = now
		has_data = true

	for award: Dictionary in awards:
		_record(award, now)

	focus_key = str(awards[0]["skill_key"])

	changed.emit()
	dropped.emit(str(payload.get("kind", "")), awards)

	return true


## End the session. Called when the socket drops and when the player asks.
func reset() -> void:
	has_data = false
	total_xp = 0
	started_at = 0.0
	focus_key = ""
	_skills = {}
	_order = []

	changed.emit()


## This session's XP per hour, or [constant NO_RATE] while warming up.
func session_rate() -> int:
	if not has_data:
		return NO_RATE

	var now: float = clock.call()

	return rate_per_hour(total_xp, now - started_at)


## One skill's XP per hour since IT was first trained this session.
##
## Timed from the skill's own first award rather than the session's: a player
## who fought for an hour and then butchered for five minutes has not been
## earning Butchery for an hour.
func skill_rate(skill_key: String) -> int:
	if not _skills.has(skill_key):
		return NO_RATE

	var entry: Dictionary = _skills[skill_key]
	var now: float = clock.call()

	return rate_per_hour(int(entry["xp"]), now - float(entry["started_at"]))


## The row the progress bar follows, or `{}` before any award.
func focus_row() -> Dictionary:
	return _skills.get(focus_key, {})


## One row per skill trained this session, in the order they were first trained.
func skill_rows() -> Array:
	var rows: Array = []

	for key: String in _order:
		rows.append(_skills[key])

	return rows


## XP over elapsed seconds, as a whole number per hour.
##
## Static and pure, so the arithmetic and the warm-up rule are tested with no
## clock at all.
static func rate_per_hour(xp: int, elapsed_seconds: float) -> int:
	if elapsed_seconds < RATE_WARMUP_SECONDS:
		return NO_RATE

	return roundi(float(xp) * SECONDS_PER_HOUR / elapsed_seconds)


func _record(award: Dictionary, now: float) -> void:
	var key: String = award["skill_key"]
	var amount: int = award["amount"]

	total_xp += amount

	if not _skills.has(key):
		_skills[key] = {"skill_key": key, "xp": 0, "started_at": now}
		_order.append(key)

	var entry: Dictionary = _skills[key]
	entry["xp"] = int(entry["xp"]) + amount
	entry["name"] = award["name"]
	entry["category"] = award["category"]
	entry["level"] = award["level"]
	entry["current_xp"] = award["current_xp"]
	entry["needed_xp"] = award["needed_xp"]


## The rows worth keeping, as ints. A row with no key or nothing earned is
## dropped: a drop reading "+0" describes an award the server never made.
func _awards(raw: Variant) -> Array:
	var rows: Array = []

	if typeof(raw) != TYPE_ARRAY:
		return rows

	for entry: Variant in raw:
		if typeof(entry) != TYPE_DICTIONARY:
			continue

		var key := str(entry.get("skill_key", ""))
		var amount := int(entry.get("amount", 0))

		if key.is_empty() or amount <= 0:
			continue

		rows.append({
			"skill_key": key,
			"name": str(entry.get("name", key)),
			"category": str(entry.get("category", "")),
			"amount": amount,
			"level": int(entry.get("level", 0)),
			"current_xp": int(entry.get("current_xp", 0)),
			"needed_xp": int(entry.get("needed_xp", 0)),
		})

	return rows
