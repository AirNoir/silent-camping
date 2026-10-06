# Male camper sculpt revision

This revision rebuilds the male orange camper from the supplied forest camping
character board. The supplied base, licensed hair, and previous prototypes are
preserved. The new head, hair, garments, hands, boots, and backpack are independent
meshes, with editable curve seams and separate materials in the Blender source.

- `camper_male_sculpt.blend`: editable source plus studio and camera.
- `camper_male_sculpt_high.glb`: full-resolution static model.
- `../../gen/camper_male_sculpt.glb`: simplified Godot model, 72,535 triangles,
  24 material batches, about 1.5 MB. Height 1.357 m; forward +X; feet at ground.
- `male_front/q34/side/back.png`: actual source renders.
- `male_face.png`: close-up.
- `male_game_asset.png`: reimported simplified GLB rendered in the same studio.
- `male_turnaround.png`: contact sheet.
- `reference_compare.png`: supplied reference beside actual model.

In Godot, open `camper_review.tscn` and press F6. Drag to orbit, scroll to zoom,
1/2/3/4 for front/three-quarter/side/back, Space for automatic rotation.
The main game scene and original character controller are unchanged.

The model remains a static sculpt: no armature, skin weights, animations, blink
controls, production UV atlas, or female model. It is a reference-driven revision,
not a claim of exact visual identity; hair clump structure, fabric folds, and
hand shape still differ from the illustrated design.

Rebuild and verify from the repository root:

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background --python tools/sculpt_camper.py
/Applications/Blender.app/Contents/MacOS/Blender --background assets/source/camper_sculpt/camper_male_sculpt.blend --python tools/render_camper_game.py
python3 tools/camper_contact.py
/Applications/Godot.app/Contents/MacOS/Godot --headless --path . --import
/Applications/Godot.app/Contents/MacOS/Godot --headless --path . --log-file /private/tmp/camper_asset.log camper_review.tscn -- --asset-check
```

Verification: Blender save/export, all five source renders, simplified GLB
reimport/render, and Godot asset/material/bounds checks. Godot's asset validation
reports `CAMPER_IMPORT_OK`. The sandboxed editor also reports unrelated macOS
certificate access and global editor-settings write warnings.
