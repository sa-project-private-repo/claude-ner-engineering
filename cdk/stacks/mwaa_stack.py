"""
AWS MWAA (Managed Workflows for Apache Airflow) Stack
Airflow 환경 및 관련 리소스 생성
"""

from constructs import Construct
from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_s3_deployment as s3deploy,
    RemovalPolicy,
    CfnOutput,
)
from aws_cdk.aws_mwaa_alpha import (
    CfnEnvironment,
)


class MWAAStack(Stack):
    """
    Apache Airflow (MWAA) 인프라 스택
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        data_bucket_name: str,
        glue_job_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.data_bucket_name = data_bucket_name
        self.glue_job_name = glue_job_name

        # VPC 생성 (MWAA는 VPC 필수)
        self.vpc = ec2.Vpc(
            self,
            "MwaaVpc",
            max_azs=2,
            nat_gateways=1,  # 비용 절감을 위해 1개만
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
        )

        # Security Group
        self.security_group = ec2.SecurityGroup(
            self,
            "MwaaSecurityGroup",
            vpc=self.vpc,
            description="Security group for MWAA environment",
            allow_all_outbound=True,
        )

        # Self-referencing rule (MWAA 요구사항)
        self.security_group.add_ingress_rule(
            peer=self.security_group,
            connection=ec2.Port.all_traffic(),
            description="Allow all traffic within security group",
        )

        # S3 버킷: Airflow DAGs, Plugins, Requirements
        self.mwaa_bucket = s3.Bucket(
            self,
            "MwaaBucket",
            bucket_name=f"neologism-mwaa-{self.account}-{self.region}",
            versioned=True,  # MWAA 요구사항
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # DAG 파일 업로드
        s3deploy.BucketDeployment(
            self,
            "DeployDags",
            sources=[s3deploy.Source.asset("../airflow/dags")],
            destination_bucket=self.mwaa_bucket,
            destination_key_prefix="dags/",
        )

        # requirements.txt 생성 및 업로드
        requirements_content = """
apache-airflow-providers-amazon>=8.0.0
boto3>=1.26.0
"""

        # Requirements 파일 업로드 (실제로는 파일로 만들어 업로드)
        # 여기서는 간단히 주석 처리
        # s3deploy.BucketDeployment(...) 사용

        # IAM Role: MWAA 실행 역할
        mwaa_role = iam.Role(
            self,
            "MwaaExecutionRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("airflow.amazonaws.com"),
                iam.ServicePrincipal("airflow-env.amazonaws.com"),
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "CloudWatchFullAccess"
                ),
            ],
        )

        # S3 접근 권한
        self.mwaa_bucket.grant_read_write(mwaa_role)

        # 데이터 버킷 접근 권한
        data_bucket = s3.Bucket.from_bucket_name(
            self, "DataBucket", self.data_bucket_name
        )
        data_bucket.grant_read_write(mwaa_role)

        # Glue 접근 권한
        mwaa_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "glue:StartJobRun",
                    "glue:GetJobRun",
                    "glue:GetJobRuns",
                    "glue:BatchStopJobRun",
                ],
                resources=[
                    f"arn:aws:glue:{self.region}:{self.account}:job/{self.glue_job_name}"
                ],
            )
        )

        # Airflow 환경 변수
        airflow_configuration_options = {
            "core.default_timezone": "Asia/Seoul",
            "webserver.default_ui_timezone": "Asia/Seoul",
            "logging.logging_level": "INFO",
        }

        # MWAA 환경 생성
        self.mwaa_environment = CfnEnvironment(
            self,
            "MwaaEnvironment",
            name="neologism-extraction-env",
            airflow_version="2.7.2",
            source_bucket_arn=self.mwaa_bucket.bucket_arn,
            dag_s3_path="dags/",
            # requirements_s3_path="requirements.txt",  # 필요시 활성화
            execution_role_arn=mwaa_role.role_arn,
            network_configuration=CfnEnvironment.NetworkConfigurationProperty(
                subnet_ids=[
                    subnet.subnet_id
                    for subnet in self.vpc.private_subnets[:2]
                ],
                security_group_ids=[self.security_group.security_group_id],
            ),
            logging_configuration=CfnEnvironment.LoggingConfigurationProperty(
                dag_processing_logs=CfnEnvironment.ModuleLoggingConfigurationProperty(
                    enabled=True,
                    log_level="INFO",
                ),
                scheduler_logs=CfnEnvironment.ModuleLoggingConfigurationProperty(
                    enabled=True,
                    log_level="INFO",
                ),
                task_logs=CfnEnvironment.ModuleLoggingConfigurationProperty(
                    enabled=True,
                    log_level="INFO",
                ),
                webserver_logs=CfnEnvironment.ModuleLoggingConfigurationProperty(
                    enabled=True,
                    log_level="INFO",
                ),
                worker_logs=CfnEnvironment.ModuleLoggingConfigurationProperty(
                    enabled=True,
                    log_level="INFO",
                ),
            ),
            airflow_configuration_options=airflow_configuration_options,
            environment_class="mw1.small",  # 최소 사양 (개발용)
            max_workers=2,
            min_workers=1,
            webserver_access_mode="PUBLIC_ONLY",  # 또는 PRIVATE_ONLY
        )

        # Airflow 변수 설정 (DAG에서 사용)
        # Note: 실제로는 Airflow UI나 CLI로 설정해야 함
        # 여기서는 참고용으로 표시
        self.airflow_variables = {
            "neologism_s3_bucket": self.data_bucket_name,
            "neologism_input_prefix": "input/raw-texts/",
            "neologism_output_prefix": "output/corpus/",
            "neologism_glue_job": self.glue_job_name,
            "aws_region": self.region,
        }

        # Output
        CfnOutput(
            self,
            "MwaaEnvironmentName",
            value=self.mwaa_environment.name,
            description="MWAA 환경 이름",
        )

        CfnOutput(
            self,
            "MwaaBucketName",
            value=self.mwaa_bucket.bucket_name,
            description="MWAA DAG 버킷",
        )

        CfnOutput(
            self,
            "AirflowVariables",
            value=str(self.airflow_variables),
            description="Airflow에 설정해야 할 변수들",
        )

        CfnOutput(
            self,
            "MwaaWebserverUrl",
            value=f"https://{self.mwaa_environment.attr_webserver_url}",
            description="Airflow 웹서버 URL",
        )
