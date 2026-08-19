"""
GNU License or generic module header.
Author: Danny Hered
Creation date: 08/17/2026
Description: Configuration for Stat Tracking.
"""

# Stat keys referenced by name from code outside systems/stat_tracker/. Kept
# here so a rename is a one-line change rather than a grep for string
# literals -- combat, shop, and quest code will reference these by name.

KILLS_PER_HOSTILE_STAT_KEY = "kills_per_hostile" # mixins.py -> at_death
CUTTING_TOTALS_STAT_KEY    = "cutting_totals"    # cutting.py _execute_gathering
CREDITS_SPENT_STAT_KEY     = "credits_spent"     # shop_service.py execute_buy
# DEATHS_PER_ENEMY_STAT_KEY                      # mixins.py -> at_death
# MATERIAL_TOTALS_STAT_KEY = "TOTAL"
# CATEGORY_KILLS_STAT_KEY = "category_kills"
# DEATHS_TOTAL_STAT_KEY
# DAMAGE_DEALT_STAT_KEY // too many writes?
# DAMAGE_TAKEN_STAT_KEY
# HIGHEST_HIT # per weapon?
# CREDITS_EARNED
# CREDITS_SPENT
# HEALTH_RESTORED_FROM_FOOD
# "items_sold"