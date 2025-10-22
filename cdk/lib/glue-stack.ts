import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as glue from 'aws-cdk-lib/aws-glue';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';

/**
 * AWS Glue Stack
 * Glue Job과 관련 리소스 생성
 */
export class GlueStack extends cdk.Stack {
  public readonly dataBucket: s3.Bucket;
  public readonly scriptBucket: s3.Bucket;
  public readonly glueJob: glue.CfnJob;
  public readonly glueDatabase: glue.CfnDatabase;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // S3 버킷: 데이터 저장소
    this.dataBucket = new s3.Bucket(this, 'NeologismDataBucket', {
      bucketName: `neologism-data-${this.account}-${this.region}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      lifecycleRules: [
        {
          id: 'DeleteOldRawData',
          prefix: 'input/raw-texts/',
          expiration: cdk.Duration.days(30), // 원본 데이터는 30일 후 삭제
        },
        {
          id: 'TransitionOldCorpus',
          prefix: 'output/corpus/',
          transitions: [
            {
              storageClass: s3.StorageClass.INFREQUENT_ACCESS,
              transitionAfter: cdk.Duration.days(90),
            },
          ],
        },
      ],
    });

    // S3 버킷: Glue 스크립트 저장
    this.scriptBucket = new s3.Bucket(this, 'GlueScriptBucket', {
      bucketName: `neologism-glue-scripts-${this.account}-${this.region}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Glue Job 스크립트 업로드
    new s3deploy.BucketDeployment(this, 'DeployGlueScripts', {
      sources: [s3deploy.Source.asset('../glue_jobs')],
      destinationBucket: this.scriptBucket,
      destinationKeyPrefix: 'scripts/',
    });

    // IAM Role: Glue Job 실행 역할
    const glueRole = new iam.Role(this, 'GlueJobRole', {
      roleName: 'AWSGlueServiceRole-NeologismExtraction',
      assumedBy: new iam.ServicePrincipal('glue.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSGlueServiceRole'),
      ],
    });

    // S3 접근 권한 추가
    this.dataBucket.grantReadWrite(glueRole);
    this.scriptBucket.grantRead(glueRole);

    // CloudWatch Logs 권한
    glueRole.addToPolicy(
      new iam.PolicyStatement({
        actions: [
          'logs:CreateLogGroup',
          'logs:CreateLogStream',
          'logs:PutLogEvents',
        ],
        resources: [`arn:aws:logs:${this.region}:${this.account}:*`],
      })
    );

    // Glue Job 생성
    this.glueJob = new glue.CfnJob(this, 'NeologismExtractionJob', {
      name: 'neologism-extraction-job',
      role: glueRole.roleArn,
      command: {
        name: 'glueetl',
        pythonVersion: '3',
        scriptLocation: `s3://${this.scriptBucket.bucketName}/scripts/neologism_extraction_job.py`,
      },
      defaultArguments: {
        '--job-language': 'python',
        '--enable-metrics': 'true',
        '--enable-continuous-cloudwatch-log': 'true',
        '--enable-spark-ui': 'true',
        '--spark-event-logs-path': `s3://${this.dataBucket.bucketName}/spark-logs/`,
        '--TempDir': `s3://${this.dataBucket.bucketName}/temp/`,
        // 기본 파라미터
        '--INPUT_BUCKET': this.dataBucket.bucketName,
        '--INPUT_PREFIX': 'input/raw-texts/',
        '--OUTPUT_BUCKET': this.dataBucket.bucketName,
        '--OUTPUT_PREFIX': 'output/corpus/',
        '--MIN_COUNT': '5',
        '--MIN_COHESION': '0.05',
        // Python 패키지 (필요시 추가)
        '--additional-python-modules': 'soynlp==0.0.493,konlpy==0.6.0',
      },
      glueVersion: '4.0',
      numberOfWorkers: 2,
      workerType: 'G.1X', // 1 DPU
      timeout: 120, // 2시간
      maxRetries: 2,
      executionProperty: {
        maxConcurrentRuns: 1, // 동시 실행 제한
      },
    });

    // Glue Database (선택사항 - Catalog 사용 시)
    this.glueDatabase = new glue.CfnDatabase(this, 'NeologismDatabase', {
      catalogId: this.account,
      databaseInput: {
        name: 'neologism_db',
        description: '신조어 추출 데이터베이스',
      },
    });

    // Glue Crawler (선택사항 - 자동 테이블 생성)
    const crawlerRole = new iam.Role(this, 'GlueCrawlerRole', {
      assumedBy: new iam.ServicePrincipal('glue.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSGlueServiceRole'),
      ],
    });

    this.dataBucket.grantRead(crawlerRole);

    new glue.CfnCrawler(this, 'NeologismCrawler', {
      name: 'neologism-corpus-crawler',
      role: crawlerRole.roleArn,
      databaseName: this.glueDatabase.ref,
      targets: {
        s3Targets: [
          {
            path: `s3://${this.dataBucket.bucketName}/output/corpus/latest/`,
          },
        ],
      },
      schemaChangePolicy: {
        updateBehavior: 'UPDATE_IN_DATABASE',
        deleteBehavior: 'LOG',
      },
    });

    // Outputs
    new cdk.CfnOutput(this, 'DataBucketName', {
      value: this.dataBucket.bucketName,
      description: '신조어 데이터 S3 버킷',
      exportName: 'NeologismDataBucket',
    });

    new cdk.CfnOutput(this, 'GlueJobName', {
      value: this.glueJob.name!,
      description: 'Glue Job 이름',
      exportName: 'NeologismGlueJobName',
    });

    new cdk.CfnOutput(this, 'GlueDatabaseName', {
      value: this.glueDatabase.ref,
      description: 'Glue Database 이름',
      exportName: 'NeologismGlueDatabase',
    });
  }
}
