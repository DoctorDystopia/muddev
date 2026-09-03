"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: The Lone Android's dialogue -- every beat of "Oasis in the
             Wastes", gated on which step of the quest the player is on.

Node names follow the vault doc's Code Mapping table: node_step1_intro,
node_step2_chores, node_step3_craft, node_step4_defend, node_step5_resolution.

    04_Content/Quests_and_Adventures/Full Quest List/
    Oasis in the Wastes (name TBD) [AI-EDITABLE].md

The android's voice is the point of the opening conversation: it is a farm
hand, not a diplomat, and it addresses the player as a probability. It does
not notice them until they physically interrupt it (DCT.1), reports its
confidence that they are human (DCT.2), and never stops being cheerful about
any of it.
"""

from systems.menus.dialogue import menu_npc
from systems.quests import constants as quest_constants
from systems.quests.content.quest_oasis_in_the_wastes import (
    QUEST_KEY as OASIS_QUEST_KEY,
    RECIPE_AXE,
    RECIPE_DAGGER,
    STEP_APPRENTICESHIP,
    STEP_DEFENSE,
    STEP_INTRO,
    STEP_MAINTENANCE,
    STEP_RESOLUTION,
)
from systems.quests.loader import GLOBAL_QUEST_REGISTRY
from systems.ui.colors import (
    HIGHLIGHT_COLOR,
    RESET_COLOR,
    SUCCESS_COLOR,
    dialog as _dialog,
    highlight as _hl,
    title as _line,
)
from systems.statefeed import constants as feed_const

# Every line this module sends a player is something an NPC says, so the
# routing tag is bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/statefeed/constants.py.
_MSG_DIALOGUE = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_DIALOGUE}


# Public constant definitions
NPC_NAME = "Lone Android"
NPC_DESC = (
    "A farm-hand android, alone. Its chassis is sand-scoured down to the "
    "primer and one knee joint whines when it moves. It is bent over a "
    "datapad, writing."
)

# This NPC keeps its dialogue in this module rather than on the object, so its
# parting line is a constant here. It is still PRINTED only by
# BlackoutEvMenu.close_menu, via CLOSING_TEXT at the foot of this module.
NPC_FAREWELL = '"Don\'t die!, [82% human]."'

# Player-customization (name, appearance) is meant to happen inside the
# opening conversation -- see the vault doc's DCT.3 rows. There is no
# customization system yet, so the beat is written and the handoff is not.
_STUB_CUSTOMIZATION = (
    "|xThe android waits, stylus poised. [Character customization goes here.]|n"
)



def _quest_status(caller: object) -> str:
    """
    Purpose: Determines the caller's relationship to the oasis quest.

    Entry:
        caller is a valid Evennia Character object

    Exit/Returns:
        Returns one of the STATUS_* constants.

    Module Globals:
        OASIS_QUEST_KEY read

    Methodology:
        Delegates to QuestHandler.status. This used to read
        caller.db.active_quests and caller.db.completed_quests and rebuild the
        three status strings itself, which made this module a second owner of
        a fact the handler already publishes.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    status = caller.quests.status(OASIS_QUEST_KEY)

    return status



def _advance(caller: object, action: str, argument: str) -> None:
    """
    Purpose: Report a conversational beat to the quest engine.

    Entry:
        caller is a Character with an active oasis quest.
        action is one of constants.QUEST_ACTIONS.
        argument identifies the specific target.

    Exit/Returns:
        No conditions.

    Module Globals:
        OASIS_QUEST_KEY read.

    Methodology:
        Names the quest, rather than going through notify_quests, because a
        dialogue node is the one caller that genuinely knows which quest it is
        advancing -- it exists only to serve this one.

        This is also why CmdTalk does not fire `talk` itself: the android is
        two different targets (talk:lone_android at the start,
        talk:lone_android_end at the end) and a blanket hook on the command
        could not tell them apart.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    caller.quests.update_progress(OASIS_QUEST_KEY, action, argument)



# ─── Step 1: Awakening in the Wastes (DCT.1 - DCT.5) ─────────────────────────

def start(caller: object, **kwargs) -> tuple:
    """
    Purpose: Entry node -- routes to whichever beat the player is owed.

    Entry:
        caller is a valid Evennia Character object
        kwargs["npc"] is the NPC object

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        NPC_NAME, NPC_DESC read.

    Methodology:
        Dispatches on quest STEP rather than on a flat offered/in-progress/
        done triple, so each phase of the quest gets its own conversation
        instead of one node that has to describe all of them. The routing
        table is keyed on step key rather than step index: inserting a step
        must not silently re-point every node after it.

    Notes/References:
        DCT.1 in the vault doc -- the android does not notice the player.

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    npc = menu_npc(caller)
    npc_name = NPC_NAME

    if npc:
        npc_name = npc.key

    status = _quest_status(caller)

    if status == quest_constants.STATUS_COMPLETED:
        return node_post_quest(caller)

    if status == quest_constants.STATUS_ACTIVE:
        step_node = _STEP_NODES.get(caller.quests.current_step_key(OASIS_QUEST_KEY))

        if step_node is not None:
            return step_node(caller)

    text = "\n".join([
        _line(npc_name),
        NPC_DESC,
        "",
        "It is writing intently and does not look up.",
    ])

    options = (
        {"desc": '"Hello?"', "goto": "node_hello_once"},
        {"desc": "*tap the android on the shoulder*", "goto": "node_shoulder_tap"},
    )

    return text, options



def node_hello_once(caller: object, **kwargs) -> tuple:
    """
    Purpose: DCT.1.1 -- the android does not hear the player.

    Entry:
        caller is a valid Evennia Character object

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        None

    Methodology:
        Offers the louder retry and the shoulder tap. The joke only lands if
        the player can choose to escalate rather than being escalated for
        them, so the polite option is never removed.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    text = "The android keeps writing. Nothing about it acknowledges you."

    options = (
        {"desc": '"Hello?!"', "goto": "node_hello_twice"},
        {"desc": "*tap the android on the shoulder*", "goto": "node_shoulder_tap"},
    )

    return text, options



def node_hello_twice(caller: object, **kwargs) -> tuple:
    """
    Purpose: DCT.1.2 -- shouting makes the note-taking worse.

    Entry:
        caller is a valid Evennia Character object

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        None

    Methodology:
        The escalation is the android's, not the player's: it writes FASTER.
        Leaves the tap as the only forward option, because the point of the
        beat is that words do not work.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    text = (
        "The stylus speeds up. Whatever it is recording must be urgent."
    )

    options = (
        {"desc": "*tap the android on the shoulder*", "goto": "node_shoulder_tap"},
    )

    return text, options



def node_shoulder_tap(caller: object, **kwargs) -> tuple:
    """
    Purpose: DCT.1.3 -- the android finally looks up.

    Entry:
        caller is a valid Evennia Character object

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        None

    Methodology:
        Opens DCT.2's three-way branch. All three converge on the same
        analysis beat with a different confidence reading, so the player's
        opening tone colours the android's assessment of them without gating
        anything -- every path reaches the same quest.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    text = (
        "With a whine of servos, the android straightens and looks at you with a welcoming smile. "
        "Its weathered, chrome face stares at you, the two photoreceptors unblinking."
    )

    options = (
        {
            "desc": '"Excuse me. Might I bother you for some help?"',
            "goto": ("node_analysis", {"note": None}),
        },
        {
            "desc": '"Start explaining, or there is going to be violence."',
            "goto": ("node_analysis", {"note": "raider"}),
        },
        {
            "desc": "*stare blankly back at it*",
            "goto": ("node_analysis", {"note": "damage"}),
        },
    )

    return text, options



def node_analysis(caller: object, **kwargs) -> tuple:
    """
    Purpose: DCT.2 -- the android reports what it thinks you probably are.

    Entry:
        caller is a valid Evennia Character object
        kwargs["note"] is None, "raider" or "damage" -- which opener was used.

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        None

    Methodology:
        One node for all three DCT.2 rows, differing only in the confidence
        line and the greeting. Three near-identical nodes would be three
        places to edit the android's voice.

        The percentages come from the vault doc: a threat reads as slightly
        less human because some of the probability mass moves to "mutant
        raider"; a blank stare reads as fully human with a caveat.

    Notes/References:
        DCT.2.1 / DCT.2.2 / DCT.2.3.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    note = kwargs.get("note")

    if note == "raider":
        human = 72
        breakdown = (
            '"Probability of [other] = [17%] and [mutant raider] = [10%]."'
        )
        greeting = f'"Greetings, [{human}% human]!"'
    elif note == "damage":
        human = 82
        breakdown = (
            '"Probability of [human] = [82%], likely brain damage. '
            'Probability of [other] = [17%]."'
        )
        greeting = (
            f'"Greetings, [{human}% human] with likely and/or guaranteed '
            'brain damage!"'
        )
    else:
        human = 82
        breakdown = (
            '"Probability of [human] = [82%]. Probability of [other] = [17%]."'
        )
        greeting = f'"Greetings, [{human}% human]!"'

    text = "\n".join([
        _dialog('"Analyzing detected [human] presence."'),
        _dialog(breakdown),
        "",
        _dialog(greeting),
        _dialog(
            '"This unit is operating at optimal stability and ready to '
            'assist! State [description] of yourself:"'
        ),
    ])

    options = (
        {
            "desc": '"Come to think of it... I am having trouble remembering."',
            "goto": "node_customization",
        },
        {
            "desc": '"What does [other] mean?"',
            "goto": "node_what_is_other",
        },
    )

    return text, options



def node_what_is_other(caller: object, **kwargs) -> tuple:
    """
    Purpose: DCT.3.5 -- the android explains the Wastes to a small child.

    Entry:
        caller is a valid Evennia Character object

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        None

    Methodology:
        Pure world-building. Converges on the customization handoff like every
        other DCT.3 row, so asking the question costs nothing.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    text = "\n".join([
        _dialog(
            '"[human] appears to have suffered brain damage. Adjusting '
            'vocabulary."'
        ),
        "",
        _dialog(
            '"Hello, little human. Many entities exist in the Wastes. There '
            "are raiders. There are mutants. There are mutant raiders, and "
            'there are raider mutants. So: everything."'
        ),
    ])

    options = (
        {
            "desc": '"That is not as helpful as you think it is."',
            "goto": "node_customization",
        },
    )

    return text, options



def node_customization(caller: object, **kwargs) -> tuple:
    """
    Purpose: DCT.3 -- where the player states who they are.

    Entry:
        caller is a valid Evennia Character object

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        _STUB_CUSTOMIZATION read.

    Methodology:
        STUBBED. The vault doc puts name and appearance selection here, inside
        the conversation, but there is no customization system to hand off to
        yet. The narrative beat is written and the handoff is a marked
        placeholder, so wiring it later is a change to one node rather than a
        change to the shape of the conversation.

    Notes/References:
        DCT.3.1 - DCT.3.5 all converge here.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    text = "\n".join([
        "You tell it what little you are sure of.",
        "",
        _STUB_CUSTOMIZATION,
        "",
        _dialog(
            '"Recorded. Retention is poor in [82% human]."'
        ),
    ])

    options = (
        {"desc": '"Where am I? What is this place?"', "goto": "node_who_are_you"},
    )

    return text, options



def node_who_are_you(caller: object, **kwargs) -> tuple:
    """
    Purpose: The android explains itself and the farm, then offers work.

    Entry:
        caller is a valid Evennia Character object

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        None

    Methodology:
        The tragic-purpose beat from the vault doc's Narrative Themes: a farm
        hand still running its protocol because nothing ever told it to stop,
        and no idea what else it would do. Played straight, not for laughs --
        the comedy is in how it talks, not in what happened to it.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    text = "\n".join([
        _dialog(
            '"Welcome to [redacted deceased owner\'s name] farm. I am C.L.A.R.K. unit."'
        ),
        "",
        _dialog(
            '"Yield is down. Yield has been down for some years. The current '
            "orange varietal is iteration seventy-three point two eight "
            'four. Status of seedling: dead. I will try seventy-three point '
            'two eight five."'
        ),
    ])

    options = (
        {
            "desc": '"Can you tell me how to get out of the desert?"',
            "goto": "node_quest_offer",
        },
        {
            "desc": '"Doesn\'t that get to you?"',
            "goto": "node_android_lore",
        },
    )

    return text, options



def node_android_lore(caller: object, **kwargs) -> tuple:
    """
    Purpose: Optional depth -- the android on being the last one here.

    Entry:
        caller is a valid Evennia Character object

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        None

    Methodology:
        Answers the question the player actually asked, in the android's
        register -- it reports its own loneliness as a maintenance statistic,
        which is bleaker than saying it outright.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    text = "\n".join([
        _dialog(
            '"Clarify [get to]. If you mean degradation: yes. Chassis '
            "integrity is falling. Battery stability is at twenty-three "
            'percent, which is described in my documentation as optimal."'
        ),
        "",
        _dialog(
            '"If you mean the other thing, you are the first entity to '
            "speak to this unit in four hundred and eleven days. This unit "
            'logged it.\"'
        ),
    ])

    options = (
        {
            "desc": '"...Can you tell me how to get out of the desert?"',
            "goto": "node_quest_offer",
        },
    )

    return text, options



def node_quest_offer(caller: object, **kwargs) -> tuple:
    """
    Purpose: The android names its price and the player accepts or declines.

    Entry:
        caller is a valid Evennia Character object

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        OASIS_QUEST_KEY read

    Methodology:
        An explicit accept prompt, rather than the vault doc's start-on-
        contact, so this quest works the way every later one will.

        Asks the handler whether the quest is AVAILABLE rather than trying to
        accept it and reading the failure -- a missing blueprint, a completed
        quest and an unmet prerequisite are three different conversations.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    blueprint = GLOBAL_QUEST_REGISTRY.get(OASIS_QUEST_KEY)

    if blueprint is None:
        text = _dialog('"Query not recognized. This unit apologizes."')
        options = ({"desc": "Never mind.", "goto": "node_goodbye"},)

        return text, options

    if not caller.quests.is_available(OASIS_QUEST_KEY):
        text = _dialog('"That arrangement is already in progress."')
        options = ({"desc": "Right.", "goto": "start"},)

        return text, options

    text = "\n".join([
        _dialog(
            '"Affirmative. Route data for Neo Cairo is held in this unit\'s '
            'navigation cache."'
        ),
        "",
        _dialog(
            '"This unit will transmit it in exchange for one day of labor. '
            "The drainage line is silted. The soil sample is unprepared. "
            'Many tasks to do."'
        ),
        "",
        _hl(f"Accept the quest '{blueprint.title}'?"),
    ])

    options = (
        {
            "desc": f"Accept: {blueprint.title}",
            "goto": _accept_oasis_quest,
        },
        {"desc": "Not yet.", "goto": "node_goodbye"},
    )

    return text, options



def _accept_oasis_quest(caller: object,
                        raw_string: str,
                        **kwargs) -> str:
    """
    Purpose: Accepts the oasis quest and moves to the first chore briefing.

    Entry:
        caller is a valid Evennia Character object
        raw_string is the raw input from the user (unused)

    Exit/Returns:
        Returns the name of the node to display next.

    Module Globals:
        SUCCESS_COLOR, RESET_COLOR read
        OASIS_QUEST_KEY read

    Methodology:
        Only a goto CALLABLE may return a node name -- a node itself must
        return (text, options), and returning a string from one prints the
        string at the player. See CLAUDE.md.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    accepted = caller.quests.accept_quest(OASIS_QUEST_KEY)

    if accepted:
        caller.msg(
            (f"{SUCCESS_COLOR}You agree to work the farm.{RESET_COLOR}", _MSG_DIALOGUE))
    else:
        caller.msg(
            (f"{HIGHLIGHT_COLOR}You have already taken this quest.{RESET_COLOR}",
             _MSG_DIALOGUE))

    return "node_step1_drainage_intro"



def node_step1_drainage_intro(caller: object, **kwargs) -> tuple:
    """
    Purpose: DCT.4 -- the android briefs the first chore and step 1 closes.

    Entry:
        caller is a valid Evennia Character object with the oasis quest active

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        OASIS_QUEST_KEY read.

    Methodology:
        This is where `talk:lone_android` fires -- not on the `talk` command,
        and not on accepting. The intro step is satisfied by having had the
        conversation, so it completes at the end of the conversation.

    Notes/References:
        DCT.4.1 in the vault doc.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    _advance(caller, quest_constants.ACTION_TALK, "lone_android")

    text = "\n".join([
        _dialog(
            '"Task one. The drainage line runs beneath the north row. Sand '
            "enters it. Sand always enters it. Remove the sand."
        ),
        "",
        _dialog(
            '"Task two. The soil sample must be prepared and iteration '
            'seventy-three point two eight five planted in it."'
        ),
        "",
        _dialog('"Report back. This unit will be here. This unit is always here."'),
    ])

    options = (
        {"desc": '"I\'ll get to it."', "goto": "node_goodbye"},
    )

    return text, options



# ─── Step 2: Crop Rotation & Maintenance (STUBBED) ───────────────────────────

def node_step2_chores(caller: object, **kwargs) -> tuple:
    """
    Purpose: The chore-reporting conversation.

    Entry:
        caller is a valid Evennia Character object on the maintenance step

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        None

    Methodology:
        STUBBED, deliberately and visibly. There is no system for interacting
        with world objects yet, so the chores are completed by REPORTING them
        here rather than by doing them in the world.

        The quest's targets are still the real ones -- `interact:pipe` and
        `interact:soil`. When drainage pipes and soil beds become real
        objects, they fire the same two targets and these options come out.
        The blueprint does not change.

    Notes/References:
        Step 2 DCT (DCT.S2.1, DCT.S2.2) in the vault doc, both stubbed there
        too.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    progress = caller.quests.progress_for(OASIS_QUEST_KEY)
    options_list = []

    if progress.get("interact:pipe") is not True:
        options_list.append({
            "desc": "[stub] Clear the sand from the drainage line.",
            "goto": _report_pipe,
        })

    if progress.get("interact:soil") is not True:
        options_list.append({
            "desc": "[stub] Prepare the soil and plant the varietal.",
            "goto": _report_soil,
        })

    options_list.append({"desc": '"Later."', "goto": "node_goodbye"})

    text = "\n".join([
        _dialog('"Report status of assigned tasks."'),
        "",
        _hl("Objectives:"),
        "\n".join(f"  {line}"
                  for line in caller.quests.objective_lines(OASIS_QUEST_KEY)),
    ])

    return text, tuple(options_list)



def _report_pipe(caller: object, raw_string: str, **kwargs) -> str:
    """Satisfy the drainage objective. Stands in for a world interaction."""
    _advance(caller, quest_constants.ACTION_INTERACT, "pipe")
    caller.msg((f"{SUCCESS_COLOR}You dig the silt out of the drainage line."
               f"{RESET_COLOR}", _MSG_DIALOGUE))

    return "start"



def _report_soil(caller: object, raw_string: str, **kwargs) -> str:
    """Satisfy the planting objective. Stands in for a world interaction."""
    _advance(caller, quest_constants.ACTION_INTERACT, "soil")
    caller.msg((f"{SUCCESS_COLOR}You work the sample bed and press the seedling "
               f"in.{RESET_COLOR}", _MSG_DIALOGUE))

    return "start"



# ─── Step 3: Make a crafting tool and weapon ─────────────────────────────────

def node_step3_craft(caller: object, **kwargs) -> tuple:
    """
    Purpose: The android teaches Cutting, Foundry and Metalsmith.

    Entry:
        caller is a valid Evennia Character object on the apprenticeship step

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        RECIPE_AXE, RECIPE_DAGGER read.

    Methodology:
        Instruction only -- no target fires here. The step is satisfied by
        actually forging the two items, which the crafting system reports
        through notify_quests without this node's involvement.

        The bare-handed beat is the doc's: the android does not warn the
        player that tearing scrap off a pole will hurt, because finding that
        out is the lesson.

    Notes/References:
        Step 3 DCT (DCT.S3.1 - S3.3). The hammer handed over here comes from
        the quest blueprint's on_enter hook, not from this conversation.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    text = "\n".join([
        _dialog(
            '"Task three. This unit will teach you to make tools, because '
            'you have none and that is statistically fatal."'
        ),
        "",
        _dialog(
            '"There are rusty poles standing in the sand. Take metal from '
            "one. You do not have an axe, so it will take metal from you as "
            'well."'
        ),
        "",
        _dialog(
            '"Then: the furnace, to smelt the chunk into scrap. Then: the '
            f'anvil, to beat the scrap into a {RECIPE_AXE} and a '
            f'{RECIPE_DAGGER}. Take this hammer. It was not doing anything."'
        ),
        "",
        _hl("Objectives:"),
        "\n".join(f"  {line}"
                  for line in caller.quests.objective_lines(OASIS_QUEST_KEY)),
    ])

    options = (
        {"desc": '"Understood."', "goto": "node_goodbye"},
    )

    return text, options



# ─── Step 4: Defend the Green ────────────────────────────────────────────────

def node_step4_defend(caller: object, **kwargs) -> tuple:
    """
    Purpose: The android sends the player out to meet the raiders.

    Entry:
        caller is a valid Evennia Character object on the defense step

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        None

    Methodology:
        No target fires here either -- `kill:mutant_raider` comes from
        at_death, through the fan-out hook. The android does not follow the
        player into the fight; a farm hand is not a combat unit and says so.

    Notes/References:
        Step 4 DCT (DCT.S4.1, DCT.S4.2). The doc floats an `equip:weapon`
        gate before combat; it is not implemented, because a player who walks
        into a raider unarmed has made a decision and the game should let
        them have it.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    text = "\n".join([
        _dialog(
            '"Movement in the dunes. Heat signature, bipedal, approaching '
            'the farm. Probability of [mutant raider] = [96%]."'
        ),
        "",
        _dialog(
            '"This unit is a farm hand. This unit no longer has no combat protocols '
            "and would be disassembled. You have a blade now. This unit "
            'calculates that this is your task."'
        ),
        "",
        _hl("Objectives:"),
        "\n".join(f"  {line}"
                  for line in caller.quests.objective_lines(OASIS_QUEST_KEY)),
    ])

    options = (
        {"desc": '"Then I will meet it."', "goto": "node_goodbye"},
    )

    return text, options



# ─── Step 5: Harvest & Departure ─────────────────────────────────────────────

def node_step5_resolution(caller: object, **kwargs) -> tuple:
    """
    Purpose: The closing conversation, which completes the quest.

    Entry:
        caller is a valid Evennia Character object on the resolution step

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        None

    Methodology:
        Presents the beat and offers the option that fires
        `talk:lone_android_end`. The firing is deliberately NOT on entry to
        this node: satisfying the last target completes the quest and runs the
        reward callback, and doing that before the player has read the scene
        would print the completion banner over the top of it.

    Notes/References:
        DCT.S5.1. Completion and the XP award are the engine's, via
        QuestHandler and award_rewards.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    text = "\n".join([
        _dialog(
            '"Threat resolved. The farm is intact. This unit had assigned '
            'a low probability to that outcome."'
        ),
        "",
        _dialog(
            '"Transmitting navigation data. Follow the pylons east. They '
            "are dead, but they still point at Neo Cairo, which is more than "
            'most things out here do."'
        ),
    ])

    options = (
        {
            "desc": '"Thank you."',
            "goto": _finish_oasis_quest,
        },
    )

    return text, options



def _finish_oasis_quest(caller: object, raw_string: str, **kwargs) -> str:
    """
    Purpose: Satisfy the final target, completing the quest.

    Entry:
        caller is a valid Evennia Character object on the resolution step

    Exit/Returns:
        Returns the name of the closing node.

    Module Globals:
        None

    Methodology:
        A goto callable, so it may return a node name. The completion banner
        and the XP award both fire inside update_progress, before the closing
        node renders.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    _advance(caller, quest_constants.ACTION_TALK, "lone_android_end")

    return "node_post_quest"



def node_post_quest(caller: object, **kwargs) -> tuple:
    """
    Purpose: What the android says to a player who already helped it.

    Entry:
        caller is a valid Evennia Character object

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        None

    Methodology:
        The android goes back to work, because that is what it does. Points
        east for a player who has forgotten where they were going.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    text = "\n".join([
        _dialog(
            '"You are still here. This unit has logged the visit. Iteration '
            'seventy-three point two eight five is dead. Iteration '
            'seventy-three point two eight six is sure to live."'
        ),
        "",
        _dialog('"East, [82% human]. Follow the pylons. Do not sleep in the open."'),
    ])

    options = (
        {"desc": '"I will. Look after yourself."', "goto": "node_goodbye"},
    )

    return text, options



def node_goodbye(caller: object, **kwargs) -> tuple:
    """
    Purpose: End the conversation in-fiction, by choosing to.

    Entry:
        caller is a valid Evennia Character object

    Exit/Returns:
        Returns ("", None). The None closes the menu; the empty text is the
        point -- closing is what speaks.

    Module Globals:
        None

    Methodology:
        Prints nothing. CLOSING_TEXT carries the farewell, so that choosing
        to say goodbye and typing q part with the same words.

    Notes/References:
        See BlackoutEvMenu.close_menu.

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    return "", None



# Which node greets a player mid-quest, by the step they are on. A table
# rather than a branch chain in start(), and keyed on step KEY so that
# inserting a step does not re-point every node after it.
_STEP_NODES = {
    STEP_INTRO: node_step1_drainage_intro,
    STEP_MAINTENANCE: node_step2_chores,
    STEP_APPRENTICESHIP: node_step3_craft,
    STEP_DEFENSE: node_step4_defend,
    STEP_RESOLUTION: node_step5_resolution,
}


# Spoken by BlackoutEvMenu.close_menu, however the conversation ends.
CLOSING_TEXT = _dialog(NPC_FAREWELL)
