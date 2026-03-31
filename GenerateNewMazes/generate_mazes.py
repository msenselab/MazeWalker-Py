#!/usr/bin/env python3
"""
Generate a pool of difficulty-matched maze files (.maz) for contextual cueing.

All mazes use 6×6 grid, fixed start at (0,0) facing north, 3 well-separated
stars, and matched total BFS path length. The experiment script assigns
old/new roles at runtime.

Output:  mazes/Maze001.maz … Maze300.maz

Usage:
  python generate_mazes.py
  python generate_mazes.py --count 300 --seed 42 --output-dir mazes
  python generate_mazes.py --tolerance 4 --min-star-sep 3
"""

import random
import math
import argparse
import statistics
from collections import deque
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.dom import minidom


# ── Maze geometry ─────────────────────────────────────────────────────────────
GRID_SIZE = 6
CELL_SIZE = 3.5
MARGIN    = 1.5
WALL_TOP  = 1.0
WALL_BOT  = -1.0

START_ROW   = 0
START_COL   = 0
START_ANGLE = 0

# Assets
TEX_WALL   = 102
TEX_FLOOR  = 101
SKYBOX_ID  = 118
MODEL_STAR = 100
AUDIO_STAR = 100

NUM_STARS           = 3
STAR_RADIUS         = 2.0
STAR_SCALE          = 0.5
MIN_STAR_SEPARATION = 3   # Manhattan distance between any two stars
MIN_STAR_DISTANCE   = 4   # BFS from start to any star

MAX_ATTEMPTS = 500


# ── Maze generation (DFS backtracking) ───────────────────────────────────────
def generate_maze(n, rng):
    h_walls = [[True] * n for _ in range(n - 1)]
    v_walls = [[True] * (n - 1) for _ in range(n)]
    visited = [[False] * n for _ in range(n)]
    stack = [(0, 0)]
    visited[0][0] = True

    while stack:
        r, c = stack[-1]
        candidates = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < n and 0 <= nc < n and not visited[nr][nc]:
                candidates.append((nr, nc, dr, dc))
        if candidates:
            nr, nc, dr, dc = rng.choice(candidates)
            if   dr ==  1: h_walls[r][c]  = False
            elif dr == -1: h_walls[nr][c] = False
            elif dc ==  1: v_walls[r][c]  = False
            else:          v_walls[r][nc] = False
            visited[nr][nc] = True
            stack.append((nr, nc))
        else:
            stack.pop()
    return h_walls, v_walls


# ── BFS ───────────────────────────────────────────────────────────────────────
def bfs_distances(n, h_walls, v_walls, sr, sc):
    dist = [[-1] * n for _ in range(n)]
    dist[sr][sc] = 0
    q = deque([(sr, sc)])
    while q:
        r, c = q.popleft()
        if r < n-1 and not h_walls[r][c]     and dist[r+1][c] == -1:
            dist[r+1][c] = dist[r][c] + 1; q.append((r+1, c))
        if r > 0   and not h_walls[r-1][c]   and dist[r-1][c] == -1:
            dist[r-1][c] = dist[r][c] + 1; q.append((r-1, c))
        if c < n-1 and not v_walls[r][c]     and dist[r][c+1] == -1:
            dist[r][c+1] = dist[r][c] + 1; q.append((r, c+1))
        if c > 0   and not v_walls[r][c-1]   and dist[r][c-1] == -1:
            dist[r][c-1] = dist[r][c] + 1; q.append((r, c-1))
    return dist


def pick_stars(n, h_walls, v_walls, rng, sr, sc):
    dist = bfs_distances(n, h_walls, v_walls, sr, sc)
    candidates = [
        (r, c) for r in range(n) for c in range(n)
        if dist[r][c] >= MIN_STAR_DISTANCE and (r, c) != (sr, sc)
    ]
    if len(candidates) < NUM_STARS:
        return None
    rng.shuffle(candidates)
    candidates.sort(key=lambda rc: -dist[rc[0]][rc[1]])
    chosen = []
    for r, c in candidates:
        if len(chosen) >= NUM_STARS:
            break
        if all(abs(r-cr) + abs(c-cc) >= MIN_STAR_SEPARATION for cr, cc in chosen):
            chosen.append((r, c))
    return chosen if len(chosen) == NUM_STARS else None


def try_one_maze(n, seed, sr, sc):
    rng = random.Random(seed)
    h, v = generate_maze(n, rng)
    stars = pick_stars(n, h, v, rng, sr, sc)
    if stars is None:
        return None
    dist = bfs_distances(n, h, v, sr, sc)
    total = sum(dist[r][c] for r, c in stars)
    star_dists = sorted(dist[r][c] for r, c in stars)
    return h, v, stars, total, star_dists


# ── XML ───────────────────────────────────────────────────────────────────────
def _f(v):
    return f"{float(v):.4f}"

def cell_center(row, col):
    return MARGIN + col * CELL_SIZE + CELL_SIZE / 2, MARGIN + row * CELL_SIZE + CELL_SIZE / 2

def _wall_elem(wid, x1, z1, x2, z2):
    length = math.hypot(x2 - x1, z2 - z1)
    w = ET.Element('Wall', group='', label='', id=str(wid),
                   itemLocked='False', itemVisible='True')
    ET.SubElement(w, 'MzPoint1', x=_f(x2), y=_f(WALL_TOP), z=_f(z2),
                  texX=_f(length), texY='2')
    ET.SubElement(w, 'MzPoint2', x=_f(x2), y=_f(WALL_BOT), z=_f(z2),
                  texX=_f(length), texY='0')
    ET.SubElement(w, 'MzPoint3', x=_f(x1), y=_f(WALL_BOT), z=_f(z1),
                  texX='0', texY='0')
    ET.SubElement(w, 'MzPoint4', x=_f(x1), y=_f(WALL_TOP), z=_f(z1),
                  texX='0', texY='2')
    ET.SubElement(w, 'Texture', id=str(TEX_WALL), aspectRatio='1', flip='False',
                  mode='Tile', rotation='3', tileSize='1')
    ET.SubElement(w, 'Color', r='1', g='1', b='1')
    ET.SubElement(w, 'Appearance', visible='True')
    return w

def _floor_elem(x_min, z_min, x_max, z_max):
    sx, sz = x_max - x_min, z_max - z_min
    fl = ET.Element('Floor', group='', label='', id='1',
                    itemLocked='False', itemVisible='True')
    ET.SubElement(fl, 'MzPoint1', x=_f(x_min), y=_f(WALL_BOT), z=_f(z_min),
                  texX='0', texY='0', texX_Ceiling='0', texY_Ceiling='0')
    ET.SubElement(fl, 'MzPoint2', x=_f(x_max), y=_f(WALL_BOT), z=_f(z_min),
                  texX='0', texY=_f(sz), texX_Ceiling='0', texY_Ceiling='1')
    ET.SubElement(fl, 'MzPoint3', x=_f(x_max), y=_f(WALL_BOT), z=_f(z_max),
                  texX=_f(sx), texY=_f(sz), texX_Ceiling='1', texY_Ceiling='1')
    ET.SubElement(fl, 'MzPoint4', x=_f(x_min), y=_f(WALL_BOT), z=_f(z_max),
                  texX=_f(sx), texY='0', texX_Ceiling='1', texY_Ceiling='0')
    ET.SubElement(fl, 'FloorColor', r='1', g='1', b='1')
    ET.SubElement(fl, 'FloorTexture', id=str(TEX_FLOOR), aspectRatio='1',
                  mode='Tile', rotation='1', tileSize='1')
    ET.SubElement(fl, 'CeilingColor', r='1', g='1', b='1')
    ET.SubElement(fl, 'Appearance', hasCeiling='False', ceilingHeight='2', visible='True')
    return fl

def _star_elem(sid, x, z):
    d = ET.Element('DynamicObject', group='', label='', id=str(sid),
                   itemLocked='False', itemVisible='True')
    ET.SubElement(d, 'MzPoint', x=_f(x), y='0', z=_f(z))
    ET.SubElement(d, 'Model', id=str(MODEL_STAR), scale=str(STAR_SCALE),
                  rotX='90', rotY='0', rotZ='0')
    ET.SubElement(d, 'Physics', collision='True', kinematic='False', mass='1')
    ph1 = ET.SubElement(d, 'Phase1Highlight', criteria='Proximity', radius='8',
                        highlightStyle='Rotate', triggerTime='0',
                        triggerTimeOperator='GreaterThan', pointThreshold='0',
                        pointThresholdOperator='GreaterThanEqual')
    ET.SubElement(ph1, 'Audio')
    ph2 = ET.SubElement(d, 'Phase2Event', criteria='Proximity',
                        radius=str(STAR_RADIUS), triggerAction='Destroy Model',
                        triggerTime='0', triggerTimeOperator='GreaterThan',
                        actionTime='3', pointThreshold='0',
                        pointThresholdOperator='GreaterThanEqual',
                        pointsGranted='1', pointsGrantedMode='Add')
    ET.SubElement(ph2, 'Audio', id=str(AUDIO_STAR), loop='False', audioBehavior='0')
    ET.SubElement(ph2, 'EndMzPoint', x='0', y='0', z='0')
    ET.SubElement(ph2, 'EndModel', rotX='0', rotY='0', rotZ='0',
                  switchModelID='', endScale='1')
    return d


def build_maz_xml(n, h_walls, v_walls, star_cells, label=''):
    root = ET.Element('MazeFile', version='2.0', url='http://www.mazesuite.com')
    info = ET.SubElement(root, 'Info')
    ET.SubElement(info, 'Author', name='MazeGenerator', comments=label)

    g = ET.SubElement(root, 'Global')
    ET.SubElement(g, 'Avatar', scale='1', rotX='0', rotY='0', rotZ='0')
    ET.SubElement(g, 'General')
    ET.SubElement(g, 'Speed', moveSpeed='3', turnSpeed='45')
    ET.SubElement(g, 'AmbientLight', r='1', g='1', b='1', intensity='0.6')
    ET.SubElement(g, 'StartMessage', enabled='True',
                  message='Collect 3 Stars to complete the Maze!')
    ET.SubElement(g, 'DefaultStartPosition', id='1')
    ET.SubElement(g, 'Timeout', enabled='False', message='', timeoutValue='0')
    ET.SubElement(g, 'PointOptions', exitThreshold=str(NUM_STARS),
                  exitThresholdOperator='GreaterThanEqual',
                  messageText='All Stars Collected!')
    ET.SubElement(g, 'Skybox', id=str(SKYBOX_ID))
    ET.SubElement(g, 'PerspectiveSettings', avatarHeight='0', cameraHeight='15',
                  cameraMode='First-Person', fieldOfView='45', fixCameraX='False',
                  fixedCameraX='20', fixCameraZ='False', fixedCameraZ='20',
                  topDownOrientation='North', xRayRendering='False')

    imglib = ET.SubElement(root, 'ImageLibrary')
    ET.SubElement(imglib, 'Image', id='101', file='ground_grass.jpg')
    ET.SubElement(imglib, 'Image', id='102', file='wall_hedge.jpg')
    ET.SubElement(imglib, 'Image', id='118', file='skybox2.jpg')
    modlib = ET.SubElement(root, 'ModelLibrary')
    ET.SubElement(modlib, 'Model', id='100', file='star.obj')
    ET.SubElement(modlib, 'Model', id='102', file='chair.obj')
    audlib = ET.SubElement(root, 'AudioLibrary')
    ET.SubElement(audlib, 'Sound', id='100', file='success.wav')

    items = ET.SubElement(root, 'MazeItems')
    walls_el = ET.SubElement(items, 'Walls')
    wid = 1
    gl = n * CELL_SIZE

    # Outer boundary
    walls_el.append(_wall_elem(wid, MARGIN, MARGIN, MARGIN+gl, MARGIN));          wid+=1
    walls_el.append(_wall_elem(wid, MARGIN, MARGIN+gl, MARGIN+gl, MARGIN+gl));    wid+=1
    walls_el.append(_wall_elem(wid, MARGIN, MARGIN, MARGIN, MARGIN+gl));           wid+=1
    walls_el.append(_wall_elem(wid, MARGIN+gl, MARGIN, MARGIN+gl, MARGIN+gl));    wid+=1

    for r in range(n - 1):
        z = MARGIN + (r + 1) * CELL_SIZE
        for c in range(n):
            if h_walls[r][c]:
                x1 = MARGIN + c * CELL_SIZE
                walls_el.append(_wall_elem(wid, x1, z, x1 + CELL_SIZE, z)); wid += 1

    for r in range(n):
        for c in range(n - 1):
            if v_walls[r][c]:
                x = MARGIN + (c + 1) * CELL_SIZE
                z1 = MARGIN + r * CELL_SIZE
                walls_el.append(_wall_elem(wid, x, z1, x, z1 + CELL_SIZE)); wid += 1

    floors_el = ET.SubElement(items, 'Floors')
    floors_el.append(_floor_elem(MARGIN, MARGIN, MARGIN+gl, MARGIN+gl))
    ET.SubElement(items, 'StaticModels')

    dyn_el = ET.SubElement(items, 'DynamicObjects')
    for i, (sr, sc) in enumerate(star_cells):
        sx, sz = cell_center(sr, sc)
        dyn_el.append(_star_elem(i + 1, sx, sz))

    sx, sz = cell_center(START_ROW, START_COL)
    starts_el = ET.SubElement(items, 'StartPositions')
    sp = ET.SubElement(starts_el, 'StartPosition', group='', label='', id='1',
                       itemLocked='False', itemVisible='True')
    ET.SubElement(sp, 'MzPoint', x=_f(sx), y='0', z=_f(sz))
    ET.SubElement(sp, 'ViewAngle', angle=str(START_ANGLE), vertAngle='0',
                  randomAngle='False', randomVertAngle='False')
    ET.SubElement(items, 'EndRegions')

    cx, cz = MARGIN + gl/2, MARGIN + gl/2
    lights_el = ET.SubElement(items, 'Lights')
    lt = ET.SubElement(lights_el, 'Light', group='', label='', id='1',
                       itemLocked='False', itemVisible='True')
    ET.SubElement(lt, 'MzPoint', x=_f(cx), y='0.9', z=_f(cz))
    ET.SubElement(lt, 'Color', r='1', g='1', b='1')
    ET.SubElement(lt, 'Appearance', attenuation='0.08', intensity='2', type='Ambulatory')
    ET.SubElement(items, 'ActiveRegions')
    return root


def to_xml(root):
    raw = ET.tostring(root, encoding='unicode')
    dom = minidom.parseString(raw)
    pretty = dom.toprettyxml(indent='  ')
    lines = [ln for ln in pretty.splitlines() if ln.strip()]
    lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
    return '\n'.join(lines) + '\n'


# ── Main generation ───────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        description='Generate a pool of difficulty-matched mazes',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument('--count',      type=int, default=300,  help='Total mazes')
    ap.add_argument('--seed',       type=int, default=42,   help='Master RNG seed')
    ap.add_argument('--output-dir', default='mazes',        help='Output folder')
    ap.add_argument('--tolerance',  type=int, default=3,    help='±cells from target dist')
    ap.add_argument('--calibration', type=int, default=200, help='Calibration sample size')
    args = ap.parse_args()

    n = GRID_SIZE
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    master = random.Random(args.seed)

    # ── Phase 1: Calibration — find target total_dist ────────────────────
    print(f'Grid: {n}×{n}  |  Start: ({START_ROW},{START_COL})  angle={START_ANGLE}°')
    print(f'Stars: {NUM_STARS}, BFS ≥ {MIN_STAR_DISTANCE}, separation ≥ {MIN_STAR_SEPARATION}')
    print(f'\nCalibrating target difficulty from {args.calibration} random mazes…')

    cal_dists = []
    cal_rng = random.Random(args.seed + 999)  # separate stream
    while len(cal_dists) < args.calibration:
        seed = cal_rng.randint(0, 2**31)
        result = try_one_maze(n, seed, START_ROW, START_COL)
        if result is not None:
            cal_dists.append(result[3])

    target = round(statistics.median(cal_dists))
    cal_mean = statistics.mean(cal_dists)
    cal_sd = statistics.stdev(cal_dists)
    low = target - args.tolerance
    high = target + args.tolerance

    print(f'  Calibration: median={target}  mean={cal_mean:.1f}  SD={cal_sd:.1f}  '
          f'range=[{min(cal_dists)}, {max(cal_dists)}]')
    print(f'  Target window: total_dist ∈ [{low}, {high}]')

    # ── Phase 2: Generate matched pool ───────────────────────────────────
    print(f'\nGenerating {args.count} mazes → {out}/')

    dists = []
    all_star_dists = []
    total_attempts = 0

    for i in range(1, args.count + 1):
        attempts = 0
        while True:
            seed = master.randint(0, 2**31)
            result = try_one_maze(n, seed, START_ROW, START_COL)
            attempts += 1
            total_attempts += 1
            if result is not None:
                h, v, stars, total, sdists = result
                if low <= total <= high:
                    break
            if attempts > MAX_ATTEMPTS:
                raise RuntimeError(
                    f'Maze {i}: {MAX_ATTEMPTS} attempts exceeded. '
                    f'Increase --tolerance (currently ±{args.tolerance}).')

        dists.append(total)
        all_star_dists.extend(sdists)

        path = out / f'Maze{i:03d}.maz'
        label = f'n={n} seed={seed} total_dist={total} stars={sdists}'
        root = build_maz_xml(n, h, v, stars, label)
        path.write_text(to_xml(root), encoding='utf-8')

        if i <= 5 or i % 50 == 0 or i == args.count:
            print(f'  Maze{i:03d}  dist={total}  stars={sdists}  '
                  f'cells={stars}  ({attempts} att)')

    # ── Summary ──────────────────────────────────────────────────────────
    m = statistics.mean(dists)
    sd = statistics.stdev(dists)
    sm = statistics.mean(all_star_dists)
    ssd = statistics.stdev(all_star_dists)
    rej = (total_attempts - args.count) / total_attempts * 100

    print(f'\n══ Pool summary ══')
    print(f'  Mazes:          {args.count}')
    print(f'  Total dist:     mean={m:.1f}  SD={sd:.1f}  range=[{min(dists)}, {max(dists)}]')
    print(f'  Star distances: mean={sm:.1f}  SD={ssd:.1f}  '
          f'range=[{min(all_star_dists)}, {max(all_star_dists)}]')
    print(f'  Rejection rate: {rej:.1f}%')
    print(f'  Files: {out}/Maze001.maz … Maze{args.count:03d}.maz')

    n_old = 8
    n_new_per_block = n_old
    n_remaining = args.count - n_old
    n_blocks = n_remaining // n_new_per_block
    print(f'\n  Experiment design (example with {n_old} old-context):')
    print(f'    Old context: randomly pick {n_old} mazes, repeat across all blocks')
    print(f'    New context: draw from remaining {n_remaining} (one per trial, never repeated)')
    print(f'    Per block:   {n_old + n_new_per_block} trials ({n_old} old + {n_new_per_block} new)')
    print(f'    Max blocks:  {n_blocks}')
    print(f'    Total trials: {n_blocks * (n_old + n_new_per_block)}')


if __name__ == '__main__':
    main()