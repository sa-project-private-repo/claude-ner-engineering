#!/usr/bin/env python3
"""
로컬 테스트 스크립트
Jupyter Notebook 없이 간단히 테스트할 수 있습니다.
"""

import sys
sys.path.append('src')

from neologism_extractor import NeologismExtractor, DataCollector, CorpusBuilder
from neologism_extractor.data_collector import TwitterCollector


def main():
    print("=" * 60)
    print("신조어 추출 시스템 - 로컬 테스트")
    print("=" * 60)

    # 1. 데이터 수집
    print("\n[1/4] 데이터 수집 중...")
    collector = DataCollector()
    twitter = TwitterCollector()  # 샘플 데이터 사용
    collector.register_collector('twitter', twitter)

    texts = collector.collect_and_merge()
    print(f"✓ {len(texts)}개의 텍스트 수집 완료")

    # 샘플 데이터 추가 (빈도 증가)
    sample_texts = [
        "오늘 완전 꿀잼이었어 ㅋㅋㅋ",
        "점메추 좀 해주세요",
        "갓생 살고 싶다 진짜",
        "이거 레알 대박이네요",
        "오늘 TMI 하나 풀자면",
        "완전 핵인싸네 ㄷㄷ",
        "JMT 맛집 발견!",
        "갓생 루틴 시작",
        "점메추 어려워",
        "불금 치맥",
    ]
    texts.extend(sample_texts * 10)  # 빈도를 높이기 위해 반복

    # 2. 신조어 추출
    print("\n[2/4] 신조어 추출 중...")
    extractor = NeologismExtractor(
        min_count=3,
        min_cohesion=0.03,
        min_length=2,
        max_length=10
    )

    neologisms = extractor.extract_neologisms(texts)
    print(f"✓ {len(neologisms)}개의 신조어 후보 추출")

    # 3. 코퍼스 생성
    print("\n[3/4] 코퍼스 생성 중...")

    # 유형 분류
    for word, stats in neologisms.items():
        stats['type'] = extractor.classify_neologism_type(word)

    builder = CorpusBuilder(output_dir="./corpus")
    dictionary = builder.build_dictionary(neologisms, metadata={
        'source': 'local_test',
        'total_texts': len(texts)
    })

    # 저장
    saved_files = builder.save_all_formats(dictionary, base_filename="test_neologism_dict")
    print(f"✓ 코퍼스 생성 완료")

    # 4. 결과 출력
    print("\n[4/4] 결과")
    print("-" * 60)
    print(f"총 단어 수: {dictionary['total_words']}")
    print(f"\n상위 20개 신조어:")
    print(f"{'순위':<6} {'단어':<15} {'빈도':<8} {'점수':<10} {'유형':<12}")
    print("-" * 60)

    for i, word_entry in enumerate(dictionary['words'][:20], 1):
        print(f"{i:<6} {word_entry['word']:<15} "
              f"{word_entry['frequency']:<8} "
              f"{word_entry['score']:<10.4f} "
              f"{word_entry['type']:<12}")

    print("\n" + "=" * 60)
    print("저장된 파일:")
    for format_type, path in saved_files.items():
        print(f"  {format_type.upper()}: {path}")

    print("\n✓ 테스트 완료!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n✗ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
