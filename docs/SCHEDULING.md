# 스케줄링 및 자동화 가이드

## 📅 DAG 스케줄링 설정

### 현재 설정

```python
schedule_interval='0 2 * * *'  # 매일 오전 2시 UTC (한국 시간 11시)
```

### Cron 표현식 가이드

| 패턴 | 설명 | 실행 시각 (KST) |
|------|------|-----------------|
| `0 2 * * *` | 매일 | 매일 오전 11시 |
| `0 2 * * 1` | 매주 월요일 | 매주 월요일 오전 11시 |
| `0 2 1 * *` | 매월 1일 | 매월 1일 오전 11시 |
| `0 */6 * * *` | 6시간마다 | 오전 6시, 12시, 오후 6시, 자정 |
| `0 2 * * 1-5` | 주중 매일 | 월-금 오전 11시 |

### 스케줄 변경 방법

#### 1. DAG 파일 수정

```python
# airflow/dags/neologism_extraction_dag.py

with DAG(
    dag_id='neologism_extraction_pipeline',
    schedule_interval='0 2 * * *',  # 이 부분 수정
    ...
)
```

#### 2. S3에 업로드

```bash
aws s3 cp airflow/dags/neologism_extraction_dag.py \
  s3://<mwaa-bucket>/dags/
```

#### 3. Airflow UI에서 확인

- MWAA 웹 UI 접속
- DAG 목록에서 새로고침
- 스케줄 변경 확인

## 🔄 중복 제거 전략

### 지원되는 전략

#### 1. **merge** (병합) - 권장 ✅

```python
'--UPDATE_STRATEGY': 'merge'
```

**동작**:
- 기존 단어 유지
- 새 단어 추가
- 중복 시 빈도 누적, 점수 최대값 사용

**사용 사례**:
- 일일 증분 업데이트
- 장기간 사전 유지

**결과 예시**:
```
기존: 100개
새로: 20개 (중복 5개, 신규 15개)
결과: 115개
```

#### 2. **new_only** (신규만)

```python
'--UPDATE_STRATEGY': 'new_only'
```

**동작**:
- 기존 단어 유지 (업데이트 없음)
- 신규 단어만 추가

**사용 사례**:
- 새로운 신조어만 추적
- 기존 데이터 보존

#### 3. **replace** (교체)

```python
'--UPDATE_STRATEGY': 'replace'
```

**동작**:
- 새 데이터로 완전 교체
- 기존 데이터 덮어쓰기

**사용 사례**:
- 전체 재계산
- 알고리즘 변경 후

## 📝 뜻 풀이 생성 옵션

### 활성화/비활성화

```python
'--GENERATE_DEFINITIONS': 'true'  # 또는 'false'
```

### LLM 사용 (선택사항)

```python
'--USE_LLM': 'false'  # 비용 절감을 위해 기본 false
```

**비교**:

| 방법 | 속도 | 정확도 | 비용 |
|------|------|--------|------|
| 규칙 기반 | 빠름 | 70% | 무료 |
| LLM (Claude) | 느림 | 95% | 약 $0.001/단어 |

### 규칙 기반 뜻 풀이 예시

```python
# 자동 생성 규칙
"갓생" → "최고, 최상급을 의미하는 신조어"
"점메추" → "추천의 줄임말"
"ㅇㅈ" → "인정의 줄임말"
```

## 🔧 운영 설정

### Airflow Variables 설정

MWAA 웹 UI > Admin > Variables에서 설정:

```python
{
  "neologism_s3_bucket": "your-bucket-name",
  "neologism_input_prefix": "input/raw-texts/",
  "neologism_output_prefix": "output/corpus/",
  "neologism_glue_job": "neologism-extraction-job",
  "aws_region": "ap-northeast-2",

  # 선택사항
  "twitter_bearer_token": "your-token",
  "aihub_api_key": "your-key",
  "notification_sns_topic": "arn:aws:sns:..."
}
```

### Glue Job 파라미터 조정

DAG 파일에서:

```python
script_args={
    '--MIN_COUNT': '3',              # 최소 빈도 (낮을수록 더 많은 후보)
    '--MIN_COHESION': '0.03',        # 최소 응집도 (낮을수록 더 많은 후보)
    '--ENABLE_DEDUP': 'true',        # 중복 제거
    '--UPDATE_STRATEGY': 'merge',    # merge, replace, new_only
    '--GENERATE_DEFINITIONS': 'true',# 뜻 풀이 생성
    '--USE_LLM': 'false',            # LLM 사용 여부
}
```

## 📊 모니터링

### CloudWatch Logs

#### Glue Job 로그
```bash
aws logs tail /aws-glue/jobs/neologism-extraction-job --follow
```

#### Airflow DAG 로그
```bash
aws logs tail /aws/mwaa/neologism-extraction-env/DAG/neologism_extraction_pipeline --follow
```

### 메트릭 확인

#### S3에서 결과 확인
```bash
# 최신 결과
aws s3 cp s3://your-bucket/output/corpus/latest/neologism_dict.json - | jq '.total_words'

# 의미 사전
aws s3 cp s3://your-bucket/output/corpus/latest/semantic_dict.json - | jq '.entries[] | {word, definition}'
```

#### 증분 통계
```bash
# 메타데이터 확인
aws s3 cp s3://your-bucket/output/corpus/latest/neologism_dict.json - | \
  jq '.metadata'

# 출력 예시:
# {
#   "updated_at": "2024-01-15T11:00:00",
#   "update_strategy": "merge",
#   "previous_count": 100,
#   "new_count": 25,
#   "result_count": 115
# }
```

## 🚨 트러블슈팅

### DAG가 실행되지 않음

1. **스케줄 확인**
   ```bash
   # Airflow UI에서 DAG가 ON인지 확인
   ```

2. **과거 실행 건너뛰기**
   ```python
   catchup=False  # DAG 설정 확인
   ```

3. **로그 확인**
   ```bash
   aws logs tail /aws/mwaa/neologism-extraction-env/Scheduler --follow
   ```

### Glue Job 실패

1. **파라미터 오류**
   - 필수 파라미터 누락 확인
   - S3 버킷/키 존재 여부 확인

2. **권한 오류**
   ```bash
   # IAM 역할 권한 확인
   aws iam get-role --role-name AWSGlueServiceRole-NeologismExtraction
   ```

3. **메모리 부족**
   - DPU 수 증가: `num_of_dpus=4`

### 중복 제거 작동하지 않음

1. **기존 사전 확인**
   ```bash
   aws s3 ls s3://your-bucket/output/corpus/latest/
   ```

2. **ENABLE_DEDUP 파라미터**
   ```python
   '--ENABLE_DEDUP': 'true'  # true인지 확인
   ```

## 💡 최적화 팁

### 성능 최적화

1. **DPU 조정**
   ```python
   num_of_dpus=2  # 데이터량에 따라 2-10
   ```

2. **MIN_COUNT 조정**
   ```python
   '--MIN_COUNT': '5'  # 높을수록 빠름, 적을수록 느림
   ```

### 비용 최적화

1. **스케줄 조정**
   ```python
   # 매일 → 주 1회
   schedule_interval='0 2 * * 1'  # 월요일만
   ```

2. **LLM 비활성화**
   ```python
   '--USE_LLM': 'false'  # 규칙 기반 사용
   ```

3. **S3 Lifecycle**
   - 90일 이상 구 버전 자동 삭제
   - Glacier로 아카이빙

## 📈 예상 비용

### 월별 (매일 실행 기준)

| 항목 | 비용 |
|------|------|
| MWAA (mw1.small) | $300 |
| Glue (2 DPU × 30일 × 10분) | $20 |
| S3 (10GB) | $0.25 |
| CloudWatch Logs | $3 |
| **총합** | **~$323/월** |

### 비용 절감 시나리오

**주 1회 실행**:
- Glue: $20 → $5 (-75%)
- **총합**: $308/월

**뜻 풀이 LLM 사용**:
- Bedrock Claude: +$30/월 (1000단어 기준)
- **총합**: $353/월

## 🎯 운영 체크리스트

### 초기 설정
- [ ] Airflow Variables 설정
- [ ] S3 버킷 생성 확인
- [ ] IAM 권한 확인
- [ ] DAG 활성화

### 주간 점검
- [ ] CloudWatch 로그 확인
- [ ] 신조어 개수 추이 확인
- [ ] 에러 발생 여부 확인

### 월간 점검
- [ ] S3 저장 공간 확인
- [ ] 비용 검토
- [ ] 파라미터 튜닝 필요성 검토
- [ ] 알고리즘 개선 검토
