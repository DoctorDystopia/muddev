"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Tunables and player-facing strings for eating.

             Eating is the food chain's last stage and the only one that is a
             MECHANIC rather than a recipe. Everything it can be tuned by lives
             here, for the same reason the curing package splits this way: a
             constants module nothing imports back is the one thing every other
             module in the package can safely depend on.

             Why ticks and not seconds
             -------------------------
             Both delays below are in TICKS, read against the universal
             0.6s tick in systems/core/tick/. That is not borrowed from combat
             -- the tick is the game's clock, and auto-walk, auras, NPC
             definitions and item definitions all already express cadence in it.

             Expressing an eat delay in wall-clock seconds would quantise
             against the tick grid anyway, and badly: 3 ticks is 1.8s, and a
             1.8s wall-clock cooldown started mid-tick expires somewhere inside
             a tick rather than on one. OSRS food delays are tick counts
             because the precision is the mechanic.
"""



from systems.interface.ui import colors



# Public constant definitions

# Ticks before a character who has just eaten may eat again.
#
# Three is OSRS's standard for ordinary food, and the number most food in
# Blackout should carry. A food overrides it only to be unusual.
STANDARD_EAT_DELAY_TICKS: int = 3

# Ticks added to a combatant's weapon cooldown when they eat.
#
# Also three for ordinary food. The cured meats override it to two, which is
# the Cooked karambwan property: a player who eats one may swing one tick
# (0.6s) sooner than one who ate anything else.
#
# Read in the OSRS sense, which is worth stating because the pair is easy to
# invert: the wiki's "Food/Fast foods" table lists ATTACK delay first and EAT
# delay second, so Cooked karambwan's famous (2, 3) is a 2-tick attack delay
# and a 3-tick eat delay -- the fast half is the swing, not the second bite.
STANDARD_ATTACK_DELAY_TICKS: int = 2 + 1

# The cured meats' attack delay -- the karambwan number, named rather than
# typed into four ItemDefs.
CURED_MEAT_ATTACK_DELAY_TICKS: int = 2

# Runtime attribute holding the tick a character may next eat on.
#
# NDB, and that is a correctness requirement rather than a preference.
# BlackoutTickEngine.current_tick() is monotonic WITHIN A PROCESS and resets to
# zero on a reload, so a tick number written to db would outlive the counter it
# is compared against: a character who ate at tick 50,000 would be refused food
# for 50,000 ticks -- eight hours -- after the next restart.
#
# Being as ephemeral as the clock is therefore the right shape, and it is what
# combat already does with ndb.cooldown_ticks. Losing a 1.8s delay to a reload
# costs nothing; a cure's five minutes is the case that needed persisting, and
# that one is stored as an absolute wall-clock time for exactly this reason.
NEXT_EAT_TICK_ATTR: str = "_next_eat_tick"



# Message templates

MSG_EATEN = "You eat the {item}."
MSG_HEALED = f"{{item}} restores {colors.SUCCESS_COLOR}{{healed}}{colors.RESET_COLOR} hit points."
MSG_NO_EFFECT = "The {item} goes down, and does you no good at all."
MSG_NOT_EDIBLE = "You cannot eat {item}."
MSG_TOO_SOON = "You are still swallowing."
MSG_NOTHING_NAMED = "Eat what?"
