#!/bin/bash

###############################################################################
# 로컬 Airflow 3.0 테스트 환경 설정 스크립트
#
# 사용법:
#   ./scripts/setup_local_airflow.sh
#
# 이 스크립트는 다음을 수행합니다:
# 1. Python 가상환경 생성
# 2. Airflow 3.0 및 필요한 패키지 설치
# 3. Airflow 데이터베이스 초기화
# 4. Admin 사용자 생성
# 5. Airflow 웹서버 및 스케줄러 실행 가이드 제공
###############################################################################

set -e  # 오류 발생 시 스크립트 종료

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 환경 변수 설정
export AIRFLOW_HOME="${PWD}/airflow_home"
export AIRFLOW__CORE__DAGS_FOLDER="${PWD}/airflow/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export AIRFLOW__CORE__EXECUTOR=LocalExecutor
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="sqlite:///${AIRFLOW_HOME}/airflow.db"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Airflow 3.0 로컬 테스트 환경 설정${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Python 버전 확인
echo -e "${YELLOW}[1/7] Python 버전 확인...${NC}"
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

echo "Python 버전: $PYTHON_VERSION"

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    echo -e "${RED}오류: Python 3.10 이상이 필요합니다.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 버전 OK${NC}\n"

# 가상환경 생성
echo -e "${YELLOW}[2/7] Python 가상환경 생성...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ 가상환경 생성 완료${NC}"
else
    echo -e "${GREEN}✓ 가상환경이 이미 존재합니다${NC}"
fi

# 가상환경 활성화
source venv/bin/activate
echo -e "${GREEN}✓ 가상환경 활성화 완료${NC}\n"

# pip 업그레이드
echo -e "${YELLOW}[3/7] pip 업그레이드...${NC}"
pip install --upgrade pip setuptools wheel
echo -e "${GREEN}✓ pip 업그레이드 완료${NC}\n"

# Airflow 및 종속성 설치
echo -e "${YELLOW}[4/7] Airflow 3.0 및 패키지 설치...${NC}"
echo "이 작업은 몇 분 걸릴 수 있습니다..."

# Airflow 3.0 설치
pip install "apache-airflow[celery,postgres,aws]==3.0.0" --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-3.0.0/constraints-3.10.txt"

# AWS Providers 설치
pip install "apache-airflow-providers-amazon>=9.15.0"

# 추가 패키지 설치
pip install -r airflow/requirements.txt

echo -e "${GREEN}✓ 패키지 설치 완료${NC}\n"

# AIRFLOW_HOME 디렉토리 생성
echo -e "${YELLOW}[5/7] Airflow 홈 디렉토리 설정...${NC}"
mkdir -p "${AIRFLOW_HOME}"
mkdir -p "${AIRFLOW_HOME}/logs"
mkdir -p "${AIRFLOW_HOME}/plugins"
echo -e "${GREEN}✓ Airflow 홈 디렉토리 생성 완료: ${AIRFLOW_HOME}${NC}\n"

# Airflow 데이터베이스 초기화
echo -e "${YELLOW}[6/7] Airflow 데이터베이스 초기화...${NC}"
airflow db migrate
echo -e "${GREEN}✓ 데이터베이스 초기화 완료${NC}\n"

# Admin 사용자 생성
echo -e "${YELLOW}[7/7] Admin 사용자 생성...${NC}"
airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin 2>/dev/null || echo "사용자가 이미 존재합니다."
echo -e "${GREEN}✓ Admin 사용자 생성 완료${NC}\n"

# Airflow Variables 설정
echo -e "${YELLOW}Airflow Variables 설정...${NC}"
airflow variables set neologism_s3_bucket "your-bucket-name" 2>/dev/null || true
airflow variables set neologism_input_prefix "input/raw-texts/" 2>/dev/null || true
airflow variables set neologism_output_prefix "output/corpus/" 2>/dev/null || true
airflow variables set neologism_glue_job "neologism-extraction-job" 2>/dev/null || true
airflow variables set aws_region "ap-northeast-2" 2>/dev/null || true
echo -e "${GREEN}✓ Variables 설정 완료${NC}\n"

# .env 파일 생성 (환경 변수)
echo -e "${YELLOW}환경 변수 파일 생성...${NC}"
cat > .env.local <<EOF
# Airflow 환경 변수
export AIRFLOW_HOME="${AIRFLOW_HOME}"
export AIRFLOW__CORE__DAGS_FOLDER="${AIRFLOW__CORE__DAGS_FOLDER}"
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export AIRFLOW__CORE__EXECUTOR=LocalExecutor
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="${AIRFLOW__DATABASE__SQL_ALCHEMY_CONN}"

# AWS 자격증명 (필요시 설정)
# export AWS_ACCESS_KEY_ID="your-access-key"
# export AWS_SECRET_ACCESS_KEY="your-secret-key"
# export AWS_DEFAULT_REGION="ap-northeast-2"
EOF
echo -e "${GREEN}✓ .env.local 파일 생성 완료${NC}\n"

# 완료 메시지
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Airflow 3.0 로컬 환경 설정 완료!${NC}"
echo -e "${GREEN}========================================${NC}\n"

# 사용 가이드
echo -e "${BLUE}다음 명령어로 Airflow를 실행하세요:${NC}\n"

echo -e "${YELLOW}1. 환경 변수 로드:${NC}"
echo -e "   source venv/bin/activate"
echo -e "   source .env.local\n"

echo -e "${YELLOW}2. Airflow 스케줄러 실행 (터미널 1):${NC}"
echo -e "   airflow scheduler\n"

echo -e "${YELLOW}3. Airflow 웹서버 실행 (터미널 2):${NC}"
echo -e "   airflow webserver --port 8080\n"

echo -e "${YELLOW}4. 웹 UI 접속:${NC}"
echo -e "   http://localhost:8080"
echo -e "   사용자: admin"
echo -e "   비밀번호: admin\n"

echo -e "${YELLOW}5. DAG 테스트 실행:${NC}"
echo -e "   airflow dags test neologism_extraction_pipeline $(date +%Y-%m-%d)\n"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}테스트 명령어:${NC}"
echo -e "${BLUE}========================================${NC}\n"

echo -e "${YELLOW}DAG 목록 확인:${NC}"
echo -e "   airflow dags list\n"

echo -e "${YELLOW}DAG 구조 확인:${NC}"
echo -e "   airflow dags show neologism_extraction_pipeline\n"

echo -e "${YELLOW}특정 Task 테스트:${NC}"
echo -e "   airflow tasks test neologism_extraction_pipeline collect_twitter_data $(date +%Y-%m-%d)\n"

echo -e "${YELLOW}pytest로 DAG 검증:${NC}"
echo -e "   pytest tests/test_dag.py -v\n"

echo -e "${GREEN}설정이 완료되었습니다! 즐거운 개발 되세요! 🚀${NC}\n"
