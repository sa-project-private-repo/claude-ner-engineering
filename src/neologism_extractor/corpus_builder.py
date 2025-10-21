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

    def __init__(self, output_dir: str = "./corpus"):
        """
        Args:
            output_dir: 출력 디렉토리
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

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
