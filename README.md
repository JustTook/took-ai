# Took AI - Multi-Agent Server

Google Gemini 기반의 멀티 에이전트 시스템을 위한 FastAPI 서버입니다.
사용자의 질문에 맞춰 전문가 에이전트를 자동으로 구성하고, 토론을 통해 결론을 도출합니다.

## 설정 (Configuration)

프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 다음 환경 변수를 설정해주세요.

```bash
# .env 예시
GOOGLE_API_KEY=your_google_api_key_here
BACKEND_URL=http://host.docker.internal:8000/agent/result
```

## 실행 방법 (Docker)

Docker Compose를 사용하여 전체 서비스를 한 번에 실행할 수 있습니다.

### 1. 서비스 시작
터미널에서 다음 명령어를 실행하세요.

```bash
docker-compose up --build -d
```
> `-d` 옵션으로 백그라운드에서 실행합니다.

### 2. 로그 확인
실행 중인 서버의 로그를 실시간으로 확인하려면:

```bash
docker-compose logs -f
```

### 3. 서비스 중지
```bash
docker-compose down
```

## API 사용 가이드

서버가 실행되면 **5001번 포트**를 통해 접근할 수 있습니다.

- **Base URL**: `http://localhost:5001`
- **Swagger UI**: `http://localhost:5001/docs` (API 문서 및 테스트)

## 로컬 환경 실행

Docker 없이 직접 Python 환경에서 실행하려면:

1. 가상환경 생성 및 활성화
```bash
python -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate  # Windows
```

2. 의존성 설치
```bash
pip install -r requirements.txt
```

3. 서버 실행
```bash
uvicorn main:app --reload --port 5001
```
