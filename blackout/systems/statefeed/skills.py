"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/28/2026
Description: Turn a character's whole skill roster into the plain values
             CharSkillsPayload carries.

             Kept out of serializers.py for the reason inventory.py and
             quests.py give: that module answers "what is this thing standing
             in the world", and every routine in it is built around an entity
             with a location and coordinates. This one answers "how good am I
             at this", which has no geometry in it at all.

             IT COMPOSES NOTHING. Every per-skill value comes from
             systems/progression/skills/detail.py, which is also what the text
             sheet renders from -- so the grid a graphical client draws and the
             sheet a telnet player reads describe the same skill by
             construction rather than by discipline. What this module adds is
             only what a single skill cannot answer: the roster's order, the
             category list, the totals, and the closest skill to levelling.

             ORDER IS THE SERVER'S, LAYOUT IS THE CLIENT'S. Rows ship sorted by
             (category, name) and the category list ships beside them, so a
             client can group a grid without a table of its own. How many
             columns that grid has, and what each cell looks like, is the
             client's and is deliberately not here.

             Imported LAZILY by events.emit_skills. detail.py reaches the
             recipe registry, the aura package walk and the equipment tables,
             and events.py is imported by typeclasses/mixins.py, which every
             Character and NPC pulls in at startup. A top-level import would
             drag all of that into typeclass import time for the benefit of a
             screen nobody has opened yet.
"""

from systems.progression.skills import constants as skill_constants

from .payloads import CharSkillsPayload


# ─── Public interface ────────────────────────────────────────────────────────

def build_payload(observer) -> CharSkillsPayload:
    """
    Purpose: Build the observer's whole skill roster as one snapshot.

    Entry:
        observer - the puppeted Character. One with no skills handler is a
                   supported no-op and yields an empty roster.

    Exit/Returns:
        Returns a CharSkillsPayload.

    Module Globals:
        skill_constants.MAX_BASE_SKILL_LEVEL read.

    Methodology:
        One detail dict per registered skill, from the shared renderer. A skill
        whose detail comes back empty is SKIPPED rather than sent hollow --
        that only happens when the registry and the renderer disagree about a
        key, and a cell a client cannot label is worse than a cell that is not
        there.

        Sorted by (category, name), which is the order both the old summary
        band and the skills menu already listed skills in. Sorting HERE rather
        than in the client is what lets the two screens agree without either of
        them saying so -- the same argument SummaryState makes about panel
        order.

        `closest` is normalised from None to {}. A JSON null and an absent key
        are two more things a client would have to branch on to say "every
        skill is capped", and an empty dict is one.

    Notes/References:
        Sent on CHANNEL_CHAR_SKILLS. Every value must survive json.dumps --
        see systems/statefeed/payloads.py.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    from systems.progression.skills import detail as skill_detail
    from systems.progression.skills.registry import SKILL_REGISTRY

    handler = getattr(observer, "skills", None)

    if handler is None:
        return CharSkillsPayload()

    rows = []

    for skill_key in SKILL_REGISTRY:
        row = skill_detail.skill_detail(observer, skill_key)

        if not row:
            continue

        rows.append(row)

    rows.sort(key=lambda entry: (entry["category"], entry["name"]))

    categories = []

    for row in rows:
        if row["category"] not in categories:
            categories.append(row["category"])

    closest = handler.closest_to_level_up()

    if closest is None:
        closest = {}

    payload = CharSkillsPayload(
        skills=rows,
        categories=categories,
        total_level=int(handler.total_level()),
        total_xp=int(handler.combined_xp()),
        max_level=int(skill_constants.MAX_BASE_SKILL_LEVEL),
        closest=closest,
    )

    return payload
