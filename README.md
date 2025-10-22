# 신조어 추출 및 코퍼스 생성 시스템

공공 데이터(SNS, AIHub)에서 한국어 신조어를 자동으로 추출하고 검색 서비스에 활용할 수 있는 코퍼스(말뭉치)를 생성하는 시스템입니다.

## 주요 기능

### ✨ v0.2.0 신기능
- **증분 업데이트**: 기존 사전과 자동 병합, 중복 제거
- **뜻 풀이 자동 생성**: 신조어 의미 사전 생성 (규칙 기반 + 선택적 LLM)
- **유연한 스케줄링**: 일일/주간/월간 자동 실행 설정

### 핵심 기능
- **자동 데이터 수집**: Twitter, AIHub 등 다양한 소스에서 텍스트 수집
- **신조어 추출**: NLP 기술(soynlp, konlpy)을 활용한 신조어 탐지
- **코퍼스 생성**: JSON, CSV, TXT 등 다양한 포맷으로 사전 생성
- **자동화 파이프라인**: AWS Glue + MWAA로 일일 자동 실행
- **테스트 환경**: Jupyter Notebook으로 간편한 테스트 및 검증

## 아키텍처

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Twitter   │────▶│  AWS Lambda  │────▶│     S3      │
│   AIHub     │     │  Data Collect│     │  Raw Data   │
└─────────────┘     └──────────────┘     └─────────────┘
                                                 │
                                                 ▼
                                          ┌─────────────┐
                                          │  AWS Glue   │
                                          │  ETL Job    │
                                          └─────────────┘
                                                 │
                                                 ▼
                                          ┌─────────────┐
                                          │     S3      │
                                          │   Corpus    │
                                          └─────────────┘
                                                 │
┌─────────────┐                                 │
│    MWAA     │─────────────────────────────────┘
│  (Airflow)  │  스케줄링 및 모니터링
└─────────────┘
```

## 프로젝트 구조

```
claude-ner-engineering/
├── src/
│   └── neologism_extractor/      # 핵심 로직
│       ├── extractor.py          # 신조어 추출기
│       ├── data_collector.py     # 데이터 수집기
│       └── corpus_builder.py     # 코퍼스 빌더
├── notebooks/
│   └── neologism_extraction_test.ipynb  # 테스트 노트북
├── glue_jobs/
│   └── neologism_extraction_job.py      # Glue ETL 스크립트
├── airflow/
│   └── dags/
│       └── neologism_extraction_dag.py  # Airflow DAG
├── cdk/
│   ├── app.py                    # CDK 앱
│   └── stacks/
│       ├── glue_stack.py         # Glue 인프라
│       └── mwaa_stack.py         # MWAA 인프라
├── requirements.txt
└── README.md
```

## 빠른 시작

### 1. 환경 설정

```bash
# Python 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 패키지 설치 (개발 모드)
pip install -e .
```

### 2. Jupyter Notebook으로 테스트

```bash
# Jupyter 실행
jupyter notebook notebooks/neologism_extraction_test.ipynb
```

노트북에서 다음을 테스트할 수 있습니다:
- 데이터 수집
- 신조어 추출
- 코퍼스 생성
- 결과 시각화

### 3. AWS 인프라 배포

```bash
cd cdk

# CDK 의존성 설치
pip install -r requirements.txt

# AWS 계정 부트스트랩 (최초 1회)
cdk bootstrap

# 스택 배포
cdk deploy --all

# 또는 개별 배포
cdk deploy NeologismGlueStack
cdk deploy NeologismMwaaStack
```

배포 후 출력되는 정보:
- S3 버킷 이름
- Glue Job 이름
- MWAA 환경 URL

### 4. Airflow 설정

1. MWAA 웹 UI 접속 (CDK 출력 참조)
2. Admin > Variables에서 다음 변수 설정:

```
neologism_s3_bucket: <data-bucket-name>
neologism_input_prefix: input/raw-texts/
neologism_output_prefix: output/corpus/
neologism_glue_job: neologism-extraction-job
aws_region: ap-northeast-2
```

3. (선택) Twitter/AIHub API 키 설정:
```
twitter_bearer_token: <your-token>
aihub_api_key: <your-key>
```

### 5. DAG 실행

Airflow UI에서:
1. `neologism_extraction_pipeline` DAG 활성화
2. 수동 실행 또는 스케줄에 따라 자동 실행

## 사용 방법

### Python 코드로 직접 사용

```python
from neologism_extractor import NeologismExtractor, DataCollector, CorpusBuilder

# 1. 데이터 수집
collector = DataCollector()
# ... 수집기 등록 ...
texts = collector.collect_and_merge()

# 2. 신조어 추출
extractor = NeologismExtractor(min_count=5)
neologisms = extractor.extract_neologisms(texts)

# 3. 코퍼스 생성
builder = CorpusBuilder(output_dir="./corpus")
dictionary = builder.build_dictionary(neologisms)
builder.save_all_formats(dictionary)
```

### Glue Job 직접 실행

AWS CLI로:
```bash
aws glue start-job-run \
  --job-name neologism-extraction-job \
  --arguments '{
    "--INPUT_BUCKET":"your-bucket",
    "--INPUT_PREFIX":"input/",
    "--OUTPUT_BUCKET":"your-bucket",
    "--OUTPUT_PREFIX":"output/",
    "--MIN_COUNT":"5"
  }'
```

## 출력 형식

### JSON (neologism_dict.json)
```json
{
  "metadata": {
    "created_at": "2024-01-01T00:00:00",
    "source": "Twitter, AIHub",
    "total_texts": 1000
  },
  "total_words": 100,
  "words": [
    {
      "word": "갓생",
      "score": 0.85,
      "frequency": 150,
      "cohesion": 0.7,
      "type": "neologism",
      "examples": ["갓생 살고 싶다", "...]
    }
  ]
}
```

### CSV (neologism_dict.csv)
```csv
word,score,frequency,cohesion,type,examples
갓생,0.85,150,0.7,neologism,"갓생 살고 싶다 | ..."
```

### TXT (neologism_list.txt)
```
갓생
점메추
꿀잼
...
```

### 의미 사전 (semantic_dict.json) ✨ NEW
```json
{
  "title": "신조어 의미 사전",
  "total_entries": 100,
  "entries": [
    {
      "word": "갓생",
      "definition": "최고, 최상급을 의미하는 신조어",
      "type": "compound",
      "frequency": 150,
      "examples": ["갓생 살고 싶다", "오늘부터 갓생"]
    },
    {
      "word": "점메추",
      "definition": "추천의 줄임말",
      "type": "abbreviation",
      "frequency": 120
    }
  ]
}
```

## 증분 업데이트 (중복 제거)

### 동작 방식

```
Day 1: 100개 신조어 추출 → 저장
Day 2: 25개 신조어 추출 (5개 중복, 20개 신규)
  → 기존 100개 + 신규 20개 = 120개
  → 중복 5개는 빈도 누적
```

### 업데이트 전략

| 전략 | 설명 | 사용 사례 |
|------|------|-----------|
| **merge** | 기존 + 신규 병합, 빈도 누적 | 일일 업데이트 (권장) |
| **new_only** | 신규만 추가 | 새 단어만 추적 |
| **replace** | 완전 교체 | 전체 재계산 |

## 스케줄링

### 기본 설정: 매일 오전 2시 (UTC)

```python
schedule_interval='0 2 * * *'  # 한국 시간 오전 11시
```

### 변경 가능 패턴

| 패턴 | 실행 주기 |
|------|----------|
| `0 2 * * *` | 매일 |
| `0 2 * * 1` | 매주 월요일 |
| `0 2 1 * *` | 매월 1일 |
| `0 */6 * * *` | 6시간마다 |

📚 **상세 가이드**: [SCHEDULING.md](docs/SCHEDULING.md)

## 신조어 추출 알고리즘

### ⚡ 핵심: 통계적 비지도 학습 (NLP)

**사용 기술**: soynlp WordExtractor + 형태소 분석 (kiwipiepy)

> ❌ CNN (딥러닝) 아님
> ❌ NER (개체명 인식) 아님
> ✅ **통계적 자연어 처리 (NLP)**

📚 **상세 설명**: [ALGORITHM.md](docs/ALGORITHM.md) | [비교 문서](docs/COMPARISON.md)

### 알고리즘 단계

1. **텍스트 전처리**
   - URL, 이메일 제거
   - 반복 문자 정규화 (ㅋㅋㅋㅋ → ㅋㅋ)
   - 해시태그 처리

2. **통계적 후보 추출** (soynlp)
   - **응집도(Cohesion)**: 단어 내부 결합력 측정
     - 예: "갓생" = "갓" + "생"의 결합 강도
   - **분기 엔트로피(Branching Entropy)**: 단어 경계 판단
     - 좌우 문맥의 다양성으로 독립 단어 여부 판단

3. **필터링**
   - 최소 빈도 (기본: 5회)
   - 길이 제한 (2-10글자)
   - 기존 사전과 비교

4. **점수 계산** (가중 평균)
   ```
   score = 0.3 × cohesion +        # 응집도
           0.3 × right_entropy +   # 우측 엔트로피
           0.2 × left_entropy +    # 좌측 엔트로피
           0.2 × log(frequency)    # 빈도 (정규화)
   ```

### 왜 통계적 방법인가?

| 특징 | 통계적 (우리) | 딥러닝 (CNN) |
|------|--------------|-------------|
| 레이블 데이터 | 불필요 ✅ | 필수 ❌ |
| 새 신조어 발견 | 즉시 ✅ | 재학습 필요 ❌ |
| 처리 속도 | 빠름 ✅ | 느림 ❌ |
| 설명 가능성 | 높음 ✅ | 낮음 ❌ |
| 비용 | 저렴 ✅ | 비싸 (GPU) ❌ |

**신조어는 매일 새로 생기므로 통계적 방법이 최적!**

## 모니터링 및 로그

### CloudWatch Logs
- Glue Job 로그: `/aws-glue/jobs/neologism-extraction-job`
- Airflow 로그: `/aws/mwaa/neologism-extraction-env/`

### 메트릭
- 추출된 신조어 수
- 처리 시간
- 에러 발생률

## 비용 최적화

- **S3**: Lifecycle 정책으로 오래된 데이터 자동 삭제
- **Glue**: 최소 DPU(2) 사용, 타임아웃 설정
- **MWAA**: Small 인스턴스, 최소 워커 수
- **VPC**: NAT Gateway 1개만 사용

예상 월 비용 (일일 1회 실행):
- MWAA: ~$300
- Glue: ~$20
- S3: ~$5
- **총 ~$325/월**

## 트러블슈팅

### Glue Job 실패
- CloudWatch Logs 확인
- Python 패키지 버전 확인
- S3 권한 확인

### MWAA DAG 오류
- Airflow Variables 설정 확인
- IAM 역할 권한 확인
- DAG 파일 문법 오류 확인

### 신조어가 추출되지 않음
- 입력 데이터 확인 (최소 100개 이상 권장)
- min_count, min_cohesion 파라미터 조정
- 텍스트 전처리 결과 확인

## 개발 가이드

### 테스트 실행
```bash
pytest tests/
```

### 코드 포맷팅
```bash
black src/
flake8 src/
```

### 새로운 데이터 소스 추가

1. `data_collector.py`에 새 Collector 클래스 작성:
```python
class NewSourceCollector(BaseCollector):
    def collect(self, **kwargs) -> List[str]:
        # 구현
        pass
```

2. DAG에 Task 추가
3. 테스트 및 배포

## 라이선스

MIT License

## 기여

이슈 및 PR은 언제나 환영합니다!

## 문의

- Email: data-team@example.com
- Slack: #neologism-extraction
