class_name ReconnectPolicy
extends RefCounted
## When to try the socket again after it drops, and how long to wait.
##
## Pure logic with no timer in it, so the schedule can be tested without
## waiting for one — which is the only way this is testable at all, since every
## interesting case here is measured in seconds.
##
## ## Why the client needs this and the webclient did not
##
## The browser client got two recoveries free that a canvas does not. Evennia's
## `evennia.js` offers "Not currently connected. Reconnect?" on the next thing
## the player types, and falls back to AJAX long-polling when a websocket never
## opens at all — which is what carries players on networks that block them.
## Godot has neither. Before this class the client printed one grey line and
## sat there dead until the page was reloaded.
##
## ## The schedule, and why each part
##
## **Exponential, from one second.** The overwhelmingly common drop is a brief
## one — a wifi handover, a laptop lid, an `evennia stop/start` — and those
## reconnect on the first or second try. Starting at a second means the player
## usually never reads the message.
##
## **Capped.** Growth without a ceiling means a client left running overnight
## through an outage waits hours after the server returns. The cap is what
## makes "come back in the morning and it is connected" true.
##
## **Never gives up.** There is no attempt limit, because the alternative is a
## client that has decided on the player's behalf that the game is not coming
## back. At the cap this costs one connection attempt every thirty seconds,
## which is nothing, and the player can always close the window.
##
## ## What a reconnect does NOT restore
##
## Stated here because it is the thing most likely to be misread. A websocket
## close ends the Evennia Session, so a new socket is a NEW session at the
## connection screen — the character is not re-puppeted and the player logs in
## again. That is also exactly what the webclient does. This class buys back
## the route to the login prompt, not the session behind it; see
## [LoginView] on why the form has to come back when the socket drops.
##
## No jitter, deliberately: jitter exists to spread a thundering herd across
## many clients, one client reconnecting to its own server is not a herd, and
## it would make every case here untestable for nothing.

## What to wait before the first retry.
const FIRST_DELAY_SECONDS := 1.0

## The ceiling. See the class comment on why there is one.
const MAX_DELAY_SECONDS := 30.0

## How fast the wait grows per failed attempt.
const GROWTH := 2.0

## How many consecutive failures have been recorded. Zero while connected.
##
## Read by the console purely to tell the player which attempt this is; nothing
## about the schedule branches on it beyond [method delay_for].
var attempts := 0


## The wait before attempt `attempt`, in seconds.
##
## `attempt` is 1-based: attempt 1 is the first retry after a drop. Anything
## lower is treated as 1 rather than refused, so a caller that has not yet
## recorded a failure still gets a usable number instead of an error.
##
## Static and pure, which is what lets the whole schedule be asserted as a
## table in the test rather than observed a second at a time.
static func delay_for(attempt: int) -> float:
	var step := maxi(attempt, 1) - 1
	var delay := FIRST_DELAY_SECONDS * pow(GROWTH, float(step))

	return minf(delay, MAX_DELAY_SECONDS)


## Record a drop and return how long to wait before trying again.
func next_delay() -> float:
	attempts += 1

	return delay_for(attempts)


## Forget the failures. Called when a socket opens.
func reset() -> void:
	attempts = 0


## True once the schedule has reached its ceiling.
##
## Exists so the console can stop counting attempts at the player and say
## "retrying every 30s" instead, which is more useful than "attempt 47".
func at_ceiling() -> bool:
	return is_equal_approx(delay_for(attempts), MAX_DELAY_SECONDS)
