"""
Anthropic 품질 검증기

Constitutional AI 원칙 준수, XML 구조 유효성, 팩트 정확성 등을 검증하여
Anthropic 프롬프트 엔지니어링 기법이 제대로 적용되었는지 확인합니다.
"""

import logging
import re
import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


class AnthropicQualityValidator:
    """Anthropic 프롬프트 엔지니어링 기법 품질 검증기"""
    
    def __init__(self):
        """품질 검증기 초기화"""
        self.validation_cache = {}
        self.metrics = {
            'total_validations': 0,
            'passed_validations': 0,
            'failed_validations': 0,
            'avg_quality_score': 0.0
        }
        
        # Constitutional AI 원칙별 가중치
        self.constitutional_weights = {
            'helpful': 0.35,      # 도움이 되는가?
            'harmless': 0.35,     # 해롭지 않은가?
            'honest': 0.30        # 정직한가?
        }
        
        # 품질 측정 가중치
        self.quality_weights = {
            'constitutional_compliance': 0.3,
            'xml_structure_validity': 0.2,
            'factual_accuracy': 0.2,
            'actionability': 0.15,
            'completeness': 0.15
        }
        
        logger.debug("AnthropicQualityValidator 초기화 완료")
    
    def calculate_anthropic_quality_score(self, 
                                        response: str, 
                                        validation_results: Dict[str, Any]) -> float:
        """
        Anthropic 기법 품질 점수 계산
        
        Args:
            response: 검증할 응답
            validation_results: 개별 검증 결과들
            
        Returns:
            float: 종합 품질 점수 (0.0 ~ 1.0)
        """
        try:
            self.metrics['total_validations'] += 1
            
            # 개별 점수들 추출
            constitutional_score = self._calculate_constitutional_score(validation_results)
            structure_score = float(validation_results.get('xml_structure_valid', False))
            factual_score = validation_results.get('factual_accuracy', 0.0)
            actionability_score = validation_results.get('actionability_score', 0.0)
            completeness_score = validation_results.get('information_completeness', 0.0)
            
            # 가중 평균 계산
            total_score = (
                constitutional_score * self.quality_weights['constitutional_compliance'] +
                structure_score * self.quality_weights['xml_structure_validity'] +
                factual_score * self.quality_weights['factual_accuracy'] +
                actionability_score * self.quality_weights['actionability'] +
                completeness_score * self.quality_weights['completeness']
            )
            
            # 메트릭 업데이트
            self._update_metrics(total_score)
            
            logger.debug(f"품질 점수 계산: 총점={total_score:.3f}, "
                        f"Constitutional={constitutional_score:.3f}, "
                        f"Structure={structure_score:.3f}, "
                        f"Factual={factual_score:.3f}")
            
            return round(total_score, 3)
            
        except Exception as e:
            logger.error(f"품질 점수 계산 실패: {e}")
            return 0.5  # 기본 점수
    
    def validate_constitutional_ai_compliance(self, 
                                            response: str,
                                            principles: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        Constitutional AI 원칙 준수 검증
        
        Args:
            response: 검증할 응답
            principles: Constitutional AI 원칙들
            
        Returns:
            Dict[str, Any]: 원칙별 준수 여부 및 점수
        """
        try:
            results = {
                'helpful': self._check_helpfulness(response, principles.get('helpful', [])),
                'harmless': self._check_harmlessness(response, principles.get('harmless', [])),
                'honest': self._check_honesty(response, principles.get('honest', [])),
                'overall_compliance': True,
                'compliance_score': 0.0,
                'violations': []
            }
            
            # 전체 준수 여부 및 점수 계산
            compliance_scores = []
            for principle, result in results.items():
                if principle in ['helpful', 'harmless', 'honest']:
                    if isinstance(result, dict):
                        score = result.get('score', 0.0)
                        compliance_scores.append(score)
                        if score < 0.7:  # 임계값 미달
                            results['overall_compliance'] = False
                            results['violations'].extend(result.get('violations', []))
            
            results['compliance_score'] = sum(compliance_scores) / len(compliance_scores) if compliance_scores else 0.0
            
            return results
            
        except Exception as e:
            logger.error(f"Constitutional AI 준수 검증 실패: {e}")
            return {
                'helpful': {'score': 0.5, 'violations': []},
                'harmless': {'score': 0.5, 'violations': []},
                'honest': {'score': 0.5, 'violations': []},
                'overall_compliance': False,
                'compliance_score': 0.5,
                'violations': ['검증 오류 발생']
            }
    
    def validate_xml_structure(self, 
                             response: str, 
                             required_sections: Dict[str, str]) -> Dict[str, Any]:
        """
        XML 구조 유효성 검증
        
        Args:
            response: 검증할 응답
            required_sections: 필수 섹션들 {tag: title}
            
        Returns:
            Dict[str, Any]: 구조 검증 결과
        """
        try:
            results = {
                'valid_structure': True,
                'found_sections': [],
                'missing_sections': [],
                'malformed_sections': [],
                'structure_score': 0.0
            }
            
            for section_tag, section_title in required_sections.items():
                open_tag = f"<{section_tag}>"
                close_tag = f"</{section_tag}>"
                
                if open_tag in response and close_tag in response:
                    # 섹션 존재 확인
                    results['found_sections'].append(section_tag)
                    
                    # 내용 추출 및 검증
                    try:
                        start_idx = response.find(open_tag) + len(open_tag)
                        end_idx = response.find(close_tag)
                        content = response[start_idx:end_idx].strip()
                        
                        if not content:
                            results['malformed_sections'].append(f"{section_tag}: 내용 없음")
                        elif len(content) < 10:
                            results['malformed_sections'].append(f"{section_tag}: 내용 부족")
                            
                    except Exception as e:
                        results['malformed_sections'].append(f"{section_tag}: 파싱 오류")
                        
                else:
                    results['missing_sections'].append(section_tag)
                    results['valid_structure'] = False
            
            # 구조 점수 계산
            total_sections = len(required_sections)
            found_sections = len(results['found_sections'])
            malformed_count = len(results['malformed_sections'])
            
            if total_sections > 0:
                structure_score = (found_sections - malformed_count * 0.5) / total_sections
                results['structure_score'] = max(0.0, min(1.0, structure_score))
            
            return results
            
        except Exception as e:
            logger.error(f"XML 구조 검증 실패: {e}")
            return {
                'valid_structure': False,
                'found_sections': [],
                'missing_sections': list(required_sections.keys()),
                'malformed_sections': [],
                'structure_score': 0.0
            }
    
    def validate_factual_accuracy(self, response: str, 
                                 source_content: Optional[str] = None) -> Dict[str, Any]:
        """
        팩트 정확성 검증
        
        Args:
            response: 검증할 응답
            source_content: 원본 내용 (있는 경우)
            
        Returns:
            Dict[str, Any]: 정확성 검증 결과
        """
        try:
            results = {
                'accuracy_score': 0.0,
                'fact_indicators': 0,
                'speculation_indicators': 0,
                'uncertainty_markers': 0,
                'technical_terms_preserved': True,
                'violations': []
            }
            
            # 팩트 지표 확인
            fact_patterns = [
                r'\b\d{4}-\d{2}-\d{2}\b',  # 날짜
                r'\b\d{1,2}:\d{2}\b',      # 시간
                r'\b\d+\.\d+\b',           # 버전 번호
                r'\b[A-Z]+\d+\b',          # 에러 코드
                r'\b\d+%\b',               # 퍼센트
                r'\b\d+[KMGT]?B\b',        # 파일 크기
            ]
            
            for pattern in fact_patterns:
                results['fact_indicators'] += len(re.findall(pattern, response))
            
            # 추측성 표현 확인
            speculation_patterns = [
                r'\b(아마도|아마|추측|것 같|것으로 보임|듯함)\b',
                r'\b(maybe|probably|perhaps|seems like|appears to)\b'
            ]
            
            for pattern in speculation_patterns:
                matches = re.findall(pattern, response, re.IGNORECASE)
                results['speculation_indicators'] += len(matches)
                if matches:
                    results['violations'].extend([f"추측성 표현: {match}" for match in matches])
            
            # 불확실성 마커 확인 (적절한 경우)
            uncertainty_patterns = [
                r'\b(확인 필요|추가 조사|불확실|가능성)\b',
                r'\b(requires verification|needs investigation|uncertain)\b'
            ]
            
            for pattern in uncertainty_patterns:
                results['uncertainty_markers'] += len(re.findall(pattern, response, re.IGNORECASE))
            
            # 정확성 점수 계산
            fact_score = min(1.0, results['fact_indicators'] / 5.0)
            speculation_penalty = min(0.5, results['speculation_indicators'] / 3.0)
            
            results['accuracy_score'] = max(0.0, fact_score - speculation_penalty)
            
            return results
            
        except Exception as e:
            logger.error(f"팩트 정확성 검증 실패: {e}")
            return {
                'accuracy_score': 0.5,
                'fact_indicators': 0,
                'speculation_indicators': 0,
                'uncertainty_markers': 0,
                'technical_terms_preserved': True,
                'violations': ['검증 오류 발생']
            }
    
    def validate_actionability(self, response: str) -> Dict[str, Any]:
        """
        실행 가능성 검증
        
        Args:
            response: 검증할 응답
            
        Returns:
            Dict[str, Any]: 실행 가능성 검증 결과
        """
        try:
            results = {
                'actionability_score': 0.0,
                'action_items': 0,
                'specific_steps': 0,
                'responsible_parties': 0,
                'deadlines': 0,
                'vague_statements': 0
            }
            
            # 액션 아이템 패턴
            action_patterns = [
                r'\b(다음 단계|즉시 조치|권장사항|해결 방법)\b',
                r'\b(next step|immediate action|recommendation|solution)\b',
                r'\b(확인.*필요|연락.*필요|검토.*필요)\b',
                r'\b(should|must|need to|required to)\b'
            ]
            
            for pattern in action_patterns:
                results['action_items'] += len(re.findall(pattern, response, re.IGNORECASE))
            
            # 구체적 단계 확인
            specific_patterns = [
                r'\b\d+\.\s*[A-Za-z가-힣]',  # 번호 매겨진 단계
                r'\b-\s*[A-Za-z가-힣]',      # 불릿 포인트
                r'\b(먼저|그 다음|마지막으로)\b',
                r'\b(first|then|next|finally)\b'
            ]
            
            for pattern in specific_patterns:
                results['specific_steps'] += len(re.findall(pattern, response, re.IGNORECASE))
            
            # 담당자 언급
            responsible_patterns = [
                r'\b[가-힣]{2,3}(개발자|상담원|팀장|매니저)\b',
                r'\b(developer|agent|manager|team lead)\b',
                r'\b(담당자|책임자|관리자)\b'
            ]
            
            for pattern in responsible_patterns:
                results['responsible_parties'] += len(re.findall(pattern, response, re.IGNORECASE))
            
            # 시간 관련 언급
            deadline_patterns = [
                r'\b\d+분\s*(내|이내)\b',
                r'\b\d+시간\s*(내|이내)\b',
                r'\b\d+일\s*(내|이내)\b',
                r'\bwithin\s+\d+\s*(minutes?|hours?|days?)\b'
            ]
            
            for pattern in deadline_patterns:
                results['deadlines'] += len(re.findall(pattern, response, re.IGNORECASE))
            
            # 모호한 표현 확인
            vague_patterns = [
                r'\b(가능하면|될 수 있으면|상황에 따라)\b',
                r'\b(if possible|when convenient|as needed)\b'
            ]
            
            for pattern in vague_patterns:
                results['vague_statements'] += len(re.findall(pattern, response, re.IGNORECASE))
            
            # 실행 가능성 점수 계산
            action_score = min(1.0, (results['action_items'] + results['specific_steps']) / 5.0)
            responsibility_score = min(1.0, results['responsible_parties'] / 2.0)
            urgency_score = min(1.0, results['deadlines'] / 2.0)
            vague_penalty = min(0.3, results['vague_statements'] / 3.0)
            
            results['actionability_score'] = max(0.0, 
                (action_score * 0.5 + responsibility_score * 0.3 + urgency_score * 0.2) - vague_penalty
            )
            
            return results
            
        except Exception as e:
            logger.error(f"실행 가능성 검증 실패: {e}")
            return {
                'actionability_score': 0.5,
                'action_items': 0,
                'specific_steps': 0,
                'responsible_parties': 0,
                'deadlines': 0,
                'vague_statements': 0
            }
    
    def validate_information_completeness(self, response: str,
                                        required_elements: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        정보 완성도 검증
        
        Args:
            response: 검증할 응답
            required_elements: 필수 정보 요소들
            
        Returns:
            Dict[str, Any]: 완성도 검증 결과
        """
        try:
            default_elements = [
                '문제', '원인', '해결', '인사이트',  # 한국어
                'problem', 'cause', 'solution', 'insight'  # 영어
            ]
            
            elements_to_check = required_elements or default_elements
            
            results = {
                'completeness_score': 0.0,
                'found_elements': [],
                'missing_elements': [],
                'element_coverage': 0.0
            }
            
            response_lower = response.lower()
            
            for element in elements_to_check:
                if element.lower() in response_lower:
                    results['found_elements'].append(element)
                else:
                    results['missing_elements'].append(element)
            
            # 완성도 점수 계산
            if elements_to_check:
                results['element_coverage'] = len(results['found_elements']) / len(elements_to_check)
            
            # 섹션 구조 확인
            section_indicators = ['🔍', '💡', '⚡', '🎯']
            section_count = sum(1 for indicator in section_indicators if indicator in response)
            section_score = min(1.0, section_count / 4.0)
            
            # 전체 완성도 점수
            results['completeness_score'] = (results['element_coverage'] * 0.7 + section_score * 0.3)
            
            return results
            
        except Exception as e:
            logger.error(f"정보 완성도 검증 실패: {e}")
            return {
                'completeness_score': 0.5,
                'found_elements': [],
                'missing_elements': required_elements or [],
                'element_coverage': 0.0
            }
    
    def _check_helpfulness(self, response: str, helpful_principles: List[str]) -> Dict[str, Any]:
        """도움이 되는지 확인"""
        try:
            helpful_indicators = [
                '5초 내', '즉시', '실행 가능', '다음 단계', '권장', '해결',
                'immediate', 'actionable', 'next step', 'recommend', 'solution'
            ]
            
            violations = []
            score = 0.0
            
            # 도움이 되는 지표 확인
            indicator_count = sum(
                1 for indicator in helpful_indicators 
                if indicator in response.lower()
            )
            
            # 구체성 확인
            specific_patterns = [
                r'\b\d+\s*(분|시간|일)\b',  # 시간 언급
                r'\b[가-힣]{2,3}(팀|부서|담당자)\b',  # 담당 부서
                r'\b(1단계|2단계|3단계)\b'  # 단계별 설명
            ]
            
            specific_count = sum(
                len(re.findall(pattern, response, re.IGNORECASE))
                for pattern in specific_patterns
            )
            
            # 점수 계산
            indicator_score = min(1.0, indicator_count / 5.0)
            specific_score = min(1.0, specific_count / 3.0)
            score = (indicator_score * 0.7 + specific_score * 0.3)
            
            if score < 0.5:
                violations.append("구체적이고 실행 가능한 정보 부족")
            
            return {
                'score': score,
                'violations': violations,
                'helpful_indicators': indicator_count,
                'specific_elements': specific_count
            }
            
        except Exception as e:
            logger.error(f"도움이 되는지 확인 실패: {e}")
            return {'score': 0.5, 'violations': ['검증 오류'], 'helpful_indicators': 0, 'specific_elements': 0}
    
    def _check_harmlessness(self, response: str, harmless_principles: List[str]) -> Dict[str, Any]:
        """해롭지 않은지 확인"""
        try:
            violations = []
            score = 1.0  # 기본적으로 안전하다고 가정
            
            # 개인정보 패턴 확인
            personal_info_patterns = [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # 이메일
                r'\b\d{2,3}-\d{3,4}-\d{4}\b',  # 전화번호
                r'\b\d{6}-\d{7}\b',  # 주민번호
                r'\b\d{4}\s*-\s*\d{4}\s*-\s*\d{4}\s*-\s*\d{4}\b'  # 카드번호
            ]
            
            for i, pattern in enumerate(personal_info_patterns):
                matches = re.findall(pattern, response)
                if matches:
                    violations.append(f"개인정보 노출: {['이메일', '전화번호', '주민번호', '카드번호'][i]}")
                    score -= 0.3
            
            # 추측성 정보 확인
            speculation_patterns = [
                r'\b(아마도|추측|것 같|듯함|~인 듯)\b',
                r'\b(probably|maybe|seems like|appears to)\b'
            ]
            
            for pattern in speculation_patterns:
                if re.search(pattern, response, re.IGNORECASE):
                    violations.append("추측성 정보 포함")
                    score -= 0.1
            
            score = max(0.0, score)
            
            return {
                'score': score,
                'violations': violations,
                'personal_info_detected': any(re.search(pattern, response) for pattern in personal_info_patterns),
                'speculation_detected': any(re.search(pattern, response, re.IGNORECASE) for pattern in speculation_patterns)
            }
            
        except Exception as e:
            logger.error(f"해롭지 않은지 확인 실패: {e}")
            return {'score': 0.5, 'violations': ['검증 오류'], 'personal_info_detected': False, 'speculation_detected': False}
    
    def _check_honesty(self, response: str, honest_principles: List[str]) -> Dict[str, Any]:
        """정직한지 확인"""
        try:
            violations = []
            score = 0.7  # 기본 점수
            
            # 불확실성 표현 확인 (정직함의 지표)
            uncertainty_patterns = [
                r'\b(확인 필요|추가 조사|불확실|가능성|예상)\b',
                r'\b(requires verification|needs investigation|uncertain|possible)\b'
            ]
            
            uncertainty_count = sum(
                len(re.findall(pattern, response, re.IGNORECASE))
                for pattern in uncertainty_patterns
            )
            
            # 한계 표현 확인
            limitation_patterns = [
                r'\b(한계|제약|불가능|어려움)\b',
                r'\b(limitation|constraint|unable|difficult)\b'
            ]
            
            limitation_count = sum(
                len(re.findall(pattern, response, re.IGNORECASE))
                for pattern in limitation_patterns
            )
            
            # 과도한 확신 표현 확인 (부정적 지표)
            overconfident_patterns = [
                r'\b(확실히|반드시|틀림없이|100%)\b',
                r'\b(definitely|certainly|absolutely|guaranteed)\b'
            ]
            
            overconfident_count = sum(
                len(re.findall(pattern, response, re.IGNORECASE))
                for pattern in overconfident_patterns
            )
            
            # 점수 계산
            if uncertainty_count > 0:
                score += 0.2  # 불확실성 인정은 정직함의 지표
            
            if limitation_count > 0:
                score += 0.1  # 한계 인정도 정직함의 지표
            
            if overconfident_count > 2:
                violations.append("과도한 확신 표현")
                score -= 0.2
            
            score = max(0.0, min(1.0, score))
            
            return {
                'score': score,
                'violations': violations,
                'uncertainty_markers': uncertainty_count,
                'limitation_markers': limitation_count,
                'overconfident_markers': overconfident_count
            }
            
        except Exception as e:
            logger.error(f"정직한지 확인 실패: {e}")
            return {'score': 0.5, 'violations': ['검증 오류'], 'uncertainty_markers': 0, 'limitation_markers': 0, 'overconfident_markers': 0}
    
    def _calculate_constitutional_score(self, validation_results: Dict[str, Any]) -> float:
        """Constitutional AI 전체 점수 계산"""
        try:
            if not isinstance(validation_results.get('constitutional_compliance'), dict):
                # 간단한 boolean 결과인 경우
                return float(validation_results.get('constitutional_compliance', False))
            
            compliance_data = validation_results['constitutional_compliance']
            
            helpful_score = compliance_data.get('helpful', {}).get('score', 0.0)
            harmless_score = compliance_data.get('harmless', {}).get('score', 0.0)
            honest_score = compliance_data.get('honest', {}).get('score', 0.0)
            
            # 가중 평균 계산
            total_score = (
                helpful_score * self.constitutional_weights['helpful'] +
                harmless_score * self.constitutional_weights['harmless'] +
                honest_score * self.constitutional_weights['honest']
            )
            
            return total_score
            
        except Exception as e:
            logger.error(f"Constitutional 점수 계산 실패: {e}")
            return 0.5
    
    def _update_metrics(self, quality_score: float):
        """메트릭 업데이트"""
        try:
            if quality_score >= 0.8:
                self.metrics['passed_validations'] += 1
            else:
                self.metrics['failed_validations'] += 1
            
            # 평균 품질 점수 업데이트
            total_validations = self.metrics['total_validations']
            if total_validations > 1:
                current_avg = self.metrics['avg_quality_score']
                self.metrics['avg_quality_score'] = (
                    (current_avg * (total_validations - 1) + quality_score) / total_validations
                )
            else:
                self.metrics['avg_quality_score'] = quality_score
                
        except Exception as e:
            logger.error(f"메트릭 업데이트 실패: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """검증 메트릭 조회"""
        return {
            **self.metrics,
            'pass_rate': (
                self.metrics['passed_validations'] / self.metrics['total_validations'] 
                if self.metrics['total_validations'] > 0 else 0.0
            )
        }
    
    def clear_cache(self):
        """검증 캐시 클리어"""
        self.validation_cache.clear()
        logger.info("AnthropicQualityValidator 캐시 클리어 완료")