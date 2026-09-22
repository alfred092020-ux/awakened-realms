# Private Logres asset hydration

Original Logres runtime binaries are not committed to this public repository.
They are recovered from the owner's private client/cache archives into paths that
are already ignored by Git.

## Default field background

`field_settings.json` names:

`map/background/mbg_002_001/mbg_002_001.png`

The newer recovered split cache contains the corresponding package:

`files/cache/patch/map/background/mbg_002_001.mbn`

Its manifest contains `mbg_002_001.astc`. The recovered ASTC is 6x6 LDR block
compression with dimensions 720x1280. Its SHA-256 is:

`74b9111b485d124722c5c3d6f4ff9cb5e95b95438fb25a31eff4cf4d63c74482`

Run:

```sh
python3 scripts/logres/hydrate_private_assets.py /path/to/files.joined.zip
```

The tool writes only beneath the gitignored `public/__logres_ref/` runtime tree.
It validates the MBN manifest, zlib size, ASTC header, dimensions, exact recovered
SHA-256, and compressed block length before writing anything.

It also creates linear and sRGB KTX 1 wrappers. These wrappers contain the exact
original ASTC compressed blocks; they do not decode, resample or recompress the
image. Both variants are retained because the raw ASTC container does not encode
whether the original renderer sampled this texture as linear or sRGB. Runtime
code must not select one until client evidence establishes the original color
interpretation.

Use `--self-test` to validate the parser and KTX wrapper using only synthetic,
non-proprietary data.
