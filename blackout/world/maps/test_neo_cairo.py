# mygame/world/maps/test_neo_cairo.py

from evennia.contrib.grid.xyzgrid.xymap_legend import MapNode

class TradeTownNode(MapNode):
    display_symbol = "X" # This must have a visual size of exactly 1
    prototype = {"typeclass": "typeclasses.rooms.GridTile"} 

XYMAP_DATA = {
    "zcoord": "trade town sector 1",
    "map": """
+

  #-#-#-#-#-#-#-#
  | | | | | | | |
  #-#-#-#-#-#-#-#
  | | | | | | | |
  #-#-#-#-#-#-#-#

+
    """,
    "legend": {
        "#": TradeTownNode 
    }
}