"""Command line: ``okf-profile-lint``."""

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, profile as profile_rules
from .vendor import okf_validate

# Official findings that a profile rule replaces with a stricter one.
SUPERSEDED = {
    "W115": "broken_links",  # link target not in the bundle
}
NOT_A_CONCEPT = "W120"


def official_findings(root, profile):
    checker = okf_validate.Checker(root, datetime.now(timezone.utc))
    checker.run()
    findings = []
    for finding in checker.findings:
        rel = Path(finding.path)
        if finding.path != "." and (
            any(part.startswith(".") for part in rel.parts) or profile.is_ignored(rel)
        ):
            continue
        if finding.code == NOT_A_CONCEPT and profile.is_non_concept(rel):
            continue
        rule = SUPERSEDED.get(finding.code)
        if rule and getattr(profile, rule):
            continue
        findings.append(profile_rules.Finding(
            finding.path, finding.line, finding.level, finding.code, finding.message,
        ))
    return findings


def run_check(args):
    root = Path(args.bundle).resolve()
    if not root.is_dir():
        print(f"okf-profile-lint: {args.bundle} is not a directory", file=sys.stderr)
        return 2
    profile = profile_rules.Profile.load(root)
    findings = official_findings(root, profile) + profile_rules.check(root, profile)
    findings.sort(key=lambda f: (f.path, f.line or 0, f.code))
    counts = {level: sum(f.level == level for f in findings) for level in ("error", "warning", "info")}
    if args.json:
        print(json.dumps({"bundle": str(root), **counts, "findings": [asdict(f) for f in findings]}, indent=2))
    else:
        for f in findings:
            location = f"{f.path}:{f.line}" if f.line else f.path
            print(f"{location}: {f.level} {f.code} {f.message}")
        print(f"{counts['error']} errors, {counts['warning']} warnings, {counts['info']} info")
    if counts["error"] or (args.strict and counts["warning"]):
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="okf-profile-lint",
        description="Check an OKF bundle for conformance and for the rules in its okf-profile.yaml.",
    )
    parser.add_argument("--version", action="version", version=f"okf-profile-lint {__version__}")
    parser.add_argument("bundle", nargs="?", default=".", help="bundle root (default: current directory)")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    parser.add_argument("--strict", action="store_true", help="exit 1 when there are warnings")
    return run_check(parser.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
