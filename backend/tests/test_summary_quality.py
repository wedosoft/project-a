#!/usr/bin/env python3
"""
요약 품질 테스트 스크립트
현재 최적화된 요약기가 제대로 작동하는지 확인
"""

import asyncio
import os
import sys

# 프로젝트 루트를 Python 패스에 추가
sys.path.insert(0, '/Users/alan/GitHub/project-a/backend')

from core.llm.optimized_summarizer import generate_optimized_summary

# 테스트용 실제 티켓 내용 (현재 파일의 마크애니 MX 레코드 관련 사례)
test_content = """
제목: 마크애니 MX레크드관련

설명: 마크애니입니다. MS레코드관련해서 다시 최종 메일 드립니다. 1. 일전에 위두측에서 저희 MS레크드 등록현황을 확인하였다시피 권고한 MS레코드가 등록 추가되었음을 확인하셨었습니다. 이는 이전에 안내된 그글쪽 안내 메일에따라 아래 레코드가 추가했었습니다. Priority Mail server 1 ASPMX.L.GOOGLE.COM . 5 ALT1.ASPMX.L.GOOGLE.COM . 5 ALT2.ASPMX.L.GOOGLE.COM . 10 ALT3.ASPMX.L.GOOGLE.COM . 10 ALT4.ASPMX.L.GOOGLE.COM . 그런데 아래 Procedure가 안내되던데요. 이건 뭔가요. 아래 절차에다라 MX레코드를 수정하라는것 같은데요. 뭐가 뭔지 모르겠습니다. 저희 DNS에 위 레코드를 추가등록하기만 하면되는줄알았는데 또 뭘 수정하라는건지..... 확인하여주시고, 그에따른 조치 부탁드리겠습니다. 갈수록 구글 메일 쓰시가 어려워집니다. To modify your MX records with GoDaddy, do the following: 1. Log in to your account at www.godaddy.com. 2. Open the Domains tab and select My Domain Names. You'll be directed to the Manage Domains page. 3. Click the domain that you'd like to use. 4. Click the Total DNS Control And MX Records in the box entitled Total DNS Control. 5. Clear all existing MX Records by clicking Delete. 6. Click OK in the confirmation dialogue box. 7. Once you've deleted all existing records, click Add New MX Record. The MX (Mail Exchangers) Record Wizard will appear. 8. For each MX Record, enter the following information: For the Select the Priority Value drop-down menu, enter the priority value. For Enter a Host Name, leave the default setting to @. For the Select TTL Value drop-down menu, the default Time to Live (TTL) value may be set to 1 Week. This will appear as 604800 seconds within the DNS system. This means that it will require one week for your MX records to propagate. For future updates to your records, we suggest you enter a shorter time span for the TTL, such as 1 day or 1 hour. For Enter Goes To Address, enter the following MX records, including the trailing dots at the end of each record. Be sure to enter your actual domain name -- for example, solarmora.com -- for yourdomain : <yourdomain>.s <your system number> a1.psmtp.com . <yourdomain>.s <your system number> a2.psmtp.com . <yourdomain>.s <your system number> b1.psmtp.com . <yourdomain>.s <your system number> b2.psmtp.com . For additional instructions on changing your MX records, see Tips for Changing Your MX Records with GoDaddy . 9. Click Continue. 10. Click Add to confirm each entry. The DNS Manager main page will reappear when you've finished. Keep in mind that changes to MX records will take time to propagate throughout the Internet. The length of time depends on the Time to Live (TTL) for your domain. When you are finished switching your MX records to the message security service, go to Test Your MX Records .

대화: 추가적으로 아래 링크상 내용들이 너무 복잡하고 어렵습니다. http://www.google.com/support/enterprise/static/postini/docs/admin/en/activate/mx_switch.html

대화: 티켓 195 에서 병합됨 제목: Fwd: (매우중요) Fwd: ACTION REQUIRED to prevent permanent loss of email 설명: MX레코드관련하여 내용이 좀다른내용의 메일입니다. 첨부된 메일 참조 부탁드립니다. 아래 첫머리 부분입니다. 무슨 말인지 모르겠습니다. MX레코드관련 조치를 하지않으면 인바운드 메일이 작동죄지않을꺼라는건데요. 이전 MX레코드관련 내용과는 또다른 내용이네요. Dear Postini Customer, In September, 2015, Google will no longer support DNS redirection of MX records from Postini to Google Apps. If you do not take action, your inbound mailflow will fail on or after that date. 금일 먼저 문의드린 내용의 원 내용입니다.

대화: From: The Postini / Google Apps Transition Team < apps-noreply@google.com > Date: 2015-06-24 6:19 GMT+09:00 Subject: ACTION REQUIRED to prevent permanent loss of email To: admin@markany.com Dear Postini Customer, In September, 2015, Google will no longer support DNS redirection of MX records from Postini to Google Apps. If you do not take action, your inbound mailflow will fail on or after that date. The MX records for the following domains currently point to Postini: markany.com These domains currently rely on DNS redirection to send your traffic to Google Apps. If you do not change your MX records to point to Google Apps, you will not receive any inbound mail for these domains.

대화: 안녕하세요 이대영 차장 님, 위두소프트 고객 지원팀입니다. 문의하신 내용 관련하여 이전까지 저희가 안내드렸던 내용이 맞다고 보입니다만, 이와 관련하여 포스티니 고객센터로 컨펌을 위한 문의를 진행하고 있습니다. 곧 다시 답신 드리겠습니다. 감사합니다.

대화: 구글로부터 수시로 전달되는 포스트니 서비스 중단 및 MX레코드 변경 수정 관련 안내 건에 대한 사항들에 현재 저희 MX레코드 상태가 문제는 없는건지 확인 부탁드립니다. 그간 메시지들을 대충보니, MX레코드변경하라는 내용은 기본적으로 동일하지만 서비스 중단 기간도 조금씩 다다르고, 실제 첨부된 링크들을 들어가보면 메시지마다 조금씩 다른것 같습니다.

대화: 안녕하세요 이대영 차장 님, 위두소프트 고객 지원팀입니다. 저희가 확인한 내용을 아래와 같이 안내드리겠습니다. 1. 포스티니 서비스 전환의 배경 - 구글은 2007년 포스티니를 인수하여 메시지 아카이빙과 보안 관련 서비스를 제공해옴. - 구글앱스의 성공적 런칭과 함께 포스티니와 중복 서비스가 발생하게됨. - 이에 단게적으로 포스티니 서비스 기능을 구글앱스 관리자 모듈에 통합작업을 진행해 옴. - 이에 메시지 필터링 등의 스팸 기능은 이미 구글앱스 관리자 기능에 내장 되었으며 아카이빙은 Google Vault로 대체됨. - 통합 작업이 막바자에 이르게 되자 포스티니 서비스를 종료할 준비를 함. - 기존 포스티니 서비스 고객은 약간의 절차를 거쳐 타 서비스로 이전을 해야하는 상황에 처함. 하지만 구글 앱스와 함께 사용하는 고객의 경우 구글앱스로 대부분 대체가 되기에 전환에 큰 어려움은 없을 것임.

대화: 마크애니입니다. 내용전달이 충분히 되었습니다. 1. 메일 필터링과 스팸기능이 기존에 포스트니 서비스를 통해 서비스가 되었다고 했는데요. 그렇다면 기존MX레코드를 삭제하여 포스트니가 작동하지않으면 기존 설정한 필터링 기능들은 그대로 서비스가 유지되는건가요? 2. 권장안에서 다음 내용은 어떻게 처리하는것인지요. 메일 환경설정에서 MX레코드를 포스티니를 제거하고 구글 설정으로 전환하기를 바란다 -->개인별로 처리해야는건지 아니면 관리자 페이지에서 진행을 하는것인지..... MX레코드를 포스트니를 제거하라는 말이 이해가 가지않습니다. DNS로부터 기존 MX레코드를 삭제하고, 관리자 페이지에서 포스트니 서비스를 사용하지않음으로 바꾸라는건가요? 3. 기존 MX레코드를 DNS에서 삭제함으로써 즉시 발생할수있는 Side Impact는 뭔지요. 사전에 어떤 작업들이 되어야하는지.......권고된 새로운 MX레코드는 기존 레코드를 유지한채 추가 등록만 되있는 상태인데요. 기존 MX레코드를 바로 삭제 해도 현재 서비스에 별다른 영향은 없을지요.

연락처: MarkAny Inc. 이대영 차장 Lee, Dae-Young 경영지원실/법무팀 / IT,구매담당 Office: 02-2262-5265, Mobile 010-2738-9311 Fax: 822-2262-5333 Email: dylee@markany.com 우100-400, 서울특별시 중구 퇴계로 286 (쌍림동) 쌍림빌딩 10층
"""

async def test_summary_quality():
    """요약 품질 테스트"""
    print("🧪 요약 품질 테스트 시작...")
    print("=" * 80)
    
    try:
        # 최적화된 요약 생성
        summary = await generate_optimized_summary(
            content=test_content,
            content_type="ticket",
            subject="마크애니 MX레크드관련",
            metadata={"priority": "high", "status": "ongoing"},
            ui_language="ko"
        )
        
        print("📝 생성된 요약:")
        print("-" * 40)
        print(summary)
        print("-" * 40)
        
        # 품질 분석
        print("\n🔍 품질 분석:")
        sections = ['🔍', '🎯', '🔧', '💡']
        missing_sections = [s for s in sections if s not in summary]
        
        print(f"✅ 총 길이: {len(summary)}자")
        print(f"✅ 섹션 개수: {len(sections) - len(missing_sections)}/4")
        if missing_sections:
            print(f"❌ 누락 섹션: {missing_sections}")
        
        # 중요 정보 포함 확인
        key_info = [
            "마크애니", "이대영", "MX레코드", "Postini", "Google Apps", 
            "2015년 9월", "DNS redirection", "인바운드 메일", "위두소프트", "markany.com"
        ]
        
        included_info = [info for info in key_info if info in summary]
        print(f"✅ 핵심 정보 포함: {len(included_info)}/{len(key_info)}")
        print(f"   포함된 정보: {included_info}")
        
        missing_info = [info for info in key_info if info not in summary]
        if missing_info:
            print(f"❌ 누락된 정보: {missing_info}")
            
        print("\n" + "=" * 80)
        print("🎯 테스트 완료!")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_summary_quality())
