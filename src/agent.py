import os

from pymatgen.core import Composition, Structure
from src.embedding import InputType
from src.search_api import SearchAPI
from src.schema import Neighbor, SynthesisRecipe, SummaryDoc


class MissingEnvError(RuntimeError):
    pass


class SynthesisAgent:
    def __init__(self):
        self._search_api_composition = None
        self._search_api_structure = None
        self._mpr = None

    def _get_search_api_composition(self) -> SearchAPI:
        if self._search_api_composition is None:
            self._search_api_composition = SearchAPI(
                input_type=InputType.COMPOSITION, max_neighbors=100
            )
        return self._search_api_composition

    def _get_search_api_structure(self) -> SearchAPI:
        if self._search_api_structure is None:
            self._search_api_structure = SearchAPI(
                input_type=InputType.STRUCTURE, max_neighbors=100
            )
        return self._search_api_structure

    def _get_mpr(self):
        if self._mpr is not None:
            return self._mpr
        mp_api_key = os.getenv("MP_API_KEY")
        if not mp_api_key:
            raise MissingEnvError("MP_API_KEY environment variable not set.")
        from mp_api.client import MPRester

        self._mpr = MPRester(api_key=mp_api_key)
        return self._mpr

    def find_similar_materials_by_composition(
        self, composition_str: str, n_neighbors: int = 10
    ) -> list[Neighbor]:
        composition = Composition(composition_str)
        results = self._get_search_api_composition().query(
            composition, n_neighbors=n_neighbors
        )
        return results

    def find_similar_materials_by_structure(
        self, structure: Structure, n_neighbors: int = 10
    ) -> list[Neighbor]:
        results = self._get_search_api_structure().query(
            structure, n_neighbors=n_neighbors
        )
        return results

    def get_synthesis_recipes_by_formula(self, formula: str) -> list[SynthesisRecipe]:
        mpr = self._get_mpr()
        recipes = mpr.materials.synthesis.search(target_formula=formula)
        return recipes

    def get_summarydoc_by_material_id(self, material_id: str) -> list[SummaryDoc]:
        mpr = self._get_mpr()
        summarydoc = mpr.materials.summary.search(material_ids=[material_id])
        return summarydoc

    def get_structure_by_material_id(self, material_id: str) -> Structure:
        mpr = self._get_mpr()
        structure = mpr.materials.get_structure_by_material_id(material_id)
        return structure


class SynthesisLLMAgent(SynthesisAgent):
    pass
