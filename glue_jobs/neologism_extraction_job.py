"""
AWS Glue Job: 신조어 추출 및 코퍼스 생성

이 스크립트는 AWS Glue에서 실행되어 S3의 데이터를 읽고,
신조어를 추출하여 코퍼스를 생성합니다.
"""

import sys
import json
from datetime import datetime
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
import boto3

# 필수 파라미터
required_params = [
    'JOB_NAME',
    'INPUT_BUCKET',
    'INPUT_PREFIX',
    'OUTPUT_BUCKET',
    'OUTPUT_PREFIX',
    'MIN_COUNT',
    'MIN_COHESION'
]

# 선택적 파라미터
optional_params = [
    'ENABLE_DEDUP',
    'UPDATE_STRATEGY',
    'GENERATE_DEFINITIONS',
    'USE_LLM'
]

# 파라미터 파싱 (선택적 파라미터는 기본값 사용)
try:
    args = getResolvedOptions(sys.argv, required_params + optional_params)
except:
    args = getResolvedOptions(sys.argv, required_params)
    # 기본값 설정
    args['ENABLE_DEDUP'] = 'false'
    args['UPDATE_STRATEGY'] = 'merge'
    args['GENERATE_DEFINITIONS'] = 'false'
    args['USE_LLM'] = 'false'

# Spark/Glue 초기화
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# S3 클라이언트
s3 = boto3.client('s3')

# Job 파라미터
INPUT_BUCKET = args['INPUT_BUCKET']
INPUT_PREFIX = args['INPUT_PREFIX']
OUTPUT_BUCKET = args['OUTPUT_BUCKET']
OUTPUT_PREFIX = args['OUTPUT_PREFIX']
MIN_COUNT = int(args.get('MIN_COUNT', '5'))
MIN_COHESION = float(args.get('MIN_COHESION', '0.05'))

# 신기능 파라미터
ENABLE_DEDUP = args.get('ENABLE_DEDUP', 'false').lower() == 'true'
UPDATE_STRATEGY = args.get('UPDATE_STRATEGY', 'merge')
GENERATE_DEFINITIONS = args.get('GENERATE_DEFINITIONS', 'false').lower() == 'true'
USE_LLM = args.get('USE_LLM', 'false').lower() == 'true'

print(f"Job 시작: {args['JOB_NAME']}")
print(f"Input: s3://{INPUT_BUCKET}/{INPUT_PREFIX}")
print(f"Output: s3://{OUTPUT_BUCKET}/{OUTPUT_PREFIX}")
print(f"중복 제거: {ENABLE_DEDUP} (전략: {UPDATE_STRATEGY})")
print(f"뜻 풀이 생성: {GENERATE_DEFINITIONS} (LLM: {USE_LLM})")


def download_package_from_s3(bucket, key, local_path='/tmp/neologism_extractor'):
    """S3에서 Python 패키지 다운로드"""
    import os
    import zipfile

    # 패키지 ZIP 다운로드
    zip_path = '/tmp/package.zip'
    s3.download_file(bucket, key, zip_path)

    # 압축 해제
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(local_path)

    # Python path에 추가
    sys.path.insert(0, local_path)
    print(f"패키지 로드 완료: {local_path}")


def read_texts_from_s3(bucket, prefix):
    """S3에서 텍스트 파일 읽기"""
    texts = []

    # S3 객체 리스트
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

    for page in pages:
        if 'Contents' not in page:
            continue

        for obj in page['Contents']:
            key = obj['Key']

            # 텍스트/JSON 파일만
            if not (key.endswith('.txt') or key.endswith('.json')):
                continue

            print(f"파일 처리 중: {key}")

            # 파일 읽기
            response = s3.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read().decode('utf-8')

            if key.endswith('.json'):
                try:
                    data = json.loads(content)
                    # JSON 구조에 따라 텍스트 추출
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                text = item.get('text') or item.get('content') or item.get('sentence')
                                if text:
                                    texts.append(text)
                            elif isinstance(item, str):
                                texts.append(item)
                    elif isinstance(data, dict):
                        text = data.get('text') or data.get('content') or data.get('sentence')
                        if text:
                            texts.append(text)
                except Exception as e:
                    print(f"JSON 파싱 오류 ({key}): {e}")
            else:
                # 일반 텍스트
                lines = content.strip().split('\n')
                texts.extend([line.strip() for line in lines if line.strip()])

    return texts


def extract_neologisms_simple(texts, min_count=5, min_cohesion=0.05):
    """
    간단한 신조어 추출 (Glue 환경용)

    Note: 실제 환경에서는 soynlp, konlpy 등의 라이브러리가 설치되어야 합니다.
    여기서는 간소화된 버전을 제공합니다.
    """
    from collections import Counter
    import re

    # 단어 빈도 카운트
    word_freq = Counter()

    for text in texts:
        # 간단한 토큰화 (공백 기준)
        words = text.split()
        for word in words:
            # 한글만 추출
            korean_only = re.sub(r'[^가-힣]', '', word)
            if len(korean_only) >= 2:
                word_freq[korean_only] += 1

    # 최소 빈도 필터링
    neologisms = {
        word: {
            'count': count,
            'score': min(count / 100, 1.0),  # 간단한 점수
            'cohesion': 0.5,  # 기본값
            'type': 'unknown'
        }
        for word, count in word_freq.items()
        if count >= min_count
    }

    return neologisms


def extract_neologisms_with_soynlp(texts, min_count=5, min_cohesion=0.05):
    """
    soynlp를 사용한 신조어 추출

    실제 운영 환경에서는 이 함수를 사용하세요.
    Glue Job에 soynlp가 설치되어 있어야 합니다.
    """
    try:
        from soynlp.word import WordExtractor
        from soynlp.normalizer import repeat_normalize
        import re

        # 텍스트 전처리
        preprocessed = []
        for text in texts:
            # URL 제거
            text = re.sub(r'http[s]?://\S+', '', text)
            # 반복 문자 정규화
            text = repeat_normalize(text, num_repeats=2)
            preprocessed.append(text)

        # WordExtractor로 후보 추출
        word_extractor = WordExtractor(
            min_count=min_count,
            min_cohesion_forward=min_cohesion,
            min_right_branching_entropy=0.0
        )

        word_extractor.train(preprocessed)
        words = word_extractor.extract()

        # 결과 정리
        neologisms = {}
        for word, stats in words.items():
            if len(word) < 2 or len(word) > 10:
                continue
            if word.isdigit():
                continue

            neologisms[word] = {
                'count': stats.count,
                'score': stats.cohesion_forward,
                'cohesion': stats.cohesion_forward,
                'type': 'neologism'
            }

        return neologisms

    except ImportError:
        print("soynlp를 사용할 수 없습니다. 간단한 방법을 사용합니다.")
        return extract_neologisms_simple(texts, min_count, min_cohesion)


def build_dictionary(neologisms, metadata=None):
    """신조어 사전 생성"""
    dictionary = {
        'metadata': metadata or {},
        'version': '1.0',
        'created_at': datetime.now().isoformat(),
        'total_words': len(neologisms),
        'words': []
    }

    for word, stats in neologisms.items():
        entry = {
            'word': word,
            'score': stats.get('score', 0),
            'frequency': stats.get('count', 0),
            'cohesion': stats.get('cohesion', 0),
            'type': stats.get('type', 'unknown')
        }
        dictionary['words'].append(entry)

    # 점수순 정렬
    dictionary['words'].sort(key=lambda x: x['score'], reverse=True)

    return dictionary


def generate_simple_definition(word):
    """
    간단한 뜻 풀이 생성 (규칙 기반)
    """
    import re

    # 간단한 규칙 기반
    definition_map = {
        r'.*생$': '삶, 생활과 관련된 신조어',
        r'^갓.*': '최고, 최상급을 의미하는 신조어',
        r'.*추$': '추천의 줄임말',
        r'.*루팡$': '쉽게 보상을 받는 상황을 의미',
        r'ㅇㅈ': '인정의 줄임말',
        r'ㄱㅅ': '감사의 줄임말',
        r'ㅋㅋ': '웃음을 나타내는 표현',
        r'.*잼$': '재미있다는 의미',
    }

    for pattern, meaning in definition_map.items():
        if re.match(pattern, word):
            return meaning

    # 자음만 있는 경우
    if re.match(r'^[ㄱ-ㅎ]+$', word):
        return "[축약어] 의미 미상"

    # 영어 포함
    if re.search(r'[a-zA-Z]', word):
        return "[합성어] 한글과 영어 혼용"

    return "최근 유행하는 신조어"


def deduplicate_with_existing(new_dict, bucket, existing_key, strategy='merge'):
    """
    기존 사전과 중복 제거

    Args:
        new_dict: 새 사전
        bucket: S3 버킷
        existing_key: 기존 사전 S3 키
        strategy: 'merge', 'replace', 'new_only'

    Returns:
        중복 제거된 사전
    """
    print(f"중복 제거 전략: {strategy}")

    # 기존 사전 로드
    try:
        response = s3.get_object(Bucket=bucket, Key=existing_key)
        existing_dict = json.loads(response['Body'].read().decode('utf-8'))
        print(f"기존 사전 로드: {len(existing_dict.get('words', []))}개 단어")
    except Exception as e:
        print(f"기존 사전 없음 또는 로드 실패: {e}")
        return new_dict  # 기존 사전 없으면 그대로 반환

    # 단어별 맵 생성
    existing_words = {w['word']: w for w in existing_dict.get('words', [])}
    new_words = {w['word']: w for w in new_dict.get('words', [])}

    result_words = {}

    if strategy == 'merge':
        # 기존 + 새로운 단어 병합
        for word, data in existing_words.items():
            result_words[word] = data

        for word, new_data in new_words.items():
            if word in result_words:
                # 중복: 빈도 누적
                result_words[word]['frequency'] += new_data['frequency']
                result_words[word]['score'] = max(
                    result_words[word]['score'],
                    new_data['score']
                )
                result_words[word]['last_updated'] = datetime.now().isoformat()
                print(f"  병합: {word}")
            else:
                new_data['first_seen'] = datetime.now().isoformat()
                result_words[word] = new_data
                print(f"  신규: {word}")

    elif strategy == 'new_only':
        result_words = existing_words.copy()
        for word, new_data in new_words.items():
            if word not in existing_words:
                new_data['first_seen'] = datetime.now().isoformat()
                result_words[word] = new_data
                print(f"  신규: {word}")

    # 결과 사전
    result_dict = {
        'metadata': {
            'updated_at': datetime.now().isoformat(),
            'update_strategy': strategy,
            'previous_count': len(existing_words),
            'new_count': len(new_words),
            'result_count': len(result_words),
        },
        'version': new_dict.get('version', '1.0'),
        'created_at': new_dict.get('created_at'),
        'total_words': len(result_words),
        'words': list(result_words.values())
    }

    # 점수순 정렬
    result_dict['words'].sort(key=lambda x: x['score'], reverse=True)

    print(f"중복 제거 완료: {len(existing_words)} → {len(result_words)} ({len(result_words) - len(existing_words):+d})")

    return result_dict


def save_to_s3(data, bucket, key):
    """JSON 데이터를 S3에 저장"""
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json_str.encode('utf-8'),
        ContentType='application/json'
    )
    print(f"저장 완료: s3://{bucket}/{key}")


def main():
    """메인 처리 로직"""

    # 1. S3에서 데이터 읽기
    print("\n=== 1. 데이터 수집 ===")
    texts = read_texts_from_s3(INPUT_BUCKET, INPUT_PREFIX)
    print(f"총 {len(texts)}개의 텍스트 수집 완료")

    if len(texts) == 0:
        print("경고: 수집된 텍스트가 없습니다!")
        return

    # 2. 신조어 추출
    print("\n=== 2. 신조어 추출 ===")
    neologisms = extract_neologisms_with_soynlp(
        texts,
        min_count=MIN_COUNT,
        min_cohesion=MIN_COHESION
    )
    print(f"총 {len(neologisms)}개의 신조어 추출 완료")

    if len(neologisms) == 0:
        print("경고: 추출된 신조어가 없습니다!")
        return

    # 3. 뜻 풀이 생성 (선택사항)
    if GENERATE_DEFINITIONS:
        print("\n=== 3. 뜻 풀이 생성 ===")
        for word, stats in neologisms.items():
            # 간단한 뜻 풀이 생성 (규칙 기반)
            definition = generate_simple_definition(word)
            stats['definition'] = definition
        print(f"✓ {len(neologisms)}개 단어 뜻 풀이 생성 완료")

    # 4. 사전 생성
    print("\n=== 4. 코퍼스 생성 ===")
    metadata = {
        'job_name': args['JOB_NAME'],
        'input_bucket': INPUT_BUCKET,
        'input_prefix': INPUT_PREFIX,
        'total_texts': len(texts),
        'min_count': MIN_COUNT,
        'min_cohesion': MIN_COHESION,
        'enable_dedup': ENABLE_DEDUP,
        'generate_definitions': GENERATE_DEFINITIONS,
        'created_at': datetime.now().isoformat()
    }

    dictionary = build_dictionary(neologisms, metadata)

    # 5. 중복 제거 (선택사항)
    if ENABLE_DEDUP:
        print("\n=== 5. 중복 제거 및 병합 ===")
        dictionary = deduplicate_with_existing(
            dictionary,
            OUTPUT_BUCKET,
            f"{OUTPUT_PREFIX}latest/neologism_dict.json",
            UPDATE_STRATEGY
        )

    # 6. S3에 저장
    print("\n=== 6. 결과 저장 ===")

    # 타임스탬프
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # JSON 저장
    json_key = f"{OUTPUT_PREFIX}neologism_dict_{timestamp}.json"
    save_to_s3(dictionary, OUTPUT_BUCKET, json_key)

    # 단어 리스트 저장
    word_list = '\n'.join([w['word'] for w in dictionary['words']])
    txt_key = f"{OUTPUT_PREFIX}neologism_list_{timestamp}.txt"
    s3.put_object(
        Bucket=OUTPUT_BUCKET,
        Key=txt_key,
        Body=word_list.encode('utf-8'),
        ContentType='text/plain'
    )
    print(f"저장 완료: s3://{OUTPUT_BUCKET}/{txt_key}")

    # 최신 버전도 저장 (링크용)
    latest_json_key = f"{OUTPUT_PREFIX}latest/neologism_dict.json"
    save_to_s3(dictionary, OUTPUT_BUCKET, latest_json_key)

    latest_txt_key = f"{OUTPUT_PREFIX}latest/neologism_list.txt"
    s3.put_object(
        Bucket=OUTPUT_BUCKET,
        Key=latest_txt_key,
        Body=word_list.encode('utf-8'),
        ContentType='text/plain'
    )

    # 7. 의미 사전 저장 (뜻 풀이 생성된 경우)
    if GENERATE_DEFINITIONS:
        print("\n=== 7. 의미 사전 저장 ===")
        semantic_dict_key = f"{OUTPUT_PREFIX}semantic_dict_{timestamp}.json"
        save_to_s3(dictionary, OUTPUT_BUCKET, semantic_dict_key)

        latest_semantic_key = f"{OUTPUT_PREFIX}latest/semantic_dict.json"
        save_to_s3(dictionary, OUTPUT_BUCKET, latest_semantic_key)
        print("✓ 의미 사전 저장 완료")

    # 8. 통계 출력
    print("\n=== 8. 작업 완료 ===")
    print(f"총 단어 수: {dictionary['total_words']}")
    if ENABLE_DEDUP:
        meta = dictionary.get('metadata', {})
        print(f"중복 제거: {meta.get('previous_count', 0)}개 → {meta.get('result_count', 0)}개")
        print(f"신규 추가: {meta.get('result_count', 0) - meta.get('previous_count', 0)}개")

    print(f"\n상위 10개 신조어:")
    for i, word_entry in enumerate(dictionary['words'][:10], 1):
        definition_str = f" - {word_entry.get('definition', '')}" if GENERATE_DEFINITIONS else ""
        print(f"  {i}. {word_entry['word']} (빈도: {word_entry['frequency']}, 점수: {word_entry['score']:.4f}){definition_str}")


# 메인 실행
try:
    main()
    print("\n✓ Job 성공!")
except Exception as e:
    print(f"\n✗ Job 실패: {e}")
    import traceback
    traceback.print_exc()
    raise
finally:
    job.commit()
