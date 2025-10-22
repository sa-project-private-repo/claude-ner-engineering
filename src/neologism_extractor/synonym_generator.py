"""
동의어 생성기 (Synonym Generator)

검색 엔진(OpenSearch/Elasticsearch)을 위한 동의어를 생성합니다.
한국어 신조어의 특성을 고려한 다양한 알고리즘을 제공합니다.

지원하는 방법:
1. 편집 거리 기반 (Levenshtein Distance) - 변형어, 오타 감지
2. 형태소 패턴 기반 - 줄임말 구조 유사도
3. 공기어 분석 (Co-occurrence) - 문맥 기반 유사도
4. 의미 임베딩 (선택) - Semantic similarity
"""

import re
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict, Counter
import json
from difflib import SequenceMatcher
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SynonymGenerator:
    """
    신조어 동의어 생성기

    여러 알고리즘을 조합하여 동의어를 추출합니다.
    """

    def __init__(
        self,
        edit_distance_threshold: float = 0.7,  # 편집 거리 유사도 임계값
        cooccurrence_threshold: int = 3,       # 공기어 최소 빈도
        min_word_length: int = 2,              # 최소 단어 길이
        use_semantic: bool = False              # 의미 임베딩 사용 여부
    ):
        """
        Args:
            edit_distance_threshold: 편집 거리 유사도 임계값 (0.0-1.0)
            cooccurrence_threshold: 공기어로 간주할 최소 빈도
            min_word_length: 동의어로 고려할 최소 단어 길이
            use_semantic: sentence-transformers 사용 여부 (선택)
        """
        self.edit_distance_threshold = edit_distance_threshold
        self.cooccurrence_threshold = cooccurrence_threshold
        self.min_word_length = min_word_length
        self.use_semantic = use_semantic

        if use_semantic:
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer('jhgan/ko-sroberta-multitask')
                logger.info("Semantic similarity 모델 로드 완료")
            except ImportError:
                logger.warning("sentence-transformers 미설치. 의미 기반 유사도 비활성화")
                self.use_semantic = False

    def generate_synonyms(
        self,
        neologisms: List[Dict],
        original_texts: Optional[List[str]] = None,
        max_synonyms_per_word: int = 5
    ) -> Dict[str, List[str]]:
        """
        동의어 생성 (모든 알고리즘 조합)

        Args:
            neologisms: 신조어 리스트 [{'word': str, 'frequency': int, ...}, ...]
            original_texts: 원본 텍스트 (공기어 분석용, 선택)
            max_synonyms_per_word: 단어당 최대 동의어 개수

        Returns:
            {word: [synonym1, synonym2, ...], ...}
        """
        logger.info(f"동의어 생성 시작: {len(neologisms)}개 단어")

        synonym_map = defaultdict(set)
        words = [item['word'] for item in neologisms]

        # 1. 편집 거리 기반 유사 단어
        logger.info("1/4: 편집 거리 기반 동의어 추출...")
        edit_distance_synonyms = self._find_edit_distance_synonyms(words)
        for word, syns in edit_distance_synonyms.items():
            synonym_map[word].update(syns)

        # 2. 형태소 패턴 기반 유사 단어
        logger.info("2/4: 형태소 패턴 기반 동의어 추출...")
        pattern_synonyms = self._find_pattern_based_synonyms(neologisms)
        for word, syns in pattern_synonyms.items():
            synonym_map[word].update(syns)

        # 3. 공기어 분석 (원본 텍스트가 있는 경우)
        if original_texts:
            logger.info("3/4: 공기어 분석 기반 동의어 추출...")
            cooccurrence_synonyms = self._find_cooccurrence_synonyms(
                words, original_texts
            )
            for word, syns in cooccurrence_synonyms.items():
                synonym_map[word].update(syns)

        # 4. 의미 임베딩 (선택)
        if self.use_semantic:
            logger.info("4/4: 의미 임베딩 기반 동의어 추출...")
            semantic_synonyms = self._find_semantic_synonyms(words)
            for word, syns in semantic_synonyms.items():
                synonym_map[word].update(syns)

        # 결과 정리: 자기 자신 제거, 최대 개수 제한
        result = {}
        for word, syns in synonym_map.items():
            syns.discard(word)  # 자기 자신 제거
            result[word] = list(syns)[:max_synonyms_per_word]

        logger.info(f"동의어 생성 완료: {len(result)}개 단어, "
                   f"평균 {sum(len(v) for v in result.values()) / len(result):.1f}개 동의어")

        return result

    def _calculate_similarity(self, word1: str, word2: str) -> float:
        """
        두 단어의 편집 거리 기반 유사도 계산

        Returns:
            0.0 ~ 1.0 (1.0이 가장 유사)
        """
        return SequenceMatcher(None, word1, word2).ratio()

    def _find_edit_distance_synonyms(
        self,
        words: List[str]
    ) -> Dict[str, List[str]]:
        """
        편집 거리 기반 동의어 찾기

        예: "갓생" ↔ "갓생활", "점메추" ↔ "점메뉴추"
        """
        synonyms = defaultdict(list)

        for i, word1 in enumerate(words):
            if len(word1) < self.min_word_length:
                continue

            for word2 in words[i+1:]:
                if len(word2) < self.min_word_length:
                    continue

                # 길이 차이가 너무 크면 건너뛰기
                if abs(len(word1) - len(word2)) > 2:
                    continue

                similarity = self._calculate_similarity(word1, word2)

                if similarity >= self.edit_distance_threshold:
                    synonyms[word1].append(word2)
                    synonyms[word2].append(word1)

        return synonyms

    def _find_pattern_based_synonyms(
        self,
        neologisms: List[Dict]
    ) -> Dict[str, List[str]]:
        """
        형태소 패턴 기반 동의어 찾기

        줄임말의 구조적 유사성을 이용:
        - "점메추" (점심+메뉴+추천) ↔ "저메추" (저녁+메뉴+추천)
        - 같은 type의 단어들 중 패턴이 유사한 것
        """
        synonyms = defaultdict(list)

        # type별로 그룹화
        by_type = defaultdict(list)
        for item in neologisms:
            word_type = item.get('type', 'unknown')
            by_type[word_type].append(item)

        # 같은 타입 내에서 패턴 유사도 확인
        for word_type, items in by_type.items():
            if word_type == 'abbreviation':
                # 줄임말의 경우 특별 처리
                for i, item1 in enumerate(items):
                    word1 = item1['word']
                    if len(word1) < 2:
                        continue

                    for item2 in items[i+1:]:
                        word2 = item2['word']
                        if len(word2) < 2:
                            continue

                        # 같은 길이의 줄임말
                        if len(word1) == len(word2):
                            # 자음 패턴 유사도 체크
                            if self._check_consonant_pattern_similarity(word1, word2):
                                synonyms[word1].append(word2)
                                synonyms[word2].append(word1)

        return synonyms

    def _check_consonant_pattern_similarity(
        self,
        word1: str,
        word2: str
    ) -> bool:
        """
        자음 패턴 유사도 체크

        예: "점메추" (ㅈㅁㅊ) vs "저메추" (ㅈㅁㅊ) → True
        """
        # 한글 초성 추출
        cho = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ',
               'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']

        def get_chosung(char):
            if '가' <= char <= '힣':
                return cho[(ord(char) - ord('가')) // 588]
            return char

        pattern1 = ''.join(get_chosung(c) for c in word1)
        pattern2 = ''.join(get_chosung(c) for c in word2)

        # 패턴이 절반 이상 일치하면 유사
        matches = sum(1 for c1, c2 in zip(pattern1, pattern2) if c1 == c2)
        return matches >= len(pattern1) * 0.5

    def _find_cooccurrence_synonyms(
        self,
        words: List[str],
        texts: List[str]
    ) -> Dict[str, List[str]]:
        """
        공기어 분석 기반 동의어 찾기

        같은 문맥에서 자주 등장하는 단어들을 동의어로 간주
        예: "꿀잼" ↔ "핵잼" (둘 다 "영화", "드라마"와 함께 등장)
        """
        synonyms = defaultdict(list)

        # 각 단어가 등장하는 문장 수집
        word_contexts = defaultdict(list)

        for text in texts:
            # 문장에 어떤 신조어들이 포함되어 있는지
            words_in_text = [w for w in words if w in text]

            for word in words_in_text:
                word_contexts[word].append(text)

        # 공기어 행렬 구축
        cooccurrence = defaultdict(lambda: defaultdict(int))

        for text in texts:
            words_in_text = [w for w in words if w in text]

            # 같은 문장에 등장하는 단어 쌍
            for i, word1 in enumerate(words_in_text):
                for word2 in words_in_text[i+1:]:
                    cooccurrence[word1][word2] += 1
                    cooccurrence[word2][word1] += 1

        # 임계값 이상 함께 등장하는 단어를 동의어로
        for word1, cooccur_dict in cooccurrence.items():
            for word2, count in cooccur_dict.items():
                if count >= self.cooccurrence_threshold:
                    synonyms[word1].append(word2)

        return synonyms

    def _find_semantic_synonyms(
        self,
        words: List[str],
        similarity_threshold: float = 0.7
    ) -> Dict[str, List[str]]:
        """
        의미 임베딩 기반 동의어 찾기 (sentence-transformers)

        BERT 기반 의미 유사도 계산
        """
        if not self.use_semantic:
            return {}

        synonyms = defaultdict(list)

        try:
            # 단어 임베딩 생성
            embeddings = self.model.encode(words)

            # 코사인 유사도 계산
            from sklearn.metrics.pairwise import cosine_similarity
            similarity_matrix = cosine_similarity(embeddings)

            # 유사도가 높은 쌍 추출
            for i, word1 in enumerate(words):
                for j, word2 in enumerate(words[i+1:], start=i+1):
                    if similarity_matrix[i][j] >= similarity_threshold:
                        synonyms[word1].append(word2)
                        synonyms[word2].append(word1)

        except Exception as e:
            logger.error(f"의미 임베딩 오류: {e}")

        return synonyms

    def generate_synonym_groups(
        self,
        synonym_map: Dict[str, List[str]]
    ) -> List[Set[str]]:
        """
        동의어 그룹 생성 (연결된 모든 동의어를 하나의 그룹으로)

        예: {A: [B], B: [A, C], C: [B]} → {A, B, C}

        Args:
            synonym_map: 단어별 동의어 매핑

        Returns:
            동의어 그룹 리스트
        """
        # Union-Find 알고리즘 사용
        parent = {}

        def find(x):
            if x not in parent:
                parent[x] = x
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        # 동의어 관계를 union
        for word, synonyms in synonym_map.items():
            for syn in synonyms:
                union(word, syn)

        # 그룹화
        groups = defaultdict(set)
        for word in synonym_map.keys():
            root = find(word)
            groups[root].add(word)

        # Set 리스트로 반환
        return [group for group in groups.values() if len(group) > 1]


if __name__ == '__main__':
    # 사용 예시
    generator = SynonymGenerator(
        edit_distance_threshold=0.7,
        cooccurrence_threshold=2
    )

    # 테스트 데이터
    neologisms = [
        {'word': '갓생', 'frequency': 100, 'type': 'compound'},
        {'word': '갓생활', 'frequency': 50, 'type': 'compound'},
        {'word': '꿀잼', 'frequency': 80, 'type': 'compound'},
        {'word': '핵잼', 'frequency': 70, 'type': 'compound'},
        {'word': '점메추', 'frequency': 60, 'type': 'abbreviation'},
        {'word': '저메추', 'frequency': 40, 'type': 'abbreviation'},
    ]

    texts = [
        "오늘은 갓생 살았어",
        "갓생활을 시작했다",
        "이 영화 완전 꿀잼",
        "드라마가 핵잼이네",
        "점메추 좀 해주세요",
        "저메추 부탁드려요",
    ]

    # 동의어 생성
    synonyms = generator.generate_synonyms(neologisms, texts)

    print("=== 동의어 매핑 ===")
    for word, syns in synonyms.items():
        if syns:
            print(f"{word}: {', '.join(syns)}")

    # 동의어 그룹
    groups = generator.generate_synonym_groups(synonyms)
    print("\n=== 동의어 그룹 ===")
    for i, group in enumerate(groups, 1):
        print(f"그룹 {i}: {', '.join(sorted(group))}")
