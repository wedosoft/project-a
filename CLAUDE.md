# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a RAG-based Freshdesk Custom App built with FastAPI backend and Freshdesk FDK frontend. The system provides AI-powered customer support assistance through natural language processing, vector database search, and multi-LLM routing capabilities.

**Architecture**: Vector DB-only architecture with RESTful streaming for real-time ticket search and analysis.

## Development Guidelines

- python을 실행할 때는 반드시 backend/venv에서 작업을 해주세요.

## Error Handling and Fallback Principles

- fallback 처리의 기본은 로직이 실패하면 오류를 정확히 표시하고 사용자가 이해할 수 있게 합니다. 절대 fallback시 기본값 같은거는 사용하지 않습니다. 기본 매핑/기본값은 사용자에게 오히려 더 혼란을 줍니다.

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

[... rest of the existing file content remains unchanged ...]