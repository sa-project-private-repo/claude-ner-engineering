# CDK 인프라 배포 가이드 (TypeScript)

## 개요

이 디렉토리는 신조어 추출 시스템의 AWS 인프라를 **CDK TypeScript**로 정의합니다.

## 스택 구성

### 1. NeologismGlueStack
- **S3 버킷** (데이터 저장)
  - 원본 텍스트: `input/raw-texts/`
  - 추출 결과: `output/corpus/`
  - Lifecycle 정책: 자동 삭제/아카이빙
- **S3 버킷** (Glue 스크립트)
- **Glue Job** (신조어 추출)
  - Python 3.9
  - 2 DPU (G.1X workers)
  - soynlp, konlpy 사전 설치
- **Glue Database & Crawler** (선택사항)
- **IAM Roles**

### 2. NeologismMwaaStack
- **VPC** (2 AZ, Public + Private 서브넷)
- **MWAA 환경** (Apache Airflow 2.7.2)
  - Environment: mw1.small
  - Workers: 1-2
  - Public 웹서버 접근
- **S3 버킷** (DAG, Plugins)
- **Security Groups**
- **IAM Roles**

## 사전 요구사항

```bash
# AWS CLI 설정
aws configure

# Node.js 설치 확인 (v18 이상 권장)
node --version

# CDK CLI 설치
npm install -g aws-cdk

# TypeScript 의존성 설치
cd cdk
npm install
```

## 배포

### 0. 빌드 (TypeScript → JavaScript)

```bash
# TypeScript 컴파일
npm run build

# 또는 watch 모드 (자동 컴파일)
npm run watch
```

### 1. 부트스트랩 (최초 1회)

```bash
export AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=ap-northeast-2

cdk bootstrap aws://$AWS_ACCOUNT/$AWS_REGION
```

### 2. 스택 확인

```bash
# 생성될 리소스 확인
npm run synth
# 또는
cdk synth

# Diff 확인
npm run diff
# 또는
cdk diff
```

### 3. 배포

```bash
# 모든 스택 배포
npm run deploy
# 또는
cdk deploy --all

# 개별 배포
cdk deploy NeologismGlueStack
cdk deploy NeologismMwaaStack
```

### 4. 삭제

```bash
# 모든 스택 삭제
npm run destroy
# 또는
cdk destroy --all
```

### 4. 배포 후 확인

```bash
# 스택 출력 확인
aws cloudformation describe-stacks \
  --stack-name NeologismGlueStack \
  --query 'Stacks[0].Outputs'

aws cloudformation describe-stacks \
  --stack-name NeologismMwaaStack \
  --query 'Stacks[0].Outputs'
```

## 주요 출력값

배포 후 다음 값들이 출력됩니다:

- **DataBucketName**: S3 데이터 버킷
- **GlueJobName**: Glue Job 이름
- **MwaaEnvironmentName**: MWAA 환경 이름
- **MwaaWebserverUrl**: Airflow UI URL

## 리소스 업데이트

### Glue Job 스크립트 업데이트

```bash
# 스크립트 수정 후
cdk deploy NeologismGlueStack
```

### DAG 업데이트

```bash
# DAG 파일 수정 후
cdk deploy NeologismMwaaStack

# 또는 직접 S3 업로드
aws s3 cp ../airflow/dags/neologism_extraction_dag.py \
  s3://<mwaa-bucket>/dags/
```

## 삭제

```bash
# 모든 스택 삭제
cdk destroy --all

# 주의: S3 버킷은 수동 삭제 필요 (데이터 보호)
```

## 비용 관리

### 예상 비용 (월)

- MWAA (mw1.small): ~$300
- Glue (일 1회, 2 DPU): ~$20
- VPC (NAT Gateway): ~$32
- S3: ~$5
- **총합: ~$357/월**

### 비용 절감 팁

1. **MWAA**: 개발 환경에서는 필요시에만 실행
2. **Glue**: DPU 수 조정, 타임아웃 설정
3. **S3**: Lifecycle 정책 활용
4. **VPC**: NAT Gateway 대신 VPC Endpoint 고려

## 트러블슈팅

### CDK 배포 실패

```bash
# 로그 확인
cdk deploy --verbose

# CloudFormation 콘솔 확인
# https://console.aws.amazon.com/cloudformation
```

### MWAA 환경 생성 실패

- VPC/서브넷 설정 확인
- IAM 권한 확인
- CloudWatch Logs 확인

### Glue Job 실패

- CloudWatch Logs 확인
- Python 패키지 버전 호환성
- S3 권한 확인

## 고급 설정

### 커스텀 VPC 사용

`mwaa_stack.py` 수정:

```python
# 기존 VPC 가져오기
vpc = ec2.Vpc.from_lookup(self, "ExistingVpc",
    vpc_id="vpc-xxxxx")
```

### Private 웹서버 접근

```python
webserver_access_mode="PRIVATE_ONLY"
```

VPN 또는 Direct Connect 필요

### 알림 설정

SNS 토픽 추가:

```python
sns_topic = sns.Topic(self, "NotificationTopic")
# DAG에서 사용
```

## 참고 자료

- [AWS CDK 문서](https://docs.aws.amazon.com/cdk/)
- [AWS Glue 문서](https://docs.aws.amazon.com/glue/)
- [AWS MWAA 문서](https://docs.aws.amazon.com/mwaa/)
