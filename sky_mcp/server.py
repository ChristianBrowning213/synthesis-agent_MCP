from __future__ import annotations

import inspect
from typing import Callable, List, Tuple

from sky_mcp import tools


ToolDef = Tuple[str, Callable[..., dict], str]


TOOL_DEFS: List[ToolDef] = [
    ("capabilities", tools.capabilities, "Report available assets, env vars, and versions."),
    ("search_similar_by_composition", tools.search_similar_by_composition, "Find similar materials by composition."),
    (
        "search_similar_by_structure_cif",
        tools.search_similar_by_structure_cif,
        "Find similar materials by CIF text (canonical).",
    ),
    (
        "search_similar_by_structure_path",
        tools.search_similar_by_structure_path,
        "Find similar materials by CIF file path (local-only).",
    ),
    ("read_cif", tools.read_cif, "Read CIF text and return structure metadata."),
    ("read_cif_path", tools.read_cif_path, "Read CIF file path and return structure metadata (local-only)."),
    ("get_material_properties", tools.get_material_properties, "Fetch Materials Project properties."),
    ("get_synthesis_recipes", tools.get_synthesis_recipes, "Retrieve synthesis recipes for a formula."),
    (
        "analyze_synthesis_parameters",
        tools.analyze_synthesis_parameters,
        "Extract synthesis parameters from text.",
    ),
    (
        "recursive_synthesis_search",
        tools.recursive_synthesis_search,
        "Recursive synthesis search using similarity neighbors.",
    ),
    (
        "discover_synthesis_report",
        tools.discover_synthesis_report,
        "Expensive, networked, nondeterministic synthesis report.",
    ),
    ("self_check", tools.self_check, "Run deterministic checks for MCP readiness."),
]


def _supports_named(tool_func: Callable[..., object]) -> bool:
    try:
        sig = inspect.signature(tool_func)
    except (TypeError, ValueError):
        return False
    return "name" in sig.parameters


def _register_tools(tool_decorator_factory: Callable[..., Callable[[Callable[..., dict]], Callable[..., dict]]]):
    supports_named = _supports_named(tool_decorator_factory)
    for name, func, description in TOOL_DEFS:
        if supports_named:
            decorator = tool_decorator_factory(name=name, description=description)
        else:
            decorator = tool_decorator_factory()
        decorator(func)


def _try_fastmcp():
    try:
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("sky")
        _register_tools(mcp.tool)

        def _run():
            mcp.run()

        return _run
    except Exception:
        return None


async def _run_stdio():
    from mcp.server import Server
    from mcp.server.stdio import stdio_server

    server = Server("sky")
    _register_tools(server.tool)

    async with stdio_server() as (read, write):
        await server.run(read, write)


def main() -> None:
    fastmcp_runner = _try_fastmcp()
    if fastmcp_runner is not None:
        fastmcp_runner()
        return

    import anyio

    anyio.run(_run_stdio)


if __name__ == "__main__":
    main()
