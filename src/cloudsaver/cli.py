"""CloudSaver command line entry point."""

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from cloudsaver import demo, report
from cloudsaver.policies import evaluate_all


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
    aws_parser = commands.add_parser("scan", help="Discover AWS resources with read-only APIs")
    aws_parser.add_argument("--regions", required=True, help="comma-separated AWS regions")
    aws_parser.add_argument(
        "--profile", help="AWS profile; otherwise use the standard credential chain"
    )
    aws_parser.add_argument("--format", choices=("table", "json"), default="table")
    aws_parser.add_argument(
        "--output", type=Path, metavar="PATH", help="write output to a new file"
    )
    custodian_parser = commands.add_parser(
        "custodian", help="Validate or evaluate safe Custodian policies"
    )
    custodian_commands = custodian_parser.add_subparsers(dest="custodian_command", required=True)
    for name in ("validate", "evaluate"):
        policy_parser = custodian_commands.add_parser(name)
        policy_parser.add_argument("--policy", required=True, type=Path, metavar="POLICY.yml")
        policy_parser.add_argument("--format", choices=("table", "json"), default="table")
        policy_parser.add_argument("--output", type=Path, metavar="PATH")
        if name == "evaluate":
            policy_parser.add_argument("--region", required=True)
            policy_parser.add_argument("--assume-role", required=True, metavar="ROLE_ARN")
            policy_parser.add_argument("--profile")
    for name, help_text in (
        ("opportunities", "List candidates in a saved report"),
        ("explain", "Explain one finding in a saved report"),
        ("report", "Render a saved report"),
    ):
        saved_parser = commands.add_parser(name, help=help_text)
        if name == "explain":
            saved_parser.add_argument("finding_id")
        saved_parser.add_argument("--input", required=True, type=Path, metavar="REPORT.json")
        saved_parser.add_argument(
            "--cost-input",
            type=Path,
            metavar="COSTS.json",
            help="optional user-supplied monthly cost components",
        )
        saved_parser.add_argument("--format", choices=("table", "json"), default="table")
        saved_parser.add_argument(
            "--output", type=Path, metavar="PATH", help="write output to a new file"
        )
    dashboard_parser = commands.add_parser(
        "dashboard", help="Create a read-only HTML dashboard from a saved report"
    )
    dashboard_parser.add_argument("--input", required=True, type=Path, metavar="REPORT.json")
    dashboard_parser.add_argument("--cost-input", type=Path, metavar="COSTS.json")
    dashboard_parser.add_argument("--output", required=True, type=Path, metavar="DASHBOARD.html")
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
    if args.command == "dashboard":
        from cloudsaver.costs import apply_scenarios
        from cloudsaver.dashboard import render_dashboard
        from cloudsaver.stored import read_report

        try:
            saved = read_report(args.input)
            if args.cost_input is not None:
                raw_costs = json.loads(args.cost_input.read_text(encoding="utf-8"))
                if not isinstance(raw_costs, dict):
                    raise ValueError("invalid cost input")
                saved = apply_scenarios(saved, raw_costs)
            _write_new_file(args.output, render_dashboard(saved))
        except (ValueError, UnicodeError, json.JSONDecodeError):
            print("Invalid report or cost input.", file=sys.stderr)
            return 2
        except FileExistsError:
            print("Output file already exists; choose a new path.", file=sys.stderr)
            return 2
        except OSError:
            print("Could not read input or write dashboard file.", file=sys.stderr)
            return 2
        return 0
    if args.command == "custodian":
        from cloudsaver.custodian import CustodianFailure, CustodianUnavailable, run

        evaluate = args.custodian_command == "evaluate"
        try:
            result = run(
                args.policy,
                evaluate=evaluate,
                region=args.region if evaluate else None,
                assume_role=args.assume_role if evaluate else None,
                profile=args.profile if evaluate else None,
            )
            if args.format == "json":
                content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
            else:
                lines = [f"Custodian {result['evaluation_status']} (validation: VALID)"]
                for item in result["policy_results"]:
                    line = f"{item['name']} | {item['resource']}"
                    if evaluate:
                        line += f" | matched: {item['matched_count']}"
                        if item["resource_refs"]:
                            line += " | " + ", ".join(item["resource_refs"])
                    lines.append(line)
                content = "\n".join(lines) + "\n"
            if args.output is None:
                sys.stdout.write(content)
            else:
                _write_new_file(args.output, content)
        except (ValueError, UnicodeError):
            print("Invalid or unsafe Custodian policy or evaluation options.", file=sys.stderr)
            return 2
        except CustodianUnavailable as error:
            print(str(error), file=sys.stderr)
            return 2
        except CustodianFailure as error:
            print(str(error), file=sys.stderr)
            return 5
        except FileExistsError:
            print("Output file already exists; choose a new path.", file=sys.stderr)
            return 2
        except OSError:
            print("Could not read policy or write output file.", file=sys.stderr)
            return 2
        return 0
    if args.command in {"opportunities", "explain", "report"}:
        from cloudsaver.costs import apply_scenarios
        from cloudsaver.stored import read_report

        try:
            saved = read_report(args.input)
            if args.cost_input is not None:
                raw_costs = json.loads(args.cost_input.read_text(encoding="utf-8"))
                if not isinstance(raw_costs, dict):
                    raise ValueError("invalid cost input")
                saved = apply_scenarios(saved, raw_costs)
            finding_id = args.finding_id if args.command == "explain" else None
            content = (
                report.render_saved_json(saved, args.command, finding_id)
                if args.format == "json"
                else report.render_saved_table(saved, args.command, finding_id)
            )
            if args.output is None:
                sys.stdout.write(content)
            else:
                _write_new_file(args.output, content)
        except (ValueError, UnicodeError, json.JSONDecodeError):
            print("Invalid report, cost input, or finding ID.", file=sys.stderr)
            return 2
        except FileExistsError:
            print("Output file already exists; choose a new path.", file=sys.stderr)
            return 2
        except OSError:
            print("Could not read input or write output file.", file=sys.stderr)
            return 2
        return 0
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
    if args.command == "scan":
        try:
            from botocore.exceptions import (
                BotoCoreError,
                NoCredentialsError,
                PartialCredentialsError,
                ProfileNotFound,
            )

            from cloudsaver.providers.aws import collect, new_session, validate_regions
        except ImportError:
            print("AWS support is not installed. Install cloudsaver[aws].", file=sys.stderr)
            return 2
        try:
            regions = validate_regions(args.regions.split(","))
            session = new_session(args.profile, regions)
            inventory = collect(session, regions, datetime.now(UTC))
            findings = evaluate_all(inventory.resources, provider="aws")
            content = (
                report.render_inventory_json(inventory, findings)
                if args.format == "json"
                else report.render_inventory_table(inventory, findings)
            )
            if args.output is None:
                sys.stdout.write(content)
            else:
                _write_new_file(args.output, content)
            return inventory.exit_code
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 2
        except (NoCredentialsError, PartialCredentialsError, ProfileNotFound):
            print("AWS credentials or profile are unavailable.", file=sys.stderr)
            return 3
        except FileExistsError:
            print("Output file already exists; choose a new path.", file=sys.stderr)
            return 2
        except OSError:
            print("Could not write output file.", file=sys.stderr)
            return 2
        except BotoCoreError:
            print("Could not initialize AWS session.", file=sys.stderr)
            return 5
    return 2
