# Strict Logres Reconstruction Mode

The active game reconstruction uses the extracted
Logres clients as its source of truth.

## Source priority

### Player-facing content

Use the Global Logres client first for:

- English text
- translated UI
- menus
- tutorials
- buttons
- labels
- dialog
- quest text
- equipment text
- chat text
- inventory text
- title/world-select assets

### Technical and newer systems

Use the Japanese client only when:

- the Global client does not contain the system
- the Japanese client contains a newer implementation
- technical evidence is absent from Global

When Japanese technical data is used, an available
Global English term or translation should still be
used for the player-facing presentation.

## Strict reconstruction rules

- No legacy Awakened Realms roguelike gameplay.
- No legacy RPG prototype content.
- No invented client-visible NPCs, monsters, jobs, skills,
  quests, items, currencies, maps, or gameplay behavior.
- No invented translations when a Global translation
  exists.
- Global client is the primary English reference.
- Japanese client is the extended-system fallback.
- Runtime visuals use extracted Logres assets privately.
- Runtime configuration reads extracted client JSON.
- Examine surviving evidence before reconstructing missing data.
- When originals cannot be recovered, replacement server-only
  rows, stats, formulas, drops, progression, economy values,
  account state, persistence, and responses are permitted.
- Replacement server data must preserve the evidenced client
  experience and must not be represented as historical originals.
- Reconstructed server behavior must be explicitly
  labeled RECONSTRUCTED.
- Currency, inventory, experience, stats, damage, results,
  rewards, drops, progression, and purchases must ultimately
  be authoritative on the replacement server, not the client.
- For Japanese-only features without Global translations,
  preserve the real behavior and provide accurate English text.

## Development and integration

- Use feat/logres-reconstruction as the integration target.
- Do not modify main without explicit owner approval.
- Do not merge agent/logres-playable-slice-core-001 or other
  diagnostic branches merely because they exist.
- Use the owner's Control Sheet Patch Runner for normal PATCH
  and guarded MERGE jobs. Verify exact base and source SHAs,
  inspect the resulting diff, and retain all runner controls.
- If runner access fails, keep locally prepared work unmerged
  and clearly distinguish local verification from VM verification.
