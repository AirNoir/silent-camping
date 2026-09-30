"""單一 GLB 的正面／指定角度渲染。用法：Blender --background --python tools/quick_view.py -- <glb> <out.png> [yaw_deg] [pitch_deg]"""
import bpy, sys, math
from mathutils import Vector
argv = sys.argv[sys.argv.index("--") + 1:]
glb, out = argv[0], argv[1]
yaw = math.radians(float(argv[2])) if len(argv) > 2 else math.radians(35)
pitch = math.radians(float(argv[3])) if len(argv) > 3 else math.radians(18)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
objs = [o for o in bpy.data.objects if o.type == "MESH"]
lo = Vector((min(min((o.matrix_world @ Vector(c)).x for c in o.bound_box) for o in objs),
             min(min((o.matrix_world @ Vector(c)).y for c in o.bound_box) for o in objs),
             min(min((o.matrix_world @ Vector(c)).z for c in o.bound_box) for o in objs)))
hi = Vector((max(max((o.matrix_world @ Vector(c)).x for c in o.bound_box) for o in objs),
             max(max((o.matrix_world @ Vector(c)).y for c in o.bound_box) for o in objs),
             max(max((o.matrix_world @ Vector(c)).z for c in o.bound_box) for o in objs)))
center = (lo + hi) / 2
size = (hi - lo).length
scene = bpy.context.scene
sun_d = bpy.data.lights.new("Sun", "SUN"); sun_d.energy = 3.0; sun_d.angle = math.radians(4)
sun = bpy.data.objects.new("Sun", sun_d); scene.collection.objects.link(sun)
sun.rotation_euler = (math.radians(48), math.radians(15), math.radians(-40))
world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.88, 0.9, 0.93, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
cam_d = bpy.data.cameras.new("Cam"); cam_d.lens = 50
cam = bpy.data.objects.new("Cam", cam_d); scene.collection.objects.link(cam)
d = Vector((math.cos(yaw) * math.cos(pitch), math.sin(yaw) * math.cos(pitch), math.sin(pitch)))
cam.location = center + d * size * 1.6
cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
scene.camera = cam
scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
scene.render.resolution_x, scene.render.resolution_y = 1200, 900
scene.view_settings.view_transform = "Standard"
scene.render.filepath = out
bpy.ops.render.render(write_still=True)
print("QUICK", out)
