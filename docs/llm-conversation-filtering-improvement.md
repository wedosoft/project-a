# LLM 요약 생성 시 대화 필터링 개선 방안

## 현재 상황 분석

### 현재 대화 처리 로직 (backend/core/langchain/llm_manager.py:730-750)
```python
# 대화 수 제한 (성능 최적화)
if len(sorted_conversations) > 5:
    # 최근 5개 대화만 포함
    recent_conversations = sorted_conversations[-5:]
    for conv in recent_conversations:
        sender = "사용자" if conv.get("user_id") else "상담원"
        body = self._extract_conversation_body(conv)
        prompt_context += f"- {sender}: {body[:200]}...\n"
else:
    # 5개 이하면 전체 포함
    for conv in sorted_conversations:
        sender = "사용자" if conv.get("user_id") else "상담원"
        body = self._extract_conversation_body(conv)
        prompt_context += f"- {sender}: {body[:300]}...\n"
```

## 제안하는 개선 방안

### 1. 스마트 대화 필터링 시스템

#### A. 불필요한 대화 패턴 정의 (다국어 지원)

**한국어 패턴**:
- **자동 응답**: "감사합니다", "티켓이 접수되었습니다", "자동 응답", "확인했습니다"
- **단순 인사**: "안녕하세요", "감사합니다", "수고하세요", "실례합니다"
- **시스템 메시지**: "첨부파일", "상태 변경", "우선순위 변경", "배정되었습니다"

**English Patterns**:
- **Auto-responses**: "thank you", "ticket has been", "auto", "received", "acknowledged"
- **Simple greetings**: "hello", "hi", "thanks", "regards", "best"
- **System messages**: "attachment", "status changed", "priority", "assigned to"

**공통 패턴**:
- **중복 내용**: 동일한 내용의 반복 대화 (유사도 85% 이상)
- **너무 짧은 대화**: 10자 미만 (한국어) / 5단어 미만 (영어)의 의미 없는 대화

#### B. 중요한 대화 우선순위 부여 (다국어 키워드)

**한국어 중요 키워드**:
- **문제 설명**: "문제", "오류", "에러", "안됩니다", "작동하지", "실패"
- **해결책 제시**: "해결", "방법", "시도해보세요", "설정", "확인해주세요"
- **고객 피드백**: "해결됐습니다", "여전히", "다시", "추가로", "다른 문제"
- **추가 정보**: "스크린샷", "로그", "버전", "환경", "재현"

**English Priority Keywords**:
- **Problem description**: "issue", "error", "problem", "not working", "failed", "unable"
- **Solution provision**: "solution", "try", "please check", "configure", "resolve"
- **Customer feedback**: "resolved", "still", "again", "additional", "another issue"
- **Additional info**: "screenshot", "log", "version", "environment", "reproduce"

### 2. 적응형 대화 선택 알고리즘

#### A. 컨텍스트 보존 우선 선택
1. **초기 문제 정의** - 첫 번째 문제 설명 대화
2. **핵심 전환점** - 상태 변화나 중요한 결정 시점
3. **최종 해결** - 마지막 해결책이나 결론

#### B. 토큰 효율성 고려
- 대화 길이 대비 정보 밀도 계산
- 중복 정보 제거하면서 맥락 유지
- 동적 대화 수 조정 (3~10개 범위에서 내용에 따라 조정)

### 3. 구체적 구현 방안

#### A. 필터링 함수 추가 (다국어 지원)
```python
def _filter_meaningful_conversations(self, conversations: List[Dict], max_conversations: int = 8) -> List[Dict]:
    """
    의미 있는 대화만 필터링하여 반환 (한국어/영어 지원)
    - 불필요한 자동응답, 인사말, 시스템 메시지 제거
    - 중요도에 따른 우선순위 부여
    - 컨텍스트 보존을 위한 적응형 선택
    - 언어별 다른 필터링 룰 적용
    """
    
def _detect_language(self, text: str) -> str:
    """
    텍스트 언어 감지 (한국어/영어)
    - 한글 문자 비율로 간단 판별
    - 향후 langdetect 라이브러리 활용 가능
    """
    korean_chars = len([c for c in text if ord(c) >= 0xAC00 and ord(c) <= 0xD7A3])
    total_chars = len([c for c in text if c.isalpha()])
    return "ko" if total_chars > 0 and korean_chars / total_chars > 0.3 else "en"
```

#### B. 중요도 점수 계산 (다국어 지원)
```python
def _calculate_conversation_importance(self, conv: Dict) -> float:
    """
    대화의 중요도 점수 계산 (0.0 ~ 1.0)
    - 길이, 키워드, 위치, 발신자 등 종합 고려
    - 언어별 다른 가중치 적용
    - 한국어: 조사, 어미 고려
    - 영어: 전치사, 관사 제외 키워드 분석
    """
    
def _get_language_specific_patterns(self, language: str) -> Dict[str, List[str]]:
    """
    언어별 패턴 반환
    - 한국어/영어별 자동응답, 인사말, 중요 키워드 패턴
    - 확장 가능한 구조로 설계
    """
```

#### C. 컨텍스트 연결성 평가
```python
def _evaluate_context_continuity(self, conversations: List[Dict]) -> List[Dict]:
    """
    선택된 대화들이 스토리의 흐름을 유지하는지 평가
    - 시간적 흐름 보존
    - 논리적 연결성 확인
    """
```

### 4. 설정 가능한 파라미터

#### A. 환경 변수로 제어
```python
# 언어별 최소 대화 길이 (기본값)
LLM_MIN_LENGTH_KO=10
LLM_MIN_LENGTH_EN=20

# 언어별 필터링 강도 (strict/normal/loose)
LLM_FILTER_LEVEL_KO=normal
LLM_FILTER_LEVEL_EN=normal

# 다국어 키워드 파일 경로
LLM_KEYWORDS_KO_PATH=./config/keywords_ko.json
LLM_KEYWORDS_EN_PATH=./config/keywords_en.json
```

#### B. 티켓별 동적 조정 (다국어 환경)
- **단순한 티켓**: 언어에 관계없이 적은 대화 수로도 충분
- **복잡한 티켓**: 언어별 특성 고려한 대화 수 조정
- **다국어 혼재 티켓**: 언어별 중요도 가중치 적용
- **긴 대화 스레드**: 언어별 핵심 포인트 추출 방식 다르게 적용

### 5. 구현 우선순위

#### Phase 1: 기본 필터링 (즉시 구현 가능)
1. 자동응답, 인사말 패턴 제거
2. 너무 짧은 대화 필터링
3. 중복 내용 제거

#### Phase 2: 스마트 선택 (2주 내 구현)
1. 중요도 점수 기반 선택
2. 컨텍스트 연결성 평가
3. 적응형 대화 수 조정

#### Phase 3: AI 기반 필터링 (향후 고도화)
1. LLM을 이용한 대화 중요도 평가
2. 자동 학습 기반 필터링 개선
3. 도메인별 맞춤 필터링

## 고급 필터링 전략: 대화 수 제한 없는 스마트 파이프라인

### 핵심 아이디어: 대화 수 제한 제거 + 3단계 필터링 파이프라인

30-50개 대화가 있는 복잡한 티켓에서도 모든 중요한 맥락을 보존하면서 노이즈만 제거하는 전략:

#### 1단계: 기본 노이즈 제거 (Pre-filtering)
- 자동응답, 시스템 메시지, 단순 인사말 제거
- 중복 내용 병합 (85% 이상 유사도)
- 의미 없는 짧은 대화 제거

#### 2단계: 지능형 중요도 평가 (Smart Scoring)
- 문제 정의, 해결 과정, 결론 등 핵심 포인트 식별
- 시간적 흐름과 논리적 연결성 평가
- 언어별 맞춤 중요도 점수 계산

#### 3단계: 토큰 예산 기반 최적 선택 (Token-aware Selection)
- LLM 토큰 한계 내에서 최대한 많은 대화 포함
- 컨텍스트 연결성 유지하면서 선택적 요약
- 동적 대화 길이 조정 (중요한 대화는 전문, 덜 중요한 것은 요약)

### 고급 필터링 파이프라인 구현

```python
class AdvancedConversationFilter:
    """
    대화 수 제한 없는 고급 필터링 시스템
    - 30-50개 대화도 효과적으로 처리
    - 맥락 보존 우선, 노이즈 제거 부차
    - 토큰 예산 내 최적 선택
    """
    
    def __init__(self, max_tokens: int = 8000, language_weights: Dict[str, float] = None):
        self.max_tokens = max_tokens
        self.language_weights = language_weights or {"ko": 1.0, "en": 1.0}
        self.keyword_cache = {}
        self._load_language_keywords()
    
    def filter_conversations_advanced(self, conversations: List[Dict]) -> List[Dict]:
        """
        고급 3단계 필터링 파이프라인
        대화 수 제한 없이 품질 기반 선택
        """
        if not conversations:
            return []
        
        # 1단계: 기본 노이즈 제거
        cleaned_conversations = self._remove_noise(conversations)
        
        # 2단계: 중요도 기반 평가 및 그룹핑
        scored_conversations = self._calculate_advanced_scores(cleaned_conversations)
        
        # 3단계: 토큰 예산 기반 최적 선택
        selected_conversations = self._select_within_token_budget(scored_conversations)
        
        return selected_conversations
    
    def _remove_noise(self, conversations: List[Dict]) -> List[Dict]:
        """1단계: 기본 노이즈 제거"""
        cleaned = []
        seen_content = set()
        
        for conv in conversations:
            body = self._extract_conversation_body(conv).strip()
            
            # 기본 필터링
            if not self._is_meaningful_conversation_advanced(conv):
                continue
            
            # 중복 제거 (단순 해시 기반)
            content_hash = hash(body.lower()[:100])  # 처음 100자로 중복 판별
            if content_hash in seen_content:
                continue
            seen_content.add(content_hash)
            
            cleaned.append(conv)
        
        return cleaned
    
    def _calculate_advanced_scores(self, conversations: List[Dict]) -> List[Tuple[Dict, float, str]]:
        """2단계: 고급 중요도 점수 계산"""
        scored_conversations = []
        
        for i, conv in enumerate(conversations):
            # 기본 중요도 점수
            importance_score = self._calculate_conversation_priority_advanced(conv)
            
            # 위치 기반 가중치 (시작, 중간 전환점, 끝 부분 중요)
            position_weight = self._calculate_position_weight(i, len(conversations))
            
            # 컨텍스트 연결성 점수
            context_score = self._calculate_context_continuity_score(conv, conversations, i)
            
            # 최종 점수 (0.0 ~ 1.0)
            final_score = (importance_score * 0.5 + position_weight * 0.2 + context_score * 0.3)
            
            # 대화 유형 분류
            conversation_type = self._classify_conversation_type(conv)
            
            scored_conversations.append((conv, final_score, conversation_type))
        
        # 점수순 정렬
        return sorted(scored_conversations, key=lambda x: x[1], reverse=True)
    
    def _select_within_token_budget(self, scored_conversations: List[Tuple[Dict, float, str]]) -> List[Dict]:
        """3단계: 토큰 예산 내 최적 선택"""
        selected = []
        current_tokens = 0
        
        # 필수 대화 우선 선택 (problem_definition, solution, conclusion)
        essential_types = ["problem_definition", "solution", "conclusion"]
        
        # 1. 필수 대화부터 선택
        for conv, score, conv_type in scored_conversations:
            if conv_type in essential_types and current_tokens < self.max_tokens * 0.7:
                body = self._extract_conversation_body(conv)
                estimated_tokens = len(body.split()) * 1.3  # 대략적 토큰 수 추정
                
                if current_tokens + estimated_tokens <= self.max_tokens:
                    selected.append(conv)
                    current_tokens += estimated_tokens
        
        # 2. 남은 예산으로 중요도 순 선택
        for conv, score, conv_type in scored_conversations:
            if conv not in selected:
                body = self._extract_conversation_body(conv)
                estimated_tokens = len(body.split()) * 1.3
                
                # 토큰 예산 내에서 선택
                if current_tokens + estimated_tokens <= self.max_tokens:
                    selected.append(conv)
                    current_tokens += estimated_tokens
                else:
                    # 토큰 예산 초과 시 요약 버전 생성
                    if score > 0.7:  # 중요도가 높으면 요약해서라도 포함
                        summarized_body = body[:150] + "..."  # 간단 요약
                        conv_copy = conv.copy()
                        conv_copy['body'] = summarized_body
                        selected.append(conv_copy)
                        current_tokens += 50  # 요약 버전 토큰 수
        
        # 시간순 정렬하여 반환
        return sorted(selected, key=lambda x: x.get('created_at', ''))
    
    def _classify_conversation_type(self, conv: Dict) -> str:
        """대화 유형 분류"""
        body = self._extract_conversation_body(conv).lower()
        language = self._detect_language(body)
        
        # 언어별 패턴 매칭
        if language == "ko":
            if any(word in body for word in ["문제", "오류", "에러", "안됩니다", "고장"]):
                return "problem_definition"
            elif any(word in body for word in ["해결", "방법", "시도", "확인해보세요"]):
                return "solution"
            elif any(word in body for word in ["해결됐습니다", "완료", "감사합니다", "닫기"]):
                return "conclusion"
            elif any(word in body for word in ["추가", "더", "또", "그런데"]):
                return "follow_up"
        else:  # English
            if any(word in body for word in ["issue", "problem", "error", "not working", "broken"]):
                return "problem_definition"
            elif any(word in body for word in ["solution", "try", "fix", "resolve", "please check"]):
                return "solution"
            elif any(word in body for word in ["resolved", "fixed", "thank you", "close", "done"]):
                return "conclusion"
            elif any(word in body for word in ["also", "additionally", "another", "furthermore"]):
                return "follow_up"
        
        return "general"
    
    def _calculate_position_weight(self, index: int, total: int) -> float:
        """위치 기반 가중치 계산"""
        if total <= 3:
            return 1.0
        
        # 시작 부분 (첫 3개)
        if index < 3:
            return 0.9
        
        # 끝 부분 (마지막 3개)
        if index >= total - 3:
            return 0.9
        
        # 중간 부분은 균등하게
        return 0.7
    
    def _calculate_context_continuity_score(self, conv: Dict, all_conversations: List[Dict], index: int) -> float:
        """컨텍스트 연결성 점수"""
        if index == 0 or index >= len(all_conversations) - 1:
            return 0.8  # 시작/끝은 기본 높은 점수
        
        current_body = self._extract_conversation_body(conv).lower()
        prev_body = self._extract_conversation_body(all_conversations[index-1]).lower()
        
        # 간단한 연결성 체크 (공통 키워드 비율)
        current_words = set(current_body.split())
        prev_words = set(prev_body.split())
        
        if len(current_words) == 0 or len(prev_words) == 0:
            return 0.5
        
        common_words = current_words.intersection(prev_words)
        continuity_ratio = len(common_words) / max(len(current_words), len(prev_words))
        
        return min(continuity_ratio * 2, 1.0)  # 최대 1.0으로 제한
```

#### C. 컨텍스트 연결성 평가
```python
def _evaluate_context_continuity(self, conversations: List[Dict]) -> List[Dict]:
    """
    선택된 대화들이 스토리의 흐름을 유지하는지 평가
    - 시간적 흐름 보존
    - 논리적 연결성 확인
    """
```

### 4. 설정 가능한 파라미터

#### A. 환경 변수로 제어
```python
# 언어별 최소 대화 길이 (기본값)
LLM_MIN_LENGTH_KO=10
LLM_MIN_LENGTH_EN=20

# 언어별 필터링 강도 (strict/normal/loose)
LLM_FILTER_LEVEL_KO=normal
LLM_FILTER_LEVEL_EN=normal

# 다국어 키워드 파일 경로
LLM_KEYWORDS_KO_PATH=./config/keywords_ko.json
LLM_KEYWORDS_EN_PATH=./config/keywords_en.json
```

#### B. 티켓별 동적 조정 (다국어 환경)
- **단순한 티켓**: 언어에 관계없이 적은 대화 수로도 충분
- **복잡한 티켓**: 언어별 특성 고려한 대화 수 조정
- **다국어 혼재 티켓**: 언어별 중요도 가중치 적용
- **긴 대화 스레드**: 언어별 핵심 포인트 추출 방식 다르게 적용

### 5. 구현 우선순위

#### Phase 1: 기본 필터링 (즉시 구현 가능)
1. 자동응답, 인사말 패턴 제거
2. 너무 짧은 대화 필터링
3. 중복 내용 제거

#### Phase 2: 스마트 선택 (2주 내 구현)
1. 중요도 점수 기반 선택
2. 컨텍스트 연결성 평가
3. 적응형 대화 수 조정

#### Phase 3: AI 기반 필터링 (향후 고도화)
1. LLM을 이용한 대화 중요도 평가
2. 자동 학습 기반 필터링 개선
3. 도메인별 맞춤 필터링

## 고급 필터링 전략: 대화 수 제한 없는 스마트 파이프라인

### 핵심 아이디어: 대화 수 제한 제거 + 3단계 필터링 파이프라인

30-50개 대화가 있는 복잡한 티켓에서도 모든 중요한 맥락을 보존하면서 노이즈만 제거하는 전략:

#### 1단계: 기본 노이즈 제거 (Pre-filtering)
- 자동응답, 시스템 메시지, 단순 인사말 제거
- 중복 내용 병합 (85% 이상 유사도)
- 의미 없는 짧은 대화 제거

#### 2단계: 지능형 중요도 평가 (Smart Scoring)
- 문제 정의, 해결 과정, 결론 등 핵심 포인트 식별
- 시간적 흐름과 논리적 연결성 평가
- 언어별 맞춤 중요도 점수 계산

#### 3단계: 토큰 예산 기반 최적 선택 (Token-aware Selection)
- LLM 토큰 한계 내에서 최대한 많은 대화 포함
- 컨텍스트 연결성 유지하면서 선택적 요약
- 동적 대화 길이 조정 (중요한 대화는 전문, 덜 중요한 것은 요약)

### 고급 필터링 파이프라인 구현

```python
class AdvancedConversationFilter:
    """
    대화 수 제한 없는 고급 필터링 시스템
    - 30-50개 대화도 효과적으로 처리
    - 맥락 보존 우선, 노이즈 제거 부차
    - 토큰 예산 내 최적 선택
    """
    
    def __init__(self, max_tokens: int = 8000, language_weights: Dict[str, float] = None):
        self.max_tokens = max_tokens
        self.language_weights = language_weights or {"ko": 1.0, "en": 1.0}
        self.keyword_cache = {}
        self._load_language_keywords()
    
    def filter_conversations_advanced(self, conversations: List[Dict]) -> List[Dict]:
        """
        고급 3단계 필터링 파이프라인
        대화 수 제한 없이 품질 기반 선택
        """
        if not conversations:
            return []
        
        # 1단계: 기본 노이즈 제거
        cleaned_conversations = self._remove_noise(conversations)
        
        # 2단계: 중요도 기반 평가 및 그룹핑
        scored_conversations = self._calculate_advanced_scores(cleaned_conversations)
        
        # 3단계: 토큰 예산 기반 최적 선택
        selected_conversations = self._select_within_token_budget(scored_conversations)
        
        return selected_conversations
    
    def _remove_noise(self, conversations: List[Dict]) -> List[Dict]:
        """1단계: 기본 노이즈 제거"""
        cleaned = []
        seen_content = set()
        
        for conv in conversations:
            body = self._extract_conversation_body(conv).strip()
            
            # 기본 필터링
            if not self._is_meaningful_conversation_advanced(conv):
                continue
            
            # 중복 제거 (단순 해시 기반)
            content_hash = hash(body.lower()[:100])  # 처음 100자로 중복 판별
            if content_hash in seen_content:
                continue
            seen_content.add(content_hash)
            
            cleaned.append(conv)
        
        return cleaned
    
    def _calculate_advanced_scores(self, conversations: List[Dict]) -> List[Tuple[Dict, float, str]]:
        """2단계: 고급 중요도 점수 계산"""
        scored_conversations = []
        
        for i, conv in enumerate(conversations):
            # 기본 중요도 점수
            importance_score = self._calculate_conversation_priority_advanced(conv)
            
            # 위치 기반 가중치 (시작, 중간 전환점, 끝 부분 중요)
            position_weight = self._calculate_position_weight(i, len(conversations))
            
            # 컨텍스트 연결성 점수
            context_score = self._calculate_context_continuity_score(conv, conversations, i)
            
            # 최종 점수 (0.0 ~ 1.0)
            final_score = (importance_score * 0.5 + position_weight * 0.2 + context_score * 0.3)
            
            # 대화 유형 분류
            conversation_type = self._classify_conversation_type(conv)
            
            scored_conversations.append((conv, final_score, conversation_type))
        
        # 점수순 정렬
        return sorted(scored_conversations, key=lambda x: x[1], reverse=True)
    
    def _select_within_token_budget(self, scored_conversations: List[Tuple[Dict, float, str]]) -> List[Dict]:
        """3단계: 토큰 예산 내 최적 선택"""
        selected = []
        current_tokens = 0
        
        # 필수 대화 우선 선택 (problem_definition, solution, conclusion)
        essential_types = ["problem_definition", "solution", "conclusion"]
        
        # 1. 필수 대화부터 선택
        for conv, score, conv_type in scored_conversations:
            if conv_type in essential_types and current_tokens < self.max_tokens * 0.7:
                body = self._extract_conversation_body(conv)
                estimated_tokens = len(body.split()) * 1.3  # 대략적 토큰 수 추정
                
                if current_tokens + estimated_tokens <= self.max_tokens:
                    selected.append(conv)
                    current_tokens += estimated_tokens
        
        # 2. 남은 예산으로 중요도 순 선택
        for conv, score, conv_type in scored_conversations:
            if conv not in selected:
                body = self._extract_conversation_body(conv)
                estimated_tokens = len(body.split()) * 1.3
                
                # 토큰 예산 내에서 선택
                if current_tokens + estimated_tokens <= self.max_tokens:
                    selected.append(conv)
                    current_tokens += estimated_tokens
                else:
                    # 토큰 예산 초과 시 요약 버전 생성
                    if score > 0.7:  # 중요도가 높으면 요약해서라도 포함
                        summarized_body = body[:150] + "..."  # 간단 요약
                        conv_copy = conv.copy()
                        conv_copy['body'] = summarized_body
                        selected.append(conv_copy)
                        current_tokens += 50  # 요약 버전 토큰 수
        
        # 시간순 정렬하여 반환
        return sorted(selected, key=lambda x: x.get('created_at', ''))
    
    def _classify_conversation_type(self, conv: Dict) -> str:
        """대화 유형 분류"""
        body = self._extract_conversation_body(conv).lower()
        language = self._detect_language(body)
        
        # 언어별 패턴 매칭
        if language == "ko":
            if any(word in body for word in ["문제", "오류", "에러", "안됩니다", "고장"]):
                return "problem_definition"
            elif any(word in body for word in ["해결", "방법", "시도", "확인해보세요"]):
                return "solution"
            elif any(word in body for word in ["해결됐습니다", "완료", "감사합니다", "닫기"]):
                return "conclusion"
            elif any(word in body for word in ["추가", "더", "또", "그런데"]):
                return "follow_up"
        else:  # English
            if any(word in body for word in ["issue", "problem", "error", "not working", "broken"]):
                return "problem_definition"
            elif any(word in body for word in ["solution", "try", "fix", "resolve", "please check"]):
                return "solution"
            elif any(word in body for word in ["resolved", "fixed", "thank you", "close", "done"]):
                return "conclusion"
            elif any(word in body for word in ["also", "additionally", "another", "furthermore"]):
                return "follow_up"
        
        return "general"
    
    def _calculate_position_weight(self, index: int, total: int) -> float:
        """위치 기반 가중치 계산"""
        if total <= 3:
            return 1.0
        
        # 시작 부분 (첫 3개)
        if index < 3:
            return 0.9
        
        # 끝 부분 (마지막 3개)
        if index >= total - 3:
            return 0.9
        
        # 중간 부분은 균등하게
        return 0.7
    
    def _calculate_context_continuity_score(self, conv: Dict, all_conversations: List[Dict], index: int) -> float:
        """컨텍스트 연결성 점수"""
        if index == 0 or index >= len(all_conversations) - 1:
            return 0.8  # 시작/끝은 기본 높은 점수
        
        current_body = self._extract_conversation_body(conv).lower()
        prev_body = self._extract_conversation_body(all_conversations[index-1]).lower()
        
        # 간단한 연결성 체크 (공통 키워드 비율)
        current_words = set(current_body.split())
        prev_words = set(prev_body.split())
        
        if len(current_words) == 0 or len(prev_words) == 0:
            return 0.5
        
        common_words = current_words.intersection(prev_words)
        continuity_ratio = len(common_words) / max(len(current_words), len(prev_words))
        
        return min(continuity_ratio * 2, 1.0)  # 최대 1.0으로 제한
```

### 4. 설정 가능한 파라미터

#### A. 환경 변수로 제어
```python
# 언어별 최소 대화 길이 (기본값)
LLM_MIN_LENGTH_KO=10
LLM_MIN_LENGTH_EN=20

# 언어별 필터링 강도 (strict/normal/loose)
LLM_FILTER_LEVEL_KO=normal
LLM_FILTER_LEVEL_EN=normal

# 다국어 키워드 파일 경로
LLM_KEYWORDS_KO_PATH=./config/keywords_ko.json
LLM_KEYWORDS_EN_PATH=./config/keywords_en.json
```

#### B. 티켓별 동적 조정 (다국어 환경)
- **단순한 티켓**: 언어에 관계없이 적은 대화 수로도 충분
- **복잡한 티켓**: 언어별 특성 고려한 대화 수 조정
- **다국어 혼재 티켓**: 언어별 중요도 가중치 적용
- **긴 대화 스레드**: 언어별 핵심 포인트 추출 방식 다르게 적용

### 5. 구현 우선순위

#### Phase 1: 기본 필터링 (즉시 구현 가능)
1. 자동응답, 인사말 패턴 제거
2. 너무 짧은 대화 필터링
3. 중복 내용 제거

#### Phase 2: 스마트 선택 (2주 내 구현)
1. 중요도 점수 기반 선택
2. 컨텍스트 연결성 평가
3. 적응형 대화 수 조정

#### Phase 3: AI 기반 필터링 (향후 고도화)
1. LLM을 이용한 대화 중요도 평가
2. 자동 학습 기반 필터링 개선
3. 도메인별 맞춤 필터링

## 고급 필터링 전략: 대화 수 제한 없는 스마트 파이프라인

### 핵심 아이디어: 대화 수 제한 제거 + 3단계 필터링 파이프라인

30-50개 대화가 있는 복잡한 티켓에서도 모든 중요한 맥락을 보존하면서 노이즈만 제거하는 전략:

#### 1단계: 기본 노이즈 제거 (Pre-filtering)
- 자동응답, 시스템 메시지, 단순 인사말 제거
- 중복 내용 병합 (85% 이상 유사도)
- 의미 없는 짧은 대화 제거

#### 2단계: 지능형 중요도 평가 (Smart Scoring)
- 문제 정의, 해결 과정, 결론 등 핵심 포인트 식별
- 시간적 흐름과 논리적 연결성 평가
- 언어별 맞춤 중요도 점수 계산

#### 3단계: 토큰 예산 기반 최적 선택 (Token-aware Selection)
- LLM 토큰 한계 내에서 최대한 많은 대화 포함
- 컨텍스트 연결성 유지하면서 선택적 요약
- 동적 대화 길이 조정 (중요한 대화는 전문, 덜 중요한 것은 요약)

### 고급 필터링 파이프라인 구현

```python
class AdvancedConversationFilter:
    """
    대화 수 제한 없는 고급 필터링 시스템
    - 30-50개 대화도 효과적으로 처리
    - 맥락 보존 우선, 노이즈 제거 부차
    - 토큰 예산 내 최적 선택
    """
    
    def __init__(self, max_tokens: int = 8000, language_weights: Dict[str, float] = None):
        self.max_tokens = max_tokens
        self.language_weights = language_weights or {"ko": 1.0, "en": 1.0}
        self.keyword_cache = {}
        self._load_language_keywords()
    
    def filter_conversations_advanced(self, conversations: List[Dict]) -> List[Dict]:
        """
        고급 3단계 필터링 파이프라인
        대화 수 제한 없이 품질 기반 선택
        """
        if not conversations:
            return []
        
        # 1단계: 기본 노이즈 제거
        cleaned_conversations = self._remove_noise(conversations)
        
        # 2단계: 중요도 기반 평가 및 그룹핑
        scored_conversations = self._calculate_advanced_scores(cleaned_conversations)
        
        # 3단계: 토큰 예산 기반 최적 선택
        selected_conversations = self._select_within_token_budget(scored_conversations)
        
        return selected_conversations
    
    def _remove_noise(self, conversations: List[Dict]) -> List[Dict]:
        """1단계: 기본 노이즈 제거"""
        cleaned = []
        seen_content = set()
        
        for conv in conversations:
            body = self._extract_conversation_body(conv).strip()
            
            # 기본 필터링
            if not self._is_meaningful_conversation_advanced(conv):
                continue
            
            # 중복 제거 (단순 해시 기반)
            content_hash = hash(body.lower()[:100])  # 처음 100자로 중복 판별
            if content_hash in seen_content:
                continue
            seen_content.add(content_hash)
            
            cleaned.append(conv)
        
        return cleaned
    
    def _calculate_advanced_scores(self, conversations: List[Dict]) -> List[Tuple[Dict, float, str]]:
        """2단계: 고급 중요도 점수 계산"""
        scored_conversations = []
        
        for i, conv in enumerate(conversations):
            # 기본 중요도 점수
            importance_score = self._calculate_conversation_priority_advanced(conv)
            
            # 위치 기반 가중치 (시작, 중간 전환점, 끝 부분 중요)
            position_weight = self._calculate_position_weight(i, len(conversations))
            
            # 컨텍스트 연결성 점수
            context_score = self._calculate_context_continuity_score(conv, conversations, i)
            
            # 최종 점수 (0.0 ~ 1.0)
            final_score = (importance_score * 0.5 + position_weight * 0.2 + context_score * 0.3)
            
            # 대화 유형 분류
            conversation_type = self._classify_conversation_type(conv)
            
            scored_conversations.append((conv, final_score, conversation_type))
        
        # 점수순 정렬
        return sorted(scored_conversations, key=lambda x: x[1], reverse=True)
    
    def _select_within_token_budget(self, scored_conversations: List[Tuple[Dict, float, str]]) -> List[Dict]:
        """3단계: 토큰 예산 내 최적 선택"""
        selected = []
        current_tokens = 0
        
        # 필수 대화 우선 선택 (problem_definition, solution, conclusion)
        essential_types = ["problem_definition", "solution", "conclusion"]
        
        # 1. 필수 대화부터 선택
        for conv, score, conv_type in scored_conversations:
            if conv_type in essential_types and current_tokens < self.max_tokens * 0.7:
                body = self._extract_conversation_body(conv)
                estimated_tokens = len(body.split()) * 1.3  # 대략적 토큰 수 추정
                
                if current_tokens + estimated_tokens <= self.max_tokens:
                    selected.append(conv)
                    current_tokens += estimated_tokens
        
        # 2. 남은 예산으로 중요도 순 선택
        for conv, score, conv_type in scored_conversations:
            if conv not in selected:
                body = self._extract_conversation_body(conv)
                estimated_tokens = len(body.split()) * 1.3
                
                # 토큰 예산 내에서 선택
                if current_tokens + estimated_tokens <= self.max_tokens:
                    selected.append(conv)
                    current_tokens += estimated_tokens
                else:
                    # 토큰 예산 초과 시 요약 버전 생성
                    if score > 0.7:  # 중요도가 높으면 요약해서라도 포함
                        summarized_body = body[:150] + "..."  # 간단 요약
                        conv_copy = conv.copy()
                        conv_copy['body'] = summarized_body
                        selected.append(conv_copy)
                        current_tokens += 50  # 요약 버전 토큰 수
        
        # 시간순 정렬하여 반환
        return sorted(selected, key=lambda x: x.get('created_at', ''))
    
    def _classify_conversation_type(self, conv: Dict) -> str:
        """대화 유형 분류"""
        body = self._extract_conversation_body(conv).lower()
        language = self._detect_language(body)
        
        # 언어별 패턴 매칭
        if language == "ko":
            if any(word in body for word in ["문제", "오류", "에러", "안됩니다", "고장"]):
                return "problem_definition"
            elif any(word in body for word in ["해결", "방법", "시도", "확인해보세요"]):
                return "solution"
            elif any(word in body for word in ["해결됐습니다", "완료", "감사합니다", "닫기"]):
                return "conclusion"
            elif any(word in body for word in ["추가", "더", "또", "그런데"]):
                return "follow_up"
        else:  # English
            if any(word in body for word in ["issue", "problem", "error", "not working", "broken"]):
                return "problem_definition"
            elif any(word in body for word in ["solution", "try", "fix", "resolve", "please check"]):
                return "solution"
            elif any(word in body for word in ["resolved", "fixed", "thank you", "close", "done"]):
                return "conclusion"
            elif any(word in body for word in ["also", "additionally", "another", "furthermore"]):
                return "follow_up"
        
        return "general"
    
    def _calculate_position_weight(self, index: int, total: int) -> float:
        """위치 기반 가중치 계산"""
        if total <= 3:
            return 1.0
        
        # 시작 부분 (첫 3개)
        if index < 3:
            return 0.9
        
        # 끝 부분 (마지막 3개)
        if index >= total - 3:
            return 0.9
        
        # 중간 부분은 균등하게
        return 0.7
    
    def _calculate_context_continuity_score(self, conv: Dict, all_conversations: List[Dict], index: int) -> float:
        """컨텍스트 연결성 점수"""
        if index == 0 or index >= len(all_conversations) - 1:
            return 0.8  # 시작/끝은 기본 높은 점수
        
        current_body = self._extract_conversation_body(conv).lower()
        prev_body = self._extract_conversation_body(all_conversations[index-1]).lower()
        
        # 간단한 연결성 체크 (공통 키워드 비율)
        current_words = set(current_body.split())
        prev_words = set(prev_body.split())
        
        if len(current_words) == 0 or len(prev_words) == 0:
            return 0.5
        
        common_words = current_words.intersection(prev_words)
        continuity_ratio = len(common_words) / max(len(current_words), len(prev_words))
        
        return min(continuity_ratio * 2, 1.0)  # 최대 1.0으로 제한
```

### 4. 설정 가능한 파라미터

#### A. 환경 변수로 제어
```python
# 언어별 최소 대화 길이 (기본값)
LLM_MIN_LENGTH_KO=10
LLM_MIN_LENGTH_EN=20

# 언어별 필터링 강도 (strict/normal/loose)
LLM_FILTER_LEVEL_KO=normal
LLM_FILTER_LEVEL_EN=normal

# 다국어 키워드 파일 경로
LLM_KEYWORDS_KO_PATH=./config/keywords_ko.json
LLM_KEYWORDS_EN_PATH=./config/keywords_en.json
```

#### B. 티켓별 동적 조정 (다국어 환경)
- **단순한 티켓**: 언어에 관계없이 적은 대화 수로도 충분
- **복잡한 티켓**: 언어별 특성 고려한 대화 수 조정
- **다국어 혼재 티켓**: 언어별 중요도 가중치 적용
- **긴 대화 스레드**: 언어별 핵심 포인트 추출 방식 다르게 적용

### 5. 구현 우선순위

#### Phase 1: 기본 필터링 (즉시 구현 가능)
1. 자동응답, 인사말 패턴 제거
2. 너무 짧은 대화 필터링
3. 중복 내용 제거

#### Phase 2: 스마트 선택 (2주 내 구현)
1. 중요도 점수 기반 선택
2. 컨텍스트 연결성 평가
3. 적응형 대화 수 조정

#### Phase 3: AI 기반 필터링 (향후 고도화)
1. LLM을 이용한 대화 중요도 평가
2. 자동 학습 기반 필터링 개선
3. 도메인별 맞춤 필터링

## 고급 필터링 전략: 대화 수 제한 없는 스마트 파이프라인

### 핵심 아이디어: 대화 수 제한 제거 + 3단계 필터링 파이프라인

30-50개 대화가 있는 복잡한 티켓에서도 모든 중요한 맥락을 보존하면서 노이즈만 제거하는 전략:

#### 1단계: 기본 노이즈 제거 (Pre-filtering)
- 자동응답, 시스템 메시지, 단순 인사말 제거
- 중복 내용 병합 (85% 이상 유사도)
- 의미 없는 짧은 대화 제거

#### 2단계: 지능형 중요도 평가 (Smart Scoring)
- 문제 정의, 해결 과정, 결론 등 핵심 포인트 식별
- 시간적 흐름과 논리적 연결성 평가
- 언어별 맞춤 중요도 점수 계산

#### 3단계: 토큰 예산 기반 최적 선택 (Token-aware Selection)
- LLM 토큰 한계 내에서 최대한 많은 대화 포함
- 컨텍스트 연결성 유지하면서 선택적 요약
- 동적 대화 길이 조정 (중요한 대화는 전문, 덜 중요한 것은 요약)

### 고급 필터링 파이프라인 구현

```python
class AdvancedConversationFilter:
    """
    대화 수 제한 없는 고급 필터링 시스템
    - 30-50개 대화도 효과적으로 처리
    - 맥락 보존 우선, 노이즈 제거 부차
    - 토큰 예산 내 최적 선택
    """
    
    def __init__(self, max_tokens: int = 8000, language_weights: Dict[str, float] = None):
        self.max_tokens = max_tokens
        self.language_weights = language_weights or {"ko": 1.0, "en": 1.0}
        self.keyword_cache = {}
        self._load_language_keywords()
    
    def filter_conversations_advanced(self, conversations: List[Dict]) -> List[Dict]:
        """
        고급 3단계 필터링 파이프라인
        대화 수 제한 없이 품질 기반 선택
        """
        if not conversations:
            return []
        
        # 1단계: 기본 노이즈 제거
        cleaned_conversations = self._remove_noise(conversations)
        
        # 2단계: 중요도 기반 평가 및 그룹핑
        scored_conversations = self._calculate_advanced_scores(cleaned_conversations)
        
        # 3단계: 토큰 예산 기반 최적 선택
        selected_conversations = self._select_within_token_budget(scored_conversations)
        
        return selected_conversations
    
    def _remove_noise(self, conversations: List[Dict]) -> List[Dict]:
        """1단계: 기본 노이즈 제거"""
        cleaned = []
        seen_content = set()
        
        for conv in conversations:
            body = self._extract_conversation_body(conv).strip()
            
            # 기본 필터링
            if not self._is_meaningful_conversation_advanced(conv):
                continue
            
            # 중복 제거 (단순 해시 기반)
            content_hash = hash(body.lower()[:100])  # 처음 100자로 중복 판별
            if content_hash in seen_content:
                continue
            seen_content.add(content_hash)
            
            cleaned.append(conv)
        
        return cleaned
    
    def _calculate_advanced_scores(self, conversations: List[Dict]) -> List[Tuple[Dict, float, str]]:
        """2단계: 고급 중요도 점수 계산"""
        scored_conversations = []
        
        for i, conv in enumerate(conversations):
            # 기본 중요도 점수
            importance_score = self._calculate_conversation_priority_advanced(conv)
            
            # 위치 기반 가중치 (시작, 중간 전환점, 끝 부분 중요)
            position_weight = self._calculate_position_weight(i, len(conversations))
            
            # 컨텍스트 연결성 점수
            context_score = self._calculate_context_continuity_score(conv, conversations, i)
            
            # 최종 점수 (0.0 ~ 1.0)
            final_score = (importance_score * 0.5 + position_weight * 0.2 + context_score * 0.3)
            
            # 대화 유형 분류
            conversation_type = self._classify_conversation_type(conv)
            
            scored_conversations.append((conv, final_score, conversation_type))
        
        # 점수순 정렬
        return sorted(scored_conversations, key=lambda x: x[1], reverse=True)
    
    def _select_within_token_budget(self, scored_conversations: List[Tuple[Dict, float, str]]) -> List[Dict]:
        """3단계: 토큰 예산 내 최적 선택"""
        selected = []
        current_tokens = 0
        
        # 필수 대화 우선 선택 (problem_definition, solution, conclusion)
        essential_types = ["problem_definition", "solution", "conclusion"]
        
        # 1. 필수 대화부터 선택
        for conv, score, conv_type in scored_conversations:
            if conv_type in essential_types and current_tokens < self.max_tokens * 0.7:
                body = self._extract_conversation_body(conv)
                estimated_tokens = len(body.split()) * 1.3  # 대략적 토큰 수 추정
                
                if current_tokens + estimated_tokens <= self.max_tokens:
                    selected.append(conv)
                    current_tokens += estimated_tokens
        
        # 2. 남은 예산으로 중요도 순 선택
        for conv, score, conv_type in scored_conversations:
            if conv not in selected:
                body = self._extract_conversation_body(conv)
                estimated_tokens = len(body.split()) * 1.3
                
                # 토큰 예산 내에서 선택
                if current_tokens + estimated_tokens <= self.max_tokens:
                    selected.append(conv)
                    current_tokens += estimated_tokens
                else:
                    # 토큰 예산 초과 시 요약 버전 생성
                    if score > 0.7:  # 중요도가 높으면 요약해서라도 포함
                        summarized_body = body[:150] + "..."  # 간단 요약
                        conv_copy = conv.copy()
                        conv_copy['body'] = summarized_body
                        selected.append(conv_copy)
                        current_tokens += 50  # 요약 버전 토큰 수
        
        # 시간순 정렬하여 반환
        return sorted(selected, key=lambda x: x.get('created_at', ''))
    
    def _classify_conversation_type(self, conv: Dict) -> str:
        """대화 유형 분류"""
        body = self._extract_conversation_body(conv).lower()
        language = self._detect_language(body)
        
        # 언어별 패턴 매칭
        if language == "ko":
            if any(word in body for word in ["문제", "오류", "에러", "안됩니다", "고장"]):
                return "problem_definition"
            elif any(word in body for word in ["해결", "방법", "시도", "확인해보세요"]):
                return "solution"
            elif any(word in body for word in ["해결됐습니다", "완료", "감사합니다", "닫기"]):
                return "conclusion"
            elif any(word in body for word in ["추가", "더", "또", "그런데"]):
                return "follow_up"
        else:  # English
            if any(word in body for word in ["issue", "problem", "error", "not working", "broken"]):
                return "problem_definition"
            elif any(word in body for word in ["solution", "try", "fix", "resolve", "please check"]):
                return "solution"
            elif any(word in body for word in ["resolved", "fixed", "thank you", "close", "done"]):
                return "conclusion"
            elif any(word in body for word in ["also", "additionally", "another", "furthermore"]):
                return "follow_up"
        
        return "general"
    
    def _calculate_position_weight(self, index: int, total: int) -> float:
        """위치 기반 가중치 계산"""
        if total <= 3:
            return 1.0
        
        # 시작 부분 (첫 3개)
        if index < 3:
            return 0.9
        
        # 끝 부분 (마지막 3개)
        if index >= total - 3:
            return 0.9
        
        # 중간 부분은 균등하게
        return 0.7
    
    def _calculate_context_continuity_score(self, conv: Dict, all_conversations: List[Dict], index: int) -> float:
        """컨텍스트 연결성 점수"""
        if index == 0 or index >= len(all_conversations) - 1:
            return 0.8  # 시작/끝은 기본 높은 점수
        
        current_body = self._extract_conversation_body(conv).lower()
        prev_body = self._extract_conversation_body(all_conversations[index-1]).lower()
        
        # 간단한 연결성 체크 (공통 키워드 비율)
        current_words = set(current_body.split())
        prev_words = set(prev_body.split())
        
        if len(current_words) == 0 or len(prev_words) == 0:
            return 0.5
        
        common_words = current_words.intersection(prev_words)
        continuity_ratio = len(common_words) / max(len(current_words), len(prev_words))
        
        return min(continuity_ratio * 2, 1.0)  # 최대 1.0으로 제한
```

### 4. 설정 가능한 파라미터

#### A. 환경 변수로 제어
```python
# 언어별 최소 대화 길이 (기본값)
LLM_MIN_LENGTH_KO=10
LLM_MIN_LENGTH_EN=20

# 언어별 필터링 강도 (strict/normal/loose)
LLM_FILTER_LEVEL_KO=normal
LLM_FILTER_LEVEL_EN=normal

# 다국어 키워드 파일 경로
LLM_KEYWORDS_KO_PATH=./config/keywords_ko.json
LLM_KEYWORDS_EN_PATH=./config/keywords_en.json
```

#### B. 티켓별 동적 조정 (다국어 환경)
- **단순한 티켓**: 언어에 관계없이 적은 대화 수로도 충분
- **복잡한 티켓**: 언어별 특성 고려한 대화 수 조정
- **다국어 혼재 티켓**: 언어별 중요도 가중치 적용
- **긴 대화 스레드**: 언어별 핵심 포인트 추출 방식 다르게 적용

### 5. 구현 우선순위

#### Phase 1: 기본 필터링 (즉시 구현 가능)
1. 자동응답, 인사말 패턴 제거
2. 너무 짧은 대화 필터링
3. 중복 내용 제거

#### Phase 2: 스마트 선택 (2주 내 구현)
1. 중요도 점수 기반 선택
2. 컨텍스트 연결성 평가
3. 적응형 대화 수 조정

#### Phase 3: AI 기반 필터링 (향후 고도화)
1. LLM을 이용한 대화 중요도 평가
2. 자동 학습 기반 필터링 개선
3. 도메인별 맞춤 필터링

## 고급 필터링 전략: 대화 수 제한 없는 스마트 파이프라인

### 핵심 아이디어: 대화 수 제한 제거 + 3단계 필터링 파이프라인

30-50개 대화가 있는 복잡한 티켓에서도 모든 중요한 맥락을 보존하면서 노이즈만 제거하는 전략:

#### 1단계: 기본 노이즈 제거 (Pre-filtering)
- 자동응답, 시스템 메시지, 단순 인사말 제거
- 중복 내용 병합 (85% 이상 유사도)
- 의미 없는 짧은 대화 제거

#### 2단계: 지능형 중요도 평가 (Smart Scoring)
- 문제 정의, 해결 과정, 결론 등 핵심 포인트 식별
- 시간적 흐름과 논리적 연결성 평가
- 언어별 맞춤 중요도 점수 계산

#### 3단계: 토큰 예산 기반 최적 선택 (Token-aware Selection)
- LLM 토큰 한계 내에서 최대한 많은 대화 포함
- 컨텍스트 연결성 유지하면서 선택적 요약
- 동적 대화 길이 조정 (중요한 대화는 전문, 덜 중요한 것은 요약)

### 고급 필터링 파이프라인 구현

```python
class AdvancedConversationFilter:
    """
    대화 수 제한 없는 고급 필터링 시스템
    - 30-50개 대화도 효과적으로 처리
    - 맥락 보존 우선, 노이즈 제거 부차
    - 토큰 예산 내 최적 선택
    """
    
    def __init__(self, max_tokens: int = 8000, language_weights: Dict[str, float] = None):
        self.max_tokens = max_tokens
        self.language_weights = language_weights or {"ko": 1.0, "en": 1.0}
        self.keyword_cache = {}
        self._load_language_keywords()
    
    def filter_conversations_advanced(self, conversations: List[Dict]) -> List[Dict]:
        """
        고급 3단계 필터링 파이프라인
        대화 수 제한 없이 품질 기반 선택
        """
        if not conversations:
            return []
        
        # 1단계: 기본 노이즈 제거
        cleaned_conversations = self._remove_noise(conversations)
        
        # 2단계: 중요도 기반 평가 및 그룹핑
        scored_conversations = self._calculate_advanced_scores(cleaned_conversations)
        
        # 3단계: 토큰 예산 기반 최적 선택
        selected_conversations = self._select_within_token_budget(scored_conversations)
        
        return selected_conversations
    
    def _remove_noise(self, conversations: List[Dict]) -> List[Dict]:
        """1단계: 기본 노이즈 제거"""
        cleaned = []
        seen_content = set()
        
        for conv in conversations:
            body = self._extract_conversation_body(conv).strip()
            
            # 기본 필터링
            if not self._is_meaningful_conversation_advanced(conv):
                continue
            
            # 중복 제거 (단순 해시 기반)
            content_hash = hash(body.lower()[:100])  # 처음 100자로 중복 판별
            if content_hash in seen_content:
                continue
            seen_content.add(content_hash)
            
            cleaned.append(conv)
        
        return cleaned
    
    def _calculate_advanced_scores(self, conversations: List[Dict]) -> List[Tuple[Dict, float, str]]:
        """2단계: 고급 중요도 점수 계산"""
        scored_conversations = []
        
        for i, conv in enumerate(conversations):
            # 기본 중요도 점수
            importance_score = self._calculate_conversation_priority_advanced(conv)
            
            # 위치 기반 가중치 (시작, 중간 전환점, 끝 부분 중요)
            position_weight = self._calculate_position_weight(i, len(conversations))
            
            # 컨텍스트 연결성 점수
            context_score = self._calculate_context_continuity_score(conv, conversations, i)
            
            # 최종 점수 (0.0 ~ 1.0)
            final_score = (importance_score * 0.5 + position_weight * 0.2 + context_score * 0.3)
            
            # 대화 유형 분류
            conversation_type = self._classify_conversation_type(conv)
            
            scored_conversations.append((conv, final_score, conversation_type))
        
        # 점수순 정렬
        return sorted(scored_conversations, key=lambda x: x[1], reverse=True)
    
    def _select_within_token_budget(self, scored_conversations: List[Tuple[Dict, float, str]]) -> List[Dict]:
        """3단계: 토큰 예산 내 최적 선택"""
        selected = []
        current_tokens = 0
        
        # 필수 대화 우선 선택 (problem_definition, solution, conclusion)
        essential_types = ["problem_definition", "solution", "conclusion"]
        
        # 1. 필수 대화부터 선택
        for conv, score, conv_type in scored_conversations:
            if conv_type in essential_types and current_tokens < self.max_tokens * 0.7:
                body = self._extract_conversation_body(conv)
                estimated_tokens = len(body.split()) * 1.3  # 대략적 토큰 수 추정
                
                if current_tokens + estimated_tokens <= self.max_tokens:
                    selected.append(conv)
                    current_tokens += estimated_tokens
        
        # 2. 남은 예산으로 중요도 순 선택
        for conv, score, conv_type in scored_conversations:
            if conv not in selected:
                body = self._extract_conversation_body(conv)
                estimated_tokens = len(body.split()) * 1.3
                
                # 토큰 예산 내에서 선택
                if current_tokens + estimated_tokens <= self.max_tokens:
                    selected.append(conv)
                    current_tokens += estimated_tokens
                else:
                    # 토큰 예산 초과 시 요약 버전 생성
                    if score > 0.7:  # 중요도가 높으면 요약해서라도 포함
                        summarized_body = body[:150] + "..."  # 간단 요약
                        conv_copy = conv.copy()
                        conv_copy['body'] = summarized_body
                        selected.append(conv_copy)
                        current_tokens += 50  # 요약 버전 토큰 수
        
        # 시간순 정렬하여 반환
        return sorted(selected, key=lambda x: x.get('created_at', ''))
    
    def _classify_conversation_type(self, conv: Dict) -> str:
        """대화 유형 분류"""
        body = self._extract_conversation_body(conv).lower()
        language = self._detect_language(body)
        
        # 언어별 패턴 매칭
        if language == "ko":
            if any(word in body for word in ["문제", "오류", "에러", "안됩니다", "고장"]):
                return "problem_definition"
            elif any(word in body for word in ["해결", "방법", "시도", "확인해보세요"]):
                return "solution"
            elif any(word in body for word in ["해결됐습니다", "완료", "감사합니다", "닫기"]):
                return "conclusion"
            elif any(word in body for word in ["추가", "더", "또", "그런데"]):
                return "follow_up"
        else:  # English
            if any(word in body for word in ["issue", "problem", "error", "not working", "broken"]):
                return "problem_definition"
            elif any(word in body for word in ["solution", "try", "fix", "resolve", "please check"]):
                return "solution"
            elif any(word in body for word in ["resolved", "fixed", "thank you", "close", "done"]):
                return "conclusion"
            elif any(word in body for word in ["also", "additionally", "another", "furthermore"]):
                return "follow_up"
        
        return "general"
    
    def _calculate_position_weight(self, index: int, total: int) -> float:
        """위치 기반 가중치 계산"""
        if total <= 3:
            return 1.0
        
        # 시작 부분 (첫 3개)
        if index < 3:
            return 0.9
        
        # 끝 부분 (마지막 3개)
        if index >= total - 3:
            return 0.9
        
        # 중간 부분은 균등하게
        return 0.7
    
    def _calculate_context_continuity_score(self, conv: Dict, all_conversations: List[Dict], index: int) -> float:
        """컨텍스트 연결성 점수"""
        if index == 0 or index >= len(all_conversations) - 1:
            return 0.8  # 시작/끝은 기본 높은 점수
        
        current_body = self._extract_conversation_body(conv).lower()
        prev_body = self._extract_conversation_body(all_conversations[index-1]).lower()
        
        # 간단한 연결성 체크 (공통 키워드 비율)
        current_words = set(current_body.split())
        prev_words = set(prev_body.split())
        
        if len(current_words) == 0 or len(prev_words) == 0:
            return 0.5
        
        common_words = current_words.intersection(prev_words)
        continuity_ratio = len(common_words) / max(len(current_words), len(prev_words))
        
        return min(continuity_ratio * 2, 1.0)  # 최대 1.0으로 제한
```

### 4. 설정 가능한 파라미터

#### A. 환경 변수로 제어
```python
# 언어별 최소 대화 길이 (기본값)
LLM_MIN_LENGTH_KO=10
LLM_MIN_LENGTH_EN=20

# 언어별 필터링 강도 (strict/normal/loose)
LLM_FILTER_LEVEL_KO=normal
LLM_FILTER_LEVEL_EN=normal

# 다국어 키워드 파일 경로
LLM_KEYWORDS_KO_PATH=./config/keywords_ko.json
LLM_KEYWORDS_EN_PATH=./config/keywords_en.json
```

#### B. 티켓별 동적 조정 (다국어 환경)
- **단순한 티켓**: 언어에 관계없이 적은 대화 수로도 충분
- **복잡한 티켓**: 언어별 특성 고려한 대화 수 조정
- **다국어 혼재 티켓**: 언어별 중요도 가중치 적용
- **긴 대화 스레드**: 언어별 핵심 포인트 추출 방식 다르게 적용

### 5. 구현 우선순위

#### Phase 1: 기본 필터링 (즉시 구현 가능)
1. 자동응답, 인사말 패턴 제거
2. 너무 짧은 대화 필터링
3. 중복 내용 제거

#### Phase 2: 스마트 선택 (2주 내 구현)
1. 중요도 점수 기반 선택
2. 컨텍스트 연결성 평가
3. 적응형 대화 수 조정

#### Phase 3: AI 기반 필터링 (향후 고도화)
1. LLM을 이용한 대화 중요도 평가
2. 자동 학습 기반 필터링 개선
3. 도메인별 맞춤 필터링

## 고급 필터링 전략: 대화 수 제한 없는 스마트 파이프라인

### 핵심 아이디어: 대화 수 제한 제거 + 3단계 필터링 파이프라인

30-50개 대화가 있는 복잡한 티켓에서도 모든 중요한 맥락을 보존하면서 노이즈만 제거하는 전략:

#### 1단계: 기본 노이즈 제거 (Pre-filtering)
- 자동응답, 시스템 메시지, 단순 인사말 제거
- 중복 내용 병합 (85% 이상 유사도)
- 의미 없는 짧은 대화 제거

#### 2단계: 지능형 중요도 평가 (Smart Scoring)
- 문제 정의, 해결 과정, 결론 등 핵심 포인트 식별
- 시간적 흐름과 논리적 연결성 평가
- 언어별 맞춤 중요도 점수 계산

#### 3단계: 토큰 예산 기반 최적 선택 (Token-aware Selection)
- LLM 토큰 한계 내에서 최대한 많은 대화 포함
- 컨텍스트 연결성 유지하면서 선택적 요약
- 동적 대화 길이 조정 (중요한 대화는 전문, 덜 중요한 것은 요약)

### 고급 필터링 파이프라인 구현

```python
class AdvancedConversationFilter:
    """
    대화 수 제한 없는 고급 필터링 시스템
    - 30-50개 대화도 효과적으로 처리
    - 맥락 보존 우선, 노이즈 제거 부차
    - 토큰 예산 내 최적 선택
    """
    
    def __init__(self, max_tokens: int = 8000, language_weights: Dict[str, float] = None):
        self.max_tokens = max_tokens
        self.language_weights = language_weights or {"ko": 1.0, "en": 1.0}
        self.keyword_cache = {}
        self._load_language_keywords()
    
    def filter_conversations_advanced(self, conversations: List[Dict]) -> List[Dict]:
        """
        고급 3단계 필터링 파이프라인
        대화 수 제한 없이 품질 기반 선택
        """
        if not conversations:
            return []
        
        # 1단계: 기본 노이즈 제거
        cleaned_conversations = self._remove_noise(conversations)
        
        # 2단계: 중요도 기반 평가 및 그룹핑
        scored_conversations = self._calculate_advanced_scores(cleaned_conversations)
        
        # 3단계: 토큰 예산 기반 최적 선택
        selected_conversations = self._select_within_token_budget(scored_conversations)
        
        return selected_conversations
    
    def _remove_noise(self, conversations: List[Dict]) -> List[Dict]:
        """1단계: 기본 노이즈 제거"""
        cleaned = []
        seen_content = set()
        
        for conv in conversations:
            body = self._extract_conversation_body(conv).strip()
            
            # 기본 필터링
            if not self._is_meaningful_conversation_advanced(conv):
                continue
            
            # 중복 제거 (단순 해시 기반)
            content_hash = hash(body.lower()[:100])  # 처음 100자로 중복 판별
            if content_hash in seen_content:
                continue
            seen_content.add(content_hash)
            
            cleaned.append(conv)
        
        return cleaned
    
    def _calculate_advanced_scores(self, conversations: List[Dict]) -> List[Tuple[Dict, float, str]]:
        """2단계: 고급 중요도 점수 계산"""
        scored_conversations = []
        
        for i, conv in enumerate(conversations):
            # 기본 중요도 점수
            importance_score = self._calculate_conversation_priority_advanced(conv)
            
            # 위치 기반 가중치 (시작, 중간 전환점, 끝 부분 중요)
            position_weight = self._calculate_position_weight(i, len(conversations))
            
            # 컨텍스트 연결성 점수
            context_score = self._calculate_context_continuity_score(conv, conversations, i)
            
            # 최종 점수 (0.0 ~ 1.0)
            final_score = (importance_score * 0.5 + position_weight * 0.2 + context_score * 0.3)
            
            # 대화 유형 분류
            conversation_type = self._classify_conversation_type(conv)
            
            scored_conversations.append((conv, final_score, conversation_type))
        
        # 점수순 정렬
        return sorted(scored_conversations, key=lambda x: x[1], reverse=True)
    
    def _select_within_token_budget(self, scored_conversations: List[Tuple[Dict, float, str]]) -> List[Dict]:
        """3단계: 토큰 예산 내 최적 선택"""
        selected = []
        current_tokens = 0
        
        # 필수 대화 우선 선택 (problem_definition, solution, conclusion)
        essential_types = ["problem_definition", "solution", "conclusion"]
        
        # 1. 필수 대화부터 선택
        for conv, score, conv_type in scored_conversations:
            if conv_type in essential_types and current_tokens < self.max_tokens * 0.7:
                body = self._extract_conversation_body(conv)
                estimated_tokens = len(body.split()) * 1.3  # 대략적 토큰 수 추정
                
                if current_tokens + estimated_tokens <= self.max_tokens:
                    selected.append(conv)
                    current_tokens += estimated_tokens
        
        # 2. 남은 예산으로 중요도 순 선택
        for conv, score, conv_type in scored_conversations:
            if conv not in selected:
                body = self._extract_conversation_body(conv)
                estimated_tokens = len(body.split()) * 1.3
                
                # 토큰 예산 내에서 선택
                if current_tokens + estimated_tokens <= self.max_tokens:
                    selected.append(conv)
                    current_tokens += estimated_tokens
                else:
                    # 토큰 예산 초과 시 요약 버전 생성
                    if score > 0.7:  # 중요도가 높으면 요약해서라도 포함
                        summarized_body = body[:150] + "..."  # 간단 요약
                        conv_copy = conv.copy()
                        conv_copy['body'] = summarized_body
                        selected.append(conv_copy)
                        current_tokens += 50  # 요약 버전 토큰 수
        
        # 시간순 정렬하여 반환
        return sorted(selected, key=lambda x: x.get('created_at', ''))
    
    def _classify_conversation_type(self, conv: Dict) -> str:
        """대화 유형 분류"""
        body = self._extract_conversation_body(conv).lower()
        language = self._detect_language(body)
        
        # 언어별 패턴 매칭
        if language == "ko":
            if any(word in body for word in ["문제", "오류", "에러", "안됩니다", "고장"]):
                return "problem_definition"
            elif any(word in body for word in ["해결", "방법", "시도", "확인해보세요"]):
                return "solution"
            elif any(word in body for word in ["해결됐습니다", "완료", "감사합니다", "닫기"]):
                return "conclusion"
            elif any(word in body for word in ["추가", "더", "또", "그런데"]):
                return "follow_up"
        else:  # English
            if any(word in body for word in ["issue", "problem", "error", "not working", "broken"]):
                return "problem_definition"
            elif any(word in body for word in ["solution", "try", "fix", "resolve", "please check"]):
                return "solution"
            elif any(word in body for word in ["resolved", "fixed", "thank you", "close", "done"]):
                return "conclusion"
            elif any(word in body for word in ["also", "additionally", "another", "furthermore"]):
                return "follow_up"
        
        return "general"
    
    def _calculate_position_weight(self, index: int, total: int) -> float:
        """위치 기반 가중치 계산"""
        if total <= 3:
            return 1.0
        
        # 시작 부분 (첫 3개)
        if index < 3:
            return 0.9
        
        # 끝 부분 (마지막 3개)
        if index >= total - 3:
            return 0.9
        
        # 중간 부분은 균등하게
        return 0.7
    
    def _calculate_context_continuity_score(self, conv: Dict, all_conversations: List[Dict], index: int) -> float:
        """컨텍스트 연결성 점수"""
        if index == 0 or index >= len(all_conversations) - 1:
            return 0.8  # 시작/끝은 기본 높은 점수
        
        current_body = self._extract_conversation_body(conv).lower()
        prev_body = self._extract_conversation_body(all_conversations[index-1]).lower()
        
        # 간단한 연결성 체크 (공통 키워드 비율)
        current_words = set(current_body.split())
        prev_words = set(prev_body.split())
        
        if len(current_words) == 0 or len(prev_words) == 0:
            return 0.5
        
        common_words = current_words.intersection(prev_words)
        continuity_ratio = len(common_words) / max(len(current_words), len(prev_words))
        
        return min(continuity_ratio * 2, 1.0)  # 최대 1.0으로 제한
```

### 4. 설정 가능한 파라미터

#### A. 환경 변수로 제어
```python
# 언어별 최소 대화 길이 (기본값)
LLM_MIN_LENGTH_KO=10
LLM_MIN_LENGTH_EN=20

# 언어별 필터링 강도 (strict/normal/loose)
LLM_FILTER_LEVEL_KO=normal
LLM_FILTER_LEVEL_EN=normal

# 다국어 키워드 파일 경로
LLM_KEYWORDS_KO_PATH=./config/keywords_ko.json
LLM_KEYWORDS_EN_PATH=./config/keywords_en.json
```

#### B. 티켓별 동적 조정 (다국어 환경)
- **단순한 티켓**: 언어에 관계없이 적은 대화 수