# Awakened Realms Combat FX Concept Curation

Curated from the Thunder RTX A6000 `combat-fx-pack-v1` generation batch on 2026-10-05.

These PNGs are **concept/source references**, not drop-in final runtime effects. Rebuild them in Unity as layered particles, trails, sprite sheets, masks, shaders, hit flashes, screen-space overlays, and pooled VFX prefabs as appropriate. Do not ship the square concept cards directly.

One strongest variant is retained for each of the 30 concepts: five faction cast/hit/trail families plus blind, boss break/enrage, buff/debuff, burn, crit, heal, poison, shield, silence, stun, ultimate charge/impact, and victory.

Runtime hierarchy remains: Basic < Skill < Ultimate < Boss/Transformation. Preserve Android readability and performance through pooling, bounded overdraw, texture compression/atlasing where useful, and quality scaling.
