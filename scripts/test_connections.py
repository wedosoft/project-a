#!/usr/bin/env python3
"""
통합 연결 테스트 스크립트
- Supabase
- Qdrant
- Freshdesk API
- OpenAI API
- Google Gemini API
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트 경로 설정
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# .env 파일 로드
env_path = project_root / ".env"
load_dotenv(env_path)

print("=" * 60)
print("🔍 AI Contact Center OS - Connection Tests")
print("=" * 60)

# Test Results
results = {
    "supabase": {"status": "❌", "message": ""},
    "freshdesk": {"status": "❌", "message": ""},
    "openai": {"status": "❌", "message": ""},
    "gemini": {"status": "❌", "message": ""},
}


# 1. Supabase 테스트
print("\n1️⃣  Testing Supabase Connection...")
try:
    from supabase import create_client, Client

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL or SUPABASE_KEY not found in .env")

    supabase: Client = create_client(supabase_url, supabase_key)

    # 간단한 쿼리로 연결 테스트 (테이블이 없을 수 있으므로 에러 무시)
    try:
        response = supabase.table("issue_blocks").select("count").limit(1).execute()
        results["supabase"]["status"] = "✅"
        results["supabase"]["message"] = f"Connected to {supabase_url}"
    except Exception as table_error:
        # 테이블이 없어도 연결 자체는 성공
        if "does not exist" in str(table_error) or "relation" in str(table_error):
            results["supabase"]["status"] = "⚠️"
            results["supabase"]["message"] = f"Connected, but tables not created yet"
        else:
            raise table_error

except Exception as e:
    results["supabase"]["status"] = "❌"
    results["supabase"]["message"] = f"Error: {str(e)[:100]}"


# 2. Freshdesk API 테스트
print("\n2️⃣  Testing Freshdesk API...")
try:
    import requests

    freshdesk_domain = os.getenv("FRESHDESK_DOMAIN")
    freshdesk_api_key = os.getenv("FRESHDESK_API_KEY")

    if not freshdesk_domain or not freshdesk_api_key:
        raise ValueError("FRESHDESK_DOMAIN or FRESHDESK_API_KEY not found in .env")

    # 티켓 1개만 조회 (API 테스트)
    url = f"https://{freshdesk_domain}/api/v2/tickets"
    auth = (freshdesk_api_key, "X")

    response = requests.get(
        url,
        auth=auth,
        params={"per_page": 1},
        timeout=10
    )

    if response.status_code == 200:
        tickets = response.json()
        results["freshdesk"]["status"] = "✅"
        results["freshdesk"]["message"] = f"Connected. Found {len(tickets)} ticket(s)"
    else:
        raise Exception(f"HTTP {response.status_code}: {response.text[:100]}")

except Exception as e:
    results["freshdesk"]["status"] = "❌"
    results["freshdesk"]["message"] = f"Error: {str(e)[:100]}"


# 3. OpenAI API 테스트
print("\n3️⃣  Testing OpenAI API...")
try:
    from openai import OpenAI

    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY not found in .env")

    client = OpenAI(api_key=openai_api_key)

    # 간단한 completion 테스트
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say 'OK' if you can read this."}],
        max_tokens=5
    )

    results["openai"]["status"] = "✅"
    results["openai"]["message"] = f"Connected. Response: {response.choices[0].message.content.strip()}"

except Exception as e:
    results["openai"]["status"] = "❌"
    results["openai"]["message"] = f"Error: {str(e)[:100]}"


# 4. Google Gemini API 테스트
print("\n4️⃣  Testing Google Gemini API...")
try:
    import google.generativeai as genai

    gemini_api_key = os.getenv("GEMINI_API_KEY")

    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY not found in .env")

    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel("gemini-2.0-flash-exp")

    # 간단한 generation 테스트
    response = model.generate_content("Say 'OK' if you can read this.")

    results["gemini"]["status"] = "✅"
    results["gemini"]["message"] = f"Connected. Response: {response.text.strip()[:50]}"

except Exception as e:
    results["gemini"]["status"] = "❌"
    results["gemini"]["message"] = f"Error: {str(e)[:100]}"


# 결과 출력
print("\n" + "=" * 60)
print("📊 Test Results Summary")
print("=" * 60)

for service, result in results.items():
    print(f"\n{result['status']} {service.upper()}")
    print(f"   {result['message']}")

# 전체 통과 여부
all_passed = all(r["status"] in ["✅", "⚠️"] for r in results.values())

print("\n" + "=" * 60)
if all_passed:
    print("✅ All critical services are accessible!")
    print("⚠️  Note: Supabase tables may need to be created via migration")
    sys.exit(0)
else:
    print("❌ Some services failed. Check the errors above.")
    sys.exit(1)
