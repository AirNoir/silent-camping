"""角色四視圖：正面正交、3/4 透視、側面正交、背面正交，各存一張 <out>_front/q34/side/back.png。模型正面朝 +X。
用法：Blender --background --python tools/turnaround.py -- <glb> <out.png> [wire] [head]（wire：疊一層線框看拓撲；head：只拍頭部特寫 front/q34/side）
"""
import bpy, sys, math, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
glb, out = argv[0], argv[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
objs = [o for o in bpy.data.objects if o.type == "MESH"]
pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
ctr = (lo + hi) / 2
if "wire" in argv[2:]:
    wm = bpy.data.materials.new("wire")
    wm.diffuse_color = (0.02, 0.02, 0.03, 1)
    wm.use_nodes = True
    next(n for n in wm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.02, 0.02, 0.03, 1)
    for o in objs:
        w = o.copy()
        w.data = o.data.copy()
        bpy.context.scene.collection.objects.link(w)
        mod = w.modifiers.new("W", "WIREFRAME")
        mod.thickness = 0.0016
        mod.use_even_offset = False
        w.data.materials.clear()
        w.data.materials.append(wm)
height = hi.z - lo.z

scene = bpy.context.scene
key = bpy.data.objects.new("Key", bpy.data.lights.new("Key", "SUN"))
key.data.energy, key.data.angle = 3.2, math.radians(6)
key.rotation_euler = (math.radians(50), 0, math.radians(35))   # 前上方偏左
fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", "SUN"))
fill.data.energy = 0.8
fill.rotation_euler = (math.radians(60), 0, math.radians(200))
for o in (key, fill):
    scene.collection.objects.link(o)
world = bpy.data.worlds.new("W")
scene.world = world
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs["Color"].default_value = (0.80, 0.80, 0.78, 1)
bg.inputs["Strength"].default_value = 1.0
engines = [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
scene.view_settings.view_transform = "Standard"
scene.render.resolution_x, scene.render.resolution_y = 640, 1000

cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
scene.collection.objects.link(cam)
scene.camera = cam
VIEWS = (("front", 0, 0, True), ("q34", 35, 8, False), ("side", 90, 0, True), ("back", 180, 0, True))
if "head" in argv[2:]:
    # 頭部特寫：以頭髮頂端往下約 0.3 個全高為中心，正交寬度約 0.62 個全高
    ctr = Vector((ctr.x, ctr.y, hi.z - height * 0.30))
    height = height * 0.56
    VIEWS = (("head_front", 0, 0, True), ("head_q34", 35, 6, False), ("head_side", 90, 0, True), ("head_back", 180, 0, True))
    scene.render.resolution_x = scene.render.resolution_y = 900
for name, yaw, pitch, ortho in VIEWS:
    y, p = math.radians(yaw), math.radians(pitch)
    d = Vector((math.cos(y) * math.cos(p), math.sin(y) * math.cos(p), math.sin(p)))
    if ortho:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = height * 1.12
        cam.location = ctr + d * 5.0
    else:
        cam.data.type = "PERSP"
        cam.data.lens = 85
        cam.location = ctr + d * height * 2.7
    cam.rotation_euler = (ctr - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.splitext(out)[0] + "_" + name + ".png"
    bpy.ops.render.render(write_still=True)
print("TURNAROUND", out)
