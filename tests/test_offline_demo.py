"""Verify the public example uses the core pipeline and reproducible fixtures."""

import json

import pytest

from examples.offline_demo import build_report, main, render_report


def test_demo_covers_all_outcomes_and_low_volume_filter():
    report = build_report()
    assert report["synthetic"] is True
    assert report["outcomes"] == {"win": 1, "half_win": 1, "draw": 1, "half_lose": 1, "lose": 1}
    assert report["cases"][-1]["filter"]["eligible"] is False
    assert report["cases"][-1]["metrics"]["total_volume"] == 20000
    assert len({case["scores"]["home"] for case in report["cases"]}) > 1


def test_demo_is_reproducible_and_never_opens_a_socket(monkeypatch):
    import socket

    def deny_network(*args, **kwargs):
        raise AssertionError("Offline demo attempted network access")

    monkeypatch.setattr(socket, "socket", deny_network)
    assert build_report() == build_report()


def test_cli_writes_html_and_json(tmp_path):
    main(["--output", str(tmp_path)])
    report = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert len(report["cases"]) == 5
    assert "<!--CASE_ROWS-->" not in html
    assert "OFFLINE / SYNTHETIC INPUTS" in html
    assert "North FC" in html


def test_html_escapes_fixture_names():
    report = build_report()
    report["cases"][0]["home"] = '<script>alert("x")</script>'
    html = render_report(report)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_rejects_unlabelled_input(tmp_path):
    path = tmp_path / "fixture.json"
    path.write_text('{"matches": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="synthetic"):
        build_report(path)
