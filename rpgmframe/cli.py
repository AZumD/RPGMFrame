"""Command-line entry point for RPGMFrame."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rpgmframe.builder import BuildError, build_game
from rpgmframe.detector import inspect_game


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rpgmframe",
        description="Inspect and convert RPG Maker games for Linux ARM64.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Detect the RPG Maker engine used by a game directory.",
    )
    inspect_parser.add_argument("path", type=Path)
    inspect_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the inspection result as JSON.",
    )

    build_parser = subparsers.add_parser(
        "build",
        help="Build a Linux ARM64 package using a supplied NW.js runtime.",
    )
    build_parser.add_argument("path", type=Path, help="RPG Maker game directory")
    build_parser.add_argument(
        "--runtime",
        required=True,
        type=Path,
        help="Extracted Linux ARM64 NW.js runtime directory",
    )
    build_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output directory (default: <source>-frame)",
    )
    build_parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing output directory",
    )

    return parser


def _print_inspection(result) -> None:
    print(f"Source:        {result.source_path}")
    print(f"Engine:        {result.engine.value}")
    print(f"Runtime:       {result.runtime or 'unknown'}")
    print(f"Confidence:    {result.confidence.value}")
    print(f"Compatibility: {result.compatibility.value}")
    if result.game_root:
        print(f"Game root:     {result.game_root}")
    if result.game_name:
        print(f"Game name:     {result.game_name}")
    if result.engine_version:
        print(f"Engine version: {result.engine_version}")
    if result.package_json:
        print(f"package.json:  {result.package_json}")

    if result.evidence:
        print("Evidence:")
        for item in result.evidence:
            print(f"  - {item}")

    if result.warnings:
        print("Warnings:")
        for item in result.warnings:
            print(f"  - {item}")


def _print_build(result) -> None:
    print(f"Built:         {result.output_path}")
    print(f"Engine:        {result.engine.value}")
    if result.engine_version:
        print(f"Engine version: {result.engine_version}")
    print(f"Runtime arch:  {result.runtime_architecture}")
    print(f"Launcher:      {result.launcher_path}")
    if result.game_name:
        print(f"Game name:     {result.game_name}")
    if result.warnings:
        print("Warnings:")
        for item in result.warnings:
            print(f"  - {item}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "inspect":
        result = inspect_game(args.path)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        else:
            _print_inspection(result)
        return 0 if result.recognized else 2

    if args.command == "build":
        try:
            result = build_game(
                args.path,
                runtime=args.runtime,
                output=args.output,
                force=args.force,
            )
        except BuildError as exc:
            print(f"error: {exc}")
            return 2
        _print_build(result)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
