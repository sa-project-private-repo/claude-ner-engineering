"""
AWS Glue Stack
Glue Job과 관련 리소스 생성
"""

from constructs import Construct
from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_glue as glue,
    aws_iam as iam,
    aws_s3_deployment as s3deploy,
    RemovalPolicy,
    Duration,
)


class GlueStack(Stack):
    """
    신조어 추출을 위한 AWS Glue 인프라 스택
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # S3 버킷: 데이터 저장소
        self.data_bucket = s3.Bucket(
            self,
            "NeologismDataBucket",
            bucket_name=f"neologism-data-{self.account}-{self.region}",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="DeleteOldRawData",
                    prefix="input/raw-texts/",
                    expiration=Duration.days(30),  # 원본 데이터는 30일 후 삭제
                ),
                s3.LifecycleRule(
                    id="TransitionOldCorpus",
                    prefix="output/corpus/",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(90),
                        )
                    ],
                ),
            ],
        )

        # S3 버킷: Glue 스크립트 저장
        self.script_bucket = s3.Bucket(
            self,
            "GlueScriptBucket",
            bucket_name=f"neologism-glue-scripts-{self.account}-{self.region}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Glue Job 스크립트 업로드
        s3deploy.BucketDeployment(
            self,
            "DeployGlueScripts",
            sources=[s3deploy.Source.asset("../glue_jobs")],
            destination_bucket=self.script_bucket,
            destination_key_prefix="scripts/",
        )

        # IAM Role: Glue Job 실행 역할
        glue_role = iam.Role(
            self,
            "GlueJobRole",
            role_name="AWSGlueServiceRole-NeologismExtraction",
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSGlueServiceRole"
                ),
            ],
        )

        # S3 접근 권한 추가
        self.data_bucket.grant_read_write(glue_role)
        self.script_bucket.grant_read(glue_role)

        # CloudWatch Logs 권한
        glue_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[f"arn:aws:logs:{self.region}:{self.account}:*"],
            )
        )

        # Glue Job 생성
        self.glue_job = glue.CfnJob(
            self,
            "NeologismExtractionJob",
            name="neologism-extraction-job",
            role=glue_role.role_arn,
            command=glue.CfnJob.JobCommandProperty(
                name="glueetl",
                python_version="3",
                script_location=f"s3://{self.script_bucket.bucket_name}/scripts/neologism_extraction_job.py",
            ),
            default_arguments={
                "--job-language": "python",
                "--enable-metrics": "true",
                "--enable-continuous-cloudwatch-log": "true",
                "--enable-spark-ui": "true",
                "--spark-event-logs-path": f"s3://{self.data_bucket.bucket_name}/spark-logs/",
                "--TempDir": f"s3://{self.data_bucket.bucket_name}/temp/",
                # 기본 파라미터
                "--INPUT_BUCKET": self.data_bucket.bucket_name,
                "--INPUT_PREFIX": "input/raw-texts/",
                "--OUTPUT_BUCKET": self.data_bucket.bucket_name,
                "--OUTPUT_PREFIX": "output/corpus/",
                "--MIN_COUNT": "5",
                "--MIN_COHESION": "0.05",
                # Python 패키지 (필요시 추가)
                "--additional-python-modules": "soynlp==0.0.493,konlpy==0.6.0",
            },
            glue_version="4.0",
            number_of_workers=2,
            worker_type="G.1X",  # 1 DPU
            timeout=120,  # 2시간
            max_retries=2,
            execution_property=glue.CfnJob.ExecutionPropertyProperty(
                max_concurrent_runs=1  # 동시 실행 제한
            ),
        )

        # Glue Database (선택사항 - Catalog 사용 시)
        self.glue_database = glue.CfnDatabase(
            self,
            "NeologismDatabase",
            catalog_id=self.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name="neologism_db",
                description="신조어 추출 데이터베이스",
            ),
        )

        # Glue Crawler (선택사항 - 자동 테이블 생성)
        crawler_role = iam.Role(
            self,
            "GlueCrawlerRole",
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSGlueServiceRole"
                ),
            ],
        )

        self.data_bucket.grant_read(crawler_role)

        self.glue_crawler = glue.CfnCrawler(
            self,
            "NeologismCrawler",
            name="neologism-corpus-crawler",
            role=crawler_role.role_arn,
            database_name=self.glue_database.ref,
            targets=glue.CfnCrawler.TargetsProperty(
                s3_targets=[
                    glue.CfnCrawler.S3TargetProperty(
                        path=f"s3://{self.data_bucket.bucket_name}/output/corpus/latest/"
                    )
                ]
            ),
            schema_change_policy=glue.CfnCrawler.SchemaChangePolicyProperty(
                update_behavior="UPDATE_IN_DATABASE",
                delete_behavior="LOG",
            ),
        )

        # Output
        from aws_cdk import CfnOutput

        CfnOutput(
            self,
            "DataBucketName",
            value=self.data_bucket.bucket_name,
            description="신조어 데이터 S3 버킷",
        )

        CfnOutput(
            self,
            "GlueJobName",
            value=self.glue_job.name,
            description="Glue Job 이름",
        )

        CfnOutput(
            self,
            "GlueDatabaseName",
            value=self.glue_database.ref,
            description="Glue Database 이름",
        )
