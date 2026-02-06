from __future__ import annotations

from pathlib import Path

import pytest

from sky_mcp import tools
from sky_mcp.report_io import atomic_write_text, build_report_path
from sky_mcp.response import validate_envelope


def test_envelope_invariants_all_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("SKY_MCP_ALLOWED_ROOTS", str(tmp_path))

    cases = [
        tools.capabilities(),
        tools.self_check(),
        tools.read_cif("not a cif"),
        tools.read_cif_path(str(tmp_path / "missing.cif")),
        tools.search_similar_by_composition(""),
        tools.search_similar_by_structure_cif("not a cif"),
        tools.search_similar_by_structure_path(str(tmp_path / "missing.cif")),
        tools.get_material_properties([]),
        tools.get_synthesis_recipes(""),
        tools.analyze_synthesis_parameters(""),
        tools.recursive_synthesis_search(""),
    ]

    for resp in cases:
        validate_envelope(resp, strict=True)


def test_determinism_sorted_lists():
    resp = tools.capabilities()
    assets = resp["data"]["assets"]["files"]
    for key, value in assets.items():
        assert value == sorted(value), f"{key} is not sorted"


def test_path_traversal_rejected():
    resp = tools.read_cif_path("../../etc/passwd")
    assert resp["ok"] is False
    assert resp["error"]["type"] in {"permission_denied", "invalid_input"}


def test_file_too_large_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("SKY_MCP_ALLOWED_ROOTS", str(tmp_path))
    big_file = tmp_path / "big.cif"
    big_file.write_bytes(b"0" * 2_000_001)
    resp = tools.read_cif_path(str(big_file))
    assert resp["ok"] is False
    assert resp["error"]["type"] == "file_too_large"


def test_report_path_relative(tmp_path, monkeypatch):
    class _FixedUUID:
        def __str__(self):
            return "fixed-uuid"

    reports_dir = tmp_path / "sky_reports"
    path = build_report_path("Fe2O3", reports_dir, uuid_func=_FixedUUID)
    atomic_write_text(path, "<html>ok</html>")
    rel = path.relative_to(tmp_path)
    assert str(rel).startswith("sky_reports")
