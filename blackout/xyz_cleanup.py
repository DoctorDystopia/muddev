import evennia

evennia._init()

from evennia.objects.models import ObjectDB
from evennia.contrib.grid.xyzgrid.xyzroom import MAP_Z_TAG_CATEGORY

map_name = "trade town sector 1"
rooms = ObjectDB.objects.filter(
    db_tags__db_key__iexact=map_name,
    db_tags__db_category=MAP_Z_TAG_CATEGORY,
)
print(f"Deleting {rooms.count()} rooms tagged '{map_name}'...")
for r in rooms:
    print(f"  #{r.id} '{r.key}' [{r.db_typeclass_path}]")
    r.delete()
print("Done.")
