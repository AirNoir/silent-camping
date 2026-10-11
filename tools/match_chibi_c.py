"""Match the user's LEFT setting-C reference using the saved, editable chibi.

Blender --background assets/source/chibi_c/before.blend --python tools/match_chibi_c.py
The original licensed hair and previous revision are kept in chibi_c/before.blend.
Only the revised model is exported; review cameras/lights are excluded.
"""
import ast
import bpy
import bmesh
import json
import math
from pathlib import Path
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "assets/source/chibi_c"
OUT.mkdir(parents=True, exist_ok=True)
sc = bpy.context.scene
root = bpy.data.objects["character_chibi_b"]
head = bpy.data.objects["Chibi_Base_Mesh2"]

# Reuse the established surface-projected feature builders, without running the
# original external hair-pack import or generating a second body/outfit.
source = (BASE / "tools/chibi_character.py").read_text()
helpers = {
    "mat", "hex2lin", "front_hit", "link", "ellipsoid", "decal", "arc_strip",
    "lerp3", "sstep", "color_iris", "link_vcol", "_closed_catmull",
    "make_eye_shape", "tube", "contour", "shade_color",
}
for node in ast.parse(source).body:
    if isinstance(node, ast.FunctionDef) and node.name in helpers:
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(BASE / "tools/chibi_character.py"), "exec"))

# Lift only the bottom of the face, preserving the supplied body and cranium.
# The neck blend prevents a step in the continuous head/body base mesh.
for v in head.data.vertices:
    x, y, z = v.co
    if -0.08 < z < 0.40:
        t = max(0.0, 1.0 - abs(z - 0.025) / 0.375)
        gate = min(1.0, max(0.0, (0.16 - y) / 0.32))
        v.co.z += 0.066 * t * t * (3 - 2 * t) * gate
        # Narrow just the lower jaw, retaining the cheek volume.
        v.co.x *= 1.0 - 0.018 * t * gate

FACE_NAMES = (
    "eye_sclera", "eye_sclera_shade", "eye_iris", "eye_iris_rim",
    "eye_pupil", "eye_contour_upper", "eye_contour_lower", "eye_glints",
    "brows", "mouth", "nose_hint",
)
for name in FACE_NAMES:
    ob = bpy.data.objects.get(name)
    if ob:
        bpy.data.objects.remove(ob, do_unlink=True)

bpy.context.view_layer.update()
ev = head.evaluated_get(bpy.context.evaluated_depsgraph_get())
bm = bmesh.new()
bm.from_mesh(ev.to_mesh())
ev.to_mesh_clear()
face_bvh = BVHTree.FromBMesh(bm)
bm.free()

# Tall eyes with a warm brown iris and visible ivory sclera at both sides.
# Values are in the original editable Blender coordinates (Z up, forward -Y).
FACE_DY = 0.0
EYE_Z, EYE_X, EYE_H, EYE_W = 0.393, 0.235, 0.108, 0.090
IRIS_W, IRIS_H = 0.068, 0.104
IRIS_UP, IRIS_IN = 0.005, 0.002
# Retain the preceding revision's pupil dimensions and position while changing
# only the surrounding iris/sclera balance.
PUPIL_KW, PUPIL_KH, PUPIL_UP = 0.586765, 0.618462, -0.003
BROW_BASE = 0.198
MOUTH_Z, NOSE_Z = 0.162, 0.263
EYE_VTOP, EYE_VBOT = 0.91, 1.0
EYE_OUTLINE = [(1.,0.),(.96,.35),(.80,.68),(.50,.90),(.15,1.),
               (-.25,.98),(-.62,.82),(-.90,.50),(-1.,.05),
               (-.92,-.42),(-.70,-.76),(-.35,-.96),(.05,-1.),
               (.45,-.92),(.78,-.68),(.96,-.35)]

# Keep the opening's height; soften only the ends of the upper lid. The maximum
# adjustment is 0.0025 source units (about 1% of the full eye height), blended
# into the existing silhouette rather than adding a distinct drooping tail.
_base_eye_shape = make_eye_shape
def make_eye_shape(sgn):
    base = _base_eye_shape(sgn)
    def shape(r, th):
        dx, dz = base(r, th)
        edge = min(1., max(0., (abs(dx)/EYE_W - .60)/.40))
        upper = min(1., max(0., (dz + .012)/.024))
        return dx, dz - .0025*edge*edge*upper
    return shape

M = {
    "skin": head.data.materials[0],
    "iris": mat("C_iris", (1, 1, 1), .78, .16),
    "pupil": mat("C_pupil", hex2lin("302015"), .8, .12),
    "sclera": mat("C_sclera", hex2lin("F2E5D2"), .85, .12),
    "sclera_sh": mat("C_sclera_sh", hex2lin("DCCAB1"), .85, .12),
    "lid": mat("C_lid", hex2lin("412B1D"), .85, .12),
    "iris_rim": mat("C_iris_rim", hex2lin("392419"), .85, .12),
    "lower": mat("C_lower", hex2lin("75503B"), .9, .1),
    "glint": mat("C_glint", hex2lin("FFF7E9"), .9, .1),
    "brow": mat("C_brow", hex2lin("60412A"), .9, .1),
    "mouth": mat("C_mouth", hex2lin("895035"), .9, .1),
    "nose": mat("C_nose", hex2lin("CB9173"), .9, .1),
}

features = source[source.index("sclera_bm, sclsh_bm,"):source.index("# 臉的柔和陰影：")]
# Preserve topology-building conventions; change the reference-driven contours.
features = features.replace("thick_b = 0.0115", "thick_b = 0.0065")
features = features.replace("0.024 * max", "0.034 * max")
features = features.replace("0.955, lambda u: 1.0", "0.977, lambda u: 1.0")
features = features.replace("0.035 + 0.110", "0.030 + 0.092")
features = features.replace("0.006 + 0.007", "0.010 + 0.007")
features = features.replace("u * 0.076", "u * 0.078")
features = features.replace("0.006 * (1 - u * u) ** 1.3 + 0.0026 * u * u", "0.011 * (1 - u * u) ** 1.1 + 0.009 * u * u")
features = features.replace("0.0020 + 0.0004 * u * u", "0.0038 + 0.0002 * u * u")
features = features.replace("(0.0104, 0.004, 0.0088)", "(0.0160, 0.004, 0.0140)")
features = features.replace("(0.0073, 0.004, 0.0065)", "(0.0080, 0.004, 0.0080)")
features = features.replace("u * 0.020", "u * 0.012")
features = features.replace("icx - 0.30 * IRIS_W, icz + PUPIL_UP + 0.30 * IRIS_H", "icx - 0.021, icz + PUPIL_UP + 0.0288")
features = features.replace("EYE_Z + oz + 0.10 * ext * t", "EYE_Z + oz - 0.035 * ext * t")
exec(compile(features, str(Path(__file__)), "exec"))

creasebm = bmesh.new()
for sign in (-1, 1):
    contour(creasebm, sign*EYE_X, EYE_Z, make_eye_shape(sign),
            35, 145, lambda u: 1.16,
            lambda u: 1.16 + .017*math.sin(math.pi*u), n=40, lift=.003)
link("C_upper_crease", creasebm, mat("C_crease",hex2lin("A5795C"),.9,.1))

# A sampled arch avoids the old polar brow's broad, almost straight leaf shape.
bpy.data.objects.remove(bpy.data.objects["brows"],do_unlink=True)
browbm=bmesh.new()
for sign in (-1,1):
    rows=[[],[]]
    for i in range(49):
        u=-1+2*i/48
        x=sign*EYE_X+u*.102
        z=EYE_Z+.196+.038*(1-u*u)-sign*.002*u
        thick=.0005+.0080*max(0,1-u*u)**.7
        for j in range(2):
            p,n=front_hit(x,z+(-1 if j==0 else 1)*thick)
            rows[j].append(browbm.verts.new(p+n*.004))
    for i in range(48):
        browbm.faces.new((rows[0][i],rows[0][i+1],rows[1][i+1],rows[1][i]))
link("brows",browbm,M["brow"])

# UV/image based iris color works in Blender and glTF without depending on a
# viewer's vertex-color handling. No duplicate COLOR_0 multiplication.
iris = bpy.data.objects["eye_iris"]
for attr in list(iris.data.color_attributes):
    iris.data.color_attributes.remove(attr)
uv = iris.data.uv_layers.new(name="IrisUV")
for loop in iris.data.loops:
    co = iris.data.vertices[loop.vertex_index].co
    uv.data[loop.index].uv = (.5, min(1, max(0, (co.z - (EYE_Z + IRIS_UP - IRIS_H)) / (2 * IRIS_H))))
nt = M["iris"].node_tree
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = bpy.data.images.load(str(OUT / "iris_gradient.png"), check_existing=True)
tex.image.pack()
tex.interpolation = "Linear"
tex.extension = "EXTEND"
nt.links.new(tex.outputs["Color"], nt.nodes.get("Principled BSDF").inputs["Base Color"])

# Bake the same skin shading into vertex colors for both saved source and GLB.
# This avoids exporting the nonportable procedural node network or applying its
# color twice on GLB reimport.
SKIN_BASE = (.88, .60, .44)
SHADE_BLOBS = [
    (.235, .515, .12, .04, .08, (.75, .48, .34)),
    (.235, .264, .13, .05, .07, (.82, .51, .38)),
    (0, .253, .035, .02, .16, (.77, .49, .34)),
    (.300, .285, .17, .12, .13, (.91, .54, .40)),
]
skin = M["skin"]
skin.name = "C_skin"
nt = skin.node_tree
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
for n in list(nt.nodes):
    if n.type not in ("BSDF_PRINCIPLED", "OUTPUT_MATERIAL"):
        nt.nodes.remove(n)
bsdf.inputs["Base Color"].default_value = (1, 1, 1, 1)
if head.data.color_attributes.get("SkinColor"):
    head.data.color_attributes.remove(head.data.color_attributes["SkinColor"])
ca = head.data.color_attributes.new("SkinColor", "FLOAT_COLOR", "POINT")
for v in head.data.vertices:
    ca.data[v.index].color = (*shade_color(v.co), 1)
head.data.color_attributes.active_color = ca
vc = nt.nodes.new("ShaderNodeVertexColor")
vc.layer_name = "SkinColor"
nt.links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])

# Some glTF viewers load COLOR_0 but leave its use disabled. Bake the original
# supplied UVs so skin, like the iris, relies on standard baseColorTexture.
assert head.data.uv_layers.active is not None
skin_image=bpy.data.images.new("C_skin_color",width=1024,height=1024,alpha=False)
skin_tex=nt.nodes.new("ShaderNodeTexImage")
skin_tex.image=skin_image
nt.nodes.active=skin_tex
emit=nt.nodes.new("ShaderNodeEmission")
nt.links.new(vc.outputs["Color"],emit.inputs["Color"])
output=next(n for n in nt.nodes if n.type=="OUTPUT_MATERIAL")
nt.links.new(emit.outputs[0],output.inputs["Surface"])
sc.render.engine="CYCLES"
sc.cycles.device="CPU"
sc.cycles.samples=1
bpy.ops.object.select_all(action="DESELECT")
head.select_set(True)
bpy.context.view_layer.objects.active=head
bpy.ops.object.bake(type="EMIT",margin=12,use_clear=True)
skin_image.filepath_raw=str(OUT/"skin_color.png")
skin_image.file_format="PNG"
skin_image.save()
skin_image.pack()
nt.links.new(bsdf.outputs[0],output.inputs["Surface"])
nt.links.new(skin_tex.outputs["Color"],bsdf.inputs["Base Color"])
nt.nodes.remove(emit)
nt.nodes.remove(vc)
for attr in list(head.data.color_attributes):
    head.data.color_attributes.remove(attr)

# Round the licensed clumps in this revision while keeping the prior mesh in
# the backup. Triangle pairing gives Catmull-Clark a usable flow along strands.
hair = [o for o in root.children if o.name.startswith("SM_Hair_")]
for ob in hair:
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for v in ob.data.vertices:
        co=ob.matrix_world@v.co
        if "Bangs" in ob.name:
            w=min(1,max(0,(.85-co.z)/.36))
            co.z-=(.110 if co.x<0 else .050)*w
        else:
            co.z+=.060*min(1,max(0,(.30-co.z)/.30))
            if abs(co.x)<.16 and co.z>1.20:
                co.z+=.045*min(1,(co.z-1.20)/.15)
        v.co=ob.matrix_world.inverted()@co
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.00005)
    bmesh.ops.join_triangles(bm, faces=list(bm.faces), angle_face_threshold=math.radians(70), angle_shape_threshold=math.radians(70))
    bm.to_mesh(ob.data)
    bm.free()
    sd = ob.modifiers.new("Rounded_reference_clumps", "SUBSURF")
    sd.levels = sd.render_levels = 2
    for p in ob.data.polygons:
        p.use_smooth = True
    # Soften coarse imported normal seams along each rounded clump.
    if ob.data.has_custom_normals:
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    ob.data.materials.clear()
    hmat = bpy.data.materials.get("C_hair") or mat("C_hair", hex2lin("6D4933"), .72, .21)
    ob.data.materials.append(hmat)

# Small swept outer lock visible on the reference's upper left silhouette.
# Its rounded base narrows into a flipped point rather than a spherical nub.
lockbm = bmesh.new()
lockpts = [(-.17,-.10,1.10),(-.22,-.12,1.11),(-.28,-.12,1.12),
           (-.34,-.11,1.14),(-.40,-.10,1.165),(-.43,-.09,1.19)]
tube(lockbm,lockpts,[(.080,.040),(.060,.034),(.045,.025),
                    (.027,.018),(.013,.010),(.001,.001)],k=12,side=(0,1,0))
lock=link("C_swept_lock",lockbm,hmat)
sd=lock.modifiers.new("Soft_swept_tip","SUBSURF")
sd.levels=sd.render_levels=2

# The left reference's cream hood wraps around the neck on both sides.
hoodmat = mat("C_hood", hex2lin("CDB99B"), .93, .12)
bpy.data.objects["hood"].data.materials.clear()
bpy.data.objects["hood"].data.materials.append(hoodmat)
hoodbm = bmesh.new()
for sign in (-1, 1):
    ctrl = [(sign*.13,.10,.005),(sign*.21,.035,-.03),
            (sign*.25,-.105,-.060),(sign*.20,-.22,-.145),
            (sign*.105,-.275,-.205)]
    # Cubic interpolation across the cushion, with narrower front tips.
    points = []
    for j in range(len(ctrl)-1):
        a = Vector(ctrl[max(0,j-1)]); b = Vector(ctrl[j]); c = Vector(ctrl[j+1]); d = Vector(ctrl[min(len(ctrl)-1,j+2)])
        for k in range(8):
            t = k/8
            points.append(.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t))
    points.append(Vector(ctrl[-1]))
    tube(hoodbm, points, [(.060*(1-.32*i/(len(points)-1)), .050) for i in range(len(points))], k=12, side=(1,0,0))
collar = link("C_hood_front", hoodbm, hoodmat)
sd = collar.modifiers.new("Padded_hood", "SUBSURF")
sd.levels = sd.render_levels = 1

# Neutral studio; front view is used for the reference comparison.
for ob in list(bpy.data.objects):
    if ob.type in ("LIGHT", "CAMERA"):
        bpy.data.objects.remove(ob, do_unlink=True)
sc.world.use_nodes = True
bg = sc.world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (.84,.84,.82,1)
bg.inputs["Strength"].default_value = .8
for name, energy, rotation, color in (
    ("C_Key",1.7,(55,-25,-30),(1,.97,.93)),
    ("C_Fill",.85,(70,20,40),(.98,.98,1)),
    ("C_Rim",.5,(60,0,170),(1,.96,.90)),
    ("C_LowerFill",.40,(110,0,0),(1,.97,.93)),
):
    ld = bpy.data.lights.new(name,"SUN")
    ld.energy = energy
    ld.angle = math.radians(25)
    ld.color = color
    ob = bpy.data.objects.new(name,ld)
    sc.collection.objects.link(ob)
    ob.rotation_euler = tuple(math.radians(v) for v in rotation)
cam = bpy.data.objects.new("C_Review",bpy.data.cameras.new("C_Review"))
sc.collection.objects.link(cam)
sc.camera = cam
engines = [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
sc.view_settings.view_transform = "Standard"
sc.render.image_settings.file_format = "PNG"
sc.render.resolution_percentage = 100

def render(name, center, direction, scale, size=(750,900)):
    center = Vector(center)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = scale
    cam.location = center + Vector(direction).normalized()*6
    cam.rotation_euler = (center-cam.location).to_track_quat("-Z","Y").to_euler()
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.filepath = str(OUT/name)
    bpy.ops.render.render(write_still=True)

render("after_front.png", (0,.05,.58), (0,-1,0), 1.78)
render("after_q34.png", (0,.05,.58), (.45,-1,.06), 1.78)
render("after_full.png", (0,.05,-.06), (.20,-1,.04), 3.12, (800,1000))
render("after_side.png", (0,.05,.58), (1,0,0), 1.78)
render("target_view.png", (0,.05,.58), (.09,-1,.025), 1.78)

# Save the editable revision in original Blender coordinates.
render_center = Vector((0,.05,.58))
cam.location = render_center + Vector((0,-1,0))*6
cam.rotation_euler = (render_center-cam.location).to_track_quat("-Z","Y").to_euler()
sc.render.resolution_x, sc.render.resolution_y = 750,900
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/"matched.blend"))

# Export in the established Godot/Fable orientation (+X forward, Y up in GLB).
k = 1.10/(1.213-(-1.434))
root.scale = (k,k,k)
root.rotation_euler = (0,0,math.pi/2)
root.location = (0,0,1.434*k)
bpy.ops.object.select_all(action="DESELECT")
for ob in [root]+list(root.children):
    ob.select_set(True)
bpy.context.view_layer.objects.active = root
bpy.ops.export_scene.gltf(filepath=str(OUT/"matched.glb"),export_format="GLB",use_selection=True,export_apply=True,export_vertex_color="ACTIVE")

# Reimport the delivered GLB in the SAME studio and source coordinate system.
# All review images after this point show the actual export, not the .blend.
for ob in list(root.children)+[root]:
    bpy.data.objects.remove(ob,do_unlink=True)
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(OUT/"matched.glb"))
imported = [ob for ob in bpy.data.objects if ob not in before]
inv = Matrix.Translation(Vector((0,0,1.434*k))) @ Matrix.Rotation(math.pi/2,4,"Z") @ Matrix.Diagonal((k,k,k,1))
for ob in imported:
    if ob.parent is None:
        ob.matrix_world = inv.inverted() @ ob.matrix_world
bpy.context.view_layer.update()
render("glb_front.png", (0,.05,.58), (0,-1,0), 1.78)
render("glb_q34.png", (0,.05,.58), (.45,-1,.06), 1.78)
print("CHIBI_C_REVISED",str(OUT/"matched.glb"))
