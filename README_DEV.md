# 개발 환경 구성

## 프로젝트 구조

```
project-a-spinoff/
├── venv/                # Python 가상환경 (루트)
├── backend/             # FastAPI 백엔드
│   ├── routes/
│   ├── services/
│   ├── models/
│   └── ...
├── frontend/            # Freshdesk FDK 앱 (Node.js)
│   └── app/
├── start_server.sh      # 백엔드 실행 스크립트
└── README.md
```

---

## 🐍 백엔드 개발 (Python/FastAPI)

### 초기 설정

```bash
# 1. 가상환경 활성화
source venv/bin/activate

# 2. 패키지 설치 (이미 설치됨)
pip install -r backend/requirements.txt
```

### 서버 실행

```bash
# 방법 1: 스크립트 사용 (권장)
./start_server.sh

# 방법 2: 직접 실행
source venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 테스트 실행

```bash
source venv/bin/activate

# 전체 테스트
pytest backend/tests/ -v

# 특정 테스트
pytest backend/tests/test_e2e.py -v
```

### 데이터 시딩

```bash
source venv/bin/activate

# Freshdesk 실데이터로 DB 채우기
python backend/scripts/seed_data.py --tickets 50 --kb 20
```

### API 테스트

```bash
source venv/bin/activate

# 통합 API 테스트
python backend/scripts/test_api.py --full-pipeline
```

---

## 🌐 프론트엔드 개발 (Node.js/Freshdesk FDK)

**⚠️ 프론트엔드는 Python 가상환경 불필요!**

### 초기 설정

```bash
# Python 가상환경 비활성화 (활성화되어 있다면)
deactivate

# frontend 폴더로 이동
cd frontend

# Node.js 버전 확인 (18 권장)
node --version

# 의존성 설치
npm install
```

### FDK 앱 실행

```bash
cd frontend

# 로컬 개발 서버
fdk run

# 또는
npm start
```

### 프론트엔드 작업 후 백엔드로 복귀

```bash
# frontend 작업 끝
cd ..

# Python 가상환경 다시 활성화
source venv/bin/activate
```

---

## 🔄 워크플로우

### 백엔드 작업 시

```bash
# 1. 가상환경 활성화
source venv/bin/activate

# 2. 작업 (코딩, 테스트 등)
uvicorn backend.main:app --reload

# 3. 작업 완료
deactivate
```

### 프론트엔드 작업 시

```bash
# 1. 가상환경 비활성화 (필요시)
deactivate

# 2. frontend로 이동
cd frontend

# 3. 작업
fdk run

# 4. 완료 후 루트로 복귀
cd ..

# 5. 백엔드 작업 계속하려면 가상환경 활성화
source venv/bin/activate
```

---

## 🛠️ 유용한 명령어

### 가상환경 관리

```bash
# 활성화
source venv/bin/activate

# 비활성화
deactivate

# 현재 활성화 여부 확인
which python
# 출력: /Users/alan/GitHub/project-a-spinoff/venv/bin/python (활성화됨)
# 출력: /usr/bin/python (비활성화됨)
```

### 패키지 관리

```bash
source venv/bin/activate

# 설치된 패키지 목록
pip list

# 패키지 추가
pip install <package-name>

# requirements.txt 업데이트
pip freeze > backend/requirements.txt
```

---

## 🚨 주의사항

1. **Python 작업 = 가상환경 ON**
   - `source venv/bin/activate` 필수

2. **Node.js 작업 = 가상환경 OFF**
   - Python 가상환경 필요 없음
   - `deactivate` 후 작업

3. **절대 임포트 구조**
   - 모든 Python 코드는 `from backend.xxx` 형식
   - **반드시 프로젝트 루트에서 실행**

4. **frontend/node_modules 무시**
   - `.gitignore`에 이미 등록됨
   - 매번 `npm install` 필요

---

## 📦 주요 의존성

### 백엔드 (Python)
- FastAPI
- Uvicorn
- LangGraph
- Qdrant Client
- Supabase
- Sentence Transformers

### 프론트엔드 (Node.js)
- Freshdesk FDK
- Node.js 18+

---

## ✅ 빠른 체크리스트

**백엔드 서버 시작 전:**
- [ ] `source venv/bin/activate` 실행
- [ ] `.env` 파일 확인
- [ ] Qdrant 실행 중 (`docker run -p 6333:6333 qdrant/qdrant`)

**프론트엔드 개발 전:**
- [ ] `deactivate` (가상환경 비활성화)
- [ ] `cd frontend`
- [ ] `node --version` (18 확인)
- [ ] `npm install` (초기 1회)
