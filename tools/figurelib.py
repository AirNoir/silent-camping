"""第四代角色原型（在 Blender 內使用）：5～5.5 頭身的「微縮模型人偶」，只做比例／剪影／臉／髮／衣服，不綁骨、不貼圖。
- 風格：跟樹、帳篷、露營車同一個世界——圓潤、霧面、塊面清楚；不寫實、不做動漫大眼
- 比例：全高 1.55 m、頭高 0.31 m（≈5 頭身，頭比真人大 ~30%）；手、鞋刻意放大
- 身體各部位用「沿路徑放樣、截面是超橢圓」的管子拼起來（軀幹、四肢），彼此重疊不縫合——原型階段只看外型
- 臉：幾何件貼在頭的表面（射線找表面點）：深色橢圓眼＋小亮點、短眉、小鼻頭、小嘴、淡腮紅、耳朵
- 頭髮：頭殼外擴後斜切成髮帽，再疊幾塊大的「髮束」橢球（瀏海、兩側、後腦），像黏土捏的
- 材質：全部純色、roughness 0.9，沒有貼圖
"""
import math
import bmesh, bpy
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import treelib as T

H = 1.55
HEAD = 0.31                      # 頭高（頭頂到下巴）
CHIN = H - HEAD                  # 1.255
HEAD_C = Vector((0.0, 0.0, CHIN + HEAD * 0.5))

# 純色（sRGB 反推的線性值）
COLORS = {
    "fig_skin": (0.88, 0.58, 0.40),       # #F2C8A8
    "fig_blush": (0.90, 0.40, 0.36),
    "fig_eye": (0.035, 0.025, 0.02),
    "fig_white": (0.92, 0.92, 0.90),
    "fig_brow": (0.10, 0.05, 0.03),
    "fig_mouth": (0.35, 0.09, 0.07),
    "fig_hair": (0.16, 0.075, 0.035),     # 栗棕
    "fig_sweater": (0.70, 0.27, 0.10),    # 磚橘毛衣 #D88C5A
    "fig_collar": (0.87, 0.80, 0.62),     # 米白領口／袖口／褲腳反摺
    "fig_pants": (0.20, 0.25, 0.11),      # 橄欖綠工作褲
    "fig_shoe": (0.30, 0.15, 0.07),       # 焦糖色短靴
    "fig_sole": (0.80, 0.74, 0.62),       # 米色厚鞋底
}
_M = {}


def mats():
    if not _M:
        for n, rgb in COLORS.items():
            _M[n] = T._mat(n, rgb)
    return _M


class Part:
    """一個材質一個 bmesh；最後各自變成物件掛在根節點底下。"""

    def __init__(self):
        self.bm = bmesh.new()

    def blob(self, c, r, rot=Matrix.Identity(3), sub=2):
        """旋轉過的橢球（髮束、手、臉部小件）。r = (rx, ry, rz)。"""
        M = Matrix.Translation(Vector(c)) @ rot.to_4x4() @ Matrix.Diagonal((r[0], r[1], r[2], 1))
        bmesh.ops.create_icosphere(self.bm, subdivisions=sub, radius=1.0, matrix=M, calc_uvs=False)

    def tube(self, path, radii, k=16, cap=True, ex=2.6, side=None):
        """沿路徑放樣：path = 點列，radii = 每點 (寬 rw, 前厚 rd[, 後厚])，截面是超橢圓（ex>2 偏方、=2 圓）。
        side = 截面的「寬」方向（預設 +Y），讓軀幹寬而扁。"""
        P = [Vector(p) for p in path]
        side = Vector(side or (0, 1, 0))
        rings = []
        for i, p in enumerate(P):
            t = (P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).normalized()
            w = (side - t * side.dot(t)).normalized()
            d = w.cross(t).normalized()          # 厚度方向
            rw, rdp = radii[i][0], radii[i][1]
            rdn = radii[i][2] if len(radii[i]) > 2 else rdp
            ring = []
            for j in range(k):
                a = 2 * math.pi * j / k
                ca, sa = math.cos(a), math.sin(a)
                sx = math.copysign(abs(ca) ** (2 / ex), ca)
                sy = math.copysign(abs(sa) ** (2 / ex), sa)
                ring.append(self.bm.verts.new(p + w * (rw * sy) + d * ((rdp if sx > 0 else rdn) * sx)))
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
        return rings

    def done(self, name, mat, parent):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        for p in me.polygons:
            p.use_smooth = True
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        ob.parent = parent
        return ob


def _rot(yaw=0.0, pitch=0.0, roll=0.0):
    """yaw 繞 Z、pitch 繞 Y、roll 繞 X（角度）。"""
    return (Matrix.Rotation(math.radians(yaw), 3, 'Z') @ Matrix.Rotation(math.radians(pitch), 3, 'Y')
            @ Matrix.Rotation(math.radians(roll), 3, 'X'))


def _smooth_path(pts, n=3):
    """控制點之間插 Catmull-Rom，四肢的彎曲才連續。"""
    P = [Vector(p) for p in pts]
    out = []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = P[max(i - 1, 0)], P[i], P[i + 1], P[min(i + 2, len(P) - 1)]
        for s in range(n):
            t = s / n
            out.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    out.append(P[-1])
    return out


def _lerp_radii(keys, n):
    """keys = 控制點上的半徑組，線性內插成 n 個。"""
    out = []
    for i in range(n):
        f = i / (n - 1) * (len(keys) - 1)
        a = int(min(f, len(keys) - 2))
        t = f - a
        out.append(tuple(keys[a][j] * (1 - t) + keys[a + 1][j] * t for j in range(len(keys[a]))))
    return out


def _limb(part, ctrl, keys, k=14, ex=2.2, n=3, side=None, cap=True):
    path = _smooth_path(ctrl, n)
    return part.tube(path, _lerp_radii(keys, len(path)), k=k, ex=ex, side=side, cap=cap)


# ================================================================ 頭

def _head(skin):
    """頭：上半近似球、下半往下巴收成圓潤的蛋形；截面沿 Z 放樣，後腦比臉深一點。"""
    N = 14
    path, radii = [], []
    for i in range(N + 1):
        t = i / N                                  # 0 = 下巴、1 = 頭頂
        s = math.sin(math.acos(1 - 2 * t))
        jaw = 0.78 + 0.22 * min(1.0, t / 0.42)
        rw = 0.140 * s * jaw
        rf = 0.138 * s * (0.86 + 0.14 * min(1.0, t / 0.4))
        rb = 0.148 * s
        path.append((0.0, 0.0, CHIN + HEAD * t))
        radii.append((max(rw, 0.004), max(rf, 0.004), max(rb, 0.004)))
    skin.tube(path, radii, k=22, ex=2.15)


def _surface(bvh, y, z, depth=0.3):
    """從正前方射線打到頭的表面：回傳 (位置, 法線)。"""
    hit = bvh.ray_cast(Vector((depth, y, z)), Vector((-1, 0, 0)))
    return hit[0], hit[1]


def _face(parts, bvh):
    eye_z = CHIN + HEAD * 0.44                    # 眼睛在頭高一半略下（大額頭）
    for s in (-1, 1):
        p, nrm = _surface(bvh, s * 0.047, eye_z)
        rot = nrm.to_track_quat('X', 'Z').to_matrix()
        parts["fig_eye"].blob(p - nrm * 0.004, (0.010, 0.017, 0.025), rot, sub=2)
        hp, hn = _surface(bvh, s * 0.047 + 0.007, eye_z + 0.010)
        parts["fig_white"].blob(hp + hn * 0.006, (0.003, 0.0055, 0.0055), sub=1)
        # 短眉：微微上揚的扁膠囊
        bp, bn = _surface(bvh, s * 0.050, eye_z + 0.044)
        parts["fig_brow"].blob(bp - bn * 0.002, (0.006, 0.020, 0.0055), bn.to_track_quat('X', 'Z').to_matrix() @ _rot(roll=-s * 8), sub=2)
        # 腮紅：很淡的扁圓
        cp, cn = _surface(bvh, s * 0.078, eye_z - 0.040)
        parts["fig_blush"].blob(cp - cn * 0.004, (0.006, 0.024, 0.014), cn.to_track_quat('X', 'Z').to_matrix(), sub=2)
        # 耳朵
        parts["fig_skin"].blob((0.0, s * 0.138, eye_z - 0.006), (0.026, 0.016, 0.036), _rot(yaw=s * -12), sub=2)
    # 小鼻頭
    np_, nn = _surface(bvh, 0.0, eye_z - 0.030)
    parts["fig_skin"].blob(np_ + nn * 0.002, (0.014, 0.016, 0.013), sub=2)
    # 小嘴：微笑的短弧
    mz = eye_z - 0.068
    pts = []
    for i in range(7):
        y = -0.019 + 0.038 * i / 6
        p, n = _surface(bvh, y, mz + 0.006 * (y / 0.019) ** 2)
        pts.append(p + n * 0.0015)
    parts["fig_mouth"].tube(pts, [(0.0032, 0.0032)] * 7, k=8, ex=2.0, side=(0, 0, 1))


def _hair(hair):
    """頭髮：外擴的髮帽（前額高、後腦低的斜切）＋幾塊大髮束。"""
    hb = bmesh.new()
    M = Matrix.Translation(HEAD_C + Vector((-0.010, 0, 0.018))) @ Matrix.Diagonal((0.162, 0.155, 0.160, 1))
    bmesh.ops.create_uvsphere(hb, u_segments=24, v_segments=14, radius=1.0, matrix=M, calc_uvs=False)
    no = Vector((0.55, 0, -1)).normalized()
    co = Vector((0.12, 0, CHIN + HEAD * 0.70))
    r = bmesh.ops.bisect_plane(hb, geom=hb.verts[:] + hb.edges[:] + hb.faces[:], plane_co=co, plane_no=no, clear_outer=True)
    edges = [e for e in r["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
    if edges:
        bmesh.ops.holes_fill(hb, edges=edges)
    # 鬢角往下延伸蓋住耳朵上緣
    for v in hb.verts:
        side = abs(v.co.y) / 0.155
        if v.co.x < 0.06 and side > 0.6:
            v.co.z -= 0.035 * (side - 0.6) / 0.4 * max(0.0, 1 - max(0.0, v.co.x) / 0.06)
    tmp = bpy.data.meshes.new("_hc")
    hb.to_mesh(tmp)
    hb.free()
    hair.bm.from_mesh(tmp)
    bpy.data.meshes.remove(tmp)

    top = CHIN + HEAD
    # 瀏海：三塊往側邊掃的大髮束，尖端停在額頭
    for (y, z, yaw, roll, sc) in ((0.055, top - 0.075, 18, -32, 1.0), (-0.005, top - 0.068, 6, -22, 1.05),
                                  (-0.068, top - 0.085, -10, 14, 0.9)):
        hair.blob((0.112, y, z), (0.05 * sc, 0.062 * sc, 0.040 * sc), _rot(yaw=yaw, pitch=-28, roll=roll), sub=2)
    # 頭頂一撮
    hair.blob((0.03, 0.02, top - 0.012), (0.085, 0.075, 0.034), _rot(pitch=-14, roll=-10), sub=2)
    # 兩側：耳朵前的髮束
    for s in (-1, 1):
        hair.blob((0.03, s * 0.140, HEAD_C.z + 0.02), (0.045, 0.030, 0.070), _rot(yaw=s * 10, roll=s * 8), sub=2)
    # 後腦：三塊往下收的髮束
    for (y, z, roll) in ((0.0, HEAD_C.z - 0.03, 0), (0.07, HEAD_C.z - 0.01, 14), (-0.07, HEAD_C.z - 0.01, -14)):
        hair.blob((-0.112, y, z), (0.05, 0.068, 0.08), _rot(pitch=18, roll=roll), sub=2)


# ================================================================ 身體與衣服

def _body(P):
    sw, pa, co, sk = P["fig_sweater"], P["fig_pants"], P["fig_collar"], P["fig_skin"]
    sk.tube([(0.0, 0, CHIN - 0.07), (0.005, 0, CHIN + 0.04)], [(0.045, 0.043), (0.046, 0.044)], k=14, ex=2.0)   # 脖子
    # 毛衣軀幹（寬而扁，胸前略鼓，下襬略寬鬆）
    trunk = [(0.0, 0, 0.74), (0.0, 0, 0.80), (0.0, 0, 0.90), (0.005, 0, 1.00), (0.005, 0, 1.10), (0.0, 0, 1.17), (0.0, 0, 1.215)]
    radii = [(0.138, 0.098, 0.100), (0.138, 0.098, 0.100), (0.128, 0.094, 0.096), (0.134, 0.100, 0.094),
             (0.142, 0.102, 0.094), (0.128, 0.094, 0.086), (0.075, 0.062, 0.062)]
    sw.tube(_smooth_path(trunk, 2), _lerp_radii(radii, 13), k=20, ex=2.7)
    co.tube([(0.0, 0, 0.725), (0.0, 0, 0.765)], [(0.143, 0.103, 0.105)] * 2, k=20, ex=2.7)   # 下襬羅紋
    co.tube([(0.002, 0, 1.19), (0.004, 0, 1.25)], [(0.062, 0.058), (0.056, 0.052)], k=16, ex=2.0)   # 高領口
    # 褲子：臀部一段 + 兩條直筒褲管 + 反摺褲腳
    pa.tube([(0.0, 0, 0.66), (0.0, 0, 0.72), (0.0, 0, 0.75)], [(0.128, 0.092, 0.100), (0.134, 0.094, 0.100), (0.130, 0.092, 0.096)],
            k=20, ex=2.6)
    for s in (-1, 1):
        y = s * 0.074
        _limb(pa, [(0.0, y, 0.74), (0.012, y * 1.02, 0.42), (0.0, y * 1.06, 0.15)],
              [(0.078, 0.080), (0.064, 0.066), (0.066, 0.068)], k=14, ex=2.3, n=3)
        co.tube([(0.0, y * 1.06, 0.115), (0.0, y * 1.06, 0.165)], [(0.072, 0.074)] * 2, k=14, ex=2.3)


def _arms(P):
    sw, co, sk = P["fig_sweater"], P["fig_collar"], P["fig_skin"]
    for s in (-1, 1):
        sh = Vector((0.0, s * 0.140, 1.125))
        el = Vector((-0.012, s * 0.178, 0.915))
        wr = Vector((0.02, s * 0.195, 0.735))
        sw.blob(sh + Vector((0, -s * 0.008, 0.012)), (0.066, 0.068, 0.062), sub=3)   # 圓肩
        # 袖子：肩膀圓潤、往手腕微收
        _limb(sw, [sh, el, wr], [(0.060, 0.060), (0.050, 0.050), (0.047, 0.047)], k=14, ex=2.1, n=3)
        co.tube([wr + Vector((0, 0, 0.022)), wr - Vector((0.0, 0, 0.022))], [(0.050, 0.050)] * 2, k=14, ex=2.1)
        # 手：偏大的連指手掌 + 拇指（不做五指）
        hc = wr + Vector((0.012, s * 0.004, -0.088))
        sk.blob(hc, (0.040, 0.034, 0.064), _rot(roll=s * 6), sub=2)
        sk.blob(hc + Vector((0.040, -s * 0.010, 0.020)), (0.020, 0.019, 0.036), _rot(pitch=-25, roll=-s * 15), sub=2)
        sk.tube([wr, hc + Vector((0, 0, 0.03))], [(0.034, 0.030)] * 2, k=12, ex=2.0)   # 手腕


def _shoes(P):
    sh, so = P["fig_shoe"], P["fig_sole"]
    for s in (-1, 1):
        y = s * 0.080
        # 圓頭短靴，比例放大（長 ~0.25）
        sh.tube([(-0.075, y, 0.075), (-0.02, y, 0.085), (0.06, y, 0.068), (0.135, y, 0.055)],
                [(0.050, 0.044), (0.055, 0.048), (0.056, 0.045), (0.050, 0.030)], k=16, ex=2.4)
        sh.tube([(-0.035, y, 0.07), (-0.035, y, 0.16)], [(0.060, 0.062), (0.062, 0.066)], k=16, ex=2.3)   # 靴筒
        sh.blob((0.105, y, 0.055), (0.060, 0.052, 0.040), sub=2)   # 鞋頭
        so.tube([(-0.08, y, 0.018), (0.145, y, 0.018)], [(0.054, 0.020), (0.052, 0.020)], k=16, ex=3.2)   # 厚鞋底


def figure(name):
    mats()
    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    P = {n: Part() for n in COLORS}
    _head(P["fig_skin"])
    bvh = BVHTree.FromBMesh(P["fig_skin"].bm)   # 這時 skin 只有頭，臉部件靠它找表面
    _face(P, bvh)
    _hair(P["fig_hair"])
    _body(P)
    _arms(P)
    _shoes(P)
    for n, part in P.items():
        if len(part.bm.verts):
            part.done(name + "_" + n, _M[n], root)
        else:
            part.bm.free()
    return root
