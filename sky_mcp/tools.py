from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from monty.serialization import loadfn
from pymatgen.core import Composition, Structure

from src import ASSETS_DIR
from src.utils.assets import find_asset
from sky_mcp.paths import PathResolutionError, resolve_local_path
from sky_mcp.report_io import atomic_write_text, build_report_path
from sky_mcp.response import make_err, make_ok


def _get_sky_version() -> str:
    try:
        import sky

        return getattr(sky, "__version__", "unknown") or "unknown"
    except Exception:
        pass
    try:
        import tomllib

        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        return str(data.get("project", {}).get("version", "unknown"))
    except Exception:
        return "unknown"


def _meta(tool_name: str, warnings: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        "tool": tool_name,
        "version": _get_sky_version(),
        "warnings": warnings or [],
    }


def _missing_asset_error(
    tool_name: str, base: Path, preferred: Iterable[str], globs: Iterable[str]
) -> Dict[str, Any]:
    return make_err(
        "file_not_found",
        "Required asset not found.",
        details={
            "base_dir": str(base),
            "preferred_names": list(preferred),
            "globs": list(globs),
        },
        meta=_meta(tool_name),
    )


def _composition_embedding_path() -> Optional[Path]:
    return find_asset(
        preferred_names=["mp_dataset_composition_magpie.h5"],
        globs=["*composition*.h5"],
        base=ASSETS_DIR / "embedding",
    )


def _structure_embedding_path() -> Optional[Path]:
    return find_asset(
        preferred_names=["mp_dataset_structure_mace.h5"],
        globs=["*structure*.h5"],
        base=ASSETS_DIR / "embedding",
    )


def _recipes_dataset_path() -> Optional[Path]:
    return find_asset(
        preferred_names=["mp_synthesis_recipes.json.gz"],
        globs=["*synthesis*recipes*.json*"],
        base=ASSETS_DIR,
    )


def _derived_similarity(distance: float) -> float:
    return 1.0 / (1.0 + float(distance))


def _parse_cif_text(cif: str) -> Structure:
    if not cif or not cif.strip():
        raise ValueError("CIF text is empty.")
    return Structure.from_str(cif, fmt="cif")


def _structure_summary(structure: Structure) -> Dict[str, Any]:
    sites = [
        {
            "element": site.species_string,
            "frac_coords": [float(x) for x in site.frac_coords],
        }
        for site in structure.sites
    ]
    sites.sort(key=lambda s: (s["element"], tuple(s["frac_coords"])))
    return {
        "formula": structure.composition.formula,
        "reduced_formula": structure.composition.reduced_formula,
        "density": structure.density,
        "num_sites": structure.num_sites,
        "lattice": {
            "a": structure.lattice.a,
            "b": structure.lattice.b,
            "c": structure.lattice.c,
            "alpha": structure.lattice.alpha,
            "beta": structure.lattice.beta,
            "gamma": structure.lattice.gamma,
            "volume": structure.lattice.volume,
        },
        "elements": sorted(str(el) for el in structure.composition.elements),
        "sites": sites,
    }

def _list_asset_files(base: Path, globs: Iterable[str]) -> List[str]:
    files: List[str] = []
    if base.exists():
        for pattern in globs:
            for match in base.glob(pattern):
                if match.is_file():
                    files.append(match.name)
    return sorted(set(files))


def capabilities() -> Dict[str, Any]:
    tool_name = "capabilities"
    comp_embedding = _composition_embedding_path()
    struct_embedding = _structure_embedding_path()
    recipes_dataset = _recipes_dataset_path()
    openai_key = os.getenv("OPENAI_MDG_API_KEY") or os.getenv("OPENAI_API_KEY")
    mp_key = os.getenv("MP_API_KEY")

    try:
        import pymatgen

        pymatgen_version = getattr(pymatgen, "__version__", "unknown")
    except Exception:
        pymatgen_version = "unknown"
    try:
        import mcp

        mcp_version = getattr(mcp, "__version__", "unknown")
    except Exception:
        mcp_version = "unknown"

    return make_ok(
        {
            "assets": {
                "composition_embedding": bool(comp_embedding and comp_embedding.exists()),
                "structure_embedding": bool(struct_embedding and struct_embedding.exists()),
                "recipes_dataset": bool(recipes_dataset and recipes_dataset.exists()),
                "files": {
                    "composition_embeddings": _list_asset_files(
                        ASSETS_DIR / "embedding", ["*composition*.h5"]
                    ),
                    "structure_embeddings": _list_asset_files(
                        ASSETS_DIR / "embedding", ["*structure*.h5"]
                    ),
                    "recipes_datasets": _list_asset_files(
                        ASSETS_DIR, ["*synthesis*recipes*.json*"]
                    ),
                },
            },
            "env": {
                "mp_api_key": bool(mp_key),
                "openai_api_key": bool(openai_key),
            },
            "versions": {
                "sky_version": _get_sky_version(),
                "pymatgen_version": pymatgen_version,
                "mcp_version": mcp_version,
            },
        },
        meta=_meta(tool_name),
        provenance={"source": "local", "ids": []},
    )


def read_cif(cif: str) -> Dict[str, Any]:
    tool_name = "read_cif"
    try:
        structure = _parse_cif_text(cif)
        data = _structure_summary(structure)
        return make_ok(
            data,
            meta=_meta(tool_name),
            provenance={"source": "local", "ids": []},
        )
    except Exception as exc:
        return make_err(
            "invalid_input",
            "Failed to parse CIF text.",
            details=str(exc),
            meta=_meta(tool_name),
        )


def read_cif_path(cif_path: str) -> Dict[str, Any]:
    tool_name = "read_cif_path"
    try:
        path = resolve_local_path(cif_path)
    except PathResolutionError as exc:
        return make_err(
            exc.error_type,
            exc.message,
            details=exc.details,
            meta=_meta(tool_name),
        )
    try:
        structure = Structure.from_file(path)
        data = _structure_summary(structure)
        return make_ok(
            data,
            meta=_meta(tool_name),
            provenance={"source": "local", "ids": []},
        )
    except Exception as exc:
        return make_err(
            "runtime_error",
            "Failed to read CIF file.",
            details=str(exc),
            meta=_meta(tool_name),
        )


def search_similar_by_composition(formula: str, top_n: int = 10) -> Dict[str, Any]:
    tool_name = "search_similar_by_composition"
    if not formula or not formula.strip():
        return make_err(
            "invalid_input",
            "Formula is required.",
            meta=_meta(tool_name),
        )
    try:
        composition = Composition(formula)
    except Exception as exc:
        return make_err(
            "invalid_input",
            "Invalid formula.",
            details=str(exc),
            meta=_meta(tool_name),
        )

    embedding_path = _composition_embedding_path()
    if not embedding_path:
        return _missing_asset_error(
            tool_name,
            base=ASSETS_DIR / "embedding",
            preferred=["mp_dataset_composition_magpie.h5"],
            globs=["*composition*.h5"],
        )

    try:
        from src.embedding import InputType
        from src.search_api import SearchAPI

        search_api = SearchAPI(input_type=InputType.COMPOSITION, max_neighbors=max(100, top_n))
        neighbors = search_api.query(composition, n_neighbors=top_n)
        neighbors = sorted(neighbors, key=lambda n: (n.distance, n.material_id, n.formula))
        results = []
        for idx, neighbor in enumerate(neighbors, start=1):
            results.append(
                {
                    "rank": idx,
                    "material_id": neighbor.material_id,
                    "formula": neighbor.formula,
                    "distance": neighbor.distance,
                    "similarity": _derived_similarity(neighbor.distance),
                }
            )
        return make_ok(
            {
                "query": formula,
                "num_results": len(results),
                "neighbors": results,
            },
            meta=_meta(tool_name),
            provenance={
                "source": "computed",
                "ids": [n["material_id"] for n in results],
            },
        )
    except FileNotFoundError as exc:
        return make_err(
            "file_not_found",
            "Embedding dataset not found.",
            details=str(exc),
            meta=_meta(tool_name),
        )
    except Exception as exc:
        return make_err(
            "runtime_error",
            "Similarity search failed.",
            details=str(exc),
            meta=_meta(tool_name),
        )


def search_similar_by_structure_cif(cif: str, top_n: int = 10) -> Dict[str, Any]:
    tool_name = "search_similar_by_structure_cif"
    try:
        structure = _parse_cif_text(cif)
    except Exception as exc:
        return make_err(
            "invalid_input",
            "Failed to parse CIF text.",
            details=str(exc),
            meta=_meta(tool_name),
        )

    embedding_path = _structure_embedding_path()
    if not embedding_path:
        return _missing_asset_error(
            tool_name,
            base=ASSETS_DIR / "embedding",
            preferred=["mp_dataset_structure_mace.h5"],
            globs=["*structure*.h5"],
        )

    try:
        from src.embedding import InputType
        from src.search_api import SearchAPI

        search_api = SearchAPI(input_type=InputType.STRUCTURE, max_neighbors=max(100, top_n))
        neighbors = search_api.query(structure, n_neighbors=top_n)
        neighbors = sorted(neighbors, key=lambda n: (n.distance, n.material_id, n.formula))
        results = []
        for idx, neighbor in enumerate(neighbors, start=1):
            results.append(
                {
                    "rank": idx,
                    "material_id": neighbor.material_id,
                    "formula": neighbor.formula,
                    "distance": neighbor.distance,
                    "similarity": _derived_similarity(neighbor.distance),
                }
            )
        return make_ok(
            {
                "num_results": len(results),
                "neighbors": results,
            },
            meta=_meta(tool_name),
            provenance={
                "source": "computed",
                "ids": [n["material_id"] for n in results],
            },
        )
    except FileNotFoundError as exc:
        return make_err(
            "file_not_found",
            "Embedding dataset not found.",
            details=str(exc),
            meta=_meta(tool_name),
        )
    except Exception as exc:
        return make_err(
            "runtime_error",
            "Similarity search failed.",
            details=str(exc),
            meta=_meta(tool_name),
        )


def search_similar_by_structure_path(cif_path: str, top_n: int = 10) -> Dict[str, Any]:
    tool_name = "search_similar_by_structure_path"
    try:
        path = resolve_local_path(cif_path)
    except PathResolutionError as exc:
        return make_err(
            exc.error_type,
            exc.message,
            details=exc.details,
            meta=_meta(tool_name),
        )
    try:
        structure = Structure.from_file(path)
    except Exception as exc:
        return make_err(
            "runtime_error",
            "Failed to read CIF file.",
            details=str(exc),
            meta=_meta(tool_name),
        )

    embedding_path = _structure_embedding_path()
    if not embedding_path:
        return _missing_asset_error(
            tool_name,
            base=ASSETS_DIR / "embedding",
            preferred=["mp_dataset_structure_mace.h5"],
            globs=["*structure*.h5"],
        )

    try:
        from src.embedding import InputType
        from src.search_api import SearchAPI

        search_api = SearchAPI(input_type=InputType.STRUCTURE, max_neighbors=max(100, top_n))
        neighbors = search_api.query(structure, n_neighbors=top_n)
        neighbors = sorted(neighbors, key=lambda n: (n.distance, n.material_id, n.formula))
        results = []
        for idx, neighbor in enumerate(neighbors, start=1):
            results.append(
                {
                    "rank": idx,
                    "material_id": neighbor.material_id,
                    "formula": neighbor.formula,
                    "distance": neighbor.distance,
                    "similarity": _derived_similarity(neighbor.distance),
                }
            )
        return make_ok(
            {
                "num_results": len(results),
                "neighbors": results,
            },
            meta=_meta(tool_name),
            provenance={
                "source": "computed",
                "ids": [n["material_id"] for n in results],
            },
        )
    except FileNotFoundError as exc:
        return make_err(
            "file_not_found",
            "Embedding dataset not found.",
            details=str(exc),
            meta=_meta(tool_name),
        )
    except Exception as exc:
        return make_err(
            "runtime_error",
            "Similarity search failed.",
            details=str(exc),
            meta=_meta(tool_name),
        )


def get_material_properties(material_ids: List[str]) -> Dict[str, Any]:
    tool_name = "get_material_properties"
    if not material_ids:
        return make_err(
            "invalid_input",
            "material_ids must be a non-empty list.",
            meta=_meta(tool_name),
        )
    mp_key = os.getenv("MP_API_KEY")
    if not mp_key:
        return make_err(
            "missing_env",
            "MP_API_KEY not found in environment.",
            meta=_meta(tool_name),
        )
    try:
        from mp_api.client import MPRester

        results = []
        with MPRester(mp_key) as mpr:
            docs = mpr.materials.summary.search(material_ids=material_ids)
            for doc in docs:
                results.append(
                    {
                        "material_id": doc.material_id,
                        "formula_pretty": doc.formula_pretty,
                        "band_gap": doc.band_gap,
                        "density": doc.density,
                        "formation_energy_per_atom": doc.formation_energy_per_atom,
                        "energy_above_hull": doc.energy_above_hull,
                        "volume": doc.volume if hasattr(doc, "volume") else None,
                        "mp_url": f"https://materialsproject.org/materials/{doc.material_id}",
                    }
                )
        results = sorted(results, key=lambda r: r["material_id"])
        return make_ok(
            results,
            meta=_meta(tool_name),
            provenance={"source": "mp", "ids": [r["material_id"] for r in results]},
        )
    except Exception as exc:
        return make_err(
            "mp_api_error",
            "Failed to fetch material properties from Materials Project.",
            details=str(exc),
            meta=_meta(tool_name),
        )


def get_synthesis_recipes(formula: str, max_recipes: int = 5) -> Dict[str, Any]:
    tool_name = "get_synthesis_recipes"
    if not formula or not formula.strip():
        return make_err(
            "invalid_input",
            "Formula is required.",
            meta=_meta(tool_name),
        )
    try:
        target_comp = Composition(formula)
    except Exception as exc:
        return make_err(
            "invalid_input",
            "Invalid formula.",
            details=str(exc),
            meta=_meta(tool_name),
        )

    recipes_path = _recipes_dataset_path()
    if recipes_path and recipes_path.exists():
        try:
            all_recipes = loadfn(recipes_path)
            matched = []
            for recipe in all_recipes:
                target_formula = recipe.get("target_formula")
                if not target_formula:
                    continue
                try:
                    recipe_comp = Composition(target_formula)
                except Exception:
                    continue
                if recipe_comp.reduced_formula == target_comp.reduced_formula:
                    matched.append(recipe)
            matched.sort(
                key=lambda r: (
                    r.get("target_formula", ""),
                    r.get("doi", ""),
                    r.get("paragraph_string", ""),
                    r.get("reaction_string", ""),
                )
            )
            data = {
                "target_formula": formula,
                "recipes_found": len(matched),
                "recipes": matched[:max_recipes],
            }
            return make_ok(
                data,
                meta=_meta(tool_name),
                provenance={"source": "local", "ids": []},
            )
        except Exception as exc:
            return make_err(
                "runtime_error",
                "Failed to load local synthesis dataset.",
                details=str(exc),
                meta=_meta(tool_name),
            )

    MissingEnv = None
    try:
        from src.agent import MissingEnvError as _MissingEnvError, SynthesisAgent

        MissingEnv = _MissingEnvError
        agent = SynthesisAgent()
        recipes = agent.get_synthesis_recipes_by_formula(formula)
        results = []
        for recipe in recipes[:max_recipes]:
            if hasattr(recipe, "model_dump"):
                results.append(recipe.model_dump())
            elif hasattr(recipe, "dict"):
                results.append(recipe.dict())
            else:
                results.append(recipe)
        results = sorted(
            results,
            key=lambda r: (
                r.get("target_formula", ""),
                r.get("doi", ""),
                r.get("paragraph_string", ""),
            )
            if isinstance(r, dict)
            else str(r),
        )
        return make_ok(
            {
                "target_formula": formula,
                "recipes_found": len(results),
                "recipes": results,
            },
            meta=_meta(tool_name),
            provenance={"source": "mp", "ids": []},
        )
    except Exception as exc:
        if MissingEnv and isinstance(exc, MissingEnv):
            return make_err(
                "missing_env",
                str(exc),
                meta=_meta(tool_name),
            )
        return make_err(
            "runtime_error",
            "Recipe retrieval failed. The Materials Project recipe route may be unavailable.",
            details=str(exc),
            meta=_meta(tool_name),
        )


def analyze_synthesis_parameters(text: str) -> Dict[str, Any]:
    tool_name = "analyze_synthesis_parameters"
    if not text or not text.strip():
        return make_err(
            "invalid_input",
            "text is required.",
            meta=_meta(tool_name),
        )

    temperature_patterns = [
        r"(\d+)\s*°C",
        r"(\d+)\s*K",
        r"(\d+)\s*degrees?\s*C",
        r"(\d+)\s*celsius",
    ]
    temperatures = []
    for pattern in temperature_patterns:
        temperatures.extend(re.findall(pattern, text, flags=re.IGNORECASE))

    time_patterns = [
        r"(\d+)\s*hours?",
        r"(\d+)\s*h\b",
        r"(\d+)\s*minutes?",
        r"(\d+)\s*min\b",
        r"(\d+)\s*days?",
    ]
    times = []
    for pattern in time_patterns:
        times.extend(re.findall(pattern, text, flags=re.IGNORECASE))

    methods = {
        "solid_state": ["solid state", "ceramic", "calcination", "sintering"],
        "sol_gel": ["sol-gel", "sol gel", "gelation", "xerogel"],
        "hydrothermal": ["hydrothermal", "solvothermal", "autoclave"],
        "precipitation": ["precipitation", "coprecipitation", "co-precipitation"],
        "cvd": ["cvd", "chemical vapor", "vapor deposition"],
        "combustion": ["combustion", "self-propagating", "shs"],
        "flux": ["flux", "molten salt", "flux growth"],
    }
    detected_methods = []
    lower = text.lower()
    for method, keywords in methods.items():
        if any(keyword in lower for keyword in keywords):
            detected_methods.append(method)

    atmospheres = []
    for keyword in ["air", "argon", "nitrogen", "n2", "ar", "oxygen", "o2", "vacuum", "inert"]:
        if keyword in lower:
            atmospheres.append(keyword)

    data = {
        "temperatures_C": sorted(set(temperatures)),
        "time_durations": sorted(set(times)),
        "synthesis_methods": sorted(set(detected_methods)),
        "atmosphere": sorted(set(atmospheres)),
        "has_heating": bool(temperatures),
        "text_length": len(text),
    }
    return make_ok(
        data,
        meta=_meta(tool_name),
        provenance={"source": "computed", "ids": []},
    )


def recursive_synthesis_search(
    formula: str,
    max_depth: int = 3,
    min_confidence: float = 0.7,
    n_initial_neighbors: int = 30,
) -> Dict[str, Any]:
    tool_name = "recursive_synthesis_search"
    if not formula or not formula.strip():
        return make_err(
            "invalid_input",
            "Formula is required.",
            meta=_meta(tool_name),
        )
    try:
        Composition(formula)
    except Exception as exc:
        return make_err(
            "invalid_input",
            "Invalid formula.",
            details=str(exc),
            meta=_meta(tool_name),
        )

    embedding_path = _composition_embedding_path()
    if not embedding_path:
        return _missing_asset_error(
            tool_name,
            base=ASSETS_DIR / "embedding",
            preferred=["mp_dataset_composition_magpie.h5"],
            globs=["*composition*.h5"],
        )

    if not os.getenv("MP_API_KEY"):
        return make_err(
            "missing_env",
            "MP_API_KEY not found in environment.",
            meta=_meta(tool_name),
        )

    MissingEnv = None
    try:
        from src.agent import MissingEnvError as _MissingEnvError, SynthesisAgent
        from src.recursive_synthesis import RecursiveSynthesisSearch

        MissingEnv = _MissingEnvError
        recursive_search = RecursiveSynthesisSearch(
            synthesis_agent=SynthesisAgent(),
            max_depth=max_depth,
            min_confidence=min_confidence,
            verbose=False,
        )
        results = recursive_search.search(
            target_formula=formula,
            n_initial_neighbors=n_initial_neighbors,
        )
        return make_ok(
            results,
            meta=_meta(tool_name),
            provenance={"source": "computed", "ids": []},
        )
    except Exception as exc:
        if MissingEnv and isinstance(exc, MissingEnv):
            return make_err(
                "missing_env",
                str(exc),
                meta=_meta(tool_name),
            )
        return make_err(
            "runtime_error",
            "Recursive synthesis search failed.",
            details=str(exc),
            meta=_meta(tool_name),
        )


def discover_synthesis_report(query: str, html: bool = False) -> Dict[str, Any]:
    tool_name = "discover_synthesis_report"
    openai_key = os.getenv("OPENAI_MDG_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not openai_key:
        return make_err(
            "missing_env",
            "OPENAI_API_KEY or OPENAI_MDG_API_KEY not found in environment.",
            meta=_meta(tool_name),
        )

    warnings = ["networked", "nondeterministic", "may incur cost"]
    try:
        from sky.core.synthesis_agent import SKYSynthesisAgent
        from sky.report.html_generator import HTMLReportGenerator

        agent = SKYSynthesisAgent()
        analysis_text = agent.discover_synthesis_sync(query)

        data: Dict[str, Any] = {"analysis_text": analysis_text}
        if html:
            generator = HTMLReportGenerator()
            report_data = generator.parse_agent_output(analysis_text)
            if not report_data.material_formula:
                report_data.material_formula = query
                report_data.material_formula_html = generator._formula_to_html(query)
            html_content = generator.generate_html(report_data)
            reports_dir = Path.cwd() / "sky_reports"
            output_path = build_report_path(query, reports_dir)
            atomic_write_text(output_path, html_content)
            data["report_path"] = str(output_path.relative_to(Path.cwd()))

        provenance: Dict[str, Any] = {"source": "openai", "outputs": []}
        if "report_path" in data:
            provenance["outputs"] = [data["report_path"]]

        return make_ok(
            data,
            meta=_meta(tool_name, warnings=warnings),
            provenance=provenance,
        )
    except Exception as exc:
        return make_err(
            "runtime_error",
            "Synthesis report generation failed.",
            details=str(exc),
            meta=_meta(tool_name, warnings=warnings),
        )


def self_check() -> Dict[str, Any]:
    tool_name = "self_check"
    comp_embedding = _composition_embedding_path()
    struct_embedding = _structure_embedding_path()
    recipes_dataset = _recipes_dataset_path()
    openai_key = os.getenv("OPENAI_MDG_API_KEY") or os.getenv("OPENAI_API_KEY")
    mp_key = os.getenv("MP_API_KEY")
    reports_dir = Path.cwd() / "sky_reports"
    reports_dir_writable = reports_dir.exists() and os.access(reports_dir, os.W_OK)
    if not reports_dir.exists():
        reports_dir_writable = os.access(reports_dir.parent, os.W_OK)

    tools = sorted(
        [
            "capabilities",
            "search_similar_by_composition",
            "search_similar_by_structure_cif",
            "search_similar_by_structure_path",
            "read_cif",
            "read_cif_path",
            "get_material_properties",
            "get_synthesis_recipes",
            "analyze_synthesis_parameters",
            "recursive_synthesis_search",
            "discover_synthesis_report",
            "self_check",
        ]
    )

    return make_ok(
        {
            "tools": tools,
            "assets": {
                "composition_embedding": bool(comp_embedding and comp_embedding.exists()),
                "structure_embedding": bool(struct_embedding and struct_embedding.exists()),
                "recipes_dataset": bool(recipes_dataset and recipes_dataset.exists()),
            },
            "report_dir_writable": bool(reports_dir_writable),
            "env": {
                "mp_api_key": bool(mp_key),
                "openai_api_key": bool(openai_key),
            },
        },
        meta=_meta(tool_name),
        provenance={"source": "local", "ids": []},
    )
