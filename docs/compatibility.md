# Compatibility notes

RPGMFrame's goal is to convert classes of RPG Maker MV/MZ Windows deployments to Linux ARM64, not to accumulate per-game patches.

## Compatibility rule

When a game fails after a runtime swap, prefer this order:

1. Identify the Windows, NW.js, packaging, filesystem, or engine assumption behind the failure.
2. Implement the narrowest generic compatibility behavior that preserves normal Linux behavior.
3. Add a regression test for that behavior.
4. Only consider a game-specific workaround when the behavior cannot reasonably apply to other RPG Maker games.

The compatibility layer must not key behavior on a game title, executable name, archive name, or known game-specific plugin unless there is no generic alternative.

## Validated hardware conversions

| Game | Engine | Hardware result | Notes |
| --- | --- | --- | --- |
| Jailbreak | RPG Maker MV 1.6.1 | Working on Steam Frame | Initial MV runtime-swap validation |
| Look Outside 0.30 | RPG Maker MZ 1.8.1 | Working on Steam Frame | Gameplay, controller input, audio, menus/settings, save/load, relaunch |
| OMORI 1.0.8d | RPG Maker MV 1.6.1 | Working on Steam Frame | Clean converted output after generic compatibility repairs |

"Working" records the tested conversion path and observed gameplay. It is not a promise that every route, plugin, media codec, or optional feature in a game has been exhaustively tested.

## Compatibility classes learned from complex MV games

### Nested archive wrappers

Downloaded or repacked games may contain more than one directory around the actual RPG Maker package.

RPGMFrame recursively descends only through an unambiguous single-directory wrapper chain. It does not guess when multiple sibling directories could contain a game.

### Package-root companion resources

A Windows MV export commonly has a `www/` payload beside `package.json`, but plugins may also read resources from the package root with Node's `fs` APIs.

RPGMFrame therefore preserves game-owned root companions while replacing known Windows NW.js runtime baggage. This is why copying only `www/` is insufficient for some games.

Examples of discarded runtime baggage include Windows executables and DLLs, `resources.pak`, `swiftshader/`, and legacy `nw_<scale>_percent.pak` files.

### Windows profile environment variables

Some NW.js plugins assume Windows profile variables such as `LOCALAPPDATA`, `APPDATA`, or `USERPROFILE` exist.

The generated launcher supplies Linux/XDG defaults only when the caller has not already set them:

```text
LOCALAPPDATA -> XDG_DATA_HOME or ~/.local/share
APPDATA      -> XDG_CONFIG_HOME or ~/.config
USERPROFILE  -> $HOME
```

The launcher also starts NW.js with the converted package root as its working directory.

### Case-insensitive filesystem assumptions

Windows game builds can request `Leaf.png` while shipping `leaf.png`, or request `Languages/` while shipping `languages/`.

RPGMFrame injects a compatibility shim before the RPG Maker engine scripts. It retries failed package-local resource reads case-insensitively for both browser-side resource loading and common Node `fs` calls.

The resolver:

- leaves exact paths alone
- never rewrites paths outside the converted package
- caches successful resolutions
- refuses to guess when a directory contains case-colliding names such as `Foo.png` and `foo.png`

This preserves the original source tree rather than renaming every asset.

### Missing engine-adjacent library includes

Some MV deployments ship a library required by the engine but omit its script tag from `index.html`. One observed example is `fpsmeter.js`, while `rpg_core.js` constructs `FPSMeter`.

RPGMFrame repairs this only when all of the following are true:

- the engine is MV
- `rpg_core.js` references `FPSMeter`
- a case-insensitive `fpsmeter.js` library exists under `js/libs/`
- the page does not already load it
- the page contains the MV core script so the library can be inserted immediately before it

This is a consistency repair based on the shipped engine and library, not a title-specific patch.

## What is deliberately not generalized yet

Failures caused by a game-specific plugin should not automatically become RPGMFrame behavior. A debugging patch belongs in the converter only after the underlying assumption can be expressed generically.

Examples include game-specific data initialization order, DRM or platform-service integrations, and plugin-specific logic unrelated to Windows/Linux compatibility.

Native Node addons are another boundary. An x86/x64 `.node` binary cannot be made ARM64-compatible by path rewriting. RPGMFrame should detect and report native addons rather than pretending they are portable.

## Regression philosophy

Hardware discoveries should become small synthetic tests wherever possible. Tests should reproduce the compatibility class without including copyrighted game assets or depending on a particular commercial game.

OMORI is useful because it exposed several assumptions at once. The regression suite should remember the assumptions, not OMORI itself.


### Old MV negative frame-skip freeze

Older RPG Maker MV cores contain a render-loop bug where
`Graphics._skipCount` can become negative after a clock adjustment. The old
core renders only when the value is exactly zero, so a negative value can leave
the screen frozen indefinitely while game logic and audio continue.

RPGMFrame applies the upstream CoreScript repair only when the copied
`rpg_core.js` contains the exact vulnerable expression once:

```javascript
if (this._skipCount === 0) {
```

It is changed to:

```javascript
if (this._skipCount <= 0) {
```

Already-fixed cores are left untouched. This was encountered while validating
Fear & Hunger, but it is intentionally implemented as an engine-level MV repair
because the bug exists across older RPG Maker MV games.


## RPG Maker XP / VX / VX Ace through mkxp-z

Classic RGSS games use a different backend from MV/MZ. RPGMFrame detects XP,
VX, and VX Ace from generation-specific Scripts data, encrypted archive
extensions, and `[Game]` INI metadata, then packages the game around a Linux
ARM64 mkxp-z runtime.

The generated `mkxp.json` sets the RGSS generation explicitly and leaves
mkxp-z's case-insensitive path cache enabled. If a game renamed the stock
`Game.exe` / `Game.ini` / encrypted archive stem, RPGMFrame derives that stem
from the matching INI and sets mkxp-z's `execName` rather than renaming the
user's files.

The backend preserves the complete game payload and does not attempt to rewrite
Ruby scripts by default. It warns about declared external RTP dependencies and
WMA assets because those can require additional compatibility work.

The currently pinned mkxp-z runtime is upstream CI revision `37a04d1`, Linux
ARM64 Ubuntu Xenial artifact `11271950906`, verified against SHA256
`3e0f3d6ed6486b672ed8988c180d2e6fd361622b5015cc245ce9c004ae5e3135`.
The pin should be refreshed deliberately rather than silently following mkxp-z
`dev`, so converter behavior remains reproducible.


## Godot

Godot exports use a separate backend from both NW.js and mkxp-z.

RPGMFrame treats the Godot PCK header as the source of truth. A standalone PCK
starts with Godot's `GDPC` magic followed by the pack format and engine
`major.minor.patch` version. Self-contained Windows exports place equivalent
pack metadata at the end of the executable, allowing RPGMFrame to locate and
extract the embedded PCK generically.

The backend requests the exact matching stable Godot release from the official
`godotengine/godot` GitHub releases. If that release contains
`linux.arm64`, RPGMFrame downloads it and verifies either the asset's
published SHA256 digest or the release's SHA512 checksum list before caching
the binary.

The converted launcher uses Godot's `--main-pack` option rather than
re-exporting or modifying project files. This keeps the game payload unchanged.

Current conservative boundaries:

- C#/.NET exports are recognized but not automatically converted.
- Releases without an official Linux ARM64 binary are recognized but not built.
- Windows native plugins may require Linux ARM64 GDNative/GDExtension builds.
- Godot support is marked `needs_testing` until validated on Steam Frame hardware.
