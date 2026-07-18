class BankHandler:
    """
    Stub handler for player bank storage.

    Future design:
        Each account has a hidden container room (account.db.bank_room).
        deposit() moves an item from the character into that room.
        withdraw() moves an item from the room to the character.
        list_items() returns the room's contents.

    Current stub:
        Stores a simple list of item keys in character.db._bank_stub.
    """

    def __init__(self, obj):
        self.obj = obj

    def _get_storage(self):
        if not self.obj.db._bank_stub:
            self.obj.db._bank_stub = []
        return self.obj.db._bank_stub

    def deposit(self, item):
        storage = self._get_storage()
        storage.append(item.key)
        self.obj.db._bank_stub = storage
        item.delete()
        self.obj.msg(f"You deposit {item.key} into the bank.")

    def withdraw(self, item_key):
        storage = self._get_storage()
        if item_key not in storage:
            self.obj.msg(f"You don't have '{item_key}' stored in the bank.")
            return None
        storage.remove(item_key)
        self.obj.db._bank_stub = storage
        from world.item_database import ITEM_DB
        item_def = ITEM_DB.get(item_key)
        if item_def:
            obj = item_def.create(location=self.obj)
        else:
            self.obj.msg(f"Error: '{item_key}' is not a known item type.")
            return None
        self.obj.msg(f"You withdraw {item_def.name if item_def else item_key} from the bank.")
        return obj

    def list_items(self):
        return list(self._get_storage())
