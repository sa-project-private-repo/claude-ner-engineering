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
 * Creates Airflow environment and related resources
 */
export class MwaaStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;
  public readonly mwaaBucket: s3.Bucket;
  public readonly mwaaEnvironment: mwaa.CfnEnvironment;

  constructor(scope: Construct, id: string, props: MwaaStackProps) {
    super(scope, id, props);

    const { dataBucketName, glueJobName } = props;

    // Create VPC (VPC is required for MWAA)
    // For MWAA high availability: 2 AZs, NAT Gateway required for each AZ
    // IMPORTANT: MWAA does not support use1-az3 (us-east-1e) in us-east-1
    this.vpc = new ec2.Vpc(this, 'MwaaVpc', {
      availabilityZones: ['us-east-1a', 'us-east-1b'], // Explicitly avoid us-east-1e (use1-az3)
      natGateways: 1, // Using 1 NAT Gateway for cost optimization
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

    // VPC Endpoints for MWAA (Cost optimization: S3 only, rest via NAT Gateway)
    // Add Gateway Endpoint for MWAA to access S3 from Private Subnet
    this.vpc.addGatewayEndpoint('S3Endpoint', {
      service: ec2.GatewayVpcEndpointAwsService.S3,
      subnets: [{ subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }],
    });

    // Security Group
    const securityGroup = new ec2.SecurityGroup(this, 'MwaaSecurityGroup', {
      vpc: this.vpc,
      description: 'Security group for MWAA environment',
      allowAllOutbound: true,
    });

    // Self-referencing rule (MWAA requirement)
    securityGroup.addIngressRule(
      securityGroup,
      ec2.Port.allTraffic(),
      'Allow all traffic within security group'
    );

    // S3 Bucket: Airflow DAGs, Plugins, Requirements
    this.mwaaBucket = new s3.Bucket(this, 'MwaaBucket', {
      // CDK auto-generates unique name if bucketName not specified
      // If explicit name needed: bucketName: `neologism-mwaa-${this.account}-${this.region}`,
      versioned: true, // MWAA requirement
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true, // Auto-delete all objects on stack delete/update
    });

    // Upload DAG files
    const dagDeployment = new s3deploy.BucketDeployment(this, 'DeployDags', {
      sources: [s3deploy.Source.asset('../airflow/dags')],
      destinationBucket: this.mwaaBucket,
      destinationKeyPrefix: 'dags/',
    });

    // Upload requirements.txt
    const requirementsDeployment = new s3deploy.BucketDeployment(this, 'DeployRequirements', {
      sources: [s3deploy.Source.asset('../airflow', {
        exclude: ['dags/**'],
      })],
      destinationBucket: this.mwaaBucket,
      destinationKeyPrefix: '',
    });

    // IAM Role: MWAA execution role
    const mwaaRole = new iam.Role(this, 'MwaaExecutionRole', {
      assumedBy: new iam.CompositePrincipal(
        new iam.ServicePrincipal('airflow.amazonaws.com'),
        new iam.ServicePrincipal('airflow-env.amazonaws.com')
      ),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('CloudWatchFullAccess'),
      ],
    });

    // S3 access permissions
    this.mwaaBucket.grantReadWrite(mwaaRole);

    // Add explicit permissions for MWAA to validate S3 paths
    mwaaRole.addToPolicy(
      new iam.PolicyStatement({
        actions: [
          's3:ListBucket',
          's3:GetBucketLocation',
          's3:GetBucketVersioning',
          's3:ListBucketVersions',
        ],
        resources: [this.mwaaBucket.bucketArn],
      })
    );

    mwaaRole.addToPolicy(
      new iam.PolicyStatement({
        actions: [
          's3:GetObject',
          's3:GetObjectVersion',
          's3:PutObject',
          's3:DeleteObject',
          's3:DeleteObjectVersion',
        ],
        resources: [`${this.mwaaBucket.bucketArn}/*`],
      })
    );

    // Data bucket access permissions
    const dataBucket = s3.Bucket.fromBucketName(this, 'DataBucket', dataBucketName);
    dataBucket.grantReadWrite(mwaaRole);

    // Glue access permissions (Required for GlueJobOperator)
    mwaaRole.addToPolicy(
      new iam.PolicyStatement({
        actions: [
          'glue:GetJob',           // Required to check if job exists
          'glue:StartJobRun',      // Required to start job
          'glue:GetJobRun',        // Required to get job run status
          'glue:GetJobRuns',       // Required to list job runs
          'glue:BatchStopJobRun',  // Required to stop job runs
        ],
        resources: [
          `arn:aws:glue:${this.region}:${this.account}:job/${glueJobName}`,
        ],
      })
    );

    // EC2/VPC permissions (Required for MWAA to create/manage ENI)
    mwaaRole.addToPolicy(
      new iam.PolicyStatement({
        actions: [
          'ec2:CreateNetworkInterface',
          'ec2:DescribeNetworkInterfaces',
          'ec2:CreateNetworkInterfacePermission',
          'ec2:DeleteNetworkInterface',
          'ec2:DeleteNetworkInterfacePermission',
          'ec2:DescribeSubnets',
          'ec2:DescribeVpcs',
          'ec2:DescribeSecurityGroups',
          'ec2:DescribeRouteTables',
        ],
        resources: ['*'], // EC2 describe actions cannot be resource-restricted
      })
    );

    // CloudWatch Logs permissions (Create log groups/streams)
    mwaaRole.addToPolicy(
      new iam.PolicyStatement({
        actions: [
          'logs:CreateLogGroup',
          'logs:CreateLogStream',
          'logs:PutLogEvents',
          'logs:GetLogEvents',
          'logs:GetLogRecord',
          'logs:GetLogGroupFields',
          'logs:GetQueryResults',
          'logs:DescribeLogGroups',
        ],
        resources: [
          `arn:aws:logs:${this.region}:${this.account}:log-group:airflow-*`,
        ],
      })
    );

    // REQUIRED: airflow:PublishMetrics permission for MWAA environment monitoring
    mwaaRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['airflow:PublishMetrics'],
        resources: [
          `arn:aws:airflow:${this.region}:${this.account}:environment/neologism-extraction-env`,
        ],
      })
    );

    // REQUIRED: SQS permissions for Airflow Celery task queue
    mwaaRole.addToPolicy(
      new iam.PolicyStatement({
        actions: [
          'sqs:ChangeMessageVisibility',
          'sqs:DeleteMessage',
          'sqs:GetQueueAttributes',
          'sqs:GetQueueUrl',
          'sqs:ReceiveMessage',
          'sqs:SendMessage',
        ],
        resources: [
          `arn:aws:sqs:${this.region}:*:airflow-celery-*`,
        ],
      })
    );

    // REQUIRED: KMS permissions for AWS owned key (via SQS)
    // Using NotResource to allow access to AWS-owned keys outside the account
    mwaaRole.addToPolicy(
      new iam.PolicyStatement({
        actions: [
          'kms:Decrypt',
          'kms:DescribeKey',
          'kms:GenerateDataKey*',
          'kms:Encrypt',
        ],
        notResources: [
          `arn:aws:kms:*:${this.account}:key/*`,
        ],
        conditions: {
          StringLike: {
            'kms:ViaService': [
              `sqs.${this.region}.amazonaws.com`,
            ],
          },
        },
      })
    );

    // REQUIRED: CloudWatch metrics permission
    mwaaRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['cloudwatch:PutMetricData'],
        resources: ['*'],
      })
    );

    // REQUIRED: S3 public access block check
    mwaaRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['s3:GetAccountPublicAccessBlock'],
        resources: ['*'],
      })
    );

    // Airflow environment variables
    const airflowConfigurationOptions: { [key: string]: string } = {
      'core.default_timezone': 'Asia/Seoul',
      'webserver.default_ui_timezone': 'Asia/Seoul',
      'logging.logging_level': 'INFO',
    };

    // Create MWAA environment
    this.mwaaEnvironment = new mwaa.CfnEnvironment(this, 'MwaaEnvironment', {
      name: 'neologism-extraction-env',
      // Use Airflow 2.9.2 (stable and supported in all regions)
      // To use Airflow 3.x: '3.0.6' (only supported in some regions)
      airflowVersion: '2.9.2',
      sourceBucketArn: this.mwaaBucket.bucketArn,
      dagS3Path: 'dags/',
      requirementsS3Path: 'requirements.txt', // Additional packages for web crawling (requests, beautifulsoup4)
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
      environmentClass: 'mw1.medium', // Medium spec - increased for faster provisioning
      maxWorkers: 2,
      minWorkers: 1,
      // Set to PUBLIC_ONLY - dev/test environment
      // For production, PRIVATE_ONLY recommended (requires VPN or SSM)
      webserverAccessMode: 'PUBLIC_ONLY',
    });

    // Set dependency so MWAA environment is created after DAG deployment
    this.mwaaEnvironment.node.addDependency(dagDeployment);
    this.mwaaEnvironment.node.addDependency(requirementsDeployment); // requirements not used but file kept in S3

    // Airflow variable configuration (used in DAGs)
    // Note: Actually needs to be set via Airflow UI or CLI
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
      description: 'MWAA environment name',
      exportName: 'NeologismMwaaEnvironment',
    });

    new cdk.CfnOutput(this, 'MwaaBucketName', {
      value: this.mwaaBucket.bucketName,
      description: 'MWAA DAG bucket',
      exportName: 'NeologismMwaaBucket',
    });

    new cdk.CfnOutput(this, 'AirflowVariables', {
      value: JSON.stringify(airflowVariables, null, 2),
      description: 'Variables to be set in Airflow',
    });

    new cdk.CfnOutput(this, 'MwaaWebserverUrl', {
      value: `https://${this.mwaaEnvironment.attrWebserverUrl}`,
      description: 'Airflow webserver URL',
    });
  }
}
