"""
API-based Data Collectors for Korean Neologism Extraction
Replaces web scraping with official APIs and RSS feeds
"""

import os
import re
import time
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from abc import ABC, abstractmethod


class BaseAPICollector(ABC):
    """Base class for API-based collectors"""

    @abstractmethod
    def collect(self, **kwargs) -> List[str]:
        """Collect data from API"""
        pass


class NaverSearchCollector(BaseAPICollector):
    """
    Naver Search API Collector
    FREE: 25,000 requests/day
    Docs: https://developers.naver.com/docs/serviceapi/search/
    """

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        """
        Args:
            client_id: Naver API Client ID (or set NAVER_CLIENT_ID env var)
            client_secret: Naver API Client Secret (or set NAVER_CLIENT_SECRET env var)
        """
        self.client_id = client_id or os.getenv('NAVER_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('NAVER_CLIENT_SECRET')

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "Naver API credentials required. "
                "Set NAVER_CLIENT_ID and NAVER_CLIENT_SECRET environment variables."
            )

        self.base_url = "https://openapi.naver.com/v1/search"

    def search_blog(self, query: str, display: int = 100, start: int = 1) -> List[str]:
        """
        Search Naver blogs

        Args:
            query: Search keyword (e.g., "패션 트렌드", "뷰티 추천")
            display: Results per page (max 100)
            start: Start position (1-1000)

        Returns:
            List of blog post texts
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
            "sort": "date"  # Latest posts
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            texts = []
            for item in data.get('items', []):
                title = self._clean_html(item.get('title', ''))
                description = self._clean_html(item.get('description', ''))
                text = f"{title} {description}".strip()
                if text:
                    texts.append(text)

            return texts

        except requests.exceptions.RequestException as e:
            print(f"Naver Blog API Error: {e}")
            return []

    def search_news(self, query: str, display: int = 100, start: int = 1) -> List[str]:
        """Search Naver news articles"""
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
                text = f"{title} {description}".strip()
                if text:
                    texts.append(text)

            return texts

        except requests.exceptions.RequestException as e:
            print(f"Naver News API Error: {e}")
            return []

    def search_shopping(self, query: str, display: int = 100, start: int = 1) -> List[str]:
        """Search Naver shopping products"""
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
                if title:
                    texts.append(title)

            return texts

        except requests.exceptions.RequestException as e:
            print(f"Naver Shopping API Error: {e}")
            return []

    def collect(self, keywords: List[str] = None, **kwargs) -> List[str]:
        """
        Collect data from Naver API (implements BaseAPICollector interface)

        Args:
            keywords: List of search keywords

        Returns:
            Combined list of texts
        """
        if keywords is None:
            keywords = ["패션", "뷰티", "맛집"]

        all_texts = []

        for keyword in keywords:
            print(f"Searching Naver for: {keyword}")

            # Blog search (100 results)
            blogs = self.search_blog(keyword, display=100)
            all_texts.extend(blogs)

            # News search (50 results)
            news = self.search_news(keyword, display=50)
            all_texts.extend(news)

            # Shopping search (50 results)
            shopping = self.search_shopping(keyword, display=50)
            all_texts.extend(shopping)

            # Be polite to API
            time.sleep(0.5)

        return all_texts

    @staticmethod
    def _clean_html(text: str) -> str:
        """Remove HTML tags and entities"""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Decode common HTML entities
        text = text.replace('&quot;', '"').replace('&amp;', '&')
        text = text.replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&nbsp;', ' ').replace('&#39;', "'")
        return text.strip()


class RSSFeedCollector(BaseAPICollector):
    """
    RSS Feed Collector for Korean news and blogs
    FREE, no authentication required
    """

    # Major Korean news RSS feeds
    DEFAULT_FEEDS = {
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

    def __init__(self, custom_feeds: Dict[str, str] = None):
        """
        Args:
            custom_feeds: Additional custom RSS feeds {name: url}
        """
        self.feeds = self.DEFAULT_FEEDS.copy()
        if custom_feeds:
            self.feeds.update(custom_feeds)

    def fetch_feed(self, feed_url: str, max_items: int = 50) -> List[str]:
        """
        Fetch and parse RSS feed

        Args:
            feed_url: RSS feed URL
            max_items: Maximum items to fetch

        Returns:
            List of article texts
        """
        import feedparser  # Lazy import to avoid dependency issues

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

    def collect(self, feeds_to_use: List[str] = None, max_items_per_feed: int = 50, **kwargs) -> List[str]:
        """
        Collect from RSS feeds (implements BaseAPICollector interface)

        Args:
            feeds_to_use: List of feed keys to use (default: all feeds)
            max_items_per_feed: Maximum items per feed

        Returns:
            Combined list of texts
        """
        if feeds_to_use is None:
            feeds_to_use = list(self.feeds.keys())

        all_texts = []

        for feed_key in feeds_to_use:
            if feed_key in self.feeds:
                feed_url = self.feeds[feed_key]
                print(f"Fetching RSS feed: {feed_key}")

                texts = self.fetch_feed(feed_url, max_items=max_items_per_feed)
                all_texts.extend(texts)

                # Be polite to servers
                time.sleep(1)

        return all_texts

    def add_feed(self, name: str, url: str):
        """Add a custom RSS feed"""
        self.feeds[name] = url


class YouTubeCommentsCollector(BaseAPICollector):
    """
    YouTube Data API v3 Comments Collector
    FREE: 10,000 quota units/day
    Docs: https://developers.google.com/youtube/v3
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: YouTube Data API key (or set YOUTUBE_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('YOUTUBE_API_KEY')

        if not self.api_key:
            raise ValueError(
                "YouTube API key required. "
                "Set YOUTUBE_API_KEY environment variable."
            )

        self.base_url = "https://www.googleapis.com/youtube/v3"

    def search_videos(self, query: str, max_results: int = 10) -> List[str]:
        """
        Search for Korean videos

        Args:
            query: Search term (e.g., "패션", "뷰티")
            max_results: Number of videos

        Returns:
            List of video IDs
        """
        url = f"{self.base_url}/search"
        params = {
            'key': self.api_key,
            'q': query,
            'part': 'id',
            'type': 'video',
            'relevanceLanguage': 'ko',
            'maxResults': max_results,
            'order': 'date'
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            video_ids = []
            for item in data.get('items', []):
                if item.get('id', {}).get('kind') == 'youtube#video':
                    video_ids.append(item['id']['videoId'])

            return video_ids

        except requests.exceptions.RequestException as e:
            print(f"YouTube Search Error: {e}")
            return []

    def get_comments(self, video_id: str, max_comments: int = 100) -> List[str]:
        """
        Get comments from a video

        Args:
            video_id: YouTube video ID
            max_comments: Maximum comments to retrieve

        Returns:
            List of comment texts
        """
        url = f"{self.base_url}/commentThreads"
        params = {
            'key': self.api_key,
            'part': 'snippet',
            'videoId': video_id,
            'maxResults': min(100, max_comments),
            'textFormat': 'plainText',
            'order': 'relevance'
        }

        comments = []

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            for item in data.get('items', []):
                comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
                comments.append(comment)

        except requests.exceptions.RequestException as e:
            print(f"YouTube Comments Error (video {video_id}): {e}")

        return comments

    def collect(self, keywords: List[str] = None,
                videos_per_keyword: int = 3,
                comments_per_video: int = 30,
                **kwargs) -> List[str]:
        """
        Collect comments from YouTube (implements BaseAPICollector interface)

        Args:
            keywords: Search keywords
            videos_per_keyword: Videos to fetch per keyword
            comments_per_video: Comments per video

        Returns:
            Combined list of comments
        """
        if keywords is None:
            keywords = ["패션", "뷰티"]

        all_comments = []

        for keyword in keywords:
            print(f"Searching YouTube for: {keyword}")

            # Search videos
            video_ids = self.search_videos(keyword, max_results=videos_per_keyword)

            # Get comments from each video
            for video_id in video_ids:
                comments = self.get_comments(video_id, max_comments=comments_per_video)
                all_comments.extend(comments)

                # Be polite to API
                time.sleep(0.5)

        return all_comments


class HybridDataCollector:
    """
    Hybrid collector combining multiple API sources
    Replaces web scraping with official APIs
    """

    def __init__(self,
                 naver_client_id: Optional[str] = None,
                 naver_client_secret: Optional[str] = None,
                 youtube_api_key: Optional[str] = None,
                 use_rss: bool = True):
        """
        Initialize hybrid collector with available API credentials

        Args:
            naver_client_id: Naver API client ID
            naver_client_secret: Naver API client secret
            youtube_api_key: YouTube API key (optional)
            use_rss: Whether to include RSS feeds (default: True)
        """
        self.collectors = {}

        # Naver API (PRIMARY - required)
        try:
            self.collectors['naver'] = NaverSearchCollector(
                client_id=naver_client_id,
                client_secret=naver_client_secret
            )
            print("Naver API collector initialized")
        except ValueError as e:
            print(f"Warning: Naver API not available - {e}")

        # RSS Feeds (SECONDARY - always available)
        if use_rss:
            self.collectors['rss'] = RSSFeedCollector()
            print("RSS feed collector initialized")

        # YouTube API (OPTIONAL)
        if youtube_api_key:
            try:
                self.collectors['youtube'] = YouTubeCommentsCollector(api_key=youtube_api_key)
                print("YouTube API collector initialized")
            except ValueError as e:
                print(f"Warning: YouTube API not available - {e}")

        if not self.collectors:
            raise ValueError("No data collectors available. Please provide API credentials.")

    def collect(self, **kwargs) -> List[str]:
        """
        Collect from all available sources

        Returns:
            Combined list of texts (300-800+ texts expected)
        """
        all_texts = []
        stats = {}

        # Naver API
        if 'naver' in self.collectors:
            print("\n=== Collecting from Naver API ===")
            naver_keywords = kwargs.get('naver_keywords', ["패션", "뷰티", "맛집"])
            naver_texts = self.collectors['naver'].collect(keywords=naver_keywords)
            all_texts.extend(naver_texts)
            stats['naver'] = len(naver_texts)
            print(f"Naver: {len(naver_texts)} texts")

        # RSS Feeds
        if 'rss' in self.collectors:
            print("\n=== Collecting from RSS Feeds ===")
            rss_texts = self.collectors['rss'].collect()
            all_texts.extend(rss_texts)
            stats['rss'] = len(rss_texts)
            print(f"RSS: {len(rss_texts)} texts")

        # YouTube
        if 'youtube' in self.collectors:
            print("\n=== Collecting from YouTube ===")
            youtube_keywords = kwargs.get('youtube_keywords', ["패션", "뷰티"])
            youtube_texts = self.collectors['youtube'].collect(keywords=youtube_keywords)
            all_texts.extend(youtube_texts)
            stats['youtube'] = len(youtube_texts)
            print(f"YouTube: {len(youtube_texts)} comments")

        print(f"\n=== Total collected: {len(all_texts)} texts ===")
        print(f"Breakdown: {stats}")

        return all_texts


# Convenience function for backward compatibility
def create_default_collector() -> HybridDataCollector:
    """
    Create a hybrid collector with environment variables

    Required environment variables:
    - NAVER_CLIENT_ID
    - NAVER_CLIENT_SECRET

    Optional environment variables:
    - YOUTUBE_API_KEY

    Returns:
        Configured HybridDataCollector
    """
    return HybridDataCollector(
        naver_client_id=os.getenv('NAVER_CLIENT_ID'),
        naver_client_secret=os.getenv('NAVER_CLIENT_SECRET'),
        youtube_api_key=os.getenv('YOUTUBE_API_KEY'),
        use_rss=True
    )


if __name__ == "__main__":
    # Example usage
    print("API-based Data Collection Example")
    print("=" * 50)

    # Option 1: Use environment variables
    collector = create_default_collector()

    # Option 2: Provide credentials explicitly
    # collector = HybridDataCollector(
    #     naver_client_id="YOUR_NAVER_CLIENT_ID",
    #     naver_client_secret="YOUR_NAVER_CLIENT_SECRET",
    #     youtube_api_key="YOUR_YOUTUBE_API_KEY",  # Optional
    #     use_rss=True
    # )

    # Collect data
    texts = collector.collect(
        naver_keywords=["패션", "뷰티", "맛집"],
        youtube_keywords=["패션", "뷰티"]
    )

    print(f"\nCollected {len(texts)} texts total")

    # Sample output
    if texts:
        print("\nSample texts:")
        for i, text in enumerate(texts[:5], 1):
            print(f"{i}. {text[:100]}...")
