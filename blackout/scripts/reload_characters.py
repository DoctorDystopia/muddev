import os
import sys
import argparse

# ==========================================
# STUB: Django / Evennia Standalone Setup
# ==========================================
# Since you are running this via python.exe directly from PowerShell, 
# you might need to bootstrap the Django environment before you can query the DB.
# If Evennia complains about apps not being loaded, uncomment the lines below:
# 
# import django
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")
# django.setup()
# ==========================================

from typeclasses.characters import Character

def reload_all_characters(reset_completely=False):
    # Use Django's query language to get a listing of all Character instances[cite: 1]
    for char in Character.objects.all():
        if reset_completely:
            # ==========================================
            # STUB: Complete Character Reset Logic
            # ==========================================
            # I do not know how your game handles stats, equipment, or inventory.
            # You will need to implement the specific logic to wipe them out here.
            # 
            # Examples of what you might do:
            # char.attributes.clear()
            # for item in char.contents:
            #     item.delete()
            # ==========================================
            print(f"STUB Triggered: Wiping stats/items for {char.key}...")
            pass
        
        # Call .at_object_creation on each character[cite: 1]
        char.at_object_creation()
        print(f"Reloaded at_object_creation for: {char.key}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reload and optionally reset characters.")
    parser.add_argument('--reset', action='store_true', help="Completely reset characters (stats, items, etc.)")
    args = parser.parse_args()
    
    reload_all_characters(reset_completely=args.reset)