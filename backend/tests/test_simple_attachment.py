#!/usr/bin/env python
"""
이미지 첨부파일 처리 로직 테스트 스크립트 (간소화 버전)
"""

import os
import sys
import json

# 테스트 데이터
test_data = [
    {
        # 'attachments' 키를 사용하는 메타데이터
        "metadata": {
            "attachments": json.dumps([
                {
                    "name": "sample_image.jpg",
                    "url": "http://example.com/sample_image.jpg",
                    "content_type": "image/jpeg"
                }
            ])
        }
    },
    {
        # 'image_attachments' 키를 사용하는 메타데이터
        "metadata": {
            "image_attachments": json.dumps([
                {
                    "name": "other_image.png",
                    "url": "http://example.com/other_image.png",
                    "content_type": "image/png"
                }
            ])
        }
    },
    {
        # 첨부파일이 없는 메타데이터
        "metadata": {
            "title": "No attachments here"
        }
    }
]

def original_logic():
    """원래 이미지 정보를 가져오는 로직 - 'image_attachments' 키만 사용"""
    context_images = []
    
    for i, metadata_wrapper in enumerate(test_data):
        metadata = metadata_wrapper["metadata"]
        image_attachments = metadata.get("image_attachments", "")
        
        if image_attachments:
            print(f"원래 로직 - 문서 #{i+1}: 이미지 데이터 발견")
            if isinstance(image_attachments, str):
                image_attachments = json.loads(image_attachments)
                
            if isinstance(image_attachments, list):
                for img in image_attachments:
                    context_images.append({
                        "name": img.get("name", ""),
                        "url": img.get("url", ""),
                        "content_type": img.get("content_type", "")
                    })
        else:
            print(f"원래 로직 - 문서 #{i+1}: 이미지 데이터 없음")
    
    return context_images

def fixed_logic():
    """수정된 이미지 정보를 가져오는 로직 - 'image_attachments'와 'attachments' 키 모두 사용"""
    context_images = []
    
    for i, metadata_wrapper in enumerate(test_data):
        metadata = metadata_wrapper["metadata"]
        image_attachments = metadata.get("image_attachments", metadata.get("attachments", ""))
        
        if image_attachments:
            print(f"수정 로직 - 문서 #{i+1}: 이미지 데이터 발견")
            if isinstance(image_attachments, str):
                image_attachments = json.loads(image_attachments)
                
            if isinstance(image_attachments, list):
                for img in image_attachments:
                    context_images.append({
                        "name": img.get("name", ""),
                        "url": img.get("url", ""),
                        "content_type": img.get("content_type", "")
                    })
        else:
            print(f"수정 로직 - 문서 #{i+1}: 이미지 데이터 없음")
    
    return context_images

if __name__ == "__main__":
    print("=== 이미지 첨부파일 처리 로직 테스트 ===")
    
    print("\n원래 로직 테스트:")
    original_images = original_logic()
    print(f"원래 로직으로 찾은 이미지 수: {len(original_images)}")
    
    print("\n수정 로직 테스트:")
    fixed_images = fixed_logic()
    print(f"수정 로직으로 찾은 이미지 수: {len(fixed_images)}")
    
    print("\n=== 결과 비교 ===")
    print(f"원래 로직: {len(original_images)}개 이미지 찾음")
    print(f"수정 로직: {len(fixed_images)}개 이미지 찾음")
    
    if len(fixed_images) > len(original_images):
        print("테스트 성공: 수정된 로직이 더 많은 이미지를 찾았습니다!")
    elif len(fixed_images) == len(original_images):
        print("테스트 불확실: 두 로직 모두 같은 수의 이미지를 찾았습니다.")
    else:
        print("테스트 실패: 원래 로직이 더 많은 이미지를 찾았습니다.")
    
    print("\n=== 이미지 정보 출력 ===")
    for i, img in enumerate(fixed_images):
        print(f"이미지 #{i+1}:")
        print(f"  이름: {img['name']}")
        print(f"  URL: {img['url']}")
        print(f"  타입: {img['content_type']}")