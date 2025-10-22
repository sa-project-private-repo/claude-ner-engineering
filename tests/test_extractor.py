"""
신조어 추출기 단위 테스트
pytest를 사용하여 NeologismExtractor 기능을 검증합니다.

실행 방법:
    pytest tests/test_extractor.py -v
"""

import pytest
import sys
import os
from typing import List, Dict

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from neologism_extractor.extractor import NeologismExtractor


class TestNeologismExtractor:
    """NeologismExtractor 클래스 테스트"""

    @pytest.fixture
    def extractor(self):
        """Extractor 인스턴스 픽스처"""
        return NeologismExtractor(
            min_count=2,
            min_cohesion=0.05,
            min_word_length=2,
            max_word_length=10
        )

    @pytest.fixture
    def sample_texts(self):
        """테스트용 샘플 텍스트"""
        return [
            "오늘 완전 꿀잼이었어 ㅋㅋㅋ",
            "점메추 좀 해주세요",
            "갓생 살고 싶다 갓생 루틴",
            "이거 레알 대박이야",
            "오늘 TMI 하나 풀자면",
            "완전 핵인싸네 ㄷㄷ",
            "JMT 맛집 발견했어",
            "갓생 살려면 운동해야지",
            "꿀잼 영화 추천해줘",
            "점메추가 너무 어렵다",
        ]

    def test_initialization(self, extractor):
        """초기화 테스트"""
        assert extractor.min_count == 2
        assert extractor.min_cohesion == 0.05
        assert extractor.min_word_length == 2
        assert extractor.max_word_length == 10

    def test_preprocess_text(self, extractor):
        """텍스트 전처리 테스트"""
        text = "https://example.com 완전 꿀잼!! ㅋㅋㅋ"
        processed = extractor.preprocess_text(text)

        # URL 제거 확인
        assert "https://" not in processed
        assert "example.com" not in processed

        # 한글 유지 확인
        assert "완전" in processed
        assert "꿀잼" in processed

    def test_extract_neologisms(self, extractor, sample_texts):
        """신조어 추출 테스트"""
        results = extractor.extract_neologisms(sample_texts)

        # 결과 구조 확인
        assert isinstance(results, list)
        assert len(results) > 0

        # 각 결과 항목 확인
        for item in results:
            assert 'word' in item
            assert 'frequency' in item
            assert 'cohesion' in item
            assert 'score' in item

            # 타입 확인
            assert isinstance(item['word'], str)
            assert isinstance(item['frequency'], int)
            assert isinstance(item['cohesion'], float)
            assert isinstance(item['score'], float)

            # 값 범위 확인
            assert item['frequency'] >= extractor.min_count
            assert len(item['word']) >= extractor.min_word_length

    def test_extract_with_threshold(self, extractor, sample_texts):
        """임계값 필터링 테스트"""
        # 높은 임계값 설정
        strict_extractor = NeologismExtractor(
            min_count=5,
            min_cohesion=0.1
        )

        # 낮은 임계값 결과
        lenient_results = extractor.extract_neologisms(sample_texts)

        # 높은 임계값 결과
        strict_results = strict_extractor.extract_neologisms(sample_texts)

        # 높은 임계값일 때 결과가 더 적어야 함
        assert len(strict_results) <= len(lenient_results)

    def test_classify_neologism_type(self, extractor):
        """신조어 유형 분류 테스트"""
        # 줄임말
        assert extractor.classify_neologism_type("점메추") == "abbreviation"
        assert extractor.classify_neologism_type("TMI") == "abbreviation"

        # 복합어
        assert extractor.classify_neologism_type("꿀잼") == "compound"
        assert extractor.classify_neologism_type("갓생") == "compound"

        # 영문 약어
        assert extractor.classify_neologism_type("JMT") == "abbreviation"

    def test_empty_input(self, extractor):
        """빈 입력 처리 테스트"""
        results = extractor.extract_neologisms([])
        assert isinstance(results, list)
        assert len(results) == 0

    def test_single_text(self, extractor):
        """단일 텍스트 처리 테스트"""
        results = extractor.extract_neologisms(["갓생 살고 싶다"])
        assert isinstance(results, list)
        # 빈도가 1이므로 min_count=2 필터에 의해 결과 없을 수 있음

    def test_special_characters(self, extractor):
        """특수문자 처리 테스트"""
        texts = [
            "!!!완전 대박!!!",
            "????진짜????",
            "ㅋㅋㅋ웃겨ㅋㅋㅋ",
        ]
        # 에러 없이 실행되어야 함
        results = extractor.extract_neologisms(texts)
        assert isinstance(results, list)

    def test_word_length_filtering(self, extractor):
        """단어 길이 필터링 테스트"""
        results = extractor.extract_neologisms([
            "아 아 아 아 아",  # 1글자
            "대박대박 대박대박",  # 2글자
            "완전대박완전대박",  # 4글자 이상
        ])

        for item in results:
            word_len = len(item['word'])
            assert word_len >= extractor.min_word_length
            assert word_len <= extractor.max_word_length

    def test_frequency_count(self, extractor):
        """빈도 계산 정확성 테스트"""
        texts = [
            "갓생 갓생 갓생",
            "갓생을 살자",
            "완전 갓생",
        ]
        results = extractor.extract_neologisms(texts)

        # '갓생'이 추출되었는지 확인
        gat_saeng = [r for r in results if r['word'] == '갓생']
        if len(gat_saeng) > 0:
            # 빈도가 최소 2 이상이어야 함
            assert gat_saeng[0]['frequency'] >= 2


class TestExtractorEdgeCases:
    """경계 조건 및 예외 상황 테스트"""

    def test_very_long_text(self):
        """매우 긴 텍스트 처리"""
        extractor = NeologismExtractor()
        long_text = "갓생을 살자 " * 1000
        results = extractor.extract_neologisms([long_text])
        assert isinstance(results, list)

    def test_only_english(self):
        """영문만 있는 텍스트"""
        extractor = NeologismExtractor()
        results = extractor.extract_neologisms([
            "This is English text only",
            "No Korean characters here"
        ])
        # 한글이 없으므로 결과가 없거나 매우 적음
        assert isinstance(results, list)

    def test_mixed_languages(self):
        """여러 언어 혼합 텍스트"""
        extractor = NeologismExtractor()
        results = extractor.extract_neologisms([
            "Today는 갓생을 살았어요",
            "완전 good vibes",
        ])
        assert isinstance(results, list)

    def test_numbers_in_text(self):
        """숫자 포함 텍스트"""
        extractor = NeologismExtractor()
        results = extractor.extract_neologisms([
            "2024년에는 갓생 살기",
            "100점 만점에 100점",
        ])
        assert isinstance(results, list)

    def test_duplicate_texts(self):
        """중복 텍스트 처리"""
        extractor = NeologismExtractor()
        same_text = "갓생을 살자"
        results = extractor.extract_neologisms([same_text] * 10)

        # 중복으로 인해 빈도가 높아져야 함
        assert isinstance(results, list)
        if len(results) > 0:
            # 최소 한 단어는 높은 빈도를 가져야 함
            max_freq = max(r['frequency'] for r in results)
            assert max_freq >= 2


class TestExtractorIntegration:
    """통합 테스트"""

    def test_full_pipeline(self):
        """전체 파이프라인 테스트"""
        extractor = NeologismExtractor(
            min_count=3,
            min_cohesion=0.05
        )

        # 실제 SNS 스타일 데이터
        texts = [
            "오늘 완전 꿀잼이었어 ㅋㅋㅋ",
            "점메추 좀 해주세요",
            "갓생 살고 싶다",
            "갓생 루틴 시작했어",
            "꿀잼 영화 추천",
            "완전 꿀잼이네",
            "점메추가 어렵다",
            "갓생 살려면 운동",
            "이거 꿀잼 아니냐",
            "점메추 부탁드려요",
        ]

        results = extractor.extract_neologisms(texts)

        # 결과 검증
        assert len(results) > 0

        # 기대되는 신조어들이 포함되어 있는지
        words = [r['word'] for r in results]
        # 빈도가 3 이상인 단어들이 추출되어야 함
        high_freq_words = [r for r in results if r['frequency'] >= 3]
        assert len(high_freq_words) > 0

        # 점수가 내림차순으로 정렬되어 있는지
        scores = [r['score'] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_output_format(self):
        """출력 포맷 일관성 테스트"""
        extractor = NeologismExtractor()
        texts = ["갓생 살자", "갓생 루틴", "완전 갓생"]

        results = extractor.extract_neologisms(texts)

        for item in results:
            # 필수 키 존재 확인
            assert 'word' in item
            assert 'frequency' in item
            assert 'cohesion' in item
            assert 'left_entropy' in item
            assert 'right_entropy' in item
            assert 'score' in item
            assert 'type' in item

            # 타입이 유효한지 확인
            assert item['type'] in ['abbreviation', 'compound', 'slang', 'unknown']


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
