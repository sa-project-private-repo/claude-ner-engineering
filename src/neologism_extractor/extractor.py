"""
신조어 추출 모듈
공공 데이터로부터 신조어를 추출하고 분석하는 기능 제공
"""

import re
from typing import List, Dict, Set, Tuple
from collections import Counter, defaultdict
import numpy as np
from soynlp.word import WordExtractor
from soynlp.normalizer import repeat_normalize
from kiwipiepy import Kiwi


class NeologismExtractor:
    """
    신조어 추출기
    형태소 분석과 통계적 방법을 결합하여 신조어를 탐지합니다.
    """

    def __init__(self,
                 min_count: int = 5,
                 min_cohesion: float = 0.05,
                 min_branching_entropy: float = 0.0,
                 min_length: int = 2,
                 max_length: int = 10):
        """
        Args:
            min_count: 최소 출현 빈도
            min_cohesion: 최소 응집도 (단어 내부 결합력)
            min_branching_entropy: 최소 분기 엔트로피 (좌/우 다양성)
            min_length: 최소 단어 길이
            max_length: 최대 단어 길이
        """
        self.min_count = min_count
        self.min_cohesion = min_cohesion
        self.min_branching_entropy = min_branching_entropy
        self.min_length = min_length
        self.max_length = max_length

        # Kiwi 형태소 분석기 초기화
        self.kiwi = Kiwi()

        # 기존 사전 단어 (비교용)
        self.existing_words = self._load_existing_words()

    def _load_existing_words(self) -> Set[str]:
        """기존 사전 단어 로드"""
        # Kiwi의 기본 사전에서 단어 추출
        try:
            # 기본적인 한국어 단어들
            return set(self.kiwi.extract_words())
        except:
            return set()

    def preprocess_text(self, text: str) -> str:
        """
        텍스트 전처리
        - 반복 문자 정규화
        - URL, 이메일 제거
        - 특수문자 정리
        """
        # URL 제거
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)

        # 이메일 제거
        text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', text)

        # 반복 문자 정규화 (ㅋㅋㅋㅋ -> ㅋㅋ, ㅎㅎㅎ -> ㅎㅎ 등)
        text = repeat_normalize(text, num_repeats=2)

        # 해시태그 보존하면서 정리
        text = re.sub(r'#(\w+)', r'\1', text)

        return text.strip()

    def extract_neologisms(self, texts: List[str]) -> Dict[str, Dict]:
        """
        신조어 추출

        Args:
            texts: 분석할 텍스트 리스트

        Returns:
            신조어 사전 {단어: {score, count, cohesion, ...}}
        """
        # 텍스트 전처리
        preprocessed_texts = [self.preprocess_text(text) for text in texts]

        # soynlp의 WordExtractor로 후보 추출
        word_extractor = WordExtractor(
            min_count=self.min_count,
            min_cohesion_forward=self.min_cohesion,
            min_right_branching_entropy=self.min_branching_entropy
        )

        word_extractor.train(preprocessed_texts)
        words = word_extractor.extract()

        # 신조어 필터링 및 점수 계산
        neologisms = {}

        for word, stats in words.items():
            # 길이 필터
            if len(word) < self.min_length or len(word) > self.max_length:
                continue

            # 숫자만 있는 경우 제외
            if word.isdigit():
                continue

            # 영어만 있는 경우 (선택적)
            if word.isalpha() and word.isascii():
                continue

            # 기존 사전에 없는 단어만 (신조어 판정)
            if word in self.existing_words:
                continue

            # 점수 계산
            cohesion = stats.cohesion_forward
            right_entropy = stats.right_branching_entropy
            left_entropy = stats.left_branching_entropy
            frequency = stats.count

            # 복합 점수 (가중치 적용)
            score = (
                0.3 * cohesion +
                0.3 * right_entropy +
                0.2 * left_entropy +
                0.2 * min(np.log(frequency + 1) / 10, 1.0)
            )

            neologisms[word] = {
                'score': score,
                'count': frequency,
                'cohesion': cohesion,
                'right_entropy': right_entropy,
                'left_entropy': left_entropy
            }

        # 점수 기준으로 정렬
        neologisms = dict(sorted(neologisms.items(),
                                key=lambda x: x[1]['score'],
                                reverse=True))

        return neologisms

    def extract_with_context(self, texts: List[str], top_n: int = 100) -> List[Dict]:
        """
        문맥과 함께 신조어 추출

        Args:
            texts: 분석할 텍스트 리스트
            top_n: 상위 N개 신조어

        Returns:
            신조어 정보 리스트 (문맥 예시 포함)
        """
        neologisms = self.extract_neologisms(texts)

        # 상위 N개만 선택
        top_neologisms = list(neologisms.items())[:top_n]

        # 각 신조어에 대한 문맥 예시 찾기
        result = []
        for word, stats in top_neologisms:
            examples = []
            for text in texts:
                if word in text:
                    # 문맥 추출 (앞뒤 50자)
                    idx = text.find(word)
                    start = max(0, idx - 50)
                    end = min(len(text), idx + len(word) + 50)
                    context = text[start:end]
                    examples.append(context)

                    if len(examples) >= 3:  # 최대 3개 예시
                        break

            result.append({
                'word': word,
                'score': stats['score'],
                'count': stats['count'],
                'cohesion': stats['cohesion'],
                'examples': examples
            })

        return result

    def classify_neologism_type(self, word: str) -> str:
        """
        신조어 유형 분류

        Returns:
            - 'abbreviation': 축약어 (ㅇㅈ, ㄱㅅ 등)
            - 'compound': 합성어
            - 'loanword': 외래어
            - 'slang': 신조 은어
            - 'other': 기타
        """
        # 자음만 있는 경우 (축약어)
        if re.match(r'^[ㄱ-ㅎ]+$', word):
            return 'abbreviation'

        # 영어 혼용
        if re.search(r'[a-zA-Z]', word) and re.search(r'[가-힣]', word):
            return 'compound'

        # 영어만
        if word.isalpha() and not word.isascii() == False:
            return 'loanword'

        # Kiwi로 형태소 분석
        try:
            result = self.kiwi.tokenize(word)
            if len(result) > 1:
                return 'compound'
        except:
            pass

        return 'slang'
