# Male camper visual prototype

Editable source: `camper_reference_male.blend`.
Godot static asset: `../gen/camper_reference_male.glb`.
Reference: supplied forest camping character board, male orange outfit.

Built from the supplied Chibi_Base_Mesh2 and locally licensed Men Hair Set 04.
The previous dressing experiment and supplied originals are preserved.
Head height is shortened, face broadened, and a separate rounded fringe added.
Clothing, boots, backpack, face, and fringe are separate editable objects.

This is a visual prototype, not a completed production character. No armature,
skin weights, animation clips, or blinking controls have been added. The supplied
hair's swept crown, hands, jacket edging, and boot soles still need art refinement.
Female character has not been built in this iteration.

Rebuild from the repository root:

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background '/Users/a01-0220-0077/Downloads/Chibi_Base_Mesh2.blend' --python tools/camper_reference.py
```

Verified: Blender source saved, GLB exported and reimported for front / 3-quarter /
side / back renders; Godot 4.7.2 asset import completed. The headless editor also
reported an unrelated sandbox denial saving its global editor settings.
