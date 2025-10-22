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
    'USE_LLM',
    'GENERATE_SYNONYMS',
    'EXPORT_FOR_SEARCH_ENGINE'
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
    args['GENERATE_SYNONYMS'] = 'true'
    args['EXPORT_FOR_SEARCH_ENGINE'] = 'true'

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
GENERATE_SYNONYMS = args.get('GENERATE_SYNONYMS', 'true').lower() == 'true'
EXPORT_FOR_SEARCH_ENGINE = args.get('EXPORT_FOR_SEARCH_ENGINE', 'true').lower() == 'true'

print(f"Job 시작: {args['JOB_NAME']}")
print(f"Input: s3://{INPUT_BUCKET}/{INPUT_PREFIX}")
print(f"Output: s3://{OUTPUT_BUCKET}/{OUTPUT_PREFIX}")
print(f"중복 제거: {ENABLE_DEDUP} (전략: {UPDATE_STRATEGY})")
print(f"뜻 풀이 생성: {GENERATE_DEFINITIONS} (LLM: {USE_LLM})")
print(f"동의어 생성: {GENERATE_SYNONYMS}")
print(f"검색 엔진 export: {EXPORT_FOR_SEARCH_ENGINE}")


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


def generate_synonyms_simple(words, texts=None):
    """
    간단한 동의어 생성 (편집 거리 기반)

    Args:
        words: 단어 리스트
        texts: 원본 텍스트 (공기어 분석용, 선택)

    Returns:
        {word: [synonyms], ...}
    """
    from difflib import SequenceMatcher

    synonym_map = {}

    # 편집 거리 기반 유사 단어 찾기
    for i, word1 in enumerate(words):
        if len(word1) < 2:
            continue

        synonyms = []
        for word2 in words[i+1:]:
            if len(word2) < 2:
                continue

            # 길이 차이가 너무 크면 건너뛰기
            if abs(len(word1) - len(word2)) > 2:
                continue

            # 유사도 계산
            similarity = SequenceMatcher(None, word1, word2).ratio()

            if similarity >= 0.7:  # 70% 이상 유사
                synonyms.append(word2)

        if synonyms:
            synonym_map[word1] = synonyms

    print(f"동의어 생성 완료: {len(synonym_map)}개 단어")
    return synonym_map


def generate_synonym_groups(synonym_map):
    """
    동의어 그룹 생성 (연결된 모든 동의어를 하나의 그룹으로)

    Args:
        synonym_map: {word: [synonyms], ...}

    Returns:
        [{word1, word2, ...}, ...]
    """
    # Union-Find 알고리즘
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
    from collections import defaultdict
    groups = defaultdict(set)
    for word in synonym_map.keys():
        root = find(word)
        groups[root].add(word)

    # 1개 이상의 단어를 가진 그룹만 반환
    result = [group for group in groups.values() if len(group) > 1]
    print(f"동의어 그룹 생성 완료: {len(result)}개 그룹")
    return result


def export_search_engine_files(dictionary, synonym_map, synonym_groups, bucket, prefix):
    """
    검색 엔진용 파일 생성 및 S3 업로드

    Args:
        dictionary: 신조어 사전
        synonym_map: 동의어 매핑
        synonym_groups: 동의어 그룹
        bucket: S3 버킷
        prefix: S3 키 프리픽스
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    search_engine_prefix = f"{prefix}search_engine/{timestamp}/"

    print(f"\n검색 엔진 파일 생성 중... (s3://{bucket}/{search_engine_prefix})")

    # 1. Solr 동의어 파일 (synonyms.txt)
    synonyms_content = []
    for group in synonym_groups:
        if len(group) > 1:
            line = ', '.join(sorted(group))
            synonyms_content.append(line)

    if synonyms_content:
        synonyms_txt = '\n'.join(synonyms_content)
        s3.put_object(
            Bucket=bucket,
            Key=f"{search_engine_prefix}synonyms.txt",
            Body=synonyms_txt.encode('utf-8'),
            ContentType='text/plain'
        )
        print(f"  ✓ synonyms.txt ({len(synonyms_content)} 그룹)")

    # 2. WordNet 동의어 파일 (synonyms_wordnet.txt)
    wordnet_content = []
    for word, synonyms in sorted(synonym_map.items()):
        if synonyms:
            line = f"{word} => {', '.join(synonyms)}"
            wordnet_content.append(line)

    if wordnet_content:
        wordnet_txt = '\n'.join(wordnet_content)
        s3.put_object(
            Bucket=bucket,
            Key=f"{search_engine_prefix}synonyms_wordnet.txt",
            Body=wordnet_txt.encode('utf-8'),
            ContentType='text/plain'
        )
        print(f"  ✓ synonyms_wordnet.txt ({len(wordnet_content)} 매핑)")

    # 3. 사용자 사전 (user_dictionary.txt)
    user_dict_content = '\n'.join([w['word'] for w in dictionary['words']])
    s3.put_object(
        Bucket=bucket,
        Key=f"{search_engine_prefix}user_dictionary.txt",
        Body=user_dict_content.encode('utf-8'),
        ContentType='text/plain'
    )
    print(f"  ✓ user_dictionary.txt ({dictionary['total_words']} 단어)")

    # 4. Nori 사용자 사전 (nori_user_dictionary.txt)
    pos_tag_map = {
        'abbreviation': 'NNP',
        'compound': 'NNG',
        'slang': 'NNG',
        'unknown': 'NNG'
    }

    nori_lines = []
    for word_entry in dictionary['words']:
        word = word_entry['word']
        word_type = word_entry.get('type', 'unknown')
        pos_tag = pos_tag_map.get(word_type, 'NNG')
        nori_lines.append(f"{word} {pos_tag}")

    nori_content = '\n'.join(nori_lines)
    s3.put_object(
        Bucket=bucket,
        Key=f"{search_engine_prefix}nori_user_dictionary.txt",
        Body=nori_content.encode('utf-8'),
        ContentType='text/plain'
    )
    print(f"  ✓ nori_user_dictionary.txt")

    # 5. 인덱스 설정 (index_settings.json)
    index_settings = {
        "settings": {
            "analysis": {
                "tokenizer": {
                    "nori_user_dict": {
                        "type": "nori_tokenizer",
                        "decompound_mode": "mixed",
                        "user_dictionary": "nori_user_dictionary.txt"
                    }
                },
                "filter": {
                    "synonym_filter": {
                        "type": "synonym",
                        "synonyms_path": "synonyms.txt",
                        "updateable": True
                    },
                    "nori_posfilter": {
                        "type": "nori_part_of_speech",
                        "stoptags": [
                            "E", "IC", "J", "MAG", "MAJ",
                            "MM", "SP", "SSC", "SSO", "SC",
                            "SE", "XPN", "XSA", "XSN", "XSV",
                            "UNA", "NA", "VSV"
                        ]
                    }
                },
                "analyzer": {
                    "korean_analyzer": {
                        "type": "custom",
                        "tokenizer": "nori_user_dict",
                        "filter": [
                            "lowercase",
                            "nori_posfilter",
                            "synonym_filter",
                            "nori_readingform"
                        ]
                    }
                }
            },
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 1
            }
        },
        "mappings": {
            "properties": {
                "text": {
                    "type": "text",
                    "analyzer": "korean_analyzer"
                },
                "title": {
                    "type": "text",
                    "analyzer": "korean_analyzer",
                    "fields": {
                        "keyword": {
                            "type": "keyword"
                        }
                    }
                },
                "timestamp": {
                    "type": "date"
                }
            }
        }
    }

    save_to_s3(index_settings, bucket, f"{search_engine_prefix}index_settings.json")
    print(f"  ✓ index_settings.json")

    # 6. README 파일
    readme_content = f"""# 검색 엔진 설정 파일

생성 일시: {datetime.now().isoformat()}
총 단어 수: {dictionary['total_words']}
동의어 그룹: {len(synonym_groups)}

## 파일 목록

1. **synonyms.txt** - Solr 형식 동의어 파일
   - OpenSearch/Elasticsearch synonym filter용
   - 형식: word1, word2, word3

2. **synonyms_wordnet.txt** - WordNet 형식 동의어 파일
   - 형식: word1 => word2, word3

3. **user_dictionary.txt** - 기본 사용자 사전
   - 한 줄에 하나씩 단어 나열

4. **nori_user_dictionary.txt** - Nori Tokenizer용 사용자 사전
   - 품사 태그 포함
   - 형식: word POS_TAG

5. **index_settings.json** - OpenSearch/Elasticsearch 인덱스 설정
   - analyzer, tokenizer, filter 설정 포함

## 사용 방법

### 1. 파일 다운로드
```bash
aws s3 cp s3://{bucket}/{search_engine_prefix} . --recursive
```

### 2. OpenSearch/Elasticsearch config 디렉토리에 복사
```bash
cp synonyms.txt $OPENSEARCH_HOME/config/analysis/
cp nori_user_dictionary.txt $OPENSEARCH_HOME/config/
```

### 3. 인덱스 생성
```bash
curl -X PUT "localhost:9200/neologism_search" \\
  -H 'Content-Type: application/json' \\
  -d @index_settings.json
```

### 4. OpenSearch/Elasticsearch 재시작
```bash
sudo systemctl restart opensearch
```

## 주의사항

- 동의어/사용자 사전 파일을 변경한 후에는 인덱스를 재생성하거나 reload API를 사용해야 합니다.
- synonym filter의 `updateable: true` 설정으로 runtime 업데이트 가능

## 참고

- Nori Tokenizer: https://www.elastic.co/guide/en/elasticsearch/plugins/current/analysis-nori.html
- Synonym Token Filter: https://opensearch.org/docs/latest/analyzers/token-filters/synonym/
"""

    s3.put_object(
        Bucket=bucket,
        Key=f"{search_engine_prefix}README.md",
        Body=readme_content.encode('utf-8'),
        ContentType='text/markdown'
    )
    print(f"  ✓ README.md")

    # 최신 버전도 복사 (latest 디렉토리)
    latest_prefix = f"{prefix}search_engine/latest/"
    print(f"\n최신 버전 복사 중... (s3://{bucket}/{latest_prefix})")

    for filename in ['synonyms.txt', 'synonyms_wordnet.txt', 'user_dictionary.txt',
                     'nori_user_dictionary.txt', 'index_settings.json', 'README.md']:
        source_key = f"{search_engine_prefix}{filename}"
        dest_key = f"{latest_prefix}{filename}"

        s3.copy_object(
            Bucket=bucket,
            CopySource={'Bucket': bucket, 'Key': source_key},
            Key=dest_key
        )

    print(f"검색 엔진 파일 생성 완료!")
    print(f"  - 타임스탬프 버전: s3://{bucket}/{search_engine_prefix}")
    print(f"  - 최신 버전: s3://{bucket}/{latest_prefix}")


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

    # 8. 동의어 생성 및 검색 엔진 파일 export (선택사항)
    if GENERATE_SYNONYMS or EXPORT_FOR_SEARCH_ENGINE:
        print("\n=== 8. 동의어 생성 및 검색 엔진 파일 export ===")

        # 단어 리스트 추출
        words = [w['word'] for w in dictionary['words']]

        # 동의어 생성
        synonym_map = {}
        synonym_groups = []

        if GENERATE_SYNONYMS:
            print("동의어 생성 중...")
            synonym_map = generate_synonyms_simple(words, texts)
            synonym_groups = generate_synonym_groups(synonym_map)

            # 동의어 정보를 사전에 추가
            for word_entry in dictionary['words']:
                word = word_entry['word']
                if word in synonym_map and synonym_map[word]:
                    word_entry['synonyms'] = synonym_map[word]

            # 업데이트된 사전 다시 저장
            save_to_s3(dictionary, OUTPUT_BUCKET, latest_json_key)
            print(f"✓ 동의어 생성 완료: {len(synonym_map)}개 단어, {len(synonym_groups)}개 그룹")

        # 검색 엔진 파일 export
        if EXPORT_FOR_SEARCH_ENGINE:
            print("검색 엔진 파일 생성 중...")
            export_search_engine_files(
                dictionary,
                synonym_map,
                synonym_groups,
                OUTPUT_BUCKET,
                OUTPUT_PREFIX
            )

    # 9. 통계 출력
    print("\n=== 9. 작업 완료 ===")
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
