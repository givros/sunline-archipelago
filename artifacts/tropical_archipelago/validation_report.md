# The Sunline Archipelago — validation

The supplied image is the layout reference. The ten coastlines, principal rail curves, settlement areas, six overwater districts and harbor locations were traced into one shared spatial definition. Dimensions and unseen architecture are reconstructed interpretations of that single aerial image.

## Reference checkpoints

Saved source checkpoints and matched aerial comparisons cover all eleven requested stages in `checkpoints/` and `comparisons/`.

| Stage | Evidence | Inspection and correction |
|---|---|---|
| 1. Boundaries | `01_boundaries.png` | Ten distinct landforms; dominant southwest, northeast, north and southeast islands retain the reference organization. |
| 2. Ocean | `02_ocean.png` | Reef shelves follow the same coast definitions; channels remain open between islands. |
| 3. Islands | `03_islands.png` | Varied relief, coves and beaches; final terrain increased to 384 angular by 100 radial samples, with blended vertex colors and continuous underwater shores. |
| 4. Railway | `04_railway.png` | Main north S-curve, east sweep and southeast branch preserved. The tightest curve was re-engineered for articulated rolling stock. |
| 5. Bridges | `05_bridges.png` | Stone arch spans in the north, supported southern viaducts; structural unions and turnout cuts remove intersecting decks, duplicate sleepers and internal railings. |
| 6. Villages | `06_villages.png` | Complete wall, roof, door, window, shutter and foundation assemblies. Building pads, a church terrace and ownership of intersecting paved surfaces corrected. |
| 7. Overwater houses | `07_stilts.png` | 46 complete supported houses across six districts; branching circulation retained. Subsequent traversal repairs are recorded separately. |
| 8. Trains | `08_trains.png` | Two animated consists with 5 and 9 cars, separate bogies and live articulated coupling links. |
| 9. Docks and boats | `09_harbors.png` | 11 pier routes and 28 detailed vessels. Close inspections identified berth overlaps and crossing foam ribbons for correction. |
| 10. Vegetation | `10_vegetation.png` | Region-specific broadleaf trees, palms, ferns, shrubs and exposed limestone. Planting reserves buildings, routes and the railway. |
| 11. Complete composition | `11_complete_layout.png` | Full layout compared again before final refinements. The final reference grid is the current comparison. |

## Complete visual passes

### Pass 1

`comparisons/pass_01_nine_views.png` contains nine actual scene renders; full-resolution images are retained in `renders/`. The matched nine-cell reference grid is separate from this contact sheet.

Observed issues: clipped northern treetops in the overview; incomplete framing in the vertical plan; overly hard reef contour bands; flat gray visible sky; a weak Porto church silhouette behind the civic frontage; undersized lagoon rotunda; sparse harbor frontage and plaza dressing. Detailed train views confirmed modeled bogies, couplings, doors and roof equipment. Their blue-and-white materials were retained after close inspection.

Corrections include wider camera framing, softer granular reef colors, a clear maritime sky, taller bell stages, a larger supported rotunda, complete harbor shops and shaded market stalls. Route and berth corrections use actual geometry, rather than hiding collision defects.

### Pass 2

`comparisons/pass_02_nine_views.png` and the corresponding reference grid were inspected after the water, tower, rotunda and harbor corrections. The vertical plan now includes all islands. The eye-height church camera shows its complete tower, and overwater views establish visible bracing and piles. The six measured boat/deck overlaps were removed. The yacht berth was subsequently tightened to a measured 0.93 m hull-to-deck gap, with attached boarding ladders and fenders.

The second pass exposed misaligned square spire roofs and dark coplanar plank seams at curved boardwalk joins. Both spire eaves were aligned to their belfries. Deck ownership was then clipped into real plank solids: house and pavilion decks own shared areas before connectors. A separate coverage fixture preserved 181.0022 square meters of usable walking surface while removing duplicate ownership; the remaining symmetric difference was 0.000005 square meters.

### Pass 3

All nine views were rendered and inspected again in `comparisons/pass_03_nine_views.png`. The aligned roofs and corrected boardwalk surfaces introduce no visible layout drift. Full-resolution church, waterfront, village, railway and overwater images remain available. Targeted final overview/plan refreshes incorporate the final berth and navigation corrections.

The final targeted comparison also identified oversized pale reef patches. Coral colony noise was separated from the broad depth field, using approximately 10 m, 4 m and 1.6 m feature scales. Saturated turquoise shallows, restrained sand colors and softer colony contrast replace the earlier cloudy pattern. Coast positions, shelf extents and open-water channels remain unchanged. Final overview, vertical plan, lagoon and Coral Key views are in `renders/final_*.png`.

Reference crops, isolated geometry and integrated views are compared in `comparisons/architecture_audit/` and `renders/marine_validation/marine_rail_hero_reference_sheet.png`. Unavailable reference angles are explicitly marked. The reference's yacht has a sleeker silhouette than the modeled trawler family; individual villa plans and roof articulation also remain simpler. High geometric detail does not make this a photographic match, and the 9/10 photographic-similarity target is not claimed as passed.

## Operational railway

The source contains 14 cars, 28 independently swiveling bogies and 12 articulated drawbars. Gauge is 1.435 m, car pitch is 19 m and cruise speed is 7.5 m/s. Acceleration, deceleration, end dwell and reversal are implemented in both Blender and the viewer.

The complete source timeline is 351.875 seconds at 24 fps. Its closing frame duplicates the first pose; playback excludes that duplicate. The source validator sampled 4,294 contact states: maximum wheel-to-rail error 0.047001 m, maximum bogie-center error 0.000043 m and maximum drawbar endpoint error 0.000043 m. The declared 0.075 m wheel contact tolerance passes. The source/runtime comparison samples keyframes, subframes, dwell, reversal and loop phases.

## Editable assets and navigation

Terrain, architecture, pilings, decks, vessels, rails, bridge structures, rolling stock and foliage are actual editable geometry. Shared prototypes retain full detail. No building or boat is represented solely by a roof or a flat image.

Walking uses actual support triangles, with a 1.72 m eye height, a 0.32 m player radius, a 0.5 m step height and a 45 degree slope limit. Swimming connects shore access. Ten named arrival points, aerial inspection and train following support orientation. Building interiors are closed; boats are environmental vessels rather than player-controlled vehicles.

Traversal exposed physical conflicts at the North shore stair, Palm Crescent approach and selected Coral Key branches. Corrections regrade the actual crossing lane, rebuild the Palm switchback and its entry guards, route around occupied house decks, clear a confirmed palm trunk, and open specific joining railings. Exact source capsule checks supplement runtime traversal; broad bounding boxes alone are not used to justify cutting architecture. The repair records are linked from `scene_spec.json` and `region_graph.json`.

## Scope of fidelity

The reference establishes one aerial view. Unseen facades, backs, interiors, underwater geometry and lighting at other times are not directly evidenced by it. This is a detailed, stylized 3D reconstruction, not a photographic or pixel-identical reproduction. Final artistic judgments, source inventory, transfer checks and measured desktop performance remain separate evidence categories.

All visible project assets were made for this scene. The user's image is retained as a reference only. No paid or externally downloaded asset packs are used.

## Final source audit

The final 267,770,528-byte Blender file was reopened in Blender 5.1.2, rendered again, saved, and audited in a separate fresh process. Its SHA-256 is `9410664a7ed7b1ef2edbd69ef13d3abbd67b35c47a5ce1513245d6715034063f`. All 14 source checks pass; the read-only audit left that identity unchanged.

| Source inventory | Verified result |
|---|---:|
| Islands | 10 |
| Houses and shops | 103, including 46 stilt houses |
| Church landmarks | 2 |
| Boats | 28 across six families |
| Pier routes | 11 |
| Palms / broadleaf trees | 520 / 1,417 |
| Rail routes | 3 |
| Train cars / bogies / drawbars | 14 / 28 / 12 |
| Visible mesh objects / unique meshes | 33,758 / 5,435 |
| Unique mesh triangles / instanced triangles | 2,849,519 / 49,984,497 |

There are no invalid coordinates, transforms or normals, no zero-area triangles and no missing dependencies. The embedded 4096 × 4096 ocean image matches its external file byte for byte. All 4,324 sampled rail-head locations and 1,081 structural-deck locations hit the continuous final geometry. All 60 animation drivers are valid, and the first/closing source poses have zero matrix difference.

`checkpoints/final_source_audit.json` holds the detailed measurements. `asset_registry.json`, `region_graph.json` and `vegetation_registry.json` identify the final surviving objects and route overrides; original scatter targets are retained only as explicitly historical records.

## Local viewer and measured performance

The production viewer runs at `http://127.0.0.1:4173/` and binds only to the local loopback interface. Three.js 0.186.1 uses a verified hardware WebGPU adapter. Its full-detail export transfers all 33,758 source mesh objects and 49,984,497 evaluated instanced triangles. Exact mesh sharing reduces duplicate storage to 1,926,095 unique exported triangles without removing scene detail. The 175,542,888-byte geometry buffer is uncompressed; the 4096 × 4096 ocean texture retains the source bytes and hash.

Validation used isolated headless Chromium 152 on the local NVIDIA RTX 3080 system, at a native 1448 × 1086 framebuffer and device-pixel ratio 1. Quality includes 4× MSAA, 4096² sun shadows, full-resolution HDR reflections and full-resolution contact shading. The display transform uses the installed Blender AgX Medium High Contrast configuration; an independent 10,000-color comparison measures a mean linear error of 0.000392 and a 95th-percentile error of 0.00160.

| Final desktop measurement | Result |
|---|---:|
| Cold load to first complete frame | approximately 15.7 seconds |
| Aerial view, median frame interval | 66.7 ms, approximately 15 FPS |
| Walking view, median frame interval | 50 ms, approximately 20 FPS |

These are measured full-quality results, not a 60 FPS claim. Whole-frame GPU timing was not independently established; the runtime report separates wall-clock frame intervals and CPU callbacks instead of labeling a partial-pass timestamp as total GPU cost. Other screen sizes and hardware may perform differently.

The browser suite verifies all ten arrival points, actual keyboard movement and mouse look, application Escape pause, cleared movement keys on focus loss, train animation, reflections, full-detail asset hashes, fullscreen API behavior, disposal and reload, with no shader or runtime errors. Native operating-system Escape interception and forced hardware device-loss recovery were not established by this headless test. `viewer/runtime_validation.json` and `viewer/render_profile.json` contain the complete results and rendering configuration.

All 24 continuous public-route fixtures pass both in the browser and in the independent controller run on the final source identity. The controller follows route corners continuously without teleporting between waypoints. Shore-to-swimming-to-shore traversal and solid building collisions also pass. An earlier Palm test incorrectly skipped switchback corners; the final fixture preserves the actual source controls. All 54 animated roots match the reopened source across 33 sampled times, with maximum position error 0.000103 m. Six rendered-browser samples compare 324 transforms, with maximum position error 0.000047 m. Controlled missing-WebGPU, unavailable-adapter and unavailable-scene cases present working reload actions.

Controls: select **Explore on foot**, use **WASD / ZQSD** and the mouse, hold **Shift** to move faster, and press **Escape** to pause. **Places** chooses a destination; **Overview** and **Follow the train** change the inspection mode.
