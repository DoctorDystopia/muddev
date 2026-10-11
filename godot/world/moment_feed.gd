class_name MomentFeed
extends RefCounted
## One game moment from `blackout_moment`, as a signal.
##
## The server sends a moment NAME, such as `task_complete`, and nothing else.
## This model holds no state. It turns each message into [signal happened].
## A view decides what the moment looks or sounds like. [SoundCues] maps a
## moment to its clip.
##
## A cue hangs off this signal, never off the text line that the server
## prints at the same moment. A match on that line would stop with no error
## at its first copy edit.

const _Const := preload("res://autoload/blackout_constants.gd")

## One moment occurred. Fired one time for each `blackout_moment` message.
signal happened(moment: String)


## Offer one message. Returns true when the channel is this model's, so the
## console stops offering it. A message with no moment name is consumed and
## fires nothing.
func ingest(channel: String, payload: Dictionary) -> bool:
	if channel != _Const.CH_MOMENT:
		return false

	var moment := str(payload.get("moment", ""))

	if moment.is_empty():
		return true

	happened.emit(moment)

	return true
