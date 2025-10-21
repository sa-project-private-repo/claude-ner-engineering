"""
데이터 수집 모듈
SNS, AIHub 등 공공 데이터 소스로부터 데이터를 수집
"""

import os
import json
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import time
import boto3
from abc import ABC, abstractmethod


class BaseCollector(ABC):
    """데이터 수집기 베이스 클래스"""

    @abstractmethod
    def collect(self, **kwargs) -> List[str]:
        """데이터 수집"""
        pass


class AIHubCollector(BaseCollector):
    """
    AIHub 데이터 수집기
    https://aihub.or.kr/
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: AIHub API 키 (환경변수 AIHUB_API_KEY에서도 로드 가능)
        """
        self.api_key = api_key or os.getenv('AIHUB_API_KEY')
        self.base_url = "https://api.aihub.or.kr"

    def collect(self,
                dataset_id: str,
                max_items: int = 1000,
                **kwargs) -> List[str]:
        """
        AIHub에서 데이터 수집

        Args:
            dataset_id: 데이터셋 ID
            max_items: 최대 수집 아이템 수

        Returns:
            텍스트 리스트
        """
        if not self.api_key:
            raise ValueError("AIHub API 키가 필요합니다. AIHUB_API_KEY 환경변수를 설정하세요.")

        texts = []

        # 실제 구현에서는 AIHub API 문서에 따라 구현
        # 여기서는 예시 구조만 제공
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        # Note: 실제 API 엔드포인트는 AIHub 문서 참조
        # 아래는 일반적인 패턴의 예시입니다
        try:
            # 페이징 처리
            page = 1
            page_size = 100

            while len(texts) < max_items:
                params = {
                    'datasetId': dataset_id,
                    'page': page,
                    'pageSize': page_size
                }

                # API 호출 (실제 엔드포인트는 변경 필요)
                # response = requests.get(
                #     f"{self.base_url}/datasets/{dataset_id}/data",
                #     headers=headers,
                #     params=params
                # )

                # if response.status_code != 200:
                #     break

                # data = response.json()
                # items = data.get('items', [])

                # if not items:
                #     break

                # # 텍스트 추출 (데이터셋 구조에 따라 다름)
                # for item in items:
                #     text = item.get('text') or item.get('sentence') or item.get('content')
                #     if text:
                #         texts.append(text)

                # page += 1
                # time.sleep(0.5)  # Rate limiting

                # 임시: API 연동 전 샘플 데이터
                break

        except Exception as e:
            print(f"AIHub 데이터 수집 오류: {e}")

        return texts


class TwitterCollector(BaseCollector):
    """
    Twitter(X) 데이터 수집기
    """

    def __init__(self,
                 bearer_token: Optional[str] = None):
        """
        Args:
            bearer_token: Twitter API Bearer Token
        """
        self.bearer_token = bearer_token or os.getenv('TWITTER_BEARER_TOKEN')
        self.base_url = "https://api.twitter.com/2"

    def collect(self,
                query: str = "lang:ko",
                max_results: int = 1000,
                days_back: int = 7,
                **kwargs) -> List[str]:
        """
        Twitter에서 한국어 트윗 수집

        Args:
            query: 검색 쿼리
            max_results: 최대 결과 수
            days_back: 과거 N일 데이터

        Returns:
            트윗 텍스트 리스트
        """
        if not self.bearer_token:
            print("경고: Twitter Bearer Token이 없습니다. 샘플 데이터를 반환합니다.")
            return self._get_sample_tweets()

        texts = []

        headers = {
            'Authorization': f'Bearer {self.bearer_token}'
        }

        # 시작/종료 시간 설정
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days_back)

        params = {
            'query': query,
            'max_results': min(100, max_results),  # API 한번에 최대 100개
            'start_time': start_time.isoformat() + 'Z',
            'end_time': end_time.isoformat() + 'Z',
            'tweet.fields': 'created_at,lang,text'
        }

        try:
            next_token = None

            while len(texts) < max_results:
                if next_token:
                    params['next_token'] = next_token

                response = requests.get(
                    f"{self.base_url}/tweets/search/recent",
                    headers=headers,
                    params=params
                )

                if response.status_code != 200:
                    print(f"Twitter API 오류: {response.status_code}")
                    break

                data = response.json()
                tweets = data.get('data', [])

                if not tweets:
                    break

                for tweet in tweets:
                    texts.append(tweet['text'])

                # 다음 페이지 토큰
                next_token = data.get('meta', {}).get('next_token')
                if not next_token:
                    break

                time.sleep(1)  # Rate limiting

        except Exception as e:
            print(f"Twitter 데이터 수집 오류: {e}")
            return self._get_sample_tweets()

        return texts

    def _get_sample_tweets(self) -> List[str]:
        """샘플 트윗 데이터 (테스트용)"""
        return [
            "오늘 완전 꿀잼이었어 ㅋㅋㅋ",
            "점메추 좀 해주세요",
            "갓생 살고 싶다",
            "이거 레알 대박",
            "오늘 TMI 하나 풀자면",
            "완전 핵인싸네 ㄷㄷ",
            "JMT 맛집 발견!",
            "오늘 할일 다 끝! 갓생",
            "이번주 불금이다!",
            "월급루팡 중",
        ]


class S3DataCollector(BaseCollector):
    """
    S3에 저장된 데이터 수집기
    """

    def __init__(self, bucket_name: str, region: str = 'ap-northeast-2'):
        """
        Args:
            bucket_name: S3 버킷 이름
            region: AWS 리전
        """
        self.bucket_name = bucket_name
        self.s3_client = boto3.client('s3', region_name=region)

    def collect(self,
                prefix: str = '',
                file_pattern: str = '*.txt',
                max_files: int = 100,
                **kwargs) -> List[str]:
        """
        S3에서 텍스트 파일 수집

        Args:
            prefix: S3 prefix (폴더 경로)
            file_pattern: 파일 패턴
            max_files: 최대 파일 수

        Returns:
            텍스트 리스트
        """
        texts = []

        try:
            # S3 객체 리스트
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_files
            )

            if 'Contents' not in response:
                return texts

            for obj in response['Contents']:
                key = obj['Key']

                # 파일 패턴 체크 (간단한 확장자 체크)
                if not key.endswith('.txt') and not key.endswith('.json'):
                    continue

                # 파일 다운로드
                obj_response = self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=key
                )

                content = obj_response['Body'].read().decode('utf-8')

                # JSON 파일인 경우
                if key.endswith('.json'):
                    data = json.loads(content)
                    # 텍스트 필드 추출 (구조에 따라 조정)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                text = item.get('text') or item.get('content')
                                if text:
                                    texts.append(text)
                            elif isinstance(item, str):
                                texts.append(item)
                    elif isinstance(data, dict):
                        text = data.get('text') or data.get('content')
                        if text:
                            texts.append(text)
                else:
                    # 일반 텍스트 파일
                    # 줄 단위로 분리
                    lines = content.strip().split('\n')
                    texts.extend([line.strip() for line in lines if line.strip()])

        except Exception as e:
            print(f"S3 데이터 수집 오류: {e}")

        return texts


class DataCollector:
    """
    통합 데이터 수집기
    여러 소스에서 데이터를 수집하고 통합
    """

    def __init__(self):
        self.collectors = {}

    def register_collector(self, name: str, collector: BaseCollector):
        """수집기 등록"""
        self.collectors[name] = collector

    def collect_from_all(self, **kwargs) -> Dict[str, List[str]]:
        """모든 등록된 수집기에서 데이터 수집"""
        results = {}

        for name, collector in self.collectors.items():
            try:
                print(f"{name}에서 데이터 수집 중...")
                data = collector.collect(**kwargs)
                results[name] = data
                print(f"{name}: {len(data)}개 수집")
            except Exception as e:
                print(f"{name} 수집 오류: {e}")
                results[name] = []

        return results

    def collect_and_merge(self, **kwargs) -> List[str]:
        """모든 소스에서 데이터를 수집하고 병합"""
        all_data = self.collect_from_all(**kwargs)
        merged = []

        for source, texts in all_data.items():
            merged.extend(texts)

        return merged
