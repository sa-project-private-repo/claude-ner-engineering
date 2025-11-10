# Alternative Data Collection Methods for Korean Neologism Extraction

**Research Date:** October 28, 2025
**Target:** 300+ high-quality Korean texts daily
**Priority:** FREE or low-cost, high-quality Korean text, easy implementation, sustainable

---

## Executive Summary

This document proposes alternative data collection methods to replace failing web scraping approaches. The top 3 recommendations are:

1. **Naver Search API** (Blog, News, Shopping) - FREE tier, easy implementation, high Korean quality
2. **RSS Feeds** (News, Blogs) - FREE, zero maintenance, reliable
3. **YouTube Data API** (Comments) - FREE tier, massive Korean content, moderate complexity

---

## 1. Official APIs

### 1.1 Naver Search API (TOP RECOMMENDATION)

**Feasibility:** Easy
**Cost:** FREE (25,000 requests/day)
**Data Volume:** Up to 1,000 results per query, 300+ texts/day easily achievable
**Korean Suitability:** HIGH (Native Korean platform)
**Legal/Ethical:** Official API, fully compliant

#### Features
- **Blog Search:** User reviews, personal stories, product experiences
- **News Search:** Current events, trending topics
- **Shopping Search:** Product reviews, customer feedback
- **Cafe Search:** Community discussions

#### Implementation

```python
import requests
from typing import List, Dict
from datetime import datetime

class NaverSearchCollector:
    """Naver Search API Collector"""

    def __init__(self, client_id: str, client_secret: str):
        """
        Get credentials from: https://developers.naver.com/

        Args:
            client_id: Naver API Client ID
            client_secret: Naver API Client Secret
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://openapi.naver.com/v1/search"

    def search_blog(self, query: str, display: int = 100, start: int = 1) -> List[str]:
        """
        Search Naver blogs

        Args:
            query: Search keyword (e.g., "패션", "뷰티", "쇼핑")
            display: Results per page (max 100)
            start: Start position (1-1000)

        Returns:
            List of blog post descriptions/content
        """
        url = f"{self.base_url}/blog.json"
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret
        }
        params = {
            "query": query,
            "display": display,
            "start": start,
            "sort": "date"  # or "sim" for similarity
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            texts = []
            for item in data.get('items', []):
                # Remove HTML tags
                title = self._clean_html(item.get('title', ''))
                description = self._clean_html(item.get('description', ''))
                texts.append(f"{title} {description}")

            return texts

        except Exception as e:
            print(f"Naver Blog Search Error: {e}")
            return []

    def search_news(self, query: str, display: int = 100, start: int = 1) -> List[str]:
        """Search Naver news"""
        url = f"{self.base_url}/news.json"
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret
        }
        params = {
            "query": query,
            "display": display,
            "start": start,
            "sort": "date"
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            texts = []
            for item in data.get('items', []):
                title = self._clean_html(item.get('title', ''))
                description = self._clean_html(item.get('description', ''))
                texts.append(f"{title} {description}")

            return texts

        except Exception as e:
            print(f"Naver News Search Error: {e}")
            return []

    def search_shopping(self, query: str, display: int = 100, start: int = 1) -> List[str]:
        """Search Naver shopping reviews"""
        url = f"{self.base_url}/shop.json"
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret
        }
        params = {
            "query": query,
            "display": display,
            "start": start
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            texts = []
            for item in data.get('items', []):
                title = self._clean_html(item.get('title', ''))
                texts.append(title)

            return texts

        except Exception as e:
            print(f"Naver Shopping Search Error: {e}")
            return []

    def collect_daily_batch(self, keywords: List[str]) -> List[str]:
        """
        Collect daily batch of texts

        Args:
            keywords: List of search keywords

        Returns:
            Combined list of texts (300+ texts)
        """
        all_texts = []

        for keyword in keywords:
            # Blog search (100 results)
            blogs = self.search_blog(keyword, display=100)
            all_texts.extend(blogs)

            # News search (50 results)
            news = self.search_news(keyword, display=50)
            all_texts.extend(news)

            # Shopping search (50 results)
            shopping = self.search_shopping(keyword, display=50)
            all_texts.extend(shopping)

        return all_texts

    @staticmethod
    def _clean_html(text: str) -> str:
        """Remove HTML tags from text"""
        import re
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Decode HTML entities
        text = text.replace('&quot;', '"').replace('&amp;', '&')
        text = text.replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&nbsp;', ' ')
        return text.strip()


# Usage Example
if __name__ == "__main__":
    # Get credentials from: https://developers.naver.com/apps/#/register
    collector = NaverSearchCollector(
        client_id="YOUR_CLIENT_ID",
        client_secret="YOUR_CLIENT_SECRET"
    )

    # Define trending keywords
    keywords = [
        "패션 트렌드",
        "뷰티 추천",
        "쇼핑 후기",
        "맛집",
        "여행"
    ]

    # Collect 300+ texts
    texts = collector.collect_daily_batch(keywords)
    print(f"Collected {len(texts)} texts")

    # Expected: 300-1000 texts depending on keywords
```

#### Advantages
- Official API, no legal issues
- FREE tier: 25,000 requests/day
- High-quality Korean content
- Multiple content types (blog, news, shopping)
- Real-time trending content
- Easy to implement

#### Limitations
- Rate limiting (25,000 requests/day)
- Maximum 100 results per request
- Requires API key registration

---

### 1.2 YouTube Data API

**Feasibility:** Medium
**Cost:** FREE (10,000 quota units/day)
**Data Volume:** ~100-300 comments/day (within quota)
**Korean Suitability:** HIGH (Large Korean content creator base)
**Legal/Ethical:** Official API, compliant

#### Implementation

```python
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import List, Optional

class YouTubeCommentsCollector:
    """YouTube Data API v3 Comments Collector"""

    def __init__(self, api_key: str):
        """
        Get API key from: https://console.cloud.google.com/
        Enable YouTube Data API v3

        Args:
            api_key: Google Cloud API key
        """
        self.youtube = build('youtube', 'v3', developerKey=api_key)

    def search_korean_videos(self, query: str, max_results: int = 10) -> List[str]:
        """
        Search for Korean videos

        Args:
            query: Search term (e.g., "패션", "뷰티")
            max_results: Number of videos (default 10)

        Returns:
            List of video IDs
        """
        try:
            search_response = self.youtube.search().list(
                q=query,
                part='id',
                type='video',
                relevanceLanguage='ko',
                maxResults=max_results,
                order='date'  # Recent videos
            ).execute()

            video_ids = []
            for item in search_response.get('items', []):
                if item['id']['kind'] == 'youtube#video':
                    video_ids.append(item['id']['videoId'])

            return video_ids

        except HttpError as e:
            print(f"YouTube Search Error: {e}")
            return []

    def get_video_comments(self, video_id: str, max_comments: int = 100) -> List[str]:
        """
        Get comments from a video

        Args:
            video_id: YouTube video ID
            max_comments: Maximum comments to retrieve

        Returns:
            List of comment texts
        """
        comments = []

        try:
            # Get comment threads (costs 1 unit)
            request = self.youtube.commentThreads().list(
                part='snippet',
                videoId=video_id,
                maxResults=min(100, max_comments),  # API max is 100
                textFormat='plainText',
                order='relevance'  # or 'time'
            )

            while request and len(comments) < max_comments:
                response = request.execute()

                for item in response['items']:
                    comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
                    comments.append(comment)

                # Get next page
                request = self.youtube.commentThreads().list_next(request, response)

        except HttpError as e:
            print(f"YouTube Comments Error: {e}")

        return comments

    def collect_daily_batch(self, keywords: List[str],
                          videos_per_keyword: int = 3,
                          comments_per_video: int = 30) -> List[str]:
        """
        Collect daily batch of comments

        Quota calculation:
        - Search: 100 units per request
        - Comments: 1 unit per request

        With 10,000 daily quota:
        - 5 keywords × 100 units = 500 units (search)
        - 15 videos × 1 unit = 15 units (comments)
        - Total: ~515 units (well within limit)

        Args:
            keywords: Search keywords
            videos_per_keyword: Videos to fetch per keyword
            comments_per_video: Comments per video

        Returns:
            Combined list of comments
        """
        all_comments = []

        for keyword in keywords:
            # Search videos (100 quota units)
            video_ids = self.search_korean_videos(
                query=keyword,
                max_results=videos_per_keyword
            )

            # Get comments from each video (1 quota unit each)
            for video_id in video_ids:
                comments = self.get_video_comments(
                    video_id=video_id,
                    max_comments=comments_per_video
                )
                all_comments.extend(comments)

        return all_comments


# Usage Example
if __name__ == "__main__":
    # Get API key from Google Cloud Console
    collector = YouTubeCommentsCollector(api_key="YOUR_YOUTUBE_API_KEY")

    # Korean trending topics
    keywords = ["패션", "뷰티", "먹방", "브이로그", "쇼핑"]

    # Collect comments (300-450 comments)
    comments = collector.collect_daily_batch(
        keywords=keywords,
        videos_per_keyword=3,
        comments_per_video=30
    )

    print(f"Collected {len(comments)} comments")
```

#### Advantages
- FREE tier: 10,000 quota units/day
- Rich, conversational Korean language
- Current slang and neologisms
- Large Korean creator ecosystem

#### Limitations
- Quota system (need to manage carefully)
- Comments may contain spam/low-quality text
- Requires Google Cloud project setup

---

### 1.3 Reddit API (Korean Subreddits)

**Feasibility:** Easy
**Cost:** FREE (60 requests/minute)
**Data Volume:** 100-500 posts/day
**Korean Suitability:** MEDIUM (Smaller Korean community)
**Legal/Ethical:** Official API, compliant

#### Implementation

```python
import praw
from typing import List
from datetime import datetime, timedelta

class RedditKoreanCollector:
    """Reddit API Collector for Korean subreddits"""

    def __init__(self, client_id: str, client_secret: str, user_agent: str):
        """
        Get credentials from: https://www.reddit.com/prefs/apps
        Create a "script" app

        Args:
            client_id: Reddit app client ID
            client_secret: Reddit app secret
            user_agent: User agent string (e.g., "KoreanNeologismBot/1.0")
        """
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )

    def get_subreddit_posts(self, subreddit_name: str,
                           limit: int = 100,
                           time_filter: str = "day") -> List[str]:
        """
        Get posts from a subreddit

        Args:
            subreddit_name: Subreddit name (e.g., "korea", "korean")
            limit: Number of posts
            time_filter: "day", "week", "month"

        Returns:
            List of post titles and text
        """
        texts = []

        try:
            subreddit = self.reddit.subreddit(subreddit_name)

            # Get hot/top posts
            for submission in subreddit.top(time_filter=time_filter, limit=limit):
                # Combine title and selftext
                text = f"{submission.title}"
                if submission.selftext:
                    text += f" {submission.selftext}"
                texts.append(text)

        except Exception as e:
            print(f"Reddit API Error: {e}")

        return texts

    def get_subreddit_comments(self, subreddit_name: str,
                              limit: int = 100) -> List[str]:
        """Get recent comments from a subreddit"""
        comments = []

        try:
            subreddit = self.reddit.subreddit(subreddit_name)

            for comment in subreddit.comments(limit=limit):
                if comment.body and comment.body != "[deleted]":
                    comments.append(comment.body)

        except Exception as e:
            print(f"Reddit Comments Error: {e}")

        return comments

    def collect_daily_batch(self) -> List[str]:
        """
        Collect from multiple Korean subreddits

        Returns:
            Combined texts (200-500+ texts)
        """
        subreddits = [
            "korea",        # General Korea discussions
            "Korean",       # Korean language learning
            "kpop",         # K-pop (high engagement)
            "kdrama",       # K-drama discussions
            "hanguk"        # Korean culture
        ]

        all_texts = []

        for subreddit in subreddits:
            # Get posts (50 per subreddit)
            posts = self.get_subreddit_posts(subreddit, limit=50)
            all_texts.extend(posts)

            # Get comments (30 per subreddit)
            comments = self.get_subreddit_comments(subreddit, limit=30)
            all_texts.extend(comments)

        return all_texts


# Usage Example
if __name__ == "__main__":
    collector = RedditKoreanCollector(
        client_id="YOUR_CLIENT_ID",
        client_secret="YOUR_CLIENT_SECRET",
        user_agent="KoreanNeologismBot/1.0"
    )

    texts = collector.collect_daily_batch()
    print(f"Collected {len(texts)} texts from Reddit")
```

#### Advantages
- FREE API access
- Active Korean communities (r/korea, r/korean, r/kpop)
- Conversational language
- Easy authentication

#### Limitations
- Korean subreddits are smaller than Korean-native platforms
- Mix of English and Korean content
- API changes in 2023 (but still accessible)

---

## 2. RSS Feeds (TOP RECOMMENDATION #2)

**Feasibility:** Very Easy
**Cost:** FREE
**Data Volume:** 100-300 articles/day
**Korean Suitability:** HIGH (Major Korean news sources)
**Legal/Ethical:** Public feeds, compliant

### Implementation

```python
import feedparser
from typing import List, Dict
from datetime import datetime
import time

class RSSFeedCollector:
    """RSS Feed Collector for Korean news and blogs"""

    # Major Korean news RSS feeds
    FEEDS = {
        # Yonhap News Agency
        "yonhap_all": "https://en.yna.co.kr/RSS/news.xml",

        # Korea Herald (Updated Feb 2025)
        "koreaherald_national": "https://www.koreaherald.com/rss/national",
        "koreaherald_business": "https://www.koreaherald.com/rss/business",
        "koreaherald_life": "https://www.koreaherald.com/rss/life",

        # Korea Times
        "koreatimes_all": "https://www.koreatimes.co.kr/www2/common/rss.asp",

        # The Hankyoreh
        "hankyoreh": "https://english.hani.co.kr/arti/english_edition/english_editorials/rss",

        # KED Global (Business/Finance)
        "ked_global": "https://www.kedglobal.com/newsRss",
    }

    def fetch_feed(self, feed_url: str, max_items: int = 50) -> List[str]:
        """
        Fetch and parse RSS feed

        Args:
            feed_url: RSS feed URL
            max_items: Maximum items to fetch

        Returns:
            List of article texts (title + description)
        """
        texts = []

        try:
            feed = feedparser.parse(feed_url)

            for entry in feed.entries[:max_items]:
                title = entry.get('title', '')
                description = entry.get('description', '') or entry.get('summary', '')

                # Combine title and description
                text = f"{title} {description}".strip()
                if text:
                    texts.append(text)

        except Exception as e:
            print(f"RSS Feed Error ({feed_url}): {e}")

        return texts

    def collect_daily_batch(self, feeds_to_use: List[str] = None) -> List[str]:
        """
        Collect from all or selected feeds

        Args:
            feeds_to_use: List of feed keys (default: all feeds)

        Returns:
            Combined texts (300+ articles)
        """
        if feeds_to_use is None:
            feeds_to_use = list(self.FEEDS.keys())

        all_texts = []

        for feed_key in feeds_to_use:
            if feed_key in self.FEEDS:
                feed_url = self.FEEDS[feed_key]
                print(f"Fetching {feed_key}...")

                texts = self.fetch_feed(feed_url, max_items=50)
                all_texts.extend(texts)

                # Be polite to servers
                time.sleep(1)

        return all_texts

    def add_custom_feed(self, name: str, url: str):
        """Add a custom RSS feed"""
        self.FEEDS[name] = url


# Usage Example
if __name__ == "__main__":
    collector = RSSFeedCollector()

    # Collect from all feeds
    texts = collector.collect_daily_batch()
    print(f"Collected {len(texts)} articles from RSS feeds")

    # Add custom blog RSS feeds
    collector.add_custom_feed("custom_blog", "https://example-blog.com/rss")

    # Expected: 300-400 articles daily
```

#### Additional Korean RSS Feeds

```python
# Add these to the FEEDS dictionary:

ADDITIONAL_FEEDS = {
    # Tech News
    "korea_tech_today": "https://koreatechtoday.com/feed/",

    # Lifestyle
    "seoul_eats": "https://seoulreader.com/feed/",

    # K-pop (if relevant)
    "allkpop": "https://www.allkpop.com/feed",
    "soompi": "https://www.soompi.com/feed",
}
```

#### Advantages
- Completely FREE, no API keys needed
- Zero rate limiting
- Reliable, standardized format (RSS/Atom)
- Low maintenance
- High-quality editorial content
- Easy to add new sources

#### Limitations
- Limited to published content (not user-generated)
- Lower volume than API-based methods
- May contain more formal language than social media

---

## 3. Public Datasets

### 3.1 AI Hub (AI 허브)

**Feasibility:** Medium
**Cost:** FREE (registration required)
**Data Volume:** MASSIVE (millions of sentences)
**Korean Suitability:** HIGH (Korean government initiative)
**Legal/Ethical:** Open data, compliant

#### Available Datasets

1. **한국어-영어 번역 말뭉치** (Korean-English Translation Corpus)
   - Size: Millions of sentence pairs
   - Quality: High (professionally curated)

2. **감성 대화 말뭉치** (Sentiment Dialogue Corpus)
   - Size: Large
   - Quality: Conversational Korean

3. **Named Entity Recognition Dataset**
   - Size: 5-6 million words
   - Quality: Annotated Korean text

#### Access Process

```python
"""
AI Hub Data Access:

1. Register at https://aihub.or.kr/
2. Login and verify email
3. Apply for dataset access
   - Provide: Project name, organization, contract period
4. Download datasets (GB-scale files)
5. Extract and process locally
"""

# Example: Processing AI Hub data
import json
from typing import List

class AIHubDataProcessor:
    """Process downloaded AI Hub datasets"""

    def load_json_corpus(self, file_path: str) -> List[str]:
        """
        Load and extract texts from AI Hub JSON format

        Args:
            file_path: Path to downloaded JSON file

        Returns:
            List of Korean texts
        """
        texts = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

                # Structure varies by dataset
                # Common patterns:
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            # Extract Korean text field
                            text = (item.get('text') or
                                   item.get('korean') or
                                   item.get('sentence'))
                            if text:
                                texts.append(text)

        except Exception as e:
            print(f"Error loading AI Hub data: {e}")

        return texts

    def sample_for_daily_use(self, all_texts: List[str],
                           sample_size: int = 500) -> List[str]:
        """
        Sample texts for daily neologism extraction

        Args:
            all_texts: Full corpus
            sample_size: Number of texts to sample

        Returns:
            Sampled texts
        """
        import random
        return random.sample(all_texts, min(sample_size, len(all_texts)))


# Usage
processor = AIHubDataProcessor()

# Load once (large file)
all_texts = processor.load_json_corpus("/path/to/aihub_data.json")

# Daily sampling
daily_sample = processor.sample_for_daily_use(all_texts, sample_size=500)
```

#### Advantages
- FREE, government-sponsored
- MASSIVE datasets (millions of texts)
- High quality, professionally curated
- Multiple domains (news, social media, dialogue)

#### Limitations
- One-time download (not daily updates)
- Registration and approval process
- Large files (GB-scale)
- Not real-time/trending content

**Recommendation:** Use as supplementary data source, not primary daily collection

---

### 3.2 모두의 말뭉치 (Modu Corpus)

**URL:** https://corpus.korean.go.kr/
**Feasibility:** Medium
**Cost:** FREE (registration required)
**Data Volume:** Very Large
**Korean Suitability:** HIGHEST (National Institute of Korean Language)

#### Features
- 10,045 works (books, magazines, reports)
- 4.24GB of Korean text
- Morphological and syntactic analysis included
- Named entity annotations

#### Process
Same as AI Hub - register, apply, download, process locally.

---

## 4. Alternative Scraping Solutions

### 4.1 Playwright on AWS Lambda

**Feasibility:** Hard
**Cost:** ~$20-50/month (Lambda + ECR)
**Data Volume:** 300+ texts/day
**Korean Suitability:** HIGH (can scrape any Korean site)
**Legal/Ethical:** Gray area, respect robots.txt

#### Implementation Overview

```python
# Dockerfile for Lambda
"""
FROM public.ecr.aws/lambda/python:3.11

# Install Playwright and dependencies
RUN pip install playwright boto3
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy function code
COPY lambda_function.py ${LAMBDA_TASK_ROOT}

CMD [ "lambda_function.handler" ]
"""

# lambda_function.py
from playwright.sync_api import sync_playwright
import boto3
import json

def handler(event, context):
    """
    Lambda function to scrape Korean websites with Playwright
    """
    url = event.get('url')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)

        # Wait for JavaScript rendering
        page.wait_for_load_state('networkidle')

        # Extract content
        content = page.inner_text('body')

        browser.close()

    # Save to S3
    s3 = boto3.client('s3')
    s3.put_object(
        Bucket='your-bucket',
        Key=f'scraped/{context.request_id}.txt',
        Body=content
    )

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Success'})
    }
```

#### Deployment

```bash
# Build and push Docker image
docker build -t playwright-scraper .
docker tag playwright-scraper:latest 123456789.dkr.ecr.us-east-1.amazonaws.com/playwright-scraper:latest
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/playwright-scraper:latest

# Create Lambda function
aws lambda create-function \
  --function-name korean-scraper \
  --package-type Image \
  --code ImageUri=123456789.dkr.ecr.us-east-1.amazonaws.com/playwright-scraper:latest \
  --role arn:aws:iam::123456789:role/lambda-role \
  --timeout 60 \
  --memory-size 2048
```

#### Advantages
- Can scrape JavaScript-heavy sites
- Serverless (only pay for usage)
- Scalable

#### Limitations
- Complex setup (Docker, ECR, Lambda)
- Higher cost than API methods
- Legal gray area
- Maintenance overhead

**Recommendation:** Use only if APIs are insufficient

---

### 4.2 Apify Actors

**Feasibility:** Easy (if budget allows)
**Cost:** $49+/month
**Data Volume:** High
**Korean Suitability:** MEDIUM-HIGH
**Legal/Ethical:** Apify handles compliance

#### Usage

```python
from apify_client import ApifyClient

client = ApifyClient("YOUR_APIFY_TOKEN")

# Run Web Scraper actor
run = client.actor("apify/web-scraper").call(
    run_input={
        "startUrls": [{"url": "https://korean-site.com"}],
        "pageFunction": """
            async function pageFunction(context) {
                const $ = context.jQuery;
                return {
                    text: $('body').text()
                };
            }
        """
    }
)

# Get results
for item in client.dataset(run["defaultDatasetId"]).iterate_items():
    print(item['text'])
```

#### Advantages
- Pre-built scrapers for major sites
- Handles proxies, CAPTCHAs
- Easy to use
- Reliable infrastructure

#### Limitations
- Monthly subscription cost
- No free tier for production use

**Recommendation:** Consider if budget > $50/month

---

## 5. Hybrid Approach (RECOMMENDED)

### Optimal Daily Collection Strategy

```python
"""
Hybrid Data Collection Pipeline
Target: 300+ high-quality Korean texts daily
Cost: FREE
"""

from typing import List
import boto3
import json
from datetime import datetime

class HybridDataCollector:
    """
    Combines multiple FREE data sources for optimal coverage
    """

    def __init__(self,
                 naver_client_id: str,
                 naver_client_secret: str,
                 youtube_api_key: str = None,
                 reddit_client_id: str = None,
                 reddit_client_secret: str = None):

        # Initialize collectors
        self.naver = NaverSearchCollector(naver_client_id, naver_client_secret)
        self.rss = RSSFeedCollector()

        # Optional collectors
        self.youtube = YouTubeCommentsCollector(youtube_api_key) if youtube_api_key else None
        self.reddit = RedditKoreanCollector(
            reddit_client_id,
            reddit_client_secret,
            "KoreanNeologism/1.0"
        ) if reddit_client_id else None

    def collect_daily_batch(self) -> List[str]:
        """
        Collect from all sources

        Expected output: 500-800 texts
        Breakdown:
        - Naver API: 300-500 texts
        - RSS Feeds: 200-300 texts
        - YouTube (optional): 100-200 comments
        - Reddit (optional): 100-200 texts
        """
        all_texts = []

        # 1. Naver Search API (PRIMARY SOURCE)
        print("Collecting from Naver API...")
        naver_keywords = ["패션", "뷰티", "맛집"]
        naver_texts = self.naver.collect_daily_batch(naver_keywords)
        all_texts.extend(naver_texts)
        print(f"Naver: {len(naver_texts)} texts")

        # 2. RSS Feeds (SECONDARY SOURCE)
        print("Collecting from RSS feeds...")
        rss_texts = self.rss.collect_daily_batch()
        all_texts.extend(rss_texts)
        print(f"RSS: {len(rss_texts)} texts")

        # 3. YouTube (OPTIONAL)
        if self.youtube:
            print("Collecting from YouTube...")
            youtube_keywords = ["패션", "뷰티"]
            youtube_texts = self.youtube.collect_daily_batch(youtube_keywords)
            all_texts.extend(youtube_texts)
            print(f"YouTube: {len(youtube_texts)} comments")

        # 4. Reddit (OPTIONAL)
        if self.reddit:
            print("Collecting from Reddit...")
            reddit_texts = self.reddit.collect_daily_batch()
            all_texts.extend(reddit_texts)
            print(f"Reddit: {len(reddit_texts)} texts")

        print(f"\nTotal collected: {len(all_texts)} texts")
        return all_texts

    def save_to_s3(self, texts: List[str], bucket: str, prefix: str):
        """Save collected texts to S3"""
        s3 = boto3.client('s3')

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{prefix}/raw_texts_{timestamp}.json"

        data = {
            'timestamp': timestamp,
            'total_texts': len(texts),
            'texts': texts
        }

        s3.put_object(
            Bucket=bucket,
            Key=filename,
            Body=json.dumps(data, ensure_ascii=False, indent=2),
            ContentType='application/json'
        )

        print(f"Saved to s3://{bucket}/{filename}")


# Airflow DAG Integration
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from datetime import datetime, timedelta

def collect_data_task(**context):
    """Airflow task to collect data"""
    collector = HybridDataCollector(
        naver_client_id=Variable.get("naver_client_id"),
        naver_client_secret=Variable.get("naver_client_secret"),
        youtube_api_key=Variable.get("youtube_api_key", default_var=None),
        reddit_client_id=Variable.get("reddit_client_id", default_var=None),
        reddit_client_secret=Variable.get("reddit_client_secret", default_var=None)
    )

    texts = collector.collect_daily_batch()

    # Save to S3
    bucket = Variable.get("neologism_s3_bucket")
    prefix = Variable.get("neologism_input_prefix")
    collector.save_to_s3(texts, bucket, prefix)

    return len(texts)


default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 10, 1),
    'retries': 2,
    'retry_delay': timedelta(minutes=5)
}

dag = DAG(
    'hybrid_data_collection',
    default_args=default_args,
    description='Hybrid data collection from multiple sources',
    schedule_interval='0 2 * * *',  # Daily at 2 AM UTC (11 AM KST)
    catchup=False
)

collect_task = PythonOperator(
    task_id='collect_data',
    python_callable=collect_data_task,
    dag=dag
)
```

---

## Comparison Matrix

| Method | Feasibility | Cost | Volume/Day | Korean Quality | Setup Time | Maintenance |
|--------|------------|------|------------|----------------|------------|-------------|
| **Naver API** | ⭐⭐⭐ Easy | FREE | 300-1000 | ⭐⭐⭐ High | 30 min | Low |
| **RSS Feeds** | ⭐⭐⭐ Easy | FREE | 200-400 | ⭐⭐⭐ High | 15 min | Very Low |
| **YouTube API** | ⭐⭐ Medium | FREE | 100-300 | ⭐⭐⭐ High | 1 hour | Low |
| **Reddit API** | ⭐⭐⭐ Easy | FREE | 100-300 | ⭐⭐ Medium | 30 min | Low |
| **AI Hub** | ⭐⭐ Medium | FREE | Millions* | ⭐⭐⭐ High | 1 day+ | None |
| **Playwright/Lambda** | ⭐ Hard | $20-50/mo | 300+ | ⭐⭐⭐ High | 1-2 days | High |
| **Apify** | ⭐⭐⭐ Easy | $49+/mo | High | ⭐⭐ Medium | 1 hour | Low |

*One-time download, not daily collection

---

## Implementation Roadmap

### Phase 1: Quick Wins (Week 1)
1. **Implement Naver Search API** (Day 1-2)
   - Register for API credentials
   - Implement collector class
   - Test with 3-5 keywords
   - Expected: 300+ texts/day

2. **Add RSS Feeds** (Day 3)
   - Implement RSS collector
   - Add 5-7 major Korean news sources
   - Expected: +200 texts/day

3. **Integrate with Airflow** (Day 4-5)
   - Update existing DAG
   - Add Airflow Variables
   - Test end-to-end pipeline

### Phase 2: Enhancement (Week 2-3)
4. **Add YouTube API** (Optional)
   - Get API credentials
   - Implement comments collector
   - Quota management
   - Expected: +100-200 comments/day

5. **Add Reddit API** (Optional)
   - Register Reddit app
   - Implement collector
   - Expected: +100-200 texts/day

### Phase 3: Optimization (Month 2)
6. **Download AI Hub Datasets**
   - Register and apply for access
   - Download and process locally
   - Use for supplementary training data

7. **Monitor and Tune**
   - Analyze neologism extraction quality
   - Adjust keywords and sources
   - Optimize collection frequency

---

## Legal and Ethical Considerations

### ✅ Compliant Methods
- **Naver API:** Official API, TOS-compliant
- **YouTube API:** Official API, follows Google policies
- **Reddit API:** Official API, follows Reddit rules
- **RSS Feeds:** Public syndication, designed for consumption
- **AI Hub / Modu Corpus:** Government open data initiative

### ⚠️ Gray Area
- **Playwright/Selenium scraping:** Check website robots.txt and TOS
- **Apify:** Generally compliant, but check specific sites

### Best Practices
1. **Rate Limiting:** Respect API quotas and implement exponential backoff
2. **User-Agent:** Always identify your bot clearly
3. **robots.txt:** Honor robots.txt for web scraping
4. **Attribution:** Maintain source attribution in metadata
5. **Data Privacy:** Remove personal information from collected texts

---

## Cost Analysis

### Recommended FREE Setup
```
Naver API:           $0/month (25,000 requests/day)
RSS Feeds:           $0/month (unlimited)
YouTube API:         $0/month (10,000 quota/day)
Reddit API:          $0/month (60 req/min)
-------------------------------------------
Total Monthly Cost:  $0
Expected Daily Texts: 500-800+ texts
```

### Enhanced Setup (If needed)
```
Above +
Apify Subscription:  $49/month (5,000 actor runs)
AWS Lambda (Playwright): $20-30/month
-------------------------------------------
Total Monthly Cost:  $69-79/month
Expected Daily Texts: 1,000+ texts
```

---

## Monitoring and Success Metrics

### Key Metrics to Track
1. **Collection Volume**
   - Target: 300+ texts/day
   - Actual: Monitor daily

2. **Data Quality**
   - Korean text percentage: >95%
   - Neologism extraction rate: Track weekly

3. **API Health**
   - Error rates by source
   - Quota usage (YouTube, Naver)

4. **Cost**
   - Target: $0/month
   - Alert if exceeds $50/month

### CloudWatch Alarms
```python
# Set up CloudWatch alarms for monitoring
import boto3

cloudwatch = boto3.client('cloudwatch')

# Alarm: Daily collection falls below 300 texts
cloudwatch.put_metric_alarm(
    AlarmName='NeologismCollectionLow',
    MetricName='TextsCollected',
    Namespace='NeologismPipeline',
    Statistic='Sum',
    Period=86400,  # 1 day
    EvaluationPeriods=1,
    Threshold=300,
    ComparisonOperator='LessThanThreshold',
    AlarmActions=['arn:aws:sns:...']
)
```

---

## Conclusion

### Top 3 Recommendations

1. **Naver Search API (PRIMARY)**
   - Implement immediately
   - FREE, easy, high Korean quality
   - 300-1000 texts/day

2. **RSS Feeds (SECONDARY)**
   - Zero maintenance
   - FREE, reliable
   - 200-400 texts/day

3. **YouTube Data API (TERTIARY)**
   - Rich conversational Korean
   - FREE tier sufficient
   - 100-300 comments/day

### Implementation Priority
```
Week 1: Naver API + RSS Feeds (500+ texts/day)
Week 2: YouTube API (optional, +200 texts/day)
Week 3: Reddit API (optional, +100 texts/day)
Month 2: AI Hub datasets (supplementary)
```

### Expected Results
- **Daily Volume:** 500-800+ high-quality Korean texts
- **Cost:** $0/month
- **Maintenance:** Low (mostly API-based)
- **Reliability:** High (official APIs)
- **Korean Quality:** High (native platforms)

This approach **completely eliminates web scraping** while providing **more reliable, sustainable, and legal** data collection at **zero cost**.

---

## Next Steps

1. Create Naver Developer account: https://developers.naver.com/
2. Create Google Cloud project for YouTube API: https://console.cloud.google.com/
3. Update `/home/ec2-user/workspace/claude-ner-engineering/src/neologism_extractor/data_collector.py` with new collectors
4. Update Airflow DAG to use hybrid approach
5. Set Airflow Variables for API credentials
6. Test end-to-end pipeline
7. Monitor for 1 week and optimize

---

**Document Version:** 1.0
**Last Updated:** October 28, 2025
**Contact:** data-team@example.com
