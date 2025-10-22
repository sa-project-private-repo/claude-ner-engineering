# 검색 엔진 통합 가이드

신조어 사전을 OpenSearch/Elasticsearch에 통합하는 방법을 설명합니다.

## 📋 목차

- [개요](#개요)
- [동의어 생성 알고리즘](#동의어-생성-알고리즘)
- [생성되는 파일](#생성되는-파일)
- [OpenSearch/Elasticsearch 설정](#opensearchelasticsearch-설정)
- [사용 예제](#사용-예제)
- [FAQ](#faq)

## 🎯 개요

신조어 추출 파이프라인은 검색 엔진(OpenSearch/Elasticsearch)에 바로 적용할 수 있는 형식으로 결과를 제공합니다:

1. **동의어 파일** - 유사한 신조어들을 동의어로 그룹화
2. **사용자 사전** - Nori Tokenizer가 인식할 수 있는 형태
3. **인덱스 설정** - analyzer, tokenizer, filter 설정 포함

### 주요 기능

✅ **자동 동의어 생성**
- 편집 거리 기반 (변형어 감지)
- 형태소 패턴 기반 (줄임말 구조 유사도)
- 공기어 분석 (문맥 기반 유사도)

✅ **검색 엔진 포맷 자동 변환**
- Solr 동의어 형식
- WordNet 동의어 형식
- Nori 사용자 사전 형식

✅ **즉시 사용 가능한 설정 파일**
- 인덱스 settings & mappings
- analyzer 및 tokenizer 구성
- 설정 스크립트

---

## 🧮 동의어 생성 알고리즘

### 1. 편집 거리 기반 (Levenshtein Distance)

**목적:** 변형어 및 오타 감지

```python
# 예시
"갓생" ↔ "갓생활"  (유사도: 0.75)
"점메추" ↔ "점메뉴추"  (유사도: 0.70)
```

**알고리즘:**
- SequenceMatcher로 유사도 계산
- 임계값 0.7 이상인 경우 동의어로 간주
- 길이 차이가 2 이하인 단어만 비교

**장점:**
- 빠른 처리 속도
- 간단한 구현
- 오타 및 변형어에 효과적

### 2. 형태소 패턴 기반

**목적:** 줄임말의 구조적 유사성 감지

```python
# 예시
"점메추" (점심+메뉴+추천) ↔ "저메추" (저녁+메뉴+추천)
초성 패턴: ㅈㅁㅊ = ㅈㅁㅊ → 유사
```

**알고리즘:**
- 한글 초성 추출
- 초성 패턴 비교
- 50% 이상 일치하면 유사

**장점:**
- 한국어 특성에 최적화
- 줄임말 패턴 인식

### 3. 공기어 분석 (Co-occurrence)

**목적:** 같은 문맥에서 사용되는 단어 감지

```python
# 예시
"꿀잼"과 "핵잼"이 같은 문장에 자주 등장
→ 유사한 의미로 사용됨을 추론
```

**알고리즘:**
- 같은 문장 내 동시 출현 빈도 계산
- 임계값(기본 3회) 이상이면 동의어로 간주

**장점:**
- 의미 기반 유사도
- 사용 패턴 반영

### 4. 의미 임베딩 (선택 사항)

**목적:** Semantic similarity 계산

```python
# sentence-transformers 사용
model = SentenceTransformer('jhgan/ko-sroberta-multitask')
embeddings = model.encode(words)
similarity = cosine_similarity(embeddings)
```

**알고리즘:**
- BERT 기반 임베딩 생성
- 코사인 유사도 계산
- 임계값 0.7 이상이면 동의어

**장점:**
- 가장 정확한 의미 유사도
- 맥락 이해

**단점:**
- 느린 처리 속도
- 높은 리소스 사용

### 종합 전략

**기본 설정 (빠르고 효과적):**
```python
SynonymGenerator(
    edit_distance_threshold=0.7,    # 편집 거리
    cooccurrence_threshold=3,        # 공기어 최소 빈도
    use_semantic=False               # 의미 임베딩 미사용
)
```

**고급 설정 (정확하지만 느림):**
```python
SynonymGenerator(
    edit_distance_threshold=0.7,
    cooccurrence_threshold=3,
    use_semantic=True                # 의미 임베딩 사용
)
```

---

## 📦 생성되는 파일

### 1. synonyms.txt (Solr 형식)

```
갓생, 갓생활
꿀잼, 핵잼
점메추, 저메추
```

**용도:** OpenSearch/Elasticsearch synonym filter

**설정:**
```json
{
  "filter": {
    "synonym_filter": {
      "type": "synonym",
      "synonyms_path": "synonyms.txt"
    }
  }
}
```

### 2. synonyms_wordnet.txt (WordNet 형식)

```
갓생 => 갓생활
꿀잼 => 핵잼
점메추 => 저메추, 점심메뉴추천
```

**용도:** 방향성이 있는 동의어 매핑

### 3. user_dictionary.txt (기본 사용자 사전)

```
갓생
꿀잼
점메추
핵인싸
JMT
```

**용도:** 기본 토크나이저용 사용자 사전

### 4. nori_user_dictionary.txt (Nori Tokenizer용)

```
갓생 NNG
꿀잼 NNG
점메추 NNP
핵인싸 NNG
JMT NNP
```

**용도:** Nori Tokenizer용 사용자 사전 (품사 태그 포함)

**품사 태그:**
- `NNG`: 일반명사 (compound, slang)
- `NNP`: 고유명사 (abbreviation)

### 5. index_settings.json (인덱스 설정)

완전한 OpenSearch/Elasticsearch 인덱스 설정:

```json
{
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
          "updateable": true
        }
      },
      "analyzer": {
        "korean_analyzer": {
          "type": "custom",
          "tokenizer": "nori_user_dict",
          "filter": ["lowercase", "synonym_filter", "nori_readingform"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "text": {
        "type": "text",
        "analyzer": "korean_analyzer"
      }
    }
  }
}
```

### 6. README.md

자세한 사용 방법 및 설명

### 7. setup_index.sh

자동화 스크립트:
```bash
./setup_index.sh https://localhost:9200
```

---

## 🔧 OpenSearch/Elasticsearch 설정

### 방법 1: 자동 설정 (권장)

```bash
# 1. S3에서 파일 다운로드
aws s3 cp s3://your-bucket/output/search_engine/latest/ . --recursive

# 2. 스크립트 실행
chmod +x setup_index.sh
./setup_index.sh https://your-opensearch-url:9200

# 3. 파일 배치 (수동)
cp synonyms.txt /etc/opensearch/analysis/
cp nori_user_dictionary.txt /etc/opensearch/

# 4. OpenSearch 재시작
sudo systemctl restart opensearch
```

### 방법 2: 수동 설정

#### Step 1: 파일 배치

```bash
# OpenSearch
/etc/opensearch/
├── analysis/
│   └── synonyms.txt
├── nori_user_dictionary.txt

# Elasticsearch
/etc/elasticsearch/
├── analysis/
│   └── synonyms.txt
├── nori_user_dictionary.txt
```

#### Step 2: 인덱스 생성

```bash
curl -X PUT "localhost:9200/neologism_search" \
  -H 'Content-Type: application/json' \
  -d @index_settings.json
```

#### Step 3: 동의어 업데이트 (런타임)

```bash
# synonyms.txt 수정 후
curl -X POST "localhost:9200/neologism_search/_reload_search_analyzers"
```

### 방법 3: AWS OpenSearch Service

```bash
# 1. S3에서 패키지 업로드
aws opensearch upload-package \
  --package-name neologism-synonyms \
  --package-type TXT-DICTIONARY \
  --package-source S3BucketName=your-bucket,S3Key=search_engine/latest/synonyms.txt

# 2. 패키지 연결
aws opensearch associate-package \
  --package-id package-id \
  --domain-name your-domain
```

---

## 💡 사용 예제

### 로컬 Python 스크립트

```python
from neologism_extractor import (
    NeologismExtractor,
    SynonymGenerator,
    SearchEngineExporter
)

# 1. 신조어 추출
extractor = NeologismExtractor()
neologisms = extractor.extract_neologisms(texts)

# 2. 동의어 생성
synonym_gen = SynonymGenerator()
synonyms = synonym_gen.generate_synonyms(neologisms, texts)
groups = synonym_gen.generate_synonym_groups(synonyms)

# 3. 검색 엔진 파일 생성
exporter = SearchEngineExporter(output_dir="./search_exports")
files = exporter.export_all(neologisms, groups, synonyms)

print(f"생성된 파일: {files}")
```

### AWS Glue Job (자동)

Glue Job은 기본적으로 검색 엔진 파일을 생성합니다:

```python
# Glue Job 파라미터
--GENERATE_SYNONYMS=true
--EXPORT_FOR_SEARCH_ENGINE=true
```

결과는 S3에 자동 저장:
```
s3://your-bucket/output/search_engine/latest/
├── synonyms.txt
├── synonyms_wordnet.txt
├── user_dictionary.txt
├── nori_user_dictionary.txt
├── index_settings.json
└── README.md
```

### 검색 테스트

```bash
# 인덱스 테스트
curl -X GET "localhost:9200/neologism_search/_analyze" \
  -H 'Content-Type: application/json' \
  -d '{
    "analyzer": "korean_analyzer",
    "text": "갓생 살고 싶어요"
  }'

# 동의어 확인 (갓생 → 갓생활도 검색됨)
curl -X GET "localhost:9200/neologism_search/_search" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {
      "match": {
        "text": "갓생"
      }
    }
  }'
```

---

## 🔍 FAQ

### Q1. 동의어가 너무 많이 생성되는데 어떻게 제어하나요?

**A:** `SynonymGenerator`의 임계값을 조정하세요:

```python
synonym_gen = SynonymGenerator(
    edit_distance_threshold=0.8,  # 더 엄격하게 (기본: 0.7)
    cooccurrence_threshold=5       # 더 높은 빈도 요구 (기본: 3)
)
```

### Q2. 동의어가 너무 적게 생성되는데요?

**A:** 임계값을 낮추거나 의미 임베딩을 사용하세요:

```python
synonym_gen = SynonymGenerator(
    edit_distance_threshold=0.6,  # 더 관대하게
    use_semantic=True              # 의미 기반 추가
)
```

### Q3. OpenSearch에서 동의어가 작동하지 않아요

**A:** 체크리스트:
1. 파일 경로가 올바른지 확인
2. OpenSearch 재시작했는지 확인
3. 인덱스 재생성 또는 reload analyzer 실행
4. 로그 확인: `/var/log/opensearch/`

```bash
# Analyzer 재로드
curl -X POST "localhost:9200/neologism_search/_reload_search_analyzers"
```

### Q4. 실시간으로 동의어를 업데이트하고 싶어요

**A:** `updateable: true` 설정 확인 후 reload API 사용:

```json
{
  "filter": {
    "synonym_filter": {
      "type": "synonym",
      "synonyms_path": "synonyms.txt",
      "updateable": true  // 중요!
    }
  }
}
```

```bash
# 파일 업데이트 후
curl -X POST "localhost:9200/neologism_search/_reload_search_analyzers"
```

### Q5. Nori Tokenizer가 신조어를 인식하지 못해요

**A:** 사용자 사전 경로와 재시작 확인:

```bash
# 1. 파일 확인
ls -la /etc/opensearch/nori_user_dictionary.txt

# 2. 권한 확인
chmod 644 /etc/opensearch/nori_user_dictionary.txt

# 3. 재시작
sudo systemctl restart opensearch

# 4. 토크나이저 테스트
curl -X GET "localhost:9200/neologism_search/_analyze" \
  -d '{"tokenizer": "nori_user_dict", "text": "갓생"}'
```

### Q6. AWS OpenSearch Service에서는 어떻게 사용하나요?

**A:** S3 패키지 업로드 방식 사용:

```bash
# 1. 패키지 생성
aws opensearch create-package \
  --package-name neologism-dict \
  --package-type TXT-DICTIONARY \
  --package-source S3BucketName=your-bucket,S3Key=search_engine/latest/synonyms.txt

# 2. 도메인에 연결
aws opensearch associate-package \
  --package-id F123456789 \
  --domain-name your-domain

# 3. 인덱스 설정에서 참조
{
  "filter": {
    "synonym_filter": {
      "type": "synonym_graph",
      "synonyms_path": "analyzers/neologism-dict"
    }
  }
}
```

### Q7. 성능에 영향이 있나요?

**A:** 동의어 개수에 따라 다릅니다:

- **< 1,000개:** 거의 영향 없음
- **1,000 ~ 10,000개:** 약간의 성능 저하 (5-10%)
- **> 10,000개:** 눈에 띄는 저하 (10-20%)

**최적화 팁:**
- 자주 사용하는 동의어만 포함
- `synonym_graph` 대신 `synonym` 사용
- 인덱스 time이 아닌 query time에 적용

---

## 📚 참고 자료

- [OpenSearch Synonym Token Filter](https://opensearch.org/docs/latest/analyzers/token-filters/synonym/)
- [Elasticsearch Nori Tokenizer](https://www.elastic.co/guide/en/elasticsearch/plugins/current/analysis-nori.html)
- [AWS OpenSearch Custom Packages](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/custom-packages.html)

---

## 🆘 문제 해결

문제가 발생하면:

1. **로그 확인**
   ```bash
   tail -f /var/log/opensearch/opensearch.log
   ```

2. **설정 확인**
   ```bash
   curl -X GET "localhost:9200/neologism_search/_settings?pretty"
   ```

3. **Analyzer 테스트**
   ```bash
   curl -X GET "localhost:9200/neologism_search/_analyze?pretty" \
     -d '{"analyzer": "korean_analyzer", "text": "테스트"}'
   ```

4. **GitHub Issues**: https://github.com/your-repo/issues
