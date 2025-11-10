# API Setup Guide - Quick Start

This guide will help you set up API-based data collection to replace web scraping in **under 30 minutes**.

---

## Overview

We're replacing web scraping with 3 FREE API sources:

1. **Naver Search API** (PRIMARY - 300-1000 texts/day)
2. **RSS Feeds** (SECONDARY - 200-400 texts/day)
3. **YouTube Data API** (OPTIONAL - 100-300 comments/day)

**Total Expected:** 500-1500+ Korean texts/day at **$0 cost**

---

## Setup Instructions

### Step 1: Naver Search API (15 minutes) - REQUIRED

**Why:** Korean-native platform, high-quality content, FREE 25,000 requests/day

#### 1.1 Register for Naver Developers Account

1. Go to https://developers.naver.com/
2. Click "Application 등록" (Register Application)
3. Login with Naver account (create one if needed)

#### 1.2 Create Application

1. Click "애플리케이션 등록" (Register Application)
2. Fill in application details:
   - **Application Name:** Korean Neologism Extractor
   - **Use APIs:** Select "검색" (Search)
   - **Environment:** Select "WEB 설정" (Web Settings)
   - **Web Service URL:** http://localhost (for testing)

3. Click "등록하기" (Register)

#### 1.3 Get Credentials

After registration, you'll see:
- **Client ID:** `ABC123xyz...`
- **Client Secret:** `XYZ789abc...`

**Save these!** You'll need them for configuration.

#### 1.4 Test API

```bash
# Test with curl (replace YOUR_CLIENT_ID and YOUR_CLIENT_SECRET)
curl "https://openapi.naver.com/v1/search/blog.json?query=패션&display=10" \
  -H "X-Naver-Client-Id: YOUR_CLIENT_ID" \
  -H "X-Naver-Client-Secret: YOUR_CLIENT_SECRET"
```

Expected response: JSON with blog search results

---

### Step 2: RSS Feeds (5 minutes) - AUTOMATIC

**Why:** Zero setup, always available, 200+ news articles/day

**No setup required!** RSS feeds work automatically.

Test it:
```bash
curl "https://www.koreaherald.com/rss/national"
```

Expected: XML feed with recent news articles

---

### Step 3: YouTube Data API (Optional, 15 minutes)

**Why:** Rich conversational Korean, 100-300 comments/day, FREE 10,000 quota/day

#### 3.1 Create Google Cloud Project

1. Go to https://console.cloud.google.com/
2. Click "Select a project" → "New Project"
3. Enter project name: "Korean Neologism"
4. Click "Create"

#### 3.2 Enable YouTube Data API

1. Go to "APIs & Services" → "Library"
2. Search for "YouTube Data API v3"
3. Click "Enable"

#### 3.3 Create API Key

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "API Key"
3. Copy the API key: `AIzaSy...`
4. (Optional) Click "Restrict Key" to limit to YouTube Data API v3

#### 3.4 Test API

```bash
# Test with curl (replace YOUR_API_KEY)
curl "https://www.googleapis.com/youtube/v3/search?part=snippet&q=패션&type=video&relevanceLanguage=ko&maxResults=5&key=YOUR_API_KEY"
```

Expected response: JSON with Korean video search results

---

## Configuration

### Option 1: Environment Variables (Recommended)

Create `.env` file in project root:

```bash
# Required
NAVER_CLIENT_ID=your_naver_client_id_here
NAVER_CLIENT_SECRET=your_naver_client_secret_here

# Optional (YouTube)
YOUTUBE_API_KEY=your_youtube_api_key_here
```

Load in Python:
```python
from dotenv import load_dotenv
load_dotenv()
```

### Option 2: Airflow Variables

Set in Airflow UI (Admin → Variables):

| Key | Value | Description |
|-----|-------|-------------|
| `naver_client_id` | `YOUR_CLIENT_ID` | Naver API Client ID |
| `naver_client_secret` | `YOUR_CLIENT_SECRET` | Naver API Client Secret |
| `youtube_api_key` | `YOUR_API_KEY` | YouTube API Key (optional) |

### Option 3: AWS Secrets Manager (Production)

```bash
# Store in AWS Secrets Manager
aws secretsmanager create-secret \
  --name neologism/api-credentials \
  --secret-string '{
    "naver_client_id": "YOUR_CLIENT_ID",
    "naver_client_secret": "YOUR_CLIENT_SECRET",
    "youtube_api_key": "YOUR_API_KEY"
  }'
```

---

## Testing

### Quick Test (Local)

```bash
cd /home/ec2-user/workspace/claude-ner-engineering

# Set environment variables
export NAVER_CLIENT_ID="your_client_id"
export NAVER_CLIENT_SECRET="your_client_secret"
export YOUTUBE_API_KEY="your_api_key"  # Optional

# Run test
python src/neologism_extractor/api_collectors.py
```

Expected output:
```
API-based Data Collection Example
==================================================
Naver API collector initialized
RSS feed collector initialized
YouTube API collector initialized

=== Collecting from Naver API ===
Searching Naver for: 패션
Searching Naver for: 뷰티
Searching Naver for: 맛집
Naver: 600 texts

=== Collecting from RSS Feeds ===
Fetching RSS feed: yonhap_all
Fetching RSS feed: koreaherald_national
...
RSS: 280 texts

=== Collecting from YouTube ===
Searching YouTube for: 패션
Searching YouTube for: 뷰티
YouTube: 180 comments

=== Total collected: 1060 texts ===
```

### Test Individual Collectors

#### Test Naver API Only
```python
from src.neologism_extractor.api_collectors import NaverSearchCollector

collector = NaverSearchCollector(
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET"
)

# Test blog search
blogs = collector.search_blog("패션", display=10)
print(f"Found {len(blogs)} blog posts")
print(blogs[0])  # Sample output
```

#### Test RSS Feeds Only
```python
from src.neologism_extractor.api_collectors import RSSFeedCollector

collector = RSSFeedCollector()
texts = collector.collect(max_items_per_feed=10)
print(f"Found {len(texts)} articles")
print(texts[0])  # Sample output
```

#### Test YouTube API Only
```python
from src.neologism_extractor.api_collectors import YouTubeCommentsCollector

collector = YouTubeCommentsCollector(api_key="YOUR_API_KEY")
comments = collector.collect(keywords=["패션"], videos_per_keyword=2, comments_per_video=10)
print(f"Found {len(comments)} comments")
print(comments[0])  # Sample output
```

---

## Integration with Existing Pipeline

### Update data_collector.py

```python
# src/neologism_extractor/data_collector.py

from .api_collectors import HybridDataCollector

class DataCollector:
    """Updated data collector using APIs instead of web scraping"""

    def __init__(self):
        # Initialize API-based hybrid collector
        self.api_collector = HybridDataCollector(
            naver_client_id=os.getenv('NAVER_CLIENT_ID'),
            naver_client_secret=os.getenv('NAVER_CLIENT_SECRET'),
            youtube_api_key=os.getenv('YOUTUBE_API_KEY'),
            use_rss=True
        )

    def collect_and_merge(self, **kwargs) -> List[str]:
        """Collect from APIs and RSS feeds"""
        return self.api_collector.collect(**kwargs)
```

### Update Airflow DAG

```python
# airflow/dags/neologism_extraction_dag.py

from airflow.models import Variable

def collect_data_task(**context):
    """Collect data using APIs"""
    from neologism_extractor.api_collectors import HybridDataCollector

    # Get credentials from Airflow Variables
    collector = HybridDataCollector(
        naver_client_id=Variable.get("naver_client_id"),
        naver_client_secret=Variable.get("naver_client_secret"),
        youtube_api_key=Variable.get("youtube_api_key", default_var=None),
        use_rss=True
    )

    # Collect data
    texts = collector.collect(
        naver_keywords=["패션", "뷰티", "맛집", "여행", "쇼핑"],
        youtube_keywords=["패션", "뷰티", "먹방"]
    )

    print(f"Collected {len(texts)} texts from APIs")

    # Save to S3
    s3_bucket = Variable.get("neologism_s3_bucket")
    s3_prefix = Variable.get("neologism_input_prefix")

    # ... save to S3 (existing logic)

    return len(texts)
```

---

## Monitoring and Limits

### API Quotas

| API | Daily Limit | Our Usage | Status |
|-----|-------------|-----------|--------|
| Naver Search | 25,000 requests | ~15 requests/day | ✅ Safe (0.06%) |
| YouTube Data | 10,000 units | ~515 units/day | ✅ Safe (5%) |
| RSS Feeds | Unlimited | N/A | ✅ No limits |

### Calculate Your Usage

#### Naver API
```
Daily usage = (Keywords × Searches per keyword)
Example: 3 keywords × 3 searches (blog/news/shopping) = 9 requests/day
Limit: 25,000 requests/day
Utilization: 0.036%
```

#### YouTube API
```
Search: 100 units per request
Comments: 1 unit per request

Daily usage:
- 5 keywords × 100 units = 500 units (search)
- 15 videos × 1 unit = 15 units (comments)
- Total: 515 units/day

Limit: 10,000 units/day
Utilization: 5.15%
```

### Monitor Usage

#### Naver API
Check usage at: https://developers.naver.com/apps/#/myapps

#### YouTube API
Check quota at: https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas

### CloudWatch Metrics (Optional)

```python
import boto3

cloudwatch = boto3.client('cloudwatch')

def log_collection_metrics(texts_collected: int, source: str):
    """Log collection metrics to CloudWatch"""
    cloudwatch.put_metric_data(
        Namespace='NeologismPipeline',
        MetricData=[
            {
                'MetricName': 'TextsCollected',
                'Value': texts_collected,
                'Unit': 'Count',
                'Dimensions': [
                    {'Name': 'Source', 'Value': source}
                ]
            }
        ]
    )
```

---

## Troubleshooting

### Naver API Errors

#### Error: "Invalid client id or secret"
**Solution:** Double-check your credentials at https://developers.naver.com/apps/#/myapps

#### Error: "Quota exceeded"
**Solution:** You've hit the 25,000 requests/day limit. Wait until next day or reduce collection frequency.

#### Error: "API not enabled"
**Solution:** Make sure you selected "검색" (Search) API when registering your app.

### YouTube API Errors

#### Error: "API key not valid"
**Solution:** Check that you copied the API key correctly and it's enabled for YouTube Data API v3.

#### Error: "Quota exceeded"
**Solution:** You've used 10,000 units today. Reduce videos_per_keyword or comments_per_video parameters.

#### Error: "Comments are disabled"
**Solution:** Some videos have comments disabled. This is normal - the collector will skip them.

### RSS Feed Errors

#### Error: "Feed not found" or "403 Forbidden"
**Solution:** The RSS feed URL may have changed. Check the website for updated RSS link.

#### Error: "Parse error"
**Solution:** Some feeds have malformed XML. The collector will skip them and continue.

### General Errors

#### Error: "No data collectors available"
**Solution:** At minimum, provide Naver API credentials. RSS feeds should always work.

#### Error: "Module not found"
**Solution:** Install dependencies:
```bash
pip install requests feedparser python-dotenv
```

---

## Performance Tuning

### Optimize Collection Volume

```python
# High volume (1000+ texts/day)
collector.collect(
    naver_keywords=["패션", "뷰티", "맛집", "여행", "쇼핑", "음식"],
    youtube_keywords=["패션", "뷰티", "먹방", "브이로그"]
)

# Medium volume (500-800 texts/day) - RECOMMENDED
collector.collect(
    naver_keywords=["패션", "뷰티", "맛집"],
    youtube_keywords=["패션", "뷰티"]
)

# Low volume (300-500 texts/day)
collector.collect(
    naver_keywords=["패션", "뷰티"],
    youtube_keywords=None  # Skip YouTube
)
```

### Keyword Selection

**Good keywords for neologism extraction:**
- 패션 (fashion)
- 뷰티 (beauty)
- 맛집 (restaurants)
- 여행 (travel)
- 쇼핑 (shopping)
- 브이로그 (vlog)
- 먹방 (mukbang)
- 게임 (gaming)
- 일상 (daily life)

**Avoid:**
- Too broad: "한국" (Korea)
- Too specific: "2025년 봄 패션 트렌드"
- English keywords (we want Korean text)

---

## Cost Analysis

### Current Setup (FREE)

```
Naver API:      $0/month (FREE tier: 25,000 requests/day)
RSS Feeds:      $0/month (no limits)
YouTube API:    $0/month (FREE tier: 10,000 units/day)
AWS S3:         ~$5/month (storage)
AWS Glue:       ~$20/month (existing)
AWS MWAA:       ~$300/month (existing)
-----------------------------------------------------------
Total:          ~$325/month (same as before)
Data cost:      $0 (DOWN FROM potential scraping costs)
```

### Comparison with Alternatives

| Method | Monthly Cost | Setup Time | Maintenance |
|--------|-------------|------------|-------------|
| **APIs (Recommended)** | $0 | 30 min | Low |
| Web Scraping (current) | $0 | 2 hours | High (broken) |
| Playwright/Lambda | $20-50 | 2 days | Medium |
| Apify | $49+ | 1 hour | Low |
| Manual curation | $0 | 10 hours/month | Very High |

---

## Next Steps

### Immediate (Day 1)
1. ✅ Register for Naver API (15 min)
2. ✅ Test Naver API with curl (5 min)
3. ✅ Test RSS feeds (5 min)
4. ✅ Run `api_collectors.py` locally (5 min)

### Short-term (Week 1)
5. Update Airflow Variables with API credentials
6. Update DAG to use HybridDataCollector
7. Test end-to-end pipeline in dev environment
8. Monitor for 2-3 days

### Optional (Week 2+)
9. Register for YouTube API (if needed)
10. Add custom RSS feeds
11. Tune keywords based on neologism extraction results
12. Set up CloudWatch monitoring

---

## Support

### Documentation
- **Naver API Docs:** https://developers.naver.com/docs/serviceapi/search/
- **YouTube API Docs:** https://developers.google.com/youtube/v3
- **RSS Specification:** https://www.rssboard.org/rss-specification

### Common Issues
- See [Troubleshooting](#troubleshooting) section above
- Check `/home/ec2-user/workspace/claude-ner-engineering/ALTERNATIVE_DATA_COLLECTION_METHODS.md` for detailed analysis

### Questions?
- Review detailed implementation in `ALTERNATIVE_DATA_COLLECTION_METHODS.md`
- Check existing code in `api_collectors.py`
- Test locally first before deploying to Airflow

---

**Setup Time:** ~30 minutes (Naver + RSS)
**Expected Data:** 500-800 texts/day
**Cost:** $0
**Status:** Ready to deploy!
