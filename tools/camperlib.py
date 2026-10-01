"""第二代 Q 版露營者（在 Blender 內使用）。參考《薩爾達傳說 智慧的再現》那種塑膠玩具人偶：大圓頭、短手腳、簡單的臉、圓潤無稜角。
- 身體：火柴人骨架（關節位置＋半徑）用 Skin modifier 長肉、Subdivision 細分 → 肩、髖、膝、肘自然相連，不再是棍子插球
- 骨架：照同一份關節表建 Armature；權重 = 最近的骨頭（關節附近兩根混合）；匯出 glTF skin，Godot 端 Skeleton3D 用程式擺姿勢／走路
- 臉：numpy 畫到貼圖（深色橢圓眼＋高光、眉毛、腮紅、小嘴、小鼻、瀏海／髮型），左右兩格（睜眼｜閉眼）供眨眼
- 配件：毛帽或漁夫帽、圍巾，合併進同一個 mesh，權重 100% 跟頭／脖子
- 手持道具（烤棉花糖的棍子、手沖壺、馬克杯）另外匯出，原點在握把，Godot 端用 BoneAttachment3D 掛到手骨
"""
import math
import bmesh, bpy
import numpy as np
from mathutils import Vector
import treelib as T
from proplib import pm, B, _dome

# 關節：名稱 → (位置 (x 前, y 左, z 上), Skin 半徑 (rx, ry))。單位公尺，約 2.8 頭身，站姿、手臂自然下垂
JOINTS = {
    "hips": ((0.0, 0.0, 0.50), (0.15, 0.17)),
    "chest": ((0.0, 0.0, 0.70), (0.155, 0.175)),
    "neck": ((0.01, 0.0, 0.84), (0.06, 0.065)),
    "head_top": ((0.03, 0.0, 1.22), (0.01, 0.01)),
    "hips_top": ((0.0, 0.0, 0.58), (0.01, 0.01)),
}
for _s, _n in ((1, "l"), (-1, "r")):
    JOINTS.update({
        "shoulder_" + _n: ((0.0, _s * 0.19, 0.78), (0.062, 0.062)),
        "elbow_" + _n: ((0.02, _s * 0.225, 0.63), (0.055, 0.055)),
        "wrist_" + _n: ((0.05, _s * 0.235, 0.50), (0.05, 0.05)),
        "hand_" + _n: ((0.07, _s * 0.24, 0.44), (0.065, 0.065)),
        "hip_" + _n: ((0.0, _s * 0.085, 0.46), (0.09, 0.09)),
        "knee_" + _n: ((0.01, _s * 0.09, 0.27), (0.075, 0.075)),
        "ankle_" + _n: ((0.01, _s * 0.09, 0.09), (0.06, 0.06)),
        "toe_" + _n: ((0.14, _s * 0.09, 0.045), (0.06, 0.05)),
    })

# 骨頭：(名稱, 起點關節, 終點關節, 父骨, 材質區, 是否參與 Skin 長肉)
BONES = [
    ("hips", "hips", "hips_top", None, "jacket", False),
    ("spine", "hips", "chest", "hips", "jacket", True),
    ("neck", "chest", "neck", "spine", "skin", True),
    ("head", "neck", "head_top", "neck", "skin", False),
]
for _n in ("l", "r"):
    BONES += [
        ("clavicle_" + _n, "chest", "shoulder_" + _n, "spine", "jacket", True),
        ("upperarm_" + _n, "shoulder_" + _n, "elbow_" + _n, "clavicle_" + _n, "jacket", True),
        ("forearm_" + _n, "elbow_" + _n, "wrist_" + _n, "upperarm_" + _n, "jacket", True),
        ("hand_" + _n, "wrist_" + _n, "hand_" + _n, "forearm_" + _n, "mitten", True),
        ("pelvis_" + _n, "hips", "hip_" + _n, "hips", "pants", True),
        ("thigh_" + _n, "hip_" + _n, "knee_" + _n, "pelvis_" + _n, "pants", True),
        ("shin_" + _n, "knee_" + _n, "ankle_" + _n, "thigh_" + _n, "pants", True),
        ("foot_" + _n, "ankle_" + _n, "toe_" + _n, "shin_" + _n, "boots", True),
    ]

HEAD_C = Vector((0.03, 0.0, 1.03))
HEAD_R = 0.21
HEAD_SCALE = (1.0, 1.04, 0.94)

# 服裝：材質名稱（pm()）。hat = beanie / bucket
OUTFITS = {
    "walk": {"jacket": "puffSky", "pants": "pantsNavy", "hat": "beanie", "hat_mat": "beanieGreen", "hair": (0.10, 0.045, 0.025), "scarf": "vanCream"},
    "roast": {"jacket": "puffMustard", "pants": "pantsNavy", "hat": "beanie", "hat_mat": "beanieRed", "hair": (0.045, 0.025, 0.017), "scarf": "vanCream"},
    "brew": {"jacket": "fleecePlum", "pants": "pantsKhaki", "hat": "bucket", "hat_mat": "hatOlive", "hair": (0.10, 0.045, 0.025), "scarf": "vanCream"},
}


# ---------------------------------------------------------------- 臉的貼圖

def _srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1.0 / 2.4) - 0.055)


def _ellipse(U, V, cu, cv, rx, ry, soft=0.004):
    d = np.sqrt(((U - cu) / rx) ** 2 + ((V - cv) / ry) ** 2)
    return np.clip((1.0 - d) * min(rx, ry) / soft, 0.0, 1.0)


def _band(U, V, cu, hw, vfn, th, soft=0.003):
    """沿 V = vfn(U) 的一條線，寬 2*hw、粗 th。"""
    iu = np.clip((hw - np.abs(U - cu)) / soft, 0.0, 1.0)
    iv = np.clip((th * 0.5 - np.abs(V - vfn(U))) / soft, 0.0, 1.0)
    return iu * iv


def _paint(img, mask, rgb):
    m = mask[..., None]
    img *= (1.0 - m)
    img += m * np.asarray(rgb, dtype=np.float64)[None, None, :]


def _face_atlas(name, hair, W=512, H=512):
    """等距柱狀投影的頭貼圖（u=0.5 是正臉、v=0 頭頂）。左半格睜眼、右半格閉眼（Godot 端 uv1_offset.x += 0.5 就眨眼）。"""
    skin = np.array((0.91, 0.60, 0.39))
    eye = np.array((0.012, 0.008, 0.008))
    white = np.array((1.0, 1.0, 1.0))
    blush = np.array((0.90, 0.33, 0.33))
    mouth = np.array((0.30, 0.08, 0.08))
    brow = np.array(hair) * 0.6
    u = (np.arange(W) + 0.5) / W
    v = (np.arange(H) + 0.5) / H
    U, V = np.meshgrid(u, v)
    frames = []
    for closed in (False, True):
        img = np.empty((H, W, 3))
        img[:] = skin
        # 頭髮：頭頂、鋸齒瀏海、側後方較長（鮑伯頭）；帽子會蓋掉頭頂，露出來的是瀏海與鬢角
        side = np.clip((np.abs(U - 0.5) - 0.24) / 0.08, 0.0, 1.0)
        bangs = 0.40 + 0.03 * np.abs(((U - 0.5) * 14.0) % 2.0 - 1.0)
        hairline = bangs * (1.0 - side) + 0.60 * side
        _paint(img, (V < hairline).astype(np.float64), hair)
        for sgn in (-1, 1):
            cu, cv, rx, ry = 0.5 + sgn * 0.075, 0.56, 0.038, 0.075
            if closed:
                _paint(img, _band(U, V, cu, rx * 0.95, lambda x, cu=cu, rx=rx: cv - 0.015 + 0.045 * ((x - cu) / rx) ** 2, 0.014), eye)
            else:
                _paint(img, _ellipse(U, V, cu, cv, rx, ry), eye)
                _paint(img, _ellipse(U, V, cu - sgn * 0.011, cv - 0.028, 0.012, 0.022), white)
                _paint(img, _ellipse(U, V, cu + sgn * 0.014, cv + 0.028, 0.006, 0.010), white)
            _paint(img, _band(U, V, cu, 0.05, lambda x, cu=cu: 0.455 - 0.018 * (1.0 - ((x - cu) / 0.05) ** 2), 0.011), brow)
            d = np.sqrt(((U - (0.5 + sgn * 0.125)) / 0.045) ** 2 + ((V - 0.645) / 0.032) ** 2)
            _paint(img, 0.55 * np.exp(-d * d * 2.2), blush)
        _paint(img, _ellipse(U, V, 0.5, 0.625, 0.007, 0.006, soft=0.003) * 0.45, skin * 0.75)   # 小鼻
        _paint(img, _band(U, V, 0.5, 0.024, lambda x: 0.700 + 0.014 * (1.0 - ((x - 0.5) / 0.024) ** 2), 0.007), mouth)
        frames.append(img)
    atlas = np.concatenate(frames, axis=1)
    rgba = np.concatenate([_srgb(atlas), np.ones((H, 2 * W, 1))], axis=2).astype(np.float32)
    image = bpy.data.images.new(name + "_face", 2 * W, H, alpha=True)
    image.pixels.foreach_set(rgba[::-1].ravel())   # Blender 影像是由下往上存
    image.pack()
    m = bpy.data.materials.new("face")
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    tex = m.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = image
    m.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.55
    return m


# ---------------------------------------------------------------- 幾何

def _seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-9)))
    return (p - (a + ab * t)).length


def _nearest_bones(p, names):
    return sorted(((_seg_dist(p, Vector(JOINTS[a][0]), Vector(JOINTS[b][0])), bn) for bn, a, b, _, _, _ in BONES if bn in names))


def _grow_body():
    """Skin + Subdivision 長出來的身體（不含頭），回傳 bmesh。"""
    skin_bones = [b for b in BONES if b[5]]
    used = []
    for _, a, b, _, _, _ in skin_bones:
        for j in (a, b):
            if j not in used:
                used.append(j)
    idx = {n: i for i, n in enumerate(used)}
    me = bpy.data.meshes.new("skel")
    me.from_pydata([JOINTS[n][0] for n in used], [(idx[a], idx[b]) for _, a, b, _, _, _ in skin_bones], [])
    ob = bpy.data.objects.new("skel", me)
    bpy.context.collection.objects.link(ob)
    mod = ob.modifiers.new("Skin", 'SKIN')
    mod.use_smooth_shade = True
    mod.branch_smoothing = 0.4
    for i, n in enumerate(used):
        sv = me.skin_vertices[0].data[i]
        sv.radius = JOINTS[n][1]
        sv.use_root = n == "hips"
    sub = ob.modifiers.new("Sub", 'SUBSURF')
    sub.levels = 2
    bpy.context.view_layer.update()
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    m2 = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(m2)
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    return bm


def _head_sphere(bm, uv, c, R, scale, segs=36, rings=18):
    """有 UV 的球：u=0.5 朝 +X（正臉），u 只用貼圖左半（0–0.5），右半是閉眼格。"""
    rows = []
    for i in range(1, rings):
        phi = math.pi * i / rings
        rows.append([bm.verts.new(c + Vector((math.sin(phi) * math.cos(2 * math.pi * (j / segs - 0.5)) * scale[0],
                                              math.sin(phi) * math.sin(2 * math.pi * (j / segs - 0.5)) * scale[1],
                                              math.cos(phi) * scale[2])) * R) for j in range(segs)])
    top = bm.verts.new(c + Vector((0, 0, R * scale[2])))
    bot = bm.verts.new(c + Vector((0, 0, -R * scale[2])))
    faces = []

    def setuv(f, uvs):
        for loop, (uu, vv) in zip(f.loops, uvs):
            loop[uv].uv = (uu * 0.5, 1.0 - vv)

    for j in range(segs):
        j1 = (j + 1) % segs
        u0, u1 = j / segs, (j + 1) / segs
        f = bm.faces.new((top, rows[0][j], rows[0][j1]))
        setuv(f, (((u0 + u1) * 0.5, 0.0), (u0, 1.0 / rings), (u1, 1.0 / rings)))
        faces.append(f)
        f = bm.faces.new((rows[-1][j1], rows[-1][j], bot))
        setuv(f, ((u1, (rings - 1) / rings), (u0, (rings - 1) / rings), ((u0 + u1) * 0.5, 1.0)))
        faces.append(f)
    for i in range(len(rows) - 1):
        v0, v1 = (i + 1) / rings, (i + 2) / rings
        for j in range(segs):
            j1 = (j + 1) % segs
            u0, u1 = j / segs, (j + 1) / segs
            f = bm.faces.new((rows[i][j], rows[i + 1][j], rows[i + 1][j1], rows[i][j1]))
            setuv(f, ((u0, v0), (u0, v1), (u1, v1), (u1, v0)))
            faces.append(f)
    verts = [top, bot] + [v for row in rows for v in row]
    return verts, faces


def _append_B(bm, b):
    """把 B 建好的幾何複製進 bm，回傳 (新頂點, [(新面, 材質)])。"""
    b.bm.verts.ensure_lookup_table()
    b.bm.faces.ensure_lookup_table()
    vmap = {v: bm.verts.new(v.co) for v in b.bm.verts}
    out = []
    for f in b.bm.faces:
        nf = bm.faces.new([vmap[v] for v in f.verts])
        rid = f[b.grp]
        m = b.groups[rid - 1][0] if rid > 0 else T.mats()["bark"]
        out.append((nf, m(f) if callable(m) else m))
    return list(vmap.values()), out


def _hat(kind, hat_mat, m):
    b = B()
    hc = HEAD_C + Vector((-0.01, 0, 0))
    if kind == "beanie":
        rb = HEAD_R + 0.03
        _dome(b, hc, rb, 22, scale=(1, 1.04, 1.12))
        b.use(m[hat_mat], smooth=True)
        zb = rb * 1.12 * math.sin(math.radians(22))
        b.torus(hc + Vector((0, 0, zb)), rb * math.cos(math.radians(22)), 0.036, axis='Z')
        b.sphere(hc + Vector((0, 0, rb * 1.12 + 0.02)), 0.058, sub=2)
        b.use(m["vanCream"], smooth=True)
    else:
        b.cyl(HEAD_C + Vector((0, 0, 0.18)), 0.215, 0.13, segs=24, r2=0.185)
        b.cyl(HEAD_C + Vector((0, 0, 0.115)), 0.31, 0.05, segs=24, r2=0.235)
        b.use(m[hat_mat], smooth=True)
    return b


def camper(name, outfit="walk"):
    """帶骨架的露營者。回傳 Armature 物件（根），身體 mesh 是它的子物件；gen_assets 會把整組匯成一個 GLB。"""
    o = OUTFITS[outfit]
    m = pm()
    face_mat = _face_atlas(name, o["hair"])
    bm = _grow_body()
    uv = bm.loops.layers.uv.new("UVMap")
    col = bm.loops.layers.color.new("Col")
    mats = []

    def idx_of(mat):
        if mat not in mats:
            mats.append(mat)
        return mats.index(mat)

    weights = {}   # BMVert → [(骨名, 權重)]
    skin_names = {b[0] for b in BONES if b[5]}
    body_verts = list(bm.verts)
    region_mat = {"jacket": m[o["jacket"]], "pants": m[o["pants"]], "boots": m["boots"], "mitten": m["mitten"], "skin": m["skin"]}
    region_of = {b[0]: b[4] for b in BONES}
    for f in bm.faces:
        c = f.calc_center_median()
        bn = _nearest_bones(c, skin_names)[0][1]
        reg = region_of[bn]
        # 軀幹與腿之間用高度切（外套下襬 0.455 m），比「最近的骨頭」乾淨；脖子只有圍巾以上才算皮膚
        if bn in ("spine", "clavicle_l", "clavicle_r", "pelvis_l", "pelvis_r", "thigh_l", "thigh_r"):
            reg = "jacket" if c.z > 0.455 else "pants"
        if reg == "skin" and c.z < 0.80:
            reg = "jacket"
        f.material_index = idx_of(region_mat[reg])
        f.smooth = True
    for v in body_verts:
        ds = _nearest_bones(v.co, skin_names | {"hips"})
        (d1, b1), (d2, b2) = ds[0], ds[1]
        blend = 0.04
        if d2 - d1 < blend:
            w1 = 0.5 + (d2 - d1) / (2.0 * blend)
            weights[v] = [(b1, w1), (b2, 1.0 - w1)]
        else:
            weights[v] = [(b1, 1.0)]
    # 頭、帽子、圍巾
    hv, hf = _head_sphere(bm, uv, HEAD_C, HEAD_R, HEAD_SCALE)
    face_idx = idx_of(face_mat)
    for f in hf:
        f.material_index = face_idx
        f.smooth = True
    for v in hv:
        weights[v] = [("head", 1.0)]
    hat_v, hat_f = _append_B(bm, _hat(o["hat"], o["hat_mat"], m))
    for f, mat in hat_f:
        f.material_index = idx_of(mat)
        f.smooth = True
    for v in hat_v:
        weights[v] = [("head", 1.0)]
    sb = B()
    sb.torus(Vector((0.01, 0, 0.845)), 0.095, 0.045, axis='Z')
    sb.use(m[o["scarf"]], smooth=True)
    sc_v, sc_f = _append_B(bm, sb)
    for f, mat in sc_f:
        f.material_index = idx_of(mat)
        f.smooth = True
    for v in sc_v:
        weights[v] = [("neck", 1.0)]
    for f in bm.faces:
        for loop in f.loops:
            loop[col] = (1, 1, 1, 1)
    bmesh.ops.recalc_face_normals(bm, faces=[f for f in bm.faces if f.material_index != face_idx])
    bm.verts.index_update()
    me = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(me)
    for mat in mats:
        me.materials.append(mat)
    # 骨架
    arm = bpy.data.armatures.new(name + "_arm")
    rig = bpy.data.objects.new(name, arm)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for bn, a, b_, parent, _, _ in BONES:
        eb = arm.edit_bones.new(bn)
        eb.head = Vector(JOINTS[a][0])
        eb.tail = Vector(JOINTS[b_][0])
        if parent:
            eb.parent = arm.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    body = bpy.data.objects.new(name + "_body", me)
    bpy.context.collection.objects.link(body)
    groups = {bn: body.vertex_groups.new(name=bn) for bn, *_ in BONES}
    per_group = {bn: [] for bn, *_ in BONES}
    for v, ws in weights.items():
        for bn, w in ws:
            per_group[bn].append((v.index, w))
    for bn, lst in per_group.items():
        for vi, w in lst:
            groups[bn].add([vi], w, 'REPLACE')
    am = body.modifiers.new("Armature", 'ARMATURE')
    am.object = rig
    body.parent = rig
    bm.free()
    return rig


# ---------------------------------------------------------------- 手持道具（原點 = 握把，+X 朝前）

def marshmallow_stick(name):
    m = pm()
    b = B()
    b.rod((-0.10, 0, 0), (0.95, 0, -0.04), 0.011, segs=8)
    b.use(m["woodPole"], smooth=True)
    b.sphere((0.98, 0, -0.045), 0.065, sub=2, scale=(1.15, 1.0, 1.0))
    b.use(m["white"], smooth=True)
    b.sphere((1.01, 0, -0.06), 0.045, sub=2, scale=(1.1, 1.0, 1.0))
    b.use(m["toast"], smooth=True)
    return b.done(name)


def kettle_hand(name):
    """鵝頸手沖壺：原點在提把頂（手握的地方），壺身在下方，壺嘴朝 +X。"""
    m = pm()
    k = B()
    kc = Vector((0.0, 0, -0.14))
    k.sphere(kc, 0.085, sub=3, scale=(1, 1, 0.8))
    k.cyl(kc + Vector((0, 0, 0.068)), 0.05, 0.02, segs=12)
    pts = [kc + Vector(p) for p in ((0.07, 0, 0.0), (0.14, 0, 0.05), (0.19, 0, 0.11), (0.24, 0, 0.12), (0.28, 0, 0.08))]
    for i in range(len(pts) - 1):
        k.rod(pts[i], pts[i + 1], 0.013 - 0.0015 * i, segs=8)
    k.use(m["copper"], smooth=True)
    k.sphere(kc + Vector((0, 0, 0.09)), 0.016, sub=1)
    hp = [kc + Vector(p) for p in ((-0.07, 0, 0.04), (-0.05, 0, 0.11), (-0.02, 0, 0.14), (0.02, 0, 0.14), (0.05, 0, 0.11), (0.07, 0, 0.04))]
    for i in range(len(hp) - 1):
        k.rod(hp[i], hp[i + 1], 0.012, segs=8)
    k.use(m["darkMetal"], smooth=True)
    return k.done(name)


def mug_hand(name):
    """馬克杯：原點在杯身側邊（手握處），杯子在 +X 側。"""
    m = pm()
    b = B()
    mc = Vector((0.06, 0, -0.02))
    b.cyl(mc, 0.05, 0.10, segs=14)
    b.use(m["vanCream"], smooth=True)
    b.cyl(mc + Vector((0, 0, 0.02)), 0.051, 0.03, segs=14)
    b.use(m["coolerBlue"], smooth=True)
    b.cyl(mc + Vector((0, 0, 0.045)), 0.042, 0.012, segs=14)
    b.use(m["coffee"], smooth=True)
    return b.done(name)
