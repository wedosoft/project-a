# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a RAG-based Freshdesk Custom App built with FastAPI backend and Freshdesk FDK frontend. The system provides AI-powered customer support assistance through natural language processing, vector database search, and multi-LLM routing capabilities.

**Architecture**: Vector DB-only architecture with RESTful streaming for real-time ticket search and analysis.

## Development Guidelines

- python을 실행할 때는 반드시 backend/venv에서 작업을 해주세요.

## Error Handling and Fallback Principles

- fallback 처리의 기본은 로직이 실패하면 오류를 정확히 표시하고 사용자가 이해할 수 있게 합니다. 절대 fallback시 기본값 같은거는 사용하지 않습니다. 기본 매핑/기본값은 사용자에게 오히려 더 혼란을 줍니다.

## 백엔드-프론트엔드 데이터 처리 원칙

### 1. 백엔드 응답 데이터 구조
백엔드는 프레시데스크 시스템의 **원본 숫자값**을 그대로 프론트엔드로 전송합니다:
- `priority`: 1 (Low), 2 (Medium), 3 (High), 4 (Urgent)
- `status`: 2 (Open), 3 (Pending), 4 (Resolved), 5 (Closed), 6 (Waiting on customer), 7 (Waiting on third party)
- `requester_id`, `responder_id`, `group_id`, `product_id`, `company_id` 등: 각종 ID 숫자값

### 2. 프론트엔드 레이블 처리 원칙
**절대 금지사항:**
- ❌ 하드코딩된 레이블 매핑 사용
- ❌ 임의로 정의한 레이블 사용  
- ❌ 백엔드 숫자값을 직접 화면에 표시
- ❌ 기본값 또는 fallback 레이블 사용

**필수 준수사항:**
- ✅ 모든 레이블은 FDK `data method` 또는 `request method`를 통해서만 추출
- ✅ 백엔드 숫자값 → FDK 조회 → 사용자용 레이블 변환
- ✅ FDK 조회 실패 시 명확한 오류 표시 (기본값 사용 금지)

### 3. FDK Data Method vs Request Method 사용 지침

#### Data Method 사용 (현재 티켓 정보)
**용도**: 현재 페이지에서 보고 있는 티켓의 정보를 가져올 때
- 메인 티켓의 priority, status 등 기본 필드
- 현재 티켓의 requester, contact, company, group 정보
- 사용 가능한 옵션 목록 조회 (`status_options`, `priority_options` 등)

#### Request Method 사용 (다른 티켓/외부 데이터)
**용도**: API 호출로 다른 티켓이나 외부 리소스 정보를 가져올 때
- 유사 티켓의 requester_id → 사용자명 변환
- 백엔드에서 받은 ID들을 실제 이름으로 변환
- 현재 티켓이 아닌 다른 티켓들의 상세 정보

### 4. 필드별 FDK 조회 방법

#### Priority 처리
- **Data Method**: `client.data.get("ticket")` → `ticket.priority`와 `ticket.priority_label` 활용
- **Options**: `client.data.get("priority_options")` → 모든 priority 옵션 목록

#### Status 처리  
- **Data Method**: `client.data.get("ticket")` → `ticket.status` 숫자값
- **Display Value**: `ticket.status_type` 또는 별도 조회 필요
- **Options**: `client.data.get("status_options")` → 모든 status 옵션 목록

#### 사용자/담당자 정보
- **Requester**: `client.data.get("requester")` → 현재 티켓 요청자
- **Contact**: `client.data.get("contact")` → 현재 티켓 연락처
- **다른 사용자**: `client.request.invokeTemplate()`로 API 호출

#### 그룹/회사 정보
- **Group**: `client.data.get("group")` → 현재 티켓 그룹
- **Company**: `client.data.get("company")` → 현재 티켓 회사
- **다른 그룹/회사**: `client.request.invokeTemplate()`로 API 호출

### 5. 구현 패턴

#### 현재 티켓 정보 표시 (Data Method)
올바른 방법: FDK data method로 현재 티켓의 모든 정보를 한 번에 조회
잘못된 방법: 숫자값을 하드코딩된 매핑으로 변환

#### 유사 티켓 정보 표시 (Request Method)
올바른 방법: 백엔드에서 받은 ID들을 request method로 실제 레이블 조회
잘못된 방법: ID 숫자값을 그대로 표시하거나 임의 레이블 사용

#### 오류 처리
올바른 방법: FDK 조회 실패 시 "정보를 가져올 수 없습니다" 등 명확한 오류 메시지
잘못된 방법: "Unknown", "N/A" 등 기본값 표시

### 6. 성능 최적화 고려사항
- Data method는 앱 초기화 후 한 번만 호출하여 캐싱
- Request method 결과는 동일 ID에 대해 로컬 캐싱 활용
- 여러 ID의 일괄 조회가 가능한 경우 배치 처리
- 재시도 로직 구현 (최대 3회, 지수 백오프)

## FDK API Call Strategies

- FDK에서 요청은 두 가지 메서드를 사용합니다:
  - `data method`: 현재 보고 있는 티켓의 정보를 가져오는 데 사용 (메인 티켓 요약)
  - `request method`: API 호출로 다른 티켓의 정보를 가져오는 데 사용 (유사 티켓)
- 메인 티켓 요약: `data method` 사용
- 메인 티켓의 일부 레이블 조회: `request method` 병행 사용
- 유사 티켓: 백엔드 응답의 숫자 값들의 레이블을 얻기 위해 `request method` 사용
- 최적화 시 이러한 메서드 사용 방식을 고려해야 합니다.
- 참고 사이트 : 
https://developers.freshworks.com/docs/app-sdk/v3.0/support_ticket/front-end-apps/data-method/                                      │
https://developers.freshworks.com/docs/app-sdk/v3.0/common/advanced-interfaces/request-method/  

## Key Development Commands

## Freshdesk API Headers

### Standard API Request Headers
- X-Tenant-ID: wedosoft
- X-Platform: freshdesk
- X-Domain: weodosft.freshdesk.com
- 모든 엔드포인트의 엔드포인트 필수 헤더입니다. 인지하세요.

## Multilingual System Guidelines

### Multilingual Processing Principles
- 기본적으로 우리 시스템은 다국어를 지향하고 있습니다. 템플릿이나 프롬프트에 한국어로만 강제하는 코드는 제거하세요.
- 다음 다국어 처리 원칙을 유의하세요:
  1. UI 언어 (Title Language):
     - 요약 섹션의 타이틀 언어를 의미합니다.
     - 본문 언어와는 완전히 별개입니다.
     - 상담원 언어 파라미터로 결정 (ko이면 한국어 타이틀, 그 외 영어 타이틀)
  2. 본문 요약 언어:
     - 본문 언어를 자동 감지하여 해당 언어로 요약
     - 현재 언어 결정 로직은 LLM에 의존
  3. LLM 의존 판단 항목:
     - 요약 본문의 언어 식별
     - 유사 티켓 요약 시 관련 첨부파일 식별
       * 원문 파일 3개 이하: 그대로 반환
       * 3개 초과: LLM이 판단
     - 다국어 및 복잡한 환경에서의 통합 판단 요청