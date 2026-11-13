"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/26/2026
Description: The sound kinds. A sound kind says what a cue is: a sound
             effect today, and music later. The kind sets the folder of the
             sound clip, the files that it takes, and the settings of its
             import.

             MUSIC IS THE SECOND ROW (DESIGN-0016, 11/08/2026). A track is
             a served kind: the wizard encodes a FLAC master to an OGG in
             the served tree, web/static/webclient/music/, and the client
             fetches it over HTTP, as it fetches a model. It never enters
             the pck, because the pck downloads before the login prompt.
             A served kind writes no .import file, so its importer is "".
             The client half is one row in the bus table of SoundCues and
             one bus in default_bus_layout.tres. The wizard asks the kind
             question only when this table holds two rows or more.

             Python owns the folder and the import. The client owns the bus
             that a kind plays on, because a bus is how a sound is heard.

             PURE. Importing it reads no file.
"""

from dataclasses import dataclass


# ─── Public constant definitions ─────────────────────────────────────────────

@dataclass(frozen=True)
class SoundKind:
    """
    What one sound kind is.

    label is its row in the kind question. folder is its folder under
    godot/audio/, or under the served tree for a served kind. suffixes are
    the sound clip files that it takes. output_suffix is the suffix of the
    file that the client plays. served is True when the file goes to the
    served tree and the client fetches it. importer and resource_type are
    the [remap] lines of its .import file, and params are the (name, value)
    lines of the [params] section. A served kind has no .import file, and
    its importer is "". import_note is what the write does to the sound,
    for the Changes column of the credits.
    """

    label: str
    folder: str
    suffixes: tuple
    output_suffix: str
    served: bool
    importer: str
    resource_type: str
    params: tuple
    import_note: str


SFX_KIND: str = "sfx"
MUSIC_KIND: str = "music"

# The Vorbis quality of a served track, 0 to 10. 6 is about 192 kbps.
MUSIC_QUALITY: int = 6

# The import of a .wav sound effect: the defaults of Godot 4.7, with Force
# Mono on. A sound effect is not positional, so a second channel only doubles
# its size. Godot keeps these settings and adds the uid at the import.
_WAV_MONO_PARAMS: tuple = (
    ("force/8_bit", "false"),
    ("force/mono", "true"),
    ("force/max_rate", "false"),
    ("force/max_rate_hz", "44100"),
    ("edit/trim", "false"),
    ("edit/normalize", "false"),
    ("edit/loop_mode", "0"),
    ("edit/loop_begin", "0"),
    ("edit/loop_end", "-1"),
    ("compress/mode", "2"),
)

KINDS: dict = {
    SFX_KIND: SoundKind(
        label="A sound effect: one short sound clip on the SFX bus",
        folder="sfx",
        suffixes=(".wav",),
        output_suffix=".wav",
        served=False,
        importer="wav",
        resource_type="AudioStreamWAV",
        params=_WAV_MONO_PARAMS,
        import_note="Imported as mono (Force → Mono).",
    ),
    MUSIC_KIND: SoundKind(
        label="A music track: a FLAC master, served as OGG on the Music bus",
        folder="music",
        suffixes=(".flac",),
        output_suffix=".ogg",
        served=True,
        importer="",
        resource_type="",
        params=(),
        import_note="Encoded to OGG Vorbis at quality %d." % MUSIC_QUALITY,
    ),
}


# ─── Private constant definitions ────────────────────────────────────────────

_IMPORT_TEMPLATE: str = """[remap]

importer="%s"
type="%s"

[params]

%s
"""
_PARAM_LINE: str = "%s=%s"


# ─── Public routines ─────────────────────────────────────────────────────────

def render_import(kind: SoundKind) -> str:
    """
    Purpose: Give the text of the .import file of a new sound clip.

    Entry:
        kind is a row of KINDS.

    Exit/Returns:
        Returns the text, with no uid and no path. The Godot import adds
        them, and it keeps each line of [params]. Returns "" for a served
        kind, which has no .import file.

    Module Globals:
        _IMPORT_TEMPLATE, _PARAM_LINE read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    if kind.served:
        return ""

    lines = [_PARAM_LINE % param for param in kind.params]
    text = _IMPORT_TEMPLATE % (kind.importer, kind.resource_type,
                               "\n".join(lines))

    return text
