"""核定角色（乾淨的生產檔）：原始 Chibi_Base_Mesh2 + BunnyBite Base 03 + Bangs 08 + 簡單的風格化五官。
用法：Blender --background <Chibi_Base_Mesh2.blend> --python tools/chibi_character.py -- <out_prefix> [out.blend] [out.glb]
- 頭／身體：原始網格，頂點完全不動（腳本開頭與結尾各算一次頂點座標的雜湊值互相比對）
- 頭髮：Base 03、Bangs 08 原樣匯入，只有一個「移動＋縮放」的物件變換（同 tools/hairpack_fit.py），頂點資料不變
- 五官（依設定表 C）：分層的眼睛（虹膜、上半過渡、瞳孔、上緣眼皮、下緣、亮點）、細眉、小嘴，全是貼在頭表面的獨立物件；
  臉的柔和陰影做在皮膚材質裡（物件空間高斯斑），匯出 GLB 時烘成頂點色；鼻子用原始網格的小鼻頭加陰影暗示
  環境變數 CHR_VIEWS=face 只渲染臉的驗收視角
- 渲染：驗證頭（隱藏頭髮：正面、3/4、側面）＋ 臉的驗收（頭部特寫正面、3/4、側面；全身正面、3/4）
"""
import bpy, bmesh, sys, os, math, hashlib
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
OUT_BLEND = argv[1] if len(argv) > 1 and argv[1] != "-" else None
OUT_GLB = argv[2] if len(argv) > 2 and argv[2] != "-" else None
PACK = "/Users/a01-0220-0077/Downloads/Modular Men Hair Pack v.1/Meshes/GLB"
GROUND, TOP = -1.434, 1.213
GAME_BODY_HEIGHT = 1.10

head = bpy.data.objects.get("Chibi_Base_Mesh2") or next(o for o in bpy.data.objects if o.type == "MESH")


def vert_hash(ob):
    h = hashlib.sha256()
    for v in ob.data.vertices:
        h.update(("%.6f,%.6f,%.6f;" % tuple(v.co)).encode())
    return h.hexdigest()[:16]


HASH0 = vert_hash(head)
ws = [v.co.copy() for v in head.data.vertices]
print("HEAD verts=%d faces=%d hash=%s bbox x[%.3f,%.3f] y[%.3f,%.3f] z[%.3f,%.3f] (right half + Mirror)" % (
    len(head.data.vertices), len(head.data.polygons), HASH0, min(p.x for p in ws), max(p.x for p in ws), min(p.y for p in ws), max(p.y for p in ws), min(p.z for p in ws), max(p.z for p in ws)))


# 頭的網格鎖住（原始 Chibi_Base_Mesh2，一個頂點都不動）。zmap 保留為恆等，方便五官程式碼共用。
zmap = lambda z: z
HEAD_TOP = 1.213; FACE_HALF_W = 0.47


def mat(name, rgb, rough=0.9, spec=0.15):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = 0.0
    for key in ("Specular IOR Level", "Specular"):
        if key in b.inputs:
            b.inputs[key].default_value = spec; break
    return m


M = {
    "skin": mat("chr_skin", (0.88, 0.60, 0.44), 0.90),
    "hair": mat("chr_hair", (0.13, 0.067, 0.043), 0.85, 0.2),
}
for p in head.data.polygons:
    p.use_smooth = True                        # 著色；不改幾何
sd = head.modifiers.new("PreviewSubdiv", "SUBSURF"); sd.levels = sd.render_levels = 1
head.data.materials.clear(); head.data.materials.append(M["skin"])
root = bpy.data.objects.new("character_chibi_b", None)
bpy.context.scene.collection.objects.link(root)
head.parent = root

# ---------------------------------------------------------------- 頭髮（核定：Base 03 + Bangs 08；變換同 hairpack_fit.py）
C_V = Vector((0.0, 1.08, -0.25)); R_V = 7.72
C_C = Vector((0.0, 0.065, 0.607)); R_C = Vector((0.49, 0.51, 0.61))
S_XY = (R_C.x + 0.03) / R_V * 1.06; S_Z = (R_C.z + 0.03) / R_V * 0.97
M_FIT = Matrix.Translation(C_C) @ Matrix.Diagonal((S_XY, S_XY, S_Z, 1.0)) @ Matrix.Translation(-C_V)
hair_obs = []
for name in ("SM_Hair_Base_03_L", "SM_Hair_Bangs_08_L"):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(PACK, name + ".glb"))
    new = [o for o in bpy.data.objects if o not in before]
    ob = next(o for o in new if o.type == "MESH")
    for o in new:
        if o is not ob: bpy.data.objects.remove(o)
    ob.name = name
    ob.matrix_world = M_FIT @ ob.matrix_world
    ob.parent = root
    ob.matrix_parent_inverse = root.matrix_world.inverted()
    ob.data.materials.clear(); ob.data.materials.append(M["hair"])
    for p in ob.data.polygons: p.use_smooth = True
    hair_obs.append(ob)

# ---------------------------------------------------------------- 臉（貼在細分後頭表面的薄片）
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
ev = head.evaluated_get(dg)
fbm = bmesh.new(); fbm.from_mesh(ev.to_mesh()); ev.to_mesh_clear()
face_bvh = BVHTree.FromBMesh(fbm); fbm.free()


def hit(y_, z_, x_=None, direction=(0, 1, 0)):
    o = Vector((x_ if x_ is not None else y_, -2.0, z_)) if x_ is None else Vector((x_, y_, z_))
    h = face_bvh.ray_cast(o, Vector(direction).normalized())
    return h[0], h[1]


def front_hit(x, z):
    h = face_bvh.ray_cast(Vector((x, -2.0, z)), Vector((0, 1, 0)))
    return h[0], h[1]


def link(name, bm, m, smooth=True):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = smooth
    me.materials.append(m)
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o); o.parent = root
    return o


def ellipsoid(bm, c, r, rot=Matrix.Identity(3), sub=2):
    M4 = Matrix.Translation(Vector(c)) @ rot.to_4x4() @ Matrix.Diagonal((r[0], r[1], r[2], 1))
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0, matrix=M4)


def decal(bm, cx, cz, shape, rings=5, segs=28, lift=0.003, bulge=0.0):
    grid = []
    for i in range(rings + 1):
        r = i / rings; row = []
        for j in range(segs if i else 1):
            th = 2 * math.pi * j / segs
            dx, dz = shape(r, th)
            p, n = front_hit(cx + dx, cz + dz)
            if p is None: return
            row.append(bm.verts.new(p + n * (lift + bulge * (1 - r * r))))
        grid.append(row)
    for j in range(segs):
        bm.faces.new((grid[0][0], grid[1][j], grid[1][(j + 1) % segs]))
    for i in range(1, rings):
        A, C = grid[i], grid[i + 1]
        for j in range(segs):
            bm.faces.new((A[j], C[j], C[(j + 1) % segs], A[(j + 1) % segs]))


def arc_strip(bm, cx, cz, shape, r_in, r_out, a0, a1, n=12, lift=0.004):
    rows = []
    for rr in (r_in, r_out):
        row = []
        for i in range(n + 1):
            th = math.radians(a0 + (a1 - a0) * i / n)
            dx, dz = shape(rr, th)
            p, nn = front_hit(cx + dx, cz + dz)
            if p is None: return
            row.append(bm.verts.new(p + nn * lift))
        rows.append(row)
    for i in range(n):
        bm.faces.new((rows[0][i], rows[0][i + 1], rows[1][i + 1], rows[1][i]))


# ---------------------------------------------------------------- 臉（依「六款少年角色表情設定表」的 C 可愛日系風重做）
# 量自 C 的大臉（臉寬=1）：眼寬 0.16、眼高 0.19（高:寬≈1.2）、眼睛中心在下巴上方 43% 臉高、眉毛在眼睛上方約 0.4 眼高、
# 嘴寬≈0.7 眼寬、在眼睛下方 1.1 眼高；亮點兩眼都在畫面左上；上緣是深而粗的眼皮線，下緣是細而淺的邊。
# 鎖住的頭：臉寬 0.94（x ±0.47）、下巴 z=0 → 眼睛中心 z 0.41（偏低，不往額頭移）
def hex2lin(hexs):
    v = [int(hexs[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((c / 12.92) if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in v)


# 五官大修（對照原本 C 版：眼寬 +41%、眼高 +26% → 近圓 1:1.09；眼睛外移保留眼距；眉毛 0.19 寬 ≈ 眼寬的 90%；嘴 +20%）
FACE_DY = float(os.environ.get("CHR_FACE_DY", "0.027"))   # 整組五官（眼、眉、鼻、嘴）一起往上的位移：可見臉高（下巴 −0.042 → 髮際線 ≈0.86）的 3%
EYE_Z, EYE_X, EYE_H, EYE_W = 0.410 + FACE_DY, 0.240, 0.1053, 0.1008   # 眼睛「開口」：整體 −10%
IRIS_W, IRIS_H = 0.0662, 0.0880                             # 虹膜：跟著眼睛整體縮（寬 ×0.9；高 ×0.93 讓上下眼白維持很少）
IRIS_UP = -0.0035                                           # 虹膜中心：頂端藏在上眼皮下，底部留約 5% 眼高的眼白
IRIS_IN = 0.0108                                            # 虹膜靠向鼻側 → 鼻側眼白少、外側眼白多（×0.9）
PUPIL_KW, PUPIL_KH, PUPIL_UP = 0.62, 0.56, 0.0086           # 瞳孔：比例不變，跟著虹膜縮
BROW_BASE = 0.123 * 0.93 + 0.034 + 0.031                    # 眉毛上提 5%（以眉毛離下巴的高度 0.613 計 = +0.031）
MOUTH_Z = 0.153 + FACE_DY                                   # 嘴（跟著整組移動；相對鼻子的距離不變）
NOSE_Z = 0.287 + FACE_DY                                    # 鼻子暗示（跟著整組移動）
M.update({
    "iris": mat("chr_iris", (1.0, 1.0, 1.0), 0.55, 0.35),          # 虹膜：顏色來自頂點色的垂直漸層（下暖亮 → 中棕 → 上深，接到上緣），沒有同心環
    "pupil": mat("chr_pupil", hex2lin("2A1D18"), 0.5, 0.35),       # 大瞳孔
    "sclera": mat("chr_sclera", hex2lin("F1E6D6"), 0.7, 0.25),     # 眼白：暖象牙色，不是純白
    "sclera_sh": mat("chr_sclera_sh", hex2lin("DCCDBC"), 0.7, 0.25),   # 眼白上緣（上輪廓下的柔和陰影）
    "lid": mat("chr_lid", hex2lin("3A2820"), 0.8, 0.2),            # 外輪廓：深暖棕，不是黑
    "iris_rim": mat("chr_iris_rim", hex2lin("2A1D18"), 0.7, 0.2),  # 虹膜的細深色邊
    "lower": mat("chr_lower", hex2lin("BE9C88"), 0.85, 0.15),      # 下眼緣：更淺的暖棕、極細（幾乎只是暗示）
    "glint": mat("chr_glint", hex2lin("F6EEE2"), 0.6, 0.2),        # 暖柔白亮點
    "brow": mat("chr_brow", hex2lin("4A3528"), 0.9),               # 眉：細、柔、暖深棕
    "mouth": mat("chr_mouth", hex2lin("A8705C"), 0.9),             # 嘴：柔和的珊瑚棕（比眼睛低對比）
    "nose": mat("chr_nose", hex2lin("C4856A"), 0.9),               # 鼻子暗示：比皮膚暖、略深
})


_nt = M["iris"].node_tree; _vc = _nt.nodes.new("ShaderNodeVertexColor"); _vc.layer_name = "Col"
_nt.links.new(_vc.outputs["Color"], next(n for n in _nt.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"])


def lerp3(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def sstep(t):
    t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)


def color_iris(bm, cz, H_):
    """虹膜的頂點色：由下到上 暖亮 → 棕 → 深，最上面接到深色上緣；平滑，沒有環。"""
    lay = bm.verts.layers.float_color.new("Col")
    lo, base, up1, up2 = hex2lin("7E5B46"), hex2lin("6A4B3A"), hex2lin("4A352C"), hex2lin("3A2A22")
    for v in bm.verts:
        t = (v.co.z - (cz - H_)) / (2 * H_)
        if t < 0.36: c = lerp3(lo, base, sstep(t / 0.36))
        elif t < 0.64: c = lerp3(base, up1, sstep((t - 0.36) / 0.28))
        else: c = lerp3(up1, up2, sstep((t - 0.64) / 0.36))
        v[lay] = (*c, 1.0)


def link_vcol(name, bm, m):
    o = link(name, bm, m)
    o.data.color_attributes.active_color = o.data.color_attributes["Col"]
    return o


# 眼睛開口（依設定表 C）：柔和圓潤的直橢圓——一條連續的曲線，沒有角、沒有收尖；兩側飽滿、底部是寬的 U、上緣比下緣略平。
# 控制點以「內眼角在 +x」定義（x 以眼寬正規化；v>0 乘 0.838、v<0 乘 0.979 → 總高比上一版低 6%，寬不變）
EYE_OUTLINE = [(1.00, 0.00), (0.96, 0.35), (0.80, 0.68), (0.50, 0.90), (0.15, 1.00), (-0.25, 0.98), (-0.62, 0.82), (-0.90, 0.50),
               (-1.00, 0.05), (-0.92, -0.42), (-0.70, -0.76), (-0.35, -0.96), (0.05, -1.00), (0.45, -0.92), (0.78, -0.68), (0.96, -0.35)]
EYE_VTOP, EYE_VBOT = 0.817, 0.959                           # 上緣 0.086、下緣 −0.101：高/寬從 0.85 拉到 0.93，輪廓更接近正圓


def _closed_catmull(pts, per=24):
    n = len(pts); out = []
    for i in range(n):
        p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        for k in range(per):
            t = k / per; t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in range(2)))
    return out


def make_eye_shape(sgn):
    """回傳 shape(r, th) → (dx, dz)：極角 th 的方向上、r 倍輪廓半徑的點。輪廓是星形（以中心看每個角度只有一個半徑）。"""
    pts = [(-sgn * x * EYE_W, (v * EYE_VTOP if v > 0 else v * EYE_VBOT) * EYE_H) for x, v in EYE_OUTLINE]   # 內眼角朝鼻子：sgn>0 時在 -x
    curve = _closed_catmull(pts, 24)
    polar = sorted((math.atan2(z, x) % (2 * math.pi), math.hypot(x, z)) for x, z in curve)
    angs = [a for a, _ in polar]; rads = [r for _, r in polar]; n = len(polar)

    def radius(th):
        th = th % (2 * math.pi)
        import bisect
        i = bisect.bisect_left(angs, th)
        a0, r0 = (angs[i - 1], rads[i - 1]) if i > 0 else (angs[-1] - 2 * math.pi, rads[-1])
        a1, r1 = (angs[i], rads[i]) if i < n else (angs[0] + 2 * math.pi, rads[0])
        t = (th - a0) / (a1 - a0) if a1 > a0 else 0.0
        return r0 + (r1 - r0) * t

    def shape(r, th):
        R = radius(th)
        return r * R * math.cos(th), r * R * math.sin(th)
    return shape


def tube(bm, pts, radii, k=8):
    """沿點列掃圓截面（眼角小延伸用）。"""
    P = [Vector(p) for p in pts]; n = len(P); rings = []
    for i, p in enumerate(P):
        t = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized()
        sd = Vector((0, 1, 0)) if abs(t.y) < 0.9 else Vector((0, 0, 1))
        w = (sd - t * sd.dot(t)).normalized(); d = w.cross(t).normalized()
        r = radii[i] if isinstance(radii, list) else radii
        rings.append([bm.verts.new(p + w * (r * math.cos(2 * math.pi * j / k)) + d * (r * math.sin(2 * math.pi * j / k))) for j in range(k)])
    for i in range(n - 1):
        for j in range(k):
            bm.faces.new((rings[i][j], rings[i][(j + 1) % k], rings[i + 1][(j + 1) % k], rings[i + 1][j]))
    bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])


def contour(bm, cx, cz, shape, a0, a1, t_in, t_out, n=22, lift=0.005):
    """沿輪廓的帶：角度 a0..a1，t_in(u)/t_out(u) 回傳相對半徑（可變厚度）。"""
    rows = [[], []]
    for i in range(n + 1):
        u = i / n; th = math.radians(a0 + (a1 - a0) * u)
        for k, rr in enumerate((t_in(u), t_out(u))):
            dx, dz = shape(rr, th)
            p, nn = front_hit(cx + dx, cz + dz)
            if p is None: return
            rows[k].append(bm.verts.new(p + nn * lift))
    for i in range(n):
        bm.faces.new((rows[0][i], rows[0][i + 1], rows[1][i + 1], rows[1][i]))


sclera_bm, sclsh_bm, iris_bm, irisrim_bm, pupil_bm, lid_bm, lower_bm, glint_bm, brow_bm, mouth_bm, nose_bm = (bmesh.new() for _ in range(11))
for sgn in (-1, 1):
    cx = sgn * EYE_X
    shape = make_eye_shape(sgn)                                     # 開口（眼白邊界）：上緣柔和弧、完整張開、外眼角微微上揚
    W_, H_ = EYE_W, EYE_H
    # 中層：眼白
    decal(sclera_bm, cx, EYE_Z, shape, rings=6, segs=36, lift=0.002, bulge=0.003)
    arc_strip(sclsh_bm, cx, EYE_Z, shape, 0.86, 1.0, 20, 160, n=18, lift=0.0035)                               # 眼白上緣：上輪廓下方一點柔和陰影
    # 內層：大虹膜（直橢圓）＋ 瞳孔 ＋ 一個亮點。虹膜「裁切到開口」：頂端伸到開口外的部分不畫 → 看起來沒入上眼皮下，上方沒有眼白
    icx, icz = cx - sgn * IRIS_IN, EYE_Z + IRIS_UP
    def iris_raw(th):
        s_, c_ = math.sin(th), math.cos(th)
        return IRIS_W * c_ * (1 + 0.03 * s_), IRIS_H * s_
    def inside_open(px, pz):                                       # (px, pz) 相對眼睛中心
        R = math.hypot(*shape(1.0, math.atan2(pz, px)))
        return math.hypot(px, pz) <= R * 0.995
    def iris_clipped(r, th):
        dx, dz = iris_raw(th)
        ox_, oz_ = icx - cx, icz - EYE_Z
        lo_, hi_ = 0.0, 1.0
        if inside_open(ox_ + dx, oz_ + dz):
            lo_ = 1.0
        else:
            for _ in range(20):
                mid = (lo_ + hi_) / 2
                if inside_open(ox_ + mid * dx, oz_ + mid * dz): lo_ = mid
                else: hi_ = mid
        return r * lo_ * dx, r * lo_ * dz
    decal(iris_bm, icx, icz, iris_clipped, rings=8, segs=48, lift=0.0050, bulge=0.004)
    contour(irisrim_bm, icx, icz, iris_clipped, 0, 360, lambda u: 0.955, lambda u: 1.0, n=56, lift=0.0092)             # 虹膜細邊（頂端被裁掉的部分藏在眼皮下）
    def pupil(r, th):
        s_, c_ = math.sin(th), math.cos(th)
        return r * PUPIL_KW * IRIS_W * c_, r * PUPIL_KH * IRIS_H * s_
    decal(pupil_bm, icx, icz + PUPIL_UP, pupil, rings=4, segs=28, lift=0.0100, bulge=0.0020)
    gp, gn = front_hit(icx - 0.30 * IRIS_W, icz + PUPIL_UP + 0.30 * IRIS_H)                                    # 亮點：一個、畫面左上、小、略不規則
    rotg = gn.to_track_quat('Y', 'Z').to_matrix() @ Matrix.Rotation(math.radians(-22), 3, 'Y')
    ellipsoid(glint_bm, gp + gn * 0.016, (0.0104, 0.004, 0.0088), rotg)
    ellipsoid(glint_bm, gp + gn * 0.016 + Vector((0.0031, 0, 0.0031)), (0.0073, 0.004, 0.0065), rotg)
    # 上眼皮 = 主要的深色線：內眼角細 → 頂部中央到外側最厚 → 外眼角中等；壓在開口邊緣上一點（虹膜頂端沒入其下）；外眼角一小段略朝上的延伸
    a_in, a_out = (183, -3) if sgn > 0 else (-3, 183)              # u=0 內眼角 → 經過頂部 → u=1 外眼角
    def lid_t(u):
        return 0.035 + 0.110 * max(0.0, math.sin(math.pi * (0.0 + 0.85 * u))) ** 0.9     # 上眼皮份量 ≈ 下眼緣的 1.4 倍以上
    contour(lid_bm, cx, EYE_Z, shape, a_in, a_out, lambda u: 0.96, lambda u: 1.0 + lid_t(u), n=44, lift=0.0120)      # 內緣壓在虹膜頂端上
    th_o = math.radians(0.0 if sgn > 0 else 180.0)
    ox, oz = shape(1.0 + lid_t(1.0) * 0.5, th_o)
    ext = 0.025 * 2 * W_                                           # 約眼寬的 2.5%（只是眼皮的小收尾）
    pts = []
    for i in range(5):
        t = i / 4
        p, nn = front_hit(cx + ox + sgn * ext * t, EYE_Z + oz + 0.10 * ext * t); pts.append(p + nn * 0.0120)
    tube(lid_bm, pts, [lid_t(1.0) * W_ * 0.5 * (1 - t / 4) ** 0.8 + 0.0006 for t in range(5)], k=8)
    # 下眼緣 = 幾乎看不見：極細、很淺，底部中央最細（只是暗示），靠眼角略粗
    a0l, a1l = (-6, 186) if sgn < 0 else (186, -6)                 # 下半：從內眼角下方經過底部到外眼角下方（角度遞減方向與上半相反）
    a0l, a1l = ((354, 174) if sgn > 0 else (186, 366))
    def low_t(u):
        return 0.006 + 0.007 * (1 - math.sin(math.pi * u)) ** 1.5
    contour(lower_bm, cx, EYE_Z, shape, a0l, a1l, lambda u: 0.992, lambda u: 1.0 + low_t(u), n=28, lift=0.0090)

    def brow(r, th, sgn=sgn):                                                                                   # 眉：鎖住（大小、長度、位置都不變）
        u = math.cos(th); v = math.sin(th) * r
        L = 0.109                                                                                           # 寬度 +15%
        inner = (1 - sgn * u) / 2
        thick_b = 0.0115 * (0.62 + 0.38 * inner) * (1 - u * u) ** 0.3
        dx = u * L * r + sgn * 0.004
        dz = BROW_BASE + 0.024 * max(0.0, 1 - (u - 0.18 * sgn) ** 2) ** 1.3 + v * thick_b \
            + (u * L * r) * math.tan(math.radians(1.5 if sgn > 0 else -0.5))
        return dx, dz
    decal(brow_bm, cx, EYE_Z, brow, rings=2, segs=28, lift=0.004)
color_iris(iris_bm, EYE_Z + IRIS_UP, IRIS_H)   # 三個色階以整顆（含被遮住的頂端）計算


# 嘴：一條很細的微笑線（管狀，沒有填滿的內部）：半寬 0.076、半徑 0.0020（嘴角 0.0024）、很淺的 U 形
mpts, mrad = [], []
for i in range(25):
    u = -1 + 2 * i / 24
    p, nn = front_hit(u * 0.076, MOUTH_Z - 0.006 * (1 - u * u) ** 1.3 + 0.0026 * u * u)   # 半寬 0.076（比 C 的 0.053–0.062 略寬）；弧度跟著等比
    mpts.append(p + nn * 0.0035); mrad.append(0.0020 + 0.0004 * u * u)
tube(mouth_bm, mpts, mrad, k=8)


def nose(r, th):                                                                                                # 鼻子：很小但看得到的暖色弧（鼻頭下緣）
    u = math.cos(th)
    return u * 0.020 * r, 0.006 * (1 - u * u) + math.sin(th) * r * 0.0034
decal(nose_bm, 0.0, NOSE_Z, nose, rings=2, segs=16, lift=0.0035)
link("nose_hint", nose_bm, M["nose"])
link("eye_sclera", sclera_bm, M["sclera"]); link("eye_sclera_shade", sclsh_bm, M["sclera_sh"])
link_vcol("eye_iris", iris_bm, M["iris"]); link("eye_iris_rim", irisrim_bm, M["iris_rim"]); link("eye_pupil", pupil_bm, M["pupil"])
link("eye_contour_upper", lid_bm, M["lid"]); link("eye_contour_lower", lower_bm, M["lower"])
link("eye_glints", glint_bm, M["glint"]); link("brows", brow_bm, M["brow"]); link("mouth", mouth_bm, M["mouth"])

# 臉的柔和陰影：做在皮膚「材質」裡（物件空間的高斯斑，只影響臉的正面），頭的網格完全不動；沒有腮紅圓圈
SKIN_BASE = (0.88, 0.60, 0.44)
SHADE_BLOBS = [  # (x, z, sx, sz, 強度, 線性顏色) — x 會自動鏡像；全部很寬很柔，不是腮紅圓圈、不是黑眼圈
    (0.240, 0.552 + FACE_DY, 0.11, 0.026, 0.26, (0.70, 0.43, 0.30)),   # 上緣接觸陰影：深色上緣跟臉接合的地方（很窄的一條暖影）
    (0.240, 0.590 + FACE_DY, 0.14, 0.060, 0.14, (0.76, 0.48, 0.34)),   # 眼睛上方的柔和過渡
    (0.240, 0.268 + FACE_DY, 0.13, 0.045, 0.16, (0.80, 0.50, 0.37)),   # 眼睛下方：淡淡的暖影
    (0.000, 0.272 + FACE_DY, 0.045, 0.024, 0.40, (0.74, 0.46, 0.33)),  # 鼻頭下方（讓鼻子更能讀出來）
    (0.055, 0.316 + FACE_DY, 0.030, 0.046, 0.26, (0.78, 0.50, 0.36)),  # 鼻翼兩側
    (0.300, 0.290, 0.16, 0.11, 0.22, (0.93, 0.56, 0.43)),    # 上臉頰：寬而淡的暖色（比額頭中央暖）
]


def build_face_shading(m, blobs):
    nt = m.node_tree; nodes = nt.nodes; links = nt.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    tc = nodes.new("ShaderNodeTexCoord"); sep = nodes.new("ShaderNodeSeparateXYZ"); links.new(tc.outputs["Object"], sep.inputs[0])
    gate = nodes.new("ShaderNodeMapRange"); gate.interpolation_type = "SMOOTHSTEP"
    gate.inputs["From Min"].default_value = 0.10; gate.inputs["From Max"].default_value = -0.25     # 只有臉的正面（y<0）
    links.new(sep.outputs["Y"], gate.inputs["Value"])

    def mth(op, a, b=None):
        n = nodes.new("ShaderNodeMath"); n.operation = op
        if isinstance(a, (int, float)): n.inputs[0].default_value = a
        else: links.new(a, n.inputs[0])
        if b is not None:
            if isinstance(b, (int, float)): n.inputs[1].default_value = b
            else: links.new(b, n.inputs[1])
        return n.outputs[0]
    rgb = nodes.new("ShaderNodeRGB"); rgb.outputs[0].default_value = (*SKIN_BASE, 1); col = rgb.outputs[0]
    for bx, bz, sx, sz, k, c in blobs:
        fac = None
        for mx in ((bx, -bx) if bx > 1e-6 else (bx,)):
            dx = mth("DIVIDE", mth("SUBTRACT", sep.outputs["X"], mx), sx)
            dz = mth("DIVIDE", mth("SUBTRACT", sep.outputs["Z"], bz), sz)
            e = mth("EXPONENT", mth("MULTIPLY", mth("ADD", mth("MULTIPLY", dx, dx), mth("MULTIPLY", dz, dz)), -0.5))
            fac = e if fac is None else mth("ADD", fac, e)
        fac = mth("MULTIPLY", mth("MULTIPLY", fac, k), gate.outputs[0])
        mix = nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MIX"
        links.new(fac, mix.inputs["Factor"]); links.new(col, mix.inputs[6]); mix.inputs[7].default_value = (*c, 1)
        col = mix.outputs[2]
    links.new(col, bsdf.inputs["Base Color"])


def shade_color(co):
    """同一組陰影的 Python 版（匯出 GLB 時烘成頂點色用）。"""
    col = Vector(SKIN_BASE)
    t = max(0.0, min(1.0, (co.y - 0.10) / (-0.25 - 0.10))); gate = t * t * (3 - 2 * t)
    for bx, bz, sx, sz, k, c in SHADE_BLOBS:
        f = sum(math.exp(-0.5 * (((co.x - mx) / sx) ** 2 + ((co.z - bz) / sz) ** 2)) for mx in ((bx, -bx) if bx > 1e-6 else (bx,)))
        col = col.lerp(Vector(c), min(1.0, f * k * gate))
    return col


build_face_shading(M["skin"], SHADE_BLOBS)
print("FACE C: eye half %.3f x %.3f (h:w=%.2f) center z=%.3f spacing=%.3f; brows/mouth/shading rebuilt" % (EYE_W, EYE_H, EYE_H / EYE_W, EYE_Z, EYE_X))

HASH1 = vert_hash(head)
print("HEAD hash after=%s  unchanged=%s" % (HASH1, HASH0 == HASH1))


# ================================================================ 服裝（五件獨立物件；全部從鎖住的身體表面「往外」長出來，身體不動）
# 米白連帽內搭 #F5EBD7、橘色短外套 #E67E3A、橄欖工裝短褲 #7A8A5B、棕色厚底登山靴 #6B5139（鞋底米褐）、深棕小背包 #3E3328
def srgb(hexs):
    v = [int(hexs[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((c / 12.92) if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in v)


M.update({
    "cream": mat("chr_cream", srgb("F5EBD7"), 0.9),
    "jacket": mat("chr_jacket", srgb("E67E3A"), 0.88),
    "jacket_dk": mat("chr_jacket_dk", srgb("C8682C"), 0.88),     # 滾邊／袖口／下襬：同色系略深，讀成厚度
    "patch": mat("chr_patch", srgb("4A3A2E"), 0.9),
    "pants": mat("chr_pants", srgb("7A8A5B"), 0.9),
    "pants_dk": mat("chr_pants_dk", srgb("66744B"), 0.9),        # 腰帶
    "boot": mat("chr_boot", srgb("6B5139"), 0.85),
    "boot_dk": mat("chr_boot_dk", srgb("5A4330"), 0.85),         # 鞋頭／鞋面分塊
    "sole": mat("chr_sole", srgb("C9B48C"), 0.9),
    "pack": mat("chr_pack", srgb("3E3328"), 0.9),
})


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def link_g(name, bm, m, subsurf=0, solid=0.0):
    o = link(name, bm, m)
    if solid:
        s_ = o.modifiers.new("Solidify", "SOLIDIFY"); s_.thickness = solid; s_.offset = -1.0; s_.use_rim = True
    if subsurf:
        d_ = o.modifiers.new("Subdivision", "SUBSURF"); d_.levels = d_.render_levels = subsurf
    return o


def rbox(bm, c, size, rot=Matrix.Identity(3), bevel=0.0, seg=3):
    M4 = Matrix.Translation(Vector(c)) @ rot.to_4x4() @ Matrix.Diagonal((size[0], size[1], size[2], 1))
    r = bmesh.ops.create_cube(bm, size=1.0, matrix=M4)
    if bevel > 0:
        es = list({e for v in r["verts"] for e in v.link_edges})
        bmesh.ops.bevel(bm, geom=es, offset=bevel, segments=seg, affect='EDGES', profile=0.5)


def tube(bm, pts, radii, k=10, closed=False, cap=True, side=None):
    P = [Vector(p) for p in pts]; n = len(P); rings = []
    for i, p in enumerate(P):
        t = (P[(i + 1) % n] - P[(i - 1) % n]).normalized() if closed else (P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized()
        sd = Vector(side[i] if isinstance(side, list) else (side or (0, 0, 1)))
        if sd.length < 1e-6 or abs(sd.normalized().dot(t)) > 0.95:
            sd = Vector((1, 0, 0)) if abs(t.x) < 0.9 else Vector((0, 1, 0))
        w = (sd - t * sd.dot(t)).normalized(); d = w.cross(t).normalized()
        r = radii[i] if isinstance(radii, list) else radii
        rw, rd = r if isinstance(r, tuple) else (r, r)
        rings.append([bm.verts.new(p + w * (rw * math.cos(2 * math.pi * j / k)) + d * (rd * math.sin(2 * math.pi * j / k))) for j in range(k)])
    for i in range(n if closed else n - 1):
        A, C = rings[i], rings[(i + 1) % n]
        for j in range(k):
            bm.faces.new((A[j], A[(j + 1) % k], C[(j + 1) % k], C[j]))
    if cap and not closed:
        bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])


def boundary_loops(bm):
    adj = {}
    for e in bm.edges:
        if e.is_boundary:
            a, b = e.verts; adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
    seen, loops = set(), []
    for start in adj:
        if start in seen: continue
        loop, prev, cur = [start], None, start; seen.add(start)
        while True:
            nxt = [v for v in adj[cur] if v is not prev and v not in seen]
            if not nxt: break
            prev, cur = cur, nxt[0]; loop.append(cur); seen.add(cur)
        if len(loop) > 4: loops.append([v.co.copy() for v in loop])
    return loops


def smooth_loop(pts, it=3):
    for _ in range(it):
        n = len(pts); pts = [(pts[(i - 1) % n] + pts[i] * 2 + pts[(i + 1) % n]) / 4 for i in range(n)]
    return pts


# 身體地標（原始座標）：肩關節、腕；腋下分界線
S_ = Vector((0.27, 0.04, -0.17)); W_ = Vector((0.51, 0.04, -0.55)); AX = (W_ - S_).normalized(); LA = (W_ - S_).length


def arm_w(p):
    x = abs(p.x)
    if p.z > -0.06: return 0.0
    lo = smoothstep(-0.25, -0.35, p.z)
    width = 0.03 + (0.008 - 0.03) * lo
    line = 0.19 + (-0.08 - p.z) * 0.3235 - 0.02 * lo
    return smoothstep(-width, width, x - line)


def arm_a(p):
    return (Vector((abs(p.x), p.y, p.z)) - S_).dot(AX)


# 完整身體（只套 Mirror，不細分）：衣服殼的來源
sd.show_viewport = sd.show_render = False
bpy.context.view_layer.update()
ev = head.evaluated_get(bpy.context.evaluated_depsgraph_get())
full = bmesh.new(); full.from_mesh(ev.to_mesh()); ev.to_mesh_clear()
sd.show_viewport = sd.show_render = True
full.normal_update(); full.verts.ensure_lookup_table()
lay_idx = full.verts.layers.int.new("orig_idx")


def shell(keep, offset, delete_extra=None):
    bm = full.copy(); bm.normal_update(); bm.verts.ensure_lookup_table()
    nrm = [v.normal.copy() for v in bm.verts]
    lay = bm.verts.layers.int["orig_idx"]
    for v in bm.verts: v[lay] = v.index
    kill = [f for f in bm.faces if not keep(f.calc_center_median()) or (delete_extra and delete_extra(f.calc_center_median()))]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    for v in bm.verts:
        n = nrm[v[lay]]; v.co += n * offset(v.co, n)
    return bm


def bvh_of(ob):
    bpy.context.view_layer.update()
    e = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    b = bmesh.new(); b.from_mesh(e.to_mesh()); e.to_mesh_clear(); t = BVHTree.FromBMesh(b); b.free(); return t


def ray(bvh, o, d):
    h = bvh.ray_cast(Vector(o), Vector(d).normalized()); return h[0], h[1]


def is_hand(c):
    return arm_w(c) > 0.5 and arm_a(c) > LA - 0.015


# ---- 1. 米白連帽內搭：貼身殼（外套敞開處看得到）＋ 小帽兜
inner = shell(lambda c: -0.72 < c.z < -0.035 and arm_w(c) < 0.5, lambda co, n: 0.018)
link_g("inner_hoodie", inner, M["cream"], subsurf=1)
hood = bmesh.new()
angs = [math.radians(-120 + 240 * i / 10) for i in range(11)]
pts = [Vector((0.15 * math.sin(a), 0.03 + 0.14 * math.cos(a), -0.08 + 0.03 * math.cos(a))) for a in angs]
tube(hood, pts, [(0.055 + 0.025 * math.cos(a) ** 2, 0.045) for a in angs], k=12, side=(0, 0, 1))   # 繞在後頸的帽兜邊
ellipsoid(hood, (0.0, 0.20, -0.18), (0.15, 0.06, 0.10), Matrix.Identity(3), sub=3)                     # 攤在上背的小帽兜
link_g("hood", hood, M["cream"], subsurf=1)


# ---- 2. 橘色短外套：鋪棉厚殼、前襟敞開、滾邊有厚度、袖子寬鬆但手露出
def jacket_keep(c):
    if is_hand(c): return False
    if arm_w(c) > 0.5: return arm_a(c) < LA - 0.02
    return -0.70 < c.z < -0.045


def jacket_open(c):
    return arm_w(c) < 0.5 and c.y < -0.05 and abs(c.x) < 0.050 + 0.07 * smoothstep(-0.40, -0.08, c.z)


def jacket_off(co, n):
    if arm_w(co) > 0.5:
        return 0.052 - 0.010 * smoothstep(LA * 0.6, LA, arm_a(co))
    return 0.062 - 0.028 * smoothstep(-0.12, -0.045, co.z)


jk = shell(jacket_keep, jacket_off, delete_extra=jacket_open)
jk_loops = boundary_loops(jk)
jacket_ob = link_g("jacket", jk, M["jacket"], subsurf=1, solid=0.014)
trim, cuff = bmesh.new(), bmesh.new()
for lp in jk_loops:
    c = sum(lp, Vector()) / len(lp); pts = smooth_loop(lp, 2)
    if abs(c.x) > 0.35: tube(cuff, pts, 0.034, k=10, closed=True)         # 袖口
    else: tube(trim, pts, 0.026, k=10, closed=True)                        # 領口＋前襟＋下襬
link_g("jacket_trim", trim, M["jacket_dk"]); link_g("jacket_cuffs", cuff, M["jacket_dk"])
jbvh = bvh_of(jacket_ob)
pk = bmesh.new()
for s in (-1, 1):                                                          # 兩個簡單口袋（下襬上方）
    p, n = ray(jbvh, (s * 0.17, -2.0, -0.57), (0, 1, 0))
    if p:
        rbox(pk, p + n * 0.008, (0.13, 0.024, 0.10), n.to_track_quat('Y', 'Z').to_matrix(), bevel=0.012)
link_g("jacket_pockets", pk, M["jacket"], subsurf=1)
patch = bmesh.new()
p, n = ray(jbvh, (2.0, 0.02, -0.30), (-1, 0, 0))                           # 右上臂一塊小深色布章
if p:
    rbox(patch, p + n * 0.004, (0.012, 0.07, 0.07), n.to_track_quat('X', 'Z').to_matrix(), bevel=0.01)
link_g("jacket_patch", patch, M["patch"])


# ---- 3. 橄欖工裝短褲：寬鬆（大腿更寬）、往腳踝收、腰帶、大而簡單的側袋
def pants_off(co, n):
    base = 0.052 + 0.028 * smoothstep(-0.70, -0.92, co.z) - 0.036 * smoothstep(-0.98, -1.14, co.z)
    if co.z < -0.80:
        inward = max(0.0, -n.x * (1 if co.x >= 0 else -1)); base *= 1 - 0.65 * inward
    return base


pt = shell(lambda c: -1.14 < c.z < -0.60 and arm_w(c) < 0.5, pants_off)
pt_loops = boundary_loops(pt)
pants_ob = link_g("pants", pt, M["pants"], subsurf=1, solid=0.010)
band = bmesh.new()
for lp in pt_loops:
    c = sum(lp, Vector()) / len(lp)
    if c.z > -0.70: tube(band, smooth_loop(lp, 2), (0.022, 0.030), k=10, closed=True)   # 腰帶
link_g("waistband", band, M["pants_dk"])
pbvh = bvh_of(pants_ob)
cp = bmesh.new()
for s in (-1, 1):                                                          # 大腿外側工裝口袋＋袋蓋
    p, n = ray(pbvh, (s * 2.0, -0.03, -0.93), (-s, 0, 0))
    if p:
        rot = n.to_track_quat('X', 'Z').to_matrix()
        rbox(cp, p + n * 0.006, (0.036, 0.16, 0.16), rot, bevel=0.014)
        rbox(cp, p + n * 0.016 + Vector((0, 0, 0.08)), (0.03, 0.17, 0.05), rot, bevel=0.012)
link_g("cargo_pockets", cp, M["pants"], subsurf=1)


# ---- 4. 厚底登山靴：寬鞋頭、厚鞋底、靴筒略高（蓋住褲腳）、簡單鞋面分塊、極簡鞋帶
boot, cap_, sole, lace = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
for s in (-1, 1):
    xc = s * 0.142
    secs = [(0.17, -1.330, 0.128, 0.070), (0.09, -1.285, 0.146, 0.112), (-0.03, -1.280, 0.154, 0.116),
            (-0.15, -1.315, 0.156, 0.094), (-0.26, -1.340, 0.146, 0.072), (-0.34, -1.355, 0.116, 0.052), (-0.38, -1.365, 0.064, 0.034)]
    tube(boot, [(xc, y, z) for y, z, _, _ in secs], [(rw, rh) for _, _, rw, rh in secs], k=16, side=(1, 0, 0))
    tube(boot, [(xc, 0.0, -1.36), (xc, 0.0, -1.28), (xc, -0.005, -1.20), (xc, -0.008, -1.10)],
         [(0.150, 0.142), (0.142, 0.136), (0.140, 0.134), (0.148, 0.142)], k=18, side=(1, 0, 0))                  # 靴筒到褲腳
    tube(boot, [(xc, -0.008, -1.105), (xc, -0.008, -1.095)], [(0.156, 0.150)] * 2, k=18, side=(1, 0, 0))     # 靴口
    tube(sole, [(xc, y, -1.400) for y, _, _, _ in secs], [(rw + 0.022, 0.036) for _, _, rw, _ in secs], k=16, side=(1, 0, 0))   # 厚鞋底
    tube(cap_, [(xc, y, z + 0.006) for y, z, _, _ in secs[-3:]], [(rw + 0.004, rh + 0.004) for _, _, rw, rh in secs[-3:]], k=16, side=(1, 0, 0))   # 鞋頭分塊
bbvh = BVHTree.FromBMesh(boot)
for s in (-1, 1):
    for i, y in enumerate((-0.10, -0.17)):                                 # 兩條鞋帶橫槓
        p, n = ray(bbvh, (s * 0.142, y, -1.0), (0, 0, -1))
        if p: rbox(lace, p + Vector((0, 0, 0.006)), (0.13 - 0.012 * i, 0.02, 0.016), bevel=0.006, seg=2)
link_g("boots", boot, M["boot"], subsurf=1); link_g("boot_toecaps", cap_, M["boot_dk"], subsurf=1)
link_g("soles", sole, M["sole"]); link_g("laces", lace, M["cream"])


# ---- 5. 深棕小背包：緊湊的圓角方體、上蓋、前袋、兩條肩帶貼著外套
pack = bmesh.new()
pb, _ = ray(jbvh, (0, 2.0, -0.36), (0, -1, 0)); by = pb.y if pb else 0.26
rbox(pack, (0, by + 0.105, -0.38), (0.40, 0.19, 0.42), bevel=0.07)
rbox(pack, (0, by + 0.125, -0.185), (0.41, 0.19, 0.06), rot=Matrix.Rotation(math.radians(-8), 3, 'X'), bevel=0.028)
rbox(pack, (0, by + 0.225, -0.44), (0.27, 0.07, 0.18), bevel=0.03)
rbox(pack, (0, by + 0.11, -0.145), (0.11, 0.03, 0.045), bevel=0.012)
for s in (-1, 1):
    x = s * 0.15
    ctrl = [(x, by + 0.02, -0.24), (x, 0.22, -0.12), (x, 0.06, -0.06), (x, -0.12, -0.11), (x * 1.02, -0.22, -0.25), (x * 1.05, -0.22, -0.40), (x * 1.1, -0.18, -0.52)]
    path = []
    for c in ctrl:
        c = Vector(c); o = Vector((x * 0.5, 0.02, min(c.z, -0.10)))
        p, n = ray(jbvh, o + (c - o).normalized() * 1.5, -(c - o))
        path.append(p + n * 0.012 if p else c)
    tube(pack, path, (0.042, 0.013), k=8, side=(1, 0, 0))
link_g("backpack", pack, M["pack"], subsurf=1)
full.free()
print("OUTFIT parts=%d (all separate objects; body untouched)" % len([o for o in root.children if o.type == "MESH"]))

# ---------------------------------------------------------------- 渲染
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
sc.view_settings.view_transform = "Standard"; sc.render.resolution_x = sc.render.resolution_y = 900
cam = bpy.data.objects.new("C", bpy.data.cameras.new("C")); sc.collection.objects.link(cam); sc.camera = cam


def shoot(name, ctr, d, ortho_scale=None, dist=6.0):
    d = Vector(d).normalized()
    if ortho_scale: cam.data.type = "ORTHO"; cam.data.ortho_scale = ortho_scale; cam.location = ctr + d * dist
    else: cam.data.type = "PERSP"; cam.data.lens = 85; cam.location = ctr + d * dist
    cam.rotation_euler = (ctr - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = "%s_%s.png" % (OUT, name); bpy.ops.render.render(write_still=True)


HC = Vector((0.0, 0.06, 0.62)); Q34 = (0.57, -0.80, 0.12)
UC = Vector((0.0, 0.05, 0.25)); BC = Vector((0.0, 0.05, -0.08))
FACE_NAMES = ("eye_sclera", "eye_sclera_shade", "eye_iris", "eye_iris_rim", "eye_pupil", "eye_contour_upper", "eye_contour_lower", "eye_glints", "brows", "mouth", "nose_hint")
VIEWS = os.environ.get("CHR_VIEWS", "outfit")
if VIEWS == "front":
    shoot("head_front", HC, (0, -1, 0), 1.6)
elif VIEWS == "head":
    import json
    from bpy_extras.object_utils import world_to_camera_view as w2c
    hair_top = max((o.matrix_world @ v.co).z for o in hair_obs for v in o.data.vertices)
    def surf(z):   # 臉中線在高度 z 的表面點
        h = face_bvh.ray_cast(Vector((0, -2.0, z)), Vector((0, 1, 0))); return h[0] if h[0] else Vector((0, -0.4, z))
    chin = min(v.co.z for v in head.data.vertices if v.co.y < -0.12 and v.co.z > -0.1)
    LM = {"top": Vector((0, 0.06, hair_top)), "eye": surf(EYE_Z), "nose": surf(zmap(0.285)), "mouth": surf(MOUTH_Z), "chin": Vector((0, -0.25, chin))}
    out = {"face_half_w": FACE_HALF_W, "head_top": HEAD_TOP, "eye_z": EYE_Z, "chin": chin, "views": {}}
    for name, d, osc, dist in (("head_front", (0, -1, 0), 1.6, 6), ("head_q34", Q34, None, 4.7), ("head_side", (1, 0, 0), 1.6, 6)):
        shoot(name, HC, d, osc, dist)
        out["views"][name] = {k: round((1 - w2c(sc, cam, p).y) * 900) for k, p in LM.items()}
        if osc:   # 正交：臉寬（像素）
            out["views"][name]["face_w_px"] = round(2 * FACE_HALF_W / osc * 900)
    json.dump(out, open(OUT + "_landmarks.json", "w"))
elif VIEWS in ("eyes", "face"):
    shoot("head_front", HC, (0, -1, 0), 1.6); shoot("head_q34", HC, Q34, None, 4.7); shoot("head_side", HC, (1, 0, 0), 1.6); shoot("body_front", BC, (0, -1, 0), 3.1, 8)
else:
    # 服裝驗收：上半身四視角、全身正面
    shoot("up_front", UC, (0, -1, 0), 2.4, 8); shoot("up_q34", UC, Q34, None, 6.6); shoot("up_side", UC, (1, 0, 0), 2.4, 8); shoot("up_back", UC, (0, 1, 0), 2.4, 8)
    shoot("body_front", BC, (0, -1, 0), 3.1, 8)
    # 純服裝：隱藏身體、頭髮、五官，確認衣服是獨立的幾何
    for o in [head] + hair_obs + [o for o in root.children if o.name in FACE_NAMES]: o.hide_render = True
    shoot("outfit_front", BC, (0, -1, 0), 3.1, 8); shoot("outfit_q34", BC, Q34, None, 8.6)
    for o in bpy.data.objects: o.hide_render = False
if OUT_BLEND:
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
if OUT_GLB:
    k = GAME_BODY_HEIGHT / (TOP - GROUND)
    root.scale = (k, k, k); root.rotation_euler = (0, 0, math.radians(90)); root.location = (0, 0, -GROUND * k)
    bpy.ops.object.select_all(action="DESELECT")
    for o in [root] + list(root.children): o.select_set(True)
    bpy.context.view_layer.objects.active = root
    # 臉的陰影在 Blender 是材質節點，glTF 帶不走 → 烘成頂點色（相對皮膚底色的倍率）。.blend 已經先存好，頭的 mesh 資料在檔案裡仍是乾淨的
    ca = head.data.color_attributes.new("FaceShade", "FLOAT_COLOR", "POINT")
    for v in head.data.vertices:
        c = shade_color(v.co); ca.data[v.index].color = (c.x / SKIN_BASE[0], c.y / SKIN_BASE[1], c.z / SKIN_BASE[2], 1.0)
    head.data.color_attributes.active_color = ca
    # glTF 匯不出程序式的 Base Color 連線（會變成白色）→ 匯出前把皮膚材質的底色改回固定值；陰影由上面的頂點色提供
    _nt = M["skin"].node_tree; _bsdf = next(n for n in _nt.nodes if n.type == "BSDF_PRINCIPLED")
    for lk in list(_nt.links):
        if lk.to_socket == _bsdf.inputs["Base Color"]: _nt.links.remove(lk)
    _bsdf.inputs["Base Color"].default_value = (*SKIN_BASE, 1)
    bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format="GLB", use_selection=True, export_apply=True, export_vertex_color="ACTIVE")
    print("GLB", OUT_GLB)
print("CHARACTER done")
