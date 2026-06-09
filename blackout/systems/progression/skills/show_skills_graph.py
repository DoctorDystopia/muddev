import os
import sys
import matplotlib.pyplot as plt

# 1. Add your current working directory (blackout) to Python's path
sys.path.insert(0, os.path.abspath(os.getcwd()))

# 2. Tell Django where your settings are. Evennia expects this specific path.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")

# 3. Bootstrap the Evennia/Django environment
import django
django.setup()

# -------------------------------------------------------------------
# Environment is ready. Safe to import Evennia-dependent logic!
# -------------------------------------------------------------------
from systems.progression.skills.logic import calculate_xp_needed

levels = list(range(128))  # Levels 0 to 127 inclusive
total_xps = []
exp_diffs = []

# Calculate totals and differences for all levels
current_total = 0
for lvl in levels:
    total_xps.append(current_total)
    diff = calculate_xp_needed(lvl)
    exp_diffs.append(diff)
    current_total += diff

# Determine the absolute max XP (Level 127's requirement)
max_xp = total_xps[-1]

# Print the table header
print(f"{'Level':<7} | {'Experience Points':<19} | {'Exp. Diff':<11} | {'% to max'}")
print("-" * 58)

# Print the table rows
for i, lvl in enumerate(levels):
    xp = total_xps[i]
    diff = exp_diffs[i]
    
    # Calculate percentage, protecting against division by zero
    percent_to_max = (xp / max_xp) * 100 if max_xp > 0 else 0
    
    # Format the print statement with commas for large numbers and 2 decimal places for the %
    print(f"{lvl:<7} | {xp:<19,} | {diff:<11,} | {percent_to_max:>6.2f}%")

# Generate and show the graph
plt.figure(figsize=(10, 6))
plt.plot(levels, total_xps, color='blue', linewidth=2)
plt.title('Total XP vs. Level (0 to 127)')
plt.xlabel('Level')
plt.ylabel('Total Cumulative XP')
plt.grid(True, linestyle='--', alpha=0.7)
plt.tight_layout()

# Render the graph in a pop-up window
plt.show()