from sky_mcp import tools


def test_analyze_synthesis_parameters():
    result = tools.analyze_synthesis_parameters("Heat at 800 C for 10 hours in air.")
    assert result["ok"] is True
    data = result["data"]
    assert "temperatures_C" in data
    assert "time_durations" in data
    assert "synthesis_methods" in data
    assert "atmosphere" in data


def test_read_cif_invalid_text():
    result = tools.read_cif("not a cif")
    assert result["ok"] is False
    assert result["error"]["type"] in {"invalid_input", "runtime_error"}


def test_read_cif_path_missing(tmp_path, monkeypatch):
    missing = tmp_path / "missing.cif"
    monkeypatch.setenv("SKY_MCP_ALLOWED_ROOTS", str(tmp_path))
    result = tools.read_cif_path(str(missing))
    assert result["ok"] is False
    assert result["error"]["type"] == "file_not_found"


def test_search_similar_by_structure_cif_missing_assets(monkeypatch):
    cif_text = """data_test
_symmetry_space_group_name_H-M 'P 1'
_cell_length_a   3.0
_cell_length_b   3.0
_cell_length_c   3.0
_cell_angle_alpha 90
_cell_angle_beta  90
_cell_angle_gamma 90
_symmetry_Int_Tables_number 1
_chemical_formula_sum 'H2 O1'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
H1 H 0 0 0
H2 H 0.5 0.5 0.5
O1 O 0.25 0.25 0.25
"""
    monkeypatch.setattr(tools, "_structure_embedding_path", lambda: None)
    result = tools.search_similar_by_structure_cif(cif_text)
    assert result["ok"] is False
    assert result["error"]["type"] == "file_not_found"
