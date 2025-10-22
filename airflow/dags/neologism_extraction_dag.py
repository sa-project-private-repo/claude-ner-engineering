"""
Airflow DAG: 신조어 추출 파이프라인

매일 실행되어 공공 데이터에서 신조어를 추출하고 코퍼스를 업데이트합니다.

워크플로우:
1. 데이터 수집 (SNS, AIHub)
2. AWS Glue Job 실행 (신조어 추출)
3. 결과 검증
4. 알림 전송
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.operators.glue import GlueJobOperator
from airflow.providers.amazon.aws.sensors.glue import GlueJobSensor
from airflow.providers.amazon.aws.operators.s3 import S3CreateObjectOperator
from airflow.operators.empty import EmptyOperator  # Airflow 3.0+
from airflow.models import Variable
import json
import boto3


# DAG 기본 설정
default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'email': ['data-team@example.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=2),
}

# 환경 변수 (Airflow Variables에서 설정)
S3_BUCKET = Variable.get("neologism_s3_bucket", default_var="your-bucket-name")
S3_INPUT_PREFIX = Variable.get("neologism_input_prefix", default_var="input/raw-texts/")
S3_OUTPUT_PREFIX = Variable.get("neologism_output_prefix", default_var="output/corpus/")
GLUE_JOB_NAME = Variable.get("neologism_glue_job", default_var="neologism-extraction-job")
AWS_REGION = Variable.get("aws_region", default_var="ap-northeast-2")


def collect_twitter_data(**context):
    """
    Twitter에서 데이터 수집하여 S3에 저장
    """
    import os

    # Twitter API 설정 (Airflow Variables 또는 Secrets Manager에서 가져오기)
    bearer_token = Variable.get("twitter_bearer_token", default_var=None)

    s3_client = boto3.client('s3', region_name=AWS_REGION)
    execution_date = context['execution_date'].strftime('%Y%m%d')

    # 샘플 데이터 (실제로는 Twitter API 호출)
    sample_tweets = [
        "오늘 완전 꿀잼이었어 ㅋㅋㅋ",
        "점메추 좀 해주세요",
        "갓생 살고 싶다",
        "이거 레알 대박",
        "오늘 TMI 하나 풀자면",
        "완전 핵인싸네 ㄷㄷ",
        "JMT 맛집 발견!",
    ]

    # JSON 형식으로 저장
    data = {
        'source': 'twitter',
        'collected_at': datetime.now().isoformat(),
        'texts': sample_tweets
    }

    # S3에 저장
    s3_key = f"{S3_INPUT_PREFIX}twitter/{execution_date}/tweets.json"
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(data, ensure_ascii=False).encode('utf-8'),
        ContentType='application/json'
    )

    print(f"Twitter 데이터 저장 완료: s3://{S3_BUCKET}/{s3_key}")
    return s3_key


def collect_aihub_data(**context):
    """
    AIHub에서 데이터 수집하여 S3에 저장
    """
    aihub_api_key = Variable.get("aihub_api_key", default_var=None)

    s3_client = boto3.client('s3', region_name=AWS_REGION)
    execution_date = context['execution_date'].strftime('%Y%m%d')

    # 샘플 데이터 (실제로는 AIHub API 호출)
    sample_texts = [
        "최근 젊은 층에서 많이 사용하는 신조어들",
        "갓생 루틴을 시작했습니다",
        "점메추가 정말 어렵네요",
    ]

    data = {
        'source': 'aihub',
        'collected_at': datetime.now().isoformat(),
        'texts': sample_texts
    }

    # S3에 저장
    s3_key = f"{S3_INPUT_PREFIX}aihub/{execution_date}/texts.json"
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(data, ensure_ascii=False).encode('utf-8'),
        ContentType='application/json'
    )

    print(f"AIHub 데이터 저장 완료: s3://{S3_BUCKET}/{s3_key}")
    return s3_key


def validate_results(**context):
    """
    Glue Job 결과 검증
    """
    s3_client = boto3.client('s3', region_name=AWS_REGION)

    # 최신 결과 파일 확인
    latest_key = f"{S3_OUTPUT_PREFIX}latest/neologism_dict.json"

    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=latest_key)
        content = response['Body'].read().decode('utf-8')
        data = json.loads(content)

        # 검증
        total_words = data.get('total_words', 0)
        words = data.get('words', [])

        print(f"검증 결과:")
        print(f"  - 총 단어 수: {total_words}")
        print(f"  - 실제 단어 수: {len(words)}")

        if total_words == 0:
            raise ValueError("신조어가 하나도 추출되지 않았습니다!")

        if total_words != len(words):
            raise ValueError("단어 수가 일치하지 않습니다!")

        # 상위 10개 출력
        print("\n상위 10개 신조어:")
        for i, word_entry in enumerate(words[:10], 1):
            print(f"  {i}. {word_entry['word']} (빈도: {word_entry['frequency']})")

        return True

    except Exception as e:
        print(f"검증 실패: {e}")
        raise


def send_notification(**context):
    """
    완료 알림 전송 (SNS, Slack 등)
    """
    execution_date = context['execution_date'].strftime('%Y-%m-%d')

    # SNS로 알림 전송 (선택사항)
    sns_topic_arn = Variable.get("notification_sns_topic", default_var=None)

    if sns_topic_arn:
        sns_client = boto3.client('sns', region_name=AWS_REGION)

        message = f"""
신조어 추출 파이프라인 완료

실행 날짜: {execution_date}
S3 결과 위치: s3://{S3_BUCKET}/{S3_OUTPUT_PREFIX}latest/

다음 단계: 검색 엔진에 코퍼스 업데이트
"""

        sns_client.publish(
            TopicArn=sns_topic_arn,
            Subject="[Airflow] 신조어 추출 완료",
            Message=message
        )

        print("SNS 알림 전송 완료")
    else:
        print("SNS 토픽이 설정되지 않아 알림을 건너뜁니다.")


# DAG 정의
with DAG(
    dag_id='neologism_extraction_pipeline',
    default_args=default_args,
    description='신조어 추출 및 코퍼스 생성 파이프라인 - 증분 업데이트 지원',
    # 스케줄링: 매일 오전 2시 KST (UTC+9 기준 전일 17시)
    # 변경하려면: '0 2 * * *' (매일), '0 2 * * 1' (매주 월요일), '0 2 1 * *' (매월 1일)
    schedule_interval='0 2 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False,  # 과거 실행 건너뛰기
    max_active_runs=1,  # 동시 실행 1개만 허용 (중복 방지)
    tags=['nlp', 'neologism', 'corpus', 'glue', 'daily'],
) as dag:

    # Task 0: 시작
    start = EmptyOperator(
        task_id='start',
    )

    # Task 1: Twitter 데이터 수집
    collect_twitter = PythonOperator(
        task_id='collect_twitter_data',
        python_callable=collect_twitter_data,
    )

    # Task 2: AIHub 데이터 수집
    collect_aihub = PythonOperator(
        task_id='collect_aihub_data',
        python_callable=collect_aihub_data,
    )

    # Task 3: 데이터 수집 완료
    data_collection_complete = EmptyOperator(
        task_id='data_collection_complete',
    )

    # Task 4: AWS Glue Job 실행 (신조어 추출 + 중복 제거 + 뜻 풀이)
    run_glue_job = GlueJobOperator(
        task_id='run_neologism_extraction_glue_job',
        job_name=GLUE_JOB_NAME,
        script_args={
            '--INPUT_BUCKET': S3_BUCKET,
            '--INPUT_PREFIX': S3_INPUT_PREFIX,
            '--OUTPUT_BUCKET': S3_BUCKET,
            '--OUTPUT_PREFIX': S3_OUTPUT_PREFIX,
            '--MIN_COUNT': '3',
            '--MIN_COHESION': '0.03',
            '--ENABLE_DEDUP': 'true',  # 중복 제거 활성화
            '--UPDATE_STRATEGY': 'merge',  # merge, replace, new_only
            '--GENERATE_DEFINITIONS': 'true',  # 뜻 풀이 생성
            '--USE_LLM': 'false',  # LLM 사용 여부 (비용 고려)
        },
        region_name=AWS_REGION,
        iam_role_name='AWSGlueServiceRole-NeologismExtraction',  # CDK에서 생성
        num_of_dpus=2,
        wait_for_completion=False,  # 비동기 실행
    )

    # Task 5: Glue Job 완료 대기
    wait_for_glue = GlueJobSensor(
        task_id='wait_for_glue_job',
        job_name=GLUE_JOB_NAME,
        run_id="{{ task_instance.xcom_pull(task_ids='run_neologism_extraction_glue_job', key='return_value')['JobRunId'] }}",
        region_name=AWS_REGION,
        poke_interval=60,  # 60초마다 체크
        timeout=3600,  # 1시간 타임아웃
    )

    # Task 6: 결과 검증
    validate = PythonOperator(
        task_id='validate_results',
        python_callable=validate_results,
    )

    # Task 7: 알림 전송
    notify = PythonOperator(
        task_id='send_notification',
        python_callable=send_notification,
    )

    # Task 8: 종료
    end = EmptyOperator(
        task_id='end',
    )

    # Task 의존성 정의
    start >> [collect_twitter, collect_aihub] >> data_collection_complete
    data_collection_complete >> run_glue_job >> wait_for_glue >> validate >> notify >> end
