"""低多邊形樹／草叢生成函式庫（在 Blender 內使用）。
葉子做法 leaf_style：
  blob    — 每根枝頭 1 大 + 1~2 小顆帶起伏的葉團（目前用的）
  cluster — 每根枝頭 7~11 顆小葉團堆成蓬鬆的一簇
  hybrid  — 葉團當核心，表面再插一圈葉片，剪影變毛茸茸
  leaves  — 不用葉團，全部用幾百片單獨的葉片填滿
"""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, noise

_MATS = {}
_PENDING_NORMALS = []   # [(face, normal)]：葉片要覆寫的「樹冠球面法線」，finish()/build() 時寫入


def _apply_custom_normals(bm, me):
    """把 _PENDING_NORMALS 寫成 mesh 的 custom split normals（葉子照整顆樹冠的球面受光）。"""
    global _PENDING_NORMALS
    if not _PENDING_NORMALS:
        return
    normals = [Vector(n.vector) for n in me.vertex_normals]
    for f, n in _PENDING_NORMALS:
        for v in f.verts:
            normals[v.index] = n
    me.normals_split_custom_set_from_vertices(normals)
    _PENDING_NORMALS = []


def _mat(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = 0.9
    return m


def mats():
    if not _MATS:
        _MATS["bark"] = _mat("woodBark", (0.44, 0.31, 0.21))
        _MATS["leaf"] = _mat("leafsGreen", (0.36, 0.63, 0.30))
        _MATS["pine"] = _mat("leafsDark", (0.22, 0.47, 0.30))
        _MATS["grass"] = _mat("grass", (0.40, 0.66, 0.30))
    return _MATS


def preview_vertex_colors():
    """讓 Blender 預覽渲染也看得到頂點色（Godot 端本來就會乘上去）。"""
    for key in ("leaf", "pine"):
        m = mats()[key]
        nt = m.node_tree
        bsdf = nt.nodes["Principled BSDF"]
        base = bsdf.inputs["Base Color"].default_value[:]
        attr = nt.nodes.new("ShaderNodeVertexColor")
        attr.layer_name = "Col"
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        mix.inputs[6].default_value = base
        nt.links.new(attr.outputs["Color"], mix.inputs[7])
        nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])


# ---------------------------------------------------------------- 幾何工具

def add_tube(bm, pts, radii, segs=6):
    rings = []
    for i, p in enumerate(pts):
        if i == 0:
            d = (pts[1] - p).normalized()
        elif i == len(pts) - 1:
            d = (p - pts[i - 1]).normalized()
        else:
            d = ((pts[i + 1] - p).normalized() + (p - pts[i - 1]).normalized()).normalized()
        up = Vector((1, 0, 0)) if abs(d.z) > 0.9 else Vector((0, 0, 1))
        x = d.cross(up).normalized()
        y = x.cross(d).normalized()
        ring = []
        for k in range(segs):
            a = k * 2 * math.pi / segs
            ring.append(bm.verts.new(p + (x * math.cos(a) + y * math.sin(a)) * radii[i]))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(segs):
            bm.faces.new((rings[i][k], rings[i][(k + 1) % segs], rings[i + 1][(k + 1) % segs], rings[i + 1][k]))
    bm.faces.new(rings[-1])
    return rings


def lerp_polyline(pts, t):
    f = t * (len(pts) - 1)
    i = min(int(f), len(pts) - 2)
    return pts[i].lerp(pts[i + 1], f - i)


def add_blob(bm, center, r, sub, seed, squash=0.85, amt=0.16):
    ret = bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r,
                                     matrix=Matrix.Translation(center), calc_uvs=False)
    off = Vector((seed * 0.37, seed * 0.11, seed * 0.23))
    for v in ret["verts"]:
        local = v.co - center
        n = noise.noise(local * (2.2 / r) + off)
        local *= 1.0 + amt * n
        local.z *= squash
        v.co = center + local


def add_leaf(bm, c, n, size, rnd, shape="leaf6", shade_normal=None):
    """一片葉子（雙面，Godot 端材質關背面剔除）。
    diamond：4 頂點菱形（2 tris）；leaf6：6 頂點尖橢圓（4 tris）；leaf8：8 頂點圓橢圓（6 tris）"""
    n = n.normalized()
    helper = Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((1, 0, 0))
    u = n.cross(helper).normalized()
    v = u.cross(n)
    a = rnd.uniform(0, math.tau)
    u2 = u * math.cos(a) + v * math.sin(a)
    v2 = n.cross(u2)
    L, W = size, size * 0.56
    if shape == "diamond":
        pts = [(0, 0.55), (0.5, 0.02), (0, -0.45), (-0.5, 0.02)]
    elif shape == "leaf6":
        pts = [(0, 0.55), (0.40, 0.22), (0.44, -0.12), (0, -0.45), (-0.44, -0.12), (-0.40, 0.22)]
    else:
        pts = [(math.sin(k * math.tau / 8) * 0.5, math.cos(k * math.tau / 8) * 0.5) for k in range(8)]
    f = bm.faces.new([bm.verts.new(c + u2 * (px * W) + v2 * (py * L)) for px, py in pts])
    if shade_normal is not None:
        _PENDING_NORMALS.append((f, shade_normal.normalized()))
    return f


def _rand_dir(rnd, up_bias=0.3):
    d = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1) + up_bias))
    return d.normalized() if d.length > 1e-4 else Vector((0, 0, 1))


def canopy(bm, style, c, R, rnd, seed, leaf_count, leaf_shape="leaf6", canopy_center=None, core=True):
    top = c + Vector((0, 0, R * 0.32))
    cc = canopy_center if canopy_center is not None else top
    if style == "blob":
        add_blob(bm, top, R, 2, seed)
        for j in range(rnd.randint(1, 2)):
            off = _rand_dir(rnd, 0.2) * R * 0.7
            add_blob(bm, c + off, R * rnd.uniform(0.5, 0.7), 1, seed * 10 + j)
    elif style == "cluster":
        for j in range(rnd.randint(7, 11)):
            off = _rand_dir(rnd, 0.35) * R * rnd.uniform(0.2, 0.75)
            add_blob(bm, top + off, R * rnd.uniform(0.34, 0.5), 1, seed * 10 + j, amt=0.22)
    elif style == "hybrid":
        add_blob(bm, top, R * 0.85, 2, seed)
        for j in range(leaf_count or 70):
            d = _rand_dir(rnd, 0.25)
            p = top + d * R * 0.85 * rnd.uniform(0.85, 1.05)
            add_leaf(bm, p, d + _rand_dir(rnd, 0) * 0.5, R * rnd.uniform(0.28, 0.4), rnd, leaf_shape)
    elif style == "leaves":
        if core:
            # 深色內核：補掉葉子之間透光的洞，讓樹冠有體積
            add_blob(bm, top, R * 0.74, 1, seed, amt=0.12)
        for j in range(leaf_count or 220):
            d = _rand_dir(rnd, 0.25)
            rad = R * (0.5 + 0.55 * rnd.random() ** 0.5)
            p = top + d * rad
            # 受光法線：一半看這簇的中心、一半看整顆樹冠中心，再往上偏一點 → 像一顆球那樣平滑受光
            n_local = (p - top).normalized()
            n_global = (p - cc).normalized() if (p - cc).length > 1e-4 else n_local
            shade_n = n_local * 0.45 + n_global * 0.55 + Vector((0, 0, 0.3))
            add_leaf(bm, p, d + _rand_dir(rnd, 0) * 0.6, R * rnd.uniform(0.26, 0.38), rnd, leaf_shape, shade_n)


def finish(bm, n_wood, name, leaf_mat, shade=True, core_shade=0.55):
    """設材質索引、平面/平滑著色、葉子頂點色（上亮下暗、外亮內暗），輸出物件。"""
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    col = bm.loops.layers.color.new("Col")
    card_faces = {f for f, _ in _PENDING_NORMALS}
    leaf_faces = [f for i, f in enumerate(bm.faces) if i >= n_wood]
    if leaf_faces:
        zs = [v.co.z for f in leaf_faces for v in f.verts]
        zmin, zmax = min(zs), max(zs)
        cen = sum((f.calc_center_median() for f in leaf_faces), Vector()) / len(leaf_faces)
        rmax = max((v.co - cen).length for f in leaf_faces for v in f.verts)
    for i, f in enumerate(bm.faces):
        f.material_index = 0 if i < n_wood else 1
        is_card = f in card_faces
        f.smooth = i < n_wood or is_card
        for loop in f.loops:
            if i < n_wood or not shade:
                loop[col] = (1, 1, 1, 1)
            elif card_faces and not is_card:
                loop[col] = (core_shade, core_shade, core_shade, 1)   # 內核：固定深色
            else:
                t = (loop.vert.co.z - zmin) / max(zmax - zmin, 1e-3)
                d = (loop.vert.co - cen).length / max(rmax, 1e-3)
                b = (0.78 + 0.22 * t) * (0.9 + 0.12 * d)
                loop[col] = (b, b, b, 1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    _apply_custom_normals(bm, me)
    bm.free()
    me.materials.append(mats()["bark"])
    me.materials.append(leaf_mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


# ---------------------------------------------------------------- 樹

def tree_broadleaf(name, seed, height=1.7, trunk_frac=0.55, n_branch=(6, 8), elev=(30, 60),
                   blob=1.0, spread=1.0, leaf_style="blob", leaf_count=None, shade=True, leaf_shape="leaf6", core=True):
    rnd = random.Random(seed)
    bm = bmesh.new()
    n = 5
    lean = Vector((rnd.uniform(-0.06, 0.06), rnd.uniform(-0.06, 0.06), 0))
    pts, radii = [], []
    for i in range(n):
        t = i / (n - 1)
        wob = Vector((rnd.uniform(-0.02, 0.02), rnd.uniform(-0.02, 0.02), 0)) if i else Vector()
        pts.append(Vector((0, 0, height * trunk_frac * t)) + lean * t * height + wob)
        radii.append(0.10 * (1 - t) + 0.045 * t)
    add_tube(bm, pts, radii, segs=7)
    tips = []
    nb = rnd.randint(*n_branch)
    for b in range(nb):
        t0 = rnd.uniform(0.5, 0.97)
        base = lerp_polyline(pts, t0)
        az = b * 2 * math.pi / nb + rnd.uniform(-0.4, 0.4)
        el = math.radians(rnd.uniform(*elev))
        d = Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)))
        L = height * rnd.uniform(0.30, 0.45) * (1.25 - 0.5 * t0) * spread
        bpts, brad = [base], [0.034]
        cur, cd = base.copy(), d.copy()
        for k in range(1, 4):
            cd = (cd + Vector((0, 0, 0.14))).normalized()
            cur = cur + cd * L / 3
            bpts.append(cur.copy())
            brad.append(0.034 * (1 - k / 3) + 0.011 * k / 3)
        add_tube(bm, bpts, brad, segs=5)
        tips.append((cur.copy(), L))
        if rnd.random() < 0.75:
            sb = bpts[2]
            sd = (cd + Vector((rnd.uniform(-0.7, 0.7), rnd.uniform(-0.7, 0.7), 0.35))).normalized()
            spts, srad = [sb], [0.017]
            c2 = sb.copy()
            for k in range(1, 3):
                c2 = c2 + sd * L * 0.24
                spts.append(c2.copy())
                srad.append(0.017 * (1 - k / 2) + 0.006)
            add_tube(bm, spts, srad, segs=4)
            tips.append((c2.copy(), L * 0.65))
    tips.append((pts[-1], height * 0.42))
    n_wood = len(bm.faces)
    canopy_c = sum((c for c, _ in tips), Vector()) / len(tips) + Vector((0, 0, height * 0.12))
    for i, (c, L) in enumerate(tips):
        R = L * rnd.uniform(0.55, 0.75) * blob
        canopy(bm, leaf_style, c, R, rnd, seed * 100 + i, leaf_count, leaf_shape, canopy_c, core)
    return finish(bm, n_wood, name, mats()["leaf"], shade)


def tree_pine(name, seed, height=2.0, tiers=4, shade=True):
    rnd = random.Random(seed)
    bm = bmesh.new()
    pts = [Vector((0, 0, 0)), Vector((0, 0, height * 0.45)), Vector((0, 0, height * 0.93))]
    add_tube(bm, pts, [0.08, 0.05, 0.015], segs=6)
    n_wood = len(bm.faces)
    for i in range(tiers):
        t = i / (tiers - 1)
        z0 = height * (0.26 + 0.60 * t)
        r = height * (0.32 - 0.21 * t) * rnd.uniform(0.9, 1.1)
        th = height * (0.30 - 0.10 * t)
        m = Matrix.Translation(Vector((rnd.uniform(-0.02, 0.02), rnd.uniform(-0.02, 0.02), z0 + th / 2)))
        ret = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=True, segments=9, radius1=r, radius2=0.012,
                                    depth=th, matrix=m, calc_uvs=False)
        for v in ret["verts"]:
            if v.co.z < z0 + th * 0.5:
                s = 1 + 0.2 * noise.noise(v.co * 3.5 + Vector((seed, 0, 0)))
                v.co.x *= s
                v.co.y *= s
                v.co.z += rnd.uniform(-0.02, 0.03)
    return finish(bm, n_wood, name, mats()["pine"], shade)


# ---------------------------------------------------------------- 草叢

def grass_tuft(name, seed, blades=10, h_range=(0.22, 0.36), w_range=(0.055, 0.085)):
    """草叢：寬短軟的葉片互相重疊成一個面（BotW 式），不是一根根細尖的針。"""
    rnd = random.Random(seed)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    for b in range(blades):
        az = b * 2 * math.pi / blades + rnd.uniform(-0.3, 0.3)
        h = rnd.uniform(*h_range)
        lean = rnd.uniform(0.35, 0.7)
        w0 = rnd.uniform(*w_range)
        segs = 3
        dv = Vector((math.cos(az), math.sin(az), 0))
        side = Vector((-math.sin(az), math.cos(az), 0))
        base = dv * rnd.uniform(0.0, 0.05)
        rows = []
        for k in range(segs + 1):
            t = k / segs
            p = base + dv * (lean * h * t * t) + Vector((0, 0, h * (t - 0.18 * t * t)))
            w = w0 * (1 - t * t) * (1 - 0.2 * t) + 0.006 * t   # 寬到接近尖端才收
            rows.append((bm.verts.new(p - side * w), bm.verts.new(p + side * w), t))
        for k in range(segs):
            a0, a1, t0 = rows[k]
            b0, b1, t1 = rows[k + 1]
            f = bm.faces.new((a0, a1, b1, b0))
            f.smooth = True
            for loop in f.loops:
                loop[uv].uv = (0.5, 1.0 - (t0 if loop.vert in (a0, a1) else t1))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mats()["grass"])
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def export_glb(ob, path):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True,
                              export_apply=True, export_vertex_color="ACTIVE")


def export_glb_objs(objs, path):
    """多物件（含父子階層、空物件）一起匯出成一個 GLB：關節動畫用的角色。"""
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True,
                              export_apply=True, export_vertex_color="ACTIVE")


def tri_count(ob):
    if ob.type != 'MESH':
        return 0
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


# ================================================================ 其他植被／小物

def _more_mats():
    m = mats()
    if "stone" not in m:
        m["stone"] = _mat("stone", (0.62, 0.62, 0.60))
        m["white"] = _mat("_defaultMat", (0.95, 0.94, 0.90))
        m["red"] = _mat("colorRed", (0.85, 0.25, 0.22))
        m["yellow"] = _mat("colorYellow", (0.98, 0.82, 0.35))
        m["purple"] = _mat("colorPurple", (0.62, 0.45, 0.85))
        m["inner"] = _mat("woodInner", (0.84, 0.71, 0.50))
    return m


def add_tube2(bm, pts, radii, segs=6, cap_start=False, cap_end=True, bark=0.0, seed=0):
    """add_tube 的加強版：可選兩端封口、樹皮凹凸。"""
    rings = []
    off = Vector((seed * 0.31, seed * 0.17, seed * 0.29))
    for i, p in enumerate(pts):
        if i == 0:
            d = (pts[1] - p).normalized()
        elif i == len(pts) - 1:
            d = (p - pts[i - 1]).normalized()
        else:
            d = ((pts[i + 1] - p).normalized() + (p - pts[i - 1]).normalized()).normalized()
        up = Vector((1, 0, 0)) if abs(d.z) > 0.9 else Vector((0, 0, 1))
        x = d.cross(up).normalized()
        y = x.cross(d).normalized()
        ring = []
        for k in range(segs):
            a = k * 2 * math.pi / segs
            rd = x * math.cos(a) + y * math.sin(a)
            r = radii[i]
            if bark > 0:
                r *= 1.0 + bark * noise.noise((p + rd * r) * (6.0 / max(r, 1e-3)) * 0.15 + off)
            ring.append(bm.verts.new(p + rd * r))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(segs):
            bm.faces.new((rings[i][k], rings[i][(k + 1) % segs], rings[i + 1][(k + 1) % segs], rings[i + 1][k]))
    if cap_end:
        bm.faces.new(rings[-1])
    if cap_start:
        bm.faces.new(rings[0][::-1])
    return rings


def _shade_faces(bm, col, faces, lo=0.72):
    if not faces:
        return
    zs = [v.co.z for f in faces for v in f.verts]
    zmin, zmax = min(zs), max(zs)
    cen = sum((f.calc_center_median() for f in faces), Vector()) / len(faces)
    rmax = max((v.co - cen).length for f in faces for v in f.verts)
    for f in faces:
        for loop in f.loops:
            t = (loop.vert.co.z - zmin) / max(zmax - zmin, 1e-3)
            d = (loop.vert.co - cen).length / max(rmax, 1e-3)
            b = (lo + (1 - lo) * t) * (0.85 + 0.2 * d)
            loop[col] = (b, b, b, 1)


def build(bm, name, ranges=None, face_mat=None, shade_ranges=(), smooth_ranges=(), smooth_pred=None):
    """把 bmesh 變成物件。
    ranges=[(面數, 材質), ...] 依建立順序指定材質；或 face_mat(face)->材質 逐面判斷。
    shade_ranges：哪些 range 套用「上亮下暗、外亮內暗」頂點色。"""
    bm.faces.ensure_lookup_table()
    col = bm.loops.layers.color.new("Col")
    for f in bm.faces:
        for loop in f.loops:
            loop[col] = (1, 1, 1, 1)
    mats_list = []

    def idx_of(m):
        if m not in mats_list:
            mats_list.append(m)
        return mats_list.index(m)

    if ranges:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.normal_update()
        start = 0
        groups = []
        for ri, (count, m) in enumerate(ranges):
            fs = [bm.faces[i] for i in range(start, min(start + count, len(bm.faces)))]
            for f in fs:
                f.material_index = idx_of(m(f) if callable(m) else m)
                f.smooth = ri in smooth_ranges
            groups.append(fs)
            start += count
        for ri in shade_ranges:
            _shade_faces(bm, col, groups[ri])
    else:
        for f in bm.faces:
            f.material_index = idx_of(face_mat(f))
            f.smooth = bool(smooth_pred and smooth_pred(f))
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    card_faces = {f for f, _ in _PENDING_NORMALS}
    for f in card_faces:
        f.smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    _apply_custom_normals(bm, me)
    bm.free()
    for m in mats_list:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def bush(name, seed, size=0.5, leaf_count=120):
    m = _more_mats()
    rnd = random.Random(seed)
    bm = bmesh.new()
    for k in range(rnd.randint(3, 5)):
        d = _rand_dir(rnd, 1.2)
        d.z = abs(d.z) + 0.3
        d.normalize()
        add_tube(bm, [Vector((0, 0, -0.02)), d * size * 0.35, d * size * 0.6 + Vector((0, 0, size * 0.1))],
                 [0.03 * size / 0.5, 0.02 * size / 0.5, 0.01], segs=5)
    n_wood = len(bm.faces)
    add_blob(bm, Vector((0, 0, size * 0.42)), size * 0.5, 1, seed, squash=0.7)
    n_core = len(bm.faces) - n_wood
    for j in range(leaf_count):
        d = _rand_dir(rnd, 0.35)
        rad = size * (0.45 + 0.35 * rnd.random() ** 0.5)
        p = Vector((0, 0, size * 0.42)) + d * rad
        p.z = max(p.z, 0.03)
        shade_n = (p - Vector((0, 0, size * 0.42))).normalized() + Vector((0, 0, 0.35))
        add_leaf(bm, p, d + _rand_dir(rnd, 0) * 0.6, size * rnd.uniform(0.28, 0.38), rnd, "leaf6", shade_n)
    n_leaf = len(bm.faces) - n_wood - n_core
    return build(bm, name, [(n_wood, m["bark"]), (n_core, m["pine"]), (n_leaf, m["leaf"])],
                 shade_ranges=(2,), smooth_ranges=(0,))


def fern(name, seed, size=0.5, fronds=(6, 9)):
    m = _more_mats()
    rnd = random.Random(seed)
    bm = bmesh.new()
    n = rnd.randint(*fronds)
    frond_pts = []
    for k in range(n):
        az = k * math.tau / n + rnd.uniform(-0.3, 0.3)
        dv = Vector((math.cos(az), math.sin(az), 0))
        L = size * rnd.uniform(0.8, 1.2)
        lift = rnd.uniform(0.35, 0.6)
        pts = []
        for i in range(9):
            t = i / 8
            pts.append(dv * L * t * 0.95 + Vector((0, 0, 0.02 + math.sin(t * math.pi * 0.85) * L * lift)))
        add_tube(bm, pts, [0.012 * size / 0.5 * (1 - 0.8 * i / 8) + 0.002 for i in range(9)], segs=3)
        frond_pts.append((pts, dv, L))
    n_stem = len(bm.faces)
    pts6 = [(0, 0.55), (0.40, 0.22), (0.44, -0.12), (0, -0.45), (-0.44, -0.12), (-0.40, 0.22)]
    for pts, dv, L in frond_pts:
        side = Vector((-dv.y, dv.x, 0))
        pairs = 11
        for i in range(pairs):
            t = 0.12 + 0.86 * i / (pairs - 1)
            p = lerp_polyline(pts, t)
            tangent = (lerp_polyline(pts, min(t + 0.05, 1)) - lerp_polyline(pts, max(t - 0.05, 0))).normalized()
            s = L * 0.26 * (1 - 0.75 * t) + L * 0.03
            for sgn in (-1, 1):
                c = p + side * sgn * s * 0.35
                nrm = (Vector((0, 0, 1)) + side * sgn * 0.5 + tangent * 0.1).normalized()
                u2 = side * sgn
                v2 = nrm.cross(u2).normalized()
                w = s * 0.42
                bm.faces.new([bm.verts.new(c + v2 * (px * w) + u2 * (py * s)) for px, py in pts6])
    n_leaf = len(bm.faces) - n_stem
    return build(bm, name, [(n_stem, m["pine"]), (n_leaf, m["pine"])], shade_ranges=(1,), smooth_ranges=(0,))


def flower(name, seed, petal, petals=6, height=0.28, center=None):
    m = _more_mats()
    rnd = random.Random(seed)
    bm = bmesh.new()
    h = height * rnd.uniform(0.9, 1.15)
    lean = Vector((rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05), 0))
    pts = [Vector((0, 0, 0)), Vector((0, 0, h * 0.5)) + lean * 0.5, Vector((0, 0, h)) + lean]
    add_tube(bm, pts, [0.012, 0.010, 0.008], segs=5)
    for zt in (0.3, 0.55):
        p = lerp_polyline(pts, zt)
        d = _rand_dir(rnd, -0.6)
        d.z = 0.35
        add_leaf(bm, p + d.normalized() * h * 0.12, d.normalized() + Vector((0, 0, 1.2)), h * 0.34, rnd, "leaf6")
    n_green = len(bm.faces)
    top = pts[-1]
    pts6 = [(0, 0.55), (0.40, 0.22), (0.44, -0.12), (0, -0.45), (-0.44, -0.12), (-0.40, 0.22)]
    for i in range(petals):
        ang = i * math.tau / petals + rnd.uniform(-0.1, 0.1)
        dv = Vector((math.cos(ang), math.sin(ang), 0))
        c = top + dv * h * 0.1 + Vector((0, 0, h * 0.02))
        u2 = Vector((-dv.y, dv.x, 0))
        s = h * 0.22
        w = s * 0.5
        bm.faces.new([bm.verts.new(c + u2 * (px * w) + dv * ((py + 0.45) * s) + Vector((0, 0, (py + 0.45) * s * 0.35)))
                      for px, py in pts6])
    n_petal = len(bm.faces) - n_green
    add_blob(bm, top + Vector((0, 0, h * 0.03)), h * 0.07, 1, seed, squash=0.55, amt=0.0)
    n_center = len(bm.faces) - n_green - n_petal
    return build(bm, name, [(n_green, m["grass"]), (n_petal, m[petal]), (n_center, m[center or "yellow"])],
                 smooth_ranges=(0, 2))


def mushroom(name, seed, cap="red", dots=True, count=1, size=1.0):
    m = _more_mats()
    rnd = random.Random(seed)
    bm = bmesh.new()
    specs = []
    for k in range(count):
        s = size * rnd.uniform(0.7, 1.0) if count > 1 else size
        off = Vector((rnd.uniform(-0.08, 0.08), rnd.uniform(-0.08, 0.08), 0)) if count > 1 else Vector()
        hgt = 0.14 * s
        lean = Vector((rnd.uniform(-0.02, 0.02), rnd.uniform(-0.02, 0.02), 0))
        pts = [off, off + Vector((0, 0, hgt * 0.5)) + lean * 0.5, off + Vector((0, 0, hgt)) + lean]
        add_tube(bm, pts, [0.032 * s, 0.026 * s, 0.028 * s], segs=7)
        specs.append((pts[-1], s))
    n_stem = len(bm.faces)
    for top, s in specs:
        r = 0.09 * s
        ret = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r, matrix=Matrix.Translation(top), calc_uvs=False)
        for v in ret["verts"]:
            local = v.co - top
            if local.z < 0:
                local.z *= 0.25
            local.z *= 0.75
            local *= 1.0 + 0.05 * noise.noise(local * 30 + Vector((seed, 0, 0)))
            v.co = top + local
    n_cap = len(bm.faces) - n_stem
    if dots:
        for top, s in specs:
            r = 0.09 * s
            for j in range(rnd.randint(5, 8)):
                d = _rand_dir(rnd, 1.0)
                d.z = abs(d.z) + 0.25
                d.normalize()
                p = top + Vector((d.x * r, d.y * r, d.z * r * 0.75))
                bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r * rnd.uniform(0.14, 0.22),
                                           matrix=Matrix.Translation(p), calc_uvs=False)
    n_dot = len(bm.faces) - n_stem - n_cap
    ranges = [(n_stem, m["white"]), (n_cap, m[cap])] + ([(n_dot, m["white"])] if dots else [])
    return build(bm, name, ranges, smooth_ranges=(0,))


def rock(name, seed, size=0.3, mossy=True, flat=False):
    m = _more_mats()
    rnd = random.Random(seed)
    bm = bmesh.new()
    ret = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=size, calc_uvs=False)
    sc = Vector((rnd.uniform(0.9, 1.3), rnd.uniform(0.75, 1.1), rnd.uniform(0.45, 0.7) if flat else rnd.uniform(0.7, 1.0)))
    off = Vector((seed * 0.41, seed * 0.13, seed * 0.27))
    for v in ret["verts"]:
        n = noise.noise(v.co * (1.8 / size) + off)
        v.co = v.co * (1.0 + 0.32 * n)
        v.co = Vector((v.co.x * sc.x, v.co.y * sc.y, v.co.z * sc.z))
    zmin = min(v.co.z for v in bm.verts)
    for v in bm.verts:
        v.co.z = max(v.co.z, zmin * 0.45) - zmin * 0.45 - size * 0.08
    zmax = max(v.co.z for v in bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    def fmat(f):
        c = f.calc_center_median()
        if mossy and f.normal.z > 0.5 and c.z > zmax * 0.45:
            return m["grass"]
        return m["stone"]
    return build(bm, name, face_mat=fmat)


def log_(name, seed, length=0.7, radius=0.09):
    m = _more_mats()
    rnd = random.Random(seed)
    bm = bmesh.new()
    pts = []
    for i in range(6):
        t = i / 5
        pts.append(Vector((-length / 2 + length * t, math.sin(t * math.pi) * 0.02, radius * 0.9 + rnd.uniform(-0.005, 0.005))))
    radii = [radius * rnd.uniform(0.92, 1.05) for _ in pts]
    add_tube2(bm, pts, radii, segs=9, cap_start=True, cap_end=True, bark=0.12, seed=seed)
    for k in range(rnd.randint(1, 2)):
        t = rnd.uniform(0.2, 0.8)
        base = lerp_polyline(pts, t)
        d = Vector((rnd.uniform(-0.3, 0.3), rnd.choice((-1, 1)) * rnd.uniform(0.4, 1.0), rnd.uniform(0.3, 1.0))).normalized()
        add_tube2(bm, [base, base + d * radius * 1.4, base + d * radius * 2.4], [radius * 0.35, radius * 0.25, radius * 0.12],
                  segs=5, cap_end=True, bark=0.1, seed=seed + k)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    def fmat(f):
        return m["inner"] if abs(f.normal.x) > 0.85 and f.calc_center_median().x ** 2 > (length * 0.45) ** 2 else m["bark"]
    return build(bm, name, face_mat=fmat, smooth_pred=lambda f: abs(f.normal.x) < 0.85)


def stump(name, seed, radius=0.13, height=0.2):
    m = _more_mats()
    rnd = random.Random(seed)
    bm = bmesh.new()
    pts = [Vector((0, 0, 0)), Vector((0, 0, height * 0.25)), Vector((0, 0, height * 0.7)), Vector((0, 0, height))]
    add_tube2(bm, pts, [radius * 1.45, radius * 1.1, radius, radius * 0.98], segs=9, cap_end=True, bark=0.15, seed=seed)
    for k in range(rnd.randint(2, 4)):
        ang = rnd.uniform(0, math.tau)
        d = Vector((math.cos(ang), math.sin(ang), 0))
        add_tube2(bm, [d * radius * 0.9 + Vector((0, 0, height * 0.12)), d * radius * 1.7 + Vector((0, 0, 0.01))],
                  [radius * 0.3, radius * 0.15], segs=5, cap_end=True, bark=0.1, seed=seed + k)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    def fmat(f):
        return m["inner"] if f.normal.z > 0.9 and f.calc_center_median().z > height * 0.9 else m["bark"]
    return build(bm, name, face_mat=fmat, smooth_pred=lambda f: f.normal.z < 0.9)


# ================================================================ 針葉樹（L4）

LANCE = [(0, 0.6), (0.22, 0.25), (0.26, -0.15), (0, -0.4), (-0.26, -0.15), (-0.22, 0.25)]  # 細長葉卡（樹頂用）


def _fan_pts(n=9, spread=150.0, r_out=0.55, r_in=0.46):
    """扁平的羽狀葉束：一片扇形，外緣鋸齒暗示一根根針葉。py 朝枝條前方。"""
    pts = [(0.0, -0.45)]
    for i in range(n):
        ang = math.radians(-spread / 2 + spread * i / (n - 1))
        r = r_out if i % 2 == 0 else r_in
        pts.append((r * math.sin(ang), -0.1 + r * math.cos(ang)))
    return pts


SPRAY = _fan_pts()


def add_card(bm, c, axis, normal, L, W, pts, shade_normal=None):
    """一片方向明確的葉卡：axis = 長軸方向，normal = 面朝向。"""
    axis = axis.normalized()
    u2 = normal.normalized().cross(axis).normalized()
    f = bm.faces.new([bm.verts.new(c + u2 * (px * W) + axis * (py * L)) for px, py in pts])
    if shade_normal is not None:
        _PENDING_NORMALS.append((f, shade_normal.normalized()))
    return f


def tree_pine_detailed(name, seed, height=2.0, tiers=6, shade=True, core=True):
    """針葉樹：樹幹 + 沿樹幹螺旋排列、往外下垂的枝條，每根枝條掛一排排針葉束；內核深色圓錐補洞。
    針葉束的受光法線 = 從樹軸往外 + 往上偏（圓錐表面），整棵樹像一個圓錐那樣平滑受光。"""
    rnd = random.Random(seed)
    bm = bmesh.new()
    hs = height / 2.0
    n = 5
    pts = [Vector((rnd.uniform(-0.01, 0.01) * hs, rnd.uniform(-0.01, 0.01) * hs, height * 0.97 * i / (n - 1))) for i in range(n)]
    pts[0] = Vector((0, 0, 0))
    add_tube(bm, pts, [0.075 * hs, 0.06 * hs, 0.045 * hs, 0.03 * hs, 0.008], segs=7)

    def radius_at(t):
        return height * (0.31 - 0.24 * t)

    def z_at(t):
        return height * (0.18 + 0.74 * t)

    N = tiers * 9
    golden = 2.399963
    branches = []
    for j in range(N):
        t = (j + 0.5) / N
        az = j * golden + rnd.uniform(-0.2, 0.2)
        radial = Vector((math.cos(az), math.sin(az), 0))
        L = radius_at(t) * rnd.uniform(0.88, 1.08)
        base = Vector((0, 0, z_at(t)))
        p1 = base + radial * L * 0.5 + Vector((0, 0, L * 0.05))
        p2 = base + radial * L + Vector((0, 0, -L * 0.2))
        stem = [base, p1, p2]
        branches.append((stem, radial, L))
    n_wood = len(bm.faces)
    for stem, radial, L in branches:   # 枝條用針葉的顏色，藏進針葉裡
        r0 = 0.011 * hs
        add_tube(bm, stem, [r0, r0 * 0.6, r0 * 0.25], segs=4)
    if core:
        segs_n = 4
        for i in range(segs_n):
            t0, t1 = i / segs_n, (i + 1) / segs_n
            z0, z1 = z_at(t0), z_at(t1)
            depth = (z1 - z0) * 1.15
            m = Matrix.Translation(Vector((0, 0, (z0 + z1) / 2 - depth * 0.05)))
            bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=True, segments=8, radius1=radius_at(t0) * 0.62,
                                  radius2=radius_at(t1) * 0.56, depth=depth, matrix=m, calc_uvs=False)
        m = Matrix.Translation(Vector((0, 0, z_at(1.0) + height * 0.03)))
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=True, segments=6, radius1=radius_at(1.0) * 0.75,
                              radius2=0.005, depth=height * 0.08, matrix=m, calc_uvs=False)
    up = Vector((0, 0, 1))
    for stem, radial, L in branches:
        side = Vector((-radial.y, radial.x, 0))
        fwd = (stem[2] - stem[0]).normalized()
        shade_n = (radial + Vector((0, 0, 0.5))).normalized()
        steps = 8
        for k in range(steps):
            tt = 0.15 + 0.85 * k / (steps - 1)
            p = lerp_polyline(stem, tt)
            s_ = L * (0.42 * (1 - 0.4 * tt) + 0.10)
            # 中央一片，沿枝條方向、微微下垂
            axis = fwd + Vector((0, 0, -0.18))
            add_card(bm, p + Vector((0, 0, s_ * 0.04)), axis, up, s_, s_ * 0.95, SPRAY, shade_n)
            # 兩側各一片，左右張開 ~28°、略往下，疊成扇形
            if True:
                for sgn in (-1, 1):
                    ax2 = (fwd * 0.88 + side * sgn * 0.47 + Vector((0, 0, -0.22)))
                    nrm = up + side * sgn * 0.25
                    add_card(bm, p + side * sgn * s_ * 0.12 - Vector((0, 0, s_ * 0.05)), ax2, nrm, s_ * 0.9, s_ * 0.85, SPRAY, shade_n)
    top = pts[-1]
    for k in range(6):
        az = k * math.tau / 6
        rad = Vector((math.cos(az), math.sin(az), 0))
        add_card(bm, top - Vector((0, 0, height * 0.03)) + rad * height * 0.02, up + rad * 0.5, rad,
                 height * 0.07, height * 0.06, SPRAY, rad + Vector((0, 0, 0.6)))
    return finish(bm, n_wood, name, mats()["pine"], shade, core_shade=0.68)
