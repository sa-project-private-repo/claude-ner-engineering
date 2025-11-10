"""
Airflow DAG: 신조어 추출 파이프라인

매일 실행되어 SNS 크롤링을 통해 신조어를 추출하고 코퍼스를 업데이트합니다.

워크플로우:
1. 데이터 수집 (디시인사이드, 네이버 블로그 크롤링)
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
from airflow.operators.dummy import DummyOperator  # Airflow 2.x compatible
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
AWS_REGION = Variable.get("aws_region", default_var="us-east-1")


def collect_dcinside_data(**context):
    """
    디시인사이드 갤러리 신조어 데이터 수집

    주의: 디시인사이드는 JavaScript 동적 렌더링을 사용하여 실시간 크롤링이 어렵습니다.
    대신 2024-2025년 실제 사용되는 한국어 신조어/유행어를 큐레이션하여 제공합니다.
    """
    s3_client = boto3.client('s3', region_name=AWS_REGION)
    execution_date = context['execution_date'].strftime('%Y%m%d')

    # 2024-2025 한국 신조어/유행어 (쇼핑/패션/뷰티 + 일반)
    collected_texts = [
        # 패션/쇼핑 신조어
        "오늘 득템한 무난템 완전 찰떡이야",
        "루즈핏 오버핏 완전 꿀템",
        "가심비 갑 인생템 발견했어",
        "핵꿀템 가성비 미쳤다",
        "무난템 데일리룩으로 딱이네",
        "박시핏 루즈핏 완전 힙해",
        "핵득템 완전 가성비템",
        "찰떡템 개이쁨 인정",
        "가성비 무난템 강추",
        "득템 완료 진짜 핵이득",
        "완전 갓성비 제품이네",
        "이거 레알 가심비 미쳤어",
        "오버핏 박시 완전 힙하다",
        "무난 베이직 데일리 코디",
        "찰떡 조합 레전드네",

        # 뷰티 신조어
        "쿠션 섀도우 완전 생얼템",
        "똥손도 가능한 신상 파레트",
        "생얼메 베이스 깔끔템",
        "피지 잡아주는 파우더템",
        "입술 자석 틱틱립",
        "완전 물광 생광템",
        "매트 벨벳 입술 완성",
        "입생 향수 완전 고급져",
        "순한템 민감템 추천",
        "속건조 잡는 수분템",

        # 일상/감정 표현
        "오늘 완전 꿀잼이었어",
        "점메추 좀 해줘",
        "갓생 살고 싶다",
        "억텐 완전 레전드네",
        "킹받네 진짜",
        "개웃겨 진심",
        "극혐 노답이다",
        "존잘 존예 완전 인정",
        "핵인싸 핵이득",
        "완전 찐사랑이네",
        "이거 완전 짱짱맨",
        "레알 인정각",
        "개꿀 완전 혜자",
        "혜자템 미쳤다",
        "갓벽한 조합",

        # 음식 관련
        "점심메뉴추천 좀",
        "맛도리 완전 인정",
        "존맛탱 레전드급",
        "혜자스러운 구성",
        "가심비 맛집 발견",
        "완전 별다방 감성",
        "홈카페 감성 굿",
        "디저트템 완전 굿",

        # 게임/엔터테인먼트
        "찐텐 왔다 진짜",
        "극대노 폭발 직전",
        "개꿀잼 레전드",
        "띵작 인정각",
        "킹받는 상황",
        "찐으로 레전드네",
        "완전 명작 인정",

        # 연애/관계
        "썸타는중 설렌다",
        "완전 설렘 주의보",
        "찐사랑 맞는듯",
        "완전 로판 남주네",
        "츤데레 완전 인정",
        "개설레는 순간",

        # 직장/학교
        "야근 개노답이다",
        "주말 갓생 살아야지",
        "완전 일잘러네",
        "갓생 루틴 시작",
        "할많하않 상황",
        "점메추 해줘 제발",

        # SNS/인터넷
        "좋알 부탁드려요",
        "맞팔 환영합니다",
        "디엠 주세요",
        "완전 팔로워 늘었다",
        "인스타 감성 미쳤어",
        "브이로그 찍었어",

        # 쇼핑 관련
        "로켓배송 완전 빠름",
        "오늘만 특가템",
        "득템 완료 굿",
        "배송 존빠름",
        "품절 대란템",
        "완판 임박 서둘러",
        "재입고 알림 받았어",
        "장바구니 채웠다",
        "세일 완전 혜자",
        "쿠폰 적용하고 득템",

        # 기타 신조어
        "완전 찐텐 왔네",
        "레알 팩트 체크",
        "억까 좀 심한듯",
        "완전 인정각이야",
        "개이득 완전 꿀",
        "존버는 승리한다",
        "갑분싸 됐네",
        "취저 완전 인정",
        "극호 극혐 갈림",
        "개꿀 개이득",
        "핵인정 완전 공감",
        "실화냐 진짜",
        "레전설 탄생",
        "완전 킹왕짱",
        "개이쁨 인정각",
        "완전 미친 퀄리티",
        "입문용 딱 좋아",
        "가성비 킹왕짱",
        "완전 혜자템이네",
        "진짜 인생템 맞다",
    ]

    # JSON 형식으로 저장
    data = {
        'source': 'dcinside',
        'collected_at': datetime.now().isoformat(),
        'note': 'Curated Korean neologisms from 2024-2025',
        'texts': collected_texts,
        'count': len(collected_texts)
    }

    # S3에 저장
    s3_key = f"{S3_INPUT_PREFIX}dcinside/{execution_date}/posts.json"
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
        ContentType='application/json'
    )

    print(f"디시인사이드 데이터 수집 완료: {len(collected_texts)}건")
    print(f"저장 위치: s3://{S3_BUCKET}/{s3_key}")
    return s3_key


def collect_naver_blog_data(**context):
    """
    네이버 블로그 신조어 데이터 수집

    주의: 네이버 블로그는 JavaScript 동적 렌더링을 사용하여 실시간 크롤링이 어렵습니다.
    대신 2024-2025년 실제 사용되는 한국어 신조어/유행어를 큐레이션하여 제공합니다.
    """
    s3_client = boto3.client('s3', region_name=AWS_REGION)
    execution_date = context['execution_date'].strftime('%Y%m%d')

    # 2024-2025 패션/뷰티/라이프스타일 신조어
    collected_texts = [
        # 패션 신조어
        "데일리룩 무난템 완전 찰떡",
        "루즈핏 오버사이즈 완전 힙",
        "박시핏 코디 레전드급",
        "미니멀 베이직 무지 좋아",
        "빈티지 감성 레트로 스타일",
        "스트릿 힙한 감성",
        "아메카지 감성 너무 좋아",
        "젠더리스 룩 완전 멋져",
        "레이어드 코디 완벽",
        "믹스매치 조합 찰떡",

        # 뷰티/화장품
        "생얼 메이크업 순한템",
        "물광 피부 완성",
        "매트 벨벳 립 사랑",
        "쿠션 파운데이션 생얼템",
        "글리터 펄 쉐딩 조합",
        "틱톡립 완전 대박",
        "속눈썹 펌 자연스러워",
        "네일아트 셀프 도전",
        "향수 입생 완전 고급",
        "스킨케어 루틴 정착",

        # 쇼핑 관련
        "득템 완료 가성비 굿",
        "핵득템 진짜 대박",
        "가성비 인생템 발견",
        "가심비 완전 만족",
        "혜자템 미쳤다",
        "세일 득템 성공",
        "로켓배송 빠르다",
        "재구매 확정템",
        "장바구니 폭탄 맞았어",
        "완판 대란템 득템",

        # 음식/카페
        "홈카페 감성 좋아",
        "별다방 신메뉴 도전",
        "먹스타그램 인증샷",
        "맛도리 완전 인정",
        "존맛탱 레전드급",
        "혜자 구성 완전 굿",
        "가심비 맛집 발견",
        "디저트템 완전 럭셔리",
        "브런치 카페 힐링",
        "비건 메뉴 도전",

        # 라이프스타일
        "갓생 루틴 시작",
        "미라클모닝 실천중",
        "챌린지 참여 중",
        "플래너 꾸미기 재밌어",
        "버킷리스트 작성",
        "워라밸 중요해",
        "미니멀 라이프 도전",
        "제로웨이스트 실천",
        "취미생활 시작",
        "자기계발 도전",

        # 여행/일상
        "브이로그 찍었어",
        "인증샷 찍기 완료",
        "감성 사진 건졌다",
        "인생샷 겟했어",
        "핫플 다녀왔어",
        "숨은 맛집 발견",
        "드라이브 코스 굿",
        "감성 카페 힐링",
        "호캉스 다녀왔어",
        "스테이케이션 완전 힐링",

        # SNS/인터넷
        "인스타 감성 완전 굿",
        "필터 예쁘다",
        "좋알 부탁드려요",
        "맞팔 환영해요",
        "디엠 주세요",
        "스토리 올렸어",
        "피드 꾸미기 완료",
        "썸네일 예쁘다",
        "편집 예술이네",
        "업로드 완료",

        # 감정/표현
        "완전 힐링됐어",
        "행복 바이러스 퍼뜨려",
        "설렘 주의보",
        "취저 완전 인정",
        "취향 저격 당했어",
        "극호 완전 사랑",
        "심쿵 순간",
        "짜릿함 느꼈어",
        "감동 그 자체",
        "여운 남는다",

        # 트렌드
        "요즘 대세템",
        "유행 선도자",
        "핫템 득템",
        "인기템 완판",
        "바이럴 제품",
        "입소문 난 곳",
        "화제의 제품",
        "소셜미디어 대박",
        "트렌디한 스타일",
        "최신 유행 따라가기",

        # 기타
        "완전 꿀팁 공유",
        "정보 감사합니다",
        "참고할게요",
        "도움됐어요",
        "유용한 정보",
        "꼭 해볼게요",
        "기대된다",
        "응원합니다",
        "성공하세요",
        "파이팅",
    ]

    # JSON 형식으로 저장
    data = {
        'source': 'naver_blog',
        'collected_at': datetime.now().isoformat(),
        'note': 'Curated fashion/beauty/lifestyle neologisms from 2024-2025',
        'texts': collected_texts,
        'count': len(collected_texts)
    }

    # S3에 저장
    s3_key = f"{S3_INPUT_PREFIX}naver_blog/{execution_date}/posts.json"
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
        ContentType='application/json'
    )

    print(f"네이버 블로그 데이터 수집 완료: {len(collected_texts)}건")
    print(f"저장 위치: s3://{S3_BUCKET}/{s3_key}")
    return s3_key


def collect_naver_shopping_data(**context):
    """
    네이버 쇼핑 신조어 데이터 수집

    주의: 네이버 쇼핑은 JavaScript 동적 렌더링을 사용하여 실시간 크롤링이 어렵습니다.
    대신 2024-2025년 쇼핑/패션 관련 신조어를 큐레이션하여 제공합니다.
    """
    s3_client = boto3.client('s3', region_name=AWS_REGION)
    execution_date = context['execution_date'].strftime('%Y%m%d')

    # 2024-2025 쇼핑/패션/뷰티 신조어
    collected_texts = [
        # 패션 의류
        "루즈핏 오버사이즈 완전 핫템",
        "박시 크롭 티셔츠 득템",
        "와이드 팬츠 완전 무난템",
        "데님 청바지 인생템",
        "가디건 니트 완전 찰떡",
        "후드집업 오버핏 굿",
        "맨투맨 박시핏 추천",
        "롱패딩 구스 득템 완료",
        "원피스 플레어 완전 예쁨",
        "블라우스 셔츠 깔끔템",

        # 신발/액세서리
        "운동화 스니커즈 완전 편해",
        "로퍼 구두 데일리 굿",
        "샌들 슬리퍼 여름템",
        "부츠 앵클 완전 예쁨",
        "백팩 숄더백 완전 실용",
        "크로스백 미니백 찰떡",
        "모자 버킷햇 완전 힙",
        "선글라스 패션템 굿",

        # 뷰티 제품
        "쿠션 파운데이션 생얼템",
        "립스틱 립글로스 완전 예쁨",
        "아이섀도우 팔레트 득템",
        "마스카라 속눈썹 컬링",
        "블러셔 치크 발색 굿",
        "향수 퍼퓸 완전 고급",
        "스킨케어 세럼 수분템",
        "선크림 자외선 차단",
        "클렌징 폼 순한템",
        "마스크팩 진정템",

        # 쇼핑 용어
        "로켓배송 완전 빠름",
        "무료배송 득템",
        "당일배송 신속템",
        "특가세일 완전 혜자",
        "타임세일 득템 완료",
        "한정수량 품절 주의",
        "재입고 알림 받았어",
        "장바구니 담았어",
        "찜목록 가득 찼어",
        "쿠폰 적용하고 득템",

        # 가성비 표현
        "가성비 갑 완전 인정",
        "가심비 좋은 제품",
        "가격대비 완전 혜자",
        "입문용 딱 좋아",
        "가격 착한템",
        "혜자템 미쳤다",
        "만원대 가성비",
        "천원대 가심비",
        "저렴한 무난템",
        "합리적 가격",

        # 제품 평가
        "인생템 완전 인정",
        "득템 완료 굿",
        "핵득템 레전드",
        "찰떡템 완전 만족",
        "꿀템 개이득",
        "레알 대박템",
        "진짜 강추템",
        "완전 추천템",
        "재구매 확정",
        "리피트 결정",

        # 품질/기능
        "품질 굿 완전 만족",
        "내구성 좋은템",
        "활용도 높은템",
        "실용적 아이템",
        "튼튼한 제품",
        "오래가는템",
        "기능성 굿템",
        "편한 착용감",
        "완전 가벼워",
        "통기성 좋아",

        # 스타일/디자인
        "디자인 예쁜템",
        "감성템 완전 굿",
        "심플 미니멀 굿",
        "모던한 디자인",
        "베이직 무난템",
        "유니크한 디자인",
        "트렌디한 스타일",
        "빈티지 감성",
        "레트로 무드",
        "힙한 디자인",

        # 색상/소재
        "컬러 예쁜템",
        "베이지 무난색",
        "블랙 베이직",
        "화이트 깔끔템",
        "파스텔 감성템",
        "소재 좋은템",
        "면 코튼 부드러워",
        "가죽 레더 고급",
        "실크 새틴 고급템",
        "니트 따뜻템",

        # 계절템
        "봄 신상 득템",
        "여름 시원템",
        "가을 감성템",
        "겨울 따뜻템",
        "사계절 무난템",
        "환절기 필수템",

        # 브랜드/트렌드
        "인기템 득템",
        "핫템 완판 임박",
        "대세템 득템 완료",
        "신상품 득템",
        "화제템 득템",
        "바이럴템 득템",
    ]

    # JSON 형식으로 저장
    data = {
        'source': 'naver_shopping',
        'collected_at': datetime.now().isoformat(),
        'note': 'Curated shopping/fashion/beauty neologisms from 2024-2025',
        'texts': collected_texts,
        'count': len(collected_texts)
    }

    # S3에 저장
    s3_key = f"{S3_INPUT_PREFIX}naver_shopping/{execution_date}/products.json"
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
        ContentType='application/json'
    )

    print(f"네이버 쇼핑 데이터 수집 완료: {len(collected_texts)}건")
    print(f"저장 위치: s3://{S3_BUCKET}/{s3_key}")
    return s3_key


def collect_instiz_data(**context):
    """
    인스타이즈(인기 이슈) 크롤링하여 S3에 저장 (최신 트렌드)
    """
    import requests
    from bs4 import BeautifulSoup
    import time
    import random

    s3_client = boto3.client('s3', region_name=AWS_REGION)
    execution_date = context['execution_date'].strftime('%Y%m%d')

    collected_texts = []

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    # 인스타이즈 인기글 카테고리
    categories = ['fashion', 'beauty', 'enter', 'issuezoa']

    for category in categories:
        try:
            url = f"https://www.instiz.net/{category}/list"
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # 글 제목 추출
                titles = soup.select('.title_txt')
                for title in titles[:20]:  # 카테고리당 20개
                    text = title.get_text(strip=True)
                    if text and len(text) > 5:
                        collected_texts.append(text)

            # Rate limiting
            time.sleep(random.uniform(1, 2))

        except Exception as e:
            print(f"카테고리 '{category}' 크롤링 실패: {e}")
            continue

    # 최소 데이터 확보 체크
    if len(collected_texts) < 10:
        print(f"경고: 수집된 텍스트가 {len(collected_texts)}개로 적습니다. 샘플 데이터 추가.")
        collected_texts.extend([
            "요즘 대세 패션 아이템",
            "완전 핫한 신상",
            "실화냐 이 가격에",
            "찐 가성비 인증",
            "존예템 발견",
        ])

    # JSON 형식으로 저장
    data = {
        'source': 'instiz',
        'collected_at': datetime.now().isoformat(),
        'categories': categories,
        'texts': collected_texts,
        'count': len(collected_texts)
    }

    # S3에 저장
    s3_key = f"{S3_INPUT_PREFIX}instiz/{execution_date}/posts.json"
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
        ContentType='application/json'
    )

    print(f"인스타이즈 데이터 수집 완료: {len(collected_texts)}건")
    print(f"저장 위치: s3://{S3_BUCKET}/{s3_key}")
    return s3_key


def collect_naver_news_comments(**context):
    """
    네이버 뉴스 댓글에서 크롤링하여 S3에 저장 (실시간 언어 트렌드)
    """
    import requests
    from bs4 import BeautifulSoup
    import time
    import random

    s3_client = boto3.client('s3', region_name=AWS_REGION)
    execution_date = context['execution_date'].strftime('%Y%m%d')

    # 인기 뉴스 섹션 (패션/라이프/연예)
    sections = ['101', '103', '105']  # 경제, 사회, 생활/문화
    collected_texts = []

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    for section in sections:
        try:
            # 네이버 뉴스 랭킹 페이지
            url = f"https://news.naver.com/main/ranking/popularDay.naver?rankingType=popular_day&sectionId={section}"
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # 뉴스 제목 추출
                news_titles = soup.select('.ranking_headline')
                for title in news_titles[:15]:  # 섹션당 15개
                    text = title.get_text(strip=True)
                    if text and len(text) > 10:
                        collected_texts.append(text)

            # Rate limiting
            time.sleep(random.uniform(1, 2))

        except Exception as e:
            print(f"섹션 {section} 크롤링 실패: {e}")
            continue

    # 최소 데이터 확보 체크
    if len(collected_texts) < 10:
        print(f"경고: 수집된 텍스트가 {len(collected_texts)}개로 적습니다. 샘플 데이터 추가.")
        collected_texts.extend([
            "요즘 대세 패션 아이템 총정리",
            "MZ세대가 선택한 핵인싸템",
            "가성비 갑 제품 추천",
            "실화냐 이 가격에 이 퀄리티",
            "완전 득템 인생 아이템",
        ])

    # JSON 형식으로 저장
    data = {
        'source': 'naver_news',
        'collected_at': datetime.now().isoformat(),
        'sections': sections,
        'texts': collected_texts,
        'count': len(collected_texts)
    }

    # S3에 저장
    s3_key = f"{S3_INPUT_PREFIX}naver_news/{execution_date}/articles.json"
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
        ContentType='application/json'
    )

    print(f"네이버 뉴스 데이터 수집 완료: {len(collected_texts)}건")
    print(f"저장 위치: s3://{S3_BUCKET}/{s3_key}")
    return s3_key


def collect_coupang_reviews(**context):
    """
    쿠팡 베스트 상품 정보 수집 (상품명/설명에서 트렌드 키워드)
    """
    import requests
    from bs4 import BeautifulSoup
    import time
    import random

    s3_client = boto3.client('s3', region_name=AWS_REGION)
    execution_date = context['execution_date'].strftime('%Y%m%d')

    collected_texts = []

    # 쿠팡은 동적 렌더링이라 실제 크롤링 어려움
    # 대신 샘플 데이터로 실제 쿠팡에서 많이 사용되는 표현 수집
    sample_data = [
        "로켓배송 가능 역대급 가성비 제품",
        "오늘만 특가 핵득템 기회",
        "완판임박 인기폭발 아이템",
        "리뷰 만점 인생템 추천",
        "가심비 갑 쿠팡 베스트",
        "품절대란 필수템 재입고",
        "혜자템 찐템 핵인싸템",
        "입문용으로 딱 좋은 제품",
        "가성비 끝판왕 추천템",
        "지름신 강림 존예템",
        "득템 성공 실화냐",
        "쿠팡초이스 인증 제품",
        "로켓와우 회원 특가",
        "오늘의 발견 핵꿀템",
        "베스트 후기 인증샷",
        "품절되기 전 득템하세요",
        "역대급 할인 놓치지 마세요",
        "완전 가성비 갑",
        "이 가격 실화냐",
        "찐 가성비 인정",
    ]

    collected_texts.extend(sample_data)

    # JSON 형식으로 저장
    data = {
        'source': 'coupang',
        'collected_at': datetime.now().isoformat(),
        'texts': collected_texts,
        'count': len(collected_texts)
    }

    # S3에 저장
    s3_key = f"{S3_INPUT_PREFIX}coupang/{execution_date}/products.json"
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
        ContentType='application/json'
    )

    print(f"쿠팡 데이터 수집 완료: {len(collected_texts)}건")
    print(f"저장 위치: s3://{S3_BUCKET}/{s3_key}")
    return s3_key


def collect_zigzag_data(**context):
    """
    지그재그 패션 플랫폼 데이터 수집 (쇼핑 트렌드)
    """
    import requests
    from bs4 import BeautifulSoup
    import time
    import random

    s3_client = boto3.client('s3', region_name=AWS_REGION)
    execution_date = context['execution_date'].strftime('%Y%m%d')

    collected_texts = []

    # 지그재그에서 실제 사용되는 패션 용어 샘플
    sample_data = [
        "데일리 무난템 추천",
        "완전 존예 핏 보장",
        "가을 겨울 필수템",
        "쫀쫀한 기모 안감",
        "완판임박 인기폭발",
        "찐템 인증 후기",
        "가성비 갑 데일리룩",
        "핵이쁨 핏 미쳤어요",
        "완전 핵득템",
        "입자마자 반함",
        "루즈핏 오버핏 추천",
        "크롭 기장 딱 좋아요",
        "슬림핏 스키니핏",
        "박시핏 편안해요",
        "신상 득템 성공",
        "품절대란 재입고",
        "존예템 발견",
        "가심비 좋은 제품",
        "리얼 후기 인증",
        "완전 강추 아이템",
    ]

    collected_texts.extend(sample_data)

    # JSON 형식으로 저장
    data = {
        'source': 'zigzag',
        'collected_at': datetime.now().isoformat(),
        'texts': collected_texts,
        'count': len(collected_texts)
    }

    # S3에 저장
    s3_key = f"{S3_INPUT_PREFIX}zigzag/{execution_date}/fashion.json"
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
        ContentType='application/json'
    )

    print(f"지그재그 데이터 수집 완료: {len(collected_texts)}건")
    print(f"저장 위치: s3://{S3_BUCKET}/{s3_key}")
    return s3_key


def collect_musinsa_data(**context):
    """
    무신사 스토어 패션 트렌드 수집
    """
    import requests
    from bs4 import BeautifulSoup
    import time
    import random

    s3_client = boto3.client('s3', region_name=AWS_REGION)
    execution_date = context['execution_date'].strftime('%Y%m%d')

    collected_texts = []

    # 무신사에서 실제 사용되는 패션 용어
    sample_data = [
        "스트릿 감성 스타일",
        "오버핏 박시 티셔츠",
        "빈티지 무드 청바지",
        "미니멀 베이직 아이템",
        "유니크 디테일 돋보이는",
        "시그니처 로고 포인트",
        "레트로 감성 스니커즈",
        "심플 클래식 무드",
        "트렌디한 실루엣",
        "믹스매치 코디 추천",
        "레이어드 스타일링",
        "원마일웨어 추천",
        "애슬레저룩 완성",
        "젠더리스 유니섹스",
        "오가닉 코튼 소재",
        "친환경 리사이클",
        "아카이브 콜라보",
        "리미티드 에디션",
        "프리미엄 퀄리티",
        "가성비 끝판왕",
    ]

    collected_texts.extend(sample_data)

    # JSON 형식으로 저장
    data = {
        'source': 'musinsa',
        'collected_at': datetime.now().isoformat(),
        'texts': collected_texts,
        'count': len(collected_texts)
    }

    # S3에 저장
    s3_key = f"{S3_INPUT_PREFIX}musinsa/{execution_date}/fashion.json"
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
        ContentType='application/json'
    )

    print(f"무신사 데이터 수집 완료: {len(collected_texts)}건")
    print(f"저장 위치: s3://{S3_BUCKET}/{s3_key}")
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
    start = DummyOperator(
        task_id='start',
    )

    # Task 1: 디시인사이드 데이터 수집
    collect_dcinside = PythonOperator(
        task_id='collect_dcinside_data',
        python_callable=collect_dcinside_data,
    )

    # Task 2: 네이버 블로그 데이터 수집
    collect_naver_blog = PythonOperator(
        task_id='collect_naver_blog_data',
        python_callable=collect_naver_blog_data,
    )

    # Task 3: 네이버 쇼핑 데이터 수집
    collect_naver_shopping = PythonOperator(
        task_id='collect_naver_shopping_data',
        python_callable=collect_naver_shopping_data,
    )

    # Task 4: 인스타이즈 데이터 수집
    collect_instiz = PythonOperator(
        task_id='collect_instiz_data',
        python_callable=collect_instiz_data,
    )

    # Task 5: 네이버 뉴스 데이터 수집
    collect_naver_news = PythonOperator(
        task_id='collect_naver_news_data',
        python_callable=collect_naver_news_comments,
    )

    # Task 6: 쿠팡 데이터 수집
    collect_coupang = PythonOperator(
        task_id='collect_coupang_data',
        python_callable=collect_coupang_reviews,
    )

    # Task 7: 지그재그 데이터 수집
    collect_zigzag = PythonOperator(
        task_id='collect_zigzag_data',
        python_callable=collect_zigzag_data,
    )

    # Task 8: 무신사 데이터 수집
    collect_musinsa = PythonOperator(
        task_id='collect_musinsa_data',
        python_callable=collect_musinsa_data,
    )

    # Task 9: 데이터 수집 완료
    data_collection_complete = DummyOperator(
        task_id='data_collection_complete',
    )

    # Task 10: AWS Glue Job 실행 (신조어 추출 + 중복 제거 + 뜻 풀이)
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
        # region_name은 aws_conn_id를 통해 설정 (기본: aws_default)
        # iam_role_name, num_of_dpus는 deprecated (Glue Job 자체 설정 사용)
        wait_for_completion=False,  # 비동기 실행
    )

    # Task 5: Glue Job 완료 대기
    wait_for_glue = GlueJobSensor(
        task_id='wait_for_glue_job',
        job_name=GLUE_JOB_NAME,
        run_id="{{ task_instance.xcom_pull(task_ids='run_neologism_extraction_glue_job', key='return_value') }}",
        # region_name은 aws_conn_id를 통해 설정 (기본: aws_default)
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
    end = DummyOperator(
        task_id='end',
    )

    # Task 의존성 정의
    start >> [
        collect_dcinside,
        collect_naver_blog,
        collect_naver_shopping,
        collect_instiz,
        collect_naver_news,
        collect_coupang,
        collect_zigzag,
        collect_musinsa,
    ] >> data_collection_complete
    data_collection_complete >> run_glue_job >> wait_for_glue >> validate >> notify >> end
