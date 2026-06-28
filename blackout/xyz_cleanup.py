import os
os.environ["DJANGO_SETTINGS_MODULE"] = "server.conf.settings"

import django
django.setup()

import evennia

evennia._init()

from evennia.objects.models import ObjectDB
from evennia.contrib.grid.xyzgrid.xyzroom import MAP_Z_TAG_CATEGORY

ZCOORDS_TO_CLEAN = [
    "oasis",
    "trade town sector 1",
]

for zcoord in ZCOORDS_TO_CLEAN:
    rooms = ObjectDB.objects.filter(
        db_tags__db_key__iexact=zcoord,
        db_tags__db_category=MAP_Z_TAG_CATEGORY,
    )
    print(f"\nDeleting {rooms.count()} objects tagged '{zcoord}'...")
    for r in rooms:
        try:
            print(f"  #{r.id} '{r.key}' [{r.db_typeclass_path}]")
            r.delete()
        except Exception as e:
            print(f"  Skipping #{r.id} '{r.key}': {e}")

print("\nDone.")
