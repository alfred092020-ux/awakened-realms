# Global field HUD layout evidence

This note records bounded layout facts recovered from the owner's Global Logres cache. It does not include proprietary Lua source bytes.

Source package

Archive member: `files/cache/patch/gui/HUD.mbn`

Package SHA-256: `d4fe09e50c8f8fa6cb560ea4ef5348c9092a41fff03f17e316a982f10cc6316a`

Relevant generated Lua entries:

- `MainHUD.lua`
  - SHA-256: `b1252039f5f64653578345990d977ddcfa62dd38fe9c8166befedcd78d0d3dc4`
- `field_hud_footer.lua`
  - SHA-256: `e15f4433dfbc2be6118a6f6564ecd72c6b1527fa0117a4f473eba1057ade3b2f`

Evidence classification: CONFIRMED ORIGINAL SOURCE BYTES.

Recovered field footer facts

The `field_hud_footer.lua` root uses a 720 by 1104 content area and a top-center root anchor.

The `footer_bar` node uses `gui/HUD/field_underbar.png` as a 720 by 100 nine-slice resource.

Its raw generated Lua position is:

- x = 360
- y = 76

Its anchor constraint is bottom plus horizontal center, with bottom = 45.

The `menu` button is anchored to vertical center plus right, with:

- right = 88
- bottom = 0

The normal menu image uses `gui/HUD/field_menu.png`. Its raw local position is x = 0, y = 0. Its nested anchor-style offsets are bottom = 35 and left = 88.

Interpretation boundary

The source coordinates and anchor constraints above are confirmed original.

The exact transform from the original GUI layout engine into the reconstructed Phaser viewport remains unresolved. The historical footer variant selected at every tutorial state also remains unresolved.

Do not convert the raw coordinates into a claimed historical screen-space position until the original anchor/layout transform is reproduced or independently verified.

Inspector

Run:

`python3 -B scripts/logres/inspect_global_field_hud_layout.py /path/to/global-cache.zip --require-known-global`

The inspector reads the HUD package, verifies the known Global hashes when requested, extracts only structured layout facts, and emits JSON. It does not write proprietary source bytes.
