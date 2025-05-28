# 프로젝트 스크립트 폴더

이 폴더는 프로젝트 전체 관리 관련 스크립트를 포함합니다.

## 파일 목록

### 📊 데이터 관리
- `load_faqs.py` - FAQ 데이터를 Qdrant DB에 로딩
- `task-complexity-report.json` - Task Master 복잡도 분석 보고서

### 📋 프로젝트 문서
- `prd.txt` - 프로젝트 요구사항 정의서 (현재 버전)
- `example_prd.txt` - PRD 작성 예시

## 사용법

### FAQ 데이터 로딩
```bash
# CSV 파일로부터 FAQ 로딩
cd backend
python ../scripts/load_faqs.py --file_path /path/to/faqs.csv --company_id your_company

# JSON 파일로부터 FAQ 로딩
python ../scripts/load_faqs.py --file_path /path/to/faqs.json --company_id your_company --file_type json
```

## 주의사항

- 모든 스크립트는 프로젝트 루트에서 실행하는 것을 권장합니다
- 데이터 로딩 스크립트는 백엔드 환경이 설정된 상태에서 실행해야 합니다
