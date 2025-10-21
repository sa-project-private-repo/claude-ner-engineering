#!/usr/bin/env python3
"""
CDK App: 신조어 추출 파이프라인 인프라

이 앱은 다음 리소스를 배포합니다:
1. AWS Glue Job (신조어 추출)
2. AWS MWAA (Apache Airflow)
3. S3 버킷 (데이터, 스크립트, DAG)
4. VPC, IAM 역할 등
"""

import os
from aws_cdk import App, Environment, Tags
from stacks import GlueStack, MWAAStack


app = App()

# 환경 설정 (계정/리전)
env = Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", "ap-northeast-2"),
)

# Stack 1: Glue 인프라
glue_stack = GlueStack(
    app,
    "NeologismGlueStack",
    env=env,
    description="신조어 추출을 위한 AWS Glue 인프라",
)

# Stack 2: MWAA 인프라
mwaa_stack = MWAAStack(
    app,
    "NeologismMwaaStack",
    data_bucket_name=glue_stack.data_bucket.bucket_name,
    glue_job_name=glue_stack.glue_job.name,
    env=env,
    description="신조어 추출 파이프라인을 위한 MWAA 인프라",
)

# MWAA는 Glue에 의존
mwaa_stack.add_dependency(glue_stack)

# 태그 추가
Tags.of(app).add("Project", "NeologismExtraction")
Tags.of(app).add("Environment", "Production")
Tags.of(app).add("ManagedBy", "CDK")

app.synth()
