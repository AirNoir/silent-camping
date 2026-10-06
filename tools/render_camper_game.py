"""Render the actual simplified GLB in the saved Blender review studio."""
import bpy, math
from mathutils import Matrix
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
source=bpy.data.collections.get('CHARACTER | male orange camper')
if source:
    for ob in list(source.objects):bpy.data.objects.remove(ob,do_unlink=True)
    bpy.data.collections.remove(source)
before=set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'assets/gen/camper_male_sculpt.glb'))
imported=[o for o in bpy.data.objects if o not in before]
for ob in imported:
    if ob.parent is None:ob.matrix_world=Matrix.Rotation(-math.pi/2,4,'Z')@ob.matrix_world
scene=bpy.context.scene
scene.cycles.samples=32
scene.render.filepath=str(ROOT/'assets/source/camper_sculpt/male_game_asset.png')
bpy.ops.render.render(write_still=True)
