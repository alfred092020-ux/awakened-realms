# Authentic static terrain proof

Open `/?rendererProof=1` after private hydration. This opt-in view never enters
the character-create/tutorial flow. `001_000_00002` is a renderer proof map only;
the tutorial/start map, spawn and encounter remain unresolved.

Hydrate privately using `scripts/logres/hydrate_live_renderer_proof.py`, with
`--output-root public/__logres_ref/renderer-proof`. The normal and `__ans` MBNs
must be present beside the private archive in `jp-live-patch-cache/map/`.
The output directory is git-ignored. Never commit assets or proof screenshots.

## Confirmed input and corrected UV handling

Live JP map payload SHA256:
`71f204a84cac4cb11f5e1d40cd31ffc226c1c33bcea8487c596d2930bc5da007`.
Hydration requires normal and `__ans` payloads to match exactly.
CHIP atlas is 718×1938; OBJ is 2048×1934, expanded from A4R4G4B4 DDS.

The decoded UV pairs are **already normalized**. Dividing them by atlas size
again was an inherited mesh-adapter defect. The adapter now preserves source
UVs and only applies an explicit optional `1-v` comparison policy.
Recovered CHIP minima include U `0.002785515272989869` (2/718 as float32)
and V `0.0025799793656915426` (5/1938 as float32).
Across this payload:

| Geometry | Vertices | X range | Y range | U range | V range |
|---|---:|---|---|---|---|
| CHIP | 51,261 | −2636…3734 | −4225…−537 | 0.0027855…0.9958217 | 0.0025800…0.9974200 |
| OBJ | 5,577 | −2518…3731 | −3898…16 | 0.0009766…0.9990234 | 0.0010341…0.9989659 |

Native current-JP `copyVertex` at `0x394cc70–0x394cc8c` copies source XY and
the first UV pair directly. Global native evidence in `MAP_SCHEMA_EVIDENCE.md`
also records normalized UVs whose atlas-scaled values reach pixel coordinates.
Do not add another isometric projection to these terrain XY positions.

## Diagnostic policies, not recovered gameplay

The proof uses a dedicated WebGL1 context with bounds-fit framing, Y up,
pan/zoom controls, CHIP then OBJ drawing and no depth test. It renders static
UV pose zero; animated objects are counted but omitted. Expanded triangles
retain the recovered strip winding and avoid 16-bit element-index limits.

Source rows and RGBA channel values are uploaded without gamma conversion or
premultiplication. Native evidence supports ONE/ONE_MINUS_SRC_ALPHA blending
and nearest magnification. Input alpha convention, native minification policy,
texture orientation, color space, final depth, camera and animation timing are
not established. The two UV origins are comparison modes, not semantic claims.
Nearest minification is a diagnostic choice.

Missing assets or unavailable/lost WebGL produce a visible error. No substitute
map or fabricated texture is generated. Pixel tests establish that authentic
geometry and assets reach the GPU, not that gameplay rendering is complete.

## Bounded native results

Oracle result branches are evidence-only and must not be merged:

- `agent/oracle-job-public-projection-constants-001`, result commit
  `3a1b20e290771a6e9abea066c8afce2ae122e170`: job succeeded but every referenced
  constant word is null. Numeric projection is unresolved; do not call the
  successful job a successful recovery of constants.
- `agent/oracle-job-public-terrain-z-001`, result commit
  `a59c4e12a1909a47dd5d87fa0b69d1f49938e0cb`: Convexhull float at +4 becomes
  vertex Z. Reported call count zero is an extractor false negative; the call
  is present at `0x394c310`.
- `agent/oracle-job-public-convexhull-source-001`, result commit
  `93a07877ac6e9762ede5bbfd6c3e2b46fa88aabb`: succeeded against source
  `9a9bf7f446b792a8384d4444489b083d4b764a6c`. `FieldQuadTreeLeaf::setupEntities`
  calls DataParser at `0x3949270`, passing two local vectors. Constructor loads
  +4 at `0x394c188` / `0x394c1c0`, then passes it unchanged to the vertex builder.
  The map/entity-depth to float-at-4 formula is outside the captured window.

Next bounded native question: recover the two vector producers in
`FieldQuadTreeLeaf::setupEntities`. Include conditional branch instructions;
current filtered reports omit `b.*` and cannot prove full branch policies.
Projection constants additionally need classification against ELF segment
file/memory extents before any initializer analysis.

## Verification

The 2026-09-22 private browser check rendered 5,465 grids, 9,237 CHIP hulls,
321 OBJ hulls and 43,838 triangles; one animated object was omitted.
Top-left sampling produced coherent castle-town texture placement. Bottom-left
sampling produced visibly scrambled texture placement. This is empirical
support for top-left sampling of these preserved DDS rows, not native upload
policy proof for all asset formats. Screenshots stayed in ignored test output.

Run `npm run verify`. With private assets hydrated, build and run
`npx playwright test e2e/logres-renderer-proof.spec.mjs`.
The private pixel test skips explicitly when assets are absent; the missing
asset test is unconditional. Inspect both generated screenshots privately.
