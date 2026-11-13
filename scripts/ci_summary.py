"""Render test and coverage results as a Markdown summary for GitHub Actions.

Reads the JUnit and Cobertura XML files that CI produces and prints Markdown, so the
workflow can append it to the run's summary page:

    python scripts/ci_summary.py >> "$GITHUB_STEP_SUMMARY"
"""

import argparse
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_FAILURES = 10
MAX_COVERAGE_ROWS = 15


def ranges(numbers):
    """Compress line numbers: [25, 26, 27, 40] -> '25-27, 40'."""
    parts = []
    start = previous = None
    for number in sorted(set(numbers)):
        if start is None:
            start = previous = number
        elif number == previous + 1:
            previous = number
        else:
            parts.append((start, previous))
            start = previous = number
    if start is not None:
        parts.append((start, previous))
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in parts)


def read_tests(path):
    """Return counts and failures for a JUnit file, None if missing, 'unreadable' if broken."""
    if not path.is_file():
        return None
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return "unreadable"

    result = {"passed": 0, "failed": 0, "skipped": 0, "seconds": 0.0, "failures": []}
    for case in root.iter("testcase"):
        result["seconds"] += float(case.get("time") or 0)
        problem = next((child for child in case if child.tag in ("failure", "error")), None)
        if problem is not None:
            result["failed"] += 1
            # Node's JUnit reporter files every case under the class "test".
            module = (case.get("classname") or "").rsplit(".", 1)[-1]
            name = case.get("name") or "(unnamed)"
            label = f"{module}::{name}" if module and module != "test" else name
            lines = (problem.get("message") or problem.text or "").strip().splitlines()
            result["failures"].append((label, lines[0][:160] if lines else ""))
        elif case.find("skipped") is not None:
            result["skipped"] += 1
        else:
            result["passed"] += 1
    return result


def read_coverage(path):
    """Return totals and per-file gaps from a Cobertura file, None if missing or broken."""
    if not path.is_file():
        return None
    try:
        root = ET.parse(path).getroot()
        lines_valid = int(root.get("lines-valid"))
        branches_valid = int(root.get("branches-valid", 0))
        covered = int(root.get("lines-covered")) + int(root.get("branches-covered", 0))
        # Lines and branches combined, the same figure `coverage report` enforces.
        valid = lines_valid + branches_valid
        files = []
        for cls in root.iter("class"):
            line_rate = float(cls.get("line-rate", 1))
            branch_rate = float(cls.get("branch-rate", 1))
            if line_rate >= 1 and branch_rate >= 1:
                continue
            gaps = []
            for line in cls.iter("line"):
                partial = line.get("branch") == "true" and not (
                    line.get("condition-coverage", "").startswith("100%")
                )
                if line.get("hits") == "0" or partial:
                    gaps.append(int(line.get("number")))
            files.append((cls.get("filename", "?"), line_rate, branch_rate, ranges(gaps)))
    except ET.ParseError, TypeError, ValueError:
        return None
    files.sort(key=lambda item: (item[1], item[2], item[0]))
    return {"percent": 100 * covered / valid if valid else 100.0, "files": files}


def read_threshold(path):
    try:
        with open(path, "rb") as handle:
            return tomllib.load(handle)["tool"]["coverage"]["report"]["fail_under"]
    except OSError, KeyError, tomllib.TOMLDecodeError:
        return None


def percent(rate):
    return f"{100 * rate:.1f}%"


def test_rows(suites):
    rows = [
        "| Suite | Result | Passed | Failed | Skipped | Time |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for name, result in suites:
        if result is None:
            rows.append(f"| {name} | ⚪ not run | – | – | – | – |")
        elif result == "unreadable":
            rows.append(f"| {name} | ❓ report unreadable | – | – | – | – |")
        else:
            total = result["passed"] + result["failed"] + result["skipped"]
            if result["failed"]:
                status = "❌ failed"
            elif total == 0:
                status = "⚠️ no tests ran"
            else:
                status = "✅ passed"
            rows.append(
                f"| {name} | {status} | {result['passed']} | {result['failed']} "
                f"| {result['skipped']} | {result['seconds']:.1f}s |"
            )
    return rows


def failure_lines(suites):
    lines = []
    for name, result in suites:
        if not isinstance(result, dict) or not result["failures"]:
            continue
        lines += ["", f"### Failed {name} tests", ""]
        for label, message in result["failures"][:MAX_FAILURES]:
            detail = f" — {message}" if message else ""
            lines.append(f"- `{label.replace('`', chr(39))}`{detail}")
        extra = len(result["failures"]) - MAX_FAILURES
        if extra > 0:
            lines.append(f"- …and {extra} more (see the job log)")
    return lines


def coverage_lines(coverage, threshold):
    if coverage is None:
        return ["_No coverage report was produced._"]
    headline = f"**{coverage['percent']:.2f}%** total (lines and branches)"
    if threshold is not None:
        ok = coverage["percent"] >= threshold
        verdict = (
            f"✅ meets the {threshold}% minimum" if ok else f"❌ below the {threshold}% minimum"
        )
        headline += f" — {verdict}"
    lines = [headline]
    files = coverage["files"]
    if files:
        lines += [
            "",
            "Files not fully covered:",
            "",
            "| File | Lines | Branches | Needs coverage |",
            "|---|---:|---:|---|",
        ]
        for filename, line_rate, branch_rate, gaps in files[:MAX_COVERAGE_ROWS]:
            short = filename.removeprefix("src/")
            lines.append(
                f"| `{short}` | {percent(line_rate)} | {percent(branch_rate)} | {gaps or '–'} |"
            )
        if len(files) > MAX_COVERAGE_ROWS:
            lines.append(f"\n…and {len(files) - MAX_COVERAGE_ROWS} more files.")
    return lines


def render(python, javascript, coverage, threshold):
    suites = [("Python", python), ("JavaScript", javascript)]
    lines = ["## Test results", "", *test_rows(suites), *failure_lines(suites)]
    lines += ["", "## Coverage", "", *coverage_lines(coverage, threshold), ""]
    return "\n".join(lines)


def main(argv=None, out=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--python", type=Path, default=Path(".reports/python-junit.xml"))
    parser.add_argument("--javascript", type=Path, default=Path(".reports/js-junit.xml"))
    parser.add_argument("--coverage", type=Path, default=Path(".reports/coverage.xml"))
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    args = parser.parse_args(argv)
    markdown = render(
        read_tests(args.python),
        read_tests(args.javascript),
        read_coverage(args.coverage),
        read_threshold(args.pyproject),
    )
    print(markdown, file=out or sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
