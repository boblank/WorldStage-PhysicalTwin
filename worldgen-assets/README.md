# WorldGen robot test arena · 2026-09-29

## Verified browser generation

- Account: logged-in **Creator** subscription; no API key was needed for the web workflow. Wallet was 45 credits before these runs and 41 afterwards. No extra purchase was made.
- Submitted image: `worldgen-submitted-screenshot.png`, SHA-256 `75e8cc2591da86777b24db6a1b906c5e5da934807912f2f8b60a9688e60e4e08`. This is the exact PNG placed on the Chrome clipboard and pasted into WorldGen. It was derived from `robot-test-arena-reference.png`, SHA-256 `5f0465dea292f1b77b0b649652c6361347d715063a89b8d338354580aa5374cb`, generated for this project with OpenAI image generation. Hyper3D subsequently stored its own WebP conversion.
- [Automatic 7-object WorldGen workspace](https://hyper3d.ai/workspace/rodin/worldgen/f33f3e2a-4a84-4477-aed4-41942da80dff): `Generate Objects` extracted staircase, three blocks, ramp, ball, and rail. `worldgen-auto-7objects.zip` SHA-256 `b0c68413fbc6dd9915694cbd432ac527d05c25ebddeb08837b94f53a56f8387c`; ZIP integrity passed. It contains 7 separated PBR GLBs, 7 shaded GLBs, 7 transform matrices and a camera matrix. No 3DGS background is in this export.
- [Manual 2-object plus 3DGS workspace](https://hyper3d.ai/workspace/rodin/worldgen/4b60933d-f55d-41fb-87d3-a155b3efba61): staircase and ramp were selected manually; FastGen created a 500K Gaussian background. `worldgen-manual-2objects-3dgs.zip` SHA-256 `8ffca46cfb26f51a92570973cc4e8b2095822bf672d5f243b0ae8ddc01ebcd95`. It contains 2 separated PBR/shaded GLBs, `500k.spz` (SHA-256 `459d71a73d780275f11656a510b4b9e0ec0628cffa4005716a0c4f52c89b88d0`) and `environment_collider.glb` (SHA-256 `1ef81b5277843e95b74cc11acc18b1ad25c410a8a512b1cd966ca27273ce7aaa`). The latter contains 34,781 position vertices and 68,576 indexed triangles. Its contact behavior has not been tested.
- The `Complete Scene` preset was disabled in this account's UI. The manual workflow still permitted 3DGS FastGen after generating the objects.

## Hackathon intake

If using the GitHub source checkout, unpack the original seven-object export before re-running the file-level gate:

```bash
unzip worldgen-assets/worldgen-auto-7objects.zip -d worldgen-assets/worldgen-auto-7objects
python3 demo-3d/studio/scene_gate.py worldgen-assets/auto-converted/scene.json --source worldgen-assets/auto-converted/source.json
```

- `auto-converted/scene.json` maps the seven GLBs into `worldstage.physical.v1` bounding-box **estimates**. `auto-converted/source.json` records the source image, workspace URL, actual exported asset SHA-256 hashes and transform hashes. The source paths are relative so the directory remains portable with its sibling export.
- `auto-converted/scene_gate.json`: structural `PASS`, `mjcf_exportable=true`, 7/7 asset files hash-verified. `robot_training_status=NOT_RUN` and `nvidia_simready_status=NOT_RUN`.
- `demo-3d/worldgen.html` is a browser viewer for the seven exported PBR GLBs. Its optional amber boxes visualize the approximate collision proxies. The robot lab links to this page. This viewer does not simulate WorldGen mesh contact.

## Measurement boundary

Hyper3D exported Y-up transforms, but did not provide a verified metre scale, object masses, friction measurements, robot traversal tests, or NVIDIA SimReady certification. The converter assumes one GLB unit equals one metre solely to create a reviewable proxy scene. It grounds each item for display. Stair and ramp contact geometry need replacement or validation before robot training. The 3DGS background is visual data; the presence of `environment_collider.glb` is file evidence only, not a collision acceptance result.

Hyper3D's [pricing page](https://hyper3d.ai/pricing) lists Creator workspace export and any-use rights; its [terms](https://hyper3d.ai/legal/terms) say Rodin output use is not limited subject to the terms, applicable law and third-party rights. The reference image was created for this project. Competition-specific submission rules still govern what may be published.
