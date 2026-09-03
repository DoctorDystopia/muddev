"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: Profiling scenarios for the web layer -- the Django views the
             Evennia webserver still answers.

What is left of this layer, and why it is measured anyway
----------------------------------------------------------
The browser-based three.js client was retired on 09/03/2026 and the Godot
project is now the sole canonical client on every platform, so the heavy
per-frame web path this layer used to own is gone. What remains is the
Evennia website: the index, the story page, and the account pages Django
renders per request.

That makes this the CHEAPEST layer in the pipeline, and measuring it is how
the audit earns the right to say so. An audit that skipped it would be open to
the reply that the bottleneck was somewhere nobody looked; one row per view,
measured the same way as everything else, closes that.

Why the marketing site is not here
-----------------------------------
playblackout.io is an Astro build in a separate repo, served from a Cloudflare
Worker with the Godot binary and the .glb tree beside it in R2. Nothing in this
repository serves it and nothing here can measure it -- see deploy/README.md.
The scenarios below cover what THIS server renders.
"""

from django.test import Client

from .. import constants as const
from . import scenario


# ─── Private constant definitions ────────────────────────────────────────────

# Views are slow relative to a serialiser -- template compilation, context
# processors, a session round trip -- so they run fewer passes.
_VIEW_REPEAT = 20

# The routes this server actually answers. The story page is the one custom
# view; the index is Evennia's own and carries the game statistics block.
_INDEX_PATH = "/"
_STORY_PATH = "/story"


# ─── Public routines ─────────────────────────────────────────────────────────

@scenario(name="GET / (Evennia index)",
          layer=const.LAYER_WEB,
          repeat=_VIEW_REPEAT,
          notes="Evennia's own index view, which counts accounts and "
                "characters to render its statistics block.")
def index_view(world):
    """Measure a full request cycle against the site index."""
    client = Client()

    def work():
        client.get(_INDEX_PATH)

    return work


@scenario(name="GET /story (custom template)",
          layer=const.LAYER_WEB,
          repeat=_VIEW_REPEAT,
          notes="A bare render() of one template, with no database access. "
                "The floor a Django view can cost on this server.")
def story_view(world):
    """Measure the cheapest custom view, as a template-rendering floor."""
    client = Client()

    def work():
        client.get(_STORY_PATH)

    return work
