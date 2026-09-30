"""把 assets/gen 的 GLB 排成一列渲染型錄。用法：Blender --background --python tools/lineup.py -- <gen資料夾> <輸出png>"""
import bpy, sys, os, math, glob
from mathutils import Vector
argv = sys.argv[sys.argv.index("--") + 1:]
gen, out = argv[:2]
prefixes = argv[2].split(",") if len(argv) > 2 else None
bpy.ops.wm.read_factory_settings(use_empty=True)
files = sorted(glob.glob(os.path.join(gen, "*.glb")))
if prefixes:
    files = [f for f in files if any(os.path.basename(f).startswith(px) for px in prefixes)]
x = 0.0
for f in files:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=f)
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    width = max(max(o.dimensions.x, o.dimensions.y) for o in new)
    x += width * 0.6
    for o in new:
        o.location.x = x
        o.rotation_euler = (0, 0, math.radians(20))
    x += width * 0.6 + 0.35
scene = bpy.context.scene
bpy.ops.mesh.primitive_plane_add(size=60, location=(x / 2, 0, 0))
floor = bpy.context.active_object
m = bpy.data.materials.new("floor"); m.use_nodes = True
m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.86, 0.9, 0.94, 1)
floor.data.materials.append(m)
sun_d = bpy.data.lights.new("Sun", "SUN"); sun_d.energy = 3.0; sun_d.angle = math.radians(4)
sun = bpy.data.objects.new("Sun", sun_d); scene.collection.objects.link(sun)
sun.rotation_euler = (math.radians(48), math.radians(15), math.radians(-40))
world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.86, 0.9, 0.94, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
cam_d = bpy.data.cameras.new("Cam"); cam_d.type = "ORTHO"; cam_d.ortho_scale = x + 0.6
cam = bpy.data.objects.new("Cam", cam_d); scene.collection.objects.link(cam)
ymax = max(o.dimensions.z for o in bpy.data.objects if o.type == "MESH" and o != floor)
cam.location = (x / 2, -30.0, 4.0)
cam.rotation_euler = (Vector((x / 2, 0, ymax * 0.45)) - cam.location).to_track_quat("-Z", "Y").to_euler()
scene.camera = cam
scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
scene.render.resolution_x, scene.render.resolution_y = 2400, int(2400 * max(ymax * 1.3, 1.0) / (x + 0.6)) + 40
scene.view_settings.view_transform = "Standard"
scene.render.filepath = out
bpy.ops.render.render(write_still=True)
print("LINEUP", out, len(files))
