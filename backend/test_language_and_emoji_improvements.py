#!/usr/bin/env python3
"""
언어 감지 및 첨부파일 이모지 개선사항 테스트 스크립트

개선사항:
1. 언어 감지 임계값 개선 (50자 → 30자)
2. 파일 타입별 다양한 이모지 적용

사용법:
    python test_language_and_emoji_improvements.py
"""

import asyncio
import sys
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent))

from core.llm.manager import LLMManager
from core.llm.summarizer.utils.language import detect_content_language

async def test_language_detection_improvement():
    """언어 감지 임계값 개선 테스트"""
    print("🌐 언어 감지 임계값 개선 테스트...")
    
    test_cases = [
        # 짧은 한국어 콘텐츠 (30-50자 사이)
        ("고객이 로그인 문제로 문의했습니다.", "ko", "한국어 (35자)"),
        ("시스템 오류 발생함", "ko", "한국어 (9자)"),
        ("Customer reported login issue", "en", "영어 (26자)"),
        ("ログインエラーが発生しました", "ja", "일본어 (13자)"),
        ("用户反馈登录问题", "zh", "중국어 (7자)"),
        # 경계 케이스
        ("아주 짧은 문의", "ko", "한국어 (7자)"),
        ("This is a slightly longer customer inquiry about system issues", "en", "영어 (62자)"),
    ]
    
    results = []
    for content, expected_lang, description in test_cases:
        # UI 언어는 한국어로 설정
        detected = detect_content_language(content, ui_language="ko")
        
        content_length = len(content)
        is_correct = detected == expected_lang
        
        # 30자 미만은 UI 언어(ko) 적용, 30자 이상은 내용 기반 감지
        if content_length < 30:
            expected_behavior = "ko"  # UI 언어 적용
            behavior_correct = detected == "ko"
        else:
            expected_behavior = expected_lang  # 내용 기반 감지
            behavior_correct = detected == expected_lang
        
        status = "✅" if behavior_correct else "❌"
        print(f"  {status} {description}: '{content[:20]}...' → {detected} (기대: {expected_behavior})")
        
        results.append(behavior_correct)
    
    success_rate = sum(results) / len(results) * 100
    print(f"\n언어 감지 정확도: {success_rate:.1f}% ({sum(results)}/{len(results)})")
    
    return success_rate > 80

async def test_file_emoji_improvements():
    """파일 타입별 이모지 개선 테스트"""
    print("\n🎨 파일 타입별 이모지 개선 테스트...")
    
    manager = LLMManager()
    
    test_files = [
        # 이미지 파일
        ("screenshot.png", "image/png", "🖼️"),
        ("animation.gif", "image/gif", "🎞️"),
        ("photo.jpg", "image/jpeg", "🖼️"),
        
        # 문서 파일
        ("report.pdf", "application/pdf", "📕"),
        ("document.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "📝"),
        ("spreadsheet.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "📊"),
        ("presentation.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "📺"),
        
        # 로그/텍스트 파일
        ("error.log", "text/plain", "📋"),
        ("readme.txt", "text/plain", "📄"),
        
        # 압축 파일
        ("backup.zip", "application/zip", "🗜️"),
        ("archive.tar.gz", "application/x-tar", "🗜️"),
        
        # 데이터 파일
        ("config.json", "application/json", "🗄️"),
        ("data.xml", "application/xml", "🗄️"),
        ("settings.yaml", "text/yaml", "🗄️"),
        
        # 미디어 파일
        ("music.mp3", "audio/mpeg", "🎵"),
        ("video.mp4", "video/mp4", "🎬"),
        
        # 기본값
        ("unknown.xyz", "", "📎"),
    ]
    
    results = []
    for filename, content_type, expected_emoji in test_files:
        actual_emoji = manager._get_file_emoji(filename, content_type)
        is_correct = actual_emoji == expected_emoji
        
        status = "✅" if is_correct else "❌"
        print(f"  {status} {filename} ({content_type}) → {actual_emoji} (기대: {expected_emoji})")
        
        results.append(is_correct)
    
    success_rate = sum(results) / len(results) * 100
    print(f"\n이모지 매핑 정확도: {success_rate:.1f}% ({sum(results)}/{len(results)})")
    
    return success_rate > 90

async def test_attachment_summary_integration():
    """첨부파일 요약 통합 테스트"""
    print("\n📎 첨부파일 요약 통합 테스트...")
    
    manager = LLMManager()
    
    # 샘플 첨부파일 데이터
    sample_attachments = [
        {
            "name": "error_log.txt",
            "size": 1024 * 50,  # 50KB
            "content_type": "text/plain"
        },
        {
            "name": "screenshot.png", 
            "size": 1024 * 300,  # 300KB
            "content_type": "image/png"
        },
        {
            "name": "config.json",
            "size": 1024 * 5,  # 5KB
            "content_type": "application/json"
        }
    ]
    
    # 메타데이터 가공 로직 시뮬레이션
    attachment_summary = []
    for attachment in sample_attachments:
        name = attachment.get("name", "unknown")
        size = attachment.get("size", 0)
        content_type = attachment.get("content_type", "")
        
        # 개선된 이모지 선택
        emoji = manager._get_file_emoji(name, content_type)
        
        if size > 0:
            size_mb = round(size / (1024*1024), 2)
            if size_mb > 0:
                attachment_summary.append(f"{emoji} {name} ({size_mb}MB)")
            else:
                size_kb = round(size / 1024, 0)
                attachment_summary.append(f"{emoji} {name} ({size_kb}KB)")
        else:
            attachment_summary.append(f"{emoji} {name}")
    
    final_summary = " | ".join(attachment_summary)
    
    print("생성된 첨부파일 요약:")
    print(f"  {final_summary}")
    
    # 기대되는 결과 확인
    expected_elements = ["📋", "🖼️", "🗄️"]  # 각 파일 타입별 이모지
    all_present = all(emoji in final_summary for emoji in expected_elements)
    
    print(f"\n예상 이모지 포함 여부: {'✅' if all_present else '❌'}")
    print(f"  📋 로그파일: {'✅' if '📋' in final_summary else '❌'}")
    print(f"  🖼️ 이미지: {'✅' if '🖼️' in final_summary else '❌'}")
    print(f"  🗄️ JSON: {'✅' if '🗄️' in final_summary else '❌'}")
    
    return all_present

async def test_short_content_language_priority():
    """짧은 콘텐츠에서 UI 언어 우선순위 테스트"""
    print("\n🔤 짧은 콘텐츠 UI 언어 우선순위 테스트...")
    
    # 30자 미만의 다양한 언어 콘텐츠
    short_contents = [
        "Hello support",  # 영어, 13자
        "こんにちは",      # 일본어, 5자
        "问题解决",        # 중국어, 4자
        "문의사항",        # 한국어, 4자
    ]
    
    ui_languages = ["ko", "en", "ja"]
    
    results = []
    for ui_lang in ui_languages:
        print(f"\n  UI 언어: {ui_lang}")
        for content in short_contents:
            detected = detect_content_language(content, ui_language=ui_lang)
            is_ui_lang = detected == ui_lang
            
            status = "✅" if is_ui_lang else "❌"
            print(f"    {status} '{content}' → {detected} (기대: {ui_lang})")
            results.append(is_ui_lang)
    
    success_rate = sum(results) / len(results) * 100
    print(f"\nUI 언어 우선 적용률: {success_rate:.1f}% ({sum(results)}/{len(results)})")
    
    return success_rate > 95

async def main():
    """메인 테스트 실행"""
    print("🚀 언어 감지 및 첨부파일 이모지 개선사항 테스트 시작\n")
    
    results = []
    
    # 1. 언어 감지 개선 테스트
    results.append(await test_language_detection_improvement())
    
    # 2. 파일 이모지 개선 테스트
    results.append(await test_file_emoji_improvements())
    
    # 3. 첨부파일 요약 통합 테스트
    results.append(await test_attachment_summary_integration())
    
    # 4. 짧은 콘텐츠 UI 언어 우선순위 테스트
    results.append(await test_short_content_language_priority())
    
    # 결과 요약
    print("\n" + "="*60)
    print("📊 테스트 결과 요약")
    print("="*60)
    
    test_names = [
        "언어 감지 임계값 개선",
        "파일 타입별 이모지 매핑",
        "첨부파일 요약 통합",
        "짧은 콘텐츠 UI 언어 우선순위"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ 성공" if result else "❌ 실패"
        print(f"{i+1}. {name}: {status}")
    
    success_rate = sum(results) / len(results) * 100
    print(f"\n전체 성공률: {success_rate:.1f}% ({sum(results)}/{len(results)})")
    
    if all(results):
        print("\n🎉 모든 테스트가 성공했습니다!")
        print("\n개선된 기능:")
        print("  ✅ 언어 감지 임계값이 50자에서 30자로 개선되었습니다")
        print("  ✅ 파일 타입별 다양하고 이쁜 이모지가 적용됩니다")
        print("  ✅ UI 언어와 본문 언어가 올바르게 분리 처리됩니다")
        print("  ✅ 첨부파일 정보가 더 직관적으로 표시됩니다")
    else:
        print("\n⚠️  일부 테스트에서 문제가 발견되었습니다.")
        print("상세한 내용을 확인하고 추가 수정이 필요할 수 있습니다.")

if __name__ == "__main__":
    asyncio.run(main())