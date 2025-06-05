# 로깅 시스템 가이드

## 개요

본 문서는 Prompt Canvas 백엔드에서 사용하는 로깅 시스템에 대한 설명입니다. 로그는 디버깅 및 시스템 모니터링을 위해 중요한 요소입니다.

## 로그 파일 구조

로그 파일은 자동으로 회전(rotation)됩니다:

- **기본 로그 파일**: `backend/freshdesk_collection.log`
- **회전 로그 파일**: `backend/freshdesk_collection.log.1`, `backend/freshdesk_collection.log.2`, ... 등
  
## 로그 설정 세부사항

- **최대 파일 크기**: 각 로그 파일은 5MB로 제한됩니다
- **백업 파일 수**: 최대 10개의 로그 파일이 유지됩니다
- **인코딩**: UTF-8
- **로그 포맷**: `시간 - 모듈명 - 로그레벨 - 메시지`

## 로그 사용 방법

### 코드에서 사용하기

```python
import logging

# 로거 가져오기
logger = logging.getLogger(__name__)

# 로그 기록
logger.info('정보 메시지')
logger.warning('경고 메시지')
logger.error('오류 메시지')
logger.debug('디버그 메시지')
```

### 로그 파일 확인

```bash
# 최신 로그 보기
tail -f backend/freshdesk_collection.log

# 모든 로그 파일 크기 확인
ls -la backend/freshdesk_collection.log*
```

## 로그 레벨

- **DEBUG**: 상세한 디버깅 정보
- **INFO**: 일반적인 정보 메시지
- **WARNING**: 주의가 필요한 상황
- **ERROR**: 오류 상황
- **CRITICAL**: 심각한 오류 상황

## 주의사항

- 민감한 정보(API 키, 비밀번호 등)는 로그에 기록하지 않도록 주의하세요.
- 대용량 데이터 수집 시 로그가 빠르게 증가할 수 있으므로 주기적으로 모니터링하세요.
- 필요 시 오래된 로그 파일은 수동으로 정리할 수 있습니다.
