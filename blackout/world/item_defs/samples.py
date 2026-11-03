"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: ItemDef entries for the Augmentation samples (DESIGN-0015,
             Phase 4). A sample is the bone of OSRS Prayer: `graft` consumes
             it for Augmentation XP, anywhere at `sample_xp`, and more on a
             tile that holds an Augmentation Locus.

             Each sample names its kind (Nick, 10/30/2026): a biological
             sample or a technological sample. The kind is the `sample_kind`
             field AND a tag of the SAMPLE_TAG_CATEGORY, so a search by tag
             finds every sample of one kind. The flavour text is Nick's.

             A neural residue from Brain Farming is a later sample. That
             skill has no loop yet, so the item waits for it (Nick,
             10/30/2026).

             Every `sample_xp` is a placeholder until Nick tunes it. The
             command reads the attribute off the item, so a tuned def
             reaches the samples that already exist.
"""

from systems.gameplay.augmentation import constants as aug_const
from world.item_database import ItemDef


ITEMS = {
    # The first biological sample. Butchery takes it off a mutant corpse at
    # level 0, and the mutants drop it too (world/loot_defs/hostile.py).
    "mutant_gland": ItemDef(
        key="mutant_gland",
        name="mutant gland",
        desc="Hot and prickly. Pulsating along with you.",
        value=20,
        weight=0.5,
        tradeable=True,
        stackable=True,
        sample_xp=15,
        sample_kind=aug_const.SAMPLE_KIND_BIO,
        tags=[(aug_const.SAMPLE_KIND_BIO, aug_const.SAMPLE_TAG_CATEGORY)],
    ),

    # The first technological sample. The floating eye drops it: no robot
    # hostile exists yet, and the eye is the one machine-like hostile.
    "cyber_shard": ItemDef(
        key="cyber_shard",
        name="cyber shard",
        desc="Remnants of some kind of microchip. Could use a new home.",
        value=45,
        weight=0.2,
        tradeable=True,
        stackable=True,
        sample_xp=40,
        sample_kind=aug_const.SAMPLE_KIND_TECHNO,
        tags=[(aug_const.SAMPLE_KIND_TECHNO, aug_const.SAMPLE_TAG_CATEGORY)],
    ),
}
