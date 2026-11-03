"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The Augmentation skill (DESIGN-0015): the Grit pool that each
             lit augment drains, and later the augments, their handler, and
             the rig.

Empty of imports on purpose. The pool module imports the statefeed, and the
statefeed reads the pool inside `emit_vitals`. A re-export here would close
that ring at import time.
"""
