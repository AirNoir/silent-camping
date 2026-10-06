"""主角基礎模型（在 Blender 內使用）：依「森林露營角色設定板」的男主角——亂翹的大塊棕髮、橘色連帽外套敞開露出米白內搭、
橄欖綠工裝褲、米白反摺襪、厚底棕色短靴、深色後背包。只做 base mesh：不綁骨、不動畫、純色霧面材質。
- 比例：頭高 0.30 m、全高 1.35 m = 4.5 頭身（設定板本身約 3 頭身，需求寫 4.5–5，取最接近設定板的 4.5）
- 身體：一個連續的 mesh。關節骨架（肩、肘、腕、骨盆、髖、膝、踝、頸都是節點，中間再插節點）用 Skin modifier 長肉、
  Subdivision 2 細分 → 全四邊面，每個節點都是一圈 edge loop，關節處有足夠的環可以彎；四肢從根部往末端逐段收細
- 衣服：以「面最靠近哪一段骨頭＋高度」分材質區（外套／內搭／褲子／襪子／靴子／手），交界處再套一圈剛體配件（袖口、下襬、褲腳、靴口）蓋住鋸齒
- 頭：四邊面的球（立方體細分後球化），臉只有幾個小件：深色直橢圓眼＋上眼皮弧線、小鼻頭、小嘴、耳朵；沒有腮紅
- 頭髮：髮帽＋二十幾塊「根部粗、尖端收」的彎曲髮束（沿頭皮外彎的放樣），瀏海蓋到眉線、兩側蓋耳上緣、後腦往外翹
- 材質：roughness 0.85、metallic 0、specular 很弱
"""
import math
import bmesh, bpy
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

HEAD = 0.30
H = HEAD * 4.5                       # 1.35
HEAD_C = Vector((0.012, 0.0, H - HEAD * 0.5))
HEAD_R = HEAD * 0.5

# 純色（sRGB 反推的線性值）
COLORS = {
    "chr_skin": (0.90, 0.61, 0.43),      # #F3CDB0
    "chr_eye": (0.023, 0.013, 0.009),    # #2A1E18
    "chr_lid": (0.06, 0.03, 0.02),
    "chr_mouth": (0.30, 0.10, 0.07),
    "chr_hair": (0.10, 0.035, 0.014),    # #5A3420
    "chr_jacket": (0.58, 0.16, 0.03),    # #C8702E 鏽橘外套
    "chr_trim": (0.11, 0.19, 0.04),      # #5F7A3A 綠色袖口／下襬
    "chr_shirt": (0.84, 0.77, 0.58),     # #EDE3C8 米白內搭、帽兜內裡
    "chr_pants": (0.11, 0.15, 0.04),     # #5E6B3A 橄欖綠工裝褲
    "chr_sock": (0.80, 0.74, 0.58),
    "chr_boot": (0.15, 0.05, 0.017),     # #6B3F24
    "chr_sole": (0.69, 0.60, 0.43),      # #D9CBB0
    "chr_pack": (0.044, 0.036, 0.030),   # #3B3530 後背包
    "chr_patch": (0.53, 0.25, 0.07),     # 背包上的菱形皮標
}
_M = {}


def _mat(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = 0.85
    b.inputs["Metallic"].default_value = 0.0
    for key in ("Specular IOR Level", "Specular"):   # Blender 4.x / 3.x
        if key in b.inputs:
            b.inputs[key].default_value = 0.2
            break
    return m


def mats():
    if not _M:
        for n, rgb in COLORS.items():
            _M[n] = _mat(n, rgb)
    return _M


# ================================================================ 身體骨架（Skin modifier 的節點）
# 名稱 → (位置 (x 前, y 左, z 上), 半徑 (rx, ry))。中間節點讓關節前後各有 loop。
J = {
    "pelvis": ((0.0, 0.0, 0.60), (0.125, 0.098)),
    "waist": ((0.0, 0.0, 0.73), (0.118, 0.092)),
    "chest": ((0.004, 0.0, 0.86), (0.132, 0.098)),
    "upchest": ((0.0, 0.0, 0.93), (0.118, 0.088)),
    "neck0": ((0.006, 0.0, 0.99), (0.050, 0.050)),
    "neck1": ((0.012, 0.0, 1.07), (0.047, 0.047)),
}
for _s, _n in ((1, "l"), (-1, "r")):
    J.update({
        # 手臂：肩 → 上臂中 → 肘 → 前臂中 → 腕 → 掌 → 指尖；拇指從掌分支往前
        "clav_" + _n: ((0.0, _s * 0.085, 0.935), (0.070, 0.070)),
        "shoulder_" + _n: ((0.0, _s * 0.145, 0.925), (0.062, 0.062)),
        "uarm_" + _n: ((-0.008, _s * 0.163, 0.840), (0.054, 0.054)),
        "elbow_" + _n: ((-0.014, _s * 0.175, 0.755), (0.046, 0.046)),
        "farm_" + _n: ((-0.006, _s * 0.181, 0.670), (0.044, 0.044)),
        "wrist_" + _n: ((0.004, _s * 0.186, 0.592), (0.036, 0.036)),
        "palm_" + _n: ((0.014, _s * 0.190, 0.535), (0.050, 0.038)),
        "tip_" + _n: ((0.020, _s * 0.190, 0.478), (0.044, 0.032)),
        "thumb_" + _n: ((0.052, _s * 0.180, 0.540), (0.022, 0.022)),
        # 腿：骨盆側 → 髖 → 大腿中 → 膝 → 小腿肚 → 踝 → 腳尖（靴子）
        "pelv_" + _n: ((0.0, _s * 0.068, 0.585), (0.090, 0.090)),
        "hip_" + _n: ((0.0, _s * 0.078, 0.540), (0.088, 0.088)),
        "thigh_" + _n: ((0.006, _s * 0.080, 0.440), (0.080, 0.080)),
        "knee_" + _n: ((0.012, _s * 0.080, 0.335), (0.066, 0.066)),
        "calf_" + _n: ((0.000, _s * 0.080, 0.240), (0.066, 0.066)),
        "ankle_" + _n: ((0.000, _s * 0.080, 0.130), (0.066, 0.066)),
        "toe_" + _n: ((0.115, _s * 0.080, 0.080), (0.066, 0.056)),
    })

E = [("pelvis", "waist"), ("waist", "chest"), ("chest", "upchest"), ("upchest", "neck0"), ("neck0", "neck1")]
for _n in ("l", "r"):
    E += [("upchest", "clav_" + _n), ("clav_" + _n, "shoulder_" + _n), ("shoulder_" + _n, "uarm_" + _n),
          ("uarm_" + _n, "elbow_" + _n), ("elbow_" + _n, "farm_" + _n), ("farm_" + _n, "wrist_" + _n),
          ("wrist_" + _n, "palm_" + _n), ("palm_" + _n, "tip_" + _n), ("palm_" + _n, "thumb_" + _n),
          ("pelvis", "pelv_" + _n), ("pelv_" + _n, "hip_" + _n), ("hip_" + _n, "thigh_" + _n), ("thigh_" + _n, "knee_" + _n),
          ("knee_" + _n, "calf_" + _n), ("calf_" + _n, "ankle_" + _n), ("ankle_" + _n, "toe_" + _n)]


def _seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-9)))
    return (p - (a + ab * t)).length


def _region(p):
    """面中心 → 材質。先找最近的骨段，再看高度／前後。"""
    def cost(e):
        d = _seg_dist(p, Vector(J[e[0]][0]), Vector(J[e[1]][0]))
        if e[1].startswith(("palm_", "tip_", "thumb_")) and abs(p.y) < 0.170:
            d += 1.0   # 大腿外側離手很近，不要被手搶走
        return d
    a, b = min(E, key=cost)
    leg = any(k in a or k in b for k in ("hip_", "thigh_", "knee_", "calf_", "ankle_", "toe_", "pelv_"))
    if b.startswith(("neck", "palm_", "tip_", "thumb_")):
        return "chr_skin"
    if leg and p.z < 0.585:
        if p.z < 0.155:
            return "chr_boot"
        if p.z < 0.215:
            return "chr_sock"
        return "chr_pants"
    if p.z < 0.585:
        return "chr_pants"
    # 敞開的外套：胸前一條直的米白內搭（等寬，細分網格是直的才不會鋸齒）
    if p.x > 0.05 and abs(p.y) < 0.050 and p.z > 0.60 and a in ("pelvis", "waist", "chest", "upchest") \
            and b in ("waist", "chest", "upchest", "neck0"):
        return "chr_shirt"
    return "chr_jacket"


def _grow_body():
    names = list(J)
    idx = {n: i for i, n in enumerate(names)}
    me = bpy.data.meshes.new("skel")
    me.from_pydata([J[n][0] for n in names], [(idx[a], idx[b]) for a, b in E], [])
    ob = bpy.data.objects.new("skel", me)
    bpy.context.scene.collection.objects.link(ob)
    mod = ob.modifiers.new("Skin", 'SKIN')
    mod.use_smooth_shade = True
    mod.branch_smoothing = 0.6
    for i, n in enumerate(names):
        sv = me.skin_vertices[0].data[i]
        sv.radius = J[n][1]
        sv.use_root = n == "pelvis"
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


# ================================================================ 小型建模器

class Part:
    def __init__(self):
        self.bm = bmesh.new()

    def blob(self, c, r, rot=Matrix.Identity(3), sub=2):
        M = Matrix.Translation(Vector(c)) @ rot.to_4x4() @ Matrix.Diagonal((r[0], r[1], r[2], 1))
        bmesh.ops.create_icosphere(self.bm, subdivisions=sub, radius=1.0, matrix=M, calc_uvs=False)

    def qsphere(self, c, r, scale=(1, 1, 1), cuts=5):
        """四邊面球：立方體細分後投影到球面（頭用，乾淨的 quad 拓撲）。"""
        tb = bmesh.new()
        bmesh.ops.create_cube(tb, size=2.0)
        bmesh.ops.subdivide_edges(tb, edges=tb.edges[:], cuts=cuts, use_grid_fill=True)
        for v in tb.verts:
            d = v.co.normalized()
            v.co = Vector(c) + Vector((d.x * r * scale[0], d.y * r * scale[1], d.z * r * scale[2]))
        tmp = bpy.data.meshes.new("_qs")
        tb.to_mesh(tmp)
        tb.free()
        self.bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)

    def box(self, c, size, rot=Matrix.Identity(3), bevel=0.0):
        M = Matrix.Translation(Vector(c)) @ rot.to_4x4() @ Matrix.Diagonal((size[0], size[1], size[2], 1))
        r = bmesh.ops.create_cube(self.bm, size=1.0, matrix=M)
        if bevel > 0:
            es = list({e for v in r["verts"] for e in v.link_edges})
            bmesh.ops.bevel(self.bm, geom=es, offset=bevel, segments=2, affect='EDGES', profile=0.5)

    def tube(self, path, radii, k=12, cap=True, ex=2.0, side=None):
        """沿路徑放樣，截面是超橢圓；radii = 每點 (寬, 厚)。side = 截面寬的方向（可給每點一個）。"""
        P = [Vector(p) for p in path]
        rings = []
        for i, p in enumerate(P):
            t = (P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).normalized()
            sd = Vector(side[i] if isinstance(side, list) else (side or (0, 1, 0)))
            if sd.length < 1e-6 or abs(sd.normalized().dot(t)) > 0.98:
                sd = Vector((1, 0, 0)) if abs(t.x) < 0.9 else Vector((0, 1, 0))
            w = (sd - t * sd.dot(t)).normalized()
            d = w.cross(t).normalized()
            rw, rd = radii[i]
            ring = []
            for j in range(k):
                a = 2 * math.pi * j / k
                ca, sa = math.cos(a), math.sin(a)
                sx = math.copysign(abs(ca) ** (2 / ex), ca)
                sy = math.copysign(abs(sa) ** (2 / ex), sa)
                ring.append(self.bm.verts.new(p + w * (rw * sy) + d * (rd * sx)))
            rings.append(ring)
        for i in range(len(rings) - 1):
            A, C = rings[i], rings[i + 1]
            for j in range(k):
                self.bm.faces.new((A[j], A[(j + 1) % k], C[(j + 1) % k], C[j]))
        if cap:
            for ring, rev in ((rings[0], True), (rings[-1], False)):
                c = self.bm.verts.new(sum((v.co for v in ring), Vector()) / k)
                for j in range(k):
                    a, b = ring[j], ring[(j + 1) % k]
                    self.bm.faces.new((b, a, c) if rev else (a, b, c))

    def ring(self, c, r, tube_r, scale=(1, 1), k=20, kt=8, z_tilt=0.0):
        """水平圓環（下襬、領口）：r = 主半徑、scale 讓它變橢圓、z_tilt 讓前面低後面高（或反過來）。"""
        rings = []
        for i in range(k):
            a = 2 * math.pi * i / k
            ring = []
            for j in range(kt):
                t = 2 * math.pi * j / kt
                rr = 1 + tube_r * math.cos(t) / r
                ring.append(self.bm.verts.new(Vector(c) + Vector((r * scale[0] * math.cos(a) * rr, r * scale[1] * math.sin(a) * rr,
                                                                  tube_r * math.sin(t) + z_tilt * math.cos(a)))))
            rings.append(ring)
        for i in range(k):
            for j in range(kt):
                self.bm.faces.new((rings[i][j], rings[(i + 1) % k][j], rings[(i + 1) % k][(j + 1) % kt], rings[i][(j + 1) % kt]))

    def done(self, name, mat, parent, smooth=True):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        for p in me.polygons:
            p.use_smooth = smooth
        for m in (mat if isinstance(mat, list) else [mat]):
            me.materials.append(m)
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        ob.parent = parent
        return ob


def _rot(yaw=0.0, pitch=0.0, roll=0.0):
    return (Matrix.Rotation(math.radians(yaw), 3, 'Z') @ Matrix.Rotation(math.radians(pitch), 3, 'Y')
            @ Matrix.Rotation(math.radians(roll), 3, 'X'))


def _bez(a, b, c, n):
    return [a * (1 - t) ** 2 + b * 2 * t * (1 - t) + c * t * t for t in [i / (n - 1) for i in range(n)]]


# ================================================================ 頭、臉、頭髮

HEAD_SCALE = (0.96, 1.05, 1.0)


def _head(P):
    P["chr_skin"].qsphere(HEAD_C, HEAD_R, HEAD_SCALE, cuts=5)
    # 下半臉微微收：柔和的蛋圓而不是正球
    for v in P["chr_skin"].bm.verts:
        dz = (v.co.z - HEAD_C.z) / HEAD_R
        if dz < 0:
            v.co.y *= 1 - 0.10 * dz * dz
            v.co.x = HEAD_C.x + (v.co.x - HEAD_C.x) * (1 - 0.05 * dz * dz)


def _surface(bvh, y, z):
    hit = bvh.ray_cast(Vector((1.0, y, z)), Vector((-1, 0, 0)))
    return hit[0], hit[1]


def _face(P, bvh):
    ez = HEAD_C.z - 0.012                 # 眼睛在頭的中線略下
    for s in (-1, 1):
        p, n = _surface(bvh, s * 0.056, ez)
        P["chr_eye"].blob(p - n * 0.003, (0.008, 0.0145, 0.023), n.to_track_quat('X', 'Z').to_matrix(), sub=2)
        # 上眼皮：眼睛上緣一道細弧，外側略長
        pts = []
        for i in range(6):
            t = i / 5
            q, qn = _surface(bvh, s * (0.056 - 0.017 + 0.036 * t), ez + 0.017 + 0.007 * math.sin(math.pi * t) - 0.004 * t)
            pts.append(q + qn * 0.002)
        P["chr_lid"].tube(pts, [(0.0028, 0.0028)] * 6, k=6)
        # 耳朵
        P["chr_skin"].blob(HEAD_C + Vector((-0.004, s * HEAD_R * HEAD_SCALE[1] * 0.97, -0.018)), (0.024, 0.016, 0.034),
                           _rot(yaw=-s * 15), sub=2)
    p, n = _surface(bvh, 0.0, ez - 0.035)
    P["chr_skin"].blob(p + n * 0.001, (0.010, 0.012, 0.009), sub=2)   # 小鼻頭
    pts = []
    for i in range(5):
        y = -0.011 + 0.022 * i / 4
        q, qn = _surface(bvh, y, ez - 0.064 + 0.004 * (y / 0.011) ** 2)
        pts.append(q + qn * 0.0012)
    P["chr_mouth"].tube(pts, [(0.0024, 0.0024)] * 5, k=6)   # 小嘴


def _clump(part, root, tip, w, t, bulge=0.04, n=7, k=8):
    """一束頭髮：根部 (w 寬、t 厚)，往尖端收；路徑往頭外側鼓（bulge），截面寬方向沿頭皮切線。"""
    root, tip = Vector(root), Vector(tip)
    mid = (root + tip) / 2
    path = _bez(root, mid + (mid - HEAD_C).normalized() * bulge, tip, n)
    radii, sides = [], []
    for i, p in enumerate(path):
        f = i / (n - 1)
        taper = (1 - f) ** 0.8 * (0.7 + 0.6 * math.sin(math.pi * min(1.0, f + 0.25)))
        radii.append((max(w * taper, 0.002), max(t * taper, 0.0015)))
        tang = path[min(i + 1, n - 1)] - path[max(i - 1, 0)]
        sides.append(tang.normalized().cross((p - HEAD_C).normalized()))
    part.tube(path, radii, k=k, ex=2.0, side=sides)


def _hair(P):
    hp = P["chr_hair"]
    # 髮帽：比頭大一圈的球，斜切掉臉的部分（前額高、後頸低）
    hb = bmesh.new()
    M = Matrix.Translation(HEAD_C + Vector((-0.012, 0, 0.022))) @ Matrix.Diagonal((0.172, 0.180, 0.168, 1))
    bmesh.ops.create_uvsphere(hb, u_segments=20, v_segments=12, radius=1.0, matrix=M)
    r = bmesh.ops.bisect_plane(hb, geom=hb.verts[:] + hb.edges[:] + hb.faces[:], plane_co=HEAD_C + Vector((0.10, 0, 0.035)),
                               plane_no=Vector((0.75, 0, -1)).normalized(), clear_outer=True)
    es = [e for e in r["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
    if es:
        bmesh.ops.holes_fill(hb, edges=es)
    tmp = bpy.data.meshes.new("_hc")
    hb.to_mesh(tmp)
    hb.free()
    hp.bm.from_mesh(tmp)
    bpy.data.meshes.remove(tmp)

    C = HEAD_C

    def sph(az, el, rr=1.0):
        """頭外的一點：az 方位角（0 = 正前、90 = 左）、el 仰角，rr 倍半徑。"""
        a, e = math.radians(az), math.radians(el)
        return C + Vector((math.cos(e) * math.cos(a) * 0.165 * rr, math.cos(e) * math.sin(a) * 0.172 * rr, math.sin(e) * 0.165 * rr))

    # 瀏海：從頭頂往前垂，尖端停在眉線（蓋住額頭），略微往兩側撇
    for az, tip_az, tip_el, w in ((-38, -46, 6, 0.050), (-16, -20, 2, 0.055), (6, 4, 0, 0.056), (26, 32, 3, 0.052), (44, 54, 8, 0.046)):
        _clump(hp, sph(az * 0.5, 62), sph(tip_az, tip_el, 1.06), w * 1.15, 0.036, bulge=0.06)
    # 兩側：蓋住耳朵上緣，尖端往外翹
    for s in (-1, 1):
        for az, el, tip_el, w in ((70, 40, -12, 0.050), (95, 38, -22, 0.052), (118, 36, -18, 0.050)):
            _clump(hp, sph(s * az * 0.85, el + 18), sph(s * (az + 12), tip_el + 4, 1.24), w * 1.2, 0.040, bulge=0.06)
    # 後腦：往下到後頸，尖端往外撇
    for az in (140, 162, 180, 198, 220):
        _clump(hp, sph(az, 55), sph(az + (16 if az < 180 else -16 if az > 180 else 0), -20, 1.22), 0.066, 0.040, bulge=0.06)
    # 頭頂：幾撮往後上方翹的亂髮
    for az, el, tz in ((-20, 70, 0.07), (25, 72, 0.06), (170, 68, 0.06), (100, 66, 0.05), (-110, 66, 0.05)):
        base = sph(az, el, 0.98)
        tip = base + (base - C).normalized() * 0.025 + Vector((-0.06, 0, tz * 0.15))   # 往後躺的亂髮，不要刺蝟頭
        _clump(hp, base, tip, 0.050, 0.030, bulge=0.02, n=5)


# ================================================================ 衣服配件

def _clothes(P):
    tr, sh, ja, so, pa, bo = P["chr_trim"], P["chr_shirt"], P["chr_jacket"], P["chr_sole"], P["chr_pants"], P["chr_boot"]
    tr.ring((0.0, 0, 0.590), 0.127, 0.017, scale=(0.80, 1.0))   # 外套下襬的綠色滾邊
    for s in (-1, 1):
        w = Vector(J["wrist_" + ("l" if s > 0 else "r")][0])
        tr.tube([w + Vector((0.004, 0, 0.022)), w + Vector((-0.002, 0, -0.012))], [(0.047, 0.047)] * 2, k=14)   # 袖口
        so.tube([(0.0, s * 0.080, 0.230), (0.0, s * 0.080, 0.190)], [(0.074, 0.074)] * 2, k=14)            # 反摺襪口
        bo.tube([(0.0, s * 0.080, 0.165), (0.0, s * 0.080, 0.140)], [(0.072, 0.072)] * 2, k=14)            # 靴口
        pa.box((0.004, s * 0.150, 0.420), (0.080, 0.030, 0.090), bevel=0.010)   # 工裝口袋
        pa.box((0.004, s * 0.158, 0.462), (0.086, 0.026, 0.024), bevel=0.008)   # 袋蓋
        so.box((0.045, s * 0.080, 0.022), (0.255, 0.122, 0.044), bevel=0.020)   # 厚鞋底
        bo.blob((0.120, s * 0.080, 0.072), (0.075, 0.064, 0.052), sub=2)        # 圓鼓的鞋頭
    # 帽兜：橘色外層攤在後頸／上背，米白內裡圍一圈領口
    ja.blob((-0.092, 0, 0.965), (0.072, 0.140, 0.080), _rot(pitch=28), sub=3)       # 攤在背上的帽兜
    sh.blob((-0.070, 0, 0.985), (0.050, 0.105, 0.050), _rot(pitch=28), sub=3)       # 帽兜內裡（從上方看得到）
    sh.ring((0.008, 0, 1.010), 0.058, 0.020, scale=(1.0, 1.05), z_tilt=-0.020)     # 米白內搭的領口


def _lapels(P, body_bvh):
    """外套敞開的前襟：兩條貼著身體的橘色厚邊，蓋住米白內搭與外套的材質交界。"""
    for s in (-1, 1):
        path = []
        for i in range(9):
            z = 0.595 + (0.975 - 0.595) * i / 8
            y = s * (0.052 + 0.010 * max(0.0, (z - 0.90) / 0.075))   # 領口處微微外開
            hit = body_bvh.ray_cast(Vector((0.4, y, z)), Vector((-1, 0, 0)))
            if hit[0]:
                path.append(hit[0] + hit[1] * 0.004)
        P["chr_jacket"].tube(path, [(0.021, 0.008)] * len(path), k=8, ex=2.6, side=(0, 1, 0))


def _backpack(P, body_bvh):
    pk, pt = P["chr_pack"], P["chr_patch"]
    pk.box((-0.165, 0, 0.82), (0.11, 0.22, 0.25), bevel=0.035)
    pk.box((-0.226, 0, 0.77), (0.04, 0.16, 0.12), bevel=0.015)                      # 前口袋
    pk.box((-0.165, 0, 0.955), (0.07, 0.06, 0.03), rot=_rot(roll=90), bevel=0.01)   # 提把
    pt.box((-0.248, 0, 0.83), (0.006, 0.035, 0.035), rot=_rot(roll=45))             # 菱形皮標
    for s in (-1, 1):
        y = s * 0.085
        # 肩帶：從背包頂端繞過肩膀到胸前腰側，每個點從身體中軸往外打射線貼到表面
        ctrl = [(-0.13, y, 0.92), (-0.08, y, 0.975), (0.0, y, 1.0), (0.07, y, 0.95), (0.10, y, 0.86), (0.10, y * 1.05, 0.76), (0.095, y * 1.1, 0.68)]
        path = []
        for c in ctrl:
            c = Vector(c)
            o = Vector((0.0, y * 0.6, min(c.z, 0.93)))
            hit = body_bvh.ray_cast(o + (c - o) * 3.0, -(c - o).normalized())
            path.append(hit[0] + hit[1] * 0.006 if hit[0] else c)
        pk.tube(path, [(0.019, 0.006)] * len(path), k=8, ex=3.0, side=(0, 1, 0))


# ================================================================

def character(name):
    mats()
    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    P = {n: Part() for n in COLORS}
    _head(P)
    bvh = BVHTree.FromBMesh(P["chr_skin"].bm)   # 這時 skin 只有頭，臉部件靠它找表面
    _face(P, bvh)
    _hair(P)
    _clothes(P)
    # 身體：一個 mesh、多個材質槽
    body = Part()
    body.bm.free()
    body.bm = _grow_body()
    bvh_body = BVHTree.FromBMesh(body.bm)
    _backpack(P, bvh_body)
    _lapels(P, bvh_body)
    order = ["chr_skin", "chr_jacket", "chr_shirt", "chr_pants", "chr_sock", "chr_boot"]
    for f in body.bm.faces:
        f.material_index = order.index(_region(f.calc_center_median()))
    body.done(name + "_body", [_M[n] for n in order], root)
    for n, part in P.items():
        if len(part.bm.verts):
            part.done(name + "_" + n, _M[n], root)
        else:
            part.bm.free()
    return root
