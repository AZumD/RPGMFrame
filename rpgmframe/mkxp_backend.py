"""RPG Maker XP/VX/VX Ace backend using Linux ARM64 mkxp-z."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from collections.abc import Callable
from pathlib import Path

from rpgmframe.elf import read_elf_architecture
from rpgmframe.launchers import mkxp_launcher_body
from rpgmframe.mkxp_runtime import MkxpRuntimeError, MkxpRuntimeManager
from rpgmframe.models import BuildResult, EngineVariant, GameInspection
from rpgmframe.rgss import choose_rgss_ini, rgss_version_for_engine


class MkxpBuildError(RuntimeError):
    """Raised when an RGSS game cannot be packaged around mkxp-z."""


_LEGACY_ENGINES = {EngineVariant.XP, EngineVariant.VX, EngineVariant.VX_ACE}
_IGNORE_NAMES = frozenset({".git", "__pycache__", ".DS_Store"})


def _normalize_path(path: Path | str) -> Path:
    return Path(path).expanduser().resolve()


def _paths_overlap(a: Path, b: Path) -> bool:
    return a == b or a in b.parents or b in a.parents


def _ignore_junk(directory: str, contents: list[str]) -> list[str]:
    del directory
    return [name for name in contents if name in _IGNORE_NAMES or name.endswith(".pyc")]


def _staging_path(output: Path) -> Path:
    return output.parent / f".{output.name}.tmp-{uuid.uuid4().hex[:8]}"


def _install_staging(staging: Path, output: Path, *, force: bool) -> None:
    if not output.exists():
        staging.rename(output)
        return
    if not force:
        raise MkxpBuildError(
            f"Output already exists: {output}. Pass --force to replace it."
        )

    backup = output.parent / f".{output.name}.old-{uuid.uuid4().hex[:8]}"
    output.rename(backup)
    try:
        staging.rename(output)
    except Exception:
        backup.rename(output)
        raise
    else:
        shutil.rmtree(backup, ignore_errors=True)


def _validate_runtime(runtime: Path) -> str:
    executable = runtime / "mkxp-z.aarch64"
    if not executable.is_file():
        raise MkxpBuildError(
            f"mkxp-z runtime is missing mkxp-z.aarch64: {executable}"
        )
    architecture = read_elf_architecture(executable)
    if architecture != "aarch64":
        raise MkxpBuildError(
            "mkxp-z runtime architecture is "
            f"{architecture or 'unknown'}, not aarch64: {executable}"
        )
    return architecture


def _write_launcher(root: Path) -> Path:
    launcher = root / "launch.sh"
    launcher.write_text(mkxp_launcher_body(), encoding="utf-8", newline="\n")
    launcher.chmod(launcher.stat().st_mode | 0o755)
    return launcher


def _write_mkxp_config(
    destination: Path,
    *,
    game_root: Path,
    engine: EngineVariant,
) -> tuple[str | None, tuple[str, ...]]:
    ini = choose_rgss_ini(game_root, engine)
    config: dict[str, object] = {
        "gameFolder": "game",
        "rgssVersion": rgss_version_for_engine(engine),
        "winResizable": True,
        "fixedAspectRatio": True,
        "pathCache": True,
    }
    if ini is not None:
        config["execName"] = ini.exec_name

    destination.write_text(
        json.dumps(config, ensure_ascii=False, indent=4) + "\n",
        encoding="utf-8",
    )
    return (ini.exec_name if ini else None, ini.rtps if ini else ())


def _has_wma(root: Path) -> bool:
    for _directory, _dirnames, filenames in os.walk(root):
        if any(name.casefold().endswith(".wma") for name in filenames):
            return True
    return False


def build_mkxp_game(
    *,
    source_path: Path,
    output_path: Path,
    inspection: GameInspection,
    runtime: Path | str | None,
    force: bool,
    archive_type: str | None,
    progress: Callable[[str], None] | None,
) -> BuildResult:
    if inspection.engine not in _LEGACY_ENGINES:
        raise MkxpBuildError(f"Unsupported mkxp-z engine: {inspection.engine.value}")
    if inspection.game_root is None:
        raise MkxpBuildError("Detected RGSS game has no payload root")

    if runtime is None:
        try:
            runtime_path = MkxpRuntimeManager().ensure_mkxpz(progress=progress)
        except MkxpRuntimeError as exc:
            raise MkxpBuildError(str(exc)) from exc
    else:
        runtime_path = _normalize_path(runtime)
        if not runtime_path.is_dir():
            raise MkxpBuildError(f"Runtime path is not a directory: {runtime_path}")
        if progress:
            progress(f"Using supplied mkxp-z runtime: {runtime_path}")

    architecture = _validate_runtime(runtime_path)

    if source_path.is_dir() and _paths_overlap(source_path, output_path):
        raise MkxpBuildError(
            f"Output path must not overlap the source: source={source_path}, "
            f"output={output_path}"
        )
    if _paths_overlap(runtime_path, output_path):
        raise MkxpBuildError(
            f"Output path must not overlap the runtime: runtime={runtime_path}, "
            f"output={output_path}"
        )
    if output_path.exists() and not force:
        raise MkxpBuildError(
            f"Output already exists: {output_path}. Pass --force to replace it."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    staging = _staging_path(output_path)
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)

    warnings = list(inspection.warnings)
    if archive_type:
        warnings.insert(0, f"Built directly from {archive_type.upper()} input")
    warnings.append(
        f"{inspection.engine.value.upper()} is running through mkxp-z on Linux "
        "ARM64 rather than the original Windows RGSS player; test scripts, "
        "fonts, media, saves, and input."
    )

    try:
        shutil.copytree(
            runtime_path,
            staging,
            symlinks=True,
            ignore=_ignore_junk,
            ignore_dangling_symlinks=True,
        )
        game_destination = staging / "game"
        shutil.copytree(
            inspection.game_root,
            game_destination,
            symlinks=True,
            ignore=_ignore_junk,
            ignore_dangling_symlinks=True,
        )

        exec_name, rtps = _write_mkxp_config(
            staging / "mkxp.json",
            game_root=inspection.game_root,
            engine=inspection.engine,
        )
        if exec_name:
            warnings.append(f"Configured mkxp-z executable/archive stem: {exec_name}")
        if rtps:
            warnings.append(
                "Game declares RPG Maker RTP dependencies "
                f"({', '.join(rtps)}). Bundled assets may be sufficient, but "
                "missing RTP resources will need to be supplied explicitly."
            )
        if _has_wma(inspection.game_root):
            warnings.append(
                "Game contains WMA audio. mkxp-z documents WMA playback as "
                "unsupported; affected tracks may need transcoding."
            )

        executable = staging / "mkxp-z.aarch64"
        executable.chmod(executable.stat().st_mode | 0o755)
        launcher = _write_launcher(staging)
        _install_staging(staging, output_path, force=force)
    except MkxpBuildError:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise
    except Exception as exc:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise MkxpBuildError(f"mkxp-z build failed: {exc}") from exc

    return BuildResult(
        success=True,
        source_path=source_path,
        output_path=output_path,
        runtime_path=runtime_path,
        launcher_path=output_path / launcher.name,
        engine=inspection.engine,
        engine_version=inspection.engine_version,
        game_name=inspection.game_name,
        runtime_architecture=architecture,
        warnings=warnings,
    )
