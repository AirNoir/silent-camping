"""給 chibi 主角綁骨（在 Blender 內跑）：匯入遊戲空間的 character_chibi_b.glb（腳在原點、+X 朝前、z-up 匯入後約 1.16 m），
照 scripts/rig.gd 的骨名建 Armature、權重 = 最近的骨頭（關節附近兩根混合，同 camperlib 的做法），
匯出成 assets/gen/camper_hero.glb 給散步模式當主角。
- 分類限制候選骨：頭髮／眼睛／眉嘴鼻 100% 跟頭；外套（含袖）跟軀幹＋手臂；褲子跟骨盆＋腿；靴子跟小腿＋腳；
  素體（Chibi_Base_Mesh2）全骨架最近距離。這樣頭髮不會被鎖骨搶走、袖口不會黏到髖。
- 關節表是照 GLB 部件邊界量出來的（tools 裡那次量測），座標 (x 前, y 左, z 上)，跟 camperlib 同一套慣例。
用法：Blender --background --python tools/chibi_rig.py -- [in.glb] [out.glb]
"""
import sys
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SRC = argv[0] if len(argv) > 0 else "assets/gen/character_chibi_b.glb"
DST = argv[1] if len(argv) > 1 else "assets/gen/camper_hero.glb"

# 關節：名稱 → 位置 (x 前, y 左, z 上)。從 GLB 部件邊界量出：
# 腰帶 z 0.32–0.36、外套 z 0.29–0.59、袖口 y ±0.25 z 0.33–0.41、褲 z 0.12–0.36、靴 z 0.01–0.14、臉在 x +0.15
JOINTS = {
    "hips": (0.0, 0.0, 0.34),
    "hips_top": (0.0, 0.0, 0.40),
    "chest": (0.0, 0.0, 0.48),
    "neck": (0.01, 0.0, 0.60),
    "head_top": (0.03, 0.0, 1.10),
}
for _s, _n in ((1, "l"), (-1, "r")):
    JOINTS.update({
        "shoulder_" + _n: (0.0, _s * 0.14, 0.50),
        "elbow_" + _n: (0.01, _s * 0.195, 0.43),
        "wrist_" + _n: (0.02, _s * 0.225, 0.365),
        "hand_" + _n: (0.03, _s * 0.255, 0.315),
        "hip_" + _n: (0.0, _s * 0.075, 0.30),
        "knee_" + _n: (0.01, _s * 0.078, 0.20),
        "ankle_" + _n: (0.0, _s * 0.078, 0.08),
        "toe_" + _n: (0.12, _s * 0.078, 0.045),
    })

# (骨名, 起點關節, 終點關節, 父骨) —— 名稱與階層照 scripts/rig.gd 的 ORDER
BONES = [
    ("hips", "hips", "hips_top", None),
    ("spine", "hips", "chest", "hips"),
    ("neck", "chest", "neck", "spine"),
    ("head", "neck", "head_top", "neck"),
]
for _n in ("l", "r"):
    BONES += [
        ("clavicle_" + _n, "chest", "shoulder_" + _n, "spine"),
        ("upperarm_" + _n, "shoulder_" + _n, "elbow_" + _n, "clavicle_" + _n),
        ("forearm_" + _n, "elbow_" + _n, "wrist_" + _n, "upperarm_" + _n),
        ("hand_" + _n, "wrist_" + _n, "hand_" + _n, "forearm_" + _n),
        ("pelvis_" + _n, "hips", "hip_" + _n, "hips"),
        ("thigh_" + _n, "hip_" + _n, "knee_" + _n, "pelvis_" + _n),
        ("shin_" + _n, "knee_" + _n, "ankle_" + _n, "thigh_" + _n),
        ("foot_" + _n, "ankle_" + _n, "toe_" + _n, "shin_" + _n),
    ]

ARMS = {"clavicle_l", "clavicle_r", "upperarm_l", "upperarm_r", "forearm_l", "forearm_r", "hand_l", "hand_r"}
LEG_BONES = {"pelvis_l", "pelvis_r", "thigh_l", "thigh_r", "shin_l", "shin_r"}
FOOT_BONES = {"shin_l", "shin_r", "foot_l", "foot_r"}
ALL_SKIN = {b[0] for b in BONES if b[0] != "hips"}

# 物件 → 候選骨集合（沒列到的用全骨架）
HEAD_ONLY = {"SM_Hair_Base_03_L", "SM_Hair_Bangs_08_L", "C_swept_lock", "C_upper_crease", "brows", "mouth", "nose_hint"}
TORSO_ARMS = {"jacket", "jacket_trim", "jacket_cuffs", "jacket_patch", "jacket_pockets", "inner_hoodie", "waistband", "C_hood_front"}
TORSO_ONLY = {"hood", "backpack"}
LEGS = {"pants", "cargo_pockets"}
FEET = {"boots", "boot_toecaps", "soles", "laces"}


def candidates(name: str):
    base = name.split(".")[0]
    if base in HEAD_ONLY or base.startswith("eye_"):
        return None   # 快速路徑：100% head
    if base in TORSO_ARMS:
        return {"spine", "neck"} | ARMS
    if base in TORSO_ONLY:
        return {"spine", "neck"}
    if base in LEGS:
        return {"spine"} | LEG_BONES
    if base in FEET:
        return FOOT_BONES
    return ALL_SKIN


def seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-9)))
    return (p - (a + ab * t)).length


SEGS = {bn: (Vector(JOINTS[a]), Vector(JOINTS[b])) for bn, a, b, _ in BONES}

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
meshes = [o for o in bpy.data.objects if o.type == "MESH"]

# 攤平物件變換進頂點資料：glTF 匯出器會忽略「蒙皮網格」的節點變換（規格如此），
# 原始 GLB 的縮放在節點上（素模 2.83 m × 節點縮放 ≈ 1.16 m），不攤平就會匯出 2.8 m 的巨人
bpy.ops.object.select_all(action='DESELECT')
for ob in meshes:
    ob.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for o in [o for o in bpy.data.objects if o.type == 'EMPTY']:
    bpy.data.objects.remove(o, do_unlink=True)

# 骨架
arm = bpy.data.armatures.new("hero_arm")
rig = bpy.data.objects.new("camper_hero", arm)
bpy.context.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='EDIT')
for bn, a, b, parent in BONES:
    eb = arm.edit_bones.new(bn)
    eb.head = Vector(JOINTS[a])
    eb.tail = Vector(JOINTS[b])
    if parent:
        eb.parent = arm.edit_bones[parent]
bpy.ops.object.mode_set(mode='OBJECT')

BLEND = 0.035
total_v = 0
for ob in meshes:
    cand = candidates(ob.name)
    groups = {}

    def grp(bn):
        if bn not in groups:
            groups[bn] = ob.vertex_groups.new(name=bn)
        return groups[bn]

    if cand is None:
        g = grp("head")
        g.add(list(range(len(ob.data.vertices))), 1.0, 'REPLACE')
    else:
        segs = [(bn, SEGS[bn][0], SEGS[bn][1]) for bn in cand]
        mw = ob.matrix_world
        for v in ob.data.vertices:
            p = mw @ v.co
            ds = sorted((seg_dist(p, a, b), bn) for bn, a, b in segs)
            (d1, b1), (d2, b2) = ds[0], ds[1] if len(ds) > 1 else ds[0]
            if d2 - d1 < BLEND and b1 != b2:
                w1 = 0.5 + (d2 - d1) / (2.0 * BLEND)
                grp(b1).add([v.index], w1, 'REPLACE')
                grp(b2).add([v.index], 1.0 - w1, 'REPLACE')
            else:
                grp(b1).add([v.index], 1.0, 'REPLACE')
    total_v += len(ob.data.vertices)
    mod = ob.modifiers.new("Armature", 'ARMATURE')
    mod.object = rig
    ob.parent = rig

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=DST, export_format='GLB')
print("CHIBI_RIG ok meshes=%d verts=%d bones=%d -> %s" % (len(meshes), total_v, len(BONES), DST))
