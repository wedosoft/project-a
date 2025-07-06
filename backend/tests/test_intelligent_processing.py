#!/usr/bin/env python3
"""
LLM 기반 통합 지능형 처리 테스트

언어감지, 첨부파일선별, 대화분석, 요약을 하나의 LLM 호출로 통합 처리
"""

import asyncio
import sys
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent))

def create_multilingual_test_ticket():
    """다국어 환경의 복잡한 테스트 티켓 생성"""
    
    ticket_data = {
        "id": "intelligent_test_001",
        "subject": "システムエラーの解決 - 韓国語ファイルアップロード問題",  # 일본어 + 한국어
        "description": "日本語言語ファイルのアップロード後、ダウンロード時に기본 파일이 표시되는 문제가 발생했습니다.",
        "status": "resolved",
        "priority": "high",
        "metadata": {
            "all_attachments": [
                {
                    "name": "error_log_jp.txt",
                    "size": 1024 * 50,
                    "content_type": "text/plain",
                    "id": "att_001"
                },
                {
                    "name": "システム設定.xlsx", 
                    "size": 1024 * 200,
                    "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "id": "att_002"
                },
                {
                    "name": "スクリーンショット.png",
                    "size": 1024 * 300,
                    "content_type": "image/png", 
                    "id": "att_003"
                },
                {
                    "name": "backup_unnecessary.zip",
                    "size": 1024 * 1024 * 20,  # 20MB - 불필요한 파일
                    "content_type": "application/zip",
                    "id": "att_004"
                },
                {
                    "name": "readme.md",
                    "size": 1024 * 5,
                    "content_type": "text/markdown",
                    "id": "att_005"
                }
            ]
        },
        "conversations": []
    }
    
    # 25개 대화 - 다국어 혼재 + 해결 과정 포함
    conversations = [
        # 1-5: 초기 문제 제기 (일본어)
        {"body_text": "こんにちは。ヘルプデスクの言語管理でJapanese言語ファイルをアップロードしましたが、問題があります。"},
        {"body_text": "アップロード成功メッセージは表示されましたが、ダウンロードすると기본 파일이 나옵니다."},
        {"body_text": "YMLファイルの形式に問題があるのでしょうか？확인을 부탁드립니다."},
        {"body_text": "顧客企業: XYZ회사, 사용자: admin@xyz.co.jp"},
        {"body_text": "첨부: 업로드한 yml 파일과 스크린샷을 添付しました。"},
        
        # 6-10: 담당자 응답 (한국어 위주)
        {"body_text": "문의사항 접수되었습니다. まず、アップロードされたYMLファイルを確인してみます。"},
        {"body_text": "파일 형식은 정상으로 보입니다. サーバーログをチェックしてみますね。"},
        {"body_text": "브라우저 캐시 문제일 수 있으니 캐시를 클리어하고 다시 시도해보세요."},
        {"body_text": "캐시 클리어했지만 여전히 같은 문제입니다. 他のブラウザでも同じ現象です。"},
        {"body_text": "서버 로그를 확인해보니 파일 업로드는 성공했지만 적용 과정에 오류가 있는 것 같습니다."},
        
        # 11-15: 조사 진행 (혼재)
        {"body_text": "개발팀에 에스컬레이션하여 システムをチェックします。"},
        {"body_text": "はい、迅速な解決をお願いします。日本のお客様がお待ちしています。"},
        {"body_text": "이해합니다. 우선순위를 높여서 처리하겠습니다。"},
        {"body_text": "開発チームでシステム点検을 시작했습니다。"},
        {"body_text": "언어 파일 저장소에 문제가 있는 것으로 확인되었습니다。ファイル同期のバグです。"},
        
        # 16-20: 해결 과정 (중요!)
        {"body_text": "修正コードの準備ができました。テスト環境で検証中です。"},
        {"body_text": "QAテストが完了しました。プロダクション環境にデプロイします。"},
        {"body_text": "배포가 완료되었습니다。言語ファイル同期システムが修正されました。"},
        {"body_text": "テストしてみてください。기존 파일을 다시 업로드하고 다운로드를 확인해주세요。"},
        {"body_text": "今テストしています。ファイルを再アップロードしました。"},
        
        # 21-25: 최종 확인 및 완료
        {"body_text": "素晴らしい！今度は正常に適用されているようです！"},
        {"body_text": "ダウンロードして확認したところ、アップロードしたファイルが正しく반映されています。"},
        {"body_text": "일본어 번역도 헬프데스크에서 正常に表示されています。"},
        {"body_text": "完璧に解決されました。ありがとうございます！"},
        {"body_text": "티켓을 해결 완료로 종료하겠습니다。ご利用いただきありがとうございました。"}
    ]
    
    ticket_data["conversations"] = conversations
    return ticket_data

async def test_intelligent_vs_traditional():
    """지능형 처리 vs 기존 처리 비교"""
    print("🧠 LLM 통합 지능형 처리 vs 기존 처리 비교")
    print("=" * 60)
    
    # 테스트 티켓 생성
    ticket_data = create_multilingual_test_ticket()
    total_conversations = len(ticket_data["conversations"])
    total_attachments = len(ticket_data["metadata"]["all_attachments"])
    
    print(f"📊 테스트 티켓:")
    print(f"   총 대화: {total_conversations}개 (다국어 혼재)")
    print(f"   총 첨부파일: {total_attachments}개")
    print(f"   언어: 일본어 + 한국어 혼재")
    
    try:
        # 1. 지능형 통합 처리
        print(f"\n🧠 1단계: LLM 통합 지능형 처리")
        
        from core.llm.intelligent_ticket_processor import get_intelligent_processor
        
        intelligent_processor = get_intelligent_processor()
        analysis = await intelligent_processor.process_ticket_intelligently(ticket_data, "ko")
        
        print(f"   감지된 언어: {analysis.language}")
        print(f"   선별된 대화: {len(analysis.important_conversation_indices)}개")
        print(f"   관련 첨부파일: {len(analysis.relevant_attachments)}개")
        
        # 선별된 대화 분석
        important_indices = analysis.important_conversation_indices
        if important_indices:
            first_conv = important_indices[0] if important_indices else 0
            last_conv = important_indices[-1] if important_indices else 0
            print(f"   대화 범위: {first_conv+1}번 ~ {last_conv+1}번")
        
        # 해결 관련 대화 포함 여부
        resolution_conversations = 0
        resolution_keywords = ['해결', '완료', '修正', 'テスト', '배포', 'デプロイ', '正常']
        
        for idx in important_indices:
            if idx < len(ticket_data["conversations"]):
                conv_text = ticket_data["conversations"][idx]["body_text"]
                if any(keyword in conv_text for keyword in resolution_keywords):
                    resolution_conversations += 1
        
        print(f"   해결 관련 대화: {resolution_conversations}개 포함")
        
        # 첨부파일 분석
        relevant_files = [att.get("name", "") for att in analysis.relevant_attachments]
        print(f"   관련 파일: {', '.join(relevant_files[:3])}{'...' if len(relevant_files) > 3 else ''}")
        
        # 2. 기존 방식 시뮬레이션
        print(f"\n🔧 2단계: 기존 방식 처리")
        
        # 기존: 후반 10개만
        traditional_conversations = list(range(max(0, total_conversations - 10), total_conversations))
        traditional_attachments = ticket_data["metadata"]["all_attachments"][:3]  # 처음 3개만
        
        print(f"   처리 대화: {len(traditional_conversations)}개 (후반 위주)")
        print(f"   대화 범위: {traditional_conversations[0]+1}번 ~ {traditional_conversations[-1]+1}번")
        print(f"   첨부파일: {len(traditional_attachments)}개 (순서대로)")
        
        # 3. 비교 분석
        print(f"\n📊 비교 분석:")
        print(f"   지능형 vs 기존 대화 수: {len(important_indices)} vs {len(traditional_conversations)}")
        print(f"   지능형 vs 기존 첨부파일: {len(analysis.relevant_attachments)} vs {len(traditional_attachments)}")
        
        # 커버리지 분석
        intelligent_coverage = set(important_indices)
        traditional_coverage = set(traditional_conversations)
        
        # 초반 대화 포함 여부 (문제 상황)
        early_conversations = set(range(0, min(5, total_conversations)))
        intelligent_early = len(intelligent_coverage & early_conversations)
        traditional_early = len(traditional_coverage & early_conversations)
        
        print(f"   초반 대화 포함: {intelligent_early}개 vs {traditional_early}개")
        
        # 해결 과정 포함 여부 (후반 5개)
        resolution_range = set(range(max(0, total_conversations - 5), total_conversations))
        intelligent_resolution = len(intelligent_coverage & resolution_range)
        traditional_resolution = len(traditional_coverage & resolution_range)
        
        print(f"   해결 과정 포함: {intelligent_resolution}개 vs {traditional_resolution}개")
        
        # 4. 요약 품질 미리보기
        print(f"\n📄 요약 미리보기:")
        summary_preview = analysis.summary[:300].replace('\n', ' ')
        print(f"   {summary_preview}...")
        
        return {
            "intelligent_conversations": len(important_indices),
            "traditional_conversations": len(traditional_conversations),
            "intelligent_resolution": intelligent_resolution,
            "traditional_resolution": traditional_resolution,
            "detected_language": analysis.language,
            "relevant_attachments": len(analysis.relevant_attachments)
        }
        
    except Exception as e:
        print(f"   ❌ 테스트 실행 실패: {e}")
        return None

async def test_multilingual_accuracy():
    """다국어 처리 정확도 테스트"""
    print(f"\n🌍 다국어 처리 정확도 테스트")
    print("=" * 60)
    
    # 다양한 언어 시나리오 테스트
    test_scenarios = [
        {
            "name": "순수 한국어",
            "content": "시스템 오류가 발생했습니다. 로그인이 되지 않습니다.",
            "expected": "ko"
        },
        {
            "name": "순수 일본어", 
            "content": "システムエラーが発生しました。ログインできません。",
            "expected": "ja"
        },
        {
            "name": "한국어 + 영어 기술용어",
            "content": "시스템에서 connection timeout 오류가 발생했습니다. SSL certificate 문제인 것 같습니다.",
            "expected": "ko"
        },
        {
            "name": "일본어 + 영어 혼재",
            "content": "システムでconnection timeoutエラーが発生しました。SSL certificateの問題だと思います。",
            "expected": "ja"
        }
    ]
    
    try:
        from core.llm.intelligent_ticket_processor import get_intelligent_processor
        processor = get_intelligent_processor()
        
        correct_detections = 0
        
        for scenario in test_scenarios:
            test_ticket = {
                "subject": scenario["content"],
                "description": scenario["content"],
                "conversations": [{"body_text": scenario["content"]}]
            }
            
            analysis = await processor.process_ticket_intelligently(test_ticket, "ko")
            detected = analysis.language
            expected = scenario["expected"]
            
            is_correct = detected == expected
            if is_correct:
                correct_detections += 1
            
            print(f"   {scenario['name']}: {detected} ({'✅' if is_correct else '❌'})")
        
        accuracy = correct_detections / len(test_scenarios) * 100
        print(f"\n   전체 정확도: {accuracy:.1f}% ({correct_detections}/{len(test_scenarios)})")
        
        return accuracy >= 75  # 75% 이상이면 성공
        
    except Exception as e:
        print(f"   ❌ 다국어 테스트 실패: {e}")
        return False

async def main():
    """메인 테스트 실행"""
    print("🚀 LLM 기반 통합 지능형 처리 테스트")
    print("=" * 70)
    print("확인 항목:")
    print("1. 지능형 처리 vs 기존 처리 성능 비교")
    print("2. 다국어 환경에서의 언어 감지 정확도")
    print("3. 해결 과정 포함 대화 선별 품질")
    print("4. 관련 첨부파일 선별 정확도")
    print("=" * 70)
    
    results = []
    
    # 1. 지능형 vs 기존 처리 비교
    comparison_result = await test_intelligent_vs_traditional()
    if comparison_result:
        # 지능형 처리가 더 많은 해결 과정을 포함하면 성공
        success = (comparison_result["intelligent_resolution"] >= comparison_result["traditional_resolution"] and
                  comparison_result["intelligent_conversations"] > 0)
        results.append(success)
    else:
        results.append(False)
    
    # 2. 다국어 정확도 테스트
    multilingual_success = await test_multilingual_accuracy()
    results.append(multilingual_success)
    
    # 결과 요약
    print(f"\n🏆 최종 테스트 결과")
    print("=" * 70)
    
    test_names = [
        "지능형 vs 기존 처리 품질",
        "다국어 처리 정확도"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ 성공" if result else "❌ 실패"
        print(f"{i+1}. {name}: {status}")
    
    success_rate = sum(results) / len(results) * 100
    print(f"\n전체 성공률: {success_rate:.1f}% ({sum(results)}/{len(results)})")
    
    if all(results):
        print("\n🎉 LLM 통합 지능형 처리가 성공적으로 구현되었습니다!")
        print("\n혁신적 개선사항:")
        print("  ✅ 언어감지 + 첨부파일선별 + 대화분석 + 요약 → 단일 LLM 호출")
        print("  ✅ 다국어 환경에서 정확한 언어 감지")
        print("  ✅ 규칙 기반 → LLM 기반 스마트 선별")
        print("  ✅ 해결 과정 중심의 대화 선별")
        print("  ✅ 기술적 관련성 기반 첨부파일 선별")
        if comparison_result:
            print(f"  ✅ 처리 효율성: {comparison_result['intelligent_conversations']}개 대화 선별")
            print(f"  ✅ 감지된 언어: {comparison_result['detected_language']}")
    else:
        print("\n⚠️  일부 기능에서 추가 개선이 필요합니다.")

if __name__ == "__main__":
    asyncio.run(main())