"""
코퍼스 빌더 단위 테스트
pytest를 사용하여 CorpusBuilder 기능을 검증합니다.

실행 방법:
    pytest tests/test_corpus_builder.py -v
"""

import pytest
import json
import os
import sys
import tempfile
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from neologism_extractor.corpus_builder import CorpusBuilder


class TestCorpusBuilder:
    """CorpusBuilder 클래스 테스트"""

    @pytest.fixture
    def builder(self, tmp_path):
        """CorpusBuilder 인스턴스 픽스처"""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        return CorpusBuilder(output_dir=str(output_dir))

    @pytest.fixture
    def sample_neologisms(self):
        """테스트용 신조어 데이터"""
        return [
            {
                'word': '갓생',
                'frequency': 10,
                'cohesion': 0.8,
                'left_entropy': 1.2,
                'right_entropy': 1.5,
                'score': 0.75,
                'type': 'compound'
            },
            {
                'word': '꿀잼',
                'frequency': 8,
                'cohesion': 0.7,
                'left_entropy': 1.0,
                'right_entropy': 1.3,
                'score': 0.65,
                'type': 'compound'
            },
            {
                'word': '점메추',
                'frequency': 6,
                'cohesion': 0.6,
                'left_entropy': 0.9,
                'right_entropy': 1.1,
                'score': 0.55,
                'type': 'abbreviation'
            },
        ]

    def test_initialization(self, tmp_path):
        """초기화 테스트"""
        output_dir = tmp_path / "test_output"
        builder = CorpusBuilder(output_dir=str(output_dir))

        assert builder.output_dir == str(output_dir)
        assert output_dir.exists()

    def test_build_corpus_json(self, builder, sample_neologisms):
        """JSON 코퍼스 생성 테스트"""
        output_file = builder.build_corpus(
            sample_neologisms,
            format='json',
            filename='test_corpus.json'
        )

        # 파일 생성 확인
        assert os.path.exists(output_file)

        # 내용 확인
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert 'metadata' in data
        assert 'words' in data
        assert data['total_words'] == len(sample_neologisms)
        assert len(data['words']) == len(sample_neologisms)

        # 첫 번째 단어 확인
        first_word = data['words'][0]
        assert first_word['word'] == '갓생'
        assert first_word['frequency'] == 10

    def test_build_corpus_csv(self, builder, sample_neologisms):
        """CSV 코퍼스 생성 테스트"""
        output_file = builder.build_corpus(
            sample_neologisms,
            format='csv',
            filename='test_corpus.csv'
        )

        # 파일 생성 확인
        assert os.path.exists(output_file)

        # 내용 확인
        with open(output_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 헤더 + 데이터 행 수
        assert len(lines) == len(sample_neologisms) + 1

        # 헤더 확인
        header = lines[0].strip()
        assert 'word' in header
        assert 'frequency' in header
        assert 'cohesion' in header

    def test_build_corpus_txt(self, builder, sample_neologisms):
        """TXT 코퍼스 생성 테스트"""
        output_file = builder.build_corpus(
            sample_neologisms,
            format='txt',
            filename='test_corpus.txt'
        )

        # 파일 생성 확인
        assert os.path.exists(output_file)

        # 내용 확인
        with open(output_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 각 단어가 한 줄씩
        assert len(lines) == len(sample_neologisms)

        # 단어 확인
        words = [line.strip() for line in lines]
        assert '갓생' in words
        assert '꿀잼' in words
        assert '점메추' in words

    def test_build_all_formats(self, builder, sample_neologisms):
        """모든 포맷 동시 생성 테스트"""
        output_files = builder.build_corpus(
            sample_neologisms,
            format='all',
            filename='test_corpus'
        )

        # 딕셔너리 형태로 반환
        assert isinstance(output_files, dict)
        assert 'json' in output_files
        assert 'csv' in output_files
        assert 'txt' in output_files

        # 모든 파일 생성 확인
        for format_type, filepath in output_files.items():
            assert os.path.exists(filepath)

    def test_deduplicate_merge_strategy(self, builder):
        """중복 제거 - merge 전략 테스트"""
        new_dict = {
            '갓생': {'frequency': 10, 'score': 0.8},
            '꿀잼': {'frequency': 5, 'score': 0.6},
        }

        existing_dict = {
            '갓생': {'frequency': 8, 'score': 0.7},
            '핵인싸': {'frequency': 3, 'score': 0.5},
        }

        result = builder.deduplicate_with_existing(
            new_dict,
            existing_dict,
            update_strategy='merge'
        )

        # 갓생: 빈도 누적 (10 + 8 = 18), 점수는 최대값 (0.8)
        assert result['갓생']['frequency'] == 18
        assert result['갓생']['score'] == 0.8

        # 꿀잼: 새로 추가
        assert '꿀잼' in result
        assert result['꿀잼']['frequency'] == 5

        # 핵인싸: 기존 유지
        assert '핵인싸' in result
        assert result['핵인싸']['frequency'] == 3

    def test_deduplicate_new_only_strategy(self, builder):
        """중복 제거 - new_only 전략 테스트"""
        new_dict = {
            '갓생': {'frequency': 10, 'score': 0.8},
            '꿀잼': {'frequency': 5, 'score': 0.6},
        }

        existing_dict = {
            '갓생': {'frequency': 8, 'score': 0.7},
            '핵인싸': {'frequency': 3, 'score': 0.5},
        }

        result = builder.deduplicate_with_existing(
            new_dict,
            existing_dict,
            update_strategy='new_only'
        )

        # 갓생: 이미 존재하므로 기존 값 유지
        assert result['갓생']['frequency'] == 8
        assert result['갓생']['score'] == 0.7

        # 꿀잼: 새로운 단어만 추가
        assert '꿀잼' in result
        assert result['꿀잼']['frequency'] == 5

        # 핵인싸: 기존 유지
        assert '핵인싸' in result

    def test_deduplicate_replace_strategy(self, builder):
        """중복 제거 - replace 전략 테스트"""
        new_dict = {
            '갓생': {'frequency': 10, 'score': 0.8},
            '꿀잼': {'frequency': 5, 'score': 0.6},
        }

        existing_dict = {
            '갓생': {'frequency': 8, 'score': 0.7},
            '핵인싸': {'frequency': 3, 'score': 0.5},
        }

        result = builder.deduplicate_with_existing(
            new_dict,
            existing_dict,
            update_strategy='replace'
        )

        # 완전히 새로운 딕셔너리로 교체
        assert len(result) == 2
        assert '갓생' in result
        assert '꿀잼' in result
        assert '핵인싸' not in result

        # 새 값 사용
        assert result['갓생']['frequency'] == 10

    def test_empty_neologisms(self, builder):
        """빈 신조어 리스트 처리"""
        output_file = builder.build_corpus(
            [],
            format='json',
            filename='empty_corpus.json'
        )

        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert data['total_words'] == 0
        assert len(data['words']) == 0

    def test_incremental_update(self, builder, sample_neologisms, tmp_path):
        """증분 업데이트 테스트"""
        # 기존 사전 생성
        existing_file = tmp_path / "existing_dict.json"
        existing_data = {
            'total_words': 1,
            'words': [
                {
                    'word': '핵인싸',
                    'frequency': 5,
                    'score': 0.5
                }
            ]
        }
        with open(existing_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False)

        # 증분 업데이트 실행
        result_file = builder.incremental_update(
            sample_neologisms,
            str(existing_file),
            update_strategy='merge',
            output_filename='updated_corpus.json'
        )

        # 결과 확인
        with open(result_file, 'r', encoding='utf-8') as f:
            result = json.load(f)

        # 기존 단어 + 새 단어들
        assert result['total_words'] == len(sample_neologisms) + 1

        # 기존 단어 유지 확인
        words = [w['word'] for w in result['words']]
        assert '핵인싸' in words


class TestCorpusBuilderEdgeCases:
    """경계 조건 테스트"""

    def test_invalid_format(self, tmp_path):
        """잘못된 포맷 지정"""
        builder = CorpusBuilder(output_dir=str(tmp_path))

        with pytest.raises(ValueError):
            builder.build_corpus(
                [{'word': 'test', 'frequency': 1}],
                format='invalid_format'
            )

    def test_invalid_strategy(self, tmp_path):
        """잘못된 전략 지정"""
        builder = CorpusBuilder(output_dir=str(tmp_path))

        with pytest.raises(ValueError):
            builder.deduplicate_with_existing(
                {'test': {'frequency': 1}},
                {'test': {'frequency': 2}},
                update_strategy='invalid_strategy'
            )

    def test_nonexistent_existing_file(self, builder, sample_neologisms):
        """존재하지 않는 기존 파일 처리"""
        # 존재하지 않는 파일 경로
        result_file = builder.incremental_update(
            sample_neologisms,
            '/nonexistent/path/dict.json',
            update_strategy='merge'
        )

        # 새로운 딕셔너리로 생성되어야 함
        assert os.path.exists(result_file)

    def test_malformed_existing_file(self, builder, sample_neologisms, tmp_path):
        """잘못된 형식의 기존 파일"""
        malformed_file = tmp_path / "malformed.json"
        with open(malformed_file, 'w') as f:
            f.write("invalid json content")

        # 오류를 처리하고 새로 생성해야 함
        result_file = builder.incremental_update(
            sample_neologisms,
            str(malformed_file),
            update_strategy='merge'
        )

        assert os.path.exists(result_file)


class TestCorpusBuilderMetadata:
    """메타데이터 테스트"""

    def test_metadata_fields(self, tmp_path):
        """메타데이터 필드 확인"""
        builder = CorpusBuilder(output_dir=str(tmp_path))
        neologisms = [
            {
                'word': '테스트',
                'frequency': 10,
                'cohesion': 0.8,
                'score': 0.7,
                'type': 'compound'
            }
        ]

        output_file = builder.build_corpus(
            neologisms,
            format='json',
            filename='test.json'
        )

        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        metadata = data['metadata']
        assert 'created_at' in metadata
        assert 'version' in metadata
        assert 'source' in metadata
        assert 'description' in metadata

    def test_statistics_in_metadata(self, tmp_path):
        """통계 정보 포함 확인"""
        builder = CorpusBuilder(output_dir=str(tmp_path))
        neologisms = [
            {'word': 'A', 'frequency': 10, 'score': 0.9, 'type': 'compound'},
            {'word': 'B', 'frequency': 5, 'score': 0.7, 'type': 'abbreviation'},
            {'word': 'C', 'frequency': 3, 'score': 0.5, 'type': 'slang'},
        ]

        output_file = builder.build_corpus(
            neologisms,
            format='json',
            filename='stats.json'
        )

        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        stats = data['metadata']['statistics']
        assert stats['total_frequency'] == 18  # 10 + 5 + 3
        assert stats['avg_frequency'] == 6.0  # 18 / 3
        assert stats['max_frequency'] == 10
        assert stats['min_frequency'] == 3


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
