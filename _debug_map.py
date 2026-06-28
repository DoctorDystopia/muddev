import ast

with open(r'C:\Users\NickR\source\repos\muddev\blackout\world\maps\test_neo_cairo.py', 'r') as f:
    source = f.read()

tree = ast.parse(source)
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == 'MAPSTR':
                map_content = node.value.value

lines = map_content.split('\n')

topleft_x = next(i for i, ch in enumerate(lines[2]) if ch == '+')
topleft_y = 2
botleft_y = next(y + topleft_y + 1 for y, l in enumerate(lines[topleft_y+1:]) if l.find('+') == topleft_x)
origo_x, origo_y = topleft_x + 2, botleft_y - 1
grid = list(reversed(lines[topleft_y+2:origo_y]))

MAPSCAN = {'n': (0, 1), 'ne': (1, 1), 'e': (1, 0), 'se': (1, -1),
           's': (0, -1), 'sw': (-1, -1), 'w': (-1, 0), 'nw': (-1, 1)}
REVERSE = {'n':'s','ne':'sw','e':'w','se':'nw','s':'n','sw':'ne','w':'e','nw':'se'}
LINK_DIRS = {
    '|': {'n':'s','s':'n'},
    '-': {'e':'w','w':'e'},
    '/': {'ne':'sw','sw':'ne'},
    '\\': {'se':'nw','nw':'se'},
}

nodes = {}
links = {}

for iy, line in enumerate(grid):
    for ix, ch in enumerate(line[origo_x:]):
        if ch == ' ':
            continue
        if ch == '#':
            world_coord = (ix // 2, iy // 2)
            nodes[world_coord] = {'ix': ix, 'iy': iy}
        else:
            links[(ix, iy)] = ch

from collections import defaultdict
node_links = defaultdict(list)

for (wx, wy), node_data in sorted(nodes.items()):
    nx, ny = node_data['ix'], node_data['iy']
    for dir_name, (dx, dy) in MAPSCAN.items():
        lx, ly = nx + dx, ny + dy
        if (lx, ly) not in links:
            continue

        lch = links[(lx, ly)]
        from_dir = REVERSE[dir_name]
        link_dirs = LINK_DIRS.get(lch, {})

        if from_dir not in link_dirs:
            continue

        cur_x, cur_y = lx, ly
        cur_from = from_dir
        found_node = None

        while True:
            cur_link = links.get((cur_x, cur_y))
            if not cur_link:
                break
            out_dir = LINK_DIRS[cur_link].get(cur_from)
            if not out_dir:
                break

            odx, ody = MAPSCAN[out_dir]
            nx2, ny2 = cur_x + odx, cur_y + ody

            for (wwx, wwy), nd in nodes.items():
                if nd['ix'] == nx2 and nd['iy'] == ny2:
                    found_node = (wwx, wwy)
                    break

            if found_node:
                break

            if (nx2, ny2) in links:
                cur_x, cur_y = nx2, ny2
                cur_from = REVERSE.get(out_dir, out_dir)
            else:
                break

        if found_node:
            node_links[(wx, wy)].append((dir_name, found_node))

print('Node connectivity:')
for coord in sorted(node_links.keys()):
    print(f'  World {coord}:')
    for direction, dest in sorted(node_links[coord], key=lambda x: x[0]):
        print(f'    {direction:>4s} -> world {dest}')

print()
print(f'Total nodes: {len(nodes)}')
print(f'Node list: {sorted(nodes.keys())}')

ne_exits = [dest for d, dest in node_links.get((1, 1), []) if d == 'ne']
print()
print(f'NE exits from (1,1): {ne_exits}')
