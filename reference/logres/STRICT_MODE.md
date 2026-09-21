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
- No invented NPCs, monsters, jobs, skills, quests,
  items, currencies, maps, or balance values.
- No invented translations when a Global translation
  exists.
- Global client is the primary English reference.
- Japanese client is the extended-system fallback.
- Runtime visuals use extracted Logres assets privately.
- Runtime configuration reads extracted client JSON.
- Missing server-only values remain unknown until they
  can be reconstructed from evidence.
- Reconstructed server behavior must be explicitly
  labeled RECONSTRUCTED.
