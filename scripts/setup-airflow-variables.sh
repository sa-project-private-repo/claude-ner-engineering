#!/bin/bash

# Airflow Variables 자동 설정 스크립트
# CloudFormation outputs에서 필요한 값들을 추출하여 JSON 파일로 생성합니다.

set -e

REGION="us-east-1"
GLUE_STACK_NAME="NeologismGlueStack"
MWAA_STACK_NAME="NeologismMwaaStack"

echo "======================================"
echo "Airflow Variables 설정 스크립트"
echo "======================================"
echo ""

# CloudFormation에서 값 추출
echo "1. CloudFormation Outputs에서 값 추출 중..."

DATA_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name ${GLUE_STACK_NAME} \
    --region ${REGION} \
    --query 'Stacks[0].Outputs[?OutputKey==`DataBucketName`].OutputValue' \
    --output text)

GLUE_JOB=$(aws cloudformation describe-stacks \
    --stack-name ${GLUE_STACK_NAME} \
    --region ${REGION} \
    --query 'Stacks[0].Outputs[?OutputKey==`GlueJobName`].OutputValue' \
    --output text)

MWAA_ENV=$(aws cloudformation describe-stacks \
    --stack-name ${MWAA_STACK_NAME} \
    --region ${REGION} \
    --query 'Stacks[0].Outputs[?OutputKey==`MwaaEnvironmentName`].OutputValue' \
    --output text)

echo "   Data Bucket: ${DATA_BUCKET}"
echo "   Glue Job: ${GLUE_JOB}"
echo "   MWAA Environment: ${MWAA_ENV}"
echo ""

# Airflow Variables JSON 생성
echo "2. Airflow Variables JSON 파일 생성 중..."

VARIABLES_JSON=$(cat <<EOF
{
  "neologism_s3_bucket": "${DATA_BUCKET}",
  "neologism_input_prefix": "input/raw-texts/",
  "neologism_output_prefix": "output/corpus/",
  "neologism_glue_job": "${GLUE_JOB}",
  "aws_region": "${REGION}"
}
EOF
)

OUTPUT_FILE="airflow-variables.json"
echo "${VARIABLES_JSON}" > ${OUTPUT_FILE}

echo "   생성 완료: ${OUTPUT_FILE}"
echo ""

# 내용 출력
echo "3. Airflow Variables 내용:"
echo "======================================"
cat ${OUTPUT_FILE}
echo ""
echo "======================================"
echo ""

# Airflow UI에서 설정하는 방법 안내
echo "4. Airflow UI에서 Variables 설정 방법:"
echo "   (주의: MWAA는 CLI를 통한 직접 설정을 지원하지 않습니다)"
echo ""
echo "   방법 1: UI에서 개별 등록"
echo "   ----------------------------------------"
echo "   1. Airflow UI 접속 (웹서버 URL 확인)"
echo "   2. Admin → Variables 메뉴 이동"
echo "   3. '+' 버튼으로 아래 변수들을 하나씩 추가:"
echo ""
jq -r 'to_entries[] | "      Key: \(.key)\n      Value: \(.value)\n"' ${OUTPUT_FILE}
echo ""
echo "   방법 2: JSON 파일 Import (권장)"
echo "   ----------------------------------------"
echo "   1. Airflow UI 접속"
echo "   2. Admin → Variables 메뉴 이동"
echo "   3. 'Import Variables' 버튼 클릭"
echo "   4. ${OUTPUT_FILE} 파일 업로드"
echo ""

# Airflow 웹서버 URL 출력
WEBSERVER_URL=$(aws cloudformation describe-stacks \
    --stack-name ${MWAA_STACK_NAME} \
    --region ${REGION} \
    --query 'Stacks[0].Outputs[?OutputKey==`MwaaWebserverUrl`].OutputValue' \
    --output text)

echo "5. Airflow 웹서버 URL:"
echo "   ${WEBSERVER_URL}"
echo ""

echo "======================================"
echo "설정 완료!"
echo "======================================"
