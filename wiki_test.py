import wikipediaapi
import requests
import json
import urllib.parse  # ❗ URL 인코딩을 위해 이 라이브러리를 추가합니다.

# --- 1. 설정 ---
USER_AGENT = "HereStoryGo/1.0 (PythonTest; https://herestorygo.com)"
START_TITLE = "Parc des Bastions"
LANGUAGE = 'fr' # 테스트할 언어 (프랑스어)
BASE_WIKI_URL = f"https://{LANGUAGE}.wikipedia.org/wiki/"
API_URL = f"https://{LANGUAGE}.wikipedia.org/w/api.php"

print(f"Wikipedia 연결 테스트를 시작합니다...")
print(f"User-Agent: {USER_AGENT}")
print(f"테스트 대상: '{START_TITLE}' ({LANGUAGE} 위키)")

# --- 2. 'wikipediaapi' 라이브러리 테스트 (fr) ---
print("\n--- 테스트 1: 'wikipediaapi' 라이브러리 (페이지 요약) ---")
try:
    wiki_api = wikipediaapi.Wikipedia(
        language=LANGUAGE,
        user_agent=USER_AGENT
    )
    
    page = wiki_api.page(START_TITLE)
    
    if page.exists():
        print(f"✅ 성공: '{START_TITLE}' 페이지를 찾았습니다. ({LANGUAGE})")
        print(f"  > 요약 (첫 100자): {page.summary[:100]}...")
    else:
        print(f"❌ 실패: '{START_TITLE}' 페이지를 찾을 수 없습니다. ({LANGUAGE})")
        
except Exception as e:
    print(f"❌ 오류 발생: {e}")

# --- 3. 'requests' 백링크 API 테스트 (fr) ---
print("\n--- 테스트 2: 'requests' (백링크 API) ---")
try:
    params = {
        "action": "query",
        "format": "json",
        "list": "backlinks",
        "bltitle": START_TITLE,
        "bllimit": 5  # 5개만 가져옵니다.
    }
    headers = {'User-Agent': USER_AGENT} 
    
    response = requests.get(API_URL, params=params, headers=headers)
    response.raise_for_status() 
    
    data = response.json()
    print(json.dumps(data, indent=2, ensure_ascii=False)) # 보기 좋게 출력하기 위해 json.dumps 사용
    backlinks = data.get('query', {}).get('backlinks', [])
    
    print(f"✅ 성공: 백링크 API가 응답했습니다. ({LANGUAGE})")
    print(f"  > {len(backlinks)}개의 백링크를 찾았습니다.")
    
    # ❗❗ 수정된 부분: 찾은 백링크의 제목과 전체 URL을 함께 출력합니다.
    if backlinks:
        print("\n  [백링크 목록 (제목과 URL)]")
        for item in backlinks:
            title = item['title']
            
            # 위키피디아 URL 형식에 맞게 띄어쓰기를 '_'로 변환하고,
            # urllib.parse.quote를 사용해 한글이나 특수문자를 URL 인코딩합니다.
            url_encoded_title = urllib.parse.quote(title.replace(" ", "_"))
            full_url = f"{BASE_WIKI_URL}{url_encoded_title}"
            
            print(f"  - 제목: {title}")
            print(f"    URL: {full_url}\n") # URL을 다음 줄에 출력하여 복사하기 쉽게 함
            
    else:
        print("\n  > 이 페이지를 링크하는 백링크를 찾지 못했습니다.")
        
except Exception as e:
    print(f"❌ 오류 발생: {e}")

print("\n--- 테스트 종료 ---")