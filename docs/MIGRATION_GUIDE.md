# Supabase Migration 적용 가이드

## 현재 상황

**문제**: `issue_repository.py`의 `create()`, `count()` 등 메서드가 `set_config()` RPC 함수를 호출하는데, Supabase에 해당 함수가 없어서 실패합니다.

**해결**: PostgreSQL 함수를 생성하는 Migration을 적용해야 합니다.

## Migration 적용 방법

### Option 1: Supabase Dashboard (추천 - 가장 쉬움)

1. **Supabase Dashboard 접속**
   ```
   https://supabase.com/dashboard
   ```

2. **프로젝트 선택**
   - 본인의 프로젝트 선택

3. **SQL Editor 열기**
   - 왼쪽 메뉴에서 "SQL Editor" 클릭
   - "New query" 버튼 클릭

4. **Migration SQL 복사 & 붙여넣기**
   ```sql
   CREATE OR REPLACE FUNCTION public.set_config(key text, value text)
   RETURNS void
   LANGUAGE plpgsql
   SECURITY DEFINER
   AS $$
   BEGIN
       PERFORM set_config(key, value, false);
   END;
   $$;

   GRANT EXECUTE ON FUNCTION public.set_config(text, text) TO authenticated;

   COMMENT ON FUNCTION public.set_config(text, text) IS
   'Sets a configuration parameter for the current transaction. Used for RLS tenant isolation.';
   ```

5. **실행**
   - "Run" 버튼 클릭 (또는 Cmd/Ctrl + Enter)
   - "Success. No rows returned" 메시지 확인

6. **검증**
   - 같은 SQL Editor에서 아래 쿼리 실행:
   ```sql
   SELECT routine_name, routine_type
   FROM information_schema.routines
   WHERE routine_schema = 'public' AND routine_name = 'set_config';
   ```
   - 결과: `set_config | FUNCTION` 나오면 성공

### Option 2: Supabase CLI

```bash
# Supabase CLI 설치 (없을 경우)
brew install supabase/tap/supabase

# 프로젝트 연결
supabase link --project-ref [YOUR_PROJECT_REF]

# Migration 적용
supabase db push
```

### Option 3: psql 직접 연결

```bash
# Connection string 확인
# Supabase Dashboard → Settings → Database → Connection string

psql "postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres" \
  -f backend/migrations/001_create_set_config_function.sql
```

## Migration 적용 확인

### 함수 존재 확인
```sql
SELECT routine_name, routine_type
FROM information_schema.routines
WHERE routine_schema = 'public'
  AND routine_name = 'set_config';
```

**정상 결과:**
```
 routine_name | routine_type
--------------+--------------
 set_config   | FUNCTION
```

### 권한 확인
```sql
SELECT grantee, privilege_type
FROM information_schema.routine_privileges
WHERE routine_schema = 'public'
  AND routine_name = 'set_config';
```

**정상 결과:**
```
    grantee     | privilege_type
----------------+----------------
 authenticated  | EXECUTE
```

## 테스트 실행

Migration 적용 후:

```bash
# 가상환경 활성화
source venv/bin/activate

# 50건 실데이터 시딩
python backend/scripts/seed_data.py --tickets 50 --kb 20
```

**예상 결과:**
```
🎫 Freshdesk에서 티켓 50개 가져오는 중...
✅ 50개 티켓 가져옴 (요청: 50개)

🤖 LLM으로 Issue Block 추출 중...
티켓 처리: 100%|██████████| 50/50
✅ 150개 Issue Block 추출 완료

💾 Supabase에 저장 중...
DB 저장: 100%|██████████| 150/150
✅ Supabase에 150개 저장 완료  ← 이전에는 0개였음!

🔍 Qdrant에 임베딩 저장 중...
✅ Qdrant에 150개 임베딩 저장 완료
```

## 롤백 방법

함수를 제거하려면:

```sql
DROP FUNCTION IF EXISTS public.set_config(text, text);
```

⚠️ **주의**: 롤백 시 Repository의 RLS 메서드가 작동하지 않습니다.

## 트러블슈팅

### 오류: "permission denied for function set_config"
**원인**: GRANT 문이 실행되지 않음
**해결**: GRANT 문만 다시 실행
```sql
GRANT EXECUTE ON FUNCTION public.set_config(text, text) TO authenticated;
```

### 오류: "function set_config(text, text) already exists"
**원인**: 이미 함수가 존재함
**해결**: 정상. 검증 쿼리로 확인만 하면 됨

### 오류: "Could not find the function public.set_config"
**원인**: Migration이 적용되지 않음
**해결**: 위 적용 방법 중 하나로 다시 시도

## 다음 단계

1. ✅ Migration 적용
2. ✅ 검증 쿼리 실행
3. ✅ 50건 실데이터 테스트
4. ✅ Supabase 저장 성공 확인
5. ✅ E2E API 테스트
