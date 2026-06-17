# Directory of ASCII Symbols to be Used in Maps

| Symbol | Entity Type | Purpose & Implementation |
| --- | --- | --- |
| `@` | Player Character | The universal standard for representing the player's avatar. |
| `.` | Walkable Ground | Empty spaces, plazas, or indoor flooring. |
| `#` | Wall / Street | Impassable structures, or generic street tiles (GridTile) depending on the map's scale. |
| `+` | Bounding Box | Critical Engine Symbol: Must be placed exactly at the top-left and bottom-left of your map string to define the grid boundary. |
| `-`, `&#124;`, `/`, `\` | Node Links | Critical Engine Symbol: Connects rooms together. They must not have trailing spaces that break grid alignment. |
| `<` / `>` | Stairs Up / Down | Standard transition symbols. These can map to a TransitionNode to stitch Z-levels together. |
| `X` | Trade Town Node | A specialized commercial tile mapped directly to GridTile via the prototype dictionary. |
| `S` | Shop | Standard commercial vendor nodes. |
| `M` | Medical Bay | Healing and recovery nodes. |