This is the structure of the Evennia library:
```text
    evennia

        __init__.py - The “flat API” of Evennia resides here.

        __main__.py - Entrypoint for calling Evennia as a module.

        settings_default.py - Root settings of Evennia. Copy settings from here to mygame/server/settings.py file.

        commands/ - The command parser and handler.

            default/ - The default commands and cmdsets.

        comms/ - Systems for communicating in-game.

        contrib/ - Optional plugins too game-specific for core Evennia.

        game_template/ - Copied to become the “game directory” when using evennia --init.

        help/ - Handles the storage and creation of help entries.

        locale/ - Language files (i18n).

        locks/ - Lock system for restricting access to in-game entities.

        objects/ - In-game entities (all types of items and Characters).

        prototypes/ - Object Prototype/spawning system and OLC menu

        accounts/ - Out-of-game Session-controlled entities (accounts, bots etc)

        scripts/ - Out-of-game entities equivalence to Objects, also with timer support.

        server/ - Core server code and Session handling.

            portal/ - Portal proxy and connection protocols.

        typeclasses/ - Abstract classes for the typeclass storage and database system.

        utils/ - Various miscellaneous useful coding resources.

        web/ - Web resources and webserver. Partly copied into game directory on initialization.
```

The __init__.py file is a special Python filename used to represent a Python ‘package’. When you import evennia on its own, you import this file. When you do evennia.foo Python will first look for a property .foo in __init__.py and then for a module or folder of that name in the same location.

While all the actual Evennia code is found in the various folders, the __init__.py represents the entire package evennia. It contains “shortcuts” to code that is actually located elsewhere. Most of these shortcuts are listed if you scroll down a bit on the Evennia-API page.