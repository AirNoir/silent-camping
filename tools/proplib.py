"""營地道具生成（在 Blender 內使用）。單位 = 公尺。
- camper_van：福斯 T1 Splitscreen 風格（圓角斷面放樣車身、分割前擋、V 形雙色前臉、VW 圓標、輪拱、白邊胎）
- dome_tent：Coleman Tough Dome 風格（圓角方形圓頂、交叉營柱、綠外帳／卡其內帳／深灰底、D 門、前庭雨棚）
- 露營器具：椅、桌、燈、營火、三腳架、木箱、保冷箱
"""
import bmesh, math
from mathutils import Vector, Matrix
import treelib as T

_P = {}


def _emat(name, rgb, strength):
    m = T._mat(name, rgb)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Emission Color"].default_value = (*rgb, 1)
    b.inputs["Emission Strength"].default_value = strength
    return m


def pm():
    if not _P:
        _P.update(T._more_mats())
        for n, rgb in [("canvas", (0.93, 0.88, 0.76)), ("canvasTrim", (0.75, 0.38, 0.30)), ("woodPole", (0.62, 0.45, 0.28)),
                       ("rope", (0.86, 0.80, 0.66)), ("vanPaint", (0.70, 0.22, 0.20)), ("vanCream", (0.96, 0.93, 0.85)),
                       ("chrome", (0.86, 0.88, 0.90)), ("glass", (0.45, 0.66, 0.80)), ("rubber", (0.12, 0.12, 0.13)),
                       ("darkMetal", (0.24, 0.24, 0.26)), ("fabricBlue", (0.30, 0.46, 0.70)), ("fabricRed", (0.78, 0.28, 0.24)),
                       ("interiorDark", (0.28, 0.22, 0.18)),
                       ("tentGreen", (0.29, 0.45, 0.27)), ("tentBeige", (0.82, 0.76, 0.60)), ("tentFloor", (0.24, 0.25, 0.26)),
                       ("tentMesh", (0.15, 0.16, 0.17)), ("tailRed", (0.80, 0.15, 0.12)),
                       ("solar", (0.13, 0.17, 0.30)),
                       # 粉彩色以「目標 sRGB 反推的線性值」填：mint #7FD8C0、cream #F5E6A3、coral #F2A0A0、blue #8EC5F0
                       ("headlightGlass", (0.70, 0.82, 0.95)),
                       ("vanMint", (0.21, 0.69, 0.52)), ("vanCreamY", (0.91, 0.79, 0.37)),
                       ("bagCoral", (0.89, 0.35, 0.35)), ("coolerBlue", (0.27, 0.56, 0.87)),
                       # 露營者（同樣是 sRGB 反推的線性值）：膚色 #F5CBA7、芥末黃 #E8B04B、梅紫 #9B5B8A、卡其 #C9B37E、橄欖 #6B7A45
                       ("skin", (0.91, 0.60, 0.39)), ("eyeDark", (0.02, 0.015, 0.012)), ("blush", (0.90, 0.33, 0.33)),
                       ("puffMustard", (0.81, 0.43, 0.07)), ("fleecePlum", (0.33, 0.10, 0.25)),
                       ("pantsNavy", (0.04, 0.07, 0.15)), ("pantsKhaki", (0.58, 0.45, 0.21)), ("boots", (0.12, 0.07, 0.04)),
                       ("beanieRed", (0.75, 0.12, 0.10)), ("hairDark", (0.045, 0.025, 0.017)), ("hairBrown", (0.10, 0.045, 0.025)),
                       ("hatOlive", (0.15, 0.19, 0.06)), ("mitten", (0.35, 0.22, 0.14)), ("toast", (0.50, 0.24, 0.08)),
                       ("copper", (0.72, 0.36, 0.20)), ("dripperTerra", (0.55, 0.20, 0.10)), ("coffee", (0.05, 0.03, 0.02)),
                       # 散步版：天藍 #7FB8E8、綠毛帽 #5C9E6B
                       ("puffSky", (0.21, 0.48, 0.81)), ("beanieGreen", (0.11, 0.34, 0.15))]:
            _P[n] = T._mat(n, rgb)
        _P["lanternGlow"] = _emat("lanternGlow", (1.0, 0.82, 0.45), 3.0)
        _P["flameOrange"] = _emat("flameOrange", (1.0, 0.45, 0.12), 4.0)
        _P["flameYellow"] = _emat("flameYellow", (1.0, 0.85, 0.30), 5.0)
    return _P


class B:
    """小型建模器：每呼叫一次 use(mat) 就把「還沒分組的面」指定給該材質（mat 可以是 callable(face)->材質）。
    分組用面的自訂整數層記錄，不依賴 bmesh 的面順序（bmesh 的面序列順序不保證等於建立順序）。"""

    def __init__(self):
        self.bm = bmesh.new()
        self.grp = self.bm.faces.layers.int.new("grp")
        self.li = self.bm.faces.layers.int.new("li")   # loft：第幾段（-1 = 非放樣面）
        self.lk = self.bm.faces.layers.int.new("lk")   # loft：環上第幾個點起的面
        self.groups = []   # rid-1 → (mat, smooth)

    def use(self, mat, smooth=False):
        rid = len(self.groups) + 1
        n = 0
        if callable(mat):
            bmesh.ops.recalc_face_normals(self.bm, faces=[f for f in self.bm.faces if f[self.grp] == 0])
            self.bm.normal_update()
            fixed = {}
            for f in self.bm.faces:
                if f[self.grp] == 0:
                    fixed[f] = mat(f)
            mat_fn = mat
            mat = lambda f, _d=fixed, _fn=mat_fn: _d.get(f) or _fn(f)
        for f in self.bm.faces:
            if f[self.grp] == 0:
                f[self.grp] = rid
                n += 1
        self.groups.append((mat, smooth))
        return n

    def box(self, c, size, rz=0.0, ry=0.0, rx=0.0):
        M = (Matrix.Translation(Vector(c)) @ Matrix.Rotation(rz, 4, 'Z') @ Matrix.Rotation(ry, 4, 'Y')
             @ Matrix.Rotation(rx, 4, 'X') @ Matrix.Diagonal((size[0], size[1], size[2], 1)))
        bmesh.ops.create_cube(self.bm, size=1.0, matrix=M, calc_uvs=False)

    def cyl(self, c, r, depth, segs=12, axis='Z', r2=None, cap=True, rz=0.0):
        rot = {'Z': Matrix.Identity(4), 'X': Matrix.Rotation(math.pi / 2, 4, 'Y'), 'Y': Matrix.Rotation(math.pi / 2, 4, 'X')}[axis]
        M = Matrix.Translation(Vector(c)) @ Matrix.Rotation(rz, 4, 'Z') @ rot
        bmesh.ops.create_cone(self.bm, cap_ends=cap, cap_tris=False, segments=segs, radius1=r,
                              radius2=r if r2 is None else r2, depth=depth, matrix=M, calc_uvs=False)

    def torus(self, c, R, r, axis='Y', seg_major=22, seg_minor=12):
        """圓環（氣球胎）：R 主半徑、r 管半徑，axis 為環的軸向。"""
        rot = {'Z': Matrix.Identity(4), 'X': Matrix.Rotation(math.pi / 2, 4, 'Y'), 'Y': Matrix.Rotation(math.pi / 2, 4, 'X')}[axis]
        M = Matrix.Translation(Vector(c)) @ rot
        rings = []
        for i in range(seg_major):
            a = i * 2 * math.pi / seg_major
            ring = []
            for j in range(seg_minor):
                t = j * 2 * math.pi / seg_minor
                p = Vector(((R + r * math.cos(t)) * math.cos(a), (R + r * math.cos(t)) * math.sin(a), r * math.sin(t)))
                ring.append(self.bm.verts.new(M @ p))
            rings.append(ring)
        for i in range(seg_major):
            for j in range(seg_minor):
                self.bm.faces.new((rings[i][j], rings[(i + 1) % seg_major][j],
                                   rings[(i + 1) % seg_major][(j + 1) % seg_minor], rings[i][(j + 1) % seg_minor]))

    def sphere(self, c, r, sub=1, scale=(1, 1, 1)):
        M = Matrix.Translation(Vector(c)) @ Matrix.Diagonal((scale[0], scale[1], scale[2], 1))
        bmesh.ops.create_icosphere(self.bm, subdivisions=sub, radius=r, matrix=M, calc_uvs=False)

    def rod(self, a, b, r, segs=6):
        a, b = Vector(a), Vector(b)
        d = b - a
        up = 'X' if abs(d.normalized().y) > 0.99 else 'Y'
        M = Matrix.Translation((a + b) / 2) @ d.to_track_quat('Z', up).to_matrix().to_4x4()
        bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=segs, radius1=r, radius2=r,
                              depth=d.length, matrix=M, calc_uvs=False)

    def prism(self, profile_xz, y0, y1):
        va = [self.bm.verts.new(Vector((x, y0, z))) for x, z in profile_xz]
        vb = [self.bm.verts.new(Vector((x, y1, z))) for x, z in profile_xz]
        self.bm.faces.new(va)
        self.bm.faces.new(vb[::-1])
        n = len(profile_xz)
        for i in range(n):
            self.bm.faces.new((va[i], va[(i + 1) % n], vb[(i + 1) % n], vb[i]))

    def poly(self, pts):
        self.bm.faces.new([self.bm.verts.new(Vector(p)) for p in pts])

    def slab(self, pts, t=0.02):
        """有厚度的多邊形板（雨棚、地布），兩面都看得到。"""
        P = [Vector(p) for p in pts]
        n = (P[1] - P[0]).cross(P[-1] - P[0]).normalized()
        va = [self.bm.verts.new(p) for p in P]
        vb = [self.bm.verts.new(p - n * t) for p in P]
        self.bm.faces.new(va)
        self.bm.faces.new(vb[::-1])
        for i in range(len(P)):
            self.bm.faces.new((va[i], vb[i], vb[(i + 1) % len(P)], va[(i + 1) % len(P)]))

    def tri(self, a, b, c):
        self.poly((a, b, c))

    def loft(self, sections, cap_start=True, cap_end=True):
        """sections = [(x, [(y, z), ...]), ...]，每段點數相同；可選兩端封口。回傳每段的頂點環。"""
        for f in self.bm.faces:
            if f[self.li] == 0 and f[self.lk] == 0:
                f[self.li] = -1
                f[self.lk] = -1
        rings = [[self.bm.verts.new(Vector((x, y, z))) for y, z in pts] for x, pts in sections]
        for i in range(len(rings) - 1):
            A, C = rings[i], rings[i + 1]
            n = len(A)
            for k in range(n):
                f = self.bm.faces.new((A[k], A[(k + 1) % n], C[(k + 1) % n], C[k]))
                f[self.li] = i
                f[self.lk] = k
        caps = ([self.bm.faces.new(rings[0][::-1])] if cap_start else []) + ([self.bm.faces.new(rings[-1])] if cap_end else [])
        for f in caps:
            f[self.li] = -1
            f[self.lk] = -1
        return rings

    def cap_with_hole(self, rim_verts, hole_pts, reverse=False):
        """把放樣末端的頂點環（rim）與一圈新的洞邊點列橋接成環帶，洞再補成一個 ngon。回傳 (環帶面, 洞面)。"""
        hole_verts = [self.bm.verts.new(Vector(p)) for p in hole_pts]
        rim_edges = [self.bm.edges.get((rim_verts[i], rim_verts[(i + 1) % len(rim_verts)])) for i in range(len(rim_verts))]
        hole_edges = [self.bm.edges.new((hole_verts[i], hole_verts[(i + 1) % len(hole_verts)])) for i in range(len(hole_verts))]
        res = bmesh.ops.bridge_loops(self.bm, edges=rim_edges + hole_edges)
        hole_face = self.bm.faces.new(hole_verts[::-1] if reverse else hole_verts)
        for f in res["faces"] + [hole_face]:
            f[self.li] = -1
            f[self.lk] = -1
        return res["faces"], hole_face

    def rings(self, rings3d, cap_start=False, cap_end=False, pole=None):
        """一串同點數的 3D 環連成面（球冠、帽子）。pole 給了就從最後一環收到一個頂點。"""
        R = [[self.bm.verts.new(Vector(p)) for p in ring] for ring in rings3d]
        for i in range(len(R) - 1):
            A, C = R[i], R[i + 1]
            n = len(A)
            for k in range(n):
                self.bm.faces.new((A[k], A[(k + 1) % n], C[(k + 1) % n], C[k]))
        if cap_start:
            self.bm.faces.new(R[0][::-1])
        if pole is not None:
            pv = self.bm.verts.new(Vector(pole))
            last = R[-1]
            for k in range(len(last)):
                self.bm.faces.new((last[k], last[(k + 1) % len(last)], pv))
        elif cap_end:
            self.bm.faces.new(R[-1])

    def done(self, name):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        self.bm.normal_update()
        grp, groups = self.grp, self.groups

        def fmat(f):
            rid = f[grp]
            if rid == 0:
                return T.mats()["bark"]
            m = groups[rid - 1][0]
            return m(f) if callable(m) else m

        def spred(f):
            rid = f[grp]
            return rid > 0 and groups[rid - 1][1]
        return T.build(self.bm, name, face_mat=fmat, smooth_pred=spred)


def rounded_ring(w, z0, z1, rb, rt, kc=3, nb=2, ns=1, nt=4):
    """(y,z) 平面上的圓角矩形封閉折線，點數固定（給 loft 用）。"""
    rb = min(rb, w * 0.9, (z1 - z0) * 0.45)
    rt = min(rt, w * 0.95, (z1 - z0) * 0.5)

    def seg(p0, p1, n):
        return [(p0[0] + (p1[0] - p0[0]) * (i + 1) / (n + 1), p0[1] + (p1[1] - p0[1]) * (i + 1) / (n + 1)) for i in range(n)]

    def arc(cy, cz, r, a0, a1, k):
        return [(cy + r * math.cos(a0 + (a1 - a0) * i / (k - 1)), cz + r * math.sin(a0 + (a1 - a0) * i / (k - 1))) for i in range(k)]

    bl, br = (-w + rb, z0), (w - rb, z0)
    pts = [bl] + seg(bl, br, nb) + [br]
    pts += arc(w - rb, z0 + rb, rb, -math.pi / 2, 0, kc)[1:]
    r0, r1 = (w, z0 + rb), (w, z1 - rt)
    pts += seg(r0, r1, ns) + [r1]
    pts += arc(w - rt, z1 - rt, rt, 0, math.pi / 2, kc)[1:]
    t0, t1 = (w - rt, z1), (-w + rt, z1)
    pts += seg(t0, t1, nt) + [t1]
    pts += arc(-w + rt, z1 - rt, rt, math.pi / 2, math.pi, kc)[1:]
    l0, l1 = (-w, z1 - rt), (-w, z0 + rb)
    pts += seg(l0, l1, ns) + [l1]
    pts += arc(-w + rb, z0 + rb, rb, math.pi, 1.5 * math.pi, kc)[1:-1]
    return pts


# ---------------------------------------------------------------- 圓角盒子放樣

def _loft_box(b, x0, x1, w, z0, z1, r_end=0.25, r_top=0.25, rb=0.08, rt=0.2, arches=(), arch_r=0.0, arch_z=0.0, nx=6):
    """沿 X 放樣的圓角盒子：兩端在平面與頂部都收圓；可在指定 x 挖輪拱。"""
    def prof(x):
        ww, zz1 = w, z1
        for d in (x - x0, x1 - x):
            if d < r_end:
                ww = min(ww, w - r_end + math.sqrt(max(r_end ** 2 - (r_end - d) ** 2, 0.0)))
            if d < r_top:
                zz1 = min(zz1, z1 - r_top + math.sqrt(max(r_top ** 2 - (r_top - d) ** 2, 0.0)))
        zz0 = z0
        for ax in arches:
            dd = abs(x - ax)
            if dd < arch_r:
                zz0 = max(zz0, arch_z + math.sqrt(arch_r ** 2 - dd ** 2) * 0.92 + 0.02)
        return ww, zz0, zz1

    xs = {x0, x1}
    r = max(r_end, r_top)
    for k in range(1, 9):
        t = (k / 9.0) ** 1.6 * r
        xs.add(x0 + t)
        xs.add(x1 - t)
    for ax in arches:
        for k in range(-6, 7):
            xx = ax + arch_r * 1.05 * k / 6.0
            if x0 < xx < x1:
                xs.add(xx)
    for k in range(1, nx):
        xs.add(x0 + (x1 - x0) * k / nx)
    b.loft([(x, rounded_ring(*prof(x), rb, rt)) for x in sorted(xs)])


# ---------------------------------------------------------------- 豆子形放樣（超橢圓，處處圓角）

# bean_ring 的點索引（共 24 點）：右側 6=腰帶 7=窗下 8=窗上 9=頂角起；10=右45° 11=右頂角 12..15 頂邊 16=左頂角 17=左45°
# 18=左頂角起 19=窗上 20=窗下 21=腰帶。面 k 介於點 k 與 k+1 之間。
K_WIN_R, K_WIN_L = 7, 19            # 側窗玻璃面
K_WS = range(10, 17)                # 環繞式前擋：右 45° → 頂 → 左 45°
K_RW = range(11, 16)                # 後窗：只有頂邊


def bean_ring(w, z0, z1, rb, rt, zb, zwl, zwh, kc=3, nb=2, nt=4):
    """(y,z) 平面的圓角矩形封閉折線。側邊依序有腰帶 zb、窗下緣 zwl、窗上緣 zwh 三排點：
    雙色分界落在 zb，側窗玻璃就是 zwl–zwh 之間那排面（車殼直接開孔換材質）。點數固定 24。"""
    rb = min(rb, w * 0.9, (z1 - z0) * 0.4)
    rt = min(rt, w * 0.95, (z1 - z0) * 0.5)
    zb = min(max(zb, z0 + rb + 0.02), z1 - rt - 0.02)
    zwl = min(max(zwl, zb), z1 - rt)
    zwh = min(max(zwh, zwl), z1 - rt)

    def seg(p0, p1, n):
        return [(p0[0] + (p1[0] - p0[0]) * (i + 1) / (n + 1), p0[1] + (p1[1] - p0[1]) * (i + 1) / (n + 1)) for i in range(n)]

    def arc(cy, cz, r, a0, a1, k):
        return [(cy + r * math.cos(a0 + (a1 - a0) * i / (k - 1)), cz + r * math.sin(a0 + (a1 - a0) * i / (k - 1))) for i in range(k)]

    bl, br = (-w + rb, z0), (w - rb, z0)
    pts = [bl] + seg(bl, br, nb) + [br]
    pts += arc(w - rb, z0 + rb, rb, -math.pi / 2, 0, kc)[1:]
    pts += [(w, zb), (w, zwl), (w, zwh), (w, z1 - rt)]
    pts += arc(w - rt, z1 - rt, rt, 0, math.pi / 2, kc)[1:]
    t0, t1 = (w - rt, z1), (-w + rt, z1)
    pts += seg(t0, t1, nt) + [t1]
    pts += arc(-w + rt, z1 - rt, rt, math.pi / 2, math.pi, kc)[1:]
    pts += [(-w, zwh), (-w, zwl), (-w, zb), (-w, z0 + rb)]
    pts += arc(-w + rb, z0 + rb, rb, math.pi, 1.5 * math.pi, kc)[1:-1]
    return pts


def _loft_bean(b, x0, x1, w, z0, z1, z_end, belt, p=4.0, q=2.8, rb=0.18, rt=0.42,
               arches=(), arch_r=0.0, arch_z=0.0, n=44, lift=0.22, u_max=0.985, win=(0.12, 0.06)):
    """豆子形車身：平面輪廓是超橢圓 (x/hl)^p + (y/w)^p = 1，頂部輪廓是超橢圓 q，底部往兩端上翹。
    回傳 dict：prof(x)→(半寬, 底, 頂)、belt_at(x)、win_z(x)→(zb, zwl, zwh)、xs（各段 x）、ring3d(x, off)（環的 3D 點，可沿法線外推）。"""
    cx, hl = (x0 + x1) / 2, (x1 - x0) / 2

    def prof(x):
        au = min(abs(x - cx) / hl, 0.9999)
        ww = w * (1 - au ** p) ** (1 / p)
        zz1 = z_end + (z1 - z_end) * (1 - au ** q) ** (1 / q)
        zz0 = z0 + lift * (max(au - 0.72, 0.0) / 0.28) ** 2
        for ax in arches:
            dd = abs(x - ax)
            if dd < arch_r:
                zz0 = max(zz0, arch_z + math.sqrt(arch_r ** 2 - dd ** 2) * 0.92 + 0.02)
        return ww, zz0, max(zz1, zz0 + 0.15)

    def win_z(x):
        ww, zz0, zz1 = prof(x)
        rbb = min(rb, ww * 0.9, (zz1 - zz0) * 0.4)
        rtt = min(rt, ww * 0.95, (zz1 - zz0) * 0.5)
        zb = min(max(belt, zz0 + rbb + 0.02), zz1 - rtt - 0.02)
        zwl = min(max(zb + win[0], zb), zz1 - rtt)
        zwh = min(max(zz1 - rtt - win[1], zwl), zz1 - rtt)
        return zb, zwl, zwh

    def ring2d(x):
        ww, zz0, zz1 = prof(x)
        return bean_ring(ww, zz0, zz1, rb, rt, *win_z(x))

    def ring3d(x, off=0.0):
        ww, zz0, zz1 = prof(x)
        cz = (zz0 + zz1) / 2
        out = []
        for y, z in ring2d(x):
            d = Vector((0, y, z - cz))
            d = d.normalized() if d.length > 1e-6 else Vector((0, 0, 1))
            out.append(Vector((x, y, z)) + d * off)
        return out

    us = [math.copysign(abs(-1 + 2 * k / (n - 1)) ** 0.75, -1 + 2 * k / (n - 1)) * u_max for k in range(n)]
    xs = [cx + u * hl for u in us]
    b.loft([(x, ring2d(x)) for x in xs])
    return dict(prof=prof, belt_at=lambda x: win_z(x)[0], win_z=win_z, xs=xs, ring3d=ring3d)


def _bean_outline(t, hl, w, p, scale=1.0):
    """超橢圓平面輪廓的參數式：t ∈ [0, 2π)，0 在車頭。"""
    c, s_ = math.cos(t), math.sin(t)
    return (hl * scale * math.copysign(abs(c) ** (2 / p), c), w * scale * math.copysign(abs(s_) ** (2 / p), s_))


def _rrect(hw, hh, r, k=4):
    """圓角矩形 (u,v) 點列，逆時針。"""
    r = min(r, hw, hh)
    pts = []
    for (su, sv, a0) in ((1, 1, 0.0), (-1, 1, math.pi / 2), (-1, -1, math.pi), (1, -1, 1.5 * math.pi)):
        for i in range(k):
            a = a0 + (math.pi / 2) * i / (k - 1)
            pts.append((su * (hw - r) + r * math.cos(a), sv * (hh - r) + r * math.sin(a)))
    return pts


def rwin(b, c, u, v, hw, hh, r, t):
    """圓角矩形厚板：中心 c 在表面上，平面由 u,v 張成，往外法線 n = u×v，厚度 t 往外長。"""
    c, u, v = Vector(c), Vector(u).normalized(), Vector(v).normalized()
    n = u.cross(v).normalized()
    b.slab([c + u * pu + v * pv + n * t for pu, pv in _rrect(hw, hh, r)], t)


def _sect_range(xs, xa, xb):
    """把 [xa, xb] 對齊到放樣段：回傳 (ia, ib)，玻璃面 = 段 ia..ib-1（即介於 xs[ia] 與 xs[ib] 之間）。"""
    ia = min(i for i, x in enumerate(xs) if x >= xa - 1e-6)
    ib = max(i for i, x in enumerate(xs) if x <= xb + 1e-6)
    return ia, ib


def _frame_loop(b, bean, ia, ib, k0, k1, off, r):
    """沿放樣面區域（段 ia..ib、點 k0..k1）的邊界繞一圈鍍鉻管，四角放球讓接頭圓潤。"""
    xs, ring3d = bean["xs"], bean["ring3d"]
    loop = [ring3d(xs[ia], off)[k] for k in range(k0, k1 + 1)]
    loop += [ring3d(xs[i], off)[k1] for i in range(ia + 1, ib + 1)]
    loop += [ring3d(xs[ib], off)[k] for k in range(k1 - 1, k0 - 1, -1)]
    loop += [ring3d(xs[i], off)[k0] for i in range(ib - 1, ia, -1)]
    loop.append(loop[0])
    T.add_tube2(b.bm, loop, [r] * len(loop), segs=8, cap_start=True, cap_end=True)
    for pnt in (ring3d(xs[ia], off)[k0], ring3d(xs[ia], off)[k1], ring3d(xs[ib], off)[k0], ring3d(xs[ib], off)[k1]):
        b.sphere(pnt, r * 1.05)


def _loft_rounded(b, x0, x1, w, z0, z1, r_end, r_top, ring_fn, arches=(), arch_r=0.0, arch_z=0.0, nx=30,
                  cap_start=True, cap_end=True):
    """沿 X 放樣的圓角盒子（兩端平面與頂部都收圓、可挖輪拱），剖面由 ring_fn(ww, zz0, zz1) 產生。
    回傳 dict：prof、xs、ring3d(x, off)、rings（每段頂點環）。"""
    def prof(x):
        ww, zz1 = w, z1
        for d in (x - x0, x1 - x):
            if d < r_end:
                ww = min(ww, w - r_end + math.sqrt(max(r_end ** 2 - (r_end - d) ** 2, 0.0)))
            if d < r_top:
                zz1 = min(zz1, z1 - r_top + math.sqrt(max(r_top ** 2 - (r_top - d) ** 2, 0.0)))
        zz0 = z0
        for ax in arches:
            dd = abs(x - ax)
            if dd < arch_r:
                zz0 = max(zz0, arch_z + math.sqrt(arch_r ** 2 - dd ** 2) * 0.92 + 0.02)
        return ww, zz0, max(zz1, zz0 + 0.05)

    xs = {x0, x1}
    r = max(r_end, r_top)
    for k in range(1, 9):
        t = (k / 9.0) ** 1.6 * r
        xs.add(x0 + t)
        xs.add(x1 - t)
    for ax in arches:
        for k in range(-6, 7):
            xx = ax + arch_r * 1.05 * k / 6.0
            if x0 < xx < x1:
                xs.add(xx)
    for k in range(1, nx):
        xs.add(x0 + (x1 - x0) * k / nx)
    xs = sorted(xs)

    def ring3d(x, off=0.0):
        ww, zz0, zz1 = prof(x)
        cz = (zz0 + zz1) / 2
        out = []
        for y, z in ring_fn(ww, zz0, zz1):
            d = Vector((0, y, z - cz))
            d = d.normalized() if d.length > 1e-6 else Vector((0, 0, 1))
            out.append(Vector((x, y, z)) + d * off)
        return out

    rings = b.loft([(x, ring_fn(*prof(x))) for x in xs], cap_start=cap_start, cap_end=cap_end)
    return dict(prof=prof, xs=xs, ring3d=ring3d, rings=rings)


def _box_outline(x0, x1, w, r, off=0.0, k=6):
    """圓角矩形平面輪廓（車身俯視）閉合點列，從車尾中央開始逆時針。"""
    pts = []
    corners = ((x1 - r, w - r, 0.0), (x0 + r, w - r, math.pi / 2), (x0 + r, -w + r, math.pi), (x1 - r, -w + r, 1.5 * math.pi))
    pts.append((x0 - off, 0.0))
    for (cx_, cy_, a0) in (corners[1], corners[2], corners[3], corners[0]):
        for i in range(k):
            a = a0 + (math.pi / 2) * i / (k - 1)
            pts.append((cx_ + (r + off) * math.cos(a), cy_ + (r + off) * math.sin(a)))
    pts.append(pts[0])
    return pts


# ---------------------------------------------------------------- Q 版復古露營車（鳥山明 × 薩爾達 Diorama）

def camper_van(name, awning=True):
    """Q 版復古露營車（方正版）：上下兩截圓角盒子——下截薄荷綠、上截奶油黃，接縫是鍍鉻腰帶；前後臉是平的，
    前擋／後窗是臉上真正開的大圓角矩形孔（bridge_loops），側窗是車殼面直接換玻璃；內裝殼、座椅、方向盤、床；
    腰帶線上兩顆圓頭燈（鍍鉻框 + 燈泡 + 半透明燈罩）；圓角行李架上睡袋＋保冷箱；小胖氣球胎。"""
    m = pm()
    b = B()
    X0, X1, W, Z0, BELT, Z1 = -1.5, 1.5, 0.95, 0.34, 0.86, 1.85
    R_END, R_TOP = 0.11, 0.11          # 邊緣圓角：小到剛好不出現尖角
    WX, WZ, ARCH = 0.95, 0.30, 0.35
    TR, TRR, TY = 0.18, 0.12, 0.88

    # ---- 下截（薄荷綠）：底部圓角、頂部幾乎方（貼腰帶），挖輪拱
    low = _loft_rounded(b, X0, X1, W, Z0, BELT + 0.01, R_END, 0.04,
                        lambda ww, zz0, zz1: rounded_ring(ww, zz0, zz1, 0.10, 0.04),
                        arches=(-WX, WX), arch_r=ARCH, arch_z=WZ, nx=30)

    def low_mat(f):
        c = f.calc_center_median()
        n = f.normal
        if n.z < -0.55:
            return m["darkMetal"]
        for ax in (-WX, WX):
            if c.z < WZ + ARCH + 0.05 and abs(c.x - ax) < ARCH + 0.05 and abs(n.y) < 0.85 and n.z < 0.3:
                return m["darkMetal"]
        return m["vanMint"]
    b.use(low_mat, smooth=True)

    # ---- 上截（奶油黃）：頂部圓角、底部貼腰帶；側邊有窗上下緣兩排點；前後不封口，改成帶窗孔的臉
    RT_SEC = 0.12   # 剖面頂部圓角

    def band(zz0, zz1):
        """側窗帶（也是前擋／後窗的垂直範圍）：腰帶上緣一點到頂部圓角下一點。"""
        rtt = min(RT_SEC, (zz1 - zz0) * 0.5)
        zb = zz0 + 0.06
        return zb, zb + 0.08, zz1 - rtt - 0.03

    def up_ring(ww, zz0, zz1):
        zb, zwl, zwh = band(zz0, zz1)
        return bean_ring(ww, zz0, zz1, 0.04, RT_SEC, zb, zwl, zwh)
    up = _loft_rounded(b, X0, X1, W, BELT - 0.01, Z1, R_END, R_TOP, up_ring, nx=30, cap_start=False, cap_end=False)
    # 側窗兩扇 + 前後「環繞角窗」（A 柱／C 柱兩側，貼著前後臉）
    side = [_sect_range(up["xs"], -0.84, -0.20), _sect_range(up["xs"], 0.02, 0.62),
            _sect_range(up["xs"], X1 - 0.36, X1), _sect_range(up["xs"], X0, X0 + 0.28)]

    def up_mat(f):
        li, lk = f[b.li], f[b.lk]
        if li >= 0:
            for ia, ib in side:
                if ia <= li < ib and lk in (K_WIN_R, K_WIN_L):
                    return m["glass"]
        return m["vanCreamY"]
    b.use(up_mat, smooth=True)

    # 前臉：外緣 → 前擋孔；後臉：外緣 → 後窗孔
    cap_w = W - R_END
    f_ww, f_z0, f_z1 = up["prof"](X1)
    _, f_zwl, f_zwh = band(f_z0, f_z1)
    # 前擋：幾乎整張臉的寬度（只留 A 柱），高度＝側窗帶，與兩側角窗連成環繞式
    ws_c, ws_hw, ws_hh, ws_r = (f_zwl + f_zwh) / 2, cap_w - 0.06, (f_zwh - f_zwl) / 2, 0.09
    ws_pts = [(X1, u_, v_) for u_, v_ in [(pu, ws_c + pv) for pu, pv in _rrect(ws_hw, ws_hh, ws_r, k=5)]]
    band_f, ws_face = b.cap_with_hole(up["rings"][-1], ws_pts)
    b.use(m["vanCreamY"], smooth=True)
    rw_c, rw_hw, rw_hh, rw_r = ws_c, cap_w - 0.14, ws_hh, 0.09
    rw_pts = [(X0, u_, v_) for u_, v_ in [(pu, rw_c + pv) for pu, pv in _rrect(rw_hw, rw_hh, rw_r, k=5)]]
    band_r, rw_face = b.cap_with_hole(up["rings"][0], rw_pts)
    b.use(m["vanCreamY"], smooth=True)
    b.bm.faces.ensure_lookup_table()
    # 玻璃面：把剛才兩個洞面歸到 glass（用 grp 直接改）
    for f in (ws_face, rw_face):
        f[b.grp] = 0
    b.use(m["glass"], smooth=False)

    # ---- 內裝：沒有第二層內殼（之前那層把座椅整個封在裡面，從窗外只看得到一片深色牆）。
    #      車殼材質在 Godot 端設雙面，內壁就是車身色；地板、座椅、床、儀表板、方向盤直接放在艙內。
    b.box((0, 0, Z0 + 0.02), (2.7, 1.6, 0.06))
    b.use(m["interiorDark"])
    b.box((0, 0, 0.30), (2.2, 1.3, 0.14))
    b.use(m["darkMetal"])
    for sy in (-1, 1):
        b.box((0.45, sy * 0.30, Z0 + 0.56), (0.36, 0.34, 0.12))
        b.box((0.26, sy * 0.30, Z0 + 0.86), (0.09, 0.34, 0.50), ry=-0.15)
        b.sphere((0.24, sy * 0.30, Z0 + 1.12), 0.09)
    b.box((-0.85, 0, Z0 + 0.50), (0.70, 1.10, 0.24))
    b.use(m["bagCoral"])
    b.box((-1.05, 0, Z0 + 0.68), (0.28, 0.40, 0.10))
    b.use(m["vanCreamY"])
    b.box((1.22, 0, Z0 + 0.60), (0.22, 1.30, 0.10))
    b.use(m["darkMetal"])
    b.torus((0.95, 0.30, Z0 + 0.88), 0.11, 0.018, axis='X')
    b.use(m["white"], smooth=True)

    # ---- 窗框（鍍鉻管，微凸）：前擋、後窗沿孔緣；側窗沿開孔邊界
    for pts, x_off in ((ws_pts, 0.012), (rw_pts, -0.012)):
        loop = [Vector((x + x_off, y, z)) for x, y, z in pts] + [Vector((pts[0][0] + x_off, pts[0][1], pts[0][2]))]
        T.add_tube2(b.bm, loop, [0.024] * len(loop), segs=8, cap_start=True, cap_end=True)
    for ia, ib in side:
        _frame_loop(b, up, ia, ib, K_WIN_R, K_WIN_R + 1, 0.012, 0.022)
        _frame_loop(b, up, ia, ib, K_WIN_L, K_WIN_L + 1, 0.012, 0.022)
    # 腰帶鍍鉻條（沿俯視輪廓一圈）、前後保險桿
    belt_loop = [Vector((x, y, BELT)) for x, y in _box_outline(X0, X1, W, R_END, 0.012)]
    T.add_tube2(b.bm, belt_loop, [0.03] * len(belt_loop), segs=8, cap_start=True, cap_end=True)
    for sx in (1, -1):
        xe = X1 if sx > 0 else X0
        pts = []
        for sy in (1, -1):
            cx_, cy_ = xe - sx * R_END, sy * (W - R_END)
            # 右側：側邊 → 臉；左側：臉 → 側邊（整條保險桿是一筆畫）
            if sx > 0:
                angs = [90 - 90 * i / 5 for i in range(6)] if sy > 0 else [360 - 90 * i / 5 for i in range(6)]
            else:
                angs = [90 + 90 * i / 5 for i in range(6)] if sy > 0 else [180 + 90 * i / 5 for i in range(6)]
            pts += [Vector((cx_ + (R_END + 0.06) * math.cos(math.radians(a)), cy_ + (R_END + 0.06) * math.sin(math.radians(a)), 0.50)) for a in angs]
        pts = [pts[0] + Vector((-sx * 0.18, 0, 0))] + pts + [pts[-1] + Vector((-sx * 0.18, 0, 0))]
        T.add_tube2(b.bm, pts, [0.06] * len(pts), segs=10, cap_start=True, cap_end=True)
    b.use(m["chrome"], smooth=True)

    # ---- 圓頭燈（縮小）：騎在腰帶線上
    HL_Z = BELT - 0.03
    for sy in (-1, 1):
        b.cyl((X1 + 0.05, sy * 0.46, HL_Z), 0.15, 0.16, segs=22, axis='X')
    b.use(m["chrome"], smooth=True)
    for sy in (-1, 1):
        b.sphere((X1 + 0.08, sy * 0.46, HL_Z), 0.09, sub=2)
    b.use(m["white"], smooth=True)
    for sy in (-1, 1):
        b.sphere((X1 + 0.13, sy * 0.46, HL_Z), 0.13, sub=2, scale=(0.5, 1, 1))
    b.use(m["headlightGlass"], smooth=True)
    # 水箱罩＋橫條、雨刷
    b.box((X1 + 0.012, 0, 0.64), (0.024, 0.30, 0.11))
    b.use(m["darkMetal"])
    for k in range(3):
        b.box((X1 + 0.03, 0, 0.61 + k * 0.035), (0.02, 0.26, 0.012))
    b.use(m["chrome"])
    for sy in (-1, 1):
        base = Vector((X1 + 0.03, sy * 0.34, ws_c - ws_hh + 0.02))
        b.rod(base, base + Vector((0, sy * 0.10, 0.40)), 0.007)
    b.use(m["darkMetal"], smooth=True)

    # ---- 門把、後視鏡
    for sy in (-1, 1):
        b.box((-0.05, sy * (W + 0.014), 0.72), (0.12, 0.024, 0.03))
        b.rod((X1 - 0.44, sy * 0.92, 1.30), (X1 - 0.44, sy * 1.08, 1.38), 0.012)
        b.cyl((X1 - 0.44, sy * 1.12, 1.38), 0.08, 0.03, segs=14, axis='X')
    b.use(m["chrome"], smooth=True)
    for sy in (-1, 1):
        b.cyl((X1 - 0.46, sy * 1.12, 1.38), 0.06, 0.012, segs=14, axis='X')
    b.use(m["glass"], smooth=True)

    # ---- 尾燈、車牌、排氣管
    for sy in (-1, 1):
        b.cyl((X0 - 0.04, sy * 0.44, 0.70), 0.10, 0.12, segs=18, axis='X')
    b.use(m["chrome"], smooth=True)
    for sy in (-1, 1):
        b.sphere((X0 - 0.09, sy * 0.44, 0.70), 0.08, sub=2, scale=(0.6, 1, 1))
    b.use(m["tailRed"], smooth=True)
    b.box((X0 - 0.012, 0, 0.66), (0.02, 0.26, 0.09))
    b.use(m["white"])
    b.cyl((X0 + 0.02, -0.55, 0.40), 0.03, 0.22, segs=10, axis='X')
    b.use(m["chrome"], smooth=True)

    # ---- 小胖氣球胎 + 奶油黃輪蓋 + 鍍鉻中心
    for wx in (-WX, WX):
        for sy in (-1, 1):
            b.torus((wx, sy * TY, WZ), TR, TRR, axis='Y')
    b.use(m["rubber"], smooth=True)
    for wx in (-WX, WX):
        for sy in (-1, 1):
            b.cyl((wx, sy * TY, WZ), 0.115, 0.25, segs=18, axis='Y')
    b.use(m["vanCreamY"], smooth=True)
    for wx in (-WX, WX):
        for sy in (-1, 1):
            b.sphere((wx, sy * (TY + 0.125), WZ), 0.04)
    b.use(m["chrome"], smooth=True)

    # ---- 圓角行李架 + 睡袋 + 保冷箱
    RZ = Z1 + 0.07
    rack = []
    for (cx_, cy_, a0) in ((0.72 - 0.16, 0.50 - 0.16, 0.0), (-0.82 + 0.16, 0.50 - 0.16, math.pi / 2),
                           (-0.82 + 0.16, -0.50 + 0.16, math.pi), (0.72 - 0.16, -0.50 + 0.16, 1.5 * math.pi)):
        for k in range(6):
            a = a0 + (math.pi / 2) * k / 5
            rack.append(Vector((cx_ + 0.16 * math.cos(a), cy_ + 0.16 * math.sin(a), RZ)))
    rack.append(rack[0])
    T.add_tube2(b.bm, rack, [0.026] * len(rack), segs=8, cap_start=True, cap_end=True)
    for x in (-0.74, 0.64):
        for sy in (-1, 1):
            b.cyl((x, sy * 0.46, RZ - 0.06), 0.02, 0.16, segs=8)
    for x in (-0.55, 0.35):
        b.cyl((x, 0, RZ), 0.02, 0.96, segs=8, axis='Y')
    b.use(m["chrome"], smooth=True)
    b.cyl((-0.30, 0, RZ + 0.22), 0.19, 0.86, segs=16, axis='Y')
    for sy in (-1, 1):
        b.sphere((-0.30, sy * 0.43, RZ + 0.22), 0.19, sub=2, scale=(1, 0.45, 1))
    b.use(m["bagCoral"], smooth=True)
    for sy in (-1, 1):
        b.cyl((-0.30, sy * 0.26, RZ + 0.22), 0.20, 0.05, segs=16, axis='Y')
    b.cyl((-0.30, 0, RZ + 0.22), 0.06, 0.88, segs=10, axis='Y')
    b.use(m["vanCreamY"], smooth=True)
    _loft_box(b, 0.22, 0.58, 0.14, RZ + 0.03, RZ + 0.27, r_end=0.06, r_top=0.04, rb=0.04, rt=0.04, nx=2)
    b.use(m["coolerBlue"], smooth=True)
    _loft_box(b, 0.21, 0.59, 0.15, RZ + 0.265, RZ + 0.33, r_end=0.05, r_top=0.03, rb=0.02, rt=0.03, nx=2)
    b.use(m["vanCreamY"], smooth=True)
    b.box((0.40, 0.0, RZ + 0.36), (0.16, 0.03, 0.02))
    for dx in (-0.07, 0.07):
        b.box((0.40 + dx, 0.0, RZ + 0.345), (0.02, 0.03, 0.03))
    b.use(m["chrome"])

    # ---- 側邊遮陽棚（+Y）
    if awning:
        z_att, out, tilt = 1.56, 1.5, 0.18
        y0 = W
        b.box((-0.10, y0 - 0.005, z_att), (1.6, 0.03, 0.03))
        b.use(m["chrome"], smooth=True)
        cy = y0 + out / 2 * math.cos(tilt)
        cz = z_att - out / 2 * math.sin(tilt)
        for i in range(0, 4, 2):
            b.box((-0.85 + 0.1875 + i * 0.375, cy, cz), (0.375, out, 0.03), rx=-tilt)
        b.use(m["canvas"])
        for i in range(1, 4, 2):
            b.box((-0.85 + 0.1875 + i * 0.375, cy, cz), (0.375, out, 0.03), rx=-tilt)
        y_far = y0 + out * math.cos(tilt)
        z_far = z_att - out * math.sin(tilt)
        b.box((-0.10, y_far + 0.02, z_far - 0.03), (1.52, 0.06, 0.08), rx=-tilt)
        b.use(m["vanMint"])
        for x in (-0.80, 0.60):
            b.cyl((x, y_far, z_far / 2), 0.024, z_far, segs=8)
        b.use(m["woodPole"], smooth=True)
        for x in (-0.80, 0.60):
            b.rod((x, y_far, z_far), (x + (0.35 if x > 0 else -0.35), y_far + 0.5, 0.0), 0.008)
        b.use(m["rope"])
        for x in (-0.80, 0.60):
            b.box((x + (0.35 if x > 0 else -0.35), y_far + 0.5, 0.07), (0.05, 0.05, 0.14))
        b.use(m["woodPole"])
    return b.done(name)


# ---------------------------------------------------------------- SD 機甲風 cab-over 露營車（車頭 +X，遮陽棚／側門在 +Y）

def camper_van_alcove(name):
    """（保留：cab-over）駕駛艙上方凸出睡艙（alcove）的露營車，Super-Deformed 比例：短、高、圓、厚。
    細節：氣球胎、分段式輪弧護板＋鉚釘、面板分割線、圓形舷窗、側門＋踏板、車頂冷氣／太陽能板／天窗／行李架、
    車尾梯子／備胎／尾燈、大後視鏡、雨刷、條紋遮陽棚。"""
    m = pm()
    b = B()
    W_BOX, W_CAB = 0.95, 0.84
    Z0, Z_CAB, Z1 = 0.62, 1.95, 2.65
    X_R, X_MID, X_F, X_ALC = -1.85, 0.55, 1.78, 2.02
    WX_F, WX_R, WZ = 1.12, -1.12, 0.44
    TR, TRR, TY = 0.27, 0.15, 0.95
    ARCH = 0.50
    BELT = 1.28

    def under_mat(f, body):
        c = f.calc_center_median()
        n = f.normal
        if n.z < -0.6:
            return m["darkMetal"]
        for ax in (WX_F, WX_R):
            if c.z < WZ + ARCH + 0.05 and abs(c.x - ax) < ARCH + 0.05 and abs(n.y) < 0.9:
                return m["darkMetal"]
        return body

    # 生活箱、睡艙、駕駛艙
    _loft_box(b, X_R, X_MID + 0.05, W_BOX, Z0, Z1, r_end=0.30, r_top=0.32, rb=0.10, rt=0.28, arches=(WX_R,), arch_r=ARCH, arch_z=WZ)
    b.use(lambda f: under_mat(f, m["vanCream"]), smooth=True)
    _loft_box(b, X_MID - 0.05, X_ALC, W_BOX, Z_CAB, Z1, r_end=0.30, r_top=0.18, rb=0.14, rt=0.18)
    b.use(m["vanCream"], smooth=True)
    _loft_box(b, X_MID - 0.05, X_F, W_CAB, Z0, Z_CAB + 0.04, r_end=0.30, r_top=0.20, rb=0.10, rt=0.16, arches=(WX_F,), arch_r=ARCH, arch_z=WZ)
    b.use(lambda f: under_mat(f, m["vanPaint"]), smooth=True)
    # 底盤
    b.box(((X_R + X_F) / 2, 0, Z0 - 0.04), (X_F - X_R - 0.3, 1.32, 0.24))
    b.use(m["darkMetal"])
    # 腰帶（紅）
    b.box(((X_R + X_MID) / 2 + 0.03, 0, BELT), (X_MID - X_R - 0.32, 2 * W_BOX + 0.012, 0.12))
    b.box((X_R - 0.006, 0, BELT), (0.014, 1.30, 0.12))
    b.use(m["vanPaint"])
    # 面板分割線（深灰細條）：腰帶上下緣、側門外框、駕駛艙門縫
    for sy in (-1, 1):
        for dz in (-0.075, 0.075):
            b.box(((X_R + X_MID) / 2 + 0.03, sy * (W_BOX + 0.008), BELT + dz), (X_MID - X_R - 0.32, 0.012, 0.016))
        b.box((0.82, sy * (W_CAB + 0.006), (Z0 + Z_CAB) / 2 + 0.1), (0.016, 0.012, Z_CAB - Z0 - 0.5))
    for x in (-0.35, 0.30):
        b.box((x, W_BOX + 0.006, (Z0 + 2.15) / 2 + 0.03), (0.016, 0.012, 2.15 - Z0 - 0.06))
    b.box((-0.025, W_BOX + 0.006, 2.15), (0.65, 0.012, 0.016))
    b.use(m["darkMetal"])
    # 分段式輪弧護板（紅）＋ 鉚釘
    for wx, wy in ((WX_F, W_CAB), (WX_R, W_BOX)):
        for sy in (-1, 1):
            fw = 1.16 - wy
            for k in range(11):
                a = math.radians(8 + 164 * k / 10)
                # 盒子長軸在 local Z：繞 Y 轉 -a 後 local Z → (-sin a, 0, cos a) = 圓弧切線方向（放在 local X 會變成徑向的齒）
                b.box((wx + (ARCH + 0.06) * math.cos(a), sy * (wy + fw / 2), WZ + (ARCH + 0.06) * math.sin(a)), (0.10, fw, 0.19), ry=-a)
    b.use(m["vanPaint"])
    for wx, wy in ((WX_F, W_CAB), (WX_R, W_BOX)):
        for sy in (-1, 1):
            for k in range(6):
                a = math.radians(22 + 136 * k / 5)
                b.sphere((wx + (ARCH + 0.115) * math.cos(a), sy * 1.10, WZ + (ARCH + 0.115) * math.sin(a)), 0.02)
    for sy in (-1, 1):
        for k in range(7):
            b.sphere((-1.5 + k * 0.3, sy * (W_BOX + 0.012), BELT + 0.105), 0.016)
    b.use(m["chrome"], smooth=True)
    # 氣球胎 + 白邊 + 鍍鉻輪蓋
    for wx in (WX_F, WX_R):
        for sy in (-1, 1):
            b.torus((wx, sy * TY, WZ), TR, TRR, axis='Y')
    b.use(m["rubber"], smooth=True)
    for wx in (WX_F, WX_R):
        for sy in (-1, 1):
            b.cyl((wx, sy * TY, WZ), TR + 0.02, 0.26, segs=20, axis='Y')
    b.use(m["white"], smooth=True)
    for wx in (WX_F, WX_R):
        for sy in (-1, 1):
            b.cyl((wx, sy * TY, WZ), 0.17, 0.30, segs=16, axis='Y')
            b.sphere((wx, sy * (TY + 0.16), WZ), 0.06)
    b.use(m["chrome"], smooth=True)
    # 擋泥板、排氣管
    for sy in (-1, 1):
        b.box((WX_R - 0.50, sy * TY, WZ - 0.14), (0.03, 0.28, 0.30))
    b.use(m["rubber"])
    b.cyl((X_R - 0.02, -0.62, Z0 - 0.06), 0.04, 0.34, segs=10, axis='X')
    b.use(m["darkMetal"], smooth=True)
    b.cyl((X_R - 0.20, -0.62, Z0 - 0.06), 0.05, 0.05, segs=10, axis='X')
    b.use(m["chrome"], smooth=True)

    # ---- 車頭：前擋、頭燈、水箱罩、保險桿、雨刷、後視鏡
    b.box((X_F + 0.006, 0, 1.46), (0.012, 1.04, 0.62))
    b.use(m["chrome"], smooth=True)
    b.box((X_F + 0.012, 0, 1.46), (0.012, 0.98, 0.56))
    b.use(m["glass"], smooth=True)
    for sy in (-1, 1):
        b.rod((X_F + 0.02, sy * 0.30, 1.20), (X_F + 0.02, sy * 0.30 + sy * 0.25, 1.62), 0.008)
        b.rod((X_F + 0.02, sy * 0.30, 1.20), (X_F + 0.02, sy * 0.30 - sy * 0.02, 1.62), 0.008)
    b.use(m["darkMetal"], smooth=True)
    for sy in (-1, 1):
        b.cyl((X_F + 0.02, sy * 0.34, 0.98), 0.15, 0.06, segs=18, axis='X')
    b.use(m["chrome"], smooth=True)
    for sy in (-1, 1):
        b.cyl((X_F + 0.045, sy * 0.34, 0.98), 0.115, 0.05, segs=18, axis='X')
    b.use(m["glass"], smooth=True)
    b.box((X_F + 0.008, 0, 0.98), (0.012, 0.30, 0.22))
    b.use(m["darkMetal"])
    for k in range(4):
        b.box((X_F + 0.016, 0, 0.90 + k * 0.055), (0.012, 0.28, 0.018))
    for x in (X_F + 0.08, X_R - 0.08):
        b.box((x, 0, 0.70), (0.14, 1.56, 0.16))
    b.use(m["chrome"], smooth=True)
    for x in (X_F + 0.10, X_R - 0.10):
        for sy in (-1, 1):
            b.box((x, sy * 0.50, 0.70), (0.16, 0.12, 0.20))
    b.use(m["rubber"])
    for sy in (-1, 1):
        b.rod((X_F - 0.35, sy * W_CAB, 1.45), (X_F - 0.35, sy * (W_CAB + 0.25), 1.58), 0.015)
        b.box((X_F - 0.35, sy * (W_CAB + 0.30), 1.60), (0.05, 0.12, 0.18))
    b.use(m["darkMetal"], smooth=True)
    for sy in (-1, 1):
        b.box((X_F - 0.32, sy * (W_CAB + 0.30), 1.60), (0.012, 0.10, 0.15))
    b.use(m["glass"])
    # 睡艙圓形舷窗
    for sy in (-1, 1):
        b.cyl((X_ALC - 0.02, sy * 0.30, 2.19), 0.15, 0.12, segs=18, axis='X')
    b.use(m["chrome"], smooth=True)
    for sy in (-1, 1):
        b.cyl((X_ALC + 0.005, sy * 0.30, 2.19), 0.115, 0.10, segs=18, axis='X')
    b.use(m["glass"], smooth=True)

    # ---- 側窗（駕駛艙兩側、車廂 -Y 兩扇、+Y 一扇＋門窗）
    wins = [(1.15, 1.51, 0.55, 0.42, W_CAB, (-1, 1)), (-1.05, 1.75, 0.80, 0.50, W_BOX, (-1,)), (0.0, 1.75, 0.60, 0.50, W_BOX, (-1,)),
            (-1.05, 1.75, 0.70, 0.50, W_BOX, (1,)), (-0.025, 1.78, 0.45, 0.36, W_BOX, (1,))]
    for x, z, wd, hg, wy, sides in wins:
        for sy in sides:
            b.box((x, sy * (wy + 0.006), z), (wd + 0.05, 0.012, hg + 0.05))
    b.box((X_R - 0.006, 0, 1.90), (0.012, 0.85, 0.50))
    b.use(m["chrome"], smooth=True)
    for x, z, wd, hg, wy, sides in wins:
        for sy in sides:
            b.box((x, sy * (wy + 0.012), z), (wd, 0.012, hg))
    b.box((X_R - 0.012, 0, 1.90), (0.012, 0.80, 0.45))
    b.use(m["glass"], smooth=True)
    # 側門把手、駕駛艙門把、踏板
    b.box((0.20, W_BOX + 0.02, 1.45), (0.04, 0.03, 0.16))
    for sy in (-1, 1):
        b.box((0.95, sy * (W_CAB + 0.012), 1.12), (0.13, 0.024, 0.035))
    b.use(m["chrome"], smooth=True)
    b.box((-0.025, W_BOX + 0.14, Z0 - 0.06), (0.52, 0.26, 0.05))
    for x in (-0.22, 0.17):
        b.rod((x, W_BOX, Z0 + 0.02), (x, W_BOX + 0.24, Z0 - 0.06), 0.012)
    b.use(m["darkMetal"])

    # ---- 車尾：梯子、備胎、尾燈、車牌
    for y in (-0.46, -0.66):
        b.cyl((X_R - 0.10, y, (0.75 + Z1) / 2), 0.014, Z1 - 0.75, segs=8)
    for k in range(6):
        b.cyl((X_R - 0.10, -0.56, 0.90 + k * 0.32), 0.011, 0.20, segs=6, axis='Y')
    for z in (0.90, 1.86, 2.50):
        for y in (-0.46, -0.66):
            b.rod((X_R - 0.10, y, z), (X_R, y, z), 0.010)
    b.use(m["chrome"], smooth=True)
    b.torus((X_R - 0.16, 0.0, 1.05), 0.24, 0.13, axis='X')
    b.use(m["rubber"], smooth=True)
    b.cyl((X_R - 0.20, 0.0, 1.05), 0.15, 0.10, segs=16, axis='X')
    b.use(m["chrome"], smooth=True)
    for sy in (-1, 1):
        b.box((X_R - 0.012, sy * 0.58, 1.25), (0.024, 0.12, 0.20))
    b.use(m["tailRed"])
    b.box((X_R - 0.012, 0.50, 0.82), (0.014, 0.30, 0.10))
    b.use(m["white"])

    # ---- 車頂：行李架、冷氣、太陽能板、天窗
    for sy in (-1, 1):
        b.cyl((-0.65, sy * 0.62, Z1 + 0.07), 0.02, 2.2, segs=8, axis='X')
        for x in (-1.65, -0.65, 0.35):
            b.cyl((x, sy * 0.62, Z1 + 0.03), 0.015, 0.08, segs=6)
    for x in (-1.65, 0.35):
        b.cyl((x, 0, Z1 + 0.07), 0.016, 1.24, segs=8, axis='Y')
    b.use(m["darkMetal"], smooth=True)
    b.box((-1.15, 0, Z1 + 0.18), (0.62, 0.72, 0.28))
    b.box((1.15, 0, Z1 + 0.05), (0.36, 0.36, 0.07))
    b.use(m["vanCream"])
    for k in range(4):
        b.box((-1.15, -0.24 + k * 0.16, Z1 + 0.325), (0.50, 0.06, 0.012))
    b.box((1.15, 0, Z1 + 0.09), (0.30, 0.30, 0.012))
    b.use(m["darkMetal"])
    b.box((-0.25, 0, Z1 + 0.12), (0.95, 1.10, 0.04))
    b.use(m["solar"], smooth=True)
    for dx in (-0.48, 0.48):
        b.box((-0.25 + dx, 0, Z1 + 0.12), (0.02, 1.12, 0.05))
    for dy in (-0.56, 0.56):
        b.box((-0.25, dy, Z1 + 0.12), (0.97, 0.02, 0.05))
    b.use(m["chrome"])

    # ---- 側邊條紋遮陽棚（+Y，罩住側門與側窗）
    z_att, out, tilt = 2.22, 1.7, 0.18
    cy = W_BOX + out / 2 * math.cos(tilt)
    cz = z_att - out / 2 * math.sin(tilt)
    for i in range(0, 6, 2):
        b.box((-1.56 + i * 0.38, cy, cz), (0.38, out, 0.03), rx=-tilt)
    b.use(m["canvas"])
    for i in range(1, 6, 2):
        b.box((-1.56 + i * 0.38, cy, cz), (0.38, out, 0.03), rx=-tilt)
    y_far = W_BOX + out * math.cos(tilt)
    z_far = z_att - out * math.sin(tilt)
    b.box((-0.61, y_far + 0.02, z_far - 0.03), (2.30, 0.06, 0.08), rx=-tilt)
    b.use(m["canvasTrim"])
    for x in (-1.56, 0.34):
        b.cyl((x, y_far, z_far / 2), 0.024, z_far, segs=8)
    b.use(m["woodPole"], smooth=True)
    for x in (-1.56, 0.34):
        b.rod((x, y_far, z_far), (x + (0.4 if x > 0 else -0.4), y_far + 0.5, 0.0), 0.008)
    b.use(m["rope"])
    for x in (-1.56, 0.34):
        b.box((x + (0.4 if x > 0 else -0.4), y_far + 0.5, 0.07), (0.05, 0.05, 0.14))
    b.use(m["woodPole"])
    return b.done(name)


# ---------------------------------------------------------------- Q 版福斯 T1 露營車（鳥山明機械比例；車頭 +X，遮陽棚在 +Y 側）

def camper_van_t1(name):
    """（保留：Q 版 T1 巴士）短胖圓潤的車身、巨大凸出的輪子、粗管擋泥板、鉚釘與排氣管；VW 的分割前擋／V 形／圓標／鍍鉻保留。"""
    m = pm()
    b = B()
    HX, W, Z0, Z1 = 1.62, 0.95, 0.55, 2.18   # 半長、半寬、底板、車頂
    RP, RR = 0.44, 0.48                      # 平面圓角、車頂前後圓角（都很圓）
    WX, WZ = 1.02, 0.46                      # 輪心 x、輪心 z
    TR, TRR = 0.30, 0.16                     # 氣球胎：主半徑、管半徑（外徑 0.46 ≈ 車高 42%）
    ARCH = 0.54                              # 輪拱半徑
    BELT = 1.22

    def profile(x):
        ax = abs(x)
        w = W
        if ax > HX - RP:
            w = W - RP + math.sqrt(max(RP ** 2 - (ax - (HX - RP)) ** 2, 0.0))
        z1 = Z1
        if ax > HX - RR:
            z1 = Z1 - RR + math.sqrt(max(RR ** 2 - (ax - (HX - RR)) ** 2, 0.0))
        z0 = Z0
        d = abs(ax - WX)
        if d < ARCH:
            z0 = max(z0, WZ + math.sqrt(ARCH ** 2 - d ** 2) * 0.92 + 0.02)
        return w, z0, z1

    xs = sorted(set([-1.62, -1.6, -1.55, -1.47, -1.36, -1.22, -1.1, -1.02, -0.94, -0.8, -0.66, -0.5, -0.38,
                     0.0, 0.38, 0.5, 0.66, 0.8, 0.94, 1.02, 1.1, 1.22, 1.36, 1.47, 1.55, 1.6, 1.62]))
    sections = [(x, rounded_ring(*profile(x), 0.14, 0.52)) for x in xs]
    b.loft(sections)

    def body_mat(f):
        c = f.calc_center_median()
        n = f.normal
        if n.z < -0.6:
            return m["darkMetal"]
        if c.z < WZ + ARCH + 0.05 and abs(abs(c.x) - WX) < ARCH + 0.05 and abs(c.y) < W - 0.05 and abs(n.y) < 0.9:
            return m["darkMetal"]                       # 輪拱內側
        belt = BELT
        if c.x > HX - 0.2 and n.x > 0.5:
            belt = 0.74 + 0.50 * min(abs(c.y) / 0.7, 1.0)   # 前臉 V 形分界
        return m["vanPaint"] if c.z < belt else m["vanCream"]
    b.use(body_mat, smooth=True)

    fw = W - RP + 0.02   # 前後端蓋平面半寬
    b.poly([(HX + 0.004, -fw, Z0 + 0.04), (HX + 0.004, fw, Z0 + 0.04), (HX + 0.004, fw, BELT - 0.04), (HX + 0.004, 0.0, 0.74), (HX + 0.004, -fw, BELT - 0.04)])
    b.poly([(-HX - 0.004, fw, Z0 + 0.04), (-HX - 0.004, -fw, Z0 + 0.04), (-HX - 0.004, -fw, BELT), (-HX - 0.004, fw, BELT)])
    b.box((0, 0, Z0 + 0.1), (2.3, 1.3, 0.2))            # 底盤
    # 粗管擋泥板（車身色）：沿輪拱外緣連續放樣的圓管，凸出車身
    for wx in (-WX, WX):
        for sy in (-1, 1):
            pts, radii = [], []
            for k in range(15):
                a = math.radians(6 + 168 * k / 14)
                pts.append(Vector((wx + (ARCH + 0.03) * math.cos(a), sy * (W + 0.03), WZ + (ARCH + 0.03) * math.sin(a))))
                radii.append(0.07)
            T.add_tube2(b.bm, pts, radii, segs=10, cap_start=True, cap_end=True)
    b.use(m["vanPaint"], smooth=True)
    # V 飾條、腰線、車頂前遮陽板、後視鏡、門把、保險桿、輪蓋、鉚釘、排氣管、大頭燈框、圓標
    for sy in (-1, 1):
        b.rod((HX + 0.015, sy * 0.78, BELT + 0.02), (HX + 0.015, 0.0, 0.745), 0.018)
        b.box((0.0, sy * (W + 0.006), BELT), (2.7, 0.016, 0.035))
    b.box((-HX - 0.01, 0, BELT), (0.016, 1.3, 0.035))
    for sy in (-1, 1):
        b.rod((HX - 0.25, sy * W, 1.55), (HX - 0.25, sy * (W + 0.17), 1.62), 0.014)
        b.box((HX - 0.25, sy * (W + 0.2), 1.64), (0.04, 0.07, 0.12))
        b.box((0.55, sy * (W + 0.012), 1.1), (0.13, 0.024, 0.035))
    for x in (HX + 0.07, -HX - 0.07):
        b.box((x, 0, 0.66), (0.12, 1.86, 0.14))
        for sy in (-1, 1):
            b.box((x, sy * 0.58, 0.70), (0.15, 0.10, 0.22))
    for wx in (-WX, WX):
        for sy in (-1, 1):
            b.cyl((wx, sy * 0.90, WZ), 0.19, 0.30, segs=16, axis='Y')
            b.sphere((wx, sy * 1.06, WZ), 0.07)
            for k in range(6):
                a = math.radians(20 + 140 * k / 5)
                b.sphere((wx + (ARCH + 0.03) * math.cos(a), sy * (W + 0.095), WZ + (ARCH + 0.03) * math.sin(a)), 0.02)
    b.cyl((-HX - 0.05, -0.55, Z0 - 0.02), 0.045, 0.35, segs=10, axis='X')
    b.cyl((-HX - 0.22, -0.55, Z0 - 0.02), 0.055, 0.06, segs=10, axis='X')
    for sy in (-1, 1):
        b.cyl((HX + 0.02, sy * 0.52, 1.36), 0.21, 0.07, segs=18, axis='X')
    b.cyl((HX + 0.02, 0, 0.96), 0.19, 0.04, segs=18, axis='X')
    b.use(m["chrome"], smooth=True)
    b.box((HX - 0.05, 0, 1.98), (0.32, 1.25, 0.03), ry=0.25)   # 前遮陽板
    b.use(m["vanCream"])
    # 分割前擋 + 側窗 + 後窗（鍍鉻框 → 玻璃）
    for sy in (-1, 1):
        b.box((HX + 0.006, sy * 0.28, 1.66), (0.012, 0.52, 0.60))
    for x, wdt in ((0.82, 0.62), (0.0, 0.66), (-0.82, 0.62)):
        for sy in (-1, 1):
            b.box((x, sy * (W + 0.006), 1.70), (wdt + 0.05, 0.012, 0.60))
    b.box((-HX - 0.006, 0, 1.68), (0.012, 1.02, 0.50))
    b.use(m["chrome"], smooth=True)
    for sy in (-1, 1):
        b.box((HX + 0.012, sy * 0.28, 1.66), (0.012, 0.48, 0.56))
    for x, wdt in ((0.82, 0.62), (0.0, 0.66), (-0.82, 0.62)):
        for sy in (-1, 1):
            b.box((x, sy * (W + 0.012), 1.70), (wdt, 0.012, 0.56))
    b.box((-HX - 0.012, 0, 1.68), (0.012, 0.98, 0.46))
    for sy in (-1, 1):
        b.cyl((HX + 0.05, sy * 0.52, 1.36), 0.165, 0.05, segs=18, axis='X')
    b.use(m["glass"], smooth=True)
    # VW 圓標
    b.cyl((HX + 0.035, 0, 0.96), 0.155, 0.02, segs=18, axis='X')
    b.use(m["vanPaint"], smooth=True)
    for a, c in (((-0.085, 1.065), (0.0, 0.94)), ((0.085, 1.065), (0.0, 0.94)),
                 ((-0.105, 0.915), (-0.052, 0.82)), ((-0.052, 0.82), (0.0, 0.915)), ((0.0, 0.915), (0.052, 0.82)), ((0.052, 0.82), (0.105, 0.915))):
        b.rod((HX + 0.05, a[0], a[1]), (HX + 0.05, c[0], c[1]), 0.011)
    b.use(m["chrome"], smooth=True)
    # 氣球胎（圓環，胎壁圓潤無胎紋）+ 白邊
    for wx in (-WX, WX):
        for sy in (-1, 1):
            b.torus((wx, sy * 0.90, WZ), TR, TRR, axis='Y')
    b.use(m["rubber"], smooth=True)
    for wx in (-WX, WX):
        for sy in (-1, 1):
            b.cyl((wx, sy * 0.90, WZ), TR + 0.02, 0.26, segs=20, axis='Y')
    b.use(m["white"], smooth=True)
    # 尾燈、車牌、散熱格
    for sy in (-1, 1):
        b.box((-HX - 0.01, sy * 0.60, 1.10), (0.02, 0.13, 0.18))
    b.use(m["tailRed"])
    for x in (HX + 0.01, -HX - 0.01):
        b.box((x, 0, 0.82), (0.012, 0.34, 0.12))
    b.use(m["white"])
    for sy in (-1, 1):
        for k in range(4):
            b.box((-HX - 0.008, sy * 0.50, 1.30 + k * 0.05), (0.01, 0.22, 0.02))
    b.use(m["darkMetal"])
    # 車頂架 + 行李箱 + 捲睡墊
    for sy in (-1, 1):
        b.cyl((-0.1, sy * 0.42, Z1 + 0.06), 0.022, 1.8, segs=8, axis='X')
        for x in (-0.85, 0.65):
            b.cyl((x, sy * 0.42, Z1 + 0.02), 0.016, 0.09, segs=6)
    for x in (-0.8, -0.1, 0.6):
        b.cyl((x, 0, Z1 + 0.06), 0.018, 0.9, segs=8, axis='Y')
    b.use(m["darkMetal"], smooth=True)
    b.box((-0.5, 0, Z1 + 0.26), (0.8, 0.8, 0.36))
    b.use(m["bark"])
    b.box((-0.5, 0, Z1 + 0.26), (0.82, 0.82, 0.05))
    b.use(m["woodPole"])
    b.cyl((0.45, 0, Z1 + 0.22), 0.16, 0.85, segs=12, axis='Y')
    b.use(m["fabricBlue"], smooth=True)
    for y in (-0.25, 0.25):
        b.box((0.45, y, Z1 + 0.22), (0.34, 0.04, 0.34))
    b.use(m["rope"])
    # 側邊條紋遮陽棚（+Y）
    for i in range(0, 5, 2):
        b.box((-0.8 + i * 0.4, 1.55, Z1 - 0.32), (0.4, 1.7, 0.03), rx=-0.18)
    b.use(m["canvas"])
    for i in range(1, 5, 2):
        b.box((-0.8 + i * 0.4, 1.55, Z1 - 0.32), (0.4, 1.7, 0.03), rx=-0.18)
    b.box((0.0, 2.37, Z1 - 0.47), (2.02, 0.06, 0.08), rx=-0.18)
    b.use(m["canvasTrim"])
    for sx in (-1, 1):
        b.cyl((sx * 0.95, 2.35, (Z1 - 0.5) / 2), 0.024, Z1 - 0.5, segs=8)
    b.use(m["woodPole"], smooth=True)
    for sx in (-1, 1):
        b.rod((sx * 0.95, 2.35, Z1 - 0.5), (sx * 1.4, 2.9, 0.0), 0.008)
    b.use(m["rope"])
    for sx in (-1, 1):
        b.box((sx * 1.4, 2.9, 0.07), (0.05, 0.05, 0.14))
    b.use(m["woodPole"])
    return b.done(name)


# ---------------------------------------------------------------- Coleman Tough Dome 風格帳篷（門朝 -Y）

def dome_tent(name):
    m = pm()
    b = B()
    R, H, P = 1.55, 1.75, 3.2
    nlat, nlon = 12, 48

    def rr(th):
        return 1.0 / ((abs(math.cos(th)) ** P + abs(math.sin(th)) ** P) ** (1.0 / P))

    def surf(th, phi):
        s = math.sin(phi) ** 0.85
        r = R * rr(th) * s
        return Vector((r * math.cos(th), r * math.sin(th), H * math.cos(phi)))

    rings = []
    for i in range(1, nlat + 1):
        phi = (math.pi / 2) * i / nlat
        rings.append([b.bm.verts.new(surf(j * 2 * math.pi / nlon, phi)) for j in range(nlon)])
    top = b.bm.verts.new(Vector((0, 0, H)))
    for j in range(nlon):
        b.bm.faces.new((top, rings[0][j], rings[0][(j + 1) % nlon]))
    for i in range(nlat - 1):
        for j in range(nlon):
            b.bm.faces.new((rings[i][j], rings[i][(j + 1) % nlon], rings[i + 1][(j + 1) % nlon], rings[i + 1][j]))
    b.bm.faces.new(rings[-1][::-1])

    def tent_mat(f):
        c = f.calc_center_median()
        n = f.normal
        if n.z < -0.5 or c.z < 0.27:
            return m["tentFloor"]
        if c.z < 0.62:
            return m["tentBeige"]
        return m["tentGreen"]
    b.use(tent_mat, smooth=True)

    def on_surface(z, want, axis, th0, off):
        """找出圓頂表面上高度 z、沿 axis（'x' 或 'y'）座標最接近 want 的點（th 在 th0 附近），並沿法線外推 off。"""
        phi = math.acos(min(max(z / H, 0.0), 0.999))
        best = None
        for k in range(241):
            th = th0 + (k / 240.0 - 0.5) * 1.5
            q = surf(th, phi)
            v = q.x if axis == 'x' else q.y
            if best is None or abs(v - want) < abs((best.x if axis == 'x' else best.y) - want):
                best = q
        nrm = Vector((best.x, best.y, best.z * 0.6)).normalized()
        return best + nrm * off

    def patch(outline, center, off, axis, th0, nring=3):
        """貼在圓頂表面上的曲面片：外框往中心縮成同心環，每個點都投影到表面（環夠密弦才不會切進圓頂）。"""
        cz, cw = center
        c = on_surface(cz, cw, axis, th0, off)
        rings = []
        for k in range(1, nring + 1):
            f = k / nring
            rings.append([on_surface(cz + (z - cz) * f, cw + (w - cw) * f, axis, th0, off) for w, z in outline])
        n = len(outline)
        for i in range(n):
            b.tri(c, rings[0][i], rings[0][(i + 1) % n])
        for k in range(nring - 1):
            for i in range(n):
                b.poly((rings[k][i], rings[k + 1][i], rings[k + 1][(i + 1) % n], rings[k][(i + 1) % n]))

    # D 形網門（正面 -Y）：米色拉鍊邊 + 深色網布，底邊平
    def d_outline(rx, rz, cz, zmin):
        return [(rx * math.cos(a), max(cz + rz * math.sin(a), zmin)) for a in [math.pi * (i / 24.0 - 0.5) * 2 for i in range(24)]]
    patch(d_outline(0.56, 0.84, 0.28, 0.06), (0.45, 0.0), 0.012, 'x', 1.5 * math.pi)
    b.use(m["tentBeige"], smooth=True)
    patch(d_outline(0.50, 0.78, 0.28, 0.08), (0.45, 0.0), 0.018, 'x', 1.5 * math.pi)
    b.use(m["tentMesh"], smooth=True)
    # 側網窗（±X）：圓角矩形
    def rrect(cy, cz, hw, hh, r=0.08, k=4):
        pts = []
        for (sx, sz, a0) in ((1, 1, 0.0), (-1, 1, math.pi / 2), (-1, -1, math.pi), (1, -1, 1.5 * math.pi)):
            for i in range(k):
                a = a0 + (math.pi / 2) * i / (k - 1)
                pts.append((cy + sx * (hw - r) + r * math.cos(a), cz + sz * (hh - r) + r * math.sin(a)))
        return pts
    for th0 in (0.0, math.pi):
        patch(rrect(0.08, 0.80, 0.46, 0.24), (0.80, 0.08), 0.012, 'y', th0)
    b.use(m["tentBeige"], smooth=True)
    for th0 in (0.0, math.pi):
        patch(rrect(0.08, 0.80, 0.41, 0.19), (0.80, 0.08), 0.018, 'y', th0)
    b.use(m["tentMesh"], smooth=True)

    # 兩根對角交叉的營柱（貼著外帳表面）
    for k, th_pair in enumerate(((math.pi / 4, 5 * math.pi / 4), (3 * math.pi / 4, 7 * math.pi / 4))):
        pts = []
        for th in (th_pair[0],):
            for i in range(nlat, 0, -1):
                pts.append(surf(th, (math.pi / 2) * i / nlat))
        pts.append(Vector((0, 0, H)))
        for i in range(1, nlat + 1):
            pts.append(surf(th_pair[1], (math.pi / 2) * i / nlat))
        lift = 0.022 + k * 0.018
        pts = [p + Vector((p.x, p.y, p.z * 0.6)).normalized() * lift for p in pts]
        for i in range(len(pts) - 1):
            b.rod(pts[i], pts[i + 1], 0.018)
    b.use(m["darkMetal"], smooth=True)
    # 頂部通風口、正面小紅標
    b.box((0, 0.22, 1.70), (0.34, 0.28, 0.05), rx=0.35)
    b.use(m["tentGreen"])
    b.box((0, -1.09, 1.33), (0.28, 0.02, 0.09), rx=0.45)
    b.use(m["red"])
    # 前庭雨棚：外帳前緣延伸、兩根柱子撐起、往外微微上揚
    b.slab([(-0.98, -1.18, 1.12), (0.98, -1.18, 1.12), (1.18, -2.95, 1.78), (-1.18, -2.95, 1.78)], 0.025)
    b.use(m["tentGreen"])
    for sx in (-1, 1):
        b.cyl((sx * 1.18, -2.95, 0.89), 0.02, 1.78, segs=8)
    b.use(m["darkMetal"], smooth=True)
    pegs = []
    for sx in (-1, 1):
        b.rod((sx * 1.18, -2.95, 1.78), (sx * 1.7, -3.5, 0.0), 0.008)
        pegs.append((sx * 1.7, -3.5))
    for th in (math.pi / 4, 3 * math.pi / 4, 5 * math.pi / 4, 7 * math.pi / 4):
        p0 = surf(th, math.acos(0.9 / H))
        p1 = Vector((2.45 * math.cos(th), 2.45 * math.sin(th), 0.02))
        b.rod(p0, p1, 0.008)
        pegs.append((p1.x, p1.y))
    b.use(m["rope"])
    for x, y in pegs:
        b.box((x, y, 0.06), (0.04, 0.04, 0.14))
    b.use(m["darkMetal"])
    # 前庭地布 + 門口踏墊
    b.slab([(-1.05, -1.3, 0.006), (1.05, -1.3, 0.006), (1.05, -2.9, 0.006), (-1.05, -2.9, 0.006)], 0.006)
    b.use(m["tentFloor"])
    b.box((0, -1.75, 0.018), (0.7, 0.45, 0.012))
    b.use(m["tentBeige"])
    return b.done(name)


# ---------------------------------------------------------------- 露營器具

def camp_chair(name, fabric="fabricBlue"):
    m = pm()
    b = B()
    b.box((0, 0, 0.43), (0.5, 0.52, 0.05))
    b.box((-0.27, 0, 0.75), (0.05, 0.52, 0.55), ry=-0.2)
    b.use(m[fabric])
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.rod((sx * 0.22, sy * 0.23, 0.42), (sx * 0.28, sy * 0.3, 0.0), 0.014)
    for sy in (-1, 1):
        b.rod((-0.25, sy * 0.25, 0.45), (-0.33, sy * 0.25, 1.0), 0.014)
        b.rod((0.15, sy * 0.28, 0.64), (0.22, sy * 0.28, 0.0), 0.012)
    b.use(m["darkMetal"], smooth=True)
    for sy in (-1, 1):
        b.box((-0.02, sy * 0.28, 0.66), (0.42, 0.06, 0.03))
    b.use(m["woodPole"])
    return b.done(name)


def camp_table(name):
    m = pm()
    b = B()
    b.box((0, 0, 0.72), (1.1, 0.65, 0.04))
    b.use(m["woodPole"])
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.rod((sx * 0.48, sy * 0.26, 0.70), (sx * 0.5, sy * 0.28, 0.0), 0.018)
    b.use(m["darkMetal"], smooth=True)
    b.cyl((0.3, 0.15, 0.79), 0.04, 0.1, segs=10)
    b.cyl((0.18, -0.18, 0.79), 0.04, 0.1, segs=10)
    b.cyl((-0.25, 0.0, 0.745), 0.12, 0.012, segs=12)
    b.use(m["white"], smooth=True)
    b.cyl((-0.1, 0.2, 0.86), 0.035, 0.24, segs=10, r2=0.02)
    b.use(m["glass"], smooth=True)
    return b.done(name)


def lantern(name):
    m = pm()
    b = B()
    b.cyl((0, 0, 0.02), 0.085, 0.04, segs=10)
    b.cyl((0, 0, 0.27), 0.1, 0.06, segs=10, r2=0.03)
    b.cyl((0, 0, 0.31), 0.02, 0.03, segs=8)
    pts = [Vector((0.09 * math.cos(math.radians(a)), 0, 0.31 + 0.11 * math.sin(math.radians(a)))) for a in range(0, 181, 30)]
    for i in range(len(pts) - 1):
        b.rod(pts[i], pts[i + 1], 0.006)
    b.use(m["darkMetal"], smooth=True)
    b.cyl((0, 0, 0.14), 0.06, 0.2, segs=10)
    b.use(m["lanternGlow"], smooth=True)
    return b.done(name)


def campfire(name):
    m = pm()
    b = B()
    for i in range(9):
        a = i * 2 * math.pi / 9
        b.sphere((0.55 * math.cos(a), 0.55 * math.sin(a), 0.07), 0.14, scale=(1.1, 0.9, 0.6))
    b.use(m["stone"])
    for a in (0.3, 1.4, 2.5):
        b.cyl((0, 0, 0.12), 0.06, 0.8, segs=7, axis='X', rz=a)
    b.use(m["bark"], smooth=True)
    b.cyl((0, 0, 0.36), 0.22, 0.5, segs=7, r2=0.0)
    b.use(m["flameOrange"])
    b.cyl((0.05, 0.03, 0.30), 0.13, 0.36, segs=6, r2=0.0)
    b.cyl((-0.06, -0.04, 0.28), 0.1, 0.3, segs=6, r2=0.0)
    b.use(m["flameYellow"])
    return b.done(name)


def tripod_kettle(name):
    m = pm()
    b = B()
    for i in range(3):
        a = i * 2 * math.pi / 3
        b.rod((0.62 * math.cos(a), 0.62 * math.sin(a), 0), (0.04 * math.cos(a), 0.04 * math.sin(a), 1.5), 0.02)
    b.use(m["woodPole"], smooth=True)
    b.rod((0, 0, 1.48), (0, 0, 1.1), 0.008)
    b.sphere((0, 0, 0.96), 0.15, scale=(1, 1, 0.8))
    b.cyl((0, 0, 1.1), 0.06, 0.05, segs=8, r2=0.03)
    b.rod((0.12, 0, 0.98), (0.26, 0, 1.08), 0.02)
    pts = [Vector((0.14 * math.cos(math.radians(a)), 0, 1.06 + 0.1 * math.sin(math.radians(a)))) for a in range(0, 181, 45)]
    for i in range(len(pts) - 1):
        b.rod(pts[i], pts[i + 1], 0.008)
    b.use(m["darkMetal"], smooth=True)
    return b.done(name)


def crate(name, size=(0.55, 0.42, 0.38)):
    m = pm()
    b = B()
    w, d, h = size
    b.box((0, 0, h / 2), (w, d, h))
    b.use(m["woodPole"])
    for zf in (0.25, 0.6, 0.92):
        b.box((0, 0, zf * h), (w + 0.02, d + 0.02, 0.04))
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.box((sx * w / 2, sy * d / 2, h / 2), (0.05, 0.05, h + 0.01))
    b.use(m["bark"])
    return b.done(name)


def cooler(name):
    m = pm()
    b = B()
    b.box((0, 0, 0.2), (0.62, 0.4, 0.4))
    b.use(m["fabricBlue"])
    b.box((0, 0, 0.44), (0.64, 0.42, 0.08))
    b.use(m["white"])
    b.box((0, 0, 0.5), (0.22, 0.05, 0.04))
    b.use(m["chrome"])
    return b.done(name)


# ---------------------------------------------------------------- Q 版露營者（多零件、有關節；Godot 端做程式動畫）
# 角色 = 幾個各自有原點（關節）的零件掛成階層：body（根）→ head / arms / kettle…，Godot 端旋轉節點就是動畫。
# 座標：+X 朝前（臉的方向）、Z 上；原點在腳底（坐姿版：椅子所在的地面）。單位公尺，約 2.9 頭身。
# 零件名稱 = <角色名>_<零件>，Godot 端用 find_child("*_head") 之類找。

def _part(b, name, pivot, parent=None, parent_pivot=(0, 0, 0)):
    """B 建好的零件 → 物件；原點搬到 pivot（關節），掛到 parent 下。"""
    ob = b.done(name)
    ob.data.transform(Matrix.Translation(-Vector(pivot)))
    ob.location = Vector(pivot) - Vector(parent_pivot)
    if parent is not None:
        ob.parent = parent
    return ob


def _empty(name, at, parent, parent_pivot):
    """空物件當標記點（壺嘴出口），Godot 端拿它的 global_position。"""
    import bpy
    ob = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(ob)
    ob.location = Vector(at) - Vector(parent_pivot)
    ob.parent = parent
    return ob


def _dome(b, c, r, phi0, scale=(1, 1, 1), n=6, k=24):
    """球冠（帽子、頭髮）：從緯度 phi0（度）到頂點；底部封口成封閉體，法線才會一致朝外。"""
    c = Vector(c)
    rings = []
    for i in range(n):
        ph = math.radians(phi0 + (80 - phi0) * i / (n - 1))
        rings.append([c + Vector((r * math.cos(ph) * math.cos(a) * scale[0], r * math.cos(ph) * math.sin(a) * scale[1],
                                  r * math.sin(ph) * scale[2])) for a in [j * 2 * math.pi / k for j in range(k)]])
    b.rings(rings, cap_start=True, pole=c + Vector((0, 0, r * scale[2])))


def _camper_head(zh, m, style, hat="beanieRed", hair="hairDark"):
    """大頭：膚色球 + 黑眼珠（帶亮點）+ 腮紅 + 小嘴；style = beanie（毛帽，顏色 hat）或 bucket（漁夫帽）。"""
    R = 0.215
    c = Vector((0.03, 0, zh + 0.60))
    b = B()
    b.sphere(c, R, sub=3, scale=(1.0, 1.02, 0.95))
    b.use(m["skin"], smooth=True)
    for s in (-1, 1):
        a = math.radians(s * 24)
        b.sphere(c + Vector((R * 0.96 * math.cos(a), R * 0.98 * math.sin(a), -0.005)), 0.03, sub=2, scale=(0.45, 1.0, 1.35))
    b.use(m["eyeDark"], smooth=True)
    for s in (-1, 1):
        a = math.radians(s * 22)
        b.sphere(c + Vector((R * math.cos(a) + 0.006, R * 0.98 * math.sin(a) + s * 0.008, 0.012)), 0.009, sub=1)
    b.use(m["white"], smooth=True)
    for s in (-1, 1):
        a = math.radians(s * 40)
        b.sphere(c + Vector((R * 0.97 * math.cos(a), R * 0.99 * math.sin(a), -0.05)), 0.034, sub=2, scale=(0.3, 1.0, 0.65))
    b.use(m["blush"], smooth=True)
    b.sphere(c + Vector((R * 0.97, 0, -0.085)), 0.012, sub=1, scale=(0.4, 1.5, 0.7))
    b.use(m["eyeDark"], smooth=True)
    hc = c + Vector((-0.01, 0, 0))
    if style == "beanie":
        _dome(b, hc, R + 0.008, 12, scale=(1, 1.02, 1.0))          # 帽子下露出一圈頭髮
        b.use(m[hair], smooth=True)
        rb = R + 0.03
        _dome(b, hc, rb, 22, scale=(1, 1.02, 1.15))               # 略高的軟帽身
        b.use(m[hat], smooth=True)
        zb = rb * 1.15 * math.sin(math.radians(22))
        b.torus(hc + Vector((0, 0, zb)), rb * math.cos(math.radians(22)), 0.036, axis='Z')   # 反摺帽緣
        b.sphere(hc + Vector((0, 0, rb * 1.15 + 0.02)), 0.058, sub=2)                        # 毛球
        b.use(m["vanCream"], smooth=True)
    else:
        _dome(b, hc, R + 0.012, 14, scale=(1, 1.02, 1.0))          # 西瓜皮
        b.use(m["hairBrown"], smooth=True)
        b.cyl(c + Vector((0, 0, 0.18)), 0.215, 0.13, segs=20, r2=0.185)     # 帽身
        b.cyl(c + Vector((0, 0, 0.115)), 0.31, 0.05, segs=20, r2=0.235)     # 下垂帽簷
        b.use(m["hatOlive"], smooth=True)
    return b


def _camper_body(zh, m, jacket, pants, sitting, legs=True):
    """身體 = 三顆壓扁的球疊成羽絨外套 + 圍巾；坐姿：大腿往前、小腿垂下（腳碰不到地，像小孩坐大椅子）。
    legs=False 時不含腿（散步版的腿是獨立關節零件，見 _leg）。"""
    b = B()
    for z, r in ((0.07, 0.19), (0.18, 0.185), (0.29, 0.165)):
        b.sphere((0, 0, zh + z), r, sub=3, scale=(0.85, 1.0, 0.62))
    b.use(m[jacket], smooth=True)
    b.torus((0.01, 0, zh + 0.375), 0.10, 0.045, axis='Z')
    b.use(m["vanCream"], smooth=True)
    if not legs:
        return b
    if sitting:
        for s in (-1, 1):
            b.rod((0.02, s * 0.085, zh + 0.02), (0.25, s * 0.10, zh + 0.01), 0.07, segs=10)
            b.rod((0.25, s * 0.10, zh + 0.01), (0.27, s * 0.10, zh - 0.30), 0.06, segs=10)
        b.use(m[pants], smooth=True)
        for s in (-1, 1):
            b.sphere((0.31, s * 0.10, zh - 0.34), 0.085, sub=2, scale=(1.25, 0.85, 0.75))
    else:
        for s in (-1, 1):
            b.rod((0.0, s * 0.085, zh), (0.01, s * 0.09, zh - 0.20), 0.07, segs=10)
            b.rod((0.01, s * 0.09, zh - 0.20), (0.02, s * 0.09, zh - 0.38), 0.06, segs=10)
        b.use(m[pants], smooth=True)
        for s in (-1, 1):
            b.sphere((0.06, s * 0.09, zh - 0.41), 0.085, sub=2, scale=(1.3, 0.85, 0.75))
    b.use(m["boots"], smooth=True)
    return b


def _arms_roast(zh, m, jacket):
    """兩手一起握著烤棉花糖的長棍；整組以肩線為軸（Godot 端慢慢上下左右晃）。"""
    b = B()
    sh = zh + 0.30
    b.rod((0.03, -0.17, sh), (0.34, -0.045, zh + 0.20), 0.055, segs=10)
    b.rod((0.03, 0.17, sh), (0.19, 0.03, zh + 0.22), 0.055, segs=10)
    b.use(m[jacket], smooth=True)
    b.sphere((0.34, -0.045, zh + 0.20), 0.065, sub=2)
    b.sphere((0.19, 0.03, zh + 0.22), 0.065, sub=2)
    b.use(m["mitten"], smooth=True)
    b.rod((0.14, -0.02, zh + 0.225), (1.25, -0.03, zh + 0.10), 0.011, segs=8)
    b.use(m["woodPole"], smooth=True)
    b.sphere((1.27, -0.03, zh + 0.10), 0.065, sub=2, scale=(1.15, 1.0, 1.0))
    b.use(m["white"], smooth=True)
    b.sphere((1.30, -0.03, zh + 0.085), 0.045, sub=2, scale=(1.1, 1.0, 1.0))   # 烤焦的那一面
    b.use(m["toast"], smooth=True)
    return b, (0.03, 0, sh)


def _arm_kettle(zh, m, jacket):
    """右手舉著鵝頸手沖壺。回傳 (手臂 B, 肩點), (壺 B, 手點=壺的關節), 壺嘴出口。"""
    sh = (0.03, -0.17, zh + 0.30)
    hand = Vector((0.36, -0.14, zh + 0.36))
    b = B()
    b.rod(sh, hand, 0.055, segs=10)
    b.use(m[jacket], smooth=True)
    b.sphere(hand, 0.065, sub=2)
    b.use(m["mitten"], smooth=True)
    k = B()
    kc = hand + Vector((0, 0, -0.14))
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
    return (b, sh), (k, tuple(hand)), tuple(pts[-1])


def _arm_mug(zh, m, jacket):
    """左手端著自己的那杯。"""
    sh = (0.03, 0.17, zh + 0.30)
    hand = (0.24, 0.13, zh + 0.22)
    b = B()
    b.rod(sh, hand, 0.055, segs=10)
    b.use(m[jacket], smooth=True)
    b.sphere(hand, 0.065, sub=2)
    b.use(m["mitten"], smooth=True)
    mc = Vector((0.28, 0.10, zh + 0.20))
    b.cyl(mc, 0.05, 0.10, segs=14)
    b.use(m["vanCream"], smooth=True)
    b.cyl(mc + Vector((0, 0, 0.02)), 0.051, 0.03, segs=14)
    b.use(m["coolerBlue"], smooth=True)
    b.cyl(mc + Vector((0, 0, 0.045)), 0.042, 0.012, segs=14)
    b.use(m["coffee"], smooth=True)
    return b, sh


def _pour(m, tip, length=0.3):
    """壺嘴倒出來的水柱：從 tip 往下 length 的細棒，Godot 端跟著壺嘴移動並縮放到濾杯口。"""
    b = B()
    b.rod(tip, (tip[0], tip[1], tip[2] - length), 0.006, segs=6)
    b.use(m["glass"], smooth=True)
    return b


def camper_roast(name):
    """坐在露營椅上烤棉花糖的露營者（毛帽、芥末黃羽絨外套）。零件：body（根）、head、arms。"""
    m = pm()
    zh = 0.525   # 髖關節高度 = 椅面 0.455 + 大腿半徑
    body = _part(_camper_body(zh, m, "puffMustard", "pantsNavy", True), name, (0, 0, 0))
    _part(_camper_head(zh, m, "beanie"), name + "_head", (0.02, 0, zh + 0.40), body)
    ab, piv = _arms_roast(zh, m, "puffMustard")
    _part(ab, name + "_arms", piv, body)
    return body


def camper_brew(name):
    """站著手沖咖啡的露營者（漁夫帽、梅紫色刷毛外套）。零件：body（根）、head、arm_r → kettle → tip（空物件）、arm_l、pour。"""
    m = pm()
    zh = 0.47
    body = _part(_camper_body(zh, m, "fleecePlum", "pantsKhaki", False), name, (0, 0, 0))
    _part(_camper_head(zh, m, "bucket"), name + "_head", (0.02, 0, zh + 0.40), body)
    (ab, sh), (kb, hand), tip = _arm_kettle(zh, m, "fleecePlum")
    arm = _part(ab, name + "_arm_r", sh, body)
    kettle = _part(kb, name + "_kettle", hand, arm, sh)
    _empty(name + "_tip", tip, kettle, hand)
    lb, sh2 = _arm_mug(zh, m, "fleecePlum")
    _part(lb, name + "_arm_l", sh2, body)
    _part(_pour(m, tip), name + "_pour", tip, body)
    return body


def _leg(zh, m, pants, s):
    """一條腿（大腿、小腿、靴子），原點在髖關節，走路時前後擺。"""
    b = B()
    b.rod((0.0, s * 0.085, zh), (0.01, s * 0.09, zh - 0.20), 0.07, segs=10)
    b.rod((0.01, s * 0.09, zh - 0.20), (0.02, s * 0.09, zh - 0.38), 0.06, segs=10)
    b.use(m[pants], smooth=True)
    b.sphere((0.06, s * 0.09, zh - 0.41), 0.085, sub=2, scale=(1.3, 0.85, 0.75))
    b.use(m["boots"], smooth=True)
    return b, (0.0, s * 0.085, zh)


def _arm_hang(zh, m, jacket, s):
    """自然下垂的手臂，原點在肩膀。"""
    sh = (0.03, s * 0.17, zh + 0.30)
    hand = (0.07, s * 0.20, zh + 0.03)
    b = B()
    b.rod(sh, hand, 0.055, segs=10)
    b.use(m[jacket], smooth=True)
    b.sphere(hand, 0.065, sub=2)
    b.use(m["mitten"], smooth=True)
    return b, sh


def camper_walk(name):
    """可操作的露營者（散步模式）：天藍羽絨外套、綠毛帽；兩腿、兩臂、頭各自是關節零件，Godot 端算走路循環。"""
    m = pm()
    zh = 0.47
    body = _part(_camper_body(zh, m, "puffSky", "pantsNavy", False, legs=False), name, (0, 0, 0))
    _part(_camper_head(zh, m, "beanie", hat="beanieGreen", hair="hairBrown"), name + "_head", (0.02, 0, zh + 0.40), body)
    for s, tag in ((-1, "r"), (1, "l")):
        lb, lp = _leg(zh, m, "pantsNavy", s)
        _part(lb, name + "_leg_" + tag, lp, body)
        ab, ap = _arm_hang(zh, m, "puffSky", s)
        _part(ab, name + "_arm_" + tag, ap, body)
    return body


def coffee_set(name):
    """桌上的手沖組：濾杯架在馬克杯上（原點），旁邊一杯已經沖好的（Godot 端在這杯上放蒸氣）。"""
    m = pm()
    b = B()
    for mc in (Vector((0, 0, 0)), Vector((-0.11, 0.10, 0))):
        b.cyl(mc + Vector((0, 0, 0.055)), 0.055, 0.11, segs=16)
    b.use(m["vanCream"], smooth=True)
    for mc in (Vector((0, 0, 0)), Vector((-0.11, 0.10, 0))):
        b.cyl(mc + Vector((0, 0, 0.03)), 0.056, 0.035, segs=16)
        b.torus(mc + Vector((0.075, 0, 0.055)), 0.03, 0.009, axis='Y', seg_major=12, seg_minor=6)   # 杯耳
    b.use(m["coolerBlue"], smooth=True)
    b.cyl((0, 0, 0.116), 0.07, 0.012, segs=16)              # 濾杯座
    b.cyl((0, 0, 0.167), 0.045, 0.09, segs=16, r2=0.085)     # 濾杯
    b.use(m["dripperTerra"], smooth=True)
    b.cyl((0, 0, 0.19), 0.072, 0.006, segs=16)               # 濕咖啡粉
    b.cyl((-0.11, 0.10, 0.10), 0.046, 0.008, segs=16)        # 沖好的咖啡
    b.use(m["coffee"], smooth=True)
    return b.done(name)


def marshmallow_bag(name):
    """椅子旁的棉花糖袋 + 兩顆掉出來的。"""
    m = pm()
    b = B()
    # 枕頭形的袋子（斜靠著）、上緣一條封口、正面一塊粉紅標籤
    b.sphere((0, 0, 0.11), 0.12, sub=3, scale=(0.45, 0.75, 1.0))
    b.use(m["white"], smooth=True)
    b.box((0.05, 0, 0.11), (0.025, 0.11, 0.08))
    b.box((0, 0, 0.225), (0.03, 0.15, 0.02))
    b.use(m["bagCoral"])
    b.cyl((0.14, 0.12, 0.028), 0.028, 0.055, segs=10, axis='X')
    b.cyl((0.19, -0.06, 0.028), 0.028, 0.055, segs=10, axis='Y')
    b.use(m["white"], smooth=True)
    return b.done(name)
