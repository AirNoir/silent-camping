"""同一棵樹用不同葉子做法排成一列比較。用法：Blender --background --python tools/leaf_levels.py -- <輸出png>"""
import bpy, sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import treelib as T
from mathutils import Vector

out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
levels = [
    ("L0 blob（目前）", dict(leaf_style="blob", shade=False)),
    ("L1 blob + 頂點色", dict(leaf_style="blob")),
    ("L2 cluster 小葉團", dict(leaf_style="cluster")),
    ("L3 hybrid 葉團+葉片", dict(leaf_style="hybrid", leaf_count=70)),
    ("L4 leaves 純葉片", dict(leaf_style="leaves", leaf_count=220)),
    ("L5 leaves 密", dict(leaf_style="leaves", leaf_count=450)),
]
T.preview_vertex_colors()
scene = bpy.context.scene
x = 0.0
dark = bpy.data.materials.new("text"); dark.use_nodes = True
dark.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.2, 0.22, 0.25, 1)
for label, kw in levels:
    ob = T.tree_broadleaf("t", 2, **kw)
    ob.location.x = x
    ob.rotation_euler.z = math.radians(20)
    tris = T.tri_count(ob)
    print("LEVEL %s tris=%d" % (label, tris))
    bpy.ops.object.text_add(location=(x, -0.6, 2.45))
    t = bpy.context.active_object
    t.data.body = "%s\n%d tris" % (label, tris)
    t.data.size = 0.17
    t.data.align_x = "CENTER"
    t.rotation_euler = (math.radians(90), 0, 0)
    t.data.materials.append(dark)
    x += 2.4
bpy.ops.mesh.primitive_plane_add(size=60, location=(x / 2, 0, 0))
floor = bpy.context.active_object
fm = bpy.data.materials.new("floor"); fm.use_nodes = True
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.88, 0.9, 0.93, 1)
floor.data.materials.append(fm)
sun_d = bpy.data.lights.new("Sun", "SUN"); sun_d.energy = 3.0; sun_d.angle = math.radians(4)
sun = bpy.data.objects.new("Sun", sun_d); scene.collection.objects.link(sun)
sun.rotation_euler = (math.radians(48), math.radians(15), math.radians(-40))
world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.88, 0.9, 0.93, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
cam_d = bpy.data.cameras.new("Cam"); cam_d.type = "ORTHO"; cam_d.ortho_scale = x + 0.6
cam = bpy.data.objects.new("Cam", cam_d); scene.collection.objects.link(cam)
cam.location = (x / 2 - 1.2, -30.0, 3.0)
cam.rotation_euler = (Vector((x / 2 - 1.2, 0, 1.25)) - cam.location).to_track_quat("-Z", "Y").to_euler()
scene.camera = cam
scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
scene.render.resolution_x, scene.render.resolution_y = 2400, 620
scene.view_settings.view_transform = "Standard"
scene.render.filepath = out
bpy.ops.render.render(write_still=True)
print("DONE", out)
