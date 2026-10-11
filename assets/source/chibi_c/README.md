# Setting-C appearance revision — 2026-10-09

The leftmost character in the user-supplied comparison image is the appearance
target. The percentages and preservation instructions printed elsewhere in that
image are not the authoring brief; this revision follows the requested left image.

The current production files are `../chibi_b.blend` and
`../../gen/character_chibi_b.glb`. Both have been updated. The original is retained
in `before.blend` / `before.glb`; `matched.blend` / `matched.glb` are the revised
editable source and validated export.

## Appearance changes

- Taller oval eyes, brown irises with visible ivory sclera on both sides,
  upper-left catchlights, and subtle upper eyelid creases. Following the user's
  feedback, iris half-width is reduced from 0.082 to 0.068 while half-height is
  0.104, with the upper iris tucked under the lid. Sclera is exposed mainly at
  the two lateral sides. Upper-lid ends receive a maximum 0.0025-unit downward
  blend; the tiny outer tail slopes downward about 2 degrees. Facial feature
  positions and the main eye-opening size are retained.
- Sampled curved eyebrows, a warmer visible smile, and adjusted feature positions.
- Small lower-jaw adjustment with a blended neck transition.
- Rounded licensed hair clumps, longer bangs, shorter lower side locks, a reshaped
  crown and a separate editable swept tip.
- A padded cream hood wrapping around the front of the neck.

The body, hands, garments, boots and backpack retain the existing geometry other
than the hood addition. This is an editable static character, with the same
established export scale and +X forward direction. No rig or animation was added.

## Portable materials

The previous iris material had a white base color and relied on vertex colors.
The previous GLB contained both COLOR_0 and COLOR_1 on the iris. A viewer that does
not select the intended vertex-color layer can show white irises.

The revised GLB embeds a standard brown iris base-color image and a skin image
baked onto the supplied UVs. Neither material depends on vertex-color support.
Both images are also packed into the editable Blender file.

## Review and verification

- `comparison.png`: supplied left reference, previous front render, and revised
  actual GLB front render. Each panel preserves its aspect ratio; lighting differs
  between the supplied reference, previous studio and revised studio.
- `after_front/q34/full/side.png`: revised Blender source renders.
- `glb_front/q34.png`: actual exported GLB reimported into the same studio.
- `target_view.png`: revised source viewed from a slight angle like the reference.
- Blender export and reimport completed successfully.
- Godot 4.7.2 direct GLTF import passed: 32 mesh nodes, 95,312 triangles,
  height 1.156 m, feet within 0.001 m of the ground, and both iris/skin textures
  present with UV coordinates. Iris image samples are brown, not white.
- Source/GLB render differences are below one intensity level per channel on
  average (0–255 range).

The reference is a single illustrated front view, not a complete 3D specification.
Hair strand flow, shading and hood folds still differ; no numerical percentage
of visual identity is claimed. Fable itself has not been inspected or tested.

Rebuild without the external hair-pack Downloads path:

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background assets/source/chibi_c/before.blend --python tools/match_chibi_c.py
cp assets/source/chibi_c/matched.blend assets/source/chibi_b.blend
cp assets/source/chibi_c/matched.glb assets/gen/character_chibi_b.glb
```

This source/review folder is excluded from Godot's asset scan by `.gdignore`.
