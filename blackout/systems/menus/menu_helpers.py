
from evennia.utils.utils import inherits_from
from evennia.utils.evmenu import EvMenuGotoAbortMessage


# Public constant definitions
ERROR_COLOR = "|r"
RESET_COLOR = "|n"



def _go_back(caller: object,
             raw_string: str,
             previous_node: str = "start",
             **kwargs) -> str:
    """
    Purpose: Generic goto-callable that returns to a named previous node.

    Entry:
        caller is a valid Evennia Object
        raw_string is the raw input string from the user
        previous_node is the name of the node to return to (default "start")
        **kwargs are additional keyword arguments

    Exit/Returns:
        Returns the previous_node name as a string.

    Module Globals:
        None

    Methodology:
        Simple passthrough that returns the named previous node.
        Useful for "Back" options in menus.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    return_node = previous_node

    return return_node



def _exit_menu(caller: object,
               raw_string: str,
               **kwargs) -> None:
    """
    Purpose: Generic goto-callable that exits the current menu.

    Entry:
        caller is a valid Evennia Object
        raw_string is the raw input string from the user
        **kwargs are additional keyword arguments

    Exit/Returns:
        Returns None to signal menu exit.

    Module Globals:
        None

    Methodology:
        Returns None which EvMenu interprets as "close menu".

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    return_value = None

    return return_value



def _validate_prerequisite(caller: object,
                           skill_key: str,
                           required_level: int,
                           error_message: str) -> bool:
    """
    Purpose: Checks if a caller meets a skill prerequisite and aborts if not.

    Entry:
        caller is a valid Evennia Character object
        skill_key is a valid string key in SKILL_REGISTRY
        required_level is a non-negative integer
        error_message is a string to show on failure

    Exit/Returns:
        Returns True if prerequisite is met.
        Raises EvMenuGotoAbortMessage if not met.

    Module Globals:
        ERROR_COLOR read
        RESET_COLOR read

    Methodology:
        Delegates to caller.skills.meets_prerequisite. On failure,
        raises EvMenuGotoAbortMessage with a colored error string.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    meets_req = caller.skills.meets_prerequisite(skill_key, required_level)

    if not meets_req:
        colored_message = f"{ERROR_COLOR}{error_message}{RESET_COLOR}"
        raise EvMenuGotoAbortMessage(colored_message)

    return True



def _has_tool_in_inventory(caller: object,
                           tool_keywords: list,
                           error_message: str) -> bool:
    """
    Purpose: Checks if the caller possesses an item matching tool keywords.

    Entry:
        caller is a valid Evennia Character object
        tool_keywords is a list of string keywords to match
        error_message is a string to show on failure

    Exit/Returns:
        Returns True if a matching tool is found.
        Raises EvMenuGotoAbortMessage if not found.

    Module Globals:
        ERROR_COLOR read
        RESET_COLOR read

    Methodology:
        Iterates caller.contents looking for any item whose key
        matches any keyword in tool_keywords (case-insensitive).

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    has_tool = any(
        item.key.lower() == keyword.lower()
        for item in caller.contents
        for keyword in tool_keywords
    )

    if not has_tool:
        colored_message = f"{ERROR_COLOR}{error_message}{RESET_COLOR}"
        raise EvMenuGotoAbortMessage(colored_message)

    return True
