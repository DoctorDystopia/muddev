from typeclasses.scripts import Script


class ShopkeepCleanup(Script):
    """
    Periodically removes excess items from a shopkeep's inventory
    to prevent accumulation from player sales.
    Attached automatically by ShopkeepNPC.at_object_creation.
    """

    def at_script_creation(self):
        self.key = "shopkeep_cleanup"
        self.desc = "Periodically removes excess items from this shopkeep"
        self.interval = 86400
        self.persistent = True

    def at_repeat(self):
        shopkeep = self.obj
        if not shopkeep:
            self.stop()
            return

        max_items = shopkeep.db.max_held_items or 20
        contents = list(shopkeep.contents)
        if len(contents) > max_items:
            to_remove = contents[:len(contents) - max_items]
            for item in to_remove:
                try:
                    item.delete()
                except Exception:
                    pass
