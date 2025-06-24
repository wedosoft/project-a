#!/usr/bin/env python3
"""
대용량 요약 처리 테스트 스크립트

이 스크립트는 대용량 데이터셋에서 요약 품질과 성능을 테스트합니다.
단계별로 규모를 늘려가며 시스템의 확장성을 검증합니다.
"""

import asyncio
import logging
import time
import json
from pathlib import Path
from typing import Dict, Any, List
import sqlite3

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 프로젝트 루트 경로 설정
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.llm.summarizer import generate_summary, enable_large_scale_processing, disable_large_scale_processing
from backend.core.llm.scalable_summarizer import ScalableSummarizer, ScalabilityConfig, process_million_scale_dataset


class SummaryQualityTester:
    """요약 품질 테스터"""
    
    def __init__(self):
        self.quality_criteria = {
            'min_length': 100,
            'max_length': 2000,
            'required_sections': [
                '문제 상황', '근본 원인', '해결 과정', '핵심 포인트'
            ],
            'required_emojis': ['🔍', '🎯', '🔧', '💡']
        }
    
    def evaluate_summary_quality(self, summary: str, original_content: str) -> Dict[str, Any]:
        """요약 품질 평가"""
        
        evaluation = {
            'overall_score': 0.0,
            'length_score': 0.0,
            'structure_score': 0.0,
            'content_score': 0.0,
            'language_score': 0.0,
            'issues': [],
            'details': {}
        }
        
        # 1. 길이 평가
        length = len(summary.strip())
        evaluation['details']['length'] = length
        
        if self.quality_criteria['min_length'] <= length <= self.quality_criteria['max_length']:
            evaluation['length_score'] = 1.0
        elif length < self.quality_criteria['min_length']:
            evaluation['length_score'] = length / self.quality_criteria['min_length']
            evaluation['issues'].append(f"너무 짧음 ({length}자)")
        else:
            excess = length - self.quality_criteria['max_length']
            evaluation['length_score'] = max(0.5, 1.0 - (excess / 1000))
            evaluation['issues'].append(f"너무 김 ({length}자)")
        
        # 2. 구조 평가
        found_sections = []
        for section in self.quality_criteria['required_sections']:
            if section in summary:
                found_sections.append(section)
        
        evaluation['structure_score'] = len(found_sections) / len(self.quality_criteria['required_sections'])
        evaluation['details']['found_sections'] = found_sections
        
        if evaluation['structure_score'] < 1.0:
            missing = set(self.quality_criteria['required_sections']) - set(found_sections)
            evaluation['issues'].append(f"누락된 섹션: {missing}")
        
        # 3. 이모지 확인
        found_emojis = [emoji for emoji in self.quality_criteria['required_emojis'] if emoji in summary]
        emoji_score = len(found_emojis) / len(self.quality_criteria['required_emojis'])
        evaluation['details']['found_emojis'] = found_emojis
        
        # 4. 내용 충실도 (간단한 키워드 기반)
        original_words = set(original_content.lower().split())
        summary_words = set(summary.lower().split())
        
        if original_words:
            common_words = original_words.intersection(summary_words)
            evaluation['content_score'] = min(len(common_words) / len(original_words) * 2, 1.0)
        else:
            evaluation['content_score'] = 0.0
        
        # 5. 언어 품질 (에러 메시지 확인)
        evaluation['language_score'] = 1.0
        error_indicators = ['[처리 실패]', 'Error', '오류', 'failed', '실패']
        if any(indicator in summary for indicator in error_indicators):
            evaluation['language_score'] = 0.0
            evaluation['issues'].append("에러 메시지 포함")
        
        # 전체 점수 계산
        evaluation['overall_score'] = (
            evaluation['length_score'] * 0.2 +
            evaluation['structure_score'] * 0.3 +
            evaluation['content_score'] * 0.3 +
            evaluation['language_score'] * 0.2
        )
        
        return evaluation


class PerformanceTester:
    """성능 테스터"""
    
    def __init__(self):
        self.test_sizes = [10, 50, 100, 500, 1000]  # 테스트 규모
        self.results = []
    
    async def run_scalability_tests(self, db_path: str) -> List[Dict[str, Any]]:
        """확장성 테스트 실행"""
        
        logger.info("=== 확장성 테스트 시작 ===")
        
        for test_size in self.test_sizes:
            logger.info(f"\n--- {test_size}건 규모 테스트 시작 ---")
            
            try:
                test_result = await self._run_single_scale_test(db_path, test_size)
                self.results.append(test_result)
                
                logger.info(f"✅ {test_size}건 테스트 완료: "
                          f"성공률 {test_result['success_rate']:.1f}%, "
                          f"평균 품질 {test_result['average_quality']:.3f}, "
                          f"처리량 {test_result['throughput']:.1f}/min")
                
                # 실패율이 너무 높으면 중단
                if test_result['success_rate'] < 70.0:
                    logger.warning(f"실패율이 높아 테스트 중단: {test_result['success_rate']:.1f}%")
                    break
                    
            except Exception as e:
                logger.error(f"❌ {test_size}건 테스트 실패: {e}")
                self.results.append({
                    'test_size': test_size,
                    'success': False,
                    'error': str(e)
                })
                break
        
        return self.results
    
    async def _run_single_scale_test(self, db_path: str, test_size: int) -> Dict[str, Any]:
        """단일 규모 테스트"""
        
        # 대용량 모드 활성화
        if test_size >= 100:
            enable_large_scale_processing(test_size)
        
        try:
            # 테스트 데이터 추출
            test_data = self._extract_test_data(db_path, test_size)
            
            # 성능 측정 시작
            start_time = time.time()
            
            # 요약 생성
            results = []
            quality_tester = SummaryQualityTester()
            
            successful = 0
            failed = 0
            total_quality = 0.0
            
            for i, item in enumerate(test_data):
                try:
                    summary = await generate_summary(
                        content=item['content'],
                        content_type='ticket',
                        subject=item['subject'],
                        ui_language='ko'
                    )
                    
                    # 품질 평가
                    quality_eval = quality_tester.evaluate_summary_quality(
                        summary, item['content']
                    )
                    
                    results.append({
                        'id': item['id'],
                        'summary': summary,
                        'quality_evaluation': quality_eval
                    })
                    
                    successful += 1
                    total_quality += quality_eval['overall_score']
                    
                    # 진행 상황 로그 (큰 테스트에서만)
                    if test_size >= 100 and (i + 1) % 50 == 0:
                        logger.info(f"  진행률: {i + 1}/{test_size} ({((i + 1)/test_size)*100:.1f}%)")
                    
                except Exception as e:
                    logger.error(f"아이템 {item['id']} 처리 실패: {e}")
                    failed += 1
            
            # 성능 측정 완료
            end_time = time.time()
            total_time = end_time - start_time
            
            # 결과 계산
            success_rate = (successful / len(test_data)) * 100 if test_data else 0
            average_quality = total_quality / successful if successful > 0 else 0
            throughput = (successful / total_time) * 60 if total_time > 0 else 0  # 분당 처리량
            
            return {
                'test_size': test_size,
                'success': True,
                'total_time': total_time,
                'successful': successful,
                'failed': failed,
                'success_rate': success_rate,
                'average_quality': average_quality,
                'throughput': throughput,
                'sample_results': results[:3]  # 샘플 결과 3개만
            }
            
        finally:
            # 대용량 모드 비활성화
            disable_large_scale_processing()
    
    def _extract_test_data(self, db_path: str, limit: int) -> List[Dict[str, Any]]:
        """테스트 데이터 추출"""
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # 무작위 샘플링으로 다양한 데이터 확보
            cursor.execute("""
            SELECT id, subject, description_text,
                   GROUP_CONCAT(c.body_text, '\n---\n') as conversations
            FROM tickets t
            LEFT JOIN conversations c ON t.id = c.ticket_id
            WHERE t.description_text IS NOT NULL
            AND LENGTH(t.description_text) > 50
            GROUP BY t.id, t.subject, t.description_text
            ORDER BY RANDOM()
            LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            
            test_data = []
            for row in rows:
                ticket_id, subject, description, conversations = row
                
                # 전체 내용 구성
                content = description or ""
                if conversations:
                    content += f"\n\n=== 대화 내용 ===\n{conversations}"
                
                test_data.append({
                    'id': str(ticket_id),
                    'subject': subject or "",
                    'content': content
                })
            
            return test_data
            
        finally:
            conn.close()


async def run_comprehensive_tests(db_path: str, output_dir: str):
    """종합 테스트 실행"""
    
    logger.info("🚀 대용량 요약 처리 종합 테스트 시작")
    
    # 출력 디렉토리 생성
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 1. 확장성 테스트
    performance_tester = PerformanceTester()
    scale_results = await performance_tester.run_scalability_tests(db_path)
    
    # 2. 결과 저장
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    # 확장성 테스트 결과
    scale_output = output_path / f"scalability_test_{timestamp}.json"
    with open(scale_output, 'w', encoding='utf-8') as f:
        json.dump({
            'test_type': 'scalability_test',
            'timestamp': timestamp,
            'results': scale_results
        }, f, ensure_ascii=False, indent=2)
    
    # 3. 요약 리포트 생성
    report = _generate_test_report(scale_results)
    
    report_output = output_path / f"test_report_{timestamp}.md"
    with open(report_output, 'w', encoding='utf-8') as f:
        f.write(report)
    
    logger.info(f"✅ 테스트 완료: {scale_output}, {report_output}")
    
    return scale_results


def _generate_test_report(scale_results: List[Dict[str, Any]]) -> str:
    """테스트 리포트 생성"""
    
    report = """# 🎯 대용량 요약 처리 테스트 리포트

## 📊 확장성 테스트 결과

| 규모 | 성공률 | 평균 품질 | 처리량 (건/분) | 총 시간 (초) |
|------|--------|-----------|----------------|--------------|
"""
    
    for result in scale_results:
        if result.get('success', False):
            report += f"| {result['test_size']} | {result['success_rate']:.1f}% | {result['average_quality']:.3f} | {result['throughput']:.1f} | {result['total_time']:.1f} |\n"
        else:
            report += f"| {result['test_size']} | ❌ 실패 | - | - | - |\n"
    
    # 성능 분석
    successful_results = [r for r in scale_results if r.get('success', False)]
    
    if successful_results:
        max_scale = max(r['test_size'] for r in successful_results)
        best_quality = max(r['average_quality'] for r in successful_results)
        best_throughput = max(r['throughput'] for r in successful_results)
        
        report += f"""
## 🔍 성능 분석

- **최대 처리 규모**: {max_scale}건
- **최고 품질 점수**: {best_quality:.3f}
- **최고 처리량**: {best_throughput:.1f}건/분

## 💡 결론

"""
        
        if max_scale >= 1000:
            report += "✅ **대용량 처리 가능**: 1000건 이상 규모에서도 안정적 처리\n"
        elif max_scale >= 100:
            report += "⚠️ **중규모 처리 가능**: 100-999건 규모에서 안정적, 대용량은 최적화 필요\n"
        else:
            report += "❌ **소규모만 처리 가능**: 100건 미만에서만 안정적, 확장성 개선 필요\n"
        
        if best_quality >= 0.9:
            report += "✅ **고품질 유지**: 품질 점수 0.9 이상 달성\n"
        elif best_quality >= 0.8:
            report += "⚠️ **적정 품질**: 품질 점수 0.8 이상, 개선 여지 있음\n"
        else:
            report += "❌ **품질 개선 필요**: 품질 점수 0.8 미만, 프롬프트 및 로직 개선 필요\n"
    
    else:
        report += """
## ❌ 테스트 실패

모든 규모에서 테스트가 실패했습니다. 시스템 설정을 점검해주세요.
"""
    
    return report


async def main():
    """메인 실행 함수"""
    
    # 데이터베이스 경로 (실제 경로로 변경 필요)
    db_path = "backend/core/data/wedosoft_freshdesk_data_simplified.db"
    output_dir = "test_results/summary_scaling"
    
    # 데이터베이스 존재 확인
    if not Path(db_path).exists():
        logger.error(f"데이터베이스 파일이 없습니다: {db_path}")
        logger.info("데이터 수집을 먼저 실행해주세요.")
        return
    
    try:
        # 종합 테스트 실행
        results = await run_comprehensive_tests(db_path, output_dir)
        
        # 간단한 요약 출력
        logger.info("\n" + "="*50)
        logger.info("🎯 테스트 요약")
        logger.info("="*50)
        
        for result in results:
            if result.get('success', False):
                logger.info(f"📊 {result['test_size']:>4}건: "
                          f"성공률 {result['success_rate']:>5.1f}%, "
                          f"품질 {result['average_quality']:.3f}, "
                          f"처리량 {result['throughput']:>5.1f}/min")
            else:
                logger.info(f"❌ {result['test_size']:>4}건: 실패")
        
    except Exception as e:
        logger.error(f"테스트 실행 중 오류: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
