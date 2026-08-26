class_name ServerEndpoint
extends RefCounted
## Which server this client talks to, and how it decides.
##
## Pure: every input is a parameter, so the whole decision is testable without a
## web export, a tunnel, or a command line. [method resolve] is the one routine;
## everything else is a caller reading its own platform.
##
## ## The rule
##
##     an explicit override      -> use it, always
##     a debug build             -> the local dev server
##     anything else             -> production
##
## **Debug-versus-release rather than a platform check.** Running from the
## editor and running a debug export both mean somebody is developing, and both
## should reach `127.0.0.1`. A release export is a build handed to a player and
## must reach the real server. `OS.is_debug_build()` already draws that line, so
## no export preset needs a custom feature and no constant needs flipping before
## a release — which is exactly the kind of step that gets forgotten once.
##
## ## Why production is not derived from the page
##
## The obvious move on the web is to read `location` and talk back to whoever
## served the page. That is wrong here: under ENG-0006 §4.2 the export is served
## from the CDN beside the marketing site, and the socket lives on
## `game.playblackout.io`. Page origin and socket origin are DIFFERENT hosts by
## design, so deriving one from the other would send every player's client to a
## host that serves no websocket.
##
## The path prefix is what lets one hostname carry both the webserver and this
## socket. Verified against the contrib: Evennia's websocket protocol never
## reads `request.path` and autobahn accepts any, so `/godot` is free.

## Where a developer's server is. Matches the port in
## `blackout/server/conf/settings.py`.
const DEV_URL := "ws://127.0.0.1:4008"

## Where players connect. `wss`, because the page is served over TLS and a
## browser blocks a plain `ws://` from an HTTPS page as mixed content -- the
## exact failure INFRA-0001 §5.1 records for the webclient, which silently
## never connected.
const PRODUCTION_URL := "wss://game.playblackout.io/godot"

## Accepted on the command line as `--server=<url>` and, on the web, as a
## `?server=<url>` query parameter.
const OVERRIDE_KEY := "server"

## Schemes an override may use. Anything else is refused rather than dialled:
## an override is a development convenience, and one that could point the
## client at `http://` or a file would fail in a way that looks like the server
## being down.
const ALLOWED_SCHEMES := ["ws://", "wss://"]


## Decide the endpoint.
##
## `override` is whatever the command line or query string supplied, or "".
## `is_debug` is `OS.is_debug_build()` at the call site.
static func resolve(override: String, is_debug: bool) -> String:
	var wanted := override.strip_edges()

	if not wanted.is_empty() and is_valid(wanted):
		return wanted

	return DEV_URL if is_debug else PRODUCTION_URL


## Is this a URL worth dialling?
static func is_valid(url: String) -> bool:
	for scheme: String in ALLOWED_SCHEMES:
		if url.begins_with(scheme) and url.length() > scheme.length():
			return true

	return false


## Pull `--server=<url>` out of a command-line argument list.
##
## Both `--server=x` and `--server x` are accepted, because both are what people
## type. Returns "" when absent.
static func override_from_args(args: PackedStringArray) -> String:
	var flag := "--" + OVERRIDE_KEY

	for index: int in range(args.size()):
		var argument := args[index]

		if argument.begins_with(flag + "="):
			return argument.substr(flag.length() + 1)

		if argument == flag and index + 1 < args.size():
			return args[index + 1]

	return ""


## Pull `server=<url>` out of a URL query string, as the web export sees it.
##
## Takes the raw query -- `a=1&server=ws%3A%2F%2Fx` -- rather than a parsed
## structure, because that is what `location.search` hands back and parsing it
## here keeps the web-only string handling in one place.
static func override_from_query(query: String) -> String:
	var raw := query.trim_prefix("?")

	for pair: String in raw.split("&", false):
		var halves := pair.split("=", true, 1)

		if halves.size() == 2 and halves[0] == OVERRIDE_KEY:
			return halves[1].uri_decode()

	return ""
