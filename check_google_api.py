import os
import google.generativeai as genai
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()
print("환경 변수를 로드했습니다.")

# API 키 가져오기
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    print("❌ 오류: .env 파일에서 GOOGLE_API_KEY를 찾을 수 없습니다.")
    exit()
else:
    print("✅ GOOGLE_API_KEY를 성공적으로 로드했습니다.")

try:
    print("\nGoogle Generative AI API에 연결을 시도하고 모델 목록을 가져옵니다...")
    # API 키 설정
    genai.configure(api_key=GOOGLE_API_KEY)

    # 사용 가능한 모델 목록 가져오기
    # 'generateContent'를 지원하는 모델만 필터링합니다.
    available_models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            available_models.append(m.name)

    print("\n✅ API 키가 유효하며, 'generateContent'를 지원하는 모델 목록:")
    if available_models:
        for model_name in available_models:
            print(f"- {model_name}")
        print("\n💡 `build_graph_v2.py` 파일의 'LLM_MODEL_NAME' 변수를 위 목록에 있는 모델 이름 중 하나로 업데이트하세요.")
        print("   (예: 'models/gemini-1.5-flash-latest' 또는 'models/gemini-pro' 가 있다면 그대로 사용)")
    else:
        print(" -> 'generateContent'를 지원하는 모델을 찾을 수 없습니다. API 키의 권한이나 지역 제한을 확인하세요.")

except Exception as e:
    print("\n❌ Google Generative AI API 연결 또는 모델 목록 조회 실패 ❌")
    print(f"\n[오류 메시지]\n{e}")
    print("\n[체크리스트]")
    print("1. .env 파일의 GOOGLE_API_KEY가 정확한지 다시 확인하세요.")
    print("2. Google AI Studio 또는 Google Cloud Console에서 API 키가 활성화되어 있는지 확인하세요.")
    print("3. 인터넷 연결이나 방화벽 설정을 확인하세요.")

print("\n--- 테스트 종료 ---")