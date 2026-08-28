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

## ## Art travels over a different transport, and a different origin
##
## The state feed is a websocket; the `.glb` models are ordinary HTTP. That
## distinction is load-bearing on the web, and it is the one thing §4.2's
## "different origins are fine" reasoning does NOT cover: `wss://` is exempt
## from CORS, an XHR for a model is not.
##
## Measured 08/26/2026: `game.playblackout.io/static/webclient/models/` serves
## 200 with **no `Access-Control-Allow-Origin`**. So a client served from the
## CDN and fetching art from the game origin would be refused by the browser,
## silently as far as the player is concerned, and every entity would fall back
## to its family shape. The answer is to fetch art from the SAME origin the page
## came from, which on the web means asking for it relatively and never naming a
## host at all.

## Where a developer's art lives — Evennia's own webserver port.
const ASSET_DEV_ORIGIN := "http://127.0.0.1:4001"

## Where a release desktop build would fetch art from.
##
## Unreachable today: there is no desktop export preset, and this phase is web
## only. Correct rather than absent, because a half-defined branch is worse than
## one that is simply never taken — and desktop has no CORS to worry about, so
## naming the game origin is right there even though it crosses the tunnel.
const ASSET_DESKTOP_ORIGIN := "https://game.playblackout.io"

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


## Which origin this build fetches art from.
##
## `is_debug` is `OS.is_debug_build()` and `is_web` is `OS.has_feature("web")`,
## both at the call site — parameters rather than reads, so every combination is
## testable without four builds.
##
## `page_origin` is what the page was served from, which only a web build can
## know and only at runtime — [method page_origin] reads it. Passed in rather
## than read here so this stays pure and every combination is testable; "" is
## the right thing to pass from anywhere that is not a web build.
##
## Returns an ORIGIN to prefix a model path with.
##
##     debug, anywhere   -> the local Evennia webserver
##     release, web      -> the page's own origin, so the fetch is same-origin
##     release, desktop  -> the game origin, since there is no page to be
##                          relative to
##
## An empty answer for a web build means the page origin could not be read, and
## it is a FAILURE rather than a shorthand for "relative" — see the class
## docstring on why relative is not something HTTPRequest can do.
##
## **The web case puts a requirement on the deploy**: whatever serves the client
## must also serve the model tree at the same path this client asks for, which
## is [constant ModelRegistry.MODEL_ROOT]. See `deploy/webexport/README.md`.
static func asset_origin(is_debug: bool, is_web: bool,
		page_origin: String = "") -> String:
	if is_debug:
		return ASSET_DEV_ORIGIN

	if is_web:
		return page_origin.rstrip("/")

	return ASSET_DESKTOP_ORIGIN


## The origin the page was served from, or "" anywhere that is not the web.
##
## The one impure routine in this file, and it is kept apart from the decision
## above for exactly that reason: every branch of [method asset_origin] is
## testable without a browser, and this is the single line that needs one.
##
## `JavaScriptBridge` exists on every platform and answers null off the web, so
## the feature check is what draws the line rather than a missing symbol.
static func page_origin() -> String:
	if not OS.has_feature("web"):
		return ""

	var answer: Variant = JavaScriptBridge.eval("location.origin", true)

	if answer == null:
		push_warning("ServerEndpoint: the page would not name its origin, so "
			+ "art cannot be fetched and everything will draw a family shape")
		return ""

	return str(answer)


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
