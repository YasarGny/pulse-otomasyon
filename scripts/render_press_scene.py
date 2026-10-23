"""Rebuild the 3D print-room assets using Blender 4.3+ and system ffmpeg.

Run from the repository root:
  blender -b -t 5 --python scripts/render_press_scene.py
PNG/mask/projection/native scene are kept in ignored test-results/press-render.
The small public assets and camera projection in printing.js are updated together.
"""

import bpy, math, json, os, re, shutil, subprocess
from pathlib import Path
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

root = Path(__file__).resolve().parents[1]
out = str(root / "test-results/press-render")
Path(out).mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 128
scene.cycles.use_denoising = False
scene.render.resolution_x = 640
scene.render.resolution_y = 640
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.film_transparent = True
scene.world.color = (0.22, 0.22, 0.22)
scene.view_settings.view_transform = "AgX"


def mat(name, color, metal=0, rough=0.35):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Metallic"].default_value = metal
    p.inputs["Roughness"].default_value = rough
    return m


ivory = mat("ivory enamel", (0.78, 0.75, 0.68), 0.12, 0.29)
cream = mat("roller porcelain", (0.88, 0.86, 0.81), 0.06, 0.24)
pink = mat("pink rubber", (0.85, 0.055, 0.25), 0.05, 0.3)
steel = mat("brushed steel", (0.14, 0.15, 0.16), 0.83, 0.27)
silver = mat("steel fasteners", (0.52, 0.53, 0.52), 0.85, 0.22)
black = mat("dark base", (0.055, 0.06, 0.065), 0.3, 0.35)
paper = mat("newspaper", (0.91, 0.895, 0.85), 0, 0.68)
objects = []


def cube(name, loc, scale, m, bevel=0.035):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(m)
    if bevel:
        mod = o.modifiers.new("soft edges", "BEVEL")
        mod.width = bevel
        mod.segments = 3
        o.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    objects.append(o)
    return o


def cyl(name, loc, radius, length, m, axis="X"):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64, radius=radius, depth=length, location=loc
    )
    o = bpy.context.object
    o.name = name
    if axis == "X":
        o.rotation_euler[1] = math.pi / 2
    elif axis == "Y":
        o.rotation_euler[0] = math.pi / 2
    o.data.materials.append(m)
    mod = o.modifiers.new("edge bevel", "BEVEL")
    mod.width = 0.016
    mod.segments = 3
    for f in o.data.polygons:
        f.use_smooth = True
    o.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    objects.append(o)
    return o


# Two rigid side frames, broad feet and a rear crosshead, matching the reference silhouette.
for x in [-1.16, 1.16]:
    cube("rubber foot", (x, 0.12, 0.075), (0.46, 0.90, 0.15), black, 0.025)
    cube("enamel foot", (x, 0.12, 0.21), (0.43, 0.85, 0.26), ivory)
    cube("rear upright", (x, 0.38, 1.03), (0.25, 0.23, 1.76), ivory)
    cube("front cheek", (x, -0.13, 0.80), (0.29, 0.28, 1.28), ivory)
    cube("bearing shoulder", (x, -0.06, 1.30), (0.30, 0.43, 0.31), ivory, 0.07)
    for z in [0.43, 1.27]:
        cyl(
            "bearing screw",
            (x - 0.157 if x < 0 else x + 0.157, -0.17, z),
            0.052,
            0.024,
            silver,
        )
    cyl(
        "pink adjustment knob",
        (x - 0.17 if x < 0 else x + 0.17, -0.17, 0.98),
        0.071,
        0.028,
        pink,
    )
    cube("front steel guide", (x * 0.86, -0.23, 0.79), (0.08, 0.11, 0.86), steel, 0.016)
    cube("cap bolt", (x, 0.36, 1.955), (0.08, 0.08, 0.04), silver, 0.012)
cube("rear crosshead", (0, 0.39, 1.90), (2.57, 0.26, 0.20), ivory, 0.035)
cube("lower brace", (0, 0.16, 0.36), (2.4, 0.18, 0.16), steel, 0.02)
# Offset press: visible pink ink roll contacts the front ivory blanket roll.
# The sheet passes between that ivory roll and the dark impression roll below.
cyl("impression shaft", (0, -0.16, 0.55), 0.065, 2.65, steel)
cyl("impression roller", (0, -0.16, 0.55), 0.270, 2.02, black)
cyl("blanket shaft", (0, -0.16, 1.10), 0.065, 2.65, steel)
for x in [-1.045, 1.045]:
    cyl("blanket end cap", (x, -0.16, 1.10), 0.284, 0.08, steel)
cyl("ivory blanket roller", (0, -0.16, 1.10), 0.270, 2.02, cream)
cyl("ink shaft", (0, 0.16, 1.55), 0.065, 2.65, steel)
for x in [-1.045, 1.045]:
    cyl("ink end cap", (x, 0.16, 1.55), 0.291, 0.08, steel)
cyl("pink ink roller", (0, 0.16, 1.55), 0.280, 2.02, pink)
# Paper crosses the 0.825-high nip between blanket and impression rolls.
verts = []
for i in range(17):
    y = -0.05 - (0.33 * i / 16)
    z = 0.825 - 0.025 * (max(0, -y - 0.16) / 0.22) ** 2
    verts.extend([(-0.945, y, z), (0.945, y, z)])
faces = [(i * 2, i * 2 + 1, i * 2 + 3, i * 2 + 2) for i in range(16)]
mesh = bpy.data.meshes.new("curved paper lead")
mesh.from_pydata(verts, [], faces)
mesh.update()
o = bpy.data.objects.new("paper emerging through nip", mesh)
bpy.context.collection.objects.link(o)
o.data.materials.append(paper)
objects.append(o)
# Printable planar sheet meets the curved lead exactly at the exit.
a = Vector((-0.945, -0.38, 0.80))
b = Vector((0.945, -0.38, 0.80))
c = Vector((-0.945, -1.90, 0.344))
d = b + (c - a)
mesh = bpy.data.meshes.new("newspaper plane")
mesh.from_pydata([a, b, d, c], [], [(0, 1, 2, 3)])
mesh.update()
sheet = bpy.data.objects.new("printable paper", mesh)
bpy.context.collection.objects.link(sheet)
sheet.data.materials.append(paper)
objects.append(sheet)
# Slight paper thickness gives an actual illuminated edge, not a floating flat overlay.
solid = sheet.modifiers.new("paper thickness", "SOLIDIFY")
solid.thickness = 0.009
# Orthographic isometric camera: paper extends to the lower right, like the supplied reference.
bpy.ops.object.camera_add(location=(-5, -7, 6.8))
camera = bpy.context.object
camera.rotation_euler = (
    (Vector((0, -0.50, 1.03)) - camera.location).to_track_quat("-Z", "Y").to_euler()
)
camera.data.type = "ORTHO"
camera.data.ortho_scale = 3.7
scene.camera = camera
for name, loc, power, size in [
    ("key", (-3, -4, 7), 620, 5),
    ("fill", (4, -1, 5), 360, 4),
    ("rim", (1, 4, 6), 550, 3),
]:
    bpy.ops.object.light_add(type="AREA", location=loc)
    o = bpy.context.object
    o.name = name
    o.data.energy = power
    o.data.shape = "DISK"
    o.data.size = size
    o.rotation_euler = (
        (Vector((0, 0, 1)) - o.location).to_track_quat("-Z", "Y").to_euler()
    )
# Native source retained for later refinement, outside the published asset directory.
bpy.ops.wm.save_as_mainfile(filepath=out + "/press.blend")
scene.render.filepath = out + "/press.png"
bpy.ops.render.render(write_still=True)


def pixel(v):
    co = world_to_camera_view(scene, camera, v)
    return [co.x * 640, (1 - co.y) * 640]


pa, pb, pc = map(pixel, [a, b, c])
matrix = [
    (pb[0] - pa[0]) / 240,
    (pb[1] - pa[1]) / 240,
    (pc[0] - pa[0]) / 320,
    (pc[1] - pa[1]) / 320,
    pa[0],
    pa[1],
]
json.dump(
    {"size": 640, "matrix": matrix, "paper_corners": [pa, pb, pixel(d), pc]},
    open(out + "/projection.json", "w"),
    indent=2,
)


# Occlusion mask is rendered from the same geometry/camera. White only where the printable sheet is visible.
def emission(name, color):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nodes = m.node_tree.nodes
    nodes.clear()
    e = nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = (*color, 1)
    e.inputs[1].default_value = 1
    outnode = nodes.new("ShaderNodeOutputMaterial")
    m.node_tree.links.new(e.outputs[0], outnode.inputs[0])
    return m


white = emission("mask white", (1, 1, 1))
zero = emission("mask black", (0, 0, 0))
for obj in objects:
    obj.data.materials.clear()
    obj.data.materials.append(white if obj == sheet else zero)
scene.view_settings.view_transform = "Standard"
scene.render.film_transparent = False
scene.world.use_nodes = True
scene.world.node_tree.nodes.get("Background").inputs[0].default_value = (0, 0, 0, 1)
scene.world.node_tree.nodes.get("Background").inputs[1].default_value = 0
scene.render.dither_intensity = 0
scene.render.image_settings.color_mode = "BW"
scene.cycles.samples = 4
scene.render.filepath = out + "/mask.png"
bpy.ops.render.render(write_still=True)

assets = root / "site/assets"
subprocess.run(
    [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        out + "/press.png",
        "-c:v",
        "libwebp",
        "-quality",
        "92",
        "-compression_level",
        "6",
        str(assets / "press-model.webp"),
    ],
    check=True,
)
shutil.copyfile(out + "/mask.png", assets / "press-mask.png")
projection = json.load(open(out + "/projection.json"))
js = assets / "printing.js"
source = js.read_text()
replacement = (
    "/* press-projection:start */\n  const pressProjection = "
    + json.dumps(projection, separators=(",", ":"))
    + ";\n  /* press-projection:end */"
)
source, count = re.subn(
    r"/\* press-projection:start \*/.*?/\* press-projection:end \*/",
    lambda _: replacement,
    source,
    flags=re.S,
)
if count != 1:
    raise RuntimeError("Missing unique projection marker in printing.js")
js.write_text(source)
