# Map schema evidence, 2026-09-22

## Confirmed Global constants

The owner-provided `Logres-3.0.24.apk`, `lib/arm64-v8a/libgame.so`, has SHA-256
`bf777cfa413b95627152246e9048af5c5fbc9c53e3c49141421360d6e86c814f`.
The `.dynsym` symbols expose 41 `map::data::*::k*FieldNumber` constants.
`global-map-schema-constants.json` records each symbol, address, file offset,
and the uint32 little-endian value read at that offset. Addresses were mapped
through their ELF sections, not inferred from listing order.

Consequently terminal records are Grid messages, with Col=1, Row=2,
DepthOrder=3, Prohibition=4, Attribute=5, PathwayIndex=6, BorderID=7,
BlendAdjacence=8, ColorIndex=9, Chips=10, Obj=11, ObjAnimated=12.
The tree is explicitly QuadTree, not merely a structural guess.

## Corroboration across five Japanese maps

Oracle `oracle-map-nested-profile-001`, source `c52773a9445660f722128c69bfea39c62df1410f`,
completed successfully. The five maps contain 14,961 unique column/row records.
Each map also has unique depth-order values; these are not row-major indexes.
At `Grid/Chips/Vertices/UvPoses`, every float pair scaled by CHIP width/height
lands within 0.001 of an integer. Object UVs closely match OBJ dimensions,
with some noninteger coordinates in two maps. Do not round those coordinates.
Chip vertices contain one or six UV poses, depending on the record. Retain all
poses; this observation alone does not establish animation speed or frame order.

Wire types/cardinalities in the decoder follow observed recovered records.
Integer signedness, protobuf required/default rules, and unseen variants are
not fully recovered. The inspection decoder flags duplicate singular fields,
unknown fields, unsupported wire types, and nonfinite geometry rather than
silently normalizing them. It is not yet a complete general protobuf runtime.

## Confirmed native terrain draw calls

Global `lfs::field::FieldTerrainNode::onDraw()` starts at `0x19185cc`.
Direct ARM64 disassembly and `.rela.plt` resolution show:

| Call site | Call | Arguments |
| --- | --- | --- |
| 0x19185f0 | cocos2d::GL::blendFunc | 1, 0x303 (ONE, ONE_MINUS_SRC_ALPHA) |
| 0x191864c | glTexParameteri | 0xde1, 0x2800, 0x2600 (TEXTURE_2D, TEXTURE_MAG_FILTER, NEAREST) |
| 0x1918714 | glDrawArrays | mode 5 (TRIANGLE_STRIP), first 0, vertex count |

`FieldVertex(map::data::Vertex const&)` at `0x19192a0` copies one position pair
and iterates the UV-pose repeated field. It does not justify discarding poses.
Rendering still requires original batching, depth transforms, shader behavior,
texture orientation, and animation timing. These calls alone do not prove all
of those details or the Japanese ASTC color space.

## Convex hull to strip conversion

Global `DataParser::addConvexhullVertices` at `0x192f690` does not submit
the map's vertex order directly. It emits indices `0, n-1, 1, n-2, ...`.
The loop at `0x192fb20` alternates the end and start; the even-size final
middle vertex is handled at `0x192fcb8`. Both odd and even hulls are covered.
When appending to an existing strip it duplicates its last vertex and the
next hull's first vertex, creating two degenerate bridge vertices. It starts
a new batch when `(old_count + incoming_count + 2) >> 16` is nonzero.
Positions retain X/Y and use the supplied Z. Initial UVs use pose zero and
colors initialize to RGBA 255. Other poses are registered with FieldAnimator.
`LogresTerrainGeometry.ts` reconstructs this geometry preparation with synthetic
tests. It is intentionally not attached to the playable field until the remaining
texture, depth, shader, camera and tutorial evidence is resolved.

## Remaining evidence work

- Initial tutorial map, spawn, and encounter remain unproven.
- Camera/HUD separation and ASTC linear/sRGB choice remain unproven.
- The Oracle cache contains 1,169 Lua entries and 4,044 JSON entries inside MBNs.
  Source inventory reported two invalid MBNs in avatar-background packages.
- Resource IDs share a format across maps, sounds, icons, and effects. Earlier
  source-inventory `map_references` labels were too strong; the corrected scanner
  reports neutral resource-ID candidates. Never select a tutorial map from ID
  syntax or cache presence alone.
- Private binaries, source files, geometry, textures, and disassembly dumps are
  not committed. Only bounded derived evidence and reconstruction code belong here.
