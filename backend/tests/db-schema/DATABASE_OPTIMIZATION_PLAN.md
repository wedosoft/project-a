# 🗄️ SQLite 데이터베이스 최적화 계획서

> **현재 상황**: 1.2GB → **목표**: 254MB (80% 절약)

## 🚨 **긴급도별 최적화 계획**

### **Phase 1: 즉시 실행 가능 (1-2시간)**
**예상 절약: 360MB (28%)**

#### 1️⃣ **JSON 데이터 압축** 🔥
```python
# 구현 방법
import zlib
import json

def compress_json_field(data):
    """JSON 데이터를 압축하여 저장"""
    json_str = json.dumps(data, ensure_ascii=False)
    compressed = zlib.compress(json_str.encode('utf-8'))
    return compressed

def decompress_json_field(compressed_data):
    """압축된 JSON 데이터를 복원"""
    decompressed = zlib.decompress(compressed_data)
    return json.loads(decompressed.decode('utf-8'))
```

**대상 테이블 & 절약 효과:**
- `tickets.raw_data`: 203MB → 61MB (70% 절약)
- `conversations.raw_data`: 141MB → 42MB (70% 절약) 
- `knowledge_base.raw_data`: 16MB → 5MB (70% 절약)

#### 2️⃣ **불필요한 텍스트 중복 제거**
```sql
-- description과 description_text 중복 제거
ALTER TABLE tickets DROP COLUMN description; -- HTML 버전 삭제
-- body와 body_text 중복 제거  
ALTER TABLE conversations DROP COLUMN body; -- HTML 버전 삭제
```

---

### **Phase 2: 구조적 재설계 (2-3일)**
**예상 절약: 508MB (40%)**

#### 🏗️ **통합 저장소 구조 재설계**

**현재 문제:**
```
tickets 테이블 (508MB) + integrated_objects 테이블 (508MB) = 1016MB 중복!
```

**해결 방안: 하이브리드 저장소**
```python
# 새로운 저장 구조
class OptimizedStorage:
    """최적화된 하이브리드 저장소"""
    
    def __init__(self, company_id: str, platform: str):
        self.company_id = company_id
        self.platform = platform
        
    def store_ticket(self, ticket_data: dict):
        """최적화된 티켓 저장"""
        
        # 1. 메타데이터만 SQLite에 저장
        metadata = {
            'id': ticket_data['id'],
            'company_id': self.company_id,
            'platform': self.platform,
            'subject': ticket_data.get('subject'),
            'status': ticket_data.get('status'),
            'created_at': ticket_data.get('created_at'),
            'updated_at': ticket_data.get('updated_at'),
            # 검색용 텍스트만 저장
            'search_text': self.extract_search_text(ticket_data),
            # 압축된 상세 데이터 참조
            'data_ref': f"{self.company_id}/{self.platform}/tickets/{ticket_data['id']}.json.gz"
        }
        
        # 2. 상세 데이터는 압축하여 외부 저장
        self.store_compressed_data(ticket_data, metadata['data_ref'])
        
        # 3. 메타데이터만 DB에 저장
        self.db.insert_ticket_metadata(metadata)
```

**새로운 테이블 구조:**
```sql
-- 경량화된 메타데이터 테이블
CREATE TABLE tickets_meta (
    id INTEGER PRIMARY KEY,
    original_id TEXT NOT NULL,
    company_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    subject TEXT,
    status TEXT,
    priority TEXT,
    created_at TEXT,
    updated_at TEXT,
    search_text TEXT,        -- 검색용 텍스트만
    data_ref TEXT,          -- 압축 데이터 참조
    summary TEXT,           -- LLM 요약
    UNIQUE(company_id, platform, original_id)
);

-- 압축된 데이터는 외부 파일시스템에 저장
-- data/{company_id}/{platform}/tickets/{id}.json.gz
```

---

### **Phase 3: 고급 최적화 (1주)**
**추가 절약: 50-100MB**

#### 3️⃣ **인텔리전트 데이터 분할**
```python
class IntelligentDataManager:
    """지능형 데이터 관리"""
    
    def classify_data_importance(self, ticket_data):
        """데이터 중요도 분류"""
        
        # Hot data (빈번 접근)
        if ticket_data.get('status') in ['open', 'pending']:
            return 'hot'
            
        # Warm data (가끔 접근)
        elif ticket_data.get('updated_at') > '2024-01-01':
            return 'warm'
            
        # Cold data (아카이브)
        else:
            return 'cold'
    
    def store_by_temperature(self, data, importance):
        """중요도별 저장 전략"""
        
        if importance == 'hot':
            # SQLite + 메모리 캐시
            self.store_in_sqlite(data)
            self.cache_in_memory(data)
            
        elif importance == 'warm':
            # 압축 파일 저장
            self.store_compressed(data)
            
        else:  # cold
            # 고압축 아카이브
            self.archive_data(data)
```

---

## 🛠️ **구현 로드맵**

### **즉시 실행 (오늘)**
```bash
# 1. 백업 생성
cp wedosoft_freshdesk_data.db wedosoft_freshdesk_data_backup_$(date +%Y%m%d).db

# 2. JSON 압축 스크립트 실행
python optimize_json_compression.py

# 3. 중복 컬럼 제거
python remove_duplicate_columns.py
```

### **단계별 마이그레이션 (내일부터)**
```python
# Day 1-2: 새로운 저장소 구조 구현
# Day 3-4: 데이터 마이그레이션
# Day 5-6: 검증 및 튜닝
# Day 7: 운영 전환
```

---

## 📊 **예상 결과**

### **최적화 전 vs 후**
| 항목 | 현재 | 최적화 후 | 절약률 |
|------|------|-----------|--------|
| **총 크기** | 1,270MB | 254MB | **80%** |
| **티켓 데이터** | 508MB | 102MB | 80% |
| **대화 데이터** | 141MB | 42MB | 70% |
| **통합 객체** | 508MB | 0MB | 100% |
| **검색 성능** | 현재 | **3-5배 향상** | - |

### **부가 효과**
- ✅ **메모리 사용량 70% 감소**
- ✅ **백업 시간 80% 단축**  
- ✅ **검색 속도 3-5배 향상**
- ✅ **벡터DB 동기화 속도 향상**

---

## ⚠️ **주의사항**

### **마이그레이션 리스크**
1. **데이터 손실 방지**: 각 단계마다 백업 필수
2. **서비스 중단 최소화**: 점진적 마이그레이션
3. **호환성 유지**: 기존 API 인터페이스 보존

### **롤백 계획**
```python
# 각 단계별 롤백 스크립트 준비
rollback_phase1.py  # JSON 압축 롤백
rollback_phase2.py  # 구조 변경 롤백
rollback_phase3.py  # 전체 롤백
```

---

**🎯 결론: 이 최적화를 통해 1.2GB → 254MB로 80% 감소시킬 수 있으며, 성능도 크게 향상될 것입니다.**
