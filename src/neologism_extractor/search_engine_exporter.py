"""
검색 엔진 내보내기 (Search Engine Exporter)

OpenSearch/Elasticsearch에서 사용할 수 있는 형식으로 신조어 사전 및 동의어를 내보냅니다.

지원 형식:
1. Solr 동의어 파일 (synonyms.txt)
2. 사용자 사전 (user_dictionary.txt) - Nori Tokenizer용
3. 인덱스 설정 (index_settings.json)
"""

import json
import os
from typing import List, Dict, Set, Optional
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SearchEngineExporter:
    """
    검색 엔진용 파일 생성기

    OpenSearch/Elasticsearch에서 사용할 수 있는 동의어 및 사용자 사전 파일을 생성합니다.
    """

    def __init__(self, output_dir: str = "./search_engine_exports"):
        """
        Args:
            output_dir: 출력 디렉토리
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_synonym_file(
        self,
        synonym_groups: List[Set[str]],
        synonym_map: Optional[Dict[str, List[str]]] = None,
        filename: str = "synonyms.txt",
        format: str = "solr"
    ) -> str:
        """
        동의어 파일 생성

        Args:
            synonym_groups: 동의어 그룹 리스트
            synonym_map: 단어별 동의어 매핑 (선택)
            filename: 파일명
            format: 'solr' 또는 'wordnet'

        Returns:
            생성된 파일 경로
        """
        output_path = self.output_dir / filename

        with open(output_path, 'w', encoding='utf-8') as f:
            if format == 'solr':
                # Solr 형식: word1, word2, word3
                for group in synonym_groups:
                    if len(group) > 1:
                        line = ', '.join(sorted(group))
                        f.write(line + '\n')

            elif format == 'wordnet':
                # WordNet 형식: word1 => word2, word3
                if synonym_map:
                    for word, synonyms in sorted(synonym_map.items()):
                        if synonyms:
                            line = f"{word} => {', '.join(synonyms)}"
                            f.write(line + '\n')

        logger.info(f"동의어 파일 생성 완료: {output_path} ({format} 형식)")
        return str(output_path)

    def export_user_dictionary(
        self,
        neologisms: List[Dict],
        filename: str = "user_dictionary.txt"
    ) -> str:
        """
        사용자 사전 파일 생성 (Nori Tokenizer용)

        Args:
            neologisms: 신조어 리스트
            filename: 파일명

        Returns:
            생성된 파일 경로
        """
        output_path = self.output_dir / filename

        with open(output_path, 'w', encoding='utf-8') as f:
            for item in neologisms:
                word = item['word']
                # 한 줄에 하나씩 단어 작성
                f.write(word + '\n')

        logger.info(f"사용자 사전 파일 생성 완료: {output_path} "
                   f"({len(neologisms)}개 단어)")
        return str(output_path)

    def export_nori_user_dictionary(
        self,
        neologisms: List[Dict],
        filename: str = "nori_user_dictionary.txt"
    ) -> str:
        """
        Nori Tokenizer용 확장 사용자 사전 생성

        형식: word [pos_tag]
        예: 갓생 NNP
        """
        output_path = self.output_dir / filename

        # 신조어 타입을 품사 태그로 매핑
        pos_tag_map = {
            'abbreviation': 'NNP',   # 고유명사
            'compound': 'NNG',       # 일반명사
            'slang': 'NNG',          # 일반명사
            'unknown': 'NNG'         # 일반명사
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            for item in neologisms:
                word = item['word']
                word_type = item.get('type', 'unknown')
                pos_tag = pos_tag_map.get(word_type, 'NNG')

                # Nori 형식: word pos_tag
                f.write(f"{word} {pos_tag}\n")

        logger.info(f"Nori 사용자 사전 파일 생성 완료: {output_path}")
        return str(output_path)

    def generate_index_settings(
        self,
        index_name: str = "neologism_search",
        synonym_file_path: str = "synonyms.txt",
        user_dict_file_path: str = "user_dictionary.txt",
        language: str = "korean"
    ) -> Dict:
        """
        OpenSearch/Elasticsearch 인덱스 설정 생성

        Args:
            index_name: 인덱스 이름
            synonym_file_path: 동의어 파일 경로 (상대 경로)
            user_dict_file_path: 사용자 사전 파일 경로
            language: 언어 ('korean', 'english', etc.)

        Returns:
            인덱스 설정 딕셔너리
        """
        if language == "korean":
            settings = {
                "settings": {
                    "analysis": {
                        "tokenizer": {
                            "nori_user_dict": {
                                "type": "nori_tokenizer",
                                "decompound_mode": "mixed",
                                "user_dictionary": user_dict_file_path
                            }
                        },
                        "filter": {
                            "synonym_filter": {
                                "type": "synonym",
                                "synonyms_path": synonym_file_path,
                                "updateable": True
                            },
                            "nori_posfilter": {
                                "type": "nori_part_of_speech",
                                "stoptags": [
                                    "E", "IC", "J", "MAG", "MAJ",
                                    "MM", "SP", "SSC", "SSO", "SC",
                                    "SE", "XPN", "XSA", "XSN", "XSV",
                                    "UNA", "NA", "VSV"
                                ]
                            }
                        },
                        "analyzer": {
                            "korean_analyzer": {
                                "type": "custom",
                                "tokenizer": "nori_user_dict",
                                "filter": [
                                    "lowercase",
                                    "nori_posfilter",
                                    "synonym_filter",
                                    "nori_readingform"
                                ]
                            },
                            "korean_search_analyzer": {
                                "type": "custom",
                                "tokenizer": "nori_user_dict",
                                "filter": [
                                    "lowercase",
                                    "synonym_filter"
                                ]
                            }
                        }
                    },
                    "index": {
                        "number_of_shards": 1,
                        "number_of_replicas": 1
                    }
                },
                "mappings": {
                    "properties": {
                        "text": {
                            "type": "text",
                            "analyzer": "korean_analyzer",
                            "search_analyzer": "korean_search_analyzer"
                        },
                        "title": {
                            "type": "text",
                            "analyzer": "korean_analyzer",
                            "search_analyzer": "korean_search_analyzer",
                            "fields": {
                                "keyword": {
                                    "type": "keyword"
                                }
                            }
                        },
                        "timestamp": {
                            "type": "date"
                        }
                    }
                }
            }
        else:
            # 기본 영어 설정
            settings = {
                "settings": {
                    "analysis": {
                        "filter": {
                            "synonym_filter": {
                                "type": "synonym",
                                "synonyms_path": synonym_file_path,
                                "updateable": True
                            }
                        },
                        "analyzer": {
                            "default_analyzer": {
                                "type": "custom",
                                "tokenizer": "standard",
                                "filter": [
                                    "lowercase",
                                    "synonym_filter"
                                ]
                            }
                        }
                    },
                    "index": {
                        "number_of_shards": 1,
                        "number_of_replicas": 1
                    }
                },
                "mappings": {
                    "properties": {
                        "text": {
                            "type": "text",
                            "analyzer": "default_analyzer"
                        },
                        "title": {
                            "type": "text",
                            "analyzer": "default_analyzer"
                        },
                        "timestamp": {
                            "type": "date"
                        }
                    }
                }
            }

        return settings

    def export_index_settings(
        self,
        settings: Dict,
        filename: str = "index_settings.json"
    ) -> str:
        """
        인덱스 설정을 JSON 파일로 저장

        Args:
            settings: 인덱스 설정 딕셔너리
            filename: 파일명

        Returns:
            생성된 파일 경로
        """
        output_path = self.output_dir / filename

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)

        logger.info(f"인덱스 설정 파일 생성 완료: {output_path}")
        return str(output_path)

    def export_all(
        self,
        neologisms: List[Dict],
        synonym_groups: List[Set[str]],
        synonym_map: Dict[str, List[str]],
        index_name: str = "neologism_search"
    ) -> Dict[str, str]:
        """
        모든 검색 엔진 파일 일괄 생성

        Args:
            neologisms: 신조어 리스트
            synonym_groups: 동의어 그룹
            synonym_map: 동의어 매핑
            index_name: 인덱스 이름

        Returns:
            생성된 파일 경로들
        """
        logger.info("검색 엔진 파일 일괄 생성 시작...")

        files = {}

        # 1. Solr 동의어 파일
        files['synonyms_solr'] = self.export_synonym_file(
            synonym_groups,
            format='solr',
            filename='synonyms.txt'
        )

        # 2. WordNet 동의어 파일
        files['synonyms_wordnet'] = self.export_synonym_file(
            synonym_groups,
            synonym_map,
            format='wordnet',
            filename='synonyms_wordnet.txt'
        )

        # 3. 기본 사용자 사전
        files['user_dictionary'] = self.export_user_dictionary(
            neologisms,
            filename='user_dictionary.txt'
        )

        # 4. Nori 사용자 사전
        files['nori_user_dictionary'] = self.export_nori_user_dictionary(
            neologisms,
            filename='nori_user_dictionary.txt'
        )

        # 5. 인덱스 설정
        settings = self.generate_index_settings(
            index_name=index_name,
            synonym_file_path='synonyms.txt',
            user_dict_file_path='nori_user_dictionary.txt'
        )
        files['index_settings'] = self.export_index_settings(
            settings,
            filename='index_settings.json'
        )

        # 6. 인덱스 생성 스크립트
        files['setup_script'] = self._generate_setup_script(
            index_name,
            'setup_index.sh'
        )

        logger.info(f"검색 엔진 파일 생성 완료: {len(files)}개 파일")
        return files

    def _generate_setup_script(
        self,
        index_name: str,
        filename: str = "setup_index.sh"
    ) -> str:
        """
        OpenSearch/Elasticsearch 인덱스 생성 스크립트 생성

        Returns:
            생성된 스크립트 파일 경로
        """
        output_path = self.output_dir / filename

        script_content = f"""#!/bin/bash

###############################################################################
# OpenSearch/Elasticsearch 인덱스 설정 스크립트
#
# 사용법:
#   ./setup_index.sh <opensearch_url>
#
# 예시:
#   ./setup_index.sh https://localhost:9200
###############################################################################

set -e

# 환경 변수
OPENSEARCH_URL="${{1:-http://localhost:9200}}"
INDEX_NAME="{index_name}"

echo "========================================="
echo "OpenSearch 인덱스 설정"
echo "========================================="
echo "URL: $OPENSEARCH_URL"
echo "Index: $INDEX_NAME"
echo ""

# 1. 기존 인덱스 삭제 (선택)
read -p "기존 인덱스를 삭제하시겠습니까? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "기존 인덱스 삭제 중..."
    curl -X DELETE "$OPENSEARCH_URL/$INDEX_NAME" || true
    echo ""
fi

# 2. 인덱스 생성
echo "인덱스 생성 중..."
curl -X PUT "$OPENSEARCH_URL/$INDEX_NAME" \\
    -H 'Content-Type: application/json' \\
    -d @index_settings.json

echo ""
echo ""

# 3. 동의어 파일 업로드 (플러그인 필요)
echo "========================================="
echo "동의어 파일 수동 배치 필요"
echo "========================================="
echo "1. synonyms.txt를 다음 경로에 복사:"
echo "   OpenSearch: config/opensearch/synonyms.txt"
echo "   Elasticsearch: config/analysis/synonyms.txt"
echo ""
echo "2. nori_user_dictionary.txt를 다음 경로에 복사:"
echo "   config/user_dictionary.txt"
echo ""
echo "3. OpenSearch/Elasticsearch 재시작"
echo ""

# 4. 인덱스 상태 확인
echo "========================================="
echo "인덱스 상태 확인"
echo "========================================="
curl -X GET "$OPENSEARCH_URL/$INDEX_NAME/_settings?pretty"
echo ""

echo "========================================="
echo "설정 완료!"
echo "========================================="
"""

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(script_content)

        # 실행 권한 부여
        os.chmod(output_path, 0o755)

        logger.info(f"설정 스크립트 생성 완료: {output_path}")
        return str(output_path)

    def upload_to_s3(
        self,
        files: Dict[str, str],
        bucket: str,
        prefix: str = "search_engine/"
    ):
        """
        생성된 파일들을 S3에 업로드

        Args:
            files: 파일 경로 딕셔너리
            bucket: S3 버킷 이름
            prefix: S3 키 프리픽스
        """
        try:
            import boto3
            s3_client = boto3.client('s3')

            for file_type, file_path in files.items():
                s3_key = f"{prefix}{Path(file_path).name}"

                s3_client.upload_file(
                    file_path,
                    bucket,
                    s3_key,
                    ExtraArgs={'ContentType': self._get_content_type(file_path)}
                )

                logger.info(f"S3 업로드 완료: s3://{bucket}/{s3_key}")

        except ImportError:
            logger.error("boto3가 설치되지 않았습니다.")
        except Exception as e:
            logger.error(f"S3 업로드 실패: {e}")

    def _get_content_type(self, file_path: str) -> str:
        """파일 확장자에 따른 Content-Type 반환"""
        ext = Path(file_path).suffix.lower()
        content_types = {
            '.txt': 'text/plain',
            '.json': 'application/json',
            '.sh': 'application/x-sh',
        }
        return content_types.get(ext, 'application/octet-stream')


if __name__ == '__main__':
    # 사용 예시
    exporter = SearchEngineExporter(output_dir="./search_exports")

    # 테스트 데이터
    neologisms = [
        {'word': '갓생', 'frequency': 100, 'type': 'compound'},
        {'word': '갓생활', 'frequency': 50, 'type': 'compound'},
        {'word': '꿀잼', 'frequency': 80, 'type': 'compound'},
        {'word': '핵잼', 'frequency': 70, 'type': 'compound'},
    ]

    synonym_groups = [
        {'갓생', '갓생활'},
        {'꿀잼', '핵잼'},
    ]

    synonym_map = {
        '갓생': ['갓생활'],
        '갓생활': ['갓생'],
        '꿀잼': ['핵잼'],
        '핵잼': ['꿀잼'],
    }

    # 모든 파일 생성
    files = exporter.export_all(
        neologisms,
        synonym_groups,
        synonym_map,
        index_name="neologism_search"
    )

    print("\n=== 생성된 파일 ===")
    for file_type, file_path in files.items():
        print(f"{file_type}: {file_path}")
