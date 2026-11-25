import json
import shutil
from pathlib import Path

import pytest

from okf_profile_lint.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "bundle"


@pytest.fixture
def bundle(tmp_path):
    target = tmp_path / "bundle"
    shutil.copytree(FIXTURE, target)
    return target


def findings(bundle, capsys):
    code = main([str(bundle), "--json"])
    report = json.loads(capsys.readouterr().out)
    return code, {(f["path"], f["code"]) for f in report["findings"]}


def test_clean_bundle_passes(bundle, capsys):
    code, found = findings(bundle, capsys)
    assert code == 0
    assert found == set()


def test_planned_link_is_not_broken(bundle, capsys):
    _, found = findings(bundle, capsys)
    assert ("concepts/lot.md", "P008") not in found


def test_profile_rules(bundle, capsys):
    lot = bundle / "concepts" / "lot.md"
    lot.write_text(
        lot.read_text()
        .replace("status: draft", "status: wip\ngenerated: {by: \"human:x\", at: \"2026-11-25T00:00:00Z\"}")
        .replace("# Lot\n", "# Lots\n")
        .replace("(/concepts/serial.md)", "(/concepts/serials.md)")
        .replace("single unit", "single unit — one")
    )
    (bundle / "concepts" / "orphan.md").write_text(
        "---\ntype: Reference\ntitle: Orphan\ndescription: Not indexed.\nstatus: draft\n---\n\n# Orphan\n"
    )
    (bundle / "concepts" / "plain.md").write_text("# Plain\n")
    code, found = findings(bundle, capsys)
    assert code == 1
    assert {
        ("concepts/lot.md", "P001"),
        ("concepts/lot.md", "P005"),
        ("concepts/lot.md", "P006"),
        ("concepts/lot.md", "P007"),
        ("concepts/lot.md", "P008"),
        ("concepts/orphan.md", "P003"),
        ("concepts/orphan.md", "P010"),
        ("concepts/plain.md", "P002"),
    } <= found


def test_missing_required_field(bundle, capsys):
    serial = bundle / "concepts" / "serial.md"
    serial.write_text(serial.read_text().replace("description: The identity of a single unit.\n", ""))
    _, found = findings(bundle, capsys)
    assert ("concepts/serial.md", "P004") in found


def test_official_conformance_errors_are_reported(bundle, capsys):
    (bundle / "concepts" / "index.md").write_text("---\nfoo: 1\n---\n# Concepts\n")
    code, found = findings(bundle, capsys)
    assert code == 1
    assert ("concepts/index.md", "E004") in found


def test_without_profile_only_conformance_applies(bundle, capsys):
    (bundle / "okf-profile.yaml").unlink()
    (bundle / "concepts" / "plain.md").write_text("# Plain\n")
    code, found = findings(bundle, capsys)
    assert code == 0
    assert not any(code.startswith("P") for _, code in found)
    assert ("README.md", "W120") in found


def test_ignored_paths_are_skipped(bundle, capsys):
    (bundle / "build").mkdir()
    (bundle / "build" / "book.md").write_text("# Book\n")
    profile = bundle / "okf-profile.yaml"
    profile.write_text("ignore: [\"build/**\"]\n" + profile.read_text())
    code, found = findings(bundle, capsys)
    assert code == 0
    assert not any(path.startswith("build/") for path, _ in found)
