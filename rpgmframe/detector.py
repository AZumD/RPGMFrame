"""Conservative RPG Maker MV/MZ directory detection."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rpgmframe.models import (
    Compatibility,
    Confidence,
    EngineVariant,
    GameInspection,
)

_VERSION_RE = re.compile(
    r"""RPGMAKER_VERSION\s*=\s*["'](?P<version>[^"']+)["']""",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _Candidate:
    engine: EngineVariant
    game_root: Path
    core_file: Path
    score: int
    evidence: tuple[str, ...]


def _normalize_path(path: Path | str) -> Path:
    return Path(path).expanduser().resolve()


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _read_text_head(path: Path, limit: int = 131072) -> str | None:
    try:
        data = path.read_bytes()[:limit]
    except OSError:
        return None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _score_candidate(
    source_root: Path,
    *,
    engine: EngineVariant,
    game_root: Path,
    core_name: str,
) -> _Candidate | None:
    core = game_root / "js" / core_name
    if not core.is_file():
        return None

    evidence: list[str] = [_relative(core, source_root)]
    score = 6

    system_json = game_root / "data" / "System.json"
    if system_json.is_file():
        score += 3
        evidence.append(_relative(system_json, source_root))

    index_html = game_root / "index.html"
    if index_html.is_file():
        score += 1
        evidence.append(_relative(index_html, source_root))

    package_candidates = (source_root / "package.json", game_root / "package.json")
    package = next((p for p in package_candidates if p.is_file()), None)
    if package is not None:
        score += 1
        evidence.append(_relative(package, source_root))

    return _Candidate(
        engine=engine,
        game_root=game_root,
        core_file=core,
        score=score,
        evidence=tuple(dict.fromkeys(evidence)),
    )


def _collect_candidates(root: Path) -> list[_Candidate]:
    candidates: list[_Candidate] = []

    # Normal Windows MV deployment: <root>/www/js/rpg_core.js.
    mv_www = _score_candidate(
        root,
        engine=EngineVariant.MV,
        game_root=root / "www",
        core_name="rpg_core.js",
    )
    if mv_www:
        candidates.append(mv_www)

    # Web exports, already-normalized layouts, and manually selected payload roots.
    mv_root = _score_candidate(
        root,
        engine=EngineVariant.MV,
        game_root=root,
        core_name="rpg_core.js",
    )
    if mv_root:
        candidates.append(mv_root)

    # Normal MZ deployment is rooted directly beside package.json.
    mz_root = _score_candidate(
        root,
        engine=EngineVariant.MZ,
        game_root=root,
        core_name="rmmz_core.js",
    )
    if mz_root:
        candidates.append(mz_root)

    # Also accept an MZ payload that has already been nested under www/.
    mz_www = _score_candidate(
        root,
        engine=EngineVariant.MZ,
        game_root=root / "www",
        core_name="rmmz_core.js",
    )
    if mz_www:
        candidates.append(mz_www)

    return candidates


def _find_package_json(source_root: Path, game_root: Path) -> Path | None:
    for candidate in (source_root / "package.json", game_root / "package.json"):
        if candidate.is_file():
            return candidate
    return None


def _detect_game_name(game_root: Path, package_json: Path | None) -> str | None:
    system = _read_json(game_root / "data" / "System.json")
    if system:
        title = system.get("gameTitle")
        if isinstance(title, str) and title.strip():
            return title.strip()

    if package_json:
        package = _read_json(package_json)
        if package:
            window = package.get("window")
            if isinstance(window, dict):
                title = window.get("title")
                if isinstance(title, str) and title.strip():
                    return title.strip()
            name = package.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()

    return None


def _detect_engine_version(core_file: Path) -> str | None:
    text = _read_text_head(core_file)
    if not text:
        return None
    match = _VERSION_RE.search(text)
    return match.group("version").strip() if match else None


def _confidence_for_score(score: int) -> Confidence:
    if score >= 9:
        return Confidence.HIGH
    if score >= 7:
        return Confidence.MEDIUM
    return Confidence.LOW


def inspect_game(path: Path | str) -> GameInspection:
    """
    Detect RPG Maker MV/MZ using engine-specific JavaScript runtime files.

    Generic markers such as package.json are never sufficient on their own.
    """
    root = _normalize_path(path)

    if not root.exists():
        return GameInspection(
            source_path=root,
            warnings=[f"Path does not exist: {root}"],
        )
    if not root.is_dir():
        return GameInspection(
            source_path=root,
            warnings=[f"Path is not a directory: {root}"],
        )

    candidates = _collect_candidates(root)
    if not candidates:
        return GameInspection(
            source_path=root,
            warnings=[
                "No RPG Maker MV/MZ engine core was found "
                "(expected rpg_core.js or rmmz_core.js)."
            ],
        )

    candidates.sort(key=lambda candidate: candidate.score, reverse=True)
    best = candidates[0]

    if len(candidates) > 1:
        runner_up = candidates[1]
        if runner_up.score == best.score and runner_up.engine is not best.engine:
            evidence = list(dict.fromkeys(best.evidence + runner_up.evidence))
            return GameInspection(
                source_path=root,
                evidence=evidence,
                warnings=[
                    "Conflicting MV and MZ engine signatures have equal confidence; "
                    "refusing to guess."
                ],
            )

    package_json = _find_package_json(root, best.game_root)
    warnings: list[str] = []
    if not (best.game_root / "data" / "System.json").is_file():
        warnings.append(
            "Engine core found, but data/System.json is missing; "
            "this may be an incomplete game directory."
        )

    return GameInspection(
        source_path=root,
        engine=best.engine,
        runtime="nwjs",
        confidence=_confidence_for_score(best.score),
        game_root=best.game_root,
        game_name=_detect_game_name(best.game_root, package_json) or root.name,
        engine_version=_detect_engine_version(best.core_file),
        package_json=package_json,
        evidence=list(best.evidence),
        warnings=warnings,
        compatibility=Compatibility.SUPPORTED,
    )
