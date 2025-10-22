"""
Neologism Extractor Package
신조어 추출 및 코퍼스 생성 패키지
"""

from .extractor import NeologismExtractor
from .data_collector import DataCollector
from .corpus_builder import CorpusBuilder
from .definition_generator import DefinitionGenerator, add_definitions_to_dictionary

__version__ = "0.2.0"
__all__ = [
    "NeologismExtractor",
    "DataCollector",
    "CorpusBuilder",
    "DefinitionGenerator",
    "add_definitions_to_dictionary"
]
