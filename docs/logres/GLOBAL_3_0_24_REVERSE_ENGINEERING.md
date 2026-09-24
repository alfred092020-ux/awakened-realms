# Global Logres 3.0.24 reverse-engineering evidence

Status: active evidence ledger
Source: original signed Global Android APK
Package: `com.aiming.logresjrpg`
Version name: `3.0.24`
Version code: `2432`
APK SHA-256: `7424aa5b84fc52358a955dd1bb6b6d0b31f50f6b58d58e592ece4257cec17943`
Signing certificate: `O=Aiming Inc., C=JP`
Certificate SHA-256: `1e1db5d8d585ca1270cf82c726b8a3d9b5c6e1f387f96e21bcbebee1c0c27d29`

This file records derived reconstruction evidence only. Private APK payload bytes stay outside Git.

## Extraction coverage

- JADX: 1,157 decompiled files.
- Apktool: 2,080 decoded files.
- APK assets: 37 bundled asset files.
- Parsed bundled MBN members: 923 across private extraction trees.
- Bundled JSON configuration: 66 valid files, 1,947 scalar values.
- Global arm64 `libgame.so`: 55,676,856 bytes.
- Global armeabi-v7a `libgame.so`: 44,701,984 bytes.
- Arm64 defined dynamic symbols: 105,314.
- Recovered Logres-specific native classes: 2,372.
- Recovered distinct methods across those classes: 19,467.
- Unique `NetworkSession` methods: 428.
- GmClProto symbol types: 7,318.
- Named GmClProto enum values: 583.

## Android shell

- Main activity: `com.aiming.lfs.LFSActivity`.
- Application: `com.aiming.lfs.LFSApplication`.
- Orientation: portrait.
- Minimum SDK: 14.
- Target SDK: 26.
- URL scheme: `logresjrpg://`.
- Cocos2d-x drives the native game layer.
- The Java layer is comparatively small. Most game behavior lives in `libgame.so`.

## Bundled startup evidence

The APK directly bundles Global title and character-create content inside MBN containers.

- `gui/title.mbn` contains `title.lua`, title textures, world-select panels, maintenance UI, takeover UI, and title effects.
- `gui/characreate.mbn` contains male/female selection Lua and original selection art.
- `json_resource.mbn` contains Global configuration and localized UI data.

Exact title layout from `title.lua`:

- logical canvas: 720 x 1280.
- title background center: 360, 640.
- start control center: 360, 200.
- start resource: `gui/title/title_ok.png`.

Character selection evidence:

- male resource: `gui/characreate/charaselect_man.png`.
- female resource: `gui/characreate/charaselect_woman.png`.
- male change control position: 200, 250 relative to centered selector.
- female change control position: -200, 250 relative to centered selector.

## Map and field schema

Recovered protobuf structures expose the original map format.

`map::data::Root`:
- Width, Height.
- FieldQuadUnitCol, FieldQuadUnitRow.
- QuadTreeRoot.
- Version, UpdateDate.

`map::data::Grid`:
- Row, Col.
- Attribute.
- Prohibition.
- PathwayIndex.
- BlendAdjacence.
- BorderID.
- ColorIndex.
- DepthOrder.
- Chips.
- Obj and ObjAnimated.

Movement evidence:

- `SelfPlayer::move` constructs a `MovePathInitializer`.
- `MovePathInitializer` uses `pathfinding::SimpleAStar`.
- Movement resolves world positions into field coordinates and tiles.
- Region IDs are compared before path construction.
- Tile adjacency uses `FieldTile::canMoveTo`.
- The client tests segment intersections against field geometry.
- A nearby reachable location fallback exists when a requested destination is not directly valid.

## Encounter evidence

`character::encounter::Encounter::checkBattleEntry` performs multiple guards:

1. encounter setting allows entry.
2. battle-symbol entry state passes.
3. quest state passes.
4. symbol distance to the self player passes.

The client then sends `C_GMCL_BATTLE_ENTRY_REQ` carrying:

- AreaUID.
- MapPos.
- encounter/battle entry integer.
- SymbolUID.
- an additional unsigned integer field.

## Battle production schema

Recovered `battleProduction` protobuf types include:

- InitializePhase.
- ApproachPhase.
- AttackMotionPhase.
- ReturnPhase.
- Motion and MotionTransform.
- Effect.
- Sound.
- Trigger.
- Loop.
- ColorSection.
- PostEffect.

Post effects expose parameters for bloom, radial blur, brightness, contrast, bokeh, gamut color, blend rate, thresholds, and transition frame ranges.

## Motion and animation evidence

`MotionTbl` exposes:

- field and battle pivots.
- field and battle touch rectangles.
- drawing rectangles.
- object categories.
- weapon shape categories.
- object-to-resource path mappings.

LFLA structures expose:

- documents, layers, frames, movie clips, symbols, bitmap items.
- matrix transforms.
- color transforms.
- frame labels and durations.
- per-frame motion, rotation, scale, skew, and time scale.

## Protocol surface

Recovered `NetworkSession` surface:

- 428 unique methods.
- 179 `C_GMCL_*` response handlers.
- 237 `S_GMCL_*` server-message handlers.

High-density protocol families include:

- battle: 68.
- quest: 30.
- character: 18.
- item: 12.
- payment: 10.
- avatar: 10.
- gift: 9.
- PvP: 8.
- field: 5.
- clan: 5.
- chat: 5.
- warp: 4.
- party: 4.
- friend: 3.
- gacha: 2.

Confirmed handlers include account login, character list/login/create, field information, player/NPC/enemy appearance, movement, warp, item information, equipment, shops, gacha, quests, chat, party, friends, clan, mail, PvP, battle initialization and battle events.

## Network/bootstrap evidence

Release hostentry:

`https://capi-prd.logres-jrpg.com:8443/lfsapi/hostentry/${platform}/${version}`

The APK also contains historical dev, staging, check, preview, promotion, and AGS-local host profiles.

Embedded transport configuration includes:

- PingInterval: 1000 ms.
- ConnectTimeout: 10000 ms.
- AllowedNoCommunicationTime: 20000 ms.
- SendBufferSize: 1048576 bytes.
- RecvBufferSize: 1048576 bytes.
- SendWindowSize: 32768 bytes.
- RecvWindowSize: 65536 bytes.
- MinimumSizeOfTransmission: 1024 bytes.
- AllowedReuseAddress: true.

## Bundled JSON evidence

66 Global JSON files parsed with no failures. Important groups include:

- authentication and system strings.
- character creation.
- world select.
- field settings.
- HUD settings.
- battle text and multi-skill reservation.
- encounter settings.
- quest data.
- equipment filters, sorting, UI and text.
- inventory.
- fusion and evolution.
- gacha and box gacha.
- shops.
- gifts.
- garage and accomplished-item garage.
- mission and event settings.
- clan and community.
- chat.
- weather.
- tutorial popup text.
- post-effect settings.
- sixth-sense UI/configuration.

## Original source-path evidence

The binary retains original build-machine source paths under:

`/Users/lfsuser/workspace/lfsen_android_client_build3/`

Recovered paths include:

- `client/game/src/scene/ReleaseScene/EntranceScene/ReleaseScene_Title.cpp`
- `client/game/src/scene/ReleaseScene/EntranceScene/ReleaseScene_CharcterMake.cpp`
- `client/game/src/resource/resources/map/mapformat.pb.cc`
- `client/game/src/flash/resource/lfla.data.pb.cc`
- `common/BattleProduction/battleproduction.pb.cc`
- `common/LflaTbl/lfla.table.pb.cc`
- `common/motion/motionTbl.pb.cc`
- `common/prefix/prefix_matchtbl.pb.cc`

Additional retained source paths cover chat, gacha, garage, item/equipment, quest, event point, HUD, clan, community, gifts, shops, sixth sense, Spine, and platform JNI code.

## Evidence policy

Global 3.0.24 evidence takes precedence over current-JP behavior for reconstruction of Global-era behavior when the two disagree.

Current-JP evidence remains useful for identifying surviving architecture, file formats, and implementation patterns, but must not silently overwrite Global-era semantics.

The full private analysis corpus remains under `/home/ubuntu/logres/private/global-apk/3.0.24/re/`.
