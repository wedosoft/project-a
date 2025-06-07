# 첨부파일 URL 만료 문제 해결 가이드

## 🔍 **문제 상황**

Freshdesk에서 수집된 첨부파일 URL이 pre-signed URL (300초 만료) 형태로 저장되어 있어, 나중에 사용자가 접근할 때 404 오류가 발생하는 문제입니다.

## 💡 **해결 방안**

### 1. 백엔드 API 엔드포인트 활용

새로 구현된 `/attachments/{attachment_id}/download-url` API를 사용하여 실시간으로 유효한 URL을 발급받습니다.

### 2. 프론트엔드 구현 방법

#### A. JavaScript/TypeScript 예시

```javascript
// 첨부파일 다운로드 URL 발급 함수
async function getAttachmentDownloadUrl(attachmentId, ticketId = null, conversationId = null) {
    try {
        const params = new URLSearchParams();
        if (ticketId) params.append('ticket_id', ticketId);
        if (conversationId) params.append('conversation_id', conversationId);
        
        const response = await fetch(
            `/api/attachments/${attachmentId}/download-url?${params.toString()}`,
            {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Company-Id': 'your-company-id'  // 회사 ID 설정
                }
            }
        );
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        return data.download_url;
        
    } catch (error) {
        console.error('첨부파일 URL 발급 실패:', error);
        throw error;
    }
}

// 이미지 표시 예시
async function displayAttachmentImage(attachmentId, ticketId, imgElement) {
    try {
        // 로딩 상태 표시
        imgElement.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCI+PC9zdmc+'; // 빈 이미지
        imgElement.alt = '로딩 중...';
        
        // 새로운 URL 발급
        const downloadUrl = await getAttachmentDownloadUrl(attachmentId, ticketId);
        
        // 이미지 설정
        imgElement.src = downloadUrl;
        imgElement.alt = '첨부파일 이미지';
        
    } catch (error) {
        console.error('이미지 로드 실패:', error);
        imgElement.src = '/static/images/error-placeholder.png';
        imgElement.alt = '이미지 로드 실패';
    }
}

// 다중 첨부파일 URL 발급 (성능 최적화)
async function getBulkAttachmentUrls(attachmentIds, ticketId = null) {
    try {
        const params = new URLSearchParams({
            attachment_ids: attachmentIds.join(',')
        });
        if (ticketId) params.append('ticket_id', ticketId);
        
        const response = await fetch(
            `/api/attachments/bulk-urls?${params.toString()}`,
            {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Company-Id': 'your-company-id'
                }
            }
        );
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
        
    } catch (error) {
        console.error('다중 첨부파일 URL 발급 실패:', error);
        throw error;
    }
}
```

#### B. React 컴포넌트 예시

```jsx
import React, { useState, useEffect } from 'react';

const AttachmentImage = ({ attachmentId, ticketId, alt = "첨부파일" }) => {
    const [imageUrl, setImageUrl] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    
    useEffect(() => {
        let isMounted = true;
        
        const loadImage = async () => {
            try {
                setLoading(true);
                setError(null);
                
                const url = await getAttachmentDownloadUrl(attachmentId, ticketId);
                
                if (isMounted) {
                    setImageUrl(url);
                }
            } catch (err) {
                if (isMounted) {
                    setError(err.message);
                }
            } finally {
                if (isMounted) {
                    setLoading(false);
                }
            }
        };
        
        loadImage();
        
        return () => {
            isMounted = false;
        };
    }, [attachmentId, ticketId]);
    
    if (loading) {
        return <div className="attachment-loading">이미지 로딩 중...</div>;
    }
    
    if (error) {
        return (
            <div className="attachment-error">
                <span>이미지 로드 실패: {error}</span>
                <button onClick={() => window.location.reload()}>
                    다시 시도
                </button>
            </div>
        );
    }
    
    return (
        <img 
            src={imageUrl} 
            alt={alt}
            className="attachment-image"
            onError={(e) => {
                e.target.src = '/static/images/error-placeholder.png';
                setError('이미지 표시 실패');
            }}
        />
    );
};

export default AttachmentImage;
```

#### C. Vue.js 컴포넌트 예시

```vue
<template>
  <div class="attachment-container">
    <div v-if="loading" class="loading">
      이미지 로딩 중...
    </div>
    <div v-else-if="error" class="error">
      <span>{{ error }}</span>
      <button @click="reloadImage">다시 시도</button>
    </div>
    <img 
      v-else
      :src="imageUrl" 
      :alt="alt"
      class="attachment-image"
      @error="handleImageError"
    />
  </div>
</template>

<script>
export default {
  name: 'AttachmentImage',
  props: {
    attachmentId: {
      type: [String, Number],
      required: true
    },
    ticketId: {
      type: [String, Number],
      default: null
    },
    alt: {
      type: String,
      default: '첨부파일'
    }
  },
  data() {
    return {
      imageUrl: null,
      loading: true,
      error: null
    };
  },
  async mounted() {
    await this.loadImage();
  },
  methods: {
    async loadImage() {
      try {
        this.loading = true;
        this.error = null;
        
        const url = await getAttachmentDownloadUrl(this.attachmentId, this.ticketId);
        this.imageUrl = url;
        
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },
    async reloadImage() {
      await this.loadImage();
    },
    handleImageError() {
      this.error = '이미지 표시 실패';
    }
  }
};
</script>

<style scoped>
.attachment-container {
  display: inline-block;
}

.loading, .error {
  padding: 10px;
  text-align: center;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.error {
  color: #d32f2f;
  background-color: #ffebee;
}

.attachment-image {
  max-width: 100%;
  height: auto;
}
</style>
```

### 4. 캐싱 전략 (선택사항)

```javascript
// URL 캐싱을 통한 성능 최적화
class AttachmentUrlCache {
    constructor(ttl = 240000) { // 4분 캐시 (Freshdesk URL 만료 전)
        this.cache = new Map();
        this.ttl = ttl;
    }
    
    set(key, value) {
        const expiry = Date.now() + this.ttl;
        this.cache.set(key, { value, expiry });
    }
    
    get(key) {
        const item = this.cache.get(key);
        if (!item) return null;
        
        if (Date.now() > item.expiry) {
            this.cache.delete(key);
            return null;
        }
        
        return item.value;
    }
    
    clear() {
        this.cache.clear();
    }
}

const urlCache = new AttachmentUrlCache();

// 캐시를 활용한 URL 발급 함수
async function getCachedAttachmentUrl(attachmentId, ticketId) {
    const cacheKey = `${attachmentId}_${ticketId || 'no_ticket'}`;
    
    // 캐시 확인
    let url = urlCache.get(cacheKey);
    if (url) {
        return url;
    }
    
    // 새로운 URL 발급
    url = await getAttachmentDownloadUrl(attachmentId, ticketId);
    
    // 캐시에 저장
    urlCache.set(cacheKey, url);
    
    return url;
}
```

## 🚀 **구현 단계**

### 1단계: 백엔드 API 테스트
```bash
# 첨부파일 URL 발급 테스트
curl -X GET "http://localhost:8000/attachments/12345/download-url?ticket_id=67890" \
  -H "Company-Id: your-company-id"
```

### 2단계: 프론트엔드 통합
- 기존 첨부파일 표시 로직을 새로운 API 호출로 교체
- 로딩 상태 및 오류 처리 로직 추가
- 성능 최적화를 위한 캐싱 구현

### 3단계: 테스트 및 최적화
- 다양한 첨부파일 타입으로 테스트
- 네트워크 오류 상황 테스트
- 성능 모니터링 및 최적화

## 📝 **주의사항**

1. **API 호출 빈도**: 동일한 첨부파일에 대해 반복 호출을 피하기 위해 캐싱 사용
2. **에러 처리**: 네트워크 오류, 404 오류 등에 대한 적절한 사용자 피드백 제공
3. **성능**: 다중 첨부파일 처리 시 bulk API 활용
4. **보안**: Company-Id 헤더를 통한 적절한 권한 확인

## 🔧 **문제 해결**

### 자주 발생하는 오류

1. **404 Not Found**: 첨부파일 ID가 잘못되었거나 티켓 ID가 누락된 경우
2. **429 Too Many Requests**: Freshdesk API 호출 한도 초과
3. **502 Bad Gateway**: Freshdesk 서버 일시적 오류

### 해결 방법

- 적절한 재시도 로직 구현
- 에러 상황에 대한 사용자 친화적 메시지 제공
- 캐싱을 통한 불필요한 API 호출 감소

이 가이드를 따라 구현하면 Freshdesk 첨부파일 URL 만료 문제를 완전히 해결할 수 있습니다.
