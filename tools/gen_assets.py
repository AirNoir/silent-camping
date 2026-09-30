"""用 Blender 生成樹、草叢與林下植被／小物，匯出 GLB 給 Godot。
用法：Blender --background --python tools/gen_assets.py -- <輸出資料夾> [leaf_style] [leaf_shape]
預設 leaf_style=leaves（L4）、leaf_shape=leaf6；其他選項見 treelib.py
"""
import bpy, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import treelib as T
import proplib as P

args = sys.argv[sys.argv.index("--") + 1:]
OUT = args[0]
STYLE = args[1] if len(args) > 1 else "leaves"
SHAPE = args[2] if len(args) > 2 else "leaf6"
SHADE = STYLE != "blob"
CORE = "nocore" not in args
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)

def pine(name, seed, **kw):
    if STYLE == "blob":
        return T.tree_pine(name, seed, shade=SHADE, **kw)
    return T.tree_pine_detailed(name, seed, shade=SHADE, core=CORE, **kw)

def bl(name, seed, **kw):
    return T.tree_broadleaf(name, seed, leaf_style=STYLE, shade=SHADE, leaf_shape=SHAPE, core=CORE, **kw)

objs = [
    # 樹
    bl("tree_round_A", 1), bl("tree_round_B", 2), bl("tree_round_C", 3),
    bl("tree_round_D", 4, height=1.6, n_branch=(7, 9)),
    bl("tree_oak_A", 11, height=1.5, trunk_frac=0.5, elev=(18, 45), blob=1.15, spread=1.15),
    bl("tree_oak_B", 12, height=1.55, trunk_frac=0.5, elev=(18, 45), blob=1.1, spread=1.1),
    bl("tree_tall_A", 21, height=2.2, trunk_frac=0.66, n_branch=(4, 5), elev=(45, 70), blob=0.85, spread=0.8),
    bl("tree_tall_B", 22, height=2.1, trunk_frac=0.64, n_branch=(4, 6), elev=(45, 70), blob=0.85, spread=0.8),
    pine("tree_pine_A", 31, height=2.0, tiers=6), pine("tree_pine_B", 32, height=2.3, tiers=7),
    pine("tree_pine_C", 33, height=1.7, tiers=5),
    pine("pine_small", 34, height=0.9, tiers=4),
    # 草
    T.grass_tuft("grass_tuft_A", 41), T.grass_tuft("grass_tuft_B", 42, blades=12),
    T.grass_tuft("grass_tuft_C", 43, blades=8, h_range=(0.16, 0.28)),
    # 林下植被
    T.bush("bush_A", 51), T.bush("bush_B", 52, size=0.42, leaf_count=100), T.bush("bush_C", 53, size=0.6, leaf_count=150),
    T.fern("fern_A", 61), T.fern("fern_B", 62, size=0.42, fronds=(5, 7)),
    T.flower("flower_yellow", 71, "yellow", petals=6, center="inner"),
    T.flower("flower_purple", 72, "purple", petals=5),
    T.flower("flower_red", 73, "red", petals=6),
    T.mushroom("mushroom_red", 81, "red", dots=True),
    T.mushroom("mushroom_tan_group", 82, "inner", dots=False, count=3, size=0.8),
    # 小物
    T.rock("rock_small_A", 91, size=0.16), T.rock("rock_small_B", 92, size=0.14, flat=True),
    T.rock("rock_large_A", 93, size=0.34), T.rock("rock_large_B", 94, size=0.3, flat=True),
    T.log_("log_A", 101), T.log_("log_B", 102, length=0.55, radius=0.075),
    T.stump("stump_A", 111), T.stump("stump_B", 112, radius=0.16, height=0.14),
    # 營地（單位 = 公尺，Godot 端 scale 1）
    P.dome_tent("dome_tent"), P.camper_van("camper_van"),
    P.camp_chair("camp_chair_blue"), P.camp_chair("camp_chair_red", "fabricRed"),
    P.camp_table("camp_table"), P.lantern("lantern"), P.campfire("campfire"), P.tripod_kettle("tripod_kettle"),
    P.crate("crate_A"), P.crate("crate_B", (0.42, 0.42, 0.5)), P.cooler("cooler"),
]
for ob in objs:
    T.export_glb(ob, os.path.join(OUT, ob.name + ".glb"))
    print("GEN %s tris=%d" % (ob.name, T.tri_count(ob)))
