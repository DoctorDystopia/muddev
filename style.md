# Style Guide for Python Code

## 1.0 Introduction

Following a consistent coding style makes interpreting software easier for whoever has to debug it. The coding style presented here makes Python code easier to debug by clearly and consistently laying out the functionality so that the code becomes essentially self-documenting.

These guidelines must be followed from the outset of module design. If you wait to retrofit comments and styling, it often never gets done, and the benefits for debugging are lost because the code is already debugged.

---

## 2.0 Routine Headers (Docstrings)

The most important mechanism is to document each routine written. While C uses large comment blocks before the function, Python uses standard **docstrings** (`"""`) immediately inside the function definition. These docstrings must describe the following:

* **Purpose:** The purpose of the routine in plain English.
* **Entry:** Conditions that must be met for parameters passed in.
* **Exit/Returns:** Conditions met for values passed out or returned.
* **Module Globals:** Any globals accessed (read or written) and the expected values.
* **Methodology:** A plain English or pseudocode description of the algorithm if it is reasonably complex.
* **Notes/References:** Special notes or book references the reader should be aware of.
* **Author & Date:** The author and the date of creation in `mm/dd/yyyy` format.

```python
def configure_device(card_num: int, command: str) -> bool:
    """
    Purpose: Configure the device LAN chip to the user-specified value.
    
    Entry:
        1 <= card_num <= 3
        command is a valid string of CMD_SIZE characters
    
    Exit/Returns:
        Returns True if the chip has been reconfigured, False otherwise.
        No changes to the command string.
    
    Module variables:
        lan_is_busy[card_num - 1] read
        lan_configured[card_num - 1] written
    
    Reference: LAN Reference Guide 1991, Section 3-2
    
    Author: Joe Blow
    Creation date: 11/14/2001
    """
    # etc., etc.

```

If a routine requires no entry conditions (like an initialization routine), explicitly state "no conditions". This comprehensive documentation prevents cluttering the actual code body with messy algorithm explanations.

---

## 3.0 Spacing

### 3.1 Line Spacing

White space is crucial for easy-to-read code. Use blank lines to separate 'clumps' of code from each other, such as separating a `while` loop from its surrounding statements.

To easily isolate routines, skip **two lines** (standard PEP 8, adapting from the original three) between the end of one procedure and the start of the next.

### 3.2 Character Spacing

Appropriate spacing on a single line prevents a crowded style that causes readers to skip over dense code.

* Separate individual parameters in function calls with one space after the comma.
* Always surround comparison and assignment operators (`=`, `==`, `<`, `>`, `<=`, `>=`, `!=`, `and`, `or`) with spaces so the eye falls immediately to the operator.
* Do not butt parameters up against keywords like `if`, `while`, or `for`; leave a space before the expression.

```python
# Correct spacing
if a == 1:
    execute_steps(NO_ABORT, instructions, result)

```

### 3.3 Indentation

Absolutely no use of tabs is allowed, as different environments interpret tab widths differently. **Use four spaces for indentation** in loops, `if` statements, and functions.

---

## 4.0 Block Specification

Python enforces block specification through indentation and colons rather than bracing (`{ }`). Even if an `if` statement or a `for` loop contains only a single line of logic, you must place that logic on the next line with a four-space indent.

```python
# Correct
if a > 3:
    report_error()

# Incorrect
if a > 3: report_error()

```

---

## 5.0 Symbol Names

Use adequately descriptive symbol names rather than highly-compressed abbreviations to ensure code is self-documenting.

### 5.1 Symbol Name Conventions

* **Variables and Routines:** Use underscores (`_`) to connect words, and keep everything in all lower case. (e.g., `lan_busy_with_command`). Do not intersperse capitals.
* **Constants:** Make the name entirely capitalized with underscores separating words. (e.g., `MAX_STRING_SIZE = 12`).
* **Globals:** Global symbols should indicate their domain and class (e.g., `cmd_history_record_command`).

### 5.2 Type Definitions and Data Structures

Instead of C-structs, use Python `dataclasses` or standard classes. All complex data types passed to routines should be passed by reference (which Python does by default for mutable objects like lists and dictionaries). Use type hinting wherever possible to maintain clarity.

---

## 6.0 Routine Layout

If parameter definitions run out of room on an 80-column screen, indent the parameter names on the next line. List "control" information parameters first, followed by source and destination parameters.

```python
def some_routine_with_a_long_name(size_of_the_world: int,
                                  radiation_flux: float) -> None:

```

Align end-of-line comments with the lines of code for which they are relevant. Do not start comments inside a routine from the left-most column, as it disrupts the indentation flow.

---

## 7.0 Module Layout

Because Python does not use `.h` header files and `.c` code files, a single `.py` file implements the class or domain. To achieve the separation of public and private symbols originally intended by the `.h` / `.c` split, utilize Python's leading underscore (`_`) convention for private variables and methods.

Lead the file with a header docstring detailing the GNU license, author flags, and description of the module.

Maintain the following order within the Python file:

1. Import statements
2. Public constant definitions
3. Private constant definitions (prefixed with `_`)
4. Module globals
5. Private helper routines (prefixed with `_`)
6. Public routines / Classes

---

## 8.0 Functional Issues

* **Incrementing:** Python does not have preincrement or postincrement operators like `x++`. Use `x += 1` alone on a single line without surrounding text.
* **Maximum routine length:** Routines should not exceed 50 lines (including whitespace) and should ideally be shorter than 20 lines (excluding the header docstring).
* **External variable access:** Variables should be hidden and accessed through getter/setter routines or properties rather than made directly visible.
* **Constants vs. literals:** No use of literals (magic numbers) is permitted. Constants must be used instead, particularly for defining maximum sizes or bounds.
* **Embedded routine calls:** Do not embed routine calls in `if` statements, `for` loops, as parameters to another routine, or directly in `return` statements. This makes the code difficult to debug because the evaluated value isn't stored for easy examination. Assign the return value to a local variable first, then evaluate it.
* **Local variables:** Use specific names for local variables (except for standard counters like `i`). Do not reuse a local variable for different purposes throughout a routine; create a new, well-named variable instead.
