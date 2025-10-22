"""
코퍼스(말뭉치) 빌더 모듈
신조어를 정리하여 사전/코퍼스 형태로 저장
"""

import json
import csv
from typing import List, Dict, Optional
from datetime import datetime
import boto3
from pathlib import Path


class CorpusBuilder:
    """
    신조어 코퍼스 빌더
    추출된 신조어를 정리하여 사전 형태로 저장
    """

    def __init__(self, output_dir: str = "./corpus", s3_bucket: Optional[str] = None):
        """
        Args:
            output_dir: 출력 디렉토리
            s3_bucket: S3 버킷 이름 (기존 사전 로드용)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.s3_bucket = s3_bucket
        self.s3_client = boto3.client('s3') if s3_bucket else None

    def build_dictionary(self,
                        neologisms: Dict[str, Dict],
                        metadata: Optional[Dict] = None) -> Dict:
        """
        신조어 사전 생성

        Args:
            neologisms: 신조어 데이터
            metadata: 메타데이터 (수집 날짜, 소스 등)

        Returns:
            사전 구조
        """
        dictionary = {
            'metadata': metadata or {},
            'version': '1.0',
            'created_at': datetime.now().isoformat(),
            'total_words': len(neologisms),
            'words': []
        }

        # 메타데이터 기본값 설정
        if 'created_at' not in dictionary['metadata']:
            dictionary['metadata']['created_at'] = datetime.now().isoformat()

        # 신조어 정리
        for word, stats in neologisms.items():
            entry = {
                'word': word,
                'score': stats.get('score', 0),
                'frequency': stats.get('count', 0),
                'cohesion': stats.get('cohesion', 0),
                'type': stats.get('type', 'unknown'),
                'examples': stats.get('examples', []),
                'first_seen': stats.get('first_seen', dictionary['metadata']['created_at'])
            }
            dictionary['words'].append(entry)

        # 점수 순으로 정렬
        dictionary['words'].sort(key=lambda x: x['score'], reverse=True)

        return dictionary

    def save_json(self, dictionary: Dict, filename: str = "neologism_dict.json"):
        """JSON 형식으로 저장"""
        output_path = self.output_dir / filename

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dictionary, f, ensure_ascii=False, indent=2)

        print(f"사전 저장 완료: {output_path}")
        return str(output_path)

    def save_csv(self, dictionary: Dict, filename: str = "neologism_dict.csv"):
        """CSV 형식으로 저장"""
        output_path = self.output_dir / filename

        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)

            # 헤더
            writer.writerow([
                'word', 'score', 'frequency', 'cohesion', 'type', 'examples'
            ])

            # 데이터
            for entry in dictionary['words']:
                writer.writerow([
                    entry['word'],
                    entry['score'],
                    entry['frequency'],
                    entry['cohesion'],
                    entry['type'],
                    ' | '.join(entry.get('examples', [])[:3])  # 최대 3개 예시
                ])

        print(f"CSV 저장 완료: {output_path}")
        return str(output_path)

    def save_txt(self, dictionary: Dict, filename: str = "neologism_list.txt"):
        """단순 단어 리스트로 저장 (TXT)"""
        output_path = self.output_dir / filename

        with open(output_path, 'w', encoding='utf-8') as f:
            for entry in dictionary['words']:
                f.write(f"{entry['word']}\n")

        print(f"단어 리스트 저장 완료: {output_path}")
        return str(output_path)

    def save_all_formats(self, dictionary: Dict, base_filename: str = "neologism_dict"):
        """모든 포맷으로 저장"""
        results = {}

        results['json'] = self.save_json(dictionary, f"{base_filename}.json")
        results['csv'] = self.save_csv(dictionary, f"{base_filename}.csv")
        results['txt'] = self.save_txt(dictionary, f"{base_filename}_list.txt")

        return results

    def upload_to_s3(self,
                     local_path: str,
                     bucket: str,
                     s3_key: str,
                     region: str = 'ap-northeast-2'):
        """S3에 업로드"""
        s3_client = boto3.client('s3', region_name=region)

        try:
            s3_client.upload_file(local_path, bucket, s3_key)
            print(f"S3 업로드 완료: s3://{bucket}/{s3_key}")
            return f"s3://{bucket}/{s3_key}"
        except Exception as e:
            print(f"S3 업로드 실패: {e}")
            raise

    def merge_dictionaries(self, dict1: Dict, dict2: Dict) -> Dict:
        """
        두 사전 병합

        Args:
            dict1: 기존 사전
            dict2: 새 사전

        Returns:
            병합된 사전
        """
        # 단어를 키로 하는 맵 생성
        word_map = {}

        # 첫 번째 사전
        for entry in dict1.get('words', []):
            word = entry['word']
            word_map[word] = entry

        # 두 번째 사전 (빈도 누적)
        for entry in dict2.get('words', []):
            word = entry['word']
            if word in word_map:
                # 기존 단어: 빈도 누적
                word_map[word]['frequency'] += entry['frequency']
                # 점수는 최대값 사용
                word_map[word]['score'] = max(
                    word_map[word]['score'],
                    entry['score']
                )
                # 예시 추가
                existing_examples = set(word_map[word].get('examples', []))
                new_examples = entry.get('examples', [])
                word_map[word]['examples'] = list(existing_examples.union(new_examples))[:5]
            else:
                # 새 단어
                word_map[word] = entry

        # 병합된 사전 생성
        merged = {
            'metadata': {
                'merged_at': datetime.now().isoformat(),
                'source_dicts': [
                    dict1.get('metadata', {}),
                    dict2.get('metadata', {})
                ]
            },
            'version': '1.0',
            'created_at': datetime.now().isoformat(),
            'total_words': len(word_map),
            'words': list(word_map.values())
        }

        # 점수순 정렬
        merged['words'].sort(key=lambda x: x['score'], reverse=True)

        return merged

    def create_elasticsearch_bulk(self, dictionary: Dict, index_name: str = "neologisms") -> str:
        """
        Elasticsearch Bulk API 형식으로 변환

        Args:
            dictionary: 사전 데이터
            index_name: 인덱스 이름

        Returns:
            Bulk API 포맷 문자열
        """
        bulk_data = []

        for entry in dictionary['words']:
            # Index 메타데이터
            action = {"index": {"_index": index_name, "_id": entry['word']}}
            bulk_data.append(json.dumps(action, ensure_ascii=False))

            # 문서 데이터
            doc = {
                'word': entry['word'],
                'score': entry['score'],
                'frequency': entry['frequency'],
                'cohesion': entry['cohesion'],
                'type': entry['type'],
                'examples': entry.get('examples', []),
                'indexed_at': datetime.now().isoformat()
            }
            bulk_data.append(json.dumps(doc, ensure_ascii=False))

        return '\n'.join(bulk_data) + '\n'

    def save_elasticsearch_bulk(self, dictionary: Dict, filename: str = "neologisms_bulk.ndjson"):
        """Elasticsearch Bulk 형식으로 저장"""
        output_path = self.output_dir / filename
        bulk_data = self.create_elasticsearch_bulk(dictionary)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(bulk_data)

        print(f"Elasticsearch Bulk 파일 저장 완료: {output_path}")
        return str(output_path)

    def load_existing_dictionary(self, source: str = 's3', s3_key: Optional[str] = None) -> Dict:
        """
        기존 사전 로드

        Args:
            source: 's3' 또는 'local'
            s3_key: S3 키 (source='s3'일 때)

        Returns:
            기존 사전 데이터
        """
        if source == 's3':
            if not self.s3_bucket or not s3_key:
                print("S3 버킷 또는 키가 지정되지 않았습니다.")
                return {'words': []}

            try:
                response = self.s3_client.get_object(
                    Bucket=self.s3_bucket,
                    Key=s3_key
                )
                content = response['Body'].read().decode('utf-8')
                existing_dict = json.loads(content)
                print(f"기존 사전 로드 완료: {len(existing_dict.get('words', []))}개 단어")
                return existing_dict
            except Exception as e:
                print(f"기존 사전 로드 실패: {e}")
                return {'words': []}

        elif source == 'local':
            # 로컬에서 최신 파일 찾기
            json_files = list(self.output_dir.glob("neologism_dict*.json"))
            if not json_files:
                print("로컬에 기존 사전이 없습니다.")
                return {'words': []}

            # 가장 최근 파일
            latest_file = max(json_files, key=lambda p: p.stat().st_mtime)
            with open(latest_file, 'r', encoding='utf-8') as f:
                existing_dict = json.load(f)
            print(f"기존 사전 로드 완료: {latest_file}, {len(existing_dict.get('words', []))}개 단어")
            return existing_dict

        return {'words': []}

    def deduplicate_with_existing(self, new_dict: Dict, existing_dict: Dict,
                                   update_strategy: str = 'merge') -> Dict:
        """
        기존 사전과 중복 제거 및 병합

        Args:
            new_dict: 새로 추출된 사전
            existing_dict: 기존 사전
            update_strategy: 'merge' (병합), 'replace' (교체), 'new_only' (신규만)

        Returns:
            중복 제거된 사전
        """
        print(f"\n=== 중복 제거 시작 ===")
        print(f"새 사전: {len(new_dict.get('words', []))}개")
        print(f"기존 사전: {len(existing_dict.get('words', []))}개")

        # 단어별 맵 생성
        existing_words = {w['word']: w for w in existing_dict.get('words', [])}
        new_words = {w['word']: w for w in new_dict.get('words', [])}

        result_words = {}

        if update_strategy == 'merge':
            # 기존 + 새로운 단어 병합
            # 중복 시: 빈도 누적, 점수 최대값 사용
            for word, data in existing_words.items():
                result_words[word] = data.copy()

            for word, new_data in new_words.items():
                if word in result_words:
                    # 중복: 빈도 누적, 점수 갱신
                    result_words[word]['frequency'] += new_data['frequency']
                    result_words[word]['score'] = max(
                        result_words[word]['score'],
                        new_data['score']
                    )
                    # 예시 병합
                    existing_examples = set(result_words[word].get('examples', []))
                    new_examples = set(new_data.get('examples', []))
                    result_words[word]['examples'] = list(existing_examples.union(new_examples))[:5]
                    result_words[word]['last_updated'] = datetime.now().isoformat()
                    print(f"  병합: {word} (빈도: {result_words[word]['frequency']})")
                else:
                    # 신규 단어
                    new_data['first_seen'] = datetime.now().isoformat()
                    result_words[word] = new_data
                    print(f"  신규: {word}")

        elif update_strategy == 'replace':
            # 새 사전으로 완전 교체 (중복 시 새 데이터 우선)
            result_words = existing_words.copy()
            for word, new_data in new_words.items():
                new_data['updated_at'] = datetime.now().isoformat()
                result_words[word] = new_data
                if word in existing_words:
                    print(f"  교체: {word}")
                else:
                    print(f"  신규: {word}")

        elif update_strategy == 'new_only':
            # 신규 단어만 추가
            result_words = existing_words.copy()
            for word, new_data in new_words.items():
                if word not in existing_words:
                    new_data['first_seen'] = datetime.now().isoformat()
                    result_words[word] = new_data
                    print(f"  신규: {word}")

        # 결과 사전 생성
        result_dict = {
            'metadata': {
                'updated_at': datetime.now().isoformat(),
                'update_strategy': update_strategy,
                'previous_count': len(existing_words),
                'new_count': len(new_words),
                'result_count': len(result_words),
            },
            'version': '1.0',
            'created_at': new_dict.get('created_at', datetime.now().isoformat()),
            'total_words': len(result_words),
            'words': list(result_words.values())
        }

        # 점수순 정렬
        result_dict['words'].sort(key=lambda x: x['score'], reverse=True)

        print(f"\n중복 제거 완료:")
        print(f"  - 기존: {len(existing_words)}개")
        print(f"  - 신규: {len(new_words)}개")
        print(f"  - 결과: {len(result_words)}개")
        print(f"  - 추가된 단어: {len(result_words) - len(existing_words)}개")

        return result_dict

    def incremental_update(self, new_neologisms: Dict[str, Dict],
                          existing_dict_key: str = "output/corpus/latest/neologism_dict.json",
                          update_strategy: str = 'merge') -> Dict:
        """
        증분 업데이트: 기존 사전과 병합하여 업데이트

        Args:
            new_neologisms: 새로 추출된 신조어
            existing_dict_key: 기존 사전 S3 키 또는 로컬 경로
            update_strategy: 업데이트 전략

        Returns:
            업데이트된 사전
        """
        # 새 사전 생성
        new_dict = self.build_dictionary(new_neologisms, metadata={
            'extraction_date': datetime.now().isoformat()
        })

        # 기존 사전 로드
        if self.s3_bucket:
            existing_dict = self.load_existing_dictionary('s3', existing_dict_key)
        else:
            existing_dict = self.load_existing_dictionary('local')

        # 중복 제거 및 병합
        updated_dict = self.deduplicate_with_existing(
            new_dict, existing_dict, update_strategy
        )

        return updated_dict
