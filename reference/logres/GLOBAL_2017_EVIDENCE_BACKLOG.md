# Global 2017 Evidence Backlog

Status: implementation-facing evidence crosswalk
Target: Global commercial launch, 25 May 2017
Integration branch: `feat/logres-reconstruction`

This file is not a gameplay specification. It records evidence that changes an
engineering decision or blocks a merge.

## Evidence precedence

1. Global official material from April-May 2017.
2. Global beta/launch gameplay, screenshots, and recovered Global client data.
3. Pre-May-2017 Japanese official/developer evidence when Global does not
   contradict it.
4. Contemporary press.
5. Contemporary community documentation.
6. Later wikis or post-launch material, only with explicit version controls.

Project labels remain:

- CONFIRMED ORIGINAL: directly established by recovered client/native data,
  primary source, or direct original recording for the specific claim.
- SUPPORTED INFERENCE: multiple compatible facts support the claim, but an
  identifying link or server-only fact is still missing.
- RECONSTRUCTED: replacement implementation needed to reproduce evidenced
  behavior without claiming historical server data.
- UNRESOLVED: evidence is conflicting, incomplete, version-sensitive, or not
  yet tied to the Global target.

## External research layer

Ingested 22 Sep 2026:

- `Logres_Research_Handoff_2026-09-22`
- Research-only handoff. Its HIGH/MEDIUM/LOW labels are retained as source
  quality, not automatically converted into project CONFIRMED ORIGINAL.
- The handoff source catalog R01-R50 remains the provenance catalog for its
  claims. URLs are not duplicated here.
- Especially relevant active-source IDs: R03-R09, R11-R20, R27-R29,
  R32-R39, R47-R50.

## Actionable findings

### G17-TUT-001 - Millennium Tree / Room 1 tutorial clue

Priority: P0
External evidence: handoff HIGH, near-Global January 2017 visual evidence
Project state: SUPPORTED INFERENCE

The handoff places a level-1 Adventurer in Millennium Tree, Room 1, with a
tutorial hand targeting Green Gels. It supports normal-field reuse with
quest-specific state. It does not establish an internal map ID.

Internal cross-check:

- User-supplied original tutorial footage independently confirms a normal
  grassy field, visible level-1 green enemies, guided targeting, a nearby NPC,
  quest overlay, and battle transition.
- Authentic rendering visually rejects `001_000_00001` as that tutorial
  field.
- A named archived Millennium Tree daytime map
  (SHA-256 `2b1adead93ff78b3aa86c7cc9800b5f71604c442e64418c8f800d85a99607248`)
  was compared deterministically against recovered authentic field renders.
- `002_000_00001` produced 338 RANSAC-consistent SIFT inliers from 434
  ratio-test matches against that named Millennium Tree artifact
  (inlier ratio 0.7788). `002_000_00012` was related but weaker at 183
  inliers; unrelated candidates were far lower.
- The exact `002_000_00001.mbn` field package is present in the recovered
  Global client cache. The similarly matching later JP variant
  `002_000_00008` is not present in that Global cache capture.
- The user-supplied original tutorial frame independently produced 59
  RANSAC-consistent inliers against `002_000_00001`, supporting the same
  field family. The tutorial frame alone is not unique enough to prove a map
  ID because nearby variants share art/topology.
- Combined with the handoff's near-Global Millennium Tree / Room 1 clue,
  `002_000_00001` is now the strongest tutorial-map candidate.
  This remains SUPPORTED INFERENCE, not CONFIRMED ORIGINAL.

Unblocks: Map/Rendering, Tutorial/Onboarding, NPC/Quest, Encounter.

Next proof:

- Tie the recovered map identifier to a Global-era area/warp/entity record or
  another primary/client source that names Millennium Tree directly.
- Resolve Room 1, tutorial spawn, Green Gel population, NPC state, and objective
  as quest-instance data rather than properties of the static map.
- Keep map identity and quest-instance state separate until those values are
  independently recovered.

### G17-ONB-001 - Character-registration ordering

Priority: P0
External evidence: handoff HIGH-MEDIUM, version-sensitive near-Global lineage
Project state: UNRESOLVED

The handoff says gender is selected before full registration and that the early
player is effectively an unnamed Adventurer, with permanent name/hair/face
registration after the Hunter tutorial sequence.

Internal cross-check:

- Recovered Global client evidence confirms the native CharacterMake scene,
  Global CharacterMake assets/text, and exact
  `C_GMCL_CHAR_CREATE_REQ` argument shape.
- Current repo flow is World Select -> Character Create -> Field.
- Current recovered Global evidence does not yet prove where the CharacterMake
  request occurs relative to the first field/Hunter registration.

Unblocks: Tutorial/Onboarding, QA/Regression, Integration.

Merge guard:

- Do not reorder the onboarding scenes from this handoff alone.
- Resolve with Global beta/launch footage or direct Global-client state/protocol
  transition evidence.

### G17-BTL-001 - Five equipped weapons versus three normal-skill slots

Priority: P0
External evidence: handoff HIGH-MEDIUM; official/help/developer lineage
Project state: UNRESOLVED SEMANTIC CONFLICT

The handoff describes five equipped weapons as the primary active combat kit,
with each weapon providing normal/special behavior and weapon switching.

Internal cross-check:

- Recovered Japanese technical config exposes
  `skill_equip_max_normal = 3`.
- Existing extracted client facts and the staged battle-foundation branch use
  that value as three normal skill slots.
- That technical UI/config value has not been proven to mean "equipped weapon
  count" and must not override Global evidence without semantic proof.
- Recovered Global tutorial text independently confirms EP recovery on hit and
  switching weapons by sliding the sword marker.

Unblocks: Battle, UI/UX, Inventory/Equipment.

Merge guard:

- Do not merge a three-weapon battle model.
- Inspect Global battle UI/assets/config and native/view semantics to separate
  equipped weapon count from normal-skill subslots.

### G17-QST-001 - Map identity and quest-instance state are separate

Priority: P0
External evidence: handoff HIGH-MEDIUM across tutorial/quest/room sources
Project state: SUPPORTED INFERENCE for tutorial reuse; RECONSTRUCTED contract
permitted

Quest state can vary enemy population, objectives, start/spawn state, NPC
state, tutorial overlays, room assignment, battle capacity, time/defeat limits,
and scripted outcomes without requiring a distinct static field map.

Internal cross-check:

- Original tutorial footage shows tutorial-specific overlays and encounter state
  on a normal field presentation.
- Current replacement server has only a generic `tutorial-field` next state
  and no explicit quest-instance model.
- Native/client evidence already treats field geometry/navigation separately
  from server authority.

Unblocks: Tutorial/Onboarding, NPC/Quest, Encounter, Protocol/Backend.

Implementation:

- Add a clearly RECONSTRUCTED quest-instance authority contract now.
- Keep every historical value null/unresolved until evidence supplies it.
- Make capacity/timer/defeat rules data-driven rather than global constants.

### G17-ROOM-001 - Shared Rooms are core quest state

Priority: P1
External evidence: handoff HIGH-MEDIUM, official help/contemporary guides
Project state: SUPPORTED INFERENCE pending Global launch-specific UI details

Quest entry assigns/selects a shared Room. Field room state is distinct from
map identity. Room selection/population belongs in the quest-instance/server
model rather than the renderer.

Unblocks: Protocol/Backend, NPC/Quest, Multiplayer.

### G17-JOIN-001 - Join Battle is distinct from formal Party

Priority: P1
External evidence: handoff HIGH-MEDIUM, official help/Global marketing
Project state: SUPPORTED INFERENCE for Global launch behavior

Do not collapse spontaneous field Join Battle into party membership. Model
encounter participation and party membership as separate concepts.

Unblocks: Encounter, Battle, Protocol/Backend, Multiplayer.

### G17-PROG-001 - Global beginner job unlock guardrail

Priority: P2
External evidence: handoff MEDIUM, surviving English documentation
Project state: UNRESOLVED until the specific Global source record is indexed

The handoff says Chapter 1 Quest 4, "Crystal and Mandra", unlocks Knight,
Ranger, Priest, and Magician together. Older JP job-unlock sequencing must not
be projected into May 2017 Global.

Unblocks later: Jobs/Progression, Quest.

### G17-VERSION-001 - Post-launch JP/Global feature exclusion

Priority: permanent guardrail
External evidence: mixed HIGH/MEDIUM dated sources
Project state: CONFIRMED ORIGINAL as chronology where supported by dated
primary releases; individual mechanics still retain their own evidence label

Do not project August 2017 JP tutorial additions or late-July 2017 Global
Guardian/Tier-4 state backward into the 25 May 2017 target. Critical rules,
Crystal holding bonuses, rarity names, jobs, and campaign behavior remain
versioned data.

Unblocks later: Jobs/Progression, Shop/Gacha, Inventory/Equipment.

## Findings already covered internally - do not duplicate research

- Client-side pathfinding with server validation: already supported by CEDEC
  lineage and current native field-navigation reverse engineering.
- Eight-neighbor navigation, Prohibition gating, movement-level checks,
  diagonal corner-cut prevention, link costs, and zero heuristic: already
  implemented from native evidence.
- Server authority as a reconstruction principle: already enforced by
  `STRICT_MODE.md`.
- Portrait orientation and low-density touch UI: already reflected in the
  extracted scene/config work and does not need another research lane.
- Static terrain is layered map data, not a prerendered screenshot: already
  supported by recovered map protobuf/native renderer work.

## Current critical evidence path

1. Identify Millennium Tree static map ID without conflating quest state.
2. Resolve Global onboarding order before changing current scene sequence.
3. Resolve five-weapon versus three-normal-skill-slot semantics before battle
   integration.
4. Build RECONSTRUCTED quest-instance authority with nullable/unresolved
   historical values.
5. Bind authentic field navigation to the identified map.
6. Add NPC/encounter state, then battle, victory, and reward flow.
