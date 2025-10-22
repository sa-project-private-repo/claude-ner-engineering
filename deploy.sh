#!/bin/bash
# 신조어 추출 시스템 배포 스크립트

set -e

echo "========================================="
echo "신조어 추출 시스템 배포"
echo "========================================="

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. 환경 확인
echo -e "\n${YELLOW}[1/5] 환경 확인 중...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python3가 설치되지 않았습니다!${NC}"
    exit 1
fi

if ! command -v aws &> /dev/null; then
    echo -e "${RED}AWS CLI가 설치되지 않았습니다!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python3: $(python3 --version)${NC}"
echo -e "${GREEN}✓ AWS CLI: $(aws --version)${NC}"

# 2. Python 의존성 설치
echo -e "\n${YELLOW}[2/5] Python 의존성 설치 중...${NC}"

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo -e "${GREEN}✓ Python 의존성 설치 완료${NC}"

# CDK TypeScript 의존성 설치
echo -e "\n${YELLOW}CDK TypeScript 의존성 설치 중...${NC}"

if ! command -v npm &> /dev/null; then
    echo -e "${RED}npm이 설치되지 않았습니다! Node.js를 설치해주세요.${NC}"
    exit 1
fi

cd cdk
npm install
cd ..

echo -e "${GREEN}✓ CDK 의존성 설치 완료${NC}"

# 3. CDK 부트스트랩 (최초 1회만)
echo -e "\n${YELLOW}[3/5] CDK 부트스트랩 확인 중...${NC}"

AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${AWS_REGION:-ap-northeast-2}

echo "  계정: $AWS_ACCOUNT"
echo "  리전: $AWS_REGION"

read -p "CDK 부트스트랩을 실행하시겠습니까? (최초 1회만 필요) [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    cd cdk
    cdk bootstrap aws://$AWS_ACCOUNT/$AWS_REGION
    cd ..
    echo -e "${GREEN}✓ CDK 부트스트랩 완료${NC}"
else
    echo "  건너뜀"
fi

# 4. CDK 스택 배포
echo -e "\n${YELLOW}[4/5] CDK 스택 배포 중...${NC}"

cd cdk

echo "다음 스택을 배포합니다:"
echo "  1. NeologismGlueStack (Glue Job, S3)"
echo "  2. NeologismMwaaStack (MWAA, VPC)"
echo ""
echo "예상 비용: ~$325/월"
echo ""

read -p "계속하시겠습니까? [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    cdk deploy --all --require-approval never
    echo -e "${GREEN}✓ CDK 스택 배포 완료${NC}"
else
    echo -e "${RED}배포 취소됨${NC}"
    exit 1
fi

cd ..

# 5. 설정 안내
echo -e "\n${YELLOW}[5/5] 배포 완료!${NC}"
echo ""
echo "========================================="
echo "다음 단계:"
echo "========================================="
echo ""
echo "1. MWAA 웹 UI 접속"
echo "   URL은 CDK 출력 결과에서 'MwaaWebserverUrl' 확인"
echo ""
echo "2. Airflow Variables 설정"
echo "   Admin > Variables에서 다음 변수 설정:"
echo "   - neologism_s3_bucket"
echo "   - neologism_glue_job"
echo "   - twitter_bearer_token (선택)"
echo "   - aihub_api_key (선택)"
echo ""
echo "3. DAG 활성화"
echo "   'neologism_extraction_pipeline' DAG를 ON으로 전환"
echo ""
echo "4. 테스트 실행"
echo "   DAG 우측의 재생 버튼 클릭하여 수동 실행"
echo ""
echo "========================================="
echo -e "${GREEN}배포가 완료되었습니다!${NC}"
echo "========================================="
