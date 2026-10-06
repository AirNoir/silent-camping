"""Hand-directed stylized camper meshes and studio review views.
Blender --background --python tools/sculpt_camper.py
Independent revision: never overwrites previous prototypes or supplied assets.
"""
import bpy, bmesh, math, sys, json
from pathlib import Path
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / 'assets/source/camper_sculpt'
DEST.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
char_col = bpy.data.collections.new('CHARACTER | male orange camper')
scene.collection.children.link(char_col)
root = bpy.data.objects.new('Camper_Male_Sculpt', None)
char_col.objects.link(root)

def rgb(h):
    vals = [int(h[i:i+2],16)/255 for i in (0,2,4)]
    return tuple(v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in vals)

def material(name,h,rough=.74):
    m = bpy.data.materials.new('camp_'+name)
    m.diffuse_color = (*rgb(h),1)
    m.use_nodes = True
    p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*rgb(h),1)
    p.inputs['Roughness'].default_value=rough
    p.inputs['Specular IOR Level'].default_value=.23
    return m

M={n:material(n,h) for n,h in {
    'skin':'F3C5A1','ear':'DCA07F','hair':'493128','hair_light':'50372C',
    'hair_dark':'402B24','eye':'36251F','brow':'604032','mouth':'B77057',
    'jacket':'D78336','jacket_trim':'BE6C2C','stitch':'E49C55',
    'cream':'EFE2C7','hood_inner':'D5C7AA','pants':'59613B','pants_shadow':'4D5533',
    'cuff':'6A714A','boot':'73503A','boot_dark':'513C2D','sole':'B5A085',
    'laces':'C3A077','pack':'493D34','pack_edge':'5B493B','patch':'B38251',
    'metal':'A89572','pupil_glint':'9C8070',
}.items()}

def mesh(name,verts,faces,mat,sub=0):
    me=bpy.data.meshes.new(name)
    me.from_pydata(verts,[],faces);me.update()
    bm=bmesh.new();bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
    bm.to_mesh(me);bm.free()
    o=bpy.data.objects.new(name,me);char_col.objects.link(o);o.parent=root
    me.materials.append(M[mat])
    for p in me.polygons:p.use_smooth=True
    if sub:
        mod=o.modifiers.new('Sculpt surface','SUBSURF');mod.levels=mod.render_levels=sub
    return o

def sphere(name,c,r,mat,rot=None):
    bm=bmesh.new()
    trans=Matrix.Translation(Vector(c)) @ (rot or Matrix.Identity(3)).to_4x4() @ Matrix.Diagonal((*r,1))
    bmesh.ops.create_uvsphere(bm,u_segments=32,v_segments=20,radius=1,matrix=trans)
    me=bpy.data.meshes.new(name);bm.to_mesh(me);bm.free()
    o=bpy.data.objects.new(name,me);char_col.objects.link(o);o.parent=root
    me.materials.append(M[mat])
    for p in me.polygons:p.use_smooth=True
    return o

def box(name,c,size,mat,bevel=.01,rot=None):
    bm=bmesh.new();bmesh.ops.create_cube(bm,size=1)
    for v in bm.verts:v.co=Vector((v.co.x*size[0],v.co.y*size[1],v.co.z*size[2]))
    if bevel:bmesh.ops.bevel(bm,geom=list(bm.edges),offset=bevel,segments=5,affect='EDGES',profile=.5,clamp_overlap=True)
    trans=Matrix.Translation(Vector(c))@(rot or Matrix.Identity(3)).to_4x4()
    bm.transform(trans);bm.normal_update()
    me=bpy.data.meshes.new(name);bm.to_mesh(me);bm.free()
    o=bpy.data.objects.new(name,me);char_col.objects.link(o);o.parent=root
    me.materials.append(M[mat])
    for p in me.polygons:p.use_smooth=True
    mod=o.modifiers.new('Weighted face normals','WEIGHTED_NORMAL');mod.keep_sharp=True;mod.weight=35
    return o

def curve(name,pts,r,mat):
    d=bpy.data.curves.new(name,'CURVE');d.dimensions='3D';d.resolution_u=16
    d.bevel_depth=r;d.bevel_resolution=3
    sp=d.splines.new('BEZIER');sp.bezier_points.add(len(pts)-1)
    for p,co in zip(sp.bezier_points,pts):p.co=co;p.handle_left_type=p.handle_right_type='AUTO'
    o=bpy.data.objects.new(name,d);char_col.objects.link(o);o.parent=root;d.materials.append(M[mat])
    return o

def sgnpow(x,p):return math.copysign(abs(x)**p,x)

def loft(name,sections,mat,ex=2.5,n=40,sub=1):
    # Each section: center xyz, radius x, radius y.
    vs=[];fs=[]
    for x,y,z,rx,ry in sections:
        for j in range(n):
            a=2*math.pi*j/n
            vs.append((x+rx*sgnpow(math.sin(a),2/ex),y-ry*sgnpow(math.cos(a),2/ex),z))
    for i in range(len(sections)-1):
        for j in range(n):
            a=i*n+j;b=i*n+(j+1)%n;fs.append((a,b,b+n,a+n))
    fs.append(tuple(reversed(range(n))));fs.append(tuple((len(sections)-1)*n+j for j in range(n)))
    return mesh(name,vs,fs,mat,sub)

def bezier(p,t):
    return (1-t)**3*p[0]+3*(1-t)**2*t*p[1]+3*(1-t)*t*t*p[2]+t**3*p[3]

def lock(name,control,width,thick,mat='hair',normal=(0,-1,0)):
    # Broad, convex, curved leaf section; individual tips have a tiny rounded end.
    p=list(map(Vector,control));vs=[];fs=[];rows=19;cols=16
    for i in range(rows):
        t=i/(rows-1);c=bezier(p,t)
        tangent=(bezier(p,min(1,t+.002))-bezier(p,max(0,t-.002))).normalized()
        outward=Vector(normal)
        outward=(outward-tangent*outward.dot(tangent)).normalized()
        side=tangent.cross(outward).normalized()
        profile=(.68+.32*math.sin(math.pi*t))*(1-t**6.0)
        rw=max(.0008,width*profile);rd=max(.0007,thick*(.65+.35*math.sin(math.pi*t))*(1-t**2.8))
        for j in range(cols):
            a=2*math.pi*j/cols
            v=c+side*rw*math.cos(a)+outward*rd*math.sin(a)
            vs.append(tuple(v))
    for i in range(rows-1):
        for j in range(cols):
            a=i*cols+j;b=i*cols+(j+1)%cols;fs.append((a,b,b+cols,a+cols))
    fs.append(tuple(reversed(range(cols))));fs.append(tuple((rows-1)*cols+j for j in range(cols)))
    return mesh(name,vs,fs,mat,1)

# Head: wide cheeks, shallow face, soft chin. Hair is roughly 36% of full height.
head=loft('Head | soft cheeks',[
    (0,.010,.814,.035,.05),(0,.010,.828,.106,.101),
    (0,.012,.858,.179,.156),(0,.013,.906,.221,.187),
    (0,.015,.961,.239,.201),(0,.016,1.025,.242,.208),
    (0,.021,1.091,.236,.206),(0,.025,1.148,.211,.185),
    (0,.024,1.193,.158,.145),(0,.023,1.222,.090,.084),
    (0,.023,1.235,.015,.016),
],'skin',ex=2.25,n=64,sub=2)
bpy.context.view_layer.update()
deps=bpy.context.evaluated_depsgraph_get();ev=head.evaluated_get(deps)
bm=bmesh.new();bm.from_mesh(ev.to_mesh());ev.to_mesh_clear();bvh=BVHTree.FromBMesh(bm);bm.free()

def facepos(x,z):
    p,n,_,_=bvh.ray_cast(Vector((x,-1,z)),Vector((0,1,0)))
    return p,n

def ellipse_decal(name,x,z,rx,rz,mat):
    vs=[];fs=[];N=40;R=5
    p,n=facepos(x,z);vs.append(tuple(p+n*.0018))
    for i in range(1,R+1):
        rr=i/R
        for j in range(N):
            a=2*math.pi*j/N
            power=.82 if mat=='eye' else 1.0
            p,n=facepos(x+rx*rr*sgnpow(math.cos(a),power),z+rz*rr*sgnpow(math.sin(a),power))
            vs.append(tuple(p+n*(.0012+.0010*(1-rr*rr))))
    for j in range(N):fs.append((0,1+j,1+(j+1)%N))
    for i in range(R-1):
        for j in range(N):
            a=1+i*N+j;b=1+i*N+(j+1)%N;fs.append((a,b,b+N,a+N))
    return mesh(name,vs,fs,mat)

for s in (-1,1):
    ellipse_decal(f'Eye_{s}',s*.092,.979,.0185,.035,'eye')
    bp=[]
    for j in range(5):
        x=s*.093-.023+.046*j/4;z=1.029+.008*math.sin(math.pi*j/4)
        p,n=facepos(x,z);bp.append(tuple(p+n*.0017))
    curve(f'Brow_{s}',bp,.0037,'brow')
    sphere(f'Ear_{s}',(s*.234,.004,.973),(.028,.031,.044),'skin')
    sphere(f'Ear_inner_{s}',(s*.246,-.020,.974),(.013,.009,.023),'ear')
# Little nose, almost flat, and subtle smile.
p,n=facepos(0,.942);sphere('Nose',p+n*.0005,(.012,.008,.009),'skin')
mp=[]
for i in range(9):
    x=-.016+.032*i/8;p,n=facepos(x,.910+.004*(x/.016)**2);mp.append(tuple(p+n*.0016))
curve('Smile',mp,.0016,'mouth')

# Continuous scalp shell with angle-specific hairline.
vs=[];fs=[];N=64;R=18
for i in range(R+1):
    t=(i+.08)/(R+.08)
    for j in range(N):
        az=2*math.pi*j/N
        # Front .107 above eyes, lower at side and nape.
        front=max(0,math.cos(az));back=max(0,-math.cos(az))
        zline=.962+.104*front**2-.020*back
        boundary=math.acos((zline-1.095)/.220)
        th=t*boundary
        vs.append((.258*math.sin(th)*math.sin(az),.025-.226*math.sin(th)*math.cos(az),1.095+.220*math.cos(th)))
for i in range(R):
    for j in range(N):
        a=i*N+j;b=i*N+(j+1)%N;fs.append((a,b,b+N,a+N))
fs.append(tuple(reversed(range(N))))
scalp=mesh('Hair | underlying cap',vs,fs,'hair_dark',1)

# Front locks: asymmetrical tufts, tips stop at the eye line instead of a comb row.
front_locks=[
    ([(-.055,-.084,1.272),(-.132,-.164,1.250),(-.238,-.186,1.109),(-.242,-.128,.965)],.053,.020),
    ([(.025,-.069,1.292),(-.075,-.175,1.267),(-.183,-.231,1.140),(-.182,-.206,1.026)],.068,.024),
    ([(.062,-.077,1.279),(-.017,-.185,1.249),(-.108,-.239,1.113),(-.084,-.218,1.042)],.062,.025),
    ([(.060,-.095,1.268),(.008,-.198,1.217),(-.014,-.240,1.081),(.015,-.219,1.024)],.059,.025),
    ([(.111,-.097,1.254),(.098,-.192,1.211),(.104,-.238,1.109),(.100,-.216,1.030)],.046,.021),
    ([(.113,-.073,1.274),(.192,-.170,1.227),(.196,-.212,1.127),(.192,-.181,.979)],.060,.023),
    ([(.143,-.015,1.272),(.244,-.092,1.206),(.243,-.161,1.098),(.242,-.112,.956)],.052,.022),
]
for i,(p,w,d) in enumerate(front_locks):lock(f'Hair | fringe {i+1:02d}',p,w,d,'hair_light' if i in (1,4) else 'hair')

# Radial crown and rear locks are broad sculpted layers, each with a hooked tip.
for i,azdeg in enumerate((62,88,114,139,166,193,218,244,273,301)):
    az=math.radians(azdeg)
    def hp(radius,z,delta=0):
        a=az+delta;return (radius*math.sin(a),.025-radius*.87*math.cos(a),z)
    normal=(math.sin(az),-math.cos(az),.12)
    lock(f'Hair | crown {i:02d}',[hp(.055,1.298,-.38),hp(.17,1.309,-.16),hp(.263,1.198,.03),hp(.288,1.147,.22)],.054,.021,'hair',normal)
    lock(f'Hair | lower {i:02d}',[hp(.205,1.201,-.16),hp(.264,1.142,-.07),hp(.274,1.027,.06),hp(.279,.990,.24)],.048,.023,'hair_dark' if i%4==0 else 'hair',normal)
# Shorter cross-swept locks break up the crown's regular fan pattern.
lock('Hair | sweeping top left',[(.042,-.067,1.302),(-.045,-.088,1.333),(-.155,-.110,1.293),(-.221,-.123,1.254)],.041,.019,'hair',normal=(0,-1,.4))
lock('Hair | sweeping top right',[(.040,-.014,1.309),(.124,-.011,1.327),(.198,-.043,1.280),(.227,-.073,1.242)],.038,.018,'hair',normal=(0,-1,.4))
lock('Hair | temple flick left',[(-.177,-.127,1.193),(-.242,-.154,1.164),(-.270,-.147,1.117),(-.294,-.118,1.106)],.029,.014,'hair',normal=(-.4,-1,0))
lock('Hair | temple flick right',[(.179,-.115,1.185),(.250,-.136,1.163),(.279,-.122,1.125),(.293,-.095,1.132)],.029,.014,'hair',normal=(.4,-1,0))
# Small cowlicks make the top silhouette uneven.
lock('Hair | crown flick left',[(.025,.001,1.289),(-.040,-.009,1.331),(-.111,.006,1.339),(-.139,.016,1.353)],.028,.014,'hair',normal=(0,-1,.6))
lock('Hair | crown flick right',[(.041,.037,1.291),(.080,.063,1.342),(.118,.065,1.352),(.139,.057,1.360)],.023,.012,'hair',normal=(0,-1,.6))

# Neck and cream hoodie under the open orange jacket.
loft('Neck',[(0,.02,.752,.040,.038),(0,.02,.849,.040,.038)],'skin',ex=2,n=28,sub=1)
loft('Cream hoodie | torso',[(0,.010,.350,.119,.072),(0,.01,.360,.126,.077),(0,.01,.430,.127,.080),
    (0,.012,.640,.121,.081),(0,.017,.738,.115,.075),(0,.017,.783,.063,.049)],'cream',sub=1)

# Jacket: open quad surface with tailored, clean front boundaries.
sec=[(.355,.143,.098,.018),(.366,.151,.104,.019),(.410,.151,.107,.022),
     (.520,.144,.105,.026),(.645,.145,.104,.031),(.721,.138,.096,.041),
     (.761,.117,.079,.048),(.792,.065,.046,.042)]
vs=[];fs=[];N=48
edge_left=[];edge_right=[]
for z,rx,ry,gap in sec:
    a0=math.asin(min(.9,(gap/rx)**(2.6/2)))
    for j in range(N+1):
        a=a0+(2*math.pi-2*a0)*j/N
        v=(rx*sgnpow(math.sin(a),2/2.6),.014-ry*sgnpow(math.cos(a),2/2.6),z)
        vs.append(v)
        if j==0:edge_right.append(v)
        if j==N:edge_left.append(v)
for i in range(len(sec)-1):
    for j in range(N):
        a=i*(N+1)+j;fs.append((a,a+1,a+N+2,a+N+1))
jacket=mesh('Jacket | tailored open body',vs,fs,'jacket',2)
sol=jacket.modifiers.new('Fabric thickness','SOLIDIFY');sol.thickness=.005;sol.offset=-1
for name,pts in [('left',edge_left),('right',edge_right)]:
    curve('Jacket | zipper seam '+name,[(x,y-.002,z) for x,y,z in pts],.003,'jacket_trim')
    curve('Jacket | zipper tape '+name,[(x+(-.004 if x<0 else .004),y-.003,z) for x,y,z in pts[:-1]],.0014,'stitch')
# Hem is narrow, regular and follows the garment surface.
hem=[]
z,rx,ry,gap=sec[1];a0=math.asin((gap/rx)**1.3)
for j in range(65):
    a=a0+(2*math.pi-2*a0)*j/64
    hem.append((rx*sgnpow(math.sin(a),2/2.6),.014-ry*sgnpow(math.cos(a),2/2.6),.366))
curve('Jacket | hem seam',hem,.0021,'jacket_trim')

for s in (-1,1):
    # Long relaxed sleeves with gently angled elbows, no ball joints.
    loft(f'Sleeve_{s}',[(s*.117,.012,.760,.038,.052),(s*.141,.012,.744,.053,.060),
        (s*.167,.012,.689,.058,.062),(s*.180,.008,.611,.053,.056),
        (s*.196,-.004,.510,.047,.051),(s*.205,-.010,.426,.044,.047),
        (s*.205,-.010,.417,.043,.046)],'jacket',ex=2.25,n=32,sub=2)
    loft(f'Sleeve cuff_{s}',[(s*.205,-.010,.409,.044,.047),(s*.205,-.010,.414,.047,.050),
        (s*.204,-.010,.433,.047,.050),(s*.204,-.010,.438,.045,.048)],'cuff',n=32,sub=1)
    # Rounded mitt hand, with an integrated-looking short thumb.
    sphere(f'Hand_{s}',(s*.211,-.007,.374),(.032,.027,.045),'skin',Matrix.Rotation(-s*.15,3,'Y'))
    sphere(f'Thumb_{s}',(s*.181,-.027,.382),(.013,.017,.028),'skin',Matrix.Rotation(s*.48,3,'Y'))
    curve(f'Hand finger crease_{s}',[(s*.224,-.032,.359),(s*.222,-.033,.351)],.00055,'ear')
    # Patch pockets and diagonal opening seams on the jacket front.
    box(f'Jacket pocket_{s}',(s*.091,-.090,.458),(.079,.015,.097),'jacket',.010)
    curve(f'Jacket pocket welt_{s}',[(s*.126,-.102,.499),(s*.095,-.110,.485),(s*.060,-.106,.467)],.0028,'jacket_trim')
    curve(f'Jacket pocket stitch_{s}',[(s*.123,-.102,.476),(s*.124,-.103,.417),(s*.060,-.105,.417)],.0008,'stitch')

# Folded hood: back basin and two distinct front lapels.
hood=[]
for j in range(19):
    a=math.radians(-118+236*j/18)
    hood.append((.067*math.sin(a),.024+.054*math.cos(a),.789+.012*math.cos(a)))
curve('Hood | orange outer rim',hood,.026,'jacket')
curve('Hood | cream inner rim',[(x*.80,y-.006,z+.004) for x,y,z in hood],.017,'cream')
sphere('Hood | folded back',(0,.103,.753),(.106,.048,.063),'jacket')
sphere('Hood | cream lining',(0,.077,.770),(.083,.035,.048),'hood_inner')
for s in (-1,1):
    # Curved cream edges in front, resting against the orange collar.
    # Broad folded lining panels create the V-shaped hoodie neckline.
    cp=[(s*.049,-.038,.793),(s*.062,-.064,.773),(s*.047,-.092,.746),(s*.019,-.100,.718)]
    vs=[];fs=[]
    for i,(x,y,z) in enumerate(cp):
        w=(.022,.025,.024,.010)[i]
        for j in range(5):
            f=-1+j*.5;vs.append((x+s*w*f,y-.004*(1-f*f),z+.011*f))
    for i in range(3):
        for j in range(4):a=i*5+j;fs.append((a,a+1,a+6,a+5))
    lapel=mesh(f'Hood | folded lining_{s}',vs,fs,'cream',2)
    sol=lapel.modifiers.new('Lining thickness','SOLIDIFY');sol.thickness=.006
    curve(f'Hood | orange fold_{s}',[(s*.074,-.040,.788),(s*.086,-.066,.772),(s*.065,-.094,.742)],.013,'jacket')
    curve(f'Hood drawstring_{s}',[(s*.040,-.067,.773),(s*.039,-.089,.714),(s*.043,-.094,.657)],.0022,'hood_inner')
    box(f'Drawstring tip_{s}',(s*.043,-.094,.650),(.005,.005,.018),'cream',.002)
box('Zipper pull',(.024,-.095,.484),(.009,.008,.022),'metal',.003)

# Straight cropped cargo trousers, separate folds and pocket flaps.
loft('Trousers | seat',[(0,.018,.286,.125,.081),(0,.016,.325,.134,.091),
    (0,.012,.378,.130,.087),(0,.012,.399,.119,.080)],'pants',n=40,sub=1)
for s in (-1,1):
    x=s*.071
    loft(f'Trouser leg_{s}',[(x,.010,.150,.058,.063),(x,.010,.160,.063,.066),
        (x,.010,.206,.062,.066),(x,.012,.270,.064,.072),(x,.016,.318,.067,.077),
        (x,.016,.344,.065,.074)],'pants',ex=2.8,n=32,sub=1)
    loft(f'Trouser turnup_{s}',[(x,.010,.137,.059,.063),(x,.010,.142,.066,.071),
        (x,.010,.178,.066,.071),(x,.010,.183,.062,.067)],'cream',ex=2.8,n=32,sub=1)
    box(f'Cargo side pocket_{s}',(s*.130,.007,.251),(.021,.083,.092),'pants',.009)
    box(f'Cargo pocket flap_{s}',(s*.142,.006,.294),(.014,.089,.026),'pants_shadow',.005)
    box(f'Cargo pocket tab_{s}',(s*.150,-.007,.275),(.004,.017,.022),'pants',.002)
    # Hiking boots: flatter sole, round toe, raised shaft and contrasting upper cuff.
    box(f'Boot sole_{s}',(x,-.039,.027),(.143,.225,.036),'sole',.016)
    box(f'Boot welt_{s}',(x,-.039,.046),(.142,.220,.014),'boot_dark',.006)
    toe=box(f'Boot rounded toe_{s}',(x,-.067,.078),(.135,.160,.076),'boot',.033)
    ankle=loft(f'Boot ankle_{s}',[(x,.022,.043,.057,.058),(x,.023,.069,.059,.061),
        (x,.023,.116,.057,.058),(x,.023,.145,.059,.061)],'boot',ex=2.6,n=32,sub=1)
    loft(f'Boot padded collar_{s}',[(x,.022,.129,.059,.062),(x,.022,.135,.065,.066),
        (x,.022,.146,.065,.066),(x,.022,.151,.060,.062)],'boot_dark',n=32,sub=1)
    tongue=box(f'Boot tongue_{s}',(x,-.051,.118),(.062,.020,.069),'boot_dark',.008,Matrix.Rotation(math.radians(-22),3,'X'))
    bpy.context.view_layer.update();boot_bm=bmesh.new()
    for piece in (toe,ankle,tongue):
        ev=piece.evaluated_get(bpy.context.evaluated_depsgraph_get())
        boot_bm.from_mesh(ev.to_mesh());ev.to_mesh_clear()
    boot_bvh=BVHTree.FromBMesh(boot_bm);boot_bm.free()
    for j in range(4):
        y=-.038-j*.020
        lace_points=[]
        for xx in (x-.031,x,x+.031):
            p,n,_,_=boot_bvh.ray_cast(Vector((xx,y,1)),Vector((0,0,-1)))
            lace_points.append(tuple(p+n*.0028))
        curve(f'Boot lace_{s}_{j}',lace_points,.0025,'laces')
        for side,p in ((-1,lace_points[0]),(1,lace_points[-1])):
            sphere(f'Boot eyelet_{s}_{j}_{side}',p,(.0035,.0035,.002),'metal')
    curve(f'Boot toe seam_{s}',[(x-.050,-.108,.071),(x-.036,-.135,.076),(x,-.145,.078),(x+.036,-.135,.076),(x+.050,-.108,.071)],.0008,'laces')

# Compact daypack, physical shoulder webbing, leather diamond and buckle straps.
box('Backpack | main',(0,.172,.570),(.258,.135,.295),'pack',.040)
box('Backpack | top flap',(0,.187,.714),(.261,.142,.053),'pack_edge',.022)
box('Backpack | front pocket',(0,.251,.497),(.196,.048,.111),'pack',.017)
box('Backpack | pocket flap',(0,.270,.547),(.199,.031,.034),'pack_edge',.011)
curve('Backpack | grab loop',[(-.032,.152,.719),(-.027,.151,.753),(.027,.151,.753),(.032,.152,.719)],.007,'pack_edge')
box('Backpack | diamond patch',(0,.245,.646),(.047,.010,.047),'patch',.005,Matrix.Rotation(math.pi/4,3,'Y'))
for s in (-1,1):
    box(f'Patch slit_{s}',(s*.007,.251,.646),(.002,.002,.012),'boot_dark',.001)
    box(f'Backpack side pocket_{s}',(s*.130,.175,.502),(.036,.096,.124),'pack_edge',.014)
    box(f'Backpack buckle strap_{s}',(s*.068,.282,.489),(.016,.010,.153),'pack_edge',.004)
    box(f'Backpack buckle_{s}',(s*.068,.291,.501),(.025,.011,.022),'boot_dark',.004)
    # A flat rectangular sweep following the body, rather than floating rods.
    path=[(s*.083,.147,.724),(s*.099,.078,.774),(s*.106,.016,.780),
          (s*.108,-.065,.739),(s*.107,-.096,.644),(s*.111,-.097,.555),(s*.122,-.069,.463)]
    vs=[];fs=[]
    for i,p in enumerate(path):
        for xx,yy in ((-.014,-.004),(.014,-.004),(.014,.004),(-.014,.004)):
            vs.append((p[0]+xx,p[1]+yy,p[2]))
    for i in range(len(path)-1):
        for j in range(4):a=4*i+j;b=4*i+(j+1)%4;fs.append((a,b,b+4,a+4))
    fs.extend([(3,2,1,0),tuple(4*(len(path)-1)+j for j in range(4))])
    mesh(f'Backpack shoulder strap_{s}',vs,fs,'pack',2)
    box(f'Shoulder strap adjuster_{s}',(s*.108,-.103,.592),(.036,.012,.018),'pack_edge',.004)

# Review rig belongs to a separate collection and is excluded from GLB export.
studio=bpy.data.collections.new('STUDIO | review lighting and cameras');scene.collection.children.link(studio)
def area(name,loc,energy,size,target,color=(1,1,1)):
    d=bpy.data.lights.new(name,'AREA');d.energy=energy;d.shape='DISK';d.size=size;d.color=color
    o=bpy.data.objects.new(name,d);studio.objects.link(o);o.location=loc
    o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area('Softbox key',(-2,-3,4),180,3,(0,0,.7),(1,.96,.92))
area('Softbox fill',(2,-2,2.3),100,3,(0,0,.7),(.90,.95,1))
area('Softbox rim',(1,2,3),180,2,(0,0,1),(1,.96,.92))
world=bpy.data.worlds.new('Warm grey studio');scene.world=world;world.use_nodes=True
world.node_tree.nodes['Background'].inputs[0].default_value=(.68,.67,.63,1)
world.node_tree.nodes['Background'].inputs[1].default_value=.35
world_nodes=world.node_tree.nodes
world_path=world_nodes.new('ShaderNodeLightPath')
world_camera=world_nodes.new('ShaderNodeBackground')
world_camera.inputs[0].default_value=(*rgb('E9E5DC'),1)
world_camera.inputs[1].default_value=1.3
world_mix=world_nodes.new('ShaderNodeMixShader')
world.node_tree.links.new(world_path.outputs['Is Camera Ray'],world_mix.inputs[0])
world.node_tree.links.new(world_nodes['Background'].outputs[0],world_mix.inputs[1])
world.node_tree.links.new(world_camera.outputs[0],world_mix.inputs[2])
world.node_tree.links.new(world_mix.outputs[0],world_nodes['World Output'].inputs[0])
floor_mat=material('studio_floor','E9E5DC',.85)
me=bpy.data.meshes.new('Floor');me.from_pydata([(-200,-200,0),(200,-200,0),(200,200,0),(-200,200,0)],[],[(0,1,2,3)])
floor=bpy.data.objects.new('Floor | studio only',me);studio.objects.link(floor);me.materials.append(floor_mat)
cam=bpy.data.objects.new('Review camera',bpy.data.cameras.new('Review camera'));studio.objects.link(cam);scene.camera=cam
cam.data.type='ORTHO';cam.data.ortho_scale=1.55
scene.render.engine='CYCLES';scene.cycles.samples=48;scene.cycles.use_denoising=True
scene.render.resolution_x=900;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
scene.view_settings.view_transform='Standard'
scene.view_settings.look='None'
scene.view_settings.exposure=-.35
floor_bsdf=floor_mat.node_tree.nodes.get('Principled BSDF')
floor_bsdf.inputs['Emission Color'].default_value=(*rgb('E9E5DC'),1)
lightpath=floor_mat.node_tree.nodes.new('ShaderNodeLightPath')
camera_emission=floor_mat.node_tree.nodes.new('ShaderNodeMath');camera_emission.operation='MULTIPLY'
camera_emission.inputs[1].default_value=.85
floor_mat.node_tree.links.new(lightpath.outputs['Is Camera Ray'],camera_emission.inputs[0])
floor_mat.node_tree.links.new(camera_emission.outputs[0],floor_bsdf.inputs['Emission Strength'])
scene.render.image_settings.file_format='PNG'

def view(yaw,pitch=0,center=(0,0,.680),scale=1.55):
    y=math.radians(yaw);p=math.radians(pitch);target=Vector(center)
    cam.location=target+Vector((math.sin(y)*math.cos(p),-math.cos(y)*math.cos(p),math.sin(p)))*4
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.ortho_scale=scale
view(25,7)
root['reference']='森林露營角色設定板.png / Main Character Male'
root['status']='Visual sculpt revision. Static asset, animation rig pending.'
root['forward']='-Y in Blender, +X in Godot'
root['height_m']=1.36
root.location.z=-.009
bpy.ops.wm.save_as_mainfile(filepath=str(DEST/'camper_male_sculpt.blend'))

# Convert curve accents to mesh for consistent export, with modifiers applied by exporter.
bpy.ops.object.select_all(action='DESELECT')
for o in list(char_col.objects):
    if o.type=='CURVE':
        o.select_set(True);bpy.context.view_layer.objects.active=o
        bpy.ops.object.convert(target='MESH');o.select_set(False)
root.rotation_euler.z=math.pi/2
for o in char_col.objects:o.select_set(True)
bpy.context.view_layer.objects.active=root
glb=ROOT/'assets/gen/camper_male_sculpt.glb'
bpy.ops.export_scene.gltf(filepath=str(DEST/'camper_male_sculpt_high.glb'),export_format='GLB',use_selection=True,export_apply=True)
root.rotation_euler.z=0
sys.path.insert(0,str(ROOT/'tools'))
from camper_export import export_game_asset
game_stats=export_game_asset(char_col,glb)

for name,yaw,pitch in [('front',0,0),('q34',30,6),('side',90,0),('back',180,0)]:
    view(yaw,pitch)
    scene.render.filepath=str(DEST/f'male_{name}.png')
    bpy.ops.render.render(write_still=True)
view(12,3,(0,-.02,1.087),.69)
scene.render.resolution_x=scene.render.resolution_y=1000
scene.render.filepath=str(DEST/'male_face.png');bpy.ops.render.render(write_still=True)
stats={'game':game_stats,'objects':len(char_col.objects),'mesh_vertices':sum(len(o.data.vertices) for o in char_col.objects if o.type=='MESH'),
    'rigged':False,'animations':0,'export':str(glb)}
(DEST/'build_info.json').write_text(json.dumps(stats,indent=2))
print('SCULPT_COMPLETE',json.dumps(stats))
