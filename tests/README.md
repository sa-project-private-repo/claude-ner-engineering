# 테스트 가이드

신조어 추출 시스템의 테스트 스위트입니다.

## 📋 목차

- [테스트 구조](#테스트-구조)
- [설치](#설치)
- [실행 방법](#실행-방법)
- [테스트 유형](#테스트-유형)
- [CI/CD 통합](#cicd-통합)

## 🗂️ 테스트 구조

```
tests/
├── README.md                    # 이 파일
├── test_dag.py                  # Airflow DAG 테스트
├── test_extractor.py            # 신조어 추출기 단위 테스트
├── test_corpus_builder.py       # 코퍼스 빌더 단위 테스트
└── conftest.py                  # pytest 설정 및 픽스처
```

## 📦 설치

### 1. 기본 요구사항 설치

```bash
# 프로젝트 루트에서
pip install -r requirements.txt
```

### 2. 테스트 전용 패키지 설치

테스트 패키지는 이미 `requirements.txt`에 포함되어 있습니다:
- pytest
- pytest-cov
- pytest-mock

## 🚀 실행 방법

### 전체 테스트 실행

```bash
# 프로젝트 루트에서
pytest
```

### 특정 테스트 파일 실행

```bash
# DAG 테스트만 실행
pytest tests/test_dag.py

# 신조어 추출기 테스트만 실행
pytest tests/test_extractor.py

# 코퍼스 빌더 테스트만 실행
pytest tests/test_corpus_builder.py
```

### 상세 출력 옵션

```bash
# 상세 출력 (-v)
pytest -v

# 매우 상세한 출력 (-vv)
pytest -vv

# 실패한 테스트만 다시 실행
pytest --lf

# 첫 번째 실패에서 중단
pytest -x
```

### 커버리지 리포트

```bash
# 커버리지와 함께 실행
pytest --cov=src/neologism_extractor --cov-report=html

# 브라우저에서 확인
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### 특정 마커로 테스트 실행

```bash
# 단위 테스트만 실행
pytest -m unit

# DAG 테스트만 실행
pytest -m dag

# 느린 테스트 제외
pytest -m "not slow"
```

## 🧪 테스트 유형

### 1. DAG 테스트 (test_dag.py)

Airflow DAG의 구조와 무결성을 검증합니다.

**테스트 항목:**
- ✅ DAG import 오류 확인
- ✅ Task 개수 및 존재 여부
- ✅ Task 의존성 확인
- ✅ 스케줄 설정 검증
- ✅ GlueJobOperator 파라미터 확인
- ✅ 순환 의존성 체크

**실행:**
```bash
pytest tests/test_dag.py -v
```

### 2. 신조어 추출기 테스트 (test_extractor.py)

NeologismExtractor 클래스의 기능을 검증합니다.

**테스트 항목:**
- ✅ 초기화 및 설정
- ✅ 텍스트 전처리
- ✅ 신조어 추출 로직
- ✅ 임계값 필터링
- ✅ 유형 분류 (줄임말, 복합어, 은어)
- ✅ 경계 조건 (빈 입력, 특수문자 등)
- ✅ 빈도 계산 정확성

**실행:**
```bash
pytest tests/test_extractor.py -v
```

### 3. 코퍼스 빌더 테스트 (test_corpus_builder.py)

CorpusBuilder 클래스의 기능을 검증합니다.

**테스트 항목:**
- ✅ JSON/CSV/TXT 포맷 생성
- ✅ 중복 제거 전략 (merge, new_only, replace)
- ✅ 증분 업데이트
- ✅ 메타데이터 생성
- ✅ 통계 정보 포함
- ✅ 오류 처리

**실행:**
```bash
pytest tests/test_corpus_builder.py -v
```

## 📊 테스트 결과 예시

```
============================= test session starts ==============================
platform linux -- Python 3.11.0, pytest-8.3.0, pluggy-1.5.0
rootdir: /home/user/claude-ner-engineering
configfile: pytest.ini
testpaths: tests
plugins: cov-6.0.0, mock-3.14.0
collected 45 items

tests/test_dag.py::TestDAGIntegrity::test_dagbag_import PASSED         [  2%]
tests/test_dag.py::TestDAGIntegrity::test_dag_loaded PASSED            [  4%]
tests/test_dag.py::TestDAGIntegrity::test_dag_has_tags PASSED          [  6%]
...
tests/test_extractor.py::TestNeologismExtractor::test_initialization PASSED
...
tests/test_corpus_builder.py::TestCorpusBuilder::test_initialization PASSED
...

=============================== 45 passed in 5.23s =============================
```

## 🔍 DAG 검증

DAG을 로컬에서 테스트하는 방법:

### 1. DAG 구문 확인

```bash
# DAG 파일 구문 오류 체크
python airflow/dags/neologism_extraction_dag.py
```

### 2. Airflow CLI로 DAG 테스트

```bash
# Airflow 환경 설정
export AIRFLOW_HOME="${PWD}/airflow_home"
export AIRFLOW__CORE__DAGS_FOLDER="${PWD}/airflow/dags"

# DAG 목록 확인
airflow dags list

# DAG 구조 확인
airflow dags show neologism_extraction_pipeline

# 특정 날짜로 전체 DAG 테스트 실행
airflow dags test neologism_extraction_pipeline 2025-01-01

# 특정 Task만 테스트
airflow tasks test neologism_extraction_pipeline collect_twitter_data 2025-01-01
```

### 3. pytest로 DAG 검증

```bash
# pytest를 사용한 자동화된 DAG 검증
pytest tests/test_dag.py -v

# 특정 테스트 클래스만 실행
pytest tests/test_dag.py::TestDAGIntegrity -v
```

## 🐳 Docker에서 테스트

```bash
# Docker 컨테이너에서 테스트 실행
docker run --rm -v $(pwd):/app -w /app python:3.11 \
  bash -c "pip install -r requirements.txt && pytest"
```

## 🔄 CI/CD 통합

### GitHub Actions 예시

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest --cov --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## 📝 테스트 작성 가이드

### 새 테스트 추가

1. `tests/` 디렉토리에 `test_*.py` 파일 생성
2. `Test*` 클래스로 테스트 그룹화
3. `test_*` 함수로 개별 테스트 작성

**예시:**

```python
import pytest

class TestMyFeature:
    @pytest.fixture
    def sample_data(self):
        return {"key": "value"}

    def test_something(self, sample_data):
        assert sample_data["key"] == "value"
```

### 픽스처 활용

공통 픽스처는 `conftest.py`에 정의:

```python
# conftest.py
import pytest

@pytest.fixture
def common_fixture():
    return "shared data"
```

### 마커 사용

테스트에 마커 추가:

```python
@pytest.mark.unit
def test_unit_feature():
    pass

@pytest.mark.slow
def test_slow_feature():
    pass
```

## 🐛 디버깅

### pdb 디버거 사용

```bash
# 실패 시 자동으로 pdb 실행
pytest --pdb

# 각 테스트 시작 시 pdb 실행
pytest --trace
```

### 로그 출력

```bash
# 모든 로그 출력
pytest --log-cli-level=DEBUG

# print 문 출력
pytest -s
```

## 📈 베스트 프랙티스

1. **테스트는 독립적이어야 함** - 각 테스트는 다른 테스트에 의존하지 않음
2. **빠른 실행** - 단위 테스트는 빠르게 실행되어야 함
3. **명확한 이름** - 테스트 함수명으로 무엇을 테스트하는지 알 수 있어야 함
4. **하나의 개념만 테스트** - 각 테스트는 하나의 기능만 검증
5. **픽스처 활용** - 반복되는 설정은 픽스처로 분리

## 🤝 기여하기

새로운 기능을 추가할 때는 반드시 테스트도 함께 작성해주세요!

```bash
# 테스트 작성 후 실행
pytest tests/test_your_feature.py -v

# 커버리지 확인
pytest --cov=src/neologism_extractor --cov-report=term-missing
```

## 📞 문제 해결

### 테스트가 실패하는 경우

1. **import 오류**: Python 경로 확인
   ```bash
   export PYTHONPATH="${PWD}/src:${PYTHONPATH}"
   ```

2. **DAG import 오류**: Airflow 환경 변수 설정
   ```bash
   export AIRFLOW_HOME="${PWD}/airflow_home"
   ```

3. **패키지 누락**: requirements.txt 재설치
   ```bash
   pip install -r requirements.txt --upgrade
   ```

## 📚 추가 자료

- [pytest 공식 문서](https://docs.pytest.org/)
- [Airflow Testing Best Practices](https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html#testing-a-dag)
- [Python Testing with pytest (Book)](https://pragprog.com/titles/bopytest/python-testing-with-pytest/)
