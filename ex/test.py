import os
import google.generativeai as genai

# 본인 API 키 입력
os.environ["GOOGLE_API_KEY"] = "AIzaSyCPD814lExKacaLxRkSdtusFf9RgNgvzNk" 

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

print("\n📋 === 사용 가능한 모델 목록 (이 이름을 복사하세요) ===")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            # "models/"를 뺀 순수 이름만 출력
            print(f"✅ {m.name.replace('models/', '')}")
except Exception as e:
    print(f"❌ 에러 발생: {e}")
print("======================================================\n")