"""在「原始」Chibi_Base_Mesh2 上穿衣服、做髮型與臉（依森林露營角色設定板的男主角）。身體比例完全不動。
用法：Blender --background <Chibi_Base_Mesh2.blend> --python tools/chibi_dress.py -- <out.blend> [out.glb]
- 身體：原始 mesh 原封不動（只加材質與預覽用 Subdivision）
- 臉：深棕直橢圓眼（間距略寬）、短而淡的眉、很小的弧線嘴；原始頭型與鼻子不動
- 頭髮：SM_M_Head_s.04（Men Hair Set 04）原樣套上，只用等比縮放、平移、旋轉；暖深棕純色
- 外套：從身體的軀幹＋手臂區域複製一層殼，沿法線往外推（鋪棉感、改變剪影），前襟敞開；邊緣沿邊界環掃一圈厚滾邊（領口、前襟、下襬），袖口綠色
- 內搭：米白色貼身殼（從外套開口看得到）+ 圍在脖子後面的米白帽兜
- 褲子：腿部複製的殼往外推得比較多（寬鬆），往腳踝收；米白反摺褲腳、大腿外側工裝口袋
- 靴子：每隻腳另外做（比光腳大很多）：厚鞋底、圓鞋頭、靴筒、簡化鞋帶，靴口上方露出米白襪
- 背包：深棕圓角小背包、上蓋、前口袋、肩帶貼著外套表面繞過肩膀
- 材質全霧面（roughness 0.8–0.95、metallic 0、specular 很弱）
原始 mesh 正面是 -Y、只有右半（x ≥ 0）＋ Mirror modifier；這裡先取鏡像後的完整網格再複製衣服殼。
"""
import bpy, bmesh, sys, math
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
OUT_BLEND = argv[0]
OUT_GLB = argv[1] if len(argv) > 1 else None
GAME_BODY_HEIGHT = 1.10     # 遊戲裡身體（不含頭髮）的高度，公尺；比第三代露營者（1.05）略高
GROUND = -1.434

# 原始 mesh 的地標（實測）
S = Vector((0.27, 0.04, -0.17))      # 肩關節
W = Vector((0.51, 0.04, -0.55))      # 腕
AX = (W - S).normalized()
LA = (W - S).length
HEAD_C = Vector((0.0, 0.06, 0.60))   # 頭的中心
HEAD_R = Vector((0.49, 0.51, 0.61))  # 頭的半徑


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def mat(name, rgb, rough=0.85):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = 0.0
    for key in ("Specular IOR Level", "Specular"):
        if key in b.inputs:
            b.inputs[key].default_value = 0.15
            break
    return m


# 材質名稱都加 dress_ 前綴：避免撞到 forest.gd 裡給舊露營者用的亮面材質表（例如 "skin"）
M = {
    "skin": mat("dress_skin", (0.88, 0.60, 0.44), 0.90),
    "skin_shade": mat("dress_skin_shade", (0.72, 0.44, 0.30), 0.90),   # 耳窩（略深的膚色）
    "eye": mat("dress_eye", (0.030, 0.021, 0.016), 0.75),        # 深暖棕 #302822，不是純黑
    "lid": mat("dress_lid", (0.075, 0.048, 0.034), 0.85),         # 上眼皮：比眼睛略亮的暖棕，很柔
    "glint": mat("dress_glint", (0.50, 0.45, 0.40), 0.6),
    "brow": mat("dress_brow", (0.055, 0.030, 0.019), 0.9),       # 深棕眉
    "mouth": mat("dress_mouth", (0.26, 0.11, 0.09), 0.9),        # 柔和的暖棕珊瑚
    "hair": mat("dress_hair", (0.130, 0.067, 0.043), 0.88),      # 暖中深棕 #65493B（純色，不用寫實頭髮貼圖）
    "jacket": mat("dress_jacket", (0.62, 0.19, 0.04), 0.9),      # 暖橘外套
    "trim": mat("dress_trim", (0.13, 0.20, 0.05), 0.9),          # 綠色袖口
    "cream": mat("dress_cream", (0.83, 0.76, 0.58), 0.9),        # 米白內搭／帽兜／褲腳／襪
    "pants": mat("dress_pants", (0.11, 0.15, 0.045), 0.9),       # 橄欖綠工裝褲
    "boot": mat("dress_boot", (0.17, 0.065, 0.025), 0.8),        # 棕色登山靴
    "sole": mat("dress_sole", (0.55, 0.42, 0.28), 0.85),         # 淺棕厚鞋底
    "pack": mat("dress_pack", (0.07, 0.042, 0.025), 0.9),        # 深棕背包
    "patch": mat("dress_patch", (0.50, 0.27, 0.10), 0.9),
}


# ================================================================ 小工具

def link(name, bm, m, parent, subsurf=0, solid=0.0, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.parent = parent
    if solid:
        s = o.modifiers.new("Solidify", "SOLIDIFY")
        s.thickness = solid
        s.offset = -1.0
        s.use_rim = True
    if subsurf:
        d = o.modifiers.new("Subdivision", "SUBSURF")
        d.levels = d.render_levels = subsurf
    return o


def ellipsoid(bm, c, r, rot=Matrix.Identity(3), sub=3):
    M4 = Matrix.Translation(Vector(c)) @ rot.to_4x4() @ Matrix.Diagonal((r[0], r[1], r[2], 1))
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0, matrix=M4)


def rbox(bm, c, size, rot=Matrix.Identity(3), bevel=0.0, seg=3):
    M4 = Matrix.Translation(Vector(c)) @ rot.to_4x4() @ Matrix.Diagonal((size[0], size[1], size[2], 1))
    r = bmesh.ops.create_cube(bm, size=1.0, matrix=M4)
    if bevel > 0:
        es = list({e for v in r["verts"] for e in v.link_edges})
        bmesh.ops.bevel(bm, geom=es, offset=bevel, segments=seg, affect='EDGES', profile=0.5)


def tube(bm, pts, radii, k=10, closed=False, cap=True, side=None, taper_ends=False):
    """沿點列掃截面（radii = 每點 (寬, 厚) 或單一半徑）。closed = 首尾相接的環（滾邊、袖口）。"""
    P = [Vector(p) for p in pts]
    n = len(P)
    rings = []
    for i, p in enumerate(P):
        if closed:
            t = (P[(i + 1) % n] - P[(i - 1) % n]).normalized()
        else:
            t = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized()
        sd = Vector(side[i] if isinstance(side, list) else (side or (0, 0, 1)))
        if sd.length < 1e-6 or abs(sd.normalized().dot(t)) > 0.95:
            sd = Vector((1, 0, 0)) if abs(t.x) < 0.9 else Vector((0, 1, 0))
        w = (sd - t * sd.dot(t)).normalized()
        d = w.cross(t).normalized()
        r = radii[i] if isinstance(radii, list) else radii
        rw, rd = r if isinstance(r, tuple) else (r, r)
        if taper_ends:
            f = i / (n - 1)
            k2 = 0.35 + 0.65 * math.sin(math.pi * (0.1 + 0.8 * f))
            rw, rd = rw * k2, rd * k2
        rings.append([bm.verts.new(p + w * (rw * math.cos(2 * math.pi * j / k)) + d * (rd * math.sin(2 * math.pi * j / k))) for j in range(k)])
    segs = n if closed else n - 1
    for i in range(segs):
        A, C = rings[i], rings[(i + 1) % n]
        for j in range(k):
            bm.faces.new((A[j], A[(j + 1) % k], C[(j + 1) % k], C[j]))
    if cap and not closed:
        bm.faces.new(rings[0][::-1])
        bm.faces.new(rings[-1])


def boundary_loops(bm):
    """bmesh 的開放邊界串成頂點環（滾邊用）。"""
    adj = {}
    for e in bm.edges:
        if e.is_boundary:
            a, b = e.verts
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
    seen, loops = set(), []
    for start in adj:
        if start in seen:
            continue
        loop, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nxt = [v for v in adj[cur] if v is not prev and v not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            loop.append(cur)
            seen.add(cur)
        if len(loop) > 4:
            loops.append([v.co.copy() for v in loop])
    return loops


def smooth_loop(pts, it=3):
    for _ in range(it):
        n = len(pts)
        pts = [(pts[(i - 1) % n] + pts[i] * 2 + pts[(i + 1) % n]) / 4 for i in range(n)]
    return pts


def arm_w(p):
    """手臂區域（腋下以下切得利，肩頭柔和）。"""
    x = abs(p.x)
    if p.z > -0.06:
        return 0.0
    lo = smoothstep(-0.25, -0.35, p.z)
    width = 0.03 + (0.008 - 0.03) * lo
    line = 0.19 + (-0.08 - p.z) * 0.3235 - 0.02 * lo
    return smoothstep(-width, width, x - line)


def arm_a(p):
    return (Vector((abs(p.x), p.y, p.z)) - S).dot(AX)


def shell(src, keep, offset, delete_extra=None):
    """從完整身體 bmesh 複製一層殼：keep(面中心) 決定保留的面，offset(co, normal) 決定沿法線往外推多少。"""
    bm = src.copy()
    bm.normal_update()
    bm.verts.ensure_lookup_table()
    nrm = [v.normal.copy() for v in bm.verts]
    lay = bm.verts.layers.int["orig_idx"]
    for v in bm.verts:
        v[lay] = v.index
    kill = [f for f in bm.faces if not keep(f.calc_center_median()) or (delete_extra and delete_extra(f.calc_center_median()))]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    for v in bm.verts:
        n = nrm[v[lay]]
        v.co += n * offset(v.co, n)
    return bm


# ================================================================ 準備身體

body = bpy.data.objects.get("Chibi_Base_Mesh2") or next(o for o in bpy.data.objects if o.type == "MESH")
body.data.materials.clear()
body.data.materials.append(M["skin"])
for p in body.data.polygons:
    p.use_smooth = True
root = bpy.data.objects.new("character_chibi_dressed", None)
bpy.context.scene.collection.objects.link(root)
body.parent = root


def gauss(dx, dz, sx, sz):
    return math.exp(-(dx * dx) / (2 * sx * sx) - (dz * dz) / (2 * sz * sz))


# 頭的網格完全不動（原始 Chibi_Base_Mesh2 的頭、臉、下巴、頭殼深度都鎖住）

# 完整（只套鏡像）的身體網格：衣服殼的來源、射線的目標
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
ev = body.evaluated_get(dg)
full = bmesh.new()
full.from_mesh(ev.to_mesh())
ev.to_mesh_clear()
lay_idx = full.verts.layers.int.new("orig_idx")
full.normal_update()
body_bvh = BVHTree.FromBMesh(full)
sd = body.modifiers.new("Subdivision", "SUBSURF")
sd.levels = sd.render_levels = 1
# 臉部件貼在「細分後」的臉上（看到的就是細分後的表面）
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
ev = body.evaluated_get(dg)
fbm = bmesh.new()
fbm.from_mesh(ev.to_mesh())
ev.to_mesh_clear()
face_bvh = BVHTree.FromBMesh(fbm)
fbm.free()


def hit_from(origin, direction, bvh=None):
    h = (bvh or body_bvh).ray_cast(Vector(origin), Vector(direction).normalized())
    return h[0], h[1]


# ================================================================ 臉（貼合臉表面的薄片，不是黏上去的膠囊）
# 依設定板量的比例（臉寬 F≈0.86）：眼睛中心在下巴上方 ~0.34F、眼高 ~0.27F、眼寬 ~0.15F、
# 兩眼中心距 ~0.45F；嘴很靠近下巴、在眼睛正下方不遠；眉毛緊貼眼睛上方（大半藏在瀏海下）
EYE_Z, EYE_X, EYE_H, EYE_W = 0.420, 0.215, 0.090, 0.048


def decal(bm, cx, cz, shape, rings=5, segs=28, lift=0.003, bulge=0.0):
    """在臉上貼一片：shape(r, θ) -> (dx, dz) 平面輪廓（r∈[0,1]），沿前方射線投到細分後的臉，沿法線抬一點；bulge 讓中間微微鼓起。"""
    grid = []
    for i in range(rings + 1):
        r = i / rings
        row = []
        for j in range(segs if i else 1):
            th = 2 * math.pi * j / segs
            dx, dz = shape(r, th)
            p, n = hit_from((cx + dx, -2.0, cz + dz), (0, 1, 0), face_bvh)
            if p is None:
                return
            row.append(bm.verts.new(p + n * (lift + bulge * (1 - r * r))))
        grid.append(row)
    for j in range(segs):
        bm.faces.new((grid[0][0], grid[1][j], grid[1][(j + 1) % segs]))
    for i in range(1, rings):
        A, C = grid[i], grid[i + 1]
        for j in range(segs):
            bm.faces.new((A[j], C[j], C[(j + 1) % segs], A[(j + 1) % segs]))


def arc_strip(bm, cx, cz, shape, r_in, r_out, a0, a1, n=12, lift=0.004):
    """沿眼睛上緣的一條窄帶（上眼皮）：在輪廓 shape 的 r_in..r_out 之間、角度 a0..a1。"""
    rows = []
    for rr in (r_in, r_out):
        row = []
        for i in range(n + 1):
            th = math.radians(a0 + (a1 - a0) * i / n)
            dx, dz = shape(rr, th)
            p, nn = hit_from((cx + dx, -2.0, cz + dz), (0, 1, 0), face_bvh)
            if p is None:
                return
            row.append(bm.verts.new(p + nn * lift))
        rows.append(row)
    for i in range(n):
        bm.faces.new((rows[0][i], rows[0][i + 1], rows[1][i + 1], rows[1][i]))


def eye_shape(r, th):
    """圓潤直橢圓：上半略寬、下半微收。"""
    s, c = math.sin(th), math.cos(th)
    w = EYE_W * (1 + 0.10 * s) if s > 0 else EYE_W * (1 + 0.16 * s)
    if s > 0:   # 上緣略平（極淡的上眼皮定義）：上半用超橢圓
        cs = math.copysign(abs(c) ** 0.8, c)
        ss = s ** 0.8
        return r * w * cs, r * EYE_H * 0.97 * ss
    return r * w * c, r * EYE_H * 0.96 * s


eye_bm, brow_bm, mouth_bm, glint_bm, lid_bm = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
for sgn in (-1, 1):
    cx = sgn * EYE_X
    decal(eye_bm, cx, EYE_Z, eye_shape, lift=0.002, bulge=0.010)
    arc_strip(lid_bm, cx, EYE_Z, eye_shape, 0.86, 1.02, 22, 158, lift=0.007)   # 很柔的上眼皮定義（只是上緣一條略亮的帶）
    gp, gn = hit_from((cx - sgn * 0.012, -2.0, EYE_Z + 0.030), (0, 1, 0), face_bvh)   # 極小的柔和亮點（內上側）
    ellipsoid(glint_bm, gp + gn * 0.014, (0.006, 0.0035, 0.0075), gn.to_track_quat('Y', 'Z').to_matrix(), sub=2)
    # 上眼皮：沿眼睛上緣一道很細的新月，外眼角略長（極淡的眼皮定義）
    def lid(r, th, sgn=sgn):
        a = math.radians(18 + 144 * (th / (2 * math.pi)))
        rr = 0.965 + 0.06 * r
        dx = rr * EYE_W * (1 + 0.10 * math.sin(a)) * math.cos(a) * 1.04
        dz = rr * EYE_H * math.sin(a)
        if sgn * dx > 0:                        # 外眼角那一側往外延伸一點
            dx += sgn * 0.010 * (1 - math.sin(a))
        return dx, dz
    # 眉毛：短、柔、微彎，緊貼眼睛上方（外側略低，不是驚訝臉）
    def brow(r, th, sgn=sgn):
        u = math.cos(th)                        # -1..1 沿眉毛長度
        v = math.sin(th) * r
        dx = u * 0.060 * r + sgn * 0.004
        dz = EYE_H + 0.020 + 0.012 * (1 - u * u) - 0.011 * (sgn * u if sgn * u > 0 else 0) + v * 0.025 + (u * 0.060 * r) * math.tan(math.radians(2.0 if sgn > 0 else -0.5))   # 外側略低（放鬆）；左右差 2.5°
        return dx, dz
    decal(brow_bm, cx, EYE_Z, brow, rings=2, segs=20, lift=0.004)
# 嘴：極小、淺弧、緊接在鼻子下面
def mouth(r, th):
    u = math.cos(th)
    return u * 0.026 * r, -0.0045 * (1 - u * u) + math.sin(th) * r * 0.005
decal(mouth_bm, 0.0, 0.205, mouth, rings=2, segs=20, lift=0.003)
link("eyes", eye_bm, M["eye"], root)
link("eyelids", lid_bm, M["lid"], root)
link("eye_glints", glint_bm, M["glint"], root)
link("brows", brow_bm, M["brow"], root)
link("mouth", mouth_bm, M["mouth"], root)

# 耳朵（獨立物件，頭的網格不動）：小而圓、略微從頭側突出、稍微在臉平面之後、中心在眼睛到眼下之間；耳窩只用一個略深的小橢圓暗示
ear_bm, earin_bm = bmesh.new(), bmesh.new()
EAR_Z, EAR_Y = EYE_Z - 0.02, 0.09
for sgn in (-1, 1):
    p, n = hit_from((sgn * 2.0, EAR_Y, EAR_Z), (-sgn, 0, 0), face_bvh)        # 頭側表面
    c = p + Vector((sgn * 0.012, 0, 0))                                        # 一半埋在頭裡、一半突出
    rot = Matrix.Rotation(math.radians(sgn * 10), 3, 'Z') @ Matrix.Rotation(math.radians(-8), 3, 'X')
    ellipsoid(ear_bm, c, (0.040, 0.068, 0.092), rot)
    ellipsoid(earin_bm, c + Vector((sgn * 0.024, 0.004, -0.004)), (0.022, 0.040, 0.056), rot)
link("ears", ear_bm, M["skin"], root)
link("ear_inner", earin_bm, M["skin_shade"], root)


# ================================================================ 頭髮：SM_M_Head_s.04 原樣套上（只用等比縮放、平移、旋轉）
# 不改造型、不壓扁、不局部變形：來源的每一塊髮束都保持原本的形狀與相對位置。
HAIR_SRC = "/Users/a01-0220-0077/Downloads/Men Hair Set 04/Meshes/GLB/SM_M_Head_s.04.glb"
SKULL_C = Vector((0.0, 0.065, 0.607))   # Q 版頭殼中心（實測：x ±0.50、y -0.45..0.575、z 0..1.21）
SKULL_TOP = 1.213
HAIR_CLEAR = 0.035                      # 頭頂離頭皮的空隙
HAIR_PITCH = 6.0                        # 繞 X 軸往前傾一點：瀏海蓋到額頭約 4 成（度；正值＝前面往下）
HAIR_SHIFT = Vector((0.0, 0.02, 0.0))   # 整頂往後一點：後腦有份量、瀏海不壓到眼睛

before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=HAIR_SRC)
src = next(o for o in bpy.data.objects if o not in before and o.type == "MESH")
for o in [o for o in bpy.data.objects if o not in before and o is not src]:
    bpy.data.objects.remove(o)
hb = bmesh.new()
hb.from_mesh(src.data)
hb.transform(src.matrix_world)
bpy.data.objects.remove(src)

# 來源的頭皮殼（最大的一塊）決定來源頭的中心與半徑
hb.verts.ensure_lookup_table()
island = [-1] * len(hb.verts)
nid = 0
for v in hb.verts:
    if island[v.index] >= 0:
        continue
    st = [v]
    island[v.index] = nid
    while st:
        x = st.pop()
        for e in x.link_edges:
            w = e.other_vert(x)
            if island[w.index] < 0:
                island[w.index] = nid
                st.append(w)
    nid += 1
_cnt = {}
for i in island:
    _cnt[i] = _cnt.get(i, 0) + 1
CAP = max(_cnt, key=_cnt.get)
capP = [v.co for v in hb.verts if island[v.index] == CAP]
lo = Vector((min(p.x for p in capP), min(p.y for p in capP), min(p.z for p in capP)))
hi = Vector((max(p.x for p in capP), max(p.y for p in capP), max(p.z for p in capP)))
CAP_R = (hi.x - lo.x) / 2
C_SRC = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, hi.z - CAP_R))

# 等比縮放：讓頭皮殼的頂端剛好在 Q 版頭頂上方 HAIR_CLEAR（Q 版頭比寬高，所以兩側、前後自然多出空間＝髮量）
k = (SKULL_TOP + HAIR_CLEAR - SKULL_C.z) / (hi.z - C_SRC.z)
Mx = (Matrix.Translation(SKULL_C + HAIR_SHIFT) @ Matrix.Rotation(math.radians(HAIR_PITCH), 4, 'X')
      @ Matrix.Diagonal((k, k, k, 1.0)) @ Matrix.Translation(-C_SRC))
hb.transform(Mx)


# ---------------------------------------------------------------- 受控造型：每一塊髮束只做整塊的變換（沿頭皮縮放／旋轉／平移、尖端離開頭皮）
# 座標：以頭殼橢球正規化後的「方向 d（單位向量）＋ 徑向距離 nd（1 = 頭殼表面）」描述每個頂點；
# 一塊髮束的變換在它根部的切平面上進行（方位等距投影），所以縮放／旋轉是「沿著頭皮」的，髮束不會陷進頭裡也不會被壓扁。
SKR = HEAD_R


def to_sk(p):
    q = Vector(((p.x - SKULL_C.x) / SKR.x, (p.y - SKULL_C.y) / SKR.y, (p.z - SKULL_C.z) / SKR.z))
    return q.normalized(), q.length


def from_sk(d, nd):
    return SKULL_C + Vector((d.x * SKR.x * nd, d.y * SKR.y * nd, d.z * SKR.z * nd))


def az_el(d):
    return math.degrees(math.atan2(d.x, -d.y)), math.degrees(math.asin(max(-1.0, min(1.0, d.z))))


hb.verts.ensure_lookup_table()
groups = {}
for v in hb.verts:
    groups.setdefault(island[v.index], []).append(v)

# 同一塊髮束在來源裡是兩層（內外殼）：合併成一個單位一起動
LOCKS = [[0], [1, 2, 3, 4], [5, 6], [7, 8, 9, 10], [11, 12, 13], [14], [15, 16], [17, 18], [21, 22], [25, 26], [29, 30], [33, 34], [37, 38], [41, 42]]
STRANDS = [i for i in range(nid) if i != CAP and not any(i in g for g in LOCKS)]   # 髮際線上的小尖撮（3–4 個頂點）


def lock_frame(vs):
    """根部方向 r0、切平面基底 (e1 沿髮束方向, e2 垂直)、每個頂點的 2D 切平面座標與 nd。根 = 高的那一端（髮束從頭頂往下垂）。"""
    D = [to_sk(v.co) for v in vs]
    dirs = [d for d, _ in D]
    c = sum(dirs, Vector()).normalized()
    # 主軸：對切平面投影做 PCA（用最遠點對近似）
    far = max(dirs, key=lambda d: (d - c).length)
    far2 = max(dirs, key=lambda d: (d - far).length)
    a, b = (far, far2) if far.z > far2.z else (far2, far)
    if abs(a.z - b.z) < 0.12:                      # 幾乎水平的髮束：根 = 靠近中線（頭頂分線）那一端
        a, b = (a, b) if abs(a.x) < abs(b.x) else (b, a)
    r0 = a
    t = (b - r0 * r0.dot(b)).normalized()          # 根 → 尖的切線方向
    e1, e2 = t, r0.cross(t).normalized()
    coords = []
    for d, nd in D:
        phi = math.acos(max(-1.0, min(1.0, d.dot(r0))))
        w = d - r0 * d.dot(r0)
        if w.length < 1e-9:
            coords.append((0.0, 0.0, nd))
            continue
        w.normalize()
        coords.append((phi * w.dot(e1), phi * w.dot(e2), nd))
    return r0, e1, e2, coords


def apply_lock(vs, shorten=1.0, width=1.0, swing=0.0, lift=0.0, slide=(0.0, 0.0), curl=0.0, lift_pow=1.5):
    """shorten：沿髮束方向縮放（根不動）；width：垂直方向縮放；swing：繞根旋轉（度，+ = 從頭外看逆時針）；
    lift：尖端離開頭皮的量（nd 加成，隨根→尖漸增）；slide：整塊沿 (e1, e2) 平移（弧度）；curl：尖端額外往 e2 彎。"""
    r0, e1, e2, coords = lock_frame(vs)
    L = max(x for x, _, _ in coords) or 1e-6
    ca, sa = math.cos(math.radians(swing)), math.sin(math.radians(swing))
    for v, (x, y, nd) in zip(vs, coords):
        t = max(0.0, min(1.0, x / L))
        x2, y2 = x * shorten, y * width + curl * t * t
        x3, y3 = x2 * ca - y2 * sa + slide[0], x2 * sa + y2 * ca + slide[1]
        phi = math.hypot(x3, y3)
        if phi < 1e-9:
            d = r0.copy()
        else:
            w = (e1 * (x3 / phi) + e2 * (y3 / phi)).normalized()
            d = (r0 * math.cos(phi) + w * math.sin(phi)).normalized()
        v.co = from_sk(d, nd + lift * t ** lift_pow)


# 髮際線：頭皮殼（與小尖撮）下緣溫和往上收——側邊到耳朵下方一點、後面到後頸上方（脖子露出來）；曲線平滑，保留 Set 04 柔和圓潤的輪廓
def hairline_z(az):
    a = abs(az)
    pts = [(0, 0.62), (45, 0.52), (70, 0.37), (95, 0.33), (120, 0.30), (145, 0.26), (180, 0.23)]   # 側邊到耳下一點（不到下顎）、後面到後頸上方
    for (a0, z0), (a1, z1) in zip(pts, pts[1:]):
        if a0 <= a <= a1:
            z = z0 + (z1 - z0) * (a - a0) / (a1 - a0)
            break
    return z


def raise_hairline(vs):
    for v in vs:
        d, nd = to_sk(v.co)
        az, el = az_el(d)
        el_min = math.degrees(math.asin(max(-1.0, min(1.0, (hairline_z(az) - SKULL_C.z) / SKR.z))))
        if el < el_min:
            el2 = el_min - 5.0 * (1 - math.exp(-(el_min - el) / 8.0))
            a, e = math.radians(az), math.radians(el2)
            d2 = Vector((math.cos(e) * math.sin(a), -math.cos(e) * math.cos(a), math.sin(e)))
            v.co = from_sk(d2, nd)


raise_hairline(groups[CAP])
for i in STRANDS:
    raise_hairline(groups[i])

print("HAIR polish: Set 04 natural fit kept (uniform scale/move/rotate), cap hairline gently raised, no per-lock reshaping")

hair_me = bpy.data.meshes.new("hair")
hb.to_mesh(hair_me)
hb.free()
hair_me.materials.clear()
hair_me.materials.append(M["hair"])
for poly in hair_me.polygons:
    poly.use_smooth = True
hair_ob = bpy.data.objects.new("hair", hair_me)
bpy.context.scene.collection.objects.link(hair_ob)
hair_ob.parent = root
_sd = hair_ob.modifiers.new("Subdivision", "SUBSURF")   # 來源是低面數遊戲模型：細分 1 級讓面圓順（不改來源幾何）
_sd.levels = _sd.render_levels = 1
print("HAIR src=SM_M_Head_s.04 verts=%d islands=%d uniform_scale=%.4f pitch=%.1f (no local deformation)" % (len(hair_me.vertices), nid, k, HAIR_PITCH))


# ================================================================ 衣服殼

def is_hand(c):
    return arm_w(c) > 0.5 and arm_a(c) > LA - 0.015


# 內搭（米白）：貼身，從外套開口看得到
inner = shell(full, lambda c: -0.70 < c.z < -0.035 and arm_w(c) < 0.5, lambda co, n: 0.018)
link("inner_shirt", inner, M["cream"], root, subsurf=1)


def jacket_keep(c):
    if is_hand(c):
        return False
    if arm_w(c) > 0.5:
        return arm_a(c) < LA - 0.02          # 袖子到手腕
    return -0.74 < c.z < -0.045              # 軀幹：蓋過腰、到臀部上緣


def jacket_open(c):
    """前襟敞開：胸前中間一條（往上變寬），只開軀幹。"""
    return arm_w(c) < 0.5 and c.y < -0.05 and abs(c.x) < 0.050 + 0.07 * smoothstep(-0.40, -0.08, c.z)


def jacket_off(co, n):
    if arm_w(co) > 0.5:
        return 0.050 - 0.012 * smoothstep(LA * 0.6, LA, arm_a(co))      # 袖子有份量，往手腕略收
    return 0.060 - 0.028 * smoothstep(-0.12, -0.045, co.z)               # 鋪棉軀幹；領口貼近脖子


jk = shell(full, jacket_keep, jacket_off, delete_extra=jacket_open)
loops = boundary_loops(jk)
jacket_ob = link("jacket", jk, M["jacket"], root, subsurf=1, solid=0.012)
# 邊緣：靠手腕的環掃綠色袖口；其他（領口＋前襟＋下襬）掃橘色厚滾邊
trim, cuff = bmesh.new(), bmesh.new()
for lp in loops:
    c = sum(lp, Vector()) / len(lp)
    pts = smooth_loop(lp, 2)
    if abs(c.x) > 0.35:
        tube(cuff, pts, 0.034, k=10, closed=True)
    else:
        tube(trim, pts, 0.026, k=10, closed=True)
link("jacket_trim", trim, M["jacket"], root)
link("jacket_cuffs", cuff, M["trim"], root)

# 帽兜：米白色，圍在脖子後面與兩側，前面不接（敞開的領口看得到）
hood = bmesh.new()
angs = [math.radians(-125 + 250 * i / 10) for i in range(11)]
pts = [Vector((0.17 * math.sin(a), 0.03 + 0.16 * math.cos(a), -0.075 + 0.035 * math.cos(a))) for a in angs]
tube(hood, pts, [(0.075 + 0.035 * math.cos(a) ** 2, 0.06) for a in angs], k=12, side=(0, 0, 1))
ellipsoid(hood, (0.0, 0.215, -0.17), (0.20, 0.07, 0.13))        # 攤在背上的帽兜
link("hood", hood, M["cream"], root, subsurf=1)


# 褲子：寬鬆（往外推得多），往腳踝收；內側（兩腿之間）推得少，避免兩條褲管互相穿插
def pants_keep(c):
    return -1.19 < c.z < -0.60 and arm_w(c) < 0.5


def pants_off(co, n):
    base = 0.050 + 0.025 * smoothstep(-0.70, -0.92, co.z) - 0.035 * smoothstep(-0.98, -1.18, co.z)
    if co.z < -0.80:
        inward = max(0.0, -n.x * (1 if co.x >= 0 else -1))
        base *= 1 - 0.65 * inward
    return base


pt = shell(full, pants_keep, pants_off)
loops = boundary_loops(pt)
pants_ob = link("pants", pt, M["pants"], root, subsurf=1, solid=0.010)
cuffs = bmesh.new()
for lp in loops:
    c = sum(lp, Vector()) / len(lp)
    if c.z < -1.0:                                   # 褲腳：米白反摺
        tube(cuffs, [p + Vector((0, 0, -0.012)) for p in smooth_loop(lp, 2)], (0.040, 0.030), k=10, closed=True)
link("pants_cuffs", cuffs, M["cream"], root)

# 工裝口袋：大腿外側（射線打到褲子表面）
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
pev = pants_ob.evaluated_get(dg)
pbm = bmesh.new()
pbm.from_mesh(pev.to_mesh())
pev.to_mesh_clear()
pants_bvh = BVHTree.FromBMesh(pbm)
pk_bm = bmesh.new()
for s in (-1, 1):
    p, n = hit_from((s * 1.0, -0.03, -0.93), (-s, 0, 0), pants_bvh)
    if p:
        rot = n.to_track_quat('X', 'Z').to_matrix()
        rbox(pk_bm, p + n * 0.004, (0.036, 0.15, 0.15), rot, bevel=0.014)
        rbox(pk_bm, p + n * 0.014 + Vector((0, 0, 0.075)), (0.03, 0.16, 0.045), rot, bevel=0.012)   # 袋蓋
link("cargo_pockets", pk_bm, M["pants"], root, subsurf=1)
pbm.free()

# 襪子：靴口上方露出一小段米白
sock = shell(full, lambda c: -1.31 < c.z < -1.17 and arm_w(c) < 0.5, lambda co, n: 0.022)
link("socks", sock, M["cream"], root, subsurf=1)


# ================================================================ 靴子（每隻腳另外做，比光腳大很多）
boot, sole, lace = bmesh.new(), bmesh.new(), bmesh.new()
for s in (-1, 1):
    xc = s * 0.140
    # 鞋身：沿 -Y 放樣（腳跟 → 圓鞋頭），寬而高，看起來沉
    secs = [(0.17, -1.330, 0.125, 0.068), (0.09, -1.290, 0.142, 0.108), (-0.03, -1.285, 0.150, 0.112),
            (-0.15, -1.322, 0.152, 0.090), (-0.26, -1.345, 0.142, 0.068), (-0.34, -1.358, 0.112, 0.050), (-0.38, -1.368, 0.062, 0.032)]
    tube(boot, [(xc, y, z) for y, z, _, _ in secs], [(rw, rh) for _, _, rw, rh in secs], k=16, side=(1, 0, 0))
    # 靴筒：包住腳踝、上緣略外擴
    tube(boot, [(xc, 0.0, -1.36), (xc, 0.0, -1.30), (xc, -0.005, -1.25)], [(0.145, 0.138), (0.138, 0.132), (0.146, 0.140)], k=18, side=(1, 0, 0))
    tube(boot, [(xc, -0.005, -1.245), (xc, -0.005, -1.235)], [(0.153, 0.147)] * 2, k=18, side=(1, 0, 0))   # 靴口
    tube(sole, [(xc, y, -1.402) for y, _, _, _ in secs], [(rw + 0.020, 0.034) for _, _, rw, _ in secs], k=16, side=(1, 0, 0))   # 厚鞋底：沿鞋型外擴一圈
boot_bvh = BVHTree.FromBMesh(boot)
for s in (-1, 1):
    xc = s * 0.140
    for i, y in enumerate((-0.08, -0.15, -0.22)):                         # 簡化鞋帶：鞋面上三條橫槓
        p, n = hit_from((xc, y, -1.0), (0, 0, -1), boot_bvh)
        if p:
            rbox(lace, p + Vector((0, 0, 0.006)), (0.13 - 0.014 * i, 0.018, 0.016), bevel=0.006, seg=2)
link("boots", boot, M["boot"], root, subsurf=1)
link("soles", sole, M["sole"], root)
link("laces", lace, M["cream"], root)


# ================================================================ 背包
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
jev = jacket_ob.evaluated_get(dg)
jbm = bmesh.new()
jbm.from_mesh(jev.to_mesh())
jev.to_mesh_clear()
jacket_bvh = BVHTree.FromBMesh(jbm)
pack = bmesh.new()
pback, _ = hit_from((0, 2.0, -0.36), (0, -1, 0), jacket_bvh)
by = pback.y if pback else 0.26
rbox(pack, (0, by + 0.125, -0.40), (0.50, 0.23, 0.50), bevel=0.09)                         # 圓角主袋
rbox(pack, (0, by + 0.150, -0.165), (0.51, 0.22, 0.07), rot=Matrix.Rotation(math.radians(-8), 3, 'X'), bevel=0.03)   # 上蓋
rbox(pack, (0, by + 0.265, -0.47), (0.34, 0.08, 0.22), bevel=0.035)                        # 前口袋
rbox(pack, (0, by + 0.13, -0.115), (0.13, 0.03, 0.05), bevel=0.012)                       # 提把
# 肩帶：從背包上緣繞過肩膀、貼著外套表面到胸前
for s in (-1, 1):
    x = s * 0.16
    ctrl = [(x, by + 0.03, -0.22), (x, 0.22, -0.11), (x, 0.06, -0.05), (x, -0.12, -0.10), (x * 1.02, -0.22, -0.24), (x * 1.05, -0.22, -0.40), (x * 1.1, -0.18, -0.52)]
    path = []
    for c in ctrl:
        c = Vector(c)
        o = Vector((x * 0.5, 0.02, min(c.z, -0.10)))
        p, n = hit_from(o + (c - o).normalized() * 1.5, -(c - o), jacket_bvh)
        path.append(p + n * 0.012 if p else c)
    tube(pack, path, (0.045, 0.014), k=8, side=(1, 0, 0))
link("backpack", pack, M["pack"], root, subsurf=1)
patch = bmesh.new()
rbox(patch, (0, by + 0.308, -0.46), (0.05, 0.012, 0.05), rot=Matrix.Rotation(math.radians(45), 3, 'Y'), bevel=0.004, seg=1)
link("backpack_patch", patch, M["patch"], root)

full.free()
jbm.free()
print("DRESS parts=%d body_verts=%d (untouched)" % (len(root.children), len(body.data.vertices)))
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)

if OUT_GLB:
    # 匯出給 Godot：身體高度縮到 GAME_BODY_HEIGHT、正面轉到 +X（專案慣例）、腳底在 0
    k = GAME_BODY_HEIGHT / (1.213 - GROUND)
    root.scale = (k, k, k)
    root.rotation_euler = (0, 0, math.radians(90))
    root.location = (0, 0, -GROUND * k)
    bpy.ops.object.select_all(action="DESELECT")
    for o in [root] + list(root.children):
        o.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format="GLB", use_selection=True, export_apply=True)
    print("GLB", OUT_GLB)
