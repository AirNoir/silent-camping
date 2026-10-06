"""Bake evaluated review meshes, simplify, and batch game meshes by material."""
import bpy
from math import pi

def export_game_asset(source_collection, filepath):
    bpy.context.view_layer.update()
    deps=bpy.context.evaluated_depsgraph_get()
    collection=bpy.data.collections.new('GAME EXPORT | temporary')
    bpy.context.scene.collection.children.link(collection)
    root=bpy.data.objects.new('Camper_Male',None);collection.objects.link(root)
    groups={}
    for src in list(source_collection.objects):
        if src.type not in {'MESH','CURVE'}:continue
        me=bpy.data.meshes.new_from_object(src.evaluated_get(deps),preserve_all_data_layers=True,depsgraph=deps)
        me.transform(src.matrix_world)
        ob=bpy.data.objects.new(src.name+'_game',me);collection.objects.link(ob)
        # Tiny accessories can be aggressively simplified; face decals stay intact.
        face=src.name.startswith(('Eye_','Brow_','Smile','Nose'))
        if not face and len(me.vertices)>200:
            modifier=ob.modifiers.new('Game mesh reduction','DECIMATE')
            modifier.ratio=.14 if 'eyelet' in src.name.lower() else (.23 if 'Hair' in src.name else .27)
            bpy.context.view_layer.update()
            simplified=bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
            ob.modifiers.clear();ob.data=simplified;bpy.data.meshes.remove(me)
        key=ob.data.materials[0].name if ob.data.materials else 'none'
        groups.setdefault(key,[]).append(ob)
    for material,objects in groups.items():
        bpy.ops.object.select_all(action='DESELECT')
        for ob in objects:ob.select_set(True)
        bpy.context.view_layer.objects.active=objects[0]
        bpy.ops.object.join()
        ob=bpy.context.view_layer.objects.active;ob.name=material;ob.parent=root
    root.rotation_euler.z=pi/2
    root['forward']='+X';root['static']=True
    bpy.ops.object.select_all(action='DESELECT')
    triangles=0
    for ob in collection.objects:
        ob.select_set(True)
        if ob.type=='MESH':
            ob.data.calc_loop_triangles();triangles+=len(ob.data.loop_triangles)
    bpy.context.view_layer.objects.active=root
    bpy.ops.export_scene.gltf(filepath=str(filepath),export_format='GLB',use_selection=True,export_apply=True)
    result={'triangles':triangles,'material_batches':len(groups),'rigged':False,'animations':0}
    for ob in list(collection.objects):bpy.data.objects.remove(ob,do_unlink=True)
    bpy.data.collections.remove(collection)
    return result
