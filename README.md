# RPGMFrame

Experimental Linux ARM64 runtime-conversion toolkit for RPG Maker games, initially targeting the Steam Frame.

RPGMFrame is intentionally separate from [RenFrame](https://github.com/AZumD/RenFrame) while the RPG Maker runtime model is still being explored. If both projects stabilize around the same abstractions, they can later become backends of a shared converter.

## Current status

RPGMFrame can:

- detect RPG Maker MV and MZ game directories
- report engine, confidence, evidence, title, payload root, and RPG Maker version
- auto-descend through a single extracted archive wrapper directory
- build **RPG Maker MV** games around Linux ARM64 NW.js
- build directly from `.zip` downloads without manual extraction
- optionally package completed builds as portable `.tar.gz` archives
- automatically download, SHA256-verify, and cache the pinned NW.js ARM64 runtime
- accept a manually supplied NW.js runtime as an override
- validate that the NW.js `nw` binary is actually AArch64
- repair an empty NW.js package name while preserving game-specific package settings
- generate a launcher that discovers a running FrameTop Plasma/Xwayland environment

The MV runtime-swap path has been validated on Steam Frame hardware with an RPG Maker MV 1.6.1 game.

MZ is detectable but its build path is intentionally gated until the same transplant has been validated on real hardware.

The default runtime is pinned to **NW.js 0.117.0**, the version currently validated on Steam Frame. Use `--runtime-version` to test another official release or `--runtime` to supply an extracted runtime directly.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Inspect

```bash
rpgmframe inspect /path/to/game
rpgmframe inspect /path/to/game --json
```

## Build MV

Normal use now needs only the game directory:

```bash
rpgmframe build /path/to/mv-game
```

ZIP downloads can be passed directly:

```bash
rpgmframe build /path/to/game.zip
```

RPGMFrame safely extracts ZIP input into a temporary workspace, builds from it, and removes the temporary files afterwards.

To also create a transfer-ready archive:

```bash
rpgmframe build /path/to/game.zip --archive
```

With the default output naming, that produces both:

```text
game-frame/
game-linux-aarch64.tar.gz
```

On the first build, RPGMFrame downloads the official Linux ARM64 NW.js tarball and `SHASUMS256.txt`, verifies the archive, and caches the extracted runtime under `~/.cache/rpgmframe/runtimes/nwjs/`. Later builds reuse that cache.

Override the pinned runtime version:

```bash
rpgmframe build /path/to/mv-game --runtime-version 0.117.0
```

Or supply an already extracted runtime:

```bash
rpgmframe build /path/to/mv-game \
  --runtime /path/to/nwjs-v0.117.0-linux-arm64
```

The default output is `<source>-frame/` (with `.zip` removed for archive input). Use `-o` to choose another directory and `--force` to replace an existing output or packaged archive.

Launch the built game on the Frame with:

```bash
./launch.sh
```

The launcher preserves a normal desktop environment, but if it detects FrameTop's nested Plasma session it imports that session's display, Xauthority, and runtime variables before starting NW.js.
