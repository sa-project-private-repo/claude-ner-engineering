"""
검색 엔진 통합 예제

이 스크립트는 신조어 추출부터 검색 엔진 파일 생성까지의 전체 프로세스를 보여줍니다.

실행 방법:
    python examples/search_engine_integration_example.py
"""

import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from neologism_extractor import (
    NeologismExtractor,
    CorpusBuilder,
    SynonymGenerator,
    SearchEngineExporter
)


def main():
    print("=" * 60)
    print("검색 엔진 통합 예제")
    print("=" * 60)

    # 1. 샘플 텍스트 데이터
    sample_texts = [
        "오늘은 완전 갓생 살았어요",
        "갓생활을 시작했습니다",
        "이 영화 완전 꿀잼이네요",
        "드라마가 핵잼이에요",
        "점메추 좀 해주세요",
        "저메추 부탁드립니다",
        "갓생 루틴을 만들어야겠어요",
        "꿀잼 영화 추천해주세요",
        "점메추가 너무 어렵네요",
        "핵잼 드라마 찾았어요",
    ] * 10  # 빈도를 높이기 위해 반복

    print(f"\n1. 샘플 데이터: {len(sample_texts)}개 텍스트")

    # 2. 신조어 추출
    print("\n2. 신조어 추출 중...")
    extractor = NeologismExtractor(
        min_count=5,
        min_cohesion=0.05
    )

    neologisms = extractor.extract_neologisms(sample_texts)
    print(f"   ✓ {len(neologisms)}개 신조어 추출 완료")

    # 상위 5개 출력
    print("\n   상위 5개 신조어:")
    for i, item in enumerate(neologisms[:5], 1):
        print(f"     {i}. {item['word']} (빈도: {item['frequency']}, 점수: {item['score']:.4f})")

    # 3. 코퍼스 생성
    print("\n3. 코퍼스 생성 중...")
    builder = CorpusBuilder(output_dir="./output")

    corpus_file = builder.build_corpus(
        neologisms,
        format='json',
        filename='neologism_corpus.json'
    )
    print(f"   ✓ 코퍼스 생성 완료: {corpus_file}")

    # 4. 동의어 생성
    print("\n4. 동의어 생성 중...")
    synonym_gen = SynonymGenerator(
        edit_distance_threshold=0.7,
        cooccurrence_threshold=3
    )

    synonyms = synonym_gen.generate_synonyms(
        neologisms,
        original_texts=sample_texts,
        max_synonyms_per_word=5
    )

    print(f"   ✓ 동의어 생성 완료: {len(synonyms)}개 단어")

    # 동의어 예시 출력
    if synonyms:
        print("\n   동의어 예시:")
        for word, syns in list(synonyms.items())[:5]:
            if syns:
                print(f"     {word} → {', '.join(syns)}")

    # 5. 동의어 그룹 생성
    print("\n5. 동의어 그룹 생성 중...")
    synonym_groups = synonym_gen.generate_synonym_groups(synonyms)
    print(f"   ✓ 동의어 그룹 생성 완료: {len(synonym_groups)}개 그룹")

    # 그룹 예시 출력
    if synonym_groups:
        print("\n   동의어 그룹 예시:")
        for i, group in enumerate(synonym_groups[:3], 1):
            print(f"     그룹 {i}: {', '.join(sorted(group))}")

    # 6. 검색 엔진 파일 생성
    print("\n6. 검색 엔진 파일 생성 중...")
    exporter = SearchEngineExporter(output_dir="./search_engine_exports")

    files = exporter.export_all(
        neologisms,
        synonym_groups,
        synonyms,
        index_name="neologism_search"
    )

    print(f"   ✓ 검색 엔진 파일 생성 완료: {len(files)}개 파일")
    print("\n   생성된 파일:")
    for file_type, file_path in files.items():
        file_size = os.path.getsize(file_path)
        print(f"     - {file_type}: {file_path} ({file_size:,} bytes)")

    # 7. 생성된 파일 미리보기
    print("\n7. 생성된 파일 미리보기")

    # synonyms.txt 미리보기
    print("\n   [synonyms.txt] (처음 5줄)")
    synonyms_file = files.get('synonyms_solr')
    if synonyms_file and os.path.exists(synonyms_file):
        with open(synonyms_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()[:5]
            for line in lines:
                print(f"     {line.strip()}")

    # user_dictionary.txt 미리보기
    print("\n   [user_dictionary.txt] (처음 10줄)")
    user_dict_file = files.get('user_dictionary')
    if user_dict_file and os.path.exists(user_dict_file):
        with open(user_dict_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()[:10]
            for line in lines:
                print(f"     {line.strip()}")

    # 8. 완료
    print("\n" + "=" * 60)
    print("✓ 전체 프로세스 완료!")
    print("=" * 60)
    print("\n생성된 파일을 OpenSearch/Elasticsearch에 적용하려면:")
    print("  1. search_engine_exports/ 디렉토리의 파일들을 확인하세요")
    print("  2. setup_index.sh 스크립트를 실행하세요")
    print("  3. 또는 README.md를 참고하여 수동으로 설정하세요")
    print()


if __name__ == '__main__':
    main()
