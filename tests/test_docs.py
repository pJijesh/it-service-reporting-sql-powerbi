"""Documentation hygiene: house style, links that resolve, and README structure."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {"__pycache__", ".pytest_cache", "build", ".git", ".venv"}
TEXT_SUFFIXES = {".md", ".py", ".sql", ".dax", ".pq", ".mmd", ".csv", ".yml", ".ini", ".txt", ".svg", ""}

# The two long dash characters are written as code points so that this file does not contain them.
LONG_DASHES = (chr(0x2014), chr(0x2013))


def repo_files(suffixes=None):
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if suffixes is None or path.suffix in suffixes:
            yield path


def markdown_files():
    return list(repo_files({".md"}))


def test_no_long_dashes_anywhere_in_the_repository():
    offenders = []
    for path in repo_files(TEXT_SUFFIXES):
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(d in text for d in LONG_DASHES):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)\)|!\[[^\]]*\]\(([^)\s]+)\)")


def local_targets(text):
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", "", text)
    for match in LINK.finditer(text):
        target = match.group(1) or match.group(2)
        if re.match(r"^(https?:|mailto:|#)", target):
            continue
        yield target.split("#")[0]


@pytest.mark.parametrize("path", markdown_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_relative_links_resolve(path):
    missing = []
    for target in local_targets(path.read_text(encoding="utf-8")):
        if target and not (path.parent / target).resolve().exists():
            missing.append(target)
    assert missing == []


def test_every_guidance_note_is_linked_from_the_docs_index():
    index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    for note in sorted((ROOT / "docs").glob("*.md")):
        if note.name != "README.md":
            assert note.name in index, note.name


def test_readme_follows_the_house_structure():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    lines = text.split("\n")
    assert lines[0].startswith("# ")
    assert "badge.svg" in lines[2] and "licence-MIT" in lines[2] and "dependencies-none" in lines[2]
    positions = [text.index(marker) for marker in
                 ("**Problem:**", "**For:**", "**Demonstrates:**", "## Quick start", "## How it is built",
                  "## Design choices", "## Limitations", "## Verification status", "## Licence",
                  "Built by Puliyappottammal Jijesh")]
    assert positions == sorted(positions)
    for marker in ("**Problem:**", "**For:**", "**Demonstrates:**"):
        line = next(l for l in lines if l.startswith(marker))
        assert line.strip() != marker


def test_readme_says_the_data_is_fictional_and_that_power_bi_was_not_run():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "All data is fictional" in text
    assert "No `.pbix` is included" in text
    assert "not run" in text.lower()


def test_repository_has_the_standard_files():
    for name in ("README.md", "LICENSE", "CONTRIBUTING.md", ".gitignore", ".github/workflows/test.yml"):
        assert (ROOT / name).is_file(), name
    assert "2026 Puliyappottammal Jijesh" in (ROOT / "LICENSE").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
    for version in ('"3.10"', '"3.11"', '"3.12"', '"3.13"'):
        assert version in workflow
    assert "pull_request" in workflow and "push" in workflow


def test_rendered_diagrams_are_committed_next_to_their_sources():
    for source in ("docs/images/pipeline", "powerbi/data-model"):
        assert (ROOT / (source + ".mmd")).is_file()
        assert (ROOT / (source + ".svg")).is_file()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/images/pipeline.svg" in readme and "powerbi/data-model.svg" in readme


def test_itil_is_acknowledged_as_a_trademark():
    for name in ("docs/README.md", "README.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "ITIL is a registered trademark" in text
