"""Reference-directed male camper, preserving the previous dressing experiment.
Blender --background Chibi_Base_Mesh2.blend --python tools/camper_reference.py
Uses the supplied base and licensed hair locally; exports a static review model.
"""
import bpy, bmesh, runpy, sys, math
from pathlib import Path
from mathutils import Vector

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / 'assets/source/camper_reference_male.blend'
GLB = BASE / 'assets/gen/camper_reference_male.glb'
sys.argv = ['dress', '--', str(OUT)]
n = runpy.run_path(str(BASE / 'tools/chibi_dress.py'))
root, body, M = n['root'], n['body'], n['M']
tube, link, rbox = n['tube'], n['link'], n['rbox']
root.name = 'Camper_Male_Reference'

# Add overlapping, rounded pointed fringe locks to the purchased side/back hair.
bm = bmesh.new()
for i, x in enumerate((-0.40, -0.29, -0.17, -0.045, 0.08, 0.205, 0.33, 0.43)):
    tip = (0.51, 0.57, 0.55, 0.49, 0.56, 0.52, 0.59, 0.47)[i]
    pts, widths = [], []
    for j in range(9):
        t = j / 8
        z = 1.10 * (1-t) + tip*t
        xx = x * (0.60 + 0.40*t) + 0.045*math.sin(math.pi*t)
        # Follow the frontal skull ellipsoid; expand slightly above skin.
        q = max(0.08, 1 - (xx/0.56)**2 - ((z-0.607)/0.68)**2)
        y = 0.065 - 0.56*math.sqrt(q) - 0.027
        pts.append((xx,y,z))
        w = (0.047 + 0.055*math.sin(math.pi*t))*(1-t**5)
        widths.append((max(0.003,w), max(0.003,0.045*(1-t**4))))
    tube(bm, pts, widths, k=12, side=(1,0,0))
link('rounded_fringe', bm, M['hair'], root, subsurf=1)

# Compress the long forehead while keeping the neck join and full outfit.
head_parts = {'eyes','eyelids','eye_glints','brows','mouth','ears','ear_inner','hair','rounded_fringe'}
for ob in root.children:
    if ob.type != 'MESH':
        continue
    if ob == body or ob.name in head_parts:
        for v in ob.data.vertices:
            if ob != body or v.co.z > 0:
                v.co.z *= 0.79
                v.co.x *= 1.07
    if ob.name == 'hair':
        for v in ob.data.vertices:
            if v.co.z > 0.83:
                v.co.z = 0.83 + (v.co.z-0.83)*0.65

# Jacket pockets, flaps, zipper pulls and hoodie cords are separate editable meshes.
detail = bmesh.new()
for s in (-1,1):
    rbox(detail, (s*0.155,-0.265,-0.51), (0.135,0.045,0.145), bevel=0.018)
    rbox(detail, (s*0.155,-0.288,-0.435), (0.145,0.024,0.036), bevel=0.01)
link('jacket_patch_pockets',detail,M['jacket'],root)
cord = bmesh.new()
for s in (-1,1):
    tube(cord, [(s*0.10,-0.185,-0.085),(s*0.095,-0.235,-0.18),(s*0.11,-0.25,-0.30)],0.009,k=8)
link('hood_drawstrings',cord,M['cream'],root)

root['status'] = 'Static visual prototype; no animation rig yet'
root['source_base'] = 'Chibi_Base_Mesh2.blend'
root['source_hair'] = 'Men Hair Set 04 / SM_M_Head_s.04.glb'
root['reference'] = '森林露營角色設定板.png / male orange outfit'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
k = 1.10/(1.213*0.79-n['GROUND'])
root.scale = (k,k,k)
root.rotation_euler.z = math.pi/2
root.location.z = -n['GROUND']*k
bpy.ops.object.select_all(action='DESELECT')
for ob in [root]+list(root.children):
    ob.select_set(True)
bpy.context.view_layer.objects.active = root
bpy.ops.export_scene.gltf(filepath=str(GLB),export_format='GLB',use_selection=True,export_apply=True)
print('REFERENCE_MODEL', OUT, GLB)
