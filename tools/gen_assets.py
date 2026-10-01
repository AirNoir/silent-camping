"""用 Blender 生成樹、草叢與林下植被／小物／營地道具／露營者，匯出 GLB 給 Godot。
用法：Blender --background --python tools/gen_assets.py -- <輸出資料夾> [leaf_style] [leaf_shape] [nocore] [only=前綴,前綴…]
預設 leaf_style=leaves（L4）、leaf_shape=leaf6；其他選項見 treelib.py
only=camper,coffee 只生成名稱以這些開頭的資產（改角色時不用重跑整批樹）
"""
import bpy, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import treelib as T
import proplib as P
import camperlib as C

args = sys.argv[sys.argv.index("--") + 1:]
OUT = args[0]
pos = [a for a in args[1:] if "=" not in a and a != "nocore"]
STYLE = pos[0] if len(pos) > 0 else "leaves"
SHAPE = pos[1] if len(pos) > 1 else "leaf6"
SHADE = STYLE != "blob"
CORE = "nocore" not in args
ONLY = [a.split("=", 1)[1].split(",") for a in args if a.startswith("only=")]
ONLY = ONLY[0] if ONLY else None
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)


def pine(name, seed, **kw):
    if STYLE == "blob":
        return T.tree_pine(name, seed, shade=SHADE, **kw)
    return T.tree_pine_detailed(name, seed, shade=SHADE, core=CORE, **kw)


def bl(name, seed, **kw):
    return T.tree_broadleaf(name, seed, leaf_style=STYLE, shade=SHADE, leaf_shape=SHAPE, core=CORE, **kw)


def G(fn, name, *a, **kw):
    """有 only= 時只生成名稱符合前綴的。"""
    if ONLY and not any(name.startswith(p) for p in ONLY):
        return None
    return fn(name, *a, **kw)


objs = [
    # 樹
    G(bl, "tree_round_A", 1), G(bl, "tree_round_B", 2), G(bl, "tree_round_C", 3),
    G(bl, "tree_round_D", 4, height=1.6, n_branch=(7, 9)),
    G(bl, "tree_oak_A", 11, height=1.5, trunk_frac=0.5, elev=(18, 45), blob=1.15, spread=1.15),
    G(bl, "tree_oak_B", 12, height=1.55, trunk_frac=0.5, elev=(18, 45), blob=1.1, spread=1.1),
    G(bl, "tree_tall_A", 21, height=2.2, trunk_frac=0.66, n_branch=(4, 5), elev=(45, 70), blob=0.85, spread=0.8),
    G(bl, "tree_tall_B", 22, height=2.1, trunk_frac=0.64, n_branch=(4, 6), elev=(45, 70), blob=0.85, spread=0.8),
    G(pine, "tree_pine_A", 31, height=2.0, tiers=6), G(pine, "tree_pine_B", 32, height=2.3, tiers=7),
    G(pine, "tree_pine_C", 33, height=1.7, tiers=5),
    G(pine, "pine_small", 34, height=0.9, tiers=4),
    # 草
    G(T.grass_tuft, "grass_tuft_A", 41), G(T.grass_tuft, "grass_tuft_B", 42, blades=12),
    G(T.grass_tuft, "grass_tuft_C", 43, blades=8, h_range=(0.16, 0.28)),
    # 林下植被
    G(T.bush, "bush_A", 51), G(T.bush, "bush_B", 52, size=0.42, leaf_count=100), G(T.bush, "bush_C", 53, size=0.6, leaf_count=150),
    G(T.fern, "fern_A", 61), G(T.fern, "fern_B", 62, size=0.42, fronds=(5, 7)),
    G(T.flower, "flower_yellow", 71, "yellow", petals=6, center="inner"),
    G(T.flower, "flower_purple", 72, "purple", petals=5),
    G(T.flower, "flower_red", 73, "red", petals=6),
    G(T.mushroom, "mushroom_red", 81, "red", dots=True),
    G(T.mushroom, "mushroom_tan_group", 82, "inner", dots=False, count=3, size=0.8),
    # 小物
    G(T.rock, "rock_small_A", 91, size=0.16), G(T.rock, "rock_small_B", 92, size=0.14, flat=True),
    G(T.rock, "rock_large_A", 93, size=0.34), G(T.rock, "rock_large_B", 94, size=0.3, flat=True),
    G(T.log_, "log_A", 101), G(T.log_, "log_B", 102, length=0.55, radius=0.075),
    G(T.stump, "stump_A", 111), G(T.stump, "stump_B", 112, radius=0.16, height=0.14),
    # 營地（單位 = 公尺，Godot 端 scale 1）
    G(P.dome_tent, "dome_tent"), G(P.camper_van, "camper_van"),
    G(P.camp_chair, "camp_chair_blue"), G(P.camp_chair, "camp_chair_red", "fabricRed"),
    G(P.camp_table, "camp_table"), G(P.lantern, "lantern"), G(P.campfire, "campfire"), G(P.tripod_kettle, "tripod_kettle"),
    G(P.crate, "crate_A"), G(P.crate, "crate_B", (0.42, 0.42, 0.5)), G(P.cooler, "cooler"),
    # 露營者（第二代：Skin 長肉 + 骨架 + 貼圖臉，整組匯成一個 GLB）、手持道具與桌上小物
    G(C.camper, "camper_walk", "walk"), G(C.camper, "camper_roast", "roast"), G(C.camper, "camper_brew", "brew"),
    G(C.marshmallow_stick, "marshmallow_stick"), G(C.kettle_hand, "kettle_hand"), G(C.mug_hand, "mug_hand"),
    G(P.coffee_set, "coffee_set"), G(P.marshmallow_bag, "marshmallow_bag"),
]
for ob in objs:
    if ob is None:
        continue
    parts = [ob] + list(ob.children_recursive)
    T.export_glb_objs(parts, os.path.join(OUT, ob.name + ".glb"))
    print("GEN %s tris=%d parts=%d" % (ob.name, sum(T.tri_count(p) for p in parts), len(parts)))
