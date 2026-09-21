"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Things standing in the world whose point is the words on them.

             A sign is the first entity in the game to carry a `world_label`,
             and it is deliberately not the last: the label is a field on the
             serialized entity row, so anything that grows something to say
             gains floating text with no edit here and none in the renderer.
             This module is what a label looks like when the words ARE the
             object.

             TWO typeclasses, not one class with a flag. A sign is content --
             worldbuilding a player is meant to read in the fiction -- and a
             marker is an annotation ABOUT the game left by whoever is
             building it. The client draws them differently on purpose, and
             the difference is a fact about what the object IS, so it is
             declared on the class where correcting it corrects every one
             already standing on the grid. A `db.label_kind` row would have
             had to be migrated, and CLAUDE.md has the receipts for what that
             costs.
"""

from evennia import DefaultObject

from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import labels

from .objects import ObjectParent, Unpocketable
from .spawners import register_attribute_spawner, spawn_once


# ─── Map-authored signage ────────────────────────────────────────────────────

# Where the spawner reads a signpost's words from, and the thing that DISPATCHES
# it.
#
# An ATTRIBUTE and not a room key, and that is what lets a signpost label the
# furnace instead of replacing it. A tile has exactly one key, so signage keyed
# on "Signpost" could never share a tile with anything -- the furnace tile is
# already keyed "Foundry Furnace Facility" and cannot also be a signpost.
# Dispatched on the attribute, one sign is one dict entry on ANY tile, and
# labelling a facility needs no edit to that facility.
#
# Named here and imported by the map modules that set it, because a map typing
# the string and this module reading it is two spellings of one fact -- the
# shape of the "Metalsmith" versus "Metalsmithing" bug CLAUDE.md records.
SIGNPOST_LABEL_ATTR: str = "signpost_label"
SIGNPOST_DESC_ATTR: str = "signpost_desc"

# The room key for a tile whose ONLY purpose is the sign standing on it.
#
# Purely a name and a minimap colour now that dispatch runs off the attribute:
# it gives a sign-only tile something to be called in `look` and one row in the
# client's ROOM_KIND_COLORS. A tile that is a furnace AND a signpost keeps the
# furnace's key, which is correct -- the tile IS a furnace, and the sign is
# standing on it.
SIGNPOST_ROOM_KEY: str = "Signpost"

# What the spawned object is called. A key players and builders both type at it
# -- `look signpost`, `read signpost` -- rather than a copy of whatever the sign
# happens to say, because a map-authored sign's text is the map's to change and
# a key that moved with it would break every quest or script naming the object.
SIGNPOST_KEY: str = "signpost"

_SIGN_TYPECLASS: str = "typeclasses.signs.Sign"


class Sign(Unpocketable, ObjectParent, DefaultObject):
    """
    Purpose: A readable fixture -- a signpost, a painted wall, a notice board.

    Entry:
        Created with a `world_label`, which is the short text drawn in the
        world. Longer text goes in `db.desc` and is read through the text
        channel, exactly as a poster's small print is not on the poster from
        across the street.

    Exit/Returns:
        No conditions.

    Module variables:
        feed_const.ASSET_KIND_SIGN and LABEL_KIND_SIGN read.

    Methodology:
        Declares `asset_kind` rather than being left to fall through
        _classify, which would report it as an ITEM. That is not cosmetic: an
        item is the one kind TARGETED_VERB_BY_KIND gives a `get` to, so a
        client would offer to pocket the signpost -- the Foundry Furnace bug,
        which the statefeed constants describe at length because a test
        account walked off with a furnace.

        The one verb it affords is published through `extra_actions` rather
        than `interact_verb`, and the difference is the target: a facility's
        own cmdset needs no target because the object IS the target, while
        `read` lives on the character and must name what to read. The list
        also becomes the natural place for a second verb -- `deface`, say --
        without the singular field going stale beside it, which is the trap
        interact_verb walked into on gathering nodes.

        `interact_verb` is therefore left empty AND stated, so the next reader
        sees a decision rather than an oversight.

        The label is a PROPERTY over db.world_label rather than a bare
        attribute, so every write passes labels.normalise. That is what makes
        the stored value already clean for the text channel, the feed and any
        future reader at once, instead of each of them normalising its own
        copy and disagreeing about the answer.

    Notes/References:
        systems/interface/statefeed/labels.py owns the cap and the markup
        rules; systems/interface/statefeed/serializers.py _world_label is what
        puts the result on the wire.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    asset_kind = feed_const.ASSET_KIND_SIGN

    # What sort of text this is, for a client deciding how to draw it. A class
    # attribute, so changing what a sign looks like never needs a migration.
    label_kind = feed_const.LABEL_KIND_SIGN

    # Empty on purpose; the verb comes from extra_actions. See Methodology.
    interact_verb = ""

    cannot_get_message = "{name} is bolted where it stands."

    # What `read` asks for. An ATTRIBUTE and not a typeclass check, so a
    # datapad or a terminal becomes readable by declaring one thing and
    # commands/read_cmds.py needs no edit -- see that module's docstring.
    is_readable = True

    # What the object looks like, as opposed to what it says. Set once at
    # creation so `look signpost` answers something, and overridable per
    # instance by Evennia's own `desc` -- which is where a builder puts
    # anything longer than a label may be.
    default_desc = "A steel board bolted to a rusted post. There are words on it."

    # The word a client's menu row shows for `read`. Named rather than left to
    # _action_label's capitalisation because the command and the label are
    # about to differ: the row should say Read, and the command names a target.
    read_label = "Read"


    def at_object_creation(self):
        """
        Purpose: Give a new sign something to say when looked at.

        Entry:
            Called once by Evennia, at creation.

        Exit/Returns:
            No conditions.

        Module variables:
            None.

        Methodology:
            Reads `default_desc` off the CLASS rather than writing a literal,
            so Marker says something truer about itself with one attribute and
            no second hook.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        parent_class = super()
        parent_class.at_object_creation()

        self.db.desc = self.default_desc


    def extra_actions(self, observer=None) -> list:
        """
        Purpose: The one thing a client may send about a sign.

        Entry:
            No conditions.

        Exit/Returns:
            Returns a single-entry list naming `read <key>`, or [] for a sign
            with nothing written on it.

        Module variables:
            None.

        Methodology:
            A blank sign affords NOTHING, and returning [] is what says so:
            serialize_entity reports `interact` as "" and the pane stops
            offering a click that would answer "it is blank". A sign in that
            state is a builder's half-finished work, not a puzzle.

            The command names the key rather than a dbref, because it must be
            exactly what a telnet player would type -- the invariant that
            keeps a graphical client from reaching anything a text one cannot.

        Notes/References:
            systems/interface/statefeed/serializers.py interact_actions
            consumes this.

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        if not self.world_label:
            return []

        return [{"command": f"read {self.key}", "label": self.read_label}]


    @property
    def world_label(self) -> str:
        """
        Purpose: The words drawn beside this sign in a graphical client.

        Entry:
            No conditions.

        Exit/Returns:
            Returns the stored label, or "" for a sign nothing has written on
            -- which every reader treats as "draws no text".

        Module variables:
            None.

        Methodology:
            Normalised on the way out as well as in. The setter is what
            SHOULD have cleaned it, and this costs nothing for a clean string
            because labels.normalise is idempotent; what it buys is a sign
            created before this property existed, or by a fixture writing
            db.world_label directly, still being safe to put on the wire.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        stored = self.db.world_label

        return labels.normalise(stored)


    @world_label.setter
    def world_label(self, text) -> None:
        """
        Purpose: Write what this sign says, cleaned once.

        Entry:
            text - any authored string. None or "" erases the label.

        Exit/Returns:
            No conditions. db.world_label is set to the normalised form, or
            deleted when the result is empty.

        Module variables:
            None.

        Methodology:
            An empty result DELETES the row rather than storing "". A blank
            attribute and a missing one would be two spellings of "this sign
            says nothing", and the readers would each have to know both.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        cleaned = labels.normalise(text)

        if not cleaned:
            del self.db.world_label

            return

        self.db.world_label = cleaned


class Marker(Sign):
    """
    Purpose: A note to whoever is BUILDING the game, left standing in it.

    Entry:
        Created exactly as a Sign is.

    Exit/Returns:
        No conditions.

    Module variables:
        feed_const.LABEL_KIND_MARKER read.

    Methodology:
        One attribute's worth of difference, and it earns a class. A marker
        that looked like signage would be read as signage by the first player
        who walked past it, so the kind has to reach the client -- and the
        client's own table is what decides it is drawn in a colour no
        in-fiction sign uses.

        Nothing else differs. A marker is unpocketable, affords nothing and
        carries its text the same way, because it IS a sign; what it is not is
        content.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    label_kind = feed_const.LABEL_KIND_MARKER

    default_desc = (
        "A slab of scrap daubed in hazard paint. Whatever it says was not "
        "meant for anyone living here.")


class Graffiti(Sign):
    """
    Purpose: Words a PLAYER left on a wall.

    Entry:
        Created by systems/gameplay/graffiti/service.py, which stamps the
        author and the time alongside the label. Nothing else should create
        one: a scrawl with no provenance is one a moderator cannot act on and
        the sweep treats as already expired.

    Exit/Returns:
        No conditions.

    Module variables:
        feed_const.LABEL_KIND_GRAFFITI read.

    Methodology:
        A SIBLING of Marker rather than a subclass, and that relationship is
        the guard the graffiti system rests on: the sweep and the moderator's
        erase both query this typeclass and its subclasses, so map-authored
        signage and a builder's notes are structurally unreachable by either.
        A tag could be stamped on a signpost by accident; a typeclass cannot.

        It inherits `is_readable` and the `read` affordance unchanged, because
        a scrawl is read exactly as a sign is. What differs is `label_kind`,
        and it differs for the reader rather than the writer: a player has to
        be able to tell the world speaking from another player speaking, since
        a scrawl reading "BANK: EAST" is a lie a signpost could not tell.

        It carries no lifetime of its own. How long a scrawl lasts is a rule
        about the SYSTEM, owned by
        systems/gameplay/graffiti/constants.py -- a per-object expiry would be
        a number a moderator would have to go and find on each one.

        KNOWN LIMITATION, recorded rather than half-fixed. Every scrawl shares
        one key, so two on one tile make `read graffiti` a multimatch and
        Evennia answers with its numbered prompt. A graphical client sends the
        command verbatim and cannot disambiguate for the player -- but neither
        can a telnet player do anything different, so the two clients behave
        identically and the invariant holds. The obvious fix, keying the
        object on its author, is the wrong one: a scrawl is anonymous to other
        PLAYERS and attributed only to a moderator, and a key naming the
        writer would publish it to anyone who typed `look`.

    Notes/References:
        systems/gameplay/graffiti/service.py owns writing, sweeping and
        erasing.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    label_kind = feed_const.LABEL_KIND_GRAFFITI

    default_desc = (
        "Aerosol green, sprayed fast and left to run. Somebody wanted this "
        "read more than they wanted it neat.")

    cannot_get_message = "{name} is sprayed onto the wall itself."


# ─── Spawners ────────────────────────────────────────────────────────────────

@register_attribute_spawner(SIGNPOST_LABEL_ATTR)
def spawn_signpost(room):
    """
    Purpose: Stand the signpost a map asked for on its tile, and keep its words
             in step with the map on every rebuild.

    Entry:
        room - the tile just spawned from a prototype carrying
               SIGNPOST_ROOM_KEY as its key.

    Exit/Returns:
        Returns the Sign standing on the tile, or None when the map named no
        text for it.

    Module variables:
        SIGNPOST_LABEL_ATTR, SIGNPOST_DESC_ATTR, SIGNPOST_KEY and
        _SIGN_TYPECLASS read.

    Methodology:
        Dispatched on the ATTRIBUTE rather than on the room key, which is what
        lets a sign stand on a tile that is already something else -- see
        SIGNPOST_LABEL_ATTR above and typeclasses/spawners.py for the argument.

        The text is RE-ASSERTED rather than only set on creation, and that is
        the point of doing it here instead of in the prototype's own `attrs`.
        A map module is the owner of what a map-authored sign says, so editing
        the line and rebuilding has to be enough to change it -- a sign that
        kept whatever it was created with would need the tile destroyed to
        correct a typo, which is the whole failure mode CLAUDE.md records for
        facts stamped into database rows.

        Assigned through the property, so labels.normalise runs and a map that
        authored something over the cap is cut here rather than on the wire.

        A tile with the signpost key and no text spawns NOTHING and says
        nothing about it. That is the honest answer -- a blank post is
        indistinguishable from scenery, and the map author's mistake is
        visible as a missing sign rather than as a mystery object.

    Notes/References:
        Dispatched by GridTile.at_object_post_spawn, which runs every
        ATTRIBUTE_SPAWNER_REGISTRY entry whose attribute the tile carries --
        after the key spawner, so a facility is already standing there.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    authored = room.attributes.get(SIGNPOST_LABEL_ATTR, default="")

    if not authored:
        return None

    sign = spawn_once(room, _SIGN_TYPECLASS, key=SIGNPOST_KEY)
    sign.world_label = authored

    described = room.attributes.get(SIGNPOST_DESC_ATTR, default="")

    if described:
        sign.db.desc = described

    return sign
