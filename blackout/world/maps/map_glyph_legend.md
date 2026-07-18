# xyzgrid LEGEND Mapping

The canonical LEGEND is defined in `evennia/evennia/contrib/grid/xyzgrid/xymap_legend.py:1354`.

## Nodes (MapNode)

| Symbol | Class | Description |
| --- | --- | --- |
| `#` | `BasicMapNode` | Standard room/node. Spawned as `xyz_room`. |
| `T` | `MapTransitionNode` | Transition to another map (not spawned in-game). Must set `target_map_xyz`. |
| `I` | `InterruptMapNode` | Point of interest. Pathfinder includes it; auto-stepper stops when passing through. |

## Links (MapLink)

| Symbol | Class | Description |
| --- | --- | --- |
| `|` | `NSMapLink` | Two-way North-South link. |
| `-` | `EWMapLink` | Two-way East-West link. |
| `/` | `NESWMapLink` | Two-way Northeast-Southwest link. |
| `\` | `SENWMapLink` | Two-way Southeast-Northwest link. |
| `x` | `CrossMapLink` | Two-way crossing NE-SW and SE-NW links. |
| `+` | `PlusMapLink` | Two-way crossing N-S and E-W links. |
| `v` | `NSOneWayMapLink` | One-way North-to-South link. |
| `^` | `SNOneWayMapLink` | One-way South-to-North link. |
| `<` | `EWOneWayMapLink` | One-way East-to-West link. |
| `>` | `WEOneWayMapLink` | One-way West-to-East link. |
| `o` | `RouterMapLink` | Smart rerouter link; builds knees, pass-throughs, and crossings based on topology. |
| `u` | `UpMapLink` | Up direction. Stays on same Z-level ("fake" up). |
| `d` | `DownMapLink` | Down direction. Stays on same Z-level ("fake" down). |
| `b` | `BlockedMapLink` | Blocked path. Pathfinder assigns `BIGVAL` weight to all directions. |
| `i` | `InterruptMapLink` | Passable but auto-stepper stops before crossing. Display is invisible (smart-invisible). |
| `t` | `TeleporterMapLink` | Teleporter. Must appear in pairs on the same XY map; creates a two-way link between them. |

## Blackout Overrides (`blackout/world/maps/legend.py`)

| Symbol | Class | Description |
| --- | --- | --- |
| `#` | `WalkableTile` | Overrides the default `BasicMapNode`. All `#` rooms render as `·` (middle dot) on the in-game map. Spawned as `xyz_room`. |

Maps merge `BLACKOUT_LEGEND` into their local `LEGEND` dict and add map-specific overrides on top:

```python
from .legend import BLACKOUT_LEGEND

LEGEND = {
    **BLACKOUT_LEGEND,
    "P": RustyPoleNode,
}
```

The `BLACKOUT_LEGEND` maps `"#"` to `WalkableTile`, which has `display_symbol = "·"`. The MAPSTR always uses `#` for walkable tiles — no map string changes needed.

## Notes

- Nodes must be placed on even (X, Y) coordinates on the xygrid.
- Links can be placed anywhere on the xygrid (odd or even coords).
- The default prototypes reference `xyz_room` (nodes) and `xyz_exit` (links) from the xyzgrid contrib.
- All link classes default to `prototype = "xyz_exit"` except transition/teleporter nodes which have `prototype = None`.
