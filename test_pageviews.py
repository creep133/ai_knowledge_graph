# test_pageviews.py

import os
import requests
from datetime import datetime, timedelta, timezone # timezone import 추가
from dotenv import load_dotenv
import urllib.parse # URL 인코딩을 위해 추가

# --- 1. 설정 및 초기화 ---
load_dotenv() # .env 파일 로드 (API 키 등 미래 확장 대비)

# 위키미디어 API 요청 시 필요한 User-Agent 정의 (앱 식별용)
USER_AGENT = "HereStoryGo/1.0 (PythonPageViewTest; https://herestorygo.com)"

# 위키미디어 페이지뷰 API 엔드포인트
PAGEVIEWS_ENDPOINT = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{project}/{access}/{agent}/{article}/{granularity}/{start}/{end}"

# --- 2. 페이지뷰 가져오기 함수 (날짜 형식 수정 및 URL 인코딩 강화) ---
def get_monthly_pageviews(page_title: str, lang: str) -> int:
    """지정된 언어의 위키피디아 문서 최근 30일 조회수를 가져옵니다 (디버깅 포함)."""
    # 시간대 정보를 포함한 현재 UTC 시간을 가져옵니다.
    today = datetime.now(timezone.utc)
    last_month = today - timedelta(days=30)
    # ❗❗ 날짜 형식을 'YYYYMMDD'로 수정 (API 요구사항)
    start_date = last_month.strftime('%Y%m%d')
    end_date = today.strftime('%Y%m%d')
    total_views = 0 # 조회수 기본값 0

    try:
        # 페이지 제목 공백을 '_'로 변환
        title_formatted = page_title.replace(" ", "_")
        # ❗ URL에 안전하도록 페이지 제목 인코딩 (특수문자 처리)
        title_url_encoded = urllib.parse.quote(title_formatted)

        # 요청할 언어 설정 (예: fr.wikipedia.org)
        project_url = f"{lang}.wikipedia.org"
        # API URL 완성
        url = PAGEVIEWS_ENDPOINT.format(
            project=project_url, access="all-access", agent="user",
            article=title_url_encoded, # 인코딩된 제목 사용
            granularity="daily", # 일별 데이터 요청
            start=start_date,    # 시작 날짜 (YYYYMMDD)
            end=end_date         # 종료 날짜 (YYYYMMDD)
        )
        # 요청 헤더 (User-Agent 포함 필수)
        headers = {'User-Agent': USER_AGENT}

        print(f"    - Requesting pageviews for '{page_title}' ({lang}): {url}") # 디버깅: 요청 URL 출력
        # API 요청 보내기 (10초 타임아웃 설정)
        response = requests.get(url, headers=headers, timeout=10)
        print(f"    - Pageviews API status code: {response.status_code}") # 디버깅: 응답 코드 출력

        # 응답 코드가 4xx 또는 5xx 이면 오류 발생시킴
        response.raise_for_status()

        # 응답받은 JSON 데이터를 파이썬 딕셔너리로 변환
        data = response.json()
        # 'items' 리스트 안의 모든 'views' 값을 합산
        total_views = sum(item['views'] for item in data.get('items', []))
        print(f"    - Fetched views: {total_views}") # 디버깅: 가져온 조회수 출력
        return total_views # 합산된 조회수 반환

    except requests.Timeout: # 타임아웃 발생 시
        print(f"    !! Timeout fetching pageviews for '{page_title}' ({lang}). Returning 0.")
        return 0
    except requests.RequestException as e: # 그 외 모든 요청 관련 오류 처리
        # 응답 코드가 404 Not Found 이면 페이지가 없는 것이므로 0 반환
        if hasattr(e, 'response') and e.response is not None and e.response.status_code == 404:
            print(f"    - Pageviews API returned 404 for '{page_title}' ({lang}). Assuming 0 views.")
            return 0
        else: # 다른 오류 시 메시지 출력 후 0 반환
            print(f"    !! Error fetching pageviews for '{page_title}' ({lang}): {e}. Returning 0.")
            return 0

# --- 3. 테스트 실행 ---
if __name__ == "__main__":
    print("Starting Wikipedia pageview test...")

    # Test Case 1: 프랑스어 원본 페이지
    print("\n--- Testing 'Parc des Bastions' (fr) ---")
    views1 = get_monthly_pageviews("Parc des Bastions", "fr")
    print(f"-> Result for 'Parc des Bastions' (fr): {views1} views")

    # Test Case 2: 관련 있는 프랑스어 페이지 (더 높은 트래픽 예상)
    print("\n--- Testing 'Genève' (fr) ---")
    views2 = get_monthly_pageviews("Genève", "fr")
    print(f"-> Result for 'Genève' (fr): {views2} views")

    # Test Case 3: 트래픽 높은 영어 페이지 (영어 API 접근 확인용)
    print("\n--- Testing 'Eiffel Tower' (en) ---") # Taylor Swift 대신 에펠탑으로 변경
    views3 = get_monthly_pageviews("Eiffel Tower", "en")
    print(f"-> Result for 'Eiffel Tower' (en): {views3} views")

    # Test Case 4: 존재하지 않는 페이지 (404 오류 처리 확인용)
    print("\n--- Testing 'NonExistentPage12345' (en) ---")
    views4 = get_monthly_pageviews("NonExistentPage123456789ABC", "en") # 더 긴 이름으로 변경
    print(f"-> Result for 'NonExistentPage123456789ABC' (en): {views4} views")

    print("\n--- Pageview test finished ---")