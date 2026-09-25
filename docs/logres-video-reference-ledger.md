# Logres video reference ledger

Status: bounded visual/behavioral evidence ledger for user-supplied recordings.

The three recordings below are valuable reference evidence, but their exact build/date lineage is not independently bound to Global 3.0.24. Therefore every observation in this ledger is capped at **VERSION_SENSITIVE** unless another primary source independently proves the historical Global fact.

## Evidence authority

1. **Recovered Global 3.0.24 APK/native evidence** — primary historical authority when a fact is actually present in the recovered client.
2. **Original gameplay footage with independently proven Global lineage** — may confirm directly visible historical presentation/behavior.
3. **User-supplied footage with unproven version lineage** — visual/behavioral reference only; never auto-promoted to Global truth.
4. **Current-JP evidence** — corroboration only. Similarity may guide reconstruction but cannot replace missing Global evidence.
5. **Reconstruction output** — implementation evidence, not historical evidence.

The supplied files in this task are category 3. No current-JP footage is being silently treated as historical Global footage.

## Source recordings

| Recording | Duration | Frame | FPS | Authority | Global 3.0.24 identity | Current-JP identity |
| --- | ---: | --- | ---: | --- | --- | --- |
| `1000027040.mp4` | 1183.57 s | 1280×720 | 30 | VERSION_SENSITIVE user video | UNPROVEN | UNPROVEN |
| `1000027041.mp4` | 830.77 s | 608×1080 | 30 | VERSION_SENSITIVE user video | UNPROVEN | UNPROVEN |
| `1000027042.mp4` | 1368.20 s | 1920×1080 | 60 | VERSION_SENSITIVE user video | UNPROVEN | UNPROVEN |

The sampled-frame source artifact is:

`/home/ubuntu/logres/artifacts/video-reference-canon/user-supplied-video-observations-20260925.md`

## Observable presentation and behavior

### Title / character creation

- `1000027040.mp4 @ 0.0s`: Logres title presentation visibly includes **Touch to start** and smaller lower utility/account controls.
- `1000027041.mp4 @ 37.9s`: Select Gender uses a gold/orange framed header, large character art, male/female selection, arrow navigation and a large red **OK** button.
- `1000027042.mp4 @ 780.0s / 812.0s`: character creation/name entry visibly uses a portrait preview, a grid of face/hair choices and a red **OK** button.

### Field HUD / town / interior

- `1000027041.mp4 @ 73.7s`: portrait field visibly has a gold top status HUD, black quest strip, compact actors/enemies, a bottom shortcut row (**World / Map / Clan / Group / Party / Direct**), plus **Message** and **MENU**.
- `1000027042.mp4 @ 684.0s / 716.0s`: populated isometric town with multiple named character/NPC sprites, a persistent gold top HUD and lower Message/MENU presentation.
- `1000027042.mp4 @ 748.0s`: an interior/town area uses a blue floor with actor sprites while retaining the same broad presentation shell.
- `1000027042.mp4 @ 972.0s`: dark interior/isometric map visibly preserves compact player presentation and environmental boundaries.
- `1000027040.mp4 @ 982.0s / 1028.0s`: isometric field maps visibly use compact character sprites and persistent HUD framing.

### NPC / dialogue

- `1000027041.mp4 @ 55.8s`: dialogue overlays the field with a cream/gold framed box, a gold **Akane** nameplate, large illustrated character presentation, **Repeat** at lower-left and **Skip** at lower-right.
- `1000027041.mp4 @ 145.3s / 163.2s`: the same dialogue-box geometry and Repeat/Skip affordances recur.
- `1000027041.mp4 @ 270.5s / 342.1s`: a dialogue presentation with the visible name **Joe** uses the same broad gold/cream frame and Repeat/Skip pattern.

The names and exact dialogue text above are facts about these sampled recordings only. They are not promoted to Global 3.0.24 actor/dialogue identity.

### Tutorial guidance

- `1000027041.mp4 @ 234.7s`: a large hand pointer is visibly placed above an interactable field target while multiple actors remain on the map.
- `1000027041.mp4 @ 252.6s`: field combat guidance visibly uses a hand/target cue while the lower shortcut row remains visible.
- `1000027041.mp4 @ 73.7s`: a speech-bubble interaction cue and prominent **Let's Fight** field guidance are visible.

### Battle

- `1000027041.mp4 @ 91.6s–109.5s`: enemy presentation occupies the upper field, player presentation the lower field, while top quest/status framing and lower action controls remain visible.
- `1000027041.mp4 @ 288.4s–324.2s`: target/attack presentation progresses into a large **Congratulations** result overlay.
- `1000027040.mp4 @ 1120.0s`: battle field again visibly contains enemy/player sprites with a lower action bar.

### Quest / result banners

- `1000027041.mp4 @ 181.1s` and `360.0s`: large blue-and-gold **Quest Cleared** overlay centered over the field.
- `1000027042.mp4 @ 844.0s`: the same broad Quest Cleared presentation family is visible.
- `1000027040.mp4 @ 522.0s`: a **Guild Congratulations** result panel uses parchment/gold presentation.

### Menus / overlays

- `1000027041.mp4 @ 216.8s`: equipment/item detail popup uses parchment/gold framing with **Lock** and **Close**.
- `1000027042.mp4 @ 876.0s`: daily-login/reward parchment screen.
- `1000027042.mp4 @ 908.0s`: hunter/equipment profile panel.
- `1000027042.mp4 @ 1036.0s–1068.0s`: event selection uses stacked promotional banners.
- `1000027040.mp4 @ 660.0s`: crystal/store list.
- `1000027040.mp4 @ 752.0s`: equipment/profile screen with portrait card and gear slots.
- `1000027040.mp4 @ 798.0s`: Multi Fusion inventory/list interface.
- `1000027040.mp4 @ 890.0s`: Friends menu.

## System-chrome observation and conflict ledger

At `1000027041.mp4 @ 55.8s` and `73.7s`, the portrait recording visibly includes a black Android navigation bar at the bottom with Back/Home/Recents-era controls. The sampled game frame begins directly with the game HUD at the top; an Android status bar is not visible there.

This is a real visible divergence from the current reconstruction, which intentionally uses immersive fullscreen presentation.

It is **not** enough to conclude that historical Global 3.0.24 required a visible Android navigation bar:

- the exact version/date lineage of this MP4 is unproven;
- the recovered Global 3.0.24 Android evidence proves `LFSActivity`, lifecycle and JNI/platform surfaces, but currently does **not** establish a historical status/navigation-bar visibility policy;
- device/OS/recording environment may also affect system chrome.

Therefore this remains a VERSION_SENSITIVE conflict rather than a historical override.

## Global vs current-JP separation

No observation in these three recordings is labeled `CONFIRMED_GLOBAL_3_0_24` solely because it resembles the recovered client.

Current-JP material remains in a separate corroboration-only bucket. A current-JP match may increase confidence that a presentation family persisted, but it cannot promote an unversioned recording to historical Global truth.

If recovered Global APK/native evidence and a version-sensitive video appear to disagree, the Global evidence wins for historical claims. The disagreement stays recorded rather than being silently normalized away.

## Unresolved

- exact build/version/date lineage of all three supplied MP4s;
- whether the visible Android navigation bar reflects Global history, a later client, a specific Android/device policy, or recording environment;
- behavior between sampled timestamps that was not inspected;
- exact historical Global actor identity/dialogue payload for names/text visible only in these version-sensitive recordings;
- any transition timing not directly measured from a narrower frame sequence.

Do not infer missing frames. Request a narrower extraction from the master when exact timing or a disputed transition matters.

