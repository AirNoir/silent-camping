"""BunnyBite 模組化髮型 → 原始 Chibi_Base_Mesh2 頭：四組原型比較表。
用法：Blender --background <Chibi_Base_Mesh2.blend> --python tools/hairpack_fit.py -- <out_prefix> [out.blend]
- 頭：原始網格，不動（只有渲染用的平滑著色與不套用的細分修飾器）
- 頭髮：GLB 原樣匯入，只做一次「移動＋縮放」：廠商頭皮殼（Base 08 的球心與半徑）對到 Q 版頭殼（橢球），
  x/y 等比、z 略放大（頭殼是蛋形），同一個變換套在每一片上，所以 Base 與 Bangs 的相對位置就是原設計
- 不雕刻、不改頂點、不合併、不用後髮
"""
import bpy, sys, os, math
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
OUT_BLEND = argv[1] if len(argv) > 1 else None
PACK = "/Users/a01-0220-0077/Downloads/Modular Men Hair Pack v.1/Meshes/GLB"

# 廠商頭皮殼（Base 08 外框實測：x ±7.71、y -6.66..8.82、頂 7.47）→ 球心 (0, 1.08, -0.25)、半徑 7.72
C_V = Vector((0.0, 1.08, -0.25)); R_V = 7.72
# Q 版頭殼（原始網格實測）：中心 (0, 0.065, 0.607)、半徑 (0.49, 0.51, 0.61)
C_C = Vector((0.0, 0.065, 0.607)); R_C = Vector((0.49, 0.51, 0.61))
CLEAR = 0.03                                   # 頭髮殼離頭殼的距離
S_XY = (R_C.x + CLEAR) / R_V                   # 0.0674：兩側剛好離頭皮 CLEAR
S_Z = (R_C.z + CLEAR) / R_V                    # 0.0829：頭頂剛好離頭皮 CLEAR（z 比 x/y 多 23%）
S_XY, S_Z = S_XY * 1.06, S_Z * 0.97            # 折衷：側邊多一點量、頂上少一點拉伸 → z/x ≈ 1.13
SCALE = Vector((S_XY, S_XY, S_Z))
LIFT = Vector((0.0, 0.0, 0.0))
M_FIT = Matrix.Translation(C_C + LIFT) @ Matrix.Diagonal((SCALE.x, SCALE.y, SCALE.z, 1.0)) @ Matrix.Translation(-C_V)

PROTOS = [("A", "Base 05 + Bangs 08", ["SM_Hair_Base_05_L", "SM_Hair_Bangs_08_L"]),
          ("B", "Base 03 + Bangs 08", ["SM_Hair_Base_03_L", "SM_Hair_Bangs_08_L"]),
          ("C", "Base 05 + Bangs 01", ["SM_Hair_Base_05_L", "SM_Hair_Bangs_01_L"]),
          ("D", "Base 07 + Bangs 08", ["SM_Hair_Base_07_L", "SM_Hair_Bangs_08_L"])]

head = bpy.data.objects.get("Chibi_Base_Mesh2") or next(o for o in bpy.data.objects if o.type == "MESH")
for p in head.data.polygons:
    p.use_smooth = True                        # 只是著色；不改幾何
sd = head.modifiers.new("PreviewSubdiv", "SUBSURF"); sd.levels = sd.render_levels = 1   # 渲染預覽，不套用
m_skin = bpy.data.materials.new("proto_skin"); m_skin.use_nodes = True
b = next(n for n in m_skin.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
b.inputs["Base Color"].default_value = (0.88, 0.60, 0.44, 1); b.inputs["Roughness"].default_value = 0.9
head.data.materials.clear(); head.data.materials.append(m_skin)

m_hair = bpy.data.materials.new("proto_hair"); m_hair.use_nodes = True
b = next(n for n in m_hair.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
b.inputs["Base Color"].default_value = (0.13, 0.067, 0.043, 1); b.inputs["Roughness"].default_value = 0.85; b.inputs["Metallic"].default_value = 0.0
for key in ("Specular IOR Level", "Specular"):
    if key in b.inputs:
        b.inputs[key].default_value = 0.2; break

pieces = {}
for name in sorted({n for _, _, ns in PROTOS for n in ns}):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(PACK, name + ".glb"))
    new = [o for o in bpy.data.objects if o not in before]
    ob = next(o for o in new if o.type == "MESH")
    for o in new:
        if o is not ob: bpy.data.objects.remove(o)
    ob.name = name
    ob.matrix_world = M_FIT @ ob.matrix_world   # 只有這一個變換；頂點資料不動
    ob.data.materials.clear(); ob.data.materials.append(m_hair)
    for p in ob.data.polygons: p.use_smooth = True
    pieces[name] = ob
    ws = [ob.matrix_world @ v.co for v in ob.data.vertices]
    print("FIT %-20s x[%.3f,%.3f] y[%.3f,%.3f] z[%.3f,%.3f]" % (name, min(p.x for p in ws), max(p.x for p in ws), min(p.y for p in ws), max(p.y for p in ws), min(p.z for p in ws), max(p.z for p in ws)))
print("FIT scale xy=%.4f z=%.4f (z/xy=%.2f)  hair shell radii ≈ (%.3f, %.3f, %.3f) vs skull (%.2f, %.2f, %.2f)" % (
    SCALE.x, SCALE.z, SCALE.z / SCALE.x, R_V * SCALE.x, R_V * SCALE.y, R_V * SCALE.z, R_C.x, R_C.y, R_C.z))

# 渲染：同一顆鏡頭、同一組燈、同一個背景
sc = bpy.context.scene
for o in list(bpy.data.objects):
    if o.type in ("CAMERA", "LIGHT"): bpy.data.objects.remove(o)
for a, e, r in ((50, 3.0, -30), (65, 0.9, 160)):
    l = bpy.data.objects.new("L", bpy.data.lights.new("L", "SUN")); l.data.energy = e; l.data.angle = math.radians(8)
    l.rotation_euler = (math.radians(a), 0, math.radians(r)); sc.collection.objects.link(l)
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
next(n for n in w.node_tree.nodes if n.type == "BACKGROUND").inputs["Color"].default_value = (0.84, 0.84, 0.82, 1)
eng = [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in eng else "BLENDER_EEVEE"
sc.view_settings.view_transform = "Standard"; sc.render.resolution_x = sc.render.resolution_y = 800
cam = bpy.data.objects.new("C", bpy.data.cameras.new("C")); sc.collection.objects.link(cam); sc.camera = cam
CTR = Vector((0.0, 0.06, 0.55)); ORTHO = 2.1
VIEWS = (("front", (0, -1, 0), True), ("q34", (0.57, -0.80, 0.12), False), ("side", (1, 0, 0), True), ("back", (0, 1, 0), True))
for ob in pieces.values(): ob.hide_render = True
for key, label, names in PROTOS:
    for n in names: pieces[n].hide_render = False
    for vname, d, ortho in VIEWS:
        d = Vector(d).normalized()
        if ortho: cam.data.type = "ORTHO"; cam.data.ortho_scale = ORTHO; cam.location = CTR + d * 6
        else: cam.data.type = "PERSP"; cam.data.lens = 85; cam.location = CTR + d * 5.6
        cam.rotation_euler = (CTR - cam.location).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = "%s_%s_%s.png" % (OUT, key, vname); bpy.ops.render.render(write_still=True)
    for n in names: pieces[n].hide_render = True
if OUT_BLEND:
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print("PROTOS done")
