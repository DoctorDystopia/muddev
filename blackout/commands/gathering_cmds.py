"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/05/2026
Description: Generic gathering commands injected via node CmdSets.
"""

from evennia import Command
from evennia import CmdSet
from evennia.utils import logger, utils

from commands.constants import HELP_CATEGORY_GATHERING
from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills.gatherables import get_gatherable_for_node
from systems.gameplay.progression.skills.registry import SKILL_REGISTRY
from systems.interface.statefeed import constants as feed_const

# Every line this module sends a player is gathering, so the routing tag is
# bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/interface/statefeed/constants.py.
_MSG_GATHERING = {
    feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_GATHERING}



def resolve_gathering_skill(character, node):
    """
    Purpose: Decide which gathering skill this character works this node with.

    Entry:
        character is a valid Evennia Character object.
        node is the object they are working. It need not be a node.

    Exit/Returns:
        Returns (skill, choices). On success `skill` is a skill instance and
        `choices` is empty. When the node affords several skills and nothing
        the character carries picks one, `skill` is None and `choices` is the
        list of skill instances they must choose between. When the node
        affords nothing, both are empty.

    Module Globals:
        SKILL_REGISTRY read.

    Methodology:
        The rule is the tool, and the order is EQUIPPED FIRST, then the rest
        of the inventory. A corpse can be butchered or brain-farmed, and what
        is in your hands is what says which you meant -- a player holding a
        knife who types `harvest corpse` means to butcher it, and does not
        want to be asked.

        Only when the character carries no tool for ANY of the node's skills
        is the choice theirs, and then it is a real question rather than a
        guess dressed as one. A node with a single skill has no question to
        ask either way, which is every node in the game today.

        Returns instances rather than classes because the caller's next move
        is always to run one, and a caller that has to remember to
        instantiate is a caller that will one day forget.

    Notes/References:
        The equipped-first rule is a design decision, not an implementation
        detail: GatheringSkill.find_tool encodes the same order for the
        single-skill case.

    Author: Nick Hobar
    Creation date: 09/10/2026
    """
    gatherable_def = get_gatherable_for_node(node)

    if gatherable_def is None:
        return None, []

    candidates = []

    for skill_key in gatherable_def.skill_keys():
        skill_class = SKILL_REGISTRY.get(skill_key)

        if skill_class is None:
            logger.log_err(
                f"resolve_gathering_skill: {gatherable_def.key} names skill "
                f"{skill_key!r}, which is not in SKILL_REGISTRY."
            )
            continue

        candidates.append(skill_class())

    if not candidates:
        return None, []

    if len(candidates) == 1:
        return candidates[0], []

    for skill in candidates:
        if skill.find_tool(character) is not None:
            return skill, []

    return None, candidates



def gathering_verbs(node) -> list:
    """
    Purpose: The clickable verbs a node affords, one per skill that works it.

    Entry:
        node is a live object carrying db.gatherable_key.

    Exit/Returns:
        Returns a list of {"command", "label"} dicts in the registry's
        declaration order. Empty for anything that is not a registered node.

    Module Globals:
        _VERB_BY_SKILL_KEY read.

    Methodology:
        The SERVER names the verb. A renderer that kept its own kind-to-verb
        table would keep sending `cut` at a corpse until someone remembered to
        edit it, which is the mistake this codebase has now made and undone
        twice.

        Built from the node's yields rather than from a table of node types,
        so a corpse that gains a Brain Farming yield gains its verb here with
        no edit -- the same guarantee GATHERABLE_REGISTRY gives everywhere
        else it is read.

        Each command NAMES the node. The verbs also work bare, because the
        cmdset hangs on the node itself, but a player may be standing beside
        two bodies and a client can only send a string.

    Notes/References:
        Consumed by the typeclasses' extra_actions, which the statefeed's
        interact_actions collects.

    Author: Nick Hobar
    Creation date: 09/10/2026
    """
    gatherable_def = get_gatherable_for_node(node)

    if gatherable_def is None:
        return []

    actions = []

    for skill_key in gatherable_def.skill_keys():
        verb = _VERB_BY_SKILL_KEY.get(skill_key)

        if not verb:
            continue

        actions.append({"command": f"{verb} {node.key}", "label": verb})

    return actions



class CmdGatherFromNode(Command):
    """
    Purpose: Base command for harvesting a resource node with a skill.

    Subclasses supply `key`/`aliases` and a `skill_key` naming the skill to
    run. The skill class itself is resolved through SKILL_REGISTRY at call
    time, so adding a gathering skill means adding its skill module and a
    four-line subclass -- no edits here, and no import of the concrete skill
    class.

    Syntax is `<verb> [<target>] [= <yield>]`. The `=` half is how a player
    names which of a node's yields they want once more than one is unlocked:
    `butcher corpse = filet`. Without it they get the best one their level
    allows.
    """
    skill_key = None
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_GATHERING

    def _parse_target_and_yield(self) -> tuple:
        """
        Purpose: Split the argument into a target name and a yield choice.

        Entry:
            self.args is the raw argument string.

        Exit/Returns:
            Returns (target_name, wanted), both stripped and either possibly
            empty.

        Module Globals:
            None.

        Methodology:
            Evennia's own `=` convention, so the two halves cannot be
            confused with each other however the node or the cut is named.
            Splitting on the FIRST `=` only, because a yield name never
            contains one and a target name should not have to be escaped.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        args = self.args.strip()

        if "=" not in args:
            return args, ""

        target_name, _, wanted = args.partition("=")

        return target_name.strip(), wanted.strip()


    def works_on(self, node) -> bool:
        """
        Purpose: Whether this command's skill can work the given object.

        Entry:
            node is any object, or None.

        Exit/Returns:
            Returns True for a registered node this command's skill appears
            on. A command with no skill_key (the generic harvest) accepts any
            registered node.

        Module Globals:
            None.

        Methodology:
            Asks GATHERABLE_REGISTRY, not the object. That is the question
            get_gatherable_for_node exists to answer, and the reason the
            per-skill is_cutting_node() predicates are gone.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        gatherable_def = get_gatherable_for_node(node)

        if gatherable_def is None:
            return False

        if self.skill_key is None:
            return True

        return self.skill_key in gatherable_def.skill_keys()


    def _candidates(self) -> list:
        """
        Purpose: Everything in reach this command could have meant.

        Entry:
            self.caller is a valid Evennia Character.

        Exit/Returns:
            Returns a list of workable nodes: those in the room first, then
            those the caller is carrying.

        Module Globals:
            None.

        Methodology:
            The room comes first, because a body on the ground is the obvious
            reading of a bare butcher. The bag is searched at all because the
            design is that a corpse may be pocketed and dealt with later, and
            a player who did that should not have to drop it again first.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        caller = self.caller
        room = getattr(caller, "location", None)
        nearby = list(room.contents) if room is not None else []

        return [
            obj for obj in nearby + list(caller.contents)
            if obj is not caller and self.works_on(obj)
        ]


    def _resolve_named(self, target_name: str):
        """
        Purpose: Find the workable node the player named, without stopping on
        an ambiguity that does not matter.

        Entry:
            target_name is a non-empty search string.

        Exit/Returns:
            Returns the object, or None after a failed search Evennia has
            already reported.

        Module Globals:
            None.

        Methodology:
            A plain search refuses on ANY multiple match, and identical
            corpses are always a multiple match. Kill two raiders on one tile,
            pocket one body, and `butcher Mutant Raider corpse` answers "More
            than one match ... Mutant Raider corpse-1 (carried), Mutant Raider
            corpse-2" -- a disambiguation the player cannot act on, between
            two objects that are the same object for every purpose this
            command has. A click in the 3D pane cannot supply a suffix at all.

            So the matches are filtered to what this SKILL can work, in
            _candidates' order -- room before bag -- and the first is taken.
            The narrowing is what makes it safe: `butcher raider` will not
            quietly pick the live one standing next to the body, because a
            live raider is not a butchery node.

            This is the same judgement commands/get_cmds.py already makes for
            `get`, and for the same reason its docstring gives: a player
            looking at eight identical chunks cannot be asked which one they
            meant.

            Falls back to a normal, noisy search when nothing workable
            matched, so "you cannot butcher a rusty pole" and Evennia's own
            not-found message both still reach the player rather than being
            swallowed into a bare "you see nothing here".

        Notes/References:
            It resolves ambiguity rather than naming the clicked object
            exactly. Two DIFFERENT workable nodes sharing a name would still
            be picked between by proximity; exact targeting would mean the
            client sending an id, which is a change to what a command accepts.

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        matches = utils.make_iter(
            self.caller.search(target_name, quiet=True))

        if matches:
            workable = [obj for obj in self._candidates() if obj in matches]

            if workable:
                return workable[0]

        return self.caller.search(target_name)


    def _resolve_target(self, target_name: str):
        """
        Purpose: Find the object this invocation acts on.

        Entry:
            target_name may be empty.

        Exit/Returns:
            Returns the object, or None after messaging the caller (or after
            Evennia's own search-failure message).

        Module Globals:
            None.

        Methodology:
            A named target is searched for, always.

            An EMPTY argument looks around instead. It used to mean "the node
            this command hangs on", which worked only because the cmdset was
            added to each node -- and that is precisely what broke the moment
            a node could be CONSUMED. Butchering a corpse deletes it, the
            cmdset goes with it, and the next butcher was not an unknown
            target but an unknown COMMAND, answered by Evennia's spell-checker
            with "Maybe you meant charcreate?".

            self.obj is still preferred when it is itself workable, so a node
            carrying the older per-object cmdset behaves exactly as before.

            Several candidates are named rather than chosen between. Two
            raiders die on one tile often enough that guessing would
            eventually guess wrong, and the player cannot see which one was
            picked until the meat is already in their bag.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 06/05/2026
        """
        if target_name:
            return self._resolve_named(target_name)

        if self.works_on(self.obj):
            return self.obj

        candidates = self._candidates()

        if not candidates:
            self.caller.msg(
                (f"You see nothing here to {self.key}.", _MSG_GATHERING))
            return None

        if len(candidates) > 1:
            names = ", ".join(sorted({obj.key for obj in candidates}))
            self.caller.msg((
                f"Which one? Name it, as in {self.key} {candidates[0].key} "
                f"-- you can see: {names}.",
                _MSG_GATHERING,
            ))
            return None

        return candidates[0]


    def pick_skill(self, target):
        """
        Purpose: Name the skill this command runs. Overridden by CmdHarvest.

        Entry:
            target is the resolved object.

        Exit/Returns:
            Returns a skill instance, or None after messaging the caller.

        Module Globals:
            SKILL_REGISTRY read.

        Methodology:
            A verb command names its own skill: a player typing `butcher` has
            already chosen, and re-deriving that from what they are holding
            would let a knife in the bag override the word they typed.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        skill_class = SKILL_REGISTRY.get(self.skill_key)

        if skill_class is None:
            logger.log_err(
                f"{type(self).__name__}: skill_key {self.skill_key!r} is not "
                f"in SKILL_REGISTRY."
            )
            self.caller.msg(("You don't know how to do that.", _MSG_GATHERING))
            return None

        return skill_class()


    def func(self) -> None:
        """
        Purpose: Resolve the target and hand it to the chosen skill.

        Entry:
            self.caller is a valid Evennia Character.
            self.obj is the gathering node this command was read from.

        Exit/Returns:
            No conditions. Messages the caller on every failure path.

        Module Globals:
            None.

        Methodology:
            Parse, resolve the target, pick the skill, run it. Every refusal
            below the skill boundary is the skill's to make and to phrase --
            this command decides only WHICH skill is asked.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 06/05/2026
        """
        target_name, wanted = self._parse_target_and_yield()
        target = self._resolve_target(target_name)

        if not target:
            return

        skill = self.pick_skill(target)

        if skill is None:
            return

        skill.execute(self.caller, target, wanted)



class CmdCutGatheringNode(CmdGatherFromNode):
    """
    Purpose: Harvest materials from a cutting node.
    """
    key = "cut"
    aliases = ["chop"]
    skill_key = skill_constants.CUTTING_SKILL_KEY



class CmdButcherGatheringNode(CmdGatherFromNode):
    """
    Purpose: Take a cut of meat off a corpse.
    """
    key = "butcher"
    skill_key = skill_constants.BUTCHERY_SKILL_KEY



class CmdHarvestGatheringNode(CmdGatherFromNode):
    """
    Purpose: Work a node with whichever skill your tool says you meant.

    The one command that does not name its skill. It exists because a corpse
    is worked by Butchery or by Brain Farming depending on what you are
    carrying, and asking the player to remember which verb goes with which
    tool is asking them to do the lookup the server can already do.
    """
    key = "harvest"

    def pick_skill(self, target):
        """
        Purpose: Choose the skill by the tool in hand.

        Entry:
            target is the resolved object.

        Exit/Returns:
            Returns a skill instance, or None after messaging the caller.

        Module Globals:
            None.

        Methodology:
            Delegates to resolve_gathering_skill, which owns the
            equipped-then-carried rule. An unresolved multi-skill node is
            reported by naming the verbs, because those are the words that
            resolve it -- telling a player "you must choose" without saying
            what the choices are is a dead end.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        skill, choices = resolve_gathering_skill(self.caller, target)

        if skill is not None:
            return skill

        if not choices:
            self.caller.msg((
                f"The {target.key} is not something you can harvest.",
                _MSG_GATHERING,
            ))
            return None

        verbs = ", ".join(sorted(choice.verb for choice in choices))
        self.caller.msg((
            f"You carry nothing that decides how to work the {target.key}. "
            f"Try one of: {verbs}.",
            _MSG_GATHERING,
        ))

        return None



# skill key -> the verb that runs it, derived from the command classes above
# so the two cannot disagree. A skill with no verb command simply has no entry
# and affords no button, which is the right answer for one that is still a
# stub: Brain Farming names yields in the registry long before it can work
# them, and a button that ran nothing would be worse than none.
_VERB_BY_SKILL_KEY = {
    command_class.skill_key: command_class.key
    for command_class in (CmdCutGatheringNode, CmdButcherGatheringNode)
}


class GatheringCmdSet(CmdSet):
    """
    Purpose: The gathering verbs, on the CHARACTER.

    They live here rather than on the node, and that placement IS the fix for
    the bug this class was written for. Butchering a corpse deletes it, and a
    cmdset hanging on the corpse is deleted with it -- so the second `butcher`
    was not "nothing to butcher here", it was "no such command", answered by
    Evennia's spell-checker with "Maybe you meant charcreate?". A verb that
    exists only while its target does cannot ever explain its own absence.

    A per-object cmdset was the wrong shape for a corpse in a second way too:
    it is `duplicates = True`, so two bodies on one tile each contributed a
    `butcher` and the player got a multiple-match prompt for the VERB rather
    than for the target.

    Every gathering verb is available to every character, and the SKILL
    refuses a node it does not work ("The rusty pole is not something you can
    butcher"). Filtering the verbs per node would mean deciding them once at
    creation, so giving an existing node type a second skill would need every
    one of them respawned -- the stale-database trap CLAUDE.md documents for
    typeclass paths in ScriptDB rows.
    """
    key = "GatheringCmdSet"

    def at_cmdset_creation(self) -> None:
        self.add(CmdCutGatheringNode())
        self.add(CmdButcherGatheringNode())
        self.add(CmdHarvestGatheringNode())



class GatheringNodeCmdSet(GatheringCmdSet):
    """
    Purpose: The per-object cmdset gathering nodes used to carry.

    Kept, and still exported, because it is PERSISTED: every gathering node
    already in the database stores this class's path in a cmdset row, and a
    path that no longer resolves is an error on every one of them at load.
    Nothing adds it any more -- see GatheringCmdSet for why -- so it leaves
    the world on its own at the next map rebuild.

    It still works while it is there: the commands are the same, and
    _resolve_target prefers self.obj when self.obj is itself workable, which
    is exactly the case a node's own cmdset produces.

    See CLAUDE.md, "An import path belongs in the code, never in a database
    row", for the general shape of this trap.
    """
    key = "GatheringNodeCmdSet"
    priority = 10
    duplicates = True
