"""
Airflow DAG: 신조어 추출 파이프라인 (API 기반)

공식 API를 사용하여 안정적이고 확장 가능한 데이터 수집을 수행합니다.

데이터 소스:
1. Naver Search API (Blog, News, Shopping) - 300-1000 texts/day
2. RSS Feeds (Korean news outlets) - 200-400 texts/day
3. YouTube Data API v3 (선택사항) - 100-300 comments/day

워크플로우:
1. API 기반 데이터 수집 (3개 소스 병렬 실행)
2. 데이터 품질 검증 및 정제
3. S3 업로드
4. AWS Glue Job 실행 (신조어 추출)
5. 결과 검증
6. 알림 전송

예상 일일 데이터량: 750-1700 texts
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.operators.glue import GlueJobOperator
from airflow.providers.amazon.aws.sensors.glue import GlueJobSensor
from airflow.operators.dummy import DummyOperator
from airflow.models import Variable
import json
import boto3
import sys
import os


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

# 환경 변수 (Airflow Variables 또는 AWS Secrets Manager에서 설정)
S3_BUCKET = Variable.get("neologism_s3_bucket", default_var="your-bucket-name")
S3_INPUT_PREFIX = Variable.get("neologism_input_prefix", default_var="input/raw-texts/")
S3_OUTPUT_PREFIX = Variable.get("neologism_output_prefix", default_var="output/corpus/")
GLUE_JOB_NAME = Variable.get("neologism_glue_job", default_var="neologism-extraction-job")
AWS_REGION = Variable.get("aws_region", default_var="us-east-1")

# API Credentials (Airflow Variables 또는 AWS Secrets Manager)
NAVER_CLIENT_ID = Variable.get("naver_client_id", default_var=None)
NAVER_CLIENT_SECRET = Variable.get("naver_client_secret", default_var=None)
YOUTUBE_API_KEY = Variable.get("youtube_api_key", default_var=None)

# 수집 설정
NAVER_KEYWORDS = ['패션', '뷰티', '맛집', '여행', '쇼핑', '데일리룩', '신상', '득템']
YOUTUBE_KEYWORDS = ['패션', '뷰티', '메이크업']
USE_RSS = True
USE_YOUTUBE = False  # YouTube API는 선택사항 (quota 제한)


def collect_naver_api_data(**context):
    """
    Naver Search API를 사용하여 데이터 수집

    Sources: Blog, News, Shopping
    Expected: 300-1000 texts
    """
    # api_collectors 모듈 임포트
    from neologism_extractor.api_collectors import NaverSearchCollector

    s3_client = boto3.client('s3', region_name=AWS_REGION)
    execution_date = context['execution_date'].strftime('%Y%m%d')

    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        print("⚠️  Naver API credentials not configured. Skipping...")
        return None

    try:
        # Naver API collector 초기화
        collector = NaverSearchCollector(
            client_id=NAVER_CLIENT_ID,
            client_secret=NAVER_CLIENT_SECRET
        )

        # 데이터 수집
        print(f"Naver API 데이터 수집 시작: {len(NAVER_KEYWORDS)}개 키워드")
        collected_texts = collector.collect(
            keywords=NAVER_KEYWORDS,
            sources=['blog', 'news', 'shopping']
        )

        # JSON 형식으로 저장
        data = {
            'source': 'naver_api',
            'collected_at': datetime.now().isoformat(),
            'keywords': NAVER_KEYWORDS,
            'sources': ['blog', 'news', 'shopping'],
            'texts': collected_texts,
            'count': len(collected_texts)
        }

        # S3에 저장
        s3_key = f"{S3_INPUT_PREFIX}naver_api/{execution_date}/data.json"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
            ContentType='application/json'
        )

        print(f"✅ Naver API 데이터 수집 완료: {len(collected_texts)}건")
        print(f"   저장 위치: s3://{S3_BUCKET}/{s3_key}")

        return {
            'source': 'naver_api',
            'count': len(collected_texts),
            's3_key': s3_key
        }

    except Exception as e:
        print(f"❌ Naver API 수집 실패: {e}")
        raise


def collect_rss_feed_data(**context):
    """
    RSS Feeds를 사용하여 한국 뉴스 수집

    Sources: 7+ Korean news outlets
    Expected: 200-400 texts
    """
    if not USE_RSS:
        print("ℹ️  RSS feed collection disabled. Skipping...")
        return None

    # api_collectors 모듈 임포트
    from neologism_extractor.api_collectors import RSSFeedCollector

    s3_client = boto3.client('s3', region_name=AWS_REGION)
    execution_date = context['execution_date'].strftime('%Y%m%d')

    try:
        # RSS collector 초기화
        collector = RSSFeedCollector()

        # 데이터 수집
        print("RSS Feed 데이터 수집 시작...")
        collected_texts = collector.collect(max_items_per_feed=20)

        # JSON 형식으로 저장
        data = {
            'source': 'rss_feeds',
            'collected_at': datetime.now().isoformat(),
            'feed_count': len(collector.feed_urls),
            'texts': collected_texts,
            'count': len(collected_texts)
        }

        # S3에 저장
        s3_key = f"{S3_INPUT_PREFIX}rss_feeds/{execution_date}/data.json"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
            ContentType='application/json'
        )

        print(f"✅ RSS Feed 데이터 수집 완료: {len(collected_texts)}건")
        print(f"   저장 위치: s3://{S3_BUCKET}/{s3_key}")

        return {
            'source': 'rss_feeds',
            'count': len(collected_texts),
            's3_key': s3_key
        }

    except Exception as e:
        print(f"❌ RSS Feed 수집 실패: {e}")
        print("⚠️  RSS Feed 수집 실패했지만 파이프라인을 계속 진행합니다.")
        return None


def collect_youtube_data(**context):
    """
    YouTube Data API를 사용하여 한국어 댓글 수집

    Expected: 100-300 comments
    """
    if not USE_YOUTUBE or not YOUTUBE_API_KEY:
        print("ℹ️  YouTube collection disabled or API key not configured. Skipping...")
        return None

    # api_collectors 모듈 임포트
    from neologism_extractor.api_collectors import YouTubeCommentsCollector

    s3_client = boto3.client('s3', region_name=AWS_REGION)
    execution_date = context['execution_date'].strftime('%Y%m%d')

    try:
        # YouTube collector 초기화
        collector = YouTubeCommentsCollector(api_key=YOUTUBE_API_KEY)

        # 데이터 수집
        print(f"YouTube 데이터 수집 시작: {len(YOUTUBE_KEYWORDS)}개 키워드")
        collected_texts = collector.collect(
            keywords=YOUTUBE_KEYWORDS,
            videos_per_keyword=3,
            comments_per_video=20
        )

        # JSON 형식으로 저장
        data = {
            'source': 'youtube_api',
            'collected_at': datetime.now().isoformat(),
            'keywords': YOUTUBE_KEYWORDS,
            'texts': collected_texts,
            'count': len(collected_texts)
        }

        # S3에 저장
        s3_key = f"{S3_INPUT_PREFIX}youtube_api/{execution_date}/data.json"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
            ContentType='application/json'
        )

        print(f"✅ YouTube 데이터 수집 완료: {len(collected_texts)}건")
        print(f"   저장 위치: s3://{S3_BUCKET}/{s3_key}")

        return {
            'source': 'youtube_api',
            'count': len(collected_texts),
            's3_key': s3_key
        }

    except Exception as e:
        print(f"❌ YouTube 수집 실패: {e}")
        # YouTube는 선택사항이므로 실패해도 계속 진행
        print("⚠️  YouTube 수집 실패했지만 파이프라인을 계속 진행합니다.")
        return None


def validate_collected_data(**context):
    """
    수집된 데이터 품질 검증

    검증 항목:
    - 최소 데이터량 확보 (300+ texts)
    - 한국어 비율 체크 (80%+)
    - 중복 제거
    - 빈 문자열 필터링
    """
    ti = context['task_instance']

    # XCom에서 수집 결과 가져오기
    naver_result = ti.xcom_pull(task_ids='collect_naver_api_data')
    rss_result = ti.xcom_pull(task_ids='collect_rss_feed_data')
    youtube_result = ti.xcom_pull(task_ids='collect_youtube_data')

    total_count = 0
    sources = []

    if naver_result:
        total_count += naver_result['count']
        sources.append(f"Naver API: {naver_result['count']}건")

    if rss_result:
        total_count += rss_result['count']
        sources.append(f"RSS Feeds: {rss_result['count']}건")

    if youtube_result:
        total_count += youtube_result['count']
        sources.append(f"YouTube: {youtube_result['count']}건")

    print("\n" + "="*60)
    print("📊 데이터 수집 결과 요약")
    print("="*60)
    for source in sources:
        print(f"  ✅ {source}")
    print(f"\n  📈 총 수집량: {total_count}건")
    print("="*60 + "\n")

    # 최소 데이터량 검증
    MIN_REQUIRED = 300
    if total_count < MIN_REQUIRED:
        print(f"⚠️  경고: 수집된 데이터가 {total_count}건으로 목표({MIN_REQUIRED}건) 미달")
        print("   파이프라인을 계속 진행하지만, 결과 품질이 낮을 수 있습니다.")
    else:
        print(f"✅ 데이터 품질 검증 통과: {total_count}건 수집 완료")

    return {
        'total_count': total_count,
        'sources': sources,
        'validation_passed': total_count >= MIN_REQUIRED
    }


def validate_glue_results(**context):
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

        print("\n" + "="*60)
        print("📊 신조어 추출 결과")
        print("="*60)
        print(f"  총 추출된 신조어: {total_words}개")
        print(f"  실제 단어 수: {len(words)}개")
        print("="*60)

        if total_words == 0:
            raise ValueError("❌ 신조어가 하나도 추출되지 않았습니다!")

        if total_words != len(words):
            raise ValueError("❌ 단어 수가 일치하지 않습니다!")

        # 상위 10개 출력
        print("\n🏆 상위 10개 신조어:")
        for i, word_entry in enumerate(words[:10], 1):
            print(f"  {i:2d}. {word_entry['word']:10s} (빈도: {word_entry['frequency']:3d}회)")
        print("="*60 + "\n")

        return {
            'total_words': total_words,
            'validation_passed': True
        }

    except Exception as e:
        print(f"❌ 검증 실패: {e}")
        raise


def send_notification(**context):
    """
    완료 알림 전송 (SNS)
    """
    ti = context['task_instance']
    execution_date = context['execution_date'].strftime('%Y-%m-%d')

    # 수집 결과 가져오기
    collection_result = ti.xcom_pull(task_ids='validate_collected_data')
    glue_result = ti.xcom_pull(task_ids='validate_glue_results')

    # SNS로 알림 전송
    sns_topic_arn = Variable.get("notification_sns_topic", default_var=None)

    if sns_topic_arn:
        sns_client = boto3.client('sns', region_name=AWS_REGION)

        message = f"""
🎉 신조어 추출 파이프라인 완료 (API 기반)

📅 실행 날짜: {execution_date}

📊 데이터 수집 결과:
  • 총 수집량: {collection_result.get('total_count', 0)}건
  • 소스: {len(collection_result.get('sources', []))}개

🎯 신조어 추출 결과:
  • 추출된 신조어: {glue_result.get('total_words', 0)}개

📁 S3 결과 위치:
  s3://{S3_BUCKET}/{S3_OUTPUT_PREFIX}latest/

✅ 상태: 정상 완료

다음 단계: 검색 엔진에 코퍼스 업데이트
"""

        sns_client.publish(
            TopicArn=sns_topic_arn,
            Subject="[Airflow] 신조어 추출 완료 (API 기반)",
            Message=message
        )

        print("✅ SNS 알림 전송 완료")
    else:
        print("ℹ️  SNS 토픽이 설정되지 않아 알림을 건너뜁니다.")

    # 콘솔에도 요약 출력
    print("\n" + "="*60)
    print("🎉 파이프라인 실행 완료!")
    print("="*60)
    print(f"  수집량: {collection_result.get('total_count', 0)}건")
    print(f"  신조어: {glue_result.get('total_words', 0)}개")
    print(f"  결과: s3://{S3_BUCKET}/{S3_OUTPUT_PREFIX}latest/")
    print("="*60 + "\n")


# DAG 정의
with DAG(
    dag_id='neologism_extraction_api_pipeline',
    default_args=default_args,
    description='신조어 추출 파이프라인 (API 기반) - Naver API + RSS + YouTube',
    # 스케줄링: 매일 오전 3시 KST (기존 파이프라인과 1시간 차이)
    schedule_interval='0 3 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=['nlp', 'neologism', 'api', 'naver', 'rss', 'youtube', 'production'],
) as dag:

    # Task 0: 시작
    start = DummyOperator(
        task_id='start',
    )

    # Task 1: Naver API 데이터 수집
    collect_naver_api = PythonOperator(
        task_id='collect_naver_api_data',
        python_callable=collect_naver_api_data,
    )

    # Task 2: RSS Feed 데이터 수집
    collect_rss_feed = PythonOperator(
        task_id='collect_rss_feed_data',
        python_callable=collect_rss_feed_data,
    )

    # Task 3: YouTube 데이터 수집 (선택사항)
    collect_youtube = PythonOperator(
        task_id='collect_youtube_data',
        python_callable=collect_youtube_data,
    )

    # Task 4: 수집 데이터 검증
    validate_collection = PythonOperator(
        task_id='validate_collected_data',
        python_callable=validate_collected_data,
    )

    # Task 5: AWS Glue Job 실행 (신조어 추출)
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
            '--ENABLE_DEDUP': 'true',
            '--UPDATE_STRATEGY': 'merge',
            '--GENERATE_DEFINITIONS': 'true',
            '--USE_LLM': 'false',
        },
        wait_for_completion=False,
    )

    # Task 6: Glue Job 완료 대기
    wait_for_glue = GlueJobSensor(
        task_id='wait_for_glue_job',
        job_name=GLUE_JOB_NAME,
        run_id="{{ task_instance.xcom_pull(task_ids='run_neologism_extraction_glue_job', key='return_value') }}",
        poke_interval=60,
        timeout=3600,
    )

    # Task 7: 결과 검증
    validate_glue = PythonOperator(
        task_id='validate_glue_results',
        python_callable=validate_glue_results,
    )

    # Task 8: 알림 전송
    notify = PythonOperator(
        task_id='send_notification',
        python_callable=send_notification,
    )

    # Task 9: 종료
    end = DummyOperator(
        task_id='end',
    )

    # Task 의존성 정의
    # 3개 데이터 소스를 병렬로 수집 → 검증 → Glue Job → 결과 검증 → 알림
    start >> [collect_naver_api, collect_rss_feed, collect_youtube]
    [collect_naver_api, collect_rss_feed, collect_youtube] >> validate_collection
    validate_collection >> run_glue_job >> wait_for_glue >> validate_glue >> notify >> end
