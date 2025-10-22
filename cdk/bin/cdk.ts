#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { GlueStack } from '../lib/glue-stack';
import { MwaaStack } from '../lib/mwaa-stack';

/**
 * CDK App: 신조어 추출 파이프라인 인프라
 *
 * 이 앱은 다음 리소스를 배포합니다:
 * 1. AWS Glue Job (신조어 추출)
 * 2. AWS MWAA (Apache Airflow)
 * 3. S3 버킷 (데이터, 스크립트, DAG)
 * 4. VPC, IAM 역할 등
 */

const app = new cdk.App();

// 환경 설정 (계정/리전)
const env: cdk.Environment = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || 'ap-northeast-2',
};

// Stack 1: Glue 인프라
const glueStack = new GlueStack(app, 'NeologismGlueStack', {
  env,
  description: '신조어 추출을 위한 AWS Glue 인프라',
  tags: {
    Project: 'NeologismExtraction',
    Environment: 'Production',
    ManagedBy: 'CDK',
  },
});

// Stack 2: MWAA 인프라
const mwaaStack = new MwaaStack(app, 'NeologismMwaaStack', {
  env,
  dataBucketName: glueStack.dataBucket.bucketName,
  glueJobName: glueStack.glueJob.name!,
  description: '신조어 추출 파이프라인을 위한 MWAA 인프라',
  tags: {
    Project: 'NeologismExtraction',
    Environment: 'Production',
    ManagedBy: 'CDK',
  },
});

// MWAA는 Glue에 의존
mwaaStack.addDependency(glueStack);

// 태그 추가
cdk.Tags.of(app).add('Project', 'NeologismExtraction');
cdk.Tags.of(app).add('Environment', 'Production');
cdk.Tags.of(app).add('ManagedBy', 'CDK');

app.synth();
