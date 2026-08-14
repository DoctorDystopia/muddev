"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: Summary panel: hitpoints, combat level, and whole-character
             progression totals.
"""

from evennia.utils import logger

from systems.combat import constants as combat_const
from systems.ui.meters import build_hp_meter

from .. import constants as const
from .. import layout
from .base_panel import BasePanel


# Public constant definitions

PANEL_TITLE = "Vitals"

# What this band is once hitpoints and combat state are stripped out for the
# public view -- see the public_title note on BasePanel.
PANEL_PUBLIC_TITLE = "Standing"

LABEL_HITPOINTS = "Hitpoints"
LABEL_REGEN = "Regen"
LABEL_COMBAT_LEVEL = "Combat Level"
LABEL_TOTAL_LEVEL = "Total Level"
LABEL_TOTAL_XP = "Total XP"
LABEL_STATUS = "Status"

# Status wording. In-combat state and burning auras are read-only here; the
# `attack` / `aura` commands remain the only things that change them.
STATUS_IN_COMBAT = "In combat"
STATUS_IDLE = "Out of combat"
STATUS_AURA_PREFIX = "aura: "


class VitalsPanel(BasePanel):
    """
    Purpose: The numbers a player checks before deciding whether to fight.

    Entry:
        character is a Character.

    Exit/Returns:
        Not applicable -- see render / data.

    Module Globals:
        combat_const.HP_REGEN_AMOUNT, combat_const.HP_REGEN_INTERVAL_SECONDS
        read.

    Methodology:
        Combat Level lives HERE, not on the equipment screen where it used to
        sit. It is computed from skill levels alone -- gear does not move it --
        so filing it under equipment told the player the opposite of the truth
        about what raises it.

        Max HP has never been visible outside a fight. The meter is the whole
        reason this panel is the first titled section on the screen.

    Notes/References:
        02_Player/Player_Overview.md: max HP scales 1:1 with Fortitude, and
        players regenerate 1 HP per minute.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """

    key = "vitals"
    title = PANEL_TITLE
    public_title = PANEL_PUBLIC_TITLE
    order = const.PANEL_ORDER_VITALS
    public = True


    @classmethod
    def _regen_text(cls) -> str:
        """
        Purpose: Describe the passive regeneration rate in words.

        Entry:
            None.

        Exit/Returns:
            Returns e.g. "+1 HP / 60s".

        Module Globals:
            combat_const.HP_REGEN_AMOUNT, combat_const.HP_REGEN_INTERVAL_SECONDS
            read.

        Methodology:
            Built from the tunables rather than written out, so retuning regen
            in combat/constants.py updates the readout with it. This is exactly
            the "Metalsmith vs Metalsmithing" class of bug the repo has already
            paid for once.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        amount = combat_const.HP_REGEN_AMOUNT
        interval = combat_const.HP_REGEN_INTERVAL_SECONDS
        text = f"+{amount} HP / {interval}s"

        return text


    @classmethod
    def _aura_key(cls, character: object) -> str:
        """
        Purpose: Name the aura currently burning on this character, if any.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns the aura's display name, or "" when none is active.

        Module Globals:
            None.

        Methodology:
            The `aura` accessor is a lazy_property that returns None when no
            handler is attached, and the handler's own aura key is ndb state
            that is legitimately absent between activation and the first pulse.
            Both absences mean the same thing to a player, so both collapse to
            the empty string here.

        Notes/References:
            systems/combat/auras/aura_handler.py owns the handler.

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        try:
            handler = getattr(character, "aura", None)

            if handler is None:
                return ""

            aura = handler.get_aura()
        except Exception as exc:
            logger.log_err(f"VitalsPanel._aura_key failed: {exc!r}")

            return ""

        if aura is None:
            return ""

        name = getattr(aura, "name", "")

        return str(name)


    @classmethod
    def _status_text(cls, character: object) -> str:
        """
        Purpose: One line describing combat and aura state.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns e.g. "In combat, aura: Cinderfield".

        Module Globals:
            STATUS_IN_COMBAT, STATUS_IDLE, STATUS_AURA_PREFIX read.

        Methodology:
            Combat state comes from db.in_combat, the canonical flag every
            combat teardown path sets, rather than from whether a handler
            script happens to exist.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        is_fighting = bool(character.db.in_combat)

        if is_fighting:
            parts = [STATUS_IN_COMBAT]
        else:
            parts = [STATUS_IDLE]

        aura_name = cls._aura_key(character)

        if aura_name:
            parts.append(f"{STATUS_AURA_PREFIX}{aura_name}")

        text = ", ".join(parts)

        return text


    @classmethod
    def render(cls, character: object) -> list:
        """
        Purpose: Render the vitals band.

        Entry:
            character is a Character exposing hp / max_hp / combat_level and a
            skills handler.

        Exit/Returns:
            Returns a list of display lines.

        Module Globals:
            LABEL_* read.

        Methodology:
            The HP meter is a wide row because it is METER_WIDTH columns on its
            own; the three progression totals pair up beneath it.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        meter = build_hp_meter(character.hp, character.max_hp)
        combat_level = character.combat_level
        total_level = character.skills.total_level()
        combined_xp = character.skills.combined_xp()

        pairs = [
            (LABEL_COMBAT_LEVEL, f"{combat_level:,}"),
            (LABEL_TOTAL_LEVEL, f"{total_level:,}"),
            (LABEL_TOTAL_XP, f"{combined_xp:,}"),
            (LABEL_REGEN, cls._regen_text()),
        ]

        lines = [layout.wide_field(LABEL_HITPOINTS, meter, color="")]
        lines.extend(layout.fields(pairs))
        lines.append(layout.wide_field(LABEL_STATUS, cls._status_text(character)))

        return lines


    @classmethod
    def render_public(cls, character: object) -> list:
        """
        Purpose: Render the vitals band as a stranger sees it.

        Entry:
            character is the Character being looked at.

        Exit/Returns:
            Returns a list of display lines: the three progression totals only.

        Module Globals:
            LABEL_COMBAT_LEVEL, LABEL_TOTAL_LEVEL, LABEL_TOTAL_XP read.

        Methodology:
            Drops current HP, combat state and active aura. Those three are
            live tactical information: an opponent who can read your remaining
            hitpoints and whether your aura is burning knows when to open on
            you, and a profile command that leaked them would be a combat tool
            rather than a social one.

            Combat level and the progression totals stay, matching OSRS, where
            combat level is public over a player's head and total level and
            total XP are public on the hiscores.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        pairs = [
            (LABEL_COMBAT_LEVEL, f"{character.combat_level:,}"),
            (LABEL_TOTAL_LEVEL, f"{character.skills.total_level():,}"),
            (LABEL_TOTAL_XP, f"{character.skills.combined_xp():,}"),
        ]
        lines = layout.fields(pairs)

        return lines


    @classmethod
    def data(cls, character: object) -> dict:
        """
        Purpose: Structured form of the vitals band.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns a dict of plain JSON-safe values.

        Module Globals:
            None.

        Methodology:
            HP and max_hp are repeated here even though the char_vitals channel
            already streams them. A summary snapshot that omitted them would
            force a client to correlate two channels to draw one panel.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        payload = {
            "hp": int(character.hp),
            "max_hp": int(character.max_hp),
            "combat_level": int(character.combat_level),
            "total_level": int(character.skills.total_level()),
            "total_xp": int(character.skills.combined_xp()),
            "in_combat": bool(character.db.in_combat),
            "aura": cls._aura_key(character),
        }

        return payload
