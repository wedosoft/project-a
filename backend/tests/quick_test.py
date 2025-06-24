#!/usr/bin/env python3
"""
빠른 요약 테스트
"""

import asyncio
import sys
import os
sys.path.insert(0, '/Users/alan/GitHub/project-a/backend')

from core.llm.optimized_summarizer import generate_optimized_summary

test_content = """제목: 마크애니 MX레크드관련

설명: 마크애니입니다. MX레코드관련해서 다시 최종 메일 드립니다. 위두측에서 저희 MX레코드 등록현황을 확인하였다시피 권고한 MX레코드가 등록 추가되었음을 확인하셨었습니다. 이는 이전에 안내된 구글쪽 안내 메일에따라 아래 레코드가 추가했었습니다. Priority Mail server 1 ASPMX.L.GOOGLE.COM . 5 ALT1.ASPMX.L.GOOGLE.COM . 5 ALT2.ASPMX.L.GOOGLE.COM . 10 ALT3.ASPMX.L.GOOGLE.COM . 10 ALT4.ASPMX.L.GOOGLE.COM . 그런데 아래 Procedure가 안내되던데요. 이건 뭔가요. 아래 절차에다라 MX레코드를 수정하라는것 같은데요. 뭐가 뭔지 모르겠습니다. 저희 DNS에 위 레코드를 추가등록하기만 하면되는줄알았는데 또 뭘 수정하라는건지..... 확인하여주시고, 그에따른 조치 부탁드리겠습니다. 갈수록 구글 메일 쓰시가 어려워집니다.

대화: From: The Postini / Google Apps Transition Team < apps-noreply@google.com > Date: 2015-06-24 6:19 GMT+09:00 Subject: ACTION REQUIRED to prevent permanent loss of email To: admin@markany.com Dear Postini Customer, In September, 2015, Google will no longer support DNS redirection of MX records from Postini to Google Apps. If you do not take action, your inbound mailflow will fail on or after that date. The MX records for the following domains currently point to Postini: markany.com These domains currently rely on DNS redirection to send your traffic to Google Apps. If you do not change your MX records to point to Google Apps, you will not receive any inbound mail for these domains.

대화: 안녕하세요 이대영 차장 님, 위두소프트 고객 지원팀입니다. 문의하신 내용 관련하여 이전까지 저희가 안내드렸던 내용이 맞다고 보입니다만, 이와 관련하여 포스티니 고객센터로 컨펌을 위한 문의를 진행하고 있습니다. 곧 다시 답신 드리겠습니다. 감사합니다.

연락처: MarkAny Inc. 이대영 차장 Lee, Dae-Young 경영지원실/법무팀 / IT,구매담당 Office: 02-2262-5265, Mobile 010-2738-9311 Fax: 822-2262-5333 Email: dylee@markany.com"""

async def test():
    print("🧪 빠른 테스트 시작...")
    
    summary = await generate_optimized_summary(
        content=test_content,
        content_type="ticket",
        subject="마크애니 MX레크드관련",
        metadata={"priority": "high"},
        ui_language="ko"
    )
    
    print("📝 생성된 요약:")
    print("=" * 60)
    print(summary)
    print("=" * 60)
    
    # 핵심 키워드 체크
    keywords = ["마크애니", "MarkAny", "MX레코드", "Postini", "Google Apps", "2015", "이대영", "위두소프트", "markany.com", "DNS"]
    found = [k for k in keywords if k in summary]
    missing = [k for k in keywords if k not in summary]
    
    print(f"\n✅ 포함된 키워드 ({len(found)}/{len(keywords)}): {found}")
    if missing:
        print(f"❌ 누락된 키워드: {missing}")
    else:
        print("🎉 모든 핵심 키워드 포함!")

if __name__ == "__main__":
    asyncio.run(test())
