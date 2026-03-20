"""
world.py – Map generation and tile system.
100×100 tile grid (10×10 outer regions, each 10×10 inner tiles).
"""
import random
import math
from constants import *

# Precomputed (dx, dy) offsets for each integer radius used by tiles_in_radius.
# Built on first use; eliminates math.dist from the inner loop entirely.
_RADIUS_OFFSETS: dict = {}

def _get_radius_offsets(r: int) -> list:
    if r not in _RADIUS_OFFSETS:
        r2 = r * r
        _RADIUS_OFFSETS[r] = [
            (dx, dy)
            for dy in range(-r, r + 1)
            for dx in range(-r, r + 1)
            if dx * dx + dy * dy <= r2
        ]
    return _RADIUS_OFFSETS[r]


# ─────────────────────────────────────────────────────────────────────────────
class Tile:
    __slots__ = [
        'x','y','terrain','elevation','moisture',
        'owner',          # int nation idx or -1
        'deposits',       # {RES_*: float}  natural deposits
        'entity',         # None | 'farm' | 'mine' | 'castle'
        'road',           # bool
        'town',           # Town obj or None
        'army',           # Army obj or None  (top army on tile)
        'armies',         # list of Army objs
        'captured_turn',
    ]

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.terrain  = TERRAIN_PLAIN
        self.elevation= 0.5
        self.moisture = 0.5
        self.owner    = -1
        self.deposits = {RES_FOOD:0, RES_WOOD:0, RES_METAL:0, RES_GOLD:0}
        self.entity   = None
        self.road     = False
        self.town     = None
        self.army     = None
        self.armies   = []
        self.captured_turn = -1

    def is_land(self):
        return self.terrain != TERRAIN_OCEAN

    def is_passable(self):
        return self.terrain != TERRAIN_MOUNTAIN

    def can_build_farm(self):
        return (self.terrain in (TERRAIN_PLAIN, TERRAIN_RIVER, TERRAIN_FOREST)
                and self.entity is None and self.town is None)

    def can_build_mine(self):
        return self.terrain == TERRAIN_MOUNTAIN and self.entity is None

    def can_build_castle(self):
        return (self.terrain not in (TERRAIN_OCEAN, TERRAIN_MOUNTAIN)
                and self.entity != 'castle' and self.town is None)

    def terrain_speed(self):
        if self.terrain == TERRAIN_OCEAN:   return SPD_OCEAN
        if self.terrain == TERRAIN_RIVER:   return SPD_RIVER
        if self.road:                        return SPD_ROAD
        return SPD_PLAIN

    def display_char(self, show_owner=True):
        if self.town:
            lvl_chars = ['t','T','C','@']
            c = lvl_chars[min(self.town.level-1, 3)]
            if show_owner and self.owner >= 0:
                return NATION_COLORS[self.owner] + c + RESET
            return c
        if self.armies:
            c = 'A'
            if show_owner and self.owner >= 0:
                return NATION_COLORS[self.owner] + c + RESET
            return c
        if self.entity == 'castle': c = '#'
        elif self.entity == 'farm': c = 'f'
        elif self.entity == 'mine': c = 'm'
        elif self.road:             c = '+'
        else:                       c = TERRAIN_CHARS[self.terrain]

        if show_owner and self.owner >= 0:
            return NATION_COLORS[self.owner] + c + RESET
        return TERRAIN_COLORS[self.terrain] + c + RESET


# ─────────────────────────────────────────────────────────────────────────────
class World:
    def __init__(self, seed=None):
        self.seed = seed or random.randint(0, 9999999)
        random.seed(self.seed)
        self.tiles = [[Tile(x,y) for x in range(MAP_SIZE)] for y in range(MAP_SIZE)]
        self._generate()

    # ── accessors ──────────────────────────────────────────────────────────
    def t(self, x, y) -> Tile:
        return self.tiles[y][x]

    def in_bounds(self, x, y):
        return 0 <= x < MAP_SIZE and 0 <= y < MAP_SIZE

    def neighbors4(self, x, y):
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx,ny = x+dx, y+dy
            if self.in_bounds(nx,ny):
                yield self.tiles[ny][nx]

    def neighbors8(self, x, y):
        for dx in range(-1,2):
            for dy in range(-1,2):
                if dx==0 and dy==0: continue
                nx,ny=x+dx,y+dy
                if self.in_bounds(nx,ny):
                    yield self.tiles[ny][nx]

    def outer_region(self, ox, oy):
        """Return list of tiles in outer region (ox,oy)."""
        tiles=[]
        for y in range(oy*INNER_SIZE,(oy+1)*INNER_SIZE):
            for x in range(ox*INNER_SIZE,(ox+1)*INNER_SIZE):
                tiles.append(self.tiles[y][x])
        return tiles

    # ── generation pipeline ────────────────────────────────────────────────
    def _generate(self):
        self._gen_heightmap()
        self._assign_terrain()
        self._gen_rivers()
        self._ensure_oceans()
        self._calc_moisture()
        self._refine_biomes()
        self._distribute_resources()
        self._calc_resource_values()

    # ── heightmap via layered noise ────────────────────────────────────────
    def _gen_heightmap(self):
        S = MAP_SIZE
        h = [[0.0]*S for _ in range(S)]

        # several octaves of value noise
        for octave in range(5):
            freq  = 2**(octave+1)
            amp   = 0.5**(octave)
            ox_off = random.uniform(0,100)
            oy_off = random.uniform(0,100)
            for y in range(S):
                for x in range(S):
                    h[y][x] += amp * self._value_noise(
                        x/S*freq + ox_off, y/S*freq + oy_off)

        # normalise
        mn = min(h[y][x] for y in range(S) for x in range(S))
        mx = max(h[y][x] for y in range(S) for x in range(S))
        rng = mx - mn or 1
        for y in range(S):
            for x in range(S):
                self.tiles[y][x].elevation = (h[y][x]-mn)/rng

    def _value_noise(self, fx, fy):
        """Smooth interpolated grid noise."""
        ix,iy = int(fx),int(fy)
        tx,ty = fx-ix, fy-iy
        tx = tx*tx*(3-2*tx)
        ty = ty*ty*(3-2*ty)
        def rv(a,b): return self._rng_hash(a,b)
        return (rv(ix,iy)*(1-tx)*(1-ty) + rv(ix+1,iy)*tx*(1-ty) +
                rv(ix,iy+1)*(1-tx)*ty   + rv(ix+1,iy+1)*tx*ty)

    def _rng_hash(self, x, y):
        n = x * 374761393 + y * 668265263 + self.seed
        n = (n ^ (n >> 13)) * 1274126177
        return ((n ^ (n >> 16)) & 0x7fffffff) / 0x7fffffff

    # ── terrain assignment ─────────────────────────────────────────────────
    def _assign_terrain(self):
        for y in range(MAP_SIZE):
            for x in range(MAP_SIZE):
                e = self.tiles[y][x].elevation
                if e < 0.30:
                    self.tiles[y][x].terrain = TERRAIN_OCEAN
                elif e < 0.45:
                    self.tiles[y][x].terrain = TERRAIN_PLAIN
                elif e < 0.62:
                    self.tiles[y][x].terrain = TERRAIN_FOREST
                elif e < 0.78:
                    self.tiles[y][x].terrain = TERRAIN_PLAIN
                else:
                    self.tiles[y][x].terrain = TERRAIN_MOUNTAIN

    # ── rivers ─────────────────────────────────────────────────────────────
    def _gen_rivers(self):
        """Trace rivers from mountain peaks towards ocean."""
        # find mountain peaks (local maxima)
        peaks = []
        for y in range(2, MAP_SIZE-2):
            for x in range(2, MAP_SIZE-2):
                t = self.tiles[y][x]
                if t.terrain == TERRAIN_MOUNTAIN and t.elevation > 0.85:
                    peaks.append((x,y))

        random.shuffle(peaks)
        num_rivers = MAP_SIZE // 10
        for px,py in peaks[:num_rivers]:
            self._trace_river(px, py)

    def _trace_river(self, sx, sy):
        x,y = sx,sy
        visited = set()
        for _ in range(MAP_SIZE*2):
            key=(x,y)
            if key in visited: break
            visited.add(key)
            t = self.tiles[y][x]
            if t.terrain == TERRAIN_OCEAN: break
            if t.terrain != TERRAIN_MOUNTAIN:
                t.terrain = TERRAIN_RIVER
            # pick lowest neighbour (horizontal/vertical only)
            candidates = []
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                nx,ny=x+dx,y+dy
                if self.in_bounds(nx,ny):
                    candidates.append((self.tiles[ny][nx].elevation,nx,ny))
            if not candidates: break
            candidates.sort()
            best_e,bx,by = candidates[0]
            if best_e >= self.tiles[y][x].elevation and t.terrain!=TERRAIN_OCEAN:
                # pick random direction to break ties / meander
                random.shuffle(candidates)
                _,bx,by = candidates[0]
            x,y = bx,by

    # ── ensure distinct ocean bodies ───────────────────────────────────────
    def _ensure_oceans(self):
        """Make map edges ocean so continents are properly bordered."""
        for x in range(MAP_SIZE):
            for border_y in [0,1,MAP_SIZE-2,MAP_SIZE-1]:
                self.tiles[border_y][x].terrain = TERRAIN_OCEAN
        for y in range(MAP_SIZE):
            for border_x in [0,1,MAP_SIZE-2,MAP_SIZE-1]:
                self.tiles[y][border_x].terrain = TERRAIN_OCEAN

    # ── moisture: proximity to water ───────────────────────────────────────
    def _calc_moisture(self):
        wet_terrain = {TERRAIN_OCEAN, TERRAIN_RIVER}
        S = MAP_SIZE
        dist = [[999]*S for _ in range(S)]
        from collections import deque
        q = deque()
        for y in range(S):
            for x in range(S):
                if self.tiles[y][x].terrain in wet_terrain:
                    dist[y][x]=0
                    q.append((x,y))
        while q:
            x,y=q.popleft()
            d=dist[y][x]
            for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                if self.in_bounds(nx,ny) and dist[ny][nx]>d+1:
                    dist[ny][nx]=d+1
                    q.append((nx,ny))
        max_d = max(dist[y][x] for y in range(S) for x in range(S)) or 1
        for y in range(S):
            for x in range(S):
                self.tiles[y][x].moisture = 1.0 - dist[y][x]/max_d

    # ── refine biomes using moisture ───────────────────────────────────────
    def _refine_biomes(self):
        for y in range(MAP_SIZE):
            for x in range(MAP_SIZE):
                t = self.tiles[y][x]
                if t.terrain in (TERRAIN_OCEAN, TERRAIN_MOUNTAIN, TERRAIN_RIVER):
                    continue
                if t.moisture < 0.15 and t.elevation < 0.55:
                    t.terrain = TERRAIN_DESERT
                elif t.moisture > 0.45 and t.terrain == TERRAIN_PLAIN:
                    if random.random() < 0.5:
                        t.terrain = TERRAIN_FOREST

    # ── resource deposits ─────────────────────────────────────────────────
    def _distribute_resources(self):
        for y in range(MAP_SIZE):
            for x in range(MAP_SIZE):
                t = self.tiles[y][x]
                d = t.deposits
                if t.terrain == TERRAIN_OCEAN:
                    continue
                if t.terrain == TERRAIN_RIVER:
                    d[RES_FOOD]  = random.uniform(4, 8)
                    d[RES_METAL] = random.uniform(0.2, 0.8)  # alluvial metal
                elif t.terrain == TERRAIN_PLAIN:
                    if t.moisture > 0.3:
                        d[RES_FOOD]  = random.uniform(1, 5)
                    d[RES_METAL] = random.uniform(0.1, 0.5)  # surface ore
                elif t.terrain == TERRAIN_FOREST:
                    d[RES_WOOD]  = random.uniform(3, 7)
                    d[RES_FOOD]  = random.uniform(0.5, 2)
                    d[RES_METAL] = random.uniform(0.1, 0.4)
                elif t.terrain == TERRAIN_MOUNTAIN:
                    d[RES_METAL] = random.uniform(3, 8)   # rich veins
                    d[RES_FOOD]  = random.uniform(0.1, 0.5)
                elif t.terrain == TERRAIN_DESERT:
                    d[RES_METAL] = random.uniform(0.3, 1.0)  # mineral deposits

        # Scatter rich metal clusters (veins) on non-ocean land
        land_tiles = [(x,y) for y in range(MAP_SIZE) for x in range(MAP_SIZE)
                      if self.tiles[y][x].is_land()]
        for _ in range(MAP_SIZE * MAP_SIZE // 80):
            if land_tiles:
                x,y = random.choice(land_tiles)
                t = self.tiles[y][x]
                t.deposits[RES_METAL] += random.uniform(1, 3)

        # scatter rare gold deposits
        for _ in range(MAP_SIZE * MAP_SIZE // 150):
            if land_tiles:
                x,y = random.choice(land_tiles)
                self.tiles[y][x].deposits[RES_GOLD] = random.uniform(1, 4)

    # ── resource rarity values ─────────────────────────────────────────────
    def _calc_resource_values(self):
        totals = [0.0]*NUM_RESOURCES
        for y in range(MAP_SIZE):
            for x in range(MAP_SIZE):
                for r in range(NUM_RESOURCES):
                    totals[r] += self.tiles[y][x].deposits[r]
        max_t = max(totals) or 1
        # value = inverse of relative abundance (0..1 scale)
        self.resource_values = [max_t / (totals[r]+1) for r in range(NUM_RESOURCES)]
        # Normalise so most common = 1.0
        mv = min(self.resource_values)
        self.resource_values = [v/mv for v in self.resource_values]

    # ── helper: find valid land spawn points ──────────────────────────────
    def valid_spawn_points(self):
        pts=[]
        for y in range(5, MAP_SIZE-5):
            for x in range(5, MAP_SIZE-5):
                t = self.tiles[y][x]
                if t.terrain in (TERRAIN_PLAIN, TERRAIN_FOREST):
                    pts.append((x,y))
        return pts

    def land_tiles_in_radius(self, cx, cy, r):
        rows   = self.tiles
        result = []
        for dx, dy in _get_radius_offsets(r):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE:
                t = rows[ny][nx]
                if t.is_land():
                    result.append(t)
        return result

    def tiles_in_radius(self, cx, cy, r):
        rows   = self.tiles
        result = []
        for dx, dy in _get_radius_offsets(r):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE:
                result.append(rows[ny][nx])
        return result
