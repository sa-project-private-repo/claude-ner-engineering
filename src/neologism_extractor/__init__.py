"""
Neologism Extractor Package
신조어 추출 및 코퍼스 생성 패키지
"""

from .extractor import NeologismExtractor
from .data_collector import DataCollector
from .corpus_builder import CorpusBuilder
from .definition_generator import DefinitionGenerator, add_definitions_to_dictionary
from .synonym_generator import SynonymGenerator
from .search_engine_exporter import SearchEngineExporter

__version__ = "0.3.0"
__all__ = [
    "NeologismExtractor",
    "DataCollector",
    "CorpusBuilder",
    "DefinitionGenerator",
    "add_definitions_to_dictionary",
    "SynonymGenerator",
    "SearchEngineExporter"
]
