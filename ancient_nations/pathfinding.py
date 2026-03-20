"""
pathfinding.py – A* pathfinding for army movement.
"""
import heapq
from constants import *

# Precompute move costs once so the inner loop does no division or max() calls.
_COST_MOUNTAIN = 999
_COST_OCEAN    = max(1, int(10 / SPD_OCEAN))
_COST_RIVER    = max(1, int(10 / SPD_RIVER))
_COST_ROAD     = max(1, int(10 / SPD_ROAD))
_COST_PLAIN    = max(1, int(10 / SPD_PLAIN))

_NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))


# Extra tiles in each direction beyond the start-to-end bounding box.
# Allows A* to route around moderate obstacles without searching the whole map.
_BOX_MARGIN = 15


def find_path(world, sx, sy, tx, ty, nation_idx=None, allow_ocean=True,
              road_allied=None):
    """
    A* path from (sx,sy) to (tx,ty).
    Returns list of (x,y) steps NOT including start, or [] if unreachable.
    Mountains are very costly (avoided). road_allied is a set of nation indices
    whose territory counts as road-speed (Tier-3 alliance shared-roads benefit).

    Search is bounded to a box around the start/end rectangle plus _BOX_MARGIN
    tiles of slack for obstacle detours.  Destinations requiring a detour wider
    than the margin return [] and are retried next turn with a fresh target.
    """
    road_allied = road_allied or set()
    if sx == tx and sy == ty:
        return []

    rows = world.tiles   # direct 2-D list access — avoids world.t() call overhead

    # Bounding box that contains both endpoints plus margin for detours.
    bx0 = max(0,        min(sx, tx) - _BOX_MARGIN)
    bx1 = min(MAP_SIZE, max(sx, tx) + _BOX_MARGIN + 1)
    by0 = max(0,        min(sy, ty) - _BOX_MARGIN)
    by1 = min(MAP_SIZE, max(sy, ty) + _BOX_MARGIN + 1)

    open_set  = []
    heapq.heappush(open_set, (0, sx, sy))
    came_from = {}
    g_score   = {(sx, sy): 0}
    visited   = set()        # closed set — each node finalised at most once

    while open_set:
        _, cx, cy = heapq.heappop(open_set)

        if (cx, cy) in visited:
            continue
        visited.add((cx, cy))

        if cx == tx and cy == ty:
            path = []
            pos  = (cx, cy)
            while pos in came_from:
                path.append(pos)
                pos = came_from[pos]
            return list(reversed(path))

        cur_g = g_score[(cx, cy)]

        for dx, dy in _NEIGHBOURS:
            nx, ny = cx + dx, cy + dy
            if nx < bx0 or nx >= bx1 or ny < by0 or ny >= by1:
                continue
            if (nx, ny) in visited:
                continue

            t       = rows[ny][nx]
            terrain = t.terrain

            if terrain == TERRAIN_MOUNTAIN:
                cost = _COST_MOUNTAIN
            elif terrain == TERRAIN_OCEAN:
                if not allow_ocean:
                    continue
                cost = _COST_OCEAN
            elif terrain == TERRAIN_RIVER:
                cost = _COST_RIVER
            elif t.road or (t.owner in road_allied):
                cost = _COST_ROAD
            else:
                cost = _COST_PLAIN

            new_g = cur_g + cost
            key   = (nx, ny)
            if new_g < g_score.get(key, 2_000_000):
                g_score[key]  = new_g
                f = new_g + abs(nx - tx) + abs(ny - ty)   # inlined heuristic
                heapq.heappush(open_set, (f, nx, ny))
                came_from[key] = (cx, cy)

    return []   # unreachable
