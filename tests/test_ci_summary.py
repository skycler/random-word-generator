import importlib.util
import io
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "ci_summary.py"
spec = importlib.util.spec_from_file_location("ci_summary", SCRIPT)
ci_summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci_summary)


def junit(cases):
    """cases: (classname, name, outcome, message); outcome is pass/fail/error/skip."""
    body = ""
    for classname, name, outcome, message in cases:
        inner = {
            "pass": "",
            "skip": "<skipped/>",
            "fail": f'<failure message="{message}">trace</failure>',
            "error": f'<error message="{message}">trace</error>',
        }[outcome]
        body += f'<testcase classname="{classname}" name="{name}" time="0.5">{inner}</testcase>'
    return f"<testsuites><testsuite>{body}</testsuite></testsuites>"


def cobertura(lines_valid, lines_covered, branches_valid, branches_covered, classes=""):
    return (
        f'<coverage lines-valid="{lines_valid}" lines-covered="{lines_covered}" '
        f'branches-valid="{branches_valid}" branches-covered="{branches_covered}">'
        f"<packages><package><classes>{classes}</classes></package></packages></coverage>"
    )


def cls(filename, line_rate, branch_rate, lines=""):
    return (
        f'<class filename="{filename}" line-rate="{line_rate}" branch-rate="{branch_rate}">'
        f"<lines>{lines}</lines></class>"
    )


def run(tmp_path, python=None, javascript=None, coverage=None, pyproject=None):
    paths = {}
    for key, content in (("python", python), ("javascript", javascript), ("coverage", coverage)):
        path = tmp_path / f"{key}.xml"
        if content is not None:
            path.write_text(content)
        paths[key] = path
    toml = tmp_path / "pyproject.toml"
    if pyproject is not None:
        toml.write_text(pyproject)
    out = io.StringIO()
    argv = [f"--{key}={path}" for key, path in paths.items()] + [f"--pyproject={toml}"]
    assert ci_summary.main(argv, out) == 0
    return out.getvalue()


THRESHOLD = "[tool.coverage.report]\nfail_under = 90\n"


@pytest.mark.parametrize(
    "numbers, expected",
    [
        ([], ""),
        ([5], "5"),
        ([25, 26, 27, 40], "25-27, 40"),
        ([3, 1, 2, 2, 9, 11, 10], "1-3, 9-11"),
    ],
)
def test_ranges_compress_consecutive_line_numbers(numbers, expected):
    assert ci_summary.ranges(numbers) == expected


def test_passing_suites_show_counts_and_status(tmp_path):
    cases = [("tests.test_a", f"t{i}", "pass", "") for i in range(3)] + [
        ("tests.test_a", "slow", "skip", "")
    ]
    text = run(tmp_path, python=junit(cases), javascript=junit(cases[:2]))
    assert "| Python | ✅ passed | 3 | 0 | 1 | 2.0s |" in text
    assert "| JavaScript | ✅ passed | 2 | 0 | 0 | 1.0s |" in text
    assert "### Failed" not in text


def test_failures_and_errors_are_listed_with_their_first_message_line(tmp_path):
    cases = [
        ("tests.test_nav", "test_ok", "pass", ""),
        ("tests.test_nav", "test_bad", "fail", "assert 1 == 2&#10;second line"),
        ("tests.test_view", "test_boom", "error", "ValueError: nope"),
    ]
    text = run(tmp_path, python=junit(cases))
    assert "| Python | ❌ failed | 1 | 2 | 0 |" in text
    assert "### Failed Python tests" in text
    assert "- `test_nav::test_bad` — assert 1 == 2" in text
    assert "second line" not in text
    assert "- `test_view::test_boom` — ValueError: nope" in text


def test_javascript_failures_use_the_bare_test_name(tmp_path):
    cases = [("test", "falls back after a server error", "fail", "expected true")]
    text = run(tmp_path, javascript=junit(cases))
    assert "### Failed JavaScript tests" in text
    assert "- `falls back after a server error` — expected true" in text
    assert "test::" not in text


def test_long_failure_lists_are_capped(tmp_path):
    cases = [("tests.test_x", f"t{i}", "fail", "x") for i in range(14)]
    text = run(tmp_path, python=junit(cases))
    assert text.count("- `test_x::t") == 10
    assert "…and 4 more (see the job log)" in text


def test_a_missing_report_is_marked_not_run_without_failing(tmp_path):
    text = run(tmp_path, python=junit([("tests.t", "a", "pass", "")]))
    assert "| JavaScript | ⚪ not run | – | – | – | – |" in text
    assert "_No coverage report was produced._" in text


def test_with_no_reports_at_all_it_still_renders(tmp_path):
    text = run(tmp_path)
    assert text.count("⚪ not run") == 2
    assert "_No coverage report was produced._" in text


def test_a_broken_report_is_flagged_instead_of_crashing(tmp_path):
    text = run(tmp_path, python="<not xml", coverage="<also broken", pyproject=THRESHOLD)
    assert "| Python | ❓ report unreadable | – | – | – | – |" in text
    assert "_No coverage report was produced._" in text


def test_a_suite_with_no_tests_is_a_warning_not_a_pass(tmp_path):
    text = run(tmp_path, python="<testsuites/>")
    assert "| Python | ⚠️ no tests ran |" in text


def test_total_coverage_combines_lines_and_branches_like_coverage_py(tmp_path):
    # 312 of 324 lines and 58 of 62 branches: (312 + 58) / (324 + 62) = 95.85%
    text = run(tmp_path, coverage=cobertura(324, 312, 62, 58), pyproject=THRESHOLD)
    assert "**95.85%** total (lines and branches) — ✅ meets the 90% minimum" in text


def test_coverage_below_the_threshold_is_called_out(tmp_path):
    text = run(tmp_path, coverage=cobertura(100, 80, 0, 0), pyproject=THRESHOLD)
    assert "**80.00%** total" in text
    assert "❌ below the 90% minimum" in text


def test_threshold_is_omitted_when_not_configured(tmp_path):
    text = run(tmp_path, coverage=cobertura(100, 100, 0, 0))
    assert "**100.00%** total (lines and branches)" in text
    assert "minimum" not in text


def test_coverage_without_branches_does_not_divide_by_zero(tmp_path):
    root = '<coverage lines-valid="0" lines-covered="0"><packages/></coverage>'
    assert "**100.00%** total" in run(tmp_path, coverage=root)


def test_gaps_list_missing_lines_and_partial_branches_worst_file_first(tmp_path):
    lines = (
        '<line number="4" hits="0"/><line number="5" hits="0"/><line number="6" hits="1"/>'
        '<line number="9" hits="1" branch="true" condition-coverage="50% (1/2)"/>'
        '<line number="12" hits="1" branch="true" condition-coverage="100% (2/2)"/>'
    )
    classes = (
        cls("src/pkg/good.py", 1, 1, '<line number="1" hits="1"/>')
        + cls("src/pkg/mild.py", 0.9, 1, '<line number="2" hits="0"/>')
        + cls("src/pkg/bad.py", 0.5, 0.5, lines)
    )
    text = run(tmp_path, coverage=cobertura(10, 8, 4, 3, classes))
    assert "good.py" not in text, "fully covered files are not listed"
    assert "| `pkg/bad.py` | 50.0% | 50.0% | 4-5, 9 |" in text
    assert "| `pkg/mild.py` | 90.0% | 100.0% | 2 |" in text
    assert text.index("bad.py") < text.index("mild.py")


def test_long_file_lists_are_capped(tmp_path):
    classes = "".join(cls(f"src/pkg/f{i:02}.py", 0.5, 1) for i in range(20))
    text = run(tmp_path, coverage=cobertura(10, 5, 0, 0, classes))
    assert text.count("| `pkg/f") == 15
    assert "…and 5 more files." in text


def test_default_paths_are_the_ones_the_workflow_writes(tmp_path, monkeypatch, capsys):
    workflow = (SCRIPT.parent.parent / ".github" / "workflows" / "tests.yml").read_text()
    for path in (".reports/python-junit.xml", ".reports/js-junit.xml", ".reports/coverage.xml"):
        assert path in workflow

    reports = tmp_path / ".reports"
    reports.mkdir()
    (reports / "python-junit.xml").write_text(junit([("tests.t", "a", "pass", "")]))
    (reports / "js-junit.xml").write_text(junit([("test", "b", "pass", "")]))
    (reports / "coverage.xml").write_text(cobertura(10, 10, 0, 0))
    (tmp_path / "pyproject.toml").write_text(THRESHOLD)
    monkeypatch.chdir(tmp_path)
    assert ci_summary.main([]) == 0
    printed = capsys.readouterr().out
    assert "| Python | ✅ passed | 1 |" in printed
    assert "| JavaScript | ✅ passed | 1 |" in printed
    assert "**100.00%** total" in printed and "meets the 90% minimum" in printed


def test_it_summarises_the_real_pyproject_threshold():
    pyproject = SCRIPT.parent.parent / "pyproject.toml"
    assert ci_summary.read_threshold(pyproject) == 90
    assert ci_summary.read_threshold(pyproject.with_name("missing.toml")) is None
