"""CloudSaver command line entry point."""

import argparse
import os
import sys
from pathlib import Path

from cloudsaver import demo, report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cloudsaver",
        description="Explainable cloud savings candidates (offline demo available)",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    demo_parser = commands.add_parser("demo", help="Use bundled fictional data without AWS")
    demo_commands = demo_parser.add_subparsers(dest="demo_command", required=True)
    scan_parser = demo_commands.add_parser("scan", help="Analyze bundled fictional resources")
    scan_parser.add_argument("--format", choices=("table", "json"), default="table")
    scan_parser.add_argument(
        "--output", type=Path, metavar="PATH", help="write output to a new file"
    )
    return parser


def _write_new_file(path: Path, content: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "demo" and args.demo_command == "scan":
        try:
            observed_at, findings = demo.scan()
            content = (
                report.render_json(observed_at, findings)
                if args.format == "json"
                else report.render_table(observed_at, findings)
            )
            if args.output is None:
                sys.stdout.write(content)
            else:
                _write_new_file(args.output, content)
        except FileExistsError:
            print("Output file already exists; choose a new path.", file=sys.stderr)
            return 2
        except OSError:
            print("Could not write output file.", file=sys.stderr)
            return 2
        except ValueError:
            print("Bundled demo data is invalid.", file=sys.stderr)
            return 70
        return 0
    return 2
