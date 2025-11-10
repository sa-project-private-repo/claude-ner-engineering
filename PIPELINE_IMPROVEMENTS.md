# MWAA 파이프라인 개선 제안

## 개요

현재 신조어 추출 파이프라인이 기본적인 데이터 처리는 잘 수행하고 있지만, 프로덕션 환경에 필요한 다음 요소들이 부족합니다:

- **관찰성(Observability)**: 파이프라인 상태를 모니터링하기 어려움
- **데이터 품질**: 입력 데이터의 품질을 검증하지 않음
- **알림**: 실패 시 기본 이메일만 발송
- **비용 최적화**: 비용 추적 및 최적화 없음
- **CI/CD**: 수동 배포로 인한 위험

---

## 🎯 우선순위별 개선 항목

### Priority 1: 즉시 구현 (1-2주)

#### 1.1 데이터 품질 모니터링

**문제:**
- 수집된 데이터가 비어있거나 품질이 낮아도 파이프라인 계속 실행
- 한글이 아닌 텍스트, 중복, 너무 짧은 텍스트 등을 검증하지 않음

**해결책:**

```python
# airflow/dags/data_quality_checks.py
def validate_input_data_quality(**context):
    """
    입력 데이터 품질 검증

    체크 항목:
    - 총 텍스트 수 (최소 100개)
    - 빈 텍스트 비율 (최대 10%)
    - 비한글 텍스트 비율 (최대 20%)
    - 평균 텍스트 길이 (최소 10자)
    - 중복 텍스트 수
    """
    s3_client = boto3.client('s3')
    execution_date = context['execution_date'].strftime('%Y%m%d')

    metrics = {
        'total_texts': 0,
        'empty_texts': 0,
        'short_texts': 0,
        'non_korean_texts': 0,
        'duplicate_texts': 0,
        'avg_text_length': 0,
        'sources': {}
    }

    seen_texts = set()

    # 모든 소스별 데이터 읽기
    for source in ['dcinside', 'naver_blog', 'naver_shopping', 'coupang',
                   'zigzag', 'musinsa', 'naver_news', 'instiz']:
        try:
            key = f"input/raw-texts/{execution_date}/{source}/posts.json"
            response = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
            data = json.loads(response['Body'].read().decode('utf-8'))

            if source not in metrics['sources']:
                metrics['sources'][source] = {'count': 0, 'issues': 0}

            for text in data.get('texts', []):
                metrics['total_texts'] += 1
                metrics['sources'][source]['count'] += 1

                # 빈 텍스트 체크
                if not text or not text.strip():
                    metrics['empty_texts'] += 1
                    metrics['sources'][source]['issues'] += 1
                    continue

                text_clean = text.strip()

                # 짧은 텍스트 체크
                if len(text_clean) < 5:
                    metrics['short_texts'] += 1
                    metrics['sources'][source]['issues'] += 1

                # 한글 비율 체크
                korean_chars = sum(1 for c in text_clean if '\uAC00' <= c <= '\uD7A3')
                if korean_chars < len(text_clean) * 0.3:
                    metrics['non_korean_texts'] += 1
                    metrics['sources'][source]['issues'] += 1

                # 중복 체크
                if text_clean in seen_texts:
                    metrics['duplicate_texts'] += 1
                else:
                    seen_texts.add(text_clean)

        except Exception as e:
            print(f"소스 {source} 읽기 실패: {e}")
            continue

    # 평균 길이 계산
    if metrics['total_texts'] > 0:
        total_length = sum(len(t) for t in seen_texts)
        metrics['avg_text_length'] = total_length / len(seen_texts)

    # 품질 임계값 체크
    quality_issues = []

    if metrics['total_texts'] < 100:
        quality_issues.append(f"데이터 수집 부족: {metrics['total_texts']}개 (최소 100개 필요)")

    if metrics['empty_texts'] > metrics['total_texts'] * 0.1:
        quality_issues.append(f"빈 텍스트 비율 과다: {metrics['empty_texts']/metrics['total_texts']*100:.1f}%")

    if metrics['non_korean_texts'] > metrics['total_texts'] * 0.2:
        quality_issues.append(f"비한글 텍스트 비율 과다: {metrics['non_korean_texts']/metrics['total_texts']*100:.1f}%")

    if metrics['avg_text_length'] < 10:
        quality_issues.append(f"평균 텍스트 길이 부족: {metrics['avg_text_length']:.1f}자")

    # CloudWatch에 메트릭 발행
    cloudwatch = boto3.client('cloudwatch')
    cloudwatch.put_metric_data(
        Namespace='NeologismPipeline/DataQuality',
        MetricData=[
            {
                'MetricName': 'TotalTexts',
                'Value': metrics['total_texts'],
                'Unit': 'Count',
                'Timestamp': context['execution_date']
            },
            {
                'MetricName': 'EmptyTextRate',
                'Value': metrics['empty_texts'] / max(metrics['total_texts'], 1) * 100,
                'Unit': 'Percent',
                'Timestamp': context['execution_date']
            },
            {
                'MetricName': 'NonKoreanTextRate',
                'Value': metrics['non_korean_texts'] / max(metrics['total_texts'], 1) * 100,
                'Unit': 'Percent',
                'Timestamp': context['execution_date']
            },
            {
                'MetricName': 'AverageTextLength',
                'Value': metrics['avg_text_length'],
                'Unit': 'None',
                'Timestamp': context['execution_date']
            }
        ]
    )

    # 메트릭 저장 (S3)
    metrics_key = f"output/metrics/{execution_date}/input_quality.json"
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=metrics_key,
        Body=json.dumps(metrics, ensure_ascii=False, indent=2).encode('utf-8'),
        ContentType='application/json'
    )

    # 심각한 문제 시 실패
    if quality_issues:
        error_msg = "데이터 품질 검증 실패:\n" + "\n".join(f"  - {issue}" for issue in quality_issues)
        print(error_msg)

        # 50개 미만이면 치명적 오류
        if metrics['total_texts'] < 50:
            raise ValueError(error_msg)
        else:
            # 경고만 발행
            context['task_instance'].xcom_push(key='quality_warnings', value=quality_issues)

    print(f"✅ 데이터 품질 검증 완료:")
    print(f"  - 총 텍스트: {metrics['total_texts']}개")
    print(f"  - 유효 텍스트: {len(seen_texts)}개 (중복 제거)")
    print(f"  - 평균 길이: {metrics['avg_text_length']:.1f}자")

    return metrics


def validate_output_data_quality(**context):
    """
    추출된 신조어 품질 검증
    """
    s3_client = boto3.client('s3')

    # 최신 출력 읽기
    latest_key = "output/corpus/latest/neologism_dict.json"
    response = s3_client.get_object(Bucket=S3_BUCKET, Key=latest_key)
    data = json.loads(response['Body'].read().decode('utf-8'))

    metrics = {
        'total_words': data['total_words'],
        'single_char_words': 0,
        'very_long_words': 0,
        'low_frequency_words': 0,
        'avg_frequency': 0,
        'avg_score': 0
    }

    total_freq = 0
    total_score = 0

    for word_entry in data['words']:
        word = word_entry['word']
        freq = word_entry['frequency']
        score = word_entry['score']

        if len(word) == 1:
            metrics['single_char_words'] += 1
        elif len(word) > 10:
            metrics['very_long_words'] += 1

        if freq < 3:
            metrics['low_frequency_words'] += 1

        total_freq += freq
        total_score += score

    if metrics['total_words'] > 0:
        metrics['avg_frequency'] = total_freq / metrics['total_words']
        metrics['avg_score'] = total_score / metrics['total_words']

    # 품질 체크
    quality_issues = []

    if metrics['total_words'] < 10:
        quality_issues.append(f"추출된 단어 수 부족: {metrics['total_words']}개")

    if metrics['single_char_words'] > metrics['total_words'] * 0.3:
        quality_issues.append(f"단일 문자 단어 과다: {metrics['single_char_words']}개")

    # CloudWatch
    cloudwatch = boto3.client('cloudwatch')
    cloudwatch.put_metric_data(
        Namespace='NeologismPipeline/DataQuality',
        MetricData=[
            {'MetricName': 'ExtractedWords', 'Value': metrics['total_words'], 'Unit': 'Count'},
            {'MetricName': 'AverageFrequency', 'Value': metrics['avg_frequency'], 'Unit': 'None'},
            {'MetricName': 'AverageScore', 'Value': metrics['avg_score'], 'Unit': 'None'}
        ]
    )

    if quality_issues:
        print(f"⚠️  출력 품질 경고: {quality_issues}")

    return metrics
```

**DAG에 추가:**

```python
# neologism_extraction_dag.py에 추가

from data_quality_checks import validate_input_data_quality, validate_output_data_quality

# 태스크 정의
validate_input_quality = PythonOperator(
    task_id='validate_input_quality',
    python_callable=validate_input_data_quality,
)

validate_output_quality = PythonOperator(
    task_id='validate_output_quality',
    python_callable=validate_output_data_quality,
)

# 의존성 업데이트
data_collection_complete >> validate_input_quality >> run_glue_job
wait_for_glue >> validate_output_quality >> validate >> notify
```

---

#### 1.2 알림 시스템 강화

**문제:**
- 기본 이메일 알림만 있음
- 심각도 구분 없음
- Slack 연동 없음
- SLA 추적 없음

**해결책:**

```python
# airflow/dags/alerting.py
import boto3
import requests
from datetime import datetime
from airflow.models import Variable

class PipelineAlerter:
    """
    다채널 알림 시스템
    """

    def __init__(self):
        self.sns = boto3.client('sns')
        self.cloudwatch = boto3.client('cloudwatch')

        # Parameter Store에서 설정 가져오기
        self.critical_topic = Variable.get('sns_critical_topic', default_var=None)
        self.warning_topic = Variable.get('sns_warning_topic', default_var=None)
        self.slack_webhook = Variable.get('slack_webhook_url', default_var=None)

    def send_critical_alert(self, title, message, context):
        """
        긴급 알림 (SNS + Slack + CloudWatch 알람)
        """
        full_message = self._format_message(title, message, context, '🚨 긴급')

        # SNS 발송
        if self.critical_topic:
            self.sns.publish(
                TopicArn=self.critical_topic,
                Subject=f"🚨 [긴급] {title}",
                Message=full_message
            )

        # Slack 발송
        if self.slack_webhook:
            self._send_slack(title, message, context, 'danger')

        print(f"🚨 긴급 알림 발송: {title}")

    def send_warning_alert(self, title, message, context):
        """
        경고 알림 (SNS + Slack)
        """
        full_message = self._format_message(title, message, context, '⚠️  경고')

        # SNS 발송
        if self.warning_topic:
            self.sns.publish(
                TopicArn=self.warning_topic,
                Subject=f"⚠️  [경고] {title}",
                Message=full_message
            )

        # Slack 발송
        if self.slack_webhook:
            self._send_slack(title, message, context, 'warning')

        print(f"⚠️  경고 알림 발송: {title}")

    def send_sla_breach_alert(self, expected_minutes, actual_minutes, context):
        """
        SLA 위반 알림
        """
        breach_minutes = actual_minutes - expected_minutes

        message = f"""
파이프라인 SLA 위반

예상 실행 시간: {expected_minutes}분
실제 실행 시간: {actual_minutes}분
초과 시간: {breach_minutes}분

DAG: {context['dag_id']}
Task: {context['task_id']}
실행 일시: {context['execution_date']}
"""
        self.send_warning_alert('SLA 위반', message, context)

    def send_data_quality_alert(self, issues, metrics, context):
        """
        데이터 품질 이슈 알림
        """
        severity = '긴급' if len(issues) > 3 else '경고'

        message = f"""
데이터 품질 이슈 감지

문제점:
{chr(10).join(f'  - {issue}' for issue in issues)}

메트릭:
  - 총 텍스트: {metrics.get('total_texts', 0)}개
  - 빈 텍스트 비율: {metrics.get('empty_texts', 0) / max(metrics.get('total_texts', 1), 1) * 100:.1f}%
  - 평균 길이: {metrics.get('avg_text_length', 0):.1f}자

실행 일시: {context['execution_date']}
"""

        if severity == '긴급':
            self.send_critical_alert('데이터 품질 실패', message, context)
        else:
            self.send_warning_alert('데이터 품질 경고', message, context)

    def _format_message(self, title, message, context, severity):
        """메시지 포맷팅"""
        task_instance = context.get('task_instance')
        log_url = task_instance.log_url if task_instance else 'N/A'

        return f"""
{severity}: {title}

{message}

상세 정보:
  - DAG: {context.get('dag_id', 'N/A')}
  - Task: {context.get('task_id', 'N/A')}
  - 실행 일시: {context.get('execution_date', 'N/A')}
  - 로그: {log_url}

발생 시각: {datetime.now().isoformat()}
"""

    def _send_slack(self, title, message, context, color):
        """Slack 알림 발송"""
        if not self.slack_webhook:
            return

        emoji_map = {
            'danger': '🚨',
            'warning': '⚠️',
            'good': '✅'
        }

        payload = {
            "attachments": [{
                "color": color,
                "title": f"{emoji_map.get(color, '')} {title}",
                "text": message,
                "fields": [
                    {"title": "DAG", "value": context.get('dag_id', 'N/A'), "short": True},
                    {"title": "Task", "value": context.get('task_id', 'N/A'), "short": True},
                    {"title": "실행 일시", "value": str(context.get('execution_date', 'N/A')), "short": False}
                ],
                "footer": "신조어 추출 파이프라인",
                "ts": int(datetime.now().timestamp())
            }]
        }

        try:
            requests.post(self.slack_webhook, json=payload, timeout=5)
        except Exception as e:
            print(f"Slack 알림 발송 실패: {e}")


def on_failure_callback(context):
    """태스크 실패 시 자동 호출"""
    alerter = PipelineAlerter()

    task_instance = context['task_instance']
    exception = context.get('exception')

    message = f"""
태스크 실패: {task_instance.task_id}

예외: {str(exception)}

실행 시간: {task_instance.duration}초
재시도 횟수: {task_instance.try_number}/{task_instance.max_tries}

로그: {task_instance.log_url}
"""

    alerter.send_critical_alert(
        f"태스크 실패: {task_instance.task_id}",
        message,
        context
    )


def on_retry_callback(context):
    """태스크 재시도 시 자동 호출"""
    alerter = PipelineAlerter()

    task_instance = context['task_instance']

    message = f"""
태스크 재시도 중: {task_instance.task_id}

재시도: {task_instance.try_number}/{task_instance.max_tries}
실행 시간: {task_instance.duration}초
"""

    alerter.send_warning_alert(
        f"태스크 재시도: {task_instance.task_id}",
        message,
        context
    )


def on_sla_miss_callback(dag, task_list, blocking_task_list, slas, blocking_tis):
    """SLA 위반 시 자동 호출"""
    alerter = PipelineAlerter()

    message = f"""
SLA 위반 감지

위반 태스크: {', '.join([t.task_id for t in task_list])}
차단 태스크: {', '.join([t.task_id for t in blocking_task_list])}
"""

    alerter.send_warning_alert('SLA 위반', message, {})
```

**DAG 설정 업데이트:**

```python
# neologism_extraction_dag.py에서 default_args 업데이트

from alerting import on_failure_callback, on_retry_callback, on_sla_miss_callback

default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'email': ['data-team@example.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=2),
    'on_failure_callback': on_failure_callback,  # ✨ 추가
    'on_retry_callback': on_retry_callback,      # ✨ 추가
    'sla': timedelta(hours=1),                   # ✨ 추가
}

with DAG(
    dag_id='neologism_extraction_pipeline',
    default_args=default_args,
    description='신조어 추출 및 코퍼스 생성 파이프라인',
    schedule_interval='0 2 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=['nlp', 'neologism', 'corpus', 'glue', 'daily'],
    sla_miss_callback=on_sla_miss_callback,  # ✨ 추가
) as dag:
    # ... 기존 코드
```

**Airflow Variables 설정:**

```bash
# AWS Systems Manager Parameter Store에 설정 저장
aws ssm put-parameter \
  --name "/airflow/variables/sns_critical_topic" \
  --value "arn:aws:sns:us-east-1:ACCOUNT:neologism-critical-alerts" \
  --type "String"

aws ssm put-parameter \
  --name "/airflow/variables/sns_warning_topic" \
  --value "arn:aws:sns:us-east-1:ACCOUNT:neologism-warning-alerts" \
  --type "String"

aws ssm put-parameter \
  --name "/airflow/variables/slack_webhook_url" \
  --value "https://hooks.slack.com/services/YOUR/WEBHOOK/URL" \
  --type "SecureString"
```

---

#### 1.3 CloudWatch 대시보드

**문제:**
- 파이프라인 상태를 한눈에 볼 수 없음
- 과거 실행 통계 없음
- 트렌드 분석 불가

**해결책:**

```bash
# terraform/cloudwatch_dashboard.tf
resource "aws_cloudwatch_dashboard" "neologism_pipeline" {
  dashboard_name = "neologism-pipeline-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      # 파이프라인 처리량
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["NeologismPipeline/DataQuality", "TotalTexts", { stat = "Sum", period = 86400, label = "수집된 텍스트" }],
            [".", "ExtractedWords", { stat = "Sum", period = 86400, label = "추출된 신조어" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = "us-east-1"
          title   = "파이프라인 처리량 (일별)"
          period  = 300
          yAxis   = {
            left = { label = "개수" }
          }
        }
      },

      # 데이터 품질 지표
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["NeologismPipeline/DataQuality", "EmptyTextRate", { stat = "Average", label = "빈 텍스트 비율" }],
            [".", "NonKoreanTextRate", { stat = "Average", label = "비한글 비율" }],
            [".", "AverageTextLength", { stat = "Average", yAxis = "right", label = "평균 길이" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = "us-east-1"
          title   = "데이터 품질 메트릭"
          yAxis   = {
            left  = { label = "비율 (%)", min = 0, max = 100 }
            right = { label = "길이 (자)" }
          }
        }
      },

      # 파이프라인 실행 현황
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["AWS/States", "ExecutionsSucceeded", { stat = "Sum", label = "성공" }],
            [".", "ExecutionsFailed", { stat = "Sum", label = "실패" }],
            [".", "ExecutionsTimedOut", { stat = "Sum", label = "타임아웃" }]
          ]
          view    = "singleValue"
          region  = "us-east-1"
          title   = "파이프라인 실행 (24시간)"
          period  = 86400
        }
      },

      # Glue Job 성능
      {
        type   = "metric"
        x      = 8
        y      = 6
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["AWS/Glue", "glue.driver.aggregate.elapsedTime", { stat = "Maximum", label = "실행 시간" }],
            [".", "glue.driver.aggregate.numCompletedStages", { stat = "Sum", label = "완료 Stage" }]
          ]
          view    = "timeSeries"
          region  = "us-east-1"
          title   = "Glue Job 성능"
        }
      },

      # S3 저장 용량
      {
        type   = "metric"
        x      = 16
        y      = 6
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["AWS/S3", "BucketSizeBytes", {
              stat       = "Average"
              dimensions = { BucketName = var.s3_bucket_name, StorageType = "StandardStorage" }
              label      = "총 용량"
            }]
          ]
          view    = "timeSeries"
          region  = "us-east-1"
          title   = "S3 저장 용량"
          yAxis   = {
            left = { label = "Bytes" }
          }
        }
      },

      # 최근 에러 로그
      {
        type   = "log"
        x      = 0
        y      = 12
        width  = 24
        height = 6
        properties = {
          query   = <<-EOT
            SOURCE '/aws/mwaa/neologism-extraction-env'
            | fields @timestamp, @message
            | filter @message like /ERROR/
            | sort @timestamp desc
            | limit 20
          EOT
          region  = "us-east-1"
          title   = "최근 에러 로그"
        }
      }
    ]
  })
}
```

**CloudWatch 알람 설정:**

```bash
# terraform/cloudwatch_alarms.tf
resource "aws_cloudwatch_metric_alarm" "pipeline_failure" {
  alarm_name          = "neologism-pipeline-failure"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "ExecutionsFailed"
  namespace           = "AWS/States"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "파이프라인 실행 실패"
  alarm_actions       = [aws_sns_topic.critical_alerts.arn]
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "low_word_count" {
  alarm_name          = "neologism-low-word-count"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "ExtractedWords"
  namespace           = "NeologismPipeline/DataQuality"
  period              = "86400"
  statistic           = "Sum"
  threshold           = "50"
  alarm_description   = "추출된 신조어 수 부족"
  alarm_actions       = [aws_sns_topic.warning_alerts.arn]
  treat_missing_data  = "breaching"
}

resource "aws_cloudwatch_metric_alarm" "high_empty_text_rate" {
  alarm_name          = "neologism-high-empty-text-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "EmptyTextRate"
  namespace           = "NeologismPipeline/DataQuality"
  period              = "300"
  statistic           = "Average"
  threshold           = "20"
  alarm_description   = "빈 텍스트 비율 과다"
  alarm_actions       = [aws_sns_topic.warning_alerts.arn]
}
```

---

### Priority 2: 중기 구현 (1개월 이내)

#### 2.1 CI/CD 파이프라인

**문제:**
- 수동 배포 (위험)
- 테스트 없음
- 버전 관리 부족

**해결책:**

```yaml
# .github/workflows/deploy-pipeline.yml
name: Deploy Neologism Pipeline

on:
  push:
    branches: [main]
    paths:
      - 'airflow/dags/**'
      - 'glue_jobs/**'
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r airflow/requirements.txt
          pip install pytest pylint

      - name: Lint DAG files
        run: pylint airflow/dags/*.py

      - name: Run DAG integrity tests
        run: pytest tests/test_dag_integrity.py -v

  deploy:
    needs: test
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Deploy DAGs to S3
        run: |
          aws s3 sync airflow/dags/ s3://${{ secrets.MWAA_BUCKET }}/dags/ \
            --exclude "*.pyc" --delete

      - name: Deploy Glue scripts to S3
        run: |
          aws s3 sync glue_jobs/ s3://${{ secrets.GLUE_BUCKET }}/scripts/ \
            --exclude "*.pyc" --delete
```

---

#### 2.2 비용 최적화

**해결책:**

```python
# S3 Lifecycle Policy
resource "aws_s3_bucket_lifecycle_configuration" "neologism" {
  bucket = aws_s3_bucket.neologism.id

  rule {
    id     = "archive-old-data"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }
  }
}

# Glue Job에서 Flex 실행 사용 (34% 비용 절감)
--execution-class: FLEX
--enable-auto-scaling: true
--auto-scaling-min-workers: 2
--auto-scaling-max-workers: 10
```

---

## 구현 로드맵

### 1-2주차: Priority 1 구현
- [ ] 데이터 품질 모니터링 태스크 추가
- [ ] 알림 시스템 구현 (SNS + Slack)
- [ ] CloudWatch 대시보드 생성
- [ ] CloudWatch 알람 설정

### 3-4주차: Priority 2 구현
- [ ] CI/CD 파이프라인 구축
- [ ] S3 Lifecycle 정책 적용
- [ ] Glue Job 최적화 (Flex 실행)
- [ ] 비용 추적 메트릭 추가

---

## 예상 효과

### 안정성
- **99.5%+ 가용성**: 에러 처리 및 알림 강화
- **MTTR 50% 감소**: 즉각적인 알림 및 로그

### 비용
- **30-40% 절감**: S3 Lifecycle + Glue Flex
- **가시성 확보**: CloudWatch 대시보드

### 운영
- **제로 다운타임 배포**: CI/CD 자동화
- **품질 보장**: 데이터 검증 자동화

---

## 다음 단계

1. **Airflow Variables 설정**
```bash
aws ssm put-parameter --name "/airflow/variables/sns_critical_topic" --value "arn:..."
aws ssm put-parameter --name "/airflow/variables/slack_webhook_url" --value "https://..." --type SecureString
```

2. **파일 추가**
```bash
# 신규 파일 생성
airflow/dags/data_quality_checks.py
airflow/dags/alerting.py

# 기존 파일 업데이트
airflow/dags/neologism_extraction_dag.py
```

3. **배포**
```bash
# S3에 업로드
aws s3 sync airflow/dags/ s3://YOUR-MWAA-BUCKET/dags/
```

4. **대시보드 확인**
- CloudWatch Console → Dashboards → neologism-pipeline-dashboard

---

## 문의사항

추가 기능이나 개선사항이 필요하시면 언제든지 말씀해주세요!
