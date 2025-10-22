import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as mwaa from 'aws-cdk-lib/aws-mwaa';

export interface MwaaStackProps extends cdk.StackProps {
  dataBucketName: string;
  glueJobName: string;
}

/**
 * AWS MWAA (Managed Workflows for Apache Airflow) Stack
 * Airflow 환경 및 관련 리소스 생성
 */
export class MwaaStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;
  public readonly mwaaBucket: s3.Bucket;
  public readonly mwaaEnvironment: mwaa.CfnEnvironment;

  constructor(scope: Construct, id: string, props: MwaaStackProps) {
    super(scope, id, props);

    const { dataBucketName, glueJobName } = props;

    // VPC 생성 (MWAA는 VPC 필수)
    this.vpc = new ec2.Vpc(this, 'MwaaVpc', {
      maxAzs: 2,
      natGateways: 1, // 비용 절감을 위해 1개만
      subnetConfiguration: [
        {
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
          cidrMask: 24,
        },
        {
          name: 'Private',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
          cidrMask: 24,
        },
      ],
    });

    // Security Group
    const securityGroup = new ec2.SecurityGroup(this, 'MwaaSecurityGroup', {
      vpc: this.vpc,
      description: 'Security group for MWAA environment',
      allowAllOutbound: true,
    });

    // Self-referencing rule (MWAA 요구사항)
    securityGroup.addIngressRule(
      securityGroup,
      ec2.Port.allTraffic(),
      'Allow all traffic within security group'
    );

    // S3 버킷: Airflow DAGs, Plugins, Requirements
    this.mwaaBucket = new s3.Bucket(this, 'MwaaBucket', {
      bucketName: `neologism-mwaa-${this.account}-${this.region}`,
      versioned: true, // MWAA 요구사항
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // DAG 파일 업로드
    new s3deploy.BucketDeployment(this, 'DeployDags', {
      sources: [s3deploy.Source.asset('../airflow/dags')],
      destinationBucket: this.mwaaBucket,
      destinationKeyPrefix: 'dags/',
    });

    // IAM Role: MWAA 실행 역할
    const mwaaRole = new iam.Role(this, 'MwaaExecutionRole', {
      assumedBy: new iam.CompositePrincipal(
        new iam.ServicePrincipal('airflow.amazonaws.com'),
        new iam.ServicePrincipal('airflow-env.amazonaws.com')
      ),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('CloudWatchFullAccess'),
      ],
    });

    // S3 접근 권한
    this.mwaaBucket.grantReadWrite(mwaaRole);

    // 데이터 버킷 접근 권한
    const dataBucket = s3.Bucket.fromBucketName(this, 'DataBucket', dataBucketName);
    dataBucket.grantReadWrite(mwaaRole);

    // Glue 접근 권한
    mwaaRole.addToPolicy(
      new iam.PolicyStatement({
        actions: [
          'glue:StartJobRun',
          'glue:GetJobRun',
          'glue:GetJobRuns',
          'glue:BatchStopJobRun',
        ],
        resources: [
          `arn:aws:glue:${this.region}:${this.account}:job/${glueJobName}`,
        ],
      })
    );

    // Airflow 환경 변수
    const airflowConfigurationOptions: { [key: string]: string } = {
      'core.default_timezone': 'Asia/Seoul',
      'webserver.default_ui_timezone': 'Asia/Seoul',
      'logging.logging_level': 'INFO',
    };

    // MWAA 환경 생성
    this.mwaaEnvironment = new mwaa.CfnEnvironment(this, 'MwaaEnvironment', {
      name: 'neologism-extraction-env',
      airflowVersion: '3.0.0',
      sourceBucketArn: this.mwaaBucket.bucketArn,
      dagS3Path: 'dags/',
      // requirementsS3Path: 'requirements.txt', // 필요시 활성화
      executionRoleArn: mwaaRole.roleArn,
      networkConfiguration: {
        subnetIds: this.vpc.privateSubnets.slice(0, 2).map(subnet => subnet.subnetId),
        securityGroupIds: [securityGroup.securityGroupId],
      },
      loggingConfiguration: {
        dagProcessingLogs: {
          enabled: true,
          logLevel: 'INFO',
        },
        schedulerLogs: {
          enabled: true,
          logLevel: 'INFO',
        },
        taskLogs: {
          enabled: true,
          logLevel: 'INFO',
        },
        webserverLogs: {
          enabled: true,
          logLevel: 'INFO',
        },
        workerLogs: {
          enabled: true,
          logLevel: 'INFO',
        },
      },
      airflowConfigurationOptions,
      environmentClass: 'mw1.small', // 최소 사양 (개발용)
      maxWorkers: 2,
      minWorkers: 1,
      webserverAccessMode: 'PUBLIC_ONLY', // 또는 PRIVATE_ONLY
    });

    // Airflow 변수 설정 (DAG에서 사용)
    // Note: 실제로는 Airflow UI나 CLI로 설정해야 함
    const airflowVariables = {
      neologism_s3_bucket: dataBucketName,
      neologism_input_prefix: 'input/raw-texts/',
      neologism_output_prefix: 'output/corpus/',
      neologism_glue_job: glueJobName,
      aws_region: this.region,
    };

    // Outputs
    new cdk.CfnOutput(this, 'MwaaEnvironmentName', {
      value: this.mwaaEnvironment.name,
      description: 'MWAA 환경 이름',
      exportName: 'NeologismMwaaEnvironment',
    });

    new cdk.CfnOutput(this, 'MwaaBucketName', {
      value: this.mwaaBucket.bucketName,
      description: 'MWAA DAG 버킷',
      exportName: 'NeologismMwaaBucket',
    });

    new cdk.CfnOutput(this, 'AirflowVariables', {
      value: JSON.stringify(airflowVariables, null, 2),
      description: 'Airflow에 설정해야 할 변수들',
    });

    new cdk.CfnOutput(this, 'MwaaWebserverUrl', {
      value: `https://${this.mwaaEnvironment.attrWebserverUrl}`,
      description: 'Airflow 웹서버 URL',
    });
  }
}
