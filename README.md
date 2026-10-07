# RPGMFrame

Experimental Linux ARM64 runtime-conversion toolkit for RPG Maker and Godot games, initially targeting the Steam Frame.

RPGMFrame is intentionally separate from [RenFrame](https://github.com/AZumD/RenFrame) while the RPG Maker runtime model is still being explored. If both projects stabilize around the same abstractions, they can later become backends of a shared converter.

## Current status

RPGMFrame can:

- detect RPG Maker XP, VX, VX Ace, MV, MZ, and Godot game exports
- report engine, confidence, evidence, title, payload root, and RPG Maker version
- auto-descend through unambiguous chains of extracted archive wrapper directories
- build **RPG Maker XP / VX / VX Ace** games around Linux ARM64 mkxp-z
- build **RPG Maker MV** games around Linux ARM64 NW.js
- build **RPG Maker MZ** games around Linux ARM64 NW.js
- build **Godot** Windows exports around the exact matching official Linux ARM64 Godot runtime when an ARM64 release exists
- build directly from `.zip` downloads without manual extraction
- optionally package completed builds as portable `.tar.gz` archives
- automatically download, verify, and cache the required ARM64 runtimes
- accept a manually supplied NW.js runtime as an override
- validate that the NW.js `nw` binary is actually AArch64
- repair an empty NW.js package name while preserving game-specific package settings
- generate a launcher that discovers a running FrameTop Plasma/Xwayland environment
- provide Windows-style environment defaults such as LOCALAPPDATA, APPDATA, and USERPROFILE
- preserve game-owned package-root companion files while dropping the old Windows NW.js runtime
- inject a generic case-insensitive Linux path compatibility shim for browser assets and Node fs reads
- repair a missing MV fpsmeter.js include when the core requires it and the shipped library is present
- apply the upstream MV negative-frame-skip fix when an older vulnerable core is detected
- provide a RenFrame-style desktop GUI with drag/drop, inspection, conversion progress, and transfer packaging

The XP/VX/VX Ace mkxp-z and Godot paths are newly enabled and still need Steam Frame hardware validation. The MV runtime-swap path has been validated on Steam Frame hardware with an RPG Maker MV 1.6.1 game.

Both MV and MZ runtime-swap paths have now been validated on Steam Frame hardware. MV was validated with Jailbreak (RPG Maker MV 1.6.1) and with OMORI 1.0.8d (RPG Maker MV 1.6.1), using a clean RPGMFrame build with no hand-edits to the converted output. MZ was validated with Look Outside 0.30 (RPG Maker MZ 1.8.1), including gameplay, controller input, audio, menus/settings, save/load, and relaunch.

OMORI is intentionally treated as a compatibility stress test rather than a game-specific target. The fixes learned from it are implemented as generic Windows/NW.js-to-Linux behavior. See [Compatibility notes](docs/compatibility.md).

The MV/MZ backend pins **NW.js 0.117.0**, the version currently validated on Steam Frame. The XP/VX/VX Ace backend pins an upstream mkxp-z Linux ARM64 CI artifact. The Godot backend reads the exact engine version from the PCK header and resolves the matching official Linux ARM64 Godot release. Downloads are checksum-verified before caching. Use `--runtime-version` to test another NW.js release or `--runtime` to supply an extracted runtime directly.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```


## Desktop GUI

RPGMFrame now includes a lightweight desktop frontend modeled after RenFrame's
GUI: dark CustomTkinter UI, optional drag-and-drop, automatic game inspection,
conversion progress, output controls, and a transfer archive enabled by default.

Run it from source:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[gui]"
rpgmframe-gui
```

Or:

```bash
python app/main.py
```

The GUI displays the detected RPG Maker engine/version and compatibility result,
then uses the same tested builder and packaging code as the CLI. It does not
maintain a separate conversion implementation.

Native packaging scripts are included for both platforms:

| Target | Script |
| --- | --- |
| Windows x64 | `powershell -File build/build_windows.ps1` |
| Linux aarch64 / Steam Frame | `bash build/build_linux_aarch64.sh` |

Windows GUI packaging is scaffolded to match RenFrame, but the native-Windows
conversion path still needs broad real-game validation. Linux/WSL and Steam
Frame are the currently proven development/runtime paths.

## Inspect

```bash
rpgmframe inspect /path/to/game
rpgmframe inspect /path/to/game --json
```

## Build

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

The launcher preserves a normal desktop environment, but if it detects FrameTop's nested Plasma session it imports that session's display, Xauthority, and runtime variables before starting NW.js. It also maps common Windows profile environment variables to Linux/XDG locations and starts NW.js with the converted package as its working directory.

Converted MV/MZ payloads include a small RPGMFrame compatibility shim. It only rewrites failed, package-local reads when the requested path differs from an existing file by case. This covers both browser-side resources such as images/audio and Node fs calls used by plugins. Exact paths are left alone, external paths are not rewritten, and case-colliding source trees are reported instead of guessed.


### XP / VX / VX Ace backend

RPGMFrame recognizes classic RGSS projects from their generation-specific script
data (`.rxdata`, `.rvdata`, `.rvdata2`), encrypted archive formats
(`.rgssad`, `.rgss2a`, `.rgss3a`), and RPG Maker `[Game]` INI metadata.

These games are packaged with Linux ARM64
[mkxp-z](https://github.com/mkxp-z/mkxp-z) instead of NW.js. RPGMFrame writes a
small `mkxp.json` that selects the correct RGSS generation, enables mkxp-z's
case-insensitive path cache, and preserves renamed executable/archive stems via
`execName`. The original game payload is copied under `game/` unchanged.

The mkxp-z backend has now booted an RPG Maker XP title to its title screen on
Steam Frame hardware. Deeper gameplay still needs broader validation. Existing
legacy mkxp deployments are migrated conservatively: RPGMFrame translates known
`mkxp.conf` settings, enables upstream compatibility preloads, uses a portable
`SRCDIR`-based game root, and disables SDL HiDPI backing by default to avoid
fractional-scale pointer drift.


### Godot backend

Godot is handled as a third runtime family. RPGMFrame recognizes standalone
`.pck` exports by the `GDPC` pack header and reads the pack format plus the
engine's exact `major.minor.patch` version directly from the PCK header.

Self-contained Windows exports are supported too. If the PCK is embedded in the
`.exe`, RPGMFrame uses Godot's own end-of-file pack footer to locate and
extract the embedded PCK without modifying the source executable.

For a normal GDScript/native export the conversion path is intentionally small:

1. identify the main PCK
2. read its exact Godot version
3. resolve the matching official `Godot_vVERSION_linux.arm64.zip` release
4. verify GitHub's SHA256 digest, or older releases' `SHA512-SUMS.txt`
5. package the ARM64 Godot binary with the original game payload
6. launch it with `--main-pack` through the normal FrameTop-aware launcher

Godot releases that do not provide an official Linux ARM64 binary are
recognized but fail cleanly instead of silently substituting another engine
version.

C#/.NET exports are detected but intentionally not converted yet. Their managed
and native runtime bundle is platform-specific, so treating them like a plain
PCK swap would overstate compatibility. Native GDNative/GDExtension plugins can
also require Linux ARM64 builds of the game's plugin libraries.
