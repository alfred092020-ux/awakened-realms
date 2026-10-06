# Awakened Realms Original Project Migration

Source archive: awakened-realm-main.zip
Source SHA-256: 174b06ffc3a300eb492e7ae015df61f9de2028b6fb0959371bc8204ecccf4c0f
Original Unity version: 6000.2.1f1
Validated migration editor: Unity 6000.3.25f1

This directory is the governed production candidate derived from the owner's original Awakened Realms project.

Import policy:
- Preserve original authored game assets, characters, animations, UI, scenes, prefabs, audio, shaders, and PlayFab integration.
- Library, Logs, UserSettings, IDE state, and generated build artifacts are excluded.
- Large UI design-source PSD files under Assets/UI/Awakened Realm New UI/psds are excluded from this runtime production copy. The original archive remains preserved by exact SHA above.
- Runtime PNG slices and referenced Unity assets remain present.

Compatibility fixes applied before import:
1. AwakenedRealm.Models.AttackInfo uses [Serializable] instead of the invalid [SerializeField] class annotation.
2. Cross Touch SwipeManager and its InputManager dedicated swipe helper methods compile in Editor as well as Android so Unity validation/build tooling is not broken by Android-only type visibility.

Battle wiring migration:
- Player formation is now a single authoritative 3x3 grid with nine stable slot indices.
- Active player party size is five.
- Placement preserves the exact selected grid slot into battle spawning.
- Duplicate hero placement is prevented.
- A sixth active hero is rejected.
- The legacy six player spawn transforms are migrated to nine.
- All fifteen legacy HeroSO assets receive stable IDs ar-legacy-001 through ar-legacy-015 when missing.
- Hero prefab, sprite, HeroController, SpriteRenderer, Animator, and animator-controller wiring is validated.
- Battle scene validation fails closed if formation wiring regresses.

Evidence:
- Unity 6.3.25f1 headless compilation succeeds.
- Battle scene serialized-reference audit: zero missing scripts and zero broken serialized references before migration.
- NormalizeBattleFormationWiring.Run succeeds.
- ValidateBattleWiring.Run succeeds with 9 player spawns, 9 enemy spawns, 1 boss spawn, party size 5, 9 UI placement cells, 15 hero assets, and 15 unique stable IDs.
- ExerciseFormationPlacement.Run succeeds, including use of former nonfunctional slots 7 and 9, exact slot preservation, moving an existing hero, and rejection of a sixth hero.
