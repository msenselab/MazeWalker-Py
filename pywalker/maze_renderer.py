"""
Ursina-based 3D maze renderer.

Loads a MazeData object (from maz_parser) and renders it as a walkable
first-person 3D environment using Ursina (Panda3D wrapper).

Supports textured walls/floors and OBJ model loading.
"""

from ursina import (
    Ursina, Entity, Vec3 as UVec3, Mesh,
    color, window, application, load_model, load_texture,
    held_keys, Text, invoke, destroy,
)
from ursina.prefabs.first_person_controller import FirstPersonController
import math
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pywalker.maz_parser import parse_maz, resolve_assets, MazeData


def build_skybox(skybox_texture_path: Path):
    """
    Build a sky dome from a MazeSuite cross-layout cubemap texture.

    Extracts the middle panoramic strip (row 1: right/back/left/front)
    and wraps it onto Ursina's built-in sky_dome model.
    """
    import tempfile
    from PIL import Image
    from ursina import Sky

    if not skybox_texture_path.exists() or skybox_texture_path.stat().st_size == 0:
        print(f"  [skip] Skybox texture missing: {skybox_texture_path.name}")
        # Fallback: solid color sky
        Sky(color=color.rgb(135, 206, 235))
        return

    img = Image.open(skybox_texture_path)
    w, h = img.size
    fw, fh = w // 4, h // 3

    # Extract the panoramic strip (middle row: right, back, left, front)
    # and stitch into a panorama in the order the dome expects
    panorama = Image.new('RGB', (4 * fw, fh))
    # Sky dome wraps left-to-right: front, right, back, left
    # Cross layout row 1 is:  col0=right, col1=back, col2=left, col3=front
    order = [3, 0, 1, 2]  # front, right, back, left
    for i, col in enumerate(order):
        face = img.crop((col * fw, 1 * fh, (col + 1) * fw, 2 * fh))
        panorama.paste(face, (i * fw, 0))

    tmp_dir = Path(tempfile.mkdtemp(prefix='maze_skybox_'))
    pano_path = tmp_dir / 'sky_panorama.png'
    panorama.save(pano_path)

    tex = load_texture(name='sky_panorama', path=str(tmp_dir))
    if tex:
        Sky(texture=tex)
        print(f"  Skybox loaded from {skybox_texture_path.name}")
    else:
        print(f"  [warn] Failed to load skybox panorama, using solid color")
        Sky(color=color.rgb(135, 206, 235))


def load_textures(maze_data: MazeData) -> dict:
    """Pre-load all textures from resolved paths. Returns {texture_id: Texture}."""
    textures = {}
    for img_id, path in maze_data.image_paths.items():
        if not path.exists() or path.stat().st_size == 0:
            print(f"  [skip] Empty or missing texture: {path.name}")
            continue
        try:
            tex = load_texture(name=path.stem, path=path.parent)
            if tex:
                textures[img_id] = tex
                print(f"  [ok] Loaded texture: {path.name}")
            else:
                print(f"  [warn] load_texture returned None: {path.name}")
        except Exception as e:
            print(f"  [warn] Failed to load texture {path.name}: {e}")
    return textures


def _obj_bounds(obj_path: Path) -> tuple:
    """Read an OBJ file and return (max_extent, min_y).

    max_extent: largest bounding box dimension (for normalization).
    min_y: lowest Y coordinate (for placing model on the ground).
    """
    xs, ys, zs = [], [], []
    with open(obj_path) as f:
        for line in f:
            if line.startswith('v '):
                parts = line.split()
                xs.append(float(parts[1]))
                ys.append(float(parts[2]))
                zs.append(float(parts[3]))
    if not xs:
        return 1.0, 0.0
    extent = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    return extent, min(ys)


def load_obj_model(model_path: Path):
    """
    Load an OBJ model and return (mesh, normalize_factor, min_y).

    normalize_factor scales the model so its max dimension = 1 unit.
    min_y is the model's lowest Y in native coords (for ground placement).
    """
    try:
        model = load_model(
            name=model_path.stem,
            path=Path(model_path.parent),
        )
        if model:
            extent, min_y = _obj_bounds(model_path)
            normalize = 1.0 / extent if extent > 0 else 1.0
            print(f"  [ok] Loaded model: {model_path.name} (extent={extent:.1f}, min_y={min_y:.1f}, norm={normalize:.4f})")
            return model, normalize, min_y
        else:
            print(f"  [warn] load_model returned None: {model_path.name}")
            return None, 1.0, 0.0
    except Exception as e:
        print(f"  [warn] Failed to load model {model_path.name}: {e}")
        return None, 1.0, 0.0


def wall_from_vertices(v, texture, wall_color):
    """
    Create a wall Entity from 4 vertices using Ursina's 'quad' model.

    MazeSuite wall vertex order:
      MzPoint1 (top-right), MzPoint2 (bottom-right),
      MzPoint3 (bottom-left), MzPoint4 (top-left)
    """
    cx = (v[0].x + v[1].x + v[2].x + v[3].x) / 4
    cy = (v[0].y + v[1].y + v[2].y + v[3].y) / 4
    cz = (v[0].z + v[1].z + v[2].z + v[3].z) / 4

    # Width = horizontal distance along wall bottom edge
    dx = v[1].x - v[2].x
    dz = v[1].z - v[2].z
    width = math.sqrt(dx * dx + dz * dz)

    # Height = vertical extent
    height = abs(v[0].y - v[1].y)
    if height < 0.01:
        height = 2.0

    # Rotation around Y axis
    angle_y = -math.degrees(math.atan2(dx, dz))

    if texture is not None:
        col = color.white  # let texture show through
    else:
        col = color.rgb(
            int(wall_color.r * 180),
            int(wall_color.g * 200),
            int(wall_color.b * 160),
        )

    # Front face (with collider for collision detection)
    Entity(
        model='quad',
        texture=texture,
        color=col,
        position=(cx, cy, cz),
        scale=(width, height),
        rotation_y=angle_y,
        unlit=True,
        collider='box',
    )
    # Back face (visual only, no collider needed)
    Entity(
        model='quad',
        texture=texture,
        color=col,
        position=(cx, cy, cz),
        scale=(width, height),
        rotation_y=angle_y + 180,
        unlit=True,
    )


def build_curved_wall(cw, texture, wall_color):
    """Create an Entity for a CurvedWall using its geometry vertices and triangle indices."""
    if not cw.geometry_verts or not cw.indices:
        return

    verts = [UVec3(v.x, v.y, v.z) for v in cw.geometry_verts]

    if texture is not None:
        col = color.white
    else:
        col = color.rgb(
            int(wall_color.r * 180),
            int(wall_color.g * 200),
            int(wall_color.b * 160),
        )

    mesh = Mesh(vertices=verts, triangles=cw.indices, mode='triangle')
    e = Entity(model=mesh, texture=texture, color=col, unlit=True)
    e.collider = 'mesh'  # collision from triangle mesh

    # Back faces (reverse winding for double-sided, visual only)
    back_tris = []
    for i in range(0, len(cw.indices), 3):
        if i + 2 < len(cw.indices):
            back_tris.extend([cw.indices[i], cw.indices[i+2], cw.indices[i+1]])
    mesh_back = Mesh(vertices=verts, triangles=back_tris, mode='triangle')
    Entity(model=mesh_back, texture=texture, color=col, unlit=True)


def build_maze_scene(maze_data: MazeData):
    """Build all Ursina entities from parsed maze data. Returns the player controller."""

    # Pre-load textures
    textures = load_textures(maze_data)
    print(f"Loaded {len(textures)}/{len(maze_data.image_paths)} textures")

    # --- Walls ---
    for wall in maze_data.walls:
        if wall.visible and len(wall.vertices) >= 4:
            tex = textures.get(wall.texture_id)
            wall_from_vertices(wall.vertices, tex, wall.color)

    # --- Curved walls (boundary arcs) ---
    for cw in maze_data.curved_walls:
        if cw.visible:
            tex = textures.get(cw.texture_id)
            build_curved_wall(cw, tex, cw.color)
    print(f"Built {len(maze_data.walls)} walls + {len(maze_data.curved_walls)} curved walls")

    # --- Floor ---
    for floor in maze_data.floors:
        if not floor.visible or len(floor.vertices) < 4:
            continue
        v = floor.vertices
        xs = [p.x for p in v]
        zs = [p.z for p in v]
        cx = (min(xs) + max(xs)) / 2
        cz = (min(zs) + max(zs)) / 2
        sx = max(xs) - min(xs)
        sz = max(zs) - min(zs)
        floor_tex = textures.get(floor.texture_id)
        Entity(
            model='quad',
            texture=floor_tex,
            color=color.white if floor_tex else color.rgb(100, 160, 80),
            position=(cx, v[0].y, cz),
            scale=(sx, sz),
            rotation_x=90,  # lay flat
            texture_scale=(sx, sz) if floor_tex else (1, 1),
            unlit=True,
            collider='box',
        )

    # --- Pre-load unique OBJ models → (mesh, normalize_factor, min_y) ---
    loaded_models = {}  # model_id -> (mesh, normalize_factor, min_y)
    all_objects = list(maze_data.static_models) + list(maze_data.dynamic_objects)
    for obj in all_objects:
        mid = obj.model_id
        if mid not in loaded_models:
            model_path = maze_data.model_paths.get(mid)
            if model_path is not None:
                loaded_models[mid] = load_obj_model(model_path)
            else:
                loaded_models[mid] = (None, 1.0, 0.0)

    # --- Static models ---
    for sobj in maze_data.static_models:
        mdl, norm, min_y = loaded_models.get(sobj.model_id, (None, 1.0, 0.0))
        if mdl is not None:
            s = sobj.scale * norm
            # Offset Y so model bottom sits at the specified position
            y_offset = -min_y * s
            Entity(
                model=mdl,
                color=color.white,
                scale=s,
                position=(sobj.position.x, sobj.position.y + y_offset, sobj.position.z),
                rotation=(sobj.rotation.x, sobj.rotation.y, sobj.rotation.z),
                unlit=True,
            )

    # --- Dynamic objects (collectibles) ---
    collectibles = []  # list of (entity, dobj) for proximity checking
    for dobj in maze_data.dynamic_objects:
        # Reload model per instance so destroying one doesn't affect others
        model_path = maze_data.model_paths.get(dobj.model_id)
        if model_path is not None:
            mdl = load_model(name=model_path.stem, path=Path(model_path.parent))
        else:
            mdl = None
        _, norm, min_y = loaded_models.get(dobj.model_id, (None, 1.0, 0.0))
        if mdl is not None:
            s = dobj.scale * norm
            y_offset = -min_y * s
            e = Entity(
                model=mdl,
                color=color.white,
                scale=s,
                position=(dobj.position.x, dobj.position.y + y_offset, dobj.position.z),
                rotation=(dobj.rotation.x, dobj.rotation.y, dobj.rotation.z),
                unlit=True,
            )
        else:
            e = Entity(
                model='sphere',
                color=color.yellow,
                scale=dobj.scale * 0.5,
                position=(dobj.position.x, dobj.position.y + 0.3, dobj.position.z),
                unlit=True,
            )
        if dobj.points_granted > 0:
            collectibles.append((e, dobj))

    # --- Start position ---
    # MazeSuite: floor at Y=-1, walls from Y=-1 to Y=1, player walks at Y≈0
    # Ursina FirstPersonController: camera at player.y + height
    # So: player.y = -1 (feet on floor), height = 1.0 → camera at Y=0 (eye level)
    start_pos = (14, -1, 14)
    start_angle = 0
    if maze_data.start_positions:
        sp = maze_data.start_positions[0]
        start_pos = (sp.position.x, -1, sp.position.z)
        start_angle = sp.angle

    # If angle is 0 (default), auto-face toward maze center
    if start_angle == 0 and maze_data.floors:
        fv = maze_data.floors[0].vertices
        cx = sum(v.x for v in fv) / len(fv)
        cz = sum(v.z for v in fv) / len(fv)
        dx = cx - start_pos[0]
        dz = cz - start_pos[2]
        start_angle = math.degrees(math.atan2(dx, dz))

    player = FirstPersonController(
        position=start_pos,
        speed=maze_data.settings.move_speed,
        mouse_sensitivity=UVec3(40, 40, 0),
    )
    player.height = 1.0           # camera at Y = -1 + 1 = 0 (mid-wall)
    player.camera_pivot.y = 1.0   # update the already-created pivot
    player.rotation_y = start_angle
    player.gravity = 0            # flat maze, no falling
    player.cursor.visible = False

    # --- Skybox ---
    skybox_path = maze_data.image_paths.get(maze_data.settings.skybox_id)
    if skybox_path is not None:
        build_skybox(skybox_path)
    else:
        print("  [info] No skybox texture, using background color")

    return player, collectibles


def run_maze(maz_filepath: str):
    """Load a .maz file and run the interactive 3D maze."""
    maze_data = parse_maz(maz_filepath)
    resolve_assets(maze_data, maz_filepath)

    print(f"Loaded maze: {len(maze_data.walls)} walls, {len(maze_data.floors)} floors")
    if maze_data.start_positions:
        sp = maze_data.start_positions[0]
        print(f"Start: ({sp.position.x:.1f}, {sp.position.z:.1f}) angle={sp.angle}")

    app = Ursina(title='MazeWalker-Py', borderless=False, size=(1024, 768))
    window.color = color.rgb(135, 206, 235)  # sky blue
    window.fps_counter.enabled = True

    player, collectibles = build_maze_scene(maze_data)

    # --- Game state ---
    exit_threshold = maze_data.settings.exit_threshold
    state = {
        'points': 0,
        'completed': False,
    }

    # --- HUD ---
    if maze_data.settings.start_message:
        msg = Text(
            text=maze_data.settings.start_message,
            origin=(0, 0),
            scale=1.5,
            background=True,
        )
        invoke(destroy, msg, delay=3)

    score_text = Text(
        text=f'Stars: 0 / {exit_threshold}',
        position=(-0.85, 0.45),
        scale=1.5,
        color=color.yellow,
    )
    pos_text = Text(text='', position=(-0.85, 0.40), scale=1)

    class GameUpdater(Entity):
        def update(self):
            # --- Collectible proximity check ---
            for item in collectibles[:]:  # iterate copy so we can remove
                entity, dobj = item
                dx = player.x - entity.x
                dz = player.z - entity.z
                dist = math.sqrt(dx * dx + dz * dz)
                if dist < dobj.trigger_radius:
                    # Collect!
                    state['points'] += dobj.points_granted
                    score_text.text = f'Stars: {state["points"]} / {exit_threshold}'
                    destroy(entity)
                    collectibles.remove(item)
                    print(f'  Collected! Points: {state["points"]}/{exit_threshold}')

                    # Check completion
                    if state['points'] >= exit_threshold and not state['completed']:
                        state['completed'] = True
                        done_msg = Text(
                            text='All Stars Collected!\nMission Complete!',
                            origin=(0, 0),
                            scale=2.5,
                            color=color.yellow,
                            background=True,
                        )
                        score_text.text = f'Stars: {state["points"]} / {exit_threshold}  COMPLETE!'
                        print('  === Mission Complete! ===')

            # --- HUD update ---
            pos_text.text = (
                f'x={player.x:.1f}  z={player.z:.1f}  '
                f'angle={player.rotation_y:.0f}'
            )
            if held_keys['escape']:
                application.quit()

    GameUpdater()
    app.run()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python maze_renderer.py <file.maz>")
        sys.exit(1)
    run_maze(sys.argv[1])
