# Supabase Migrations

이 디렉토리는 Supabase 데이터베이스 마이그레이션 파일을 포함합니다.

## 마이그레이션 적용 방법

### Option 1: Supabase Dashboard (권장)

1. [Supabase Dashboard](https://supabase.com/dashboard) 접속
2. 프로젝트 선택
3. **SQL Editor** 메뉴 클릭
4. **New query** 버튼 클릭
5. 마이그레이션 SQL 파일 내용 복사 & 붙여넣기
6. **Run** 버튼 클릭

### Option 2: Supabase CLI

```bash
# Supabase CLI 설치 (없을 경우)
brew install supabase/tap/supabase

# 프로젝트 연결
supabase link --project-ref [YOUR_PROJECT_REF]

# 마이그레이션 적용
supabase db push
```

### Option 3: SQL 직접 실행

```bash
# PostgreSQL 클라이언트로 직접 연결
psql -h [YOUR_SUPABASE_HOST] -p 5432 -U postgres -d postgres -f migrations/001_create_set_config_function.sql
```

## 마이그레이션 목록

### 001_create_set_config_function.sql
- **목적**: RLS (Row Level Security) 테넌트 격리를 위한 `set_config()` 함수 생성
- **생성일**: 2025-11-02
- **의존성**: 없음
- **영향**: `issue_blocks`, `kb_blocks` 테이블의 RLS 정책 동작

## 마이그레이션 검증

마이그레이션 적용 후 다음 명령으로 함수가 생성되었는지 확인:

```sql
-- 함수 존재 확인
SELECT routine_name, routine_type
FROM information_schema.routines
WHERE routine_schema = 'public'
  AND routine_name = 'set_config';

-- 함수 권한 확인
SELECT grantee, privilege_type
FROM information_schema.routine_privileges
WHERE routine_schema = 'public'
  AND routine_name = 'set_config';
```

정상적으로 생성되었다면:
```
 routine_name | routine_type
--------------+--------------
 set_config   | FUNCTION

    grantee     | privilege_type
----------------+----------------
 authenticated  | EXECUTE
```

## 롤백 방법

함수를 제거하려면:

```sql
DROP FUNCTION IF EXISTS public.set_config(text, text);
```

⚠️ **주의**: 롤백 시 Repository의 `create()`, `count()` 등 RLS 메서드가 작동하지 않습니다.
