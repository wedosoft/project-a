#!/usr/bin/env python3
"""
개발/테스트용 AWS Secrets Manager 설정 스크립트

이 스크립트는 멀티테넌트 환경을 테스트하기 위해
AWS Secrets Manager에 샘플 테넌트 설정을 생성합니다.

사용법:
    python scripts/setup_test_secrets.py
"""

import json
import boto3
from botocore.exceptions import ClientError
import os
import sys
from pathlib import Path

# 백엔드 디렉토리를 Python 경로에 추가
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from core.config import get_settings, get_llm_keys_manager

def create_test_tenant_secrets():
    """테스트용 테넌트 시크릿들을 AWS Secrets Manager에 생성"""
    
    settings = get_settings()
    
    # AWS Secrets Manager 클라이언트 생성
    try:
        client = boto3.client(
            'secretsmanager',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        print(f"✅ AWS Secrets Manager 클라이언트 초기화 완료 (리전: {settings.AWS_REGION})")
    except Exception as e:
        print(f"❌ AWS 클라이언트 초기화 실패: {e}")
        print("💡 AWS 자격증명을 확인하거나 로컬 테스트를 위해 aws configure를 실행하세요")
        return False
    
    # 테스트용 테넌트 설정들
    test_tenants = [
        {
            "company_id": "wedosoft",
            "platform": "freshdesk", 
            "domain": "wedosoft.freshdesk.com",
            "api_key": "Ug9H1cKCZZtZ4haamBy"
        },
        {
            "company_id": "company-a", 
            "platform": "freshdesk",
            "domain": "companya.freshdesk.com", 
            "api_key": "test-api-key-company-a"
        },
        {
            "company_id": "demo-corp",
            "platform": "freshdesk", 
            "domain": "democorp.freshdesk.com",
            "api_key": "demo-api-key-12345"
        }
    ]
    
    print(f"\n🔐 {len(test_tenants)}개 테스트 테넌트 시크릿 생성 중...")
    
    success_count = 0
    for tenant in test_tenants:
        if create_tenant_secret(client, tenant):
            success_count += 1
    
    print(f"\n✅ {success_count}/{len(test_tenants)}개 테넌트 시크릿 생성 완료")
    
    if success_count > 0:
        print("\n📋 생성된 테넌트 목록:")
        for tenant in test_tenants[:success_count]:
            print(f"  - {tenant['company_id']} ({tenant['platform']}): {tenant['domain']}")
        
        print("\n🧪 테스트 방법:")
        print("1. API 요청 시 다음 헤더 사용:")
        print("   X-Company-ID: wedosoft")
        print("   X-Platform: freshdesk") 
        print("   X-Domain: wedosoft.freshdesk.com")
        print("   X-API-Key: (Secrets Manager에서 자동 조회)")
        
        print("\n2. 다른 테넌트 테스트:")
        print("   X-Company-ID: company-a")
        print("   X-Platform: freshdesk")
        print("   등등...")
    
    return success_count > 0

def create_tenant_secret(client, tenant_config):
    """개별 테넌트 시크릿 생성"""
    
    secret_name = f"tenant-configs/{tenant_config['company_id']}"
    secret_value = {
        "platform": tenant_config["platform"],
        "domain": tenant_config["domain"], 
        "api_key": tenant_config["api_key"]
    }
    
    try:
        # 시크릿이 이미 존재하는지 확인
        try:
            client.describe_secret(SecretId=secret_name)
            
            # 존재하면 업데이트
            client.update_secret(
                SecretId=secret_name,
                SecretString=json.dumps(secret_value)
            )
            print(f"🔄 업데이트: {secret_name}")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                # 존재하지 않으면 생성
                client.create_secret(
                    Name=secret_name,
                    SecretString=json.dumps(secret_value),
                    Description=f"멀티테넌트 설정 - {tenant_config['company_id']} ({tenant_config['platform']})"
                )
                print(f"✨ 생성: {secret_name}")
            else:
                raise
        
        return True
        
    except Exception as e:
        print(f"❌ 시크릿 생성/업데이트 실패 ({secret_name}): {e}")
        return False

def list_tenant_secrets():
    """생성된 테넌트 시크릿들 조회"""
    
    settings = get_settings()
    
    try:
        client = boto3.client(
            'secretsmanager',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID, 
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        
        # tenant-configs/ 접두사를 가진 시크릿들 조회
        response = client.list_secrets(
            Filters=[
                {
                    'Key': 'name',
                    'Values': ['tenant-configs/']
                }
            ]
        )
        
        secrets = response.get('SecretList', [])
        
        if not secrets:
            print("📭 생성된 테넌트 시크릿이 없습니다")
            return
        
        print(f"\n📋 생성된 테넌트 시크릿 목록 ({len(secrets)}개):")
        
        for secret in secrets:
            secret_name = secret['Name']
            company_id = secret_name.replace('tenant-configs/', '')
            
            try:
                # 시크릿 값 조회
                secret_response = client.get_secret_value(SecretId=secret_name)
                secret_data = json.loads(secret_response['SecretString'])
                
                print(f"  🏢 {company_id}")
                print(f"     플랫폼: {secret_data.get('platform', 'N/A')}")
                print(f"     도메인: {secret_data.get('domain', 'N/A')}")
                print(f"     API 키: {secret_data.get('api_key', 'N/A')[:8]}...")
                print()
                
            except Exception as e:
                print(f"  ❌ {company_id}: 조회 실패 ({e})")
        
    except Exception as e:
        print(f"❌ 시크릿 목록 조회 실패: {e}")

def delete_test_secrets():
    """테스트용 시크릿들 삭제"""
    
    settings = get_settings()
    
    try:
        client = boto3.client(
            'secretsmanager',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        
        # tenant-configs/ 접두사를 가진 시크릿들 조회
        response = client.list_secrets(
            Filters=[
                {
                    'Key': 'name', 
                    'Values': ['tenant-configs/']
                }
            ]
        )
        
        secrets = response.get('SecretList', [])
        
        if not secrets:
            print("📭 삭제할 테넌트 시크릿이 없습니다")
            return
        
        print(f"🗑️  {len(secrets)}개 테넌트 시크릿 삭제 중...")
        
        for secret in secrets:
            secret_name = secret['Name']
            try:
                client.delete_secret(
                    SecretId=secret_name,
                    ForceDeleteWithoutRecovery=True
                )
                print(f"✅ 삭제됨: {secret_name}")
            except Exception as e:
                print(f"❌ 삭제 실패 ({secret_name}): {e}")
        
        print("🧹 테스트 시크릿 정리 완료")
        
    except Exception as e:
        print(f"❌ 시크릿 삭제 실패: {e}")

def create_global_llm_secrets():
    """전역 LLM API 키들을 AWS Secrets Manager에 생성"""
    
    settings = get_settings()
    llm_manager = get_llm_keys_manager()
    
    # 환경변수에서 LLM API 키들 수집
    llm_keys = {}
    
    if settings.ANTHROPIC_API_KEY:
        llm_keys["anthropic_api_key"] = settings.ANTHROPIC_API_KEY
    if settings.OPENAI_API_KEY:
        llm_keys["openai_api_key"] = settings.OPENAI_API_KEY
    if settings.GOOGLE_API_KEY:
        llm_keys["google_api_key"] = settings.GOOGLE_API_KEY
    if settings.PERPLEXITY_API_KEY:
        llm_keys["perplexity_api_key"] = settings.PERPLEXITY_API_KEY
    if settings.DEEPSEEK_API_KEY:
        llm_keys["deepseek_api_key"] = settings.DEEPSEEK_API_KEY
    if settings.OPENROUTER_API_KEY:
        llm_keys["openrouter_api_key"] = settings.OPENROUTER_API_KEY
    
    if not llm_keys:
        print("⚠️  환경변수에 LLM API 키가 설정되지 않았습니다")
        return False
    
    print(f"🔑 {len(llm_keys)}개 전역 LLM API 키를 Secrets Manager에 저장 중...")
    
    success = llm_manager.save_llm_keys_to_secrets(llm_keys)
    
    if success:
        print("✅ 전역 LLM API 키 저장 완료")
        print("📋 저장된 LLM 제공자:")
        for key in llm_keys.keys():
            provider = key.replace("_api_key", "")
            print(f"  - {provider}")
        
        print("\n💡 이제 환경변수에서 LLM API 키를 제거하고 Secrets Manager에서 자동 로드됩니다")
        return True
    else:
        print("❌ 전역 LLM API 키 저장 실패")
        return False

def test_llm_key_retrieval():
    """LLM API 키 조회 테스트"""
    
    print("🧪 LLM API 키 조회 테스트 중...")
    
    llm_manager = get_llm_keys_manager()
    
    providers = ["anthropic", "openai", "google", "perplexity", "deepseek", "openrouter"]
    
    for provider in providers:
        api_key = llm_manager.get_llm_api_key(provider)
        if api_key:
            print(f"✅ {provider}: {api_key[:8]}..." if len(api_key) > 8 else f"✅ {provider}: {api_key}")
        else:
            print(f"❌ {provider}: 키를 찾을 수 없음")
    
    print("🔍 조회 테스트 완료")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="AWS Secrets Manager 테넌트 시크릿 관리")
    parser.add_argument("action", choices=["create", "list", "delete", "llm-create", "llm-test"], 
                       help="수행할 작업 (create: 테넌트 생성, list: 조회, delete: 삭제, llm-create: LLM 키 생성, llm-test: LLM 키 테스트)")
    
    args = parser.parse_args()
    
    print("🔐 AWS Secrets Manager 테넌트 시크릿 관리 도구")
    print("=" * 50)
    
    if args.action == "create":
        create_test_tenant_secrets()
    elif args.action == "list":
        list_tenant_secrets()
    elif args.action == "delete":
        delete_test_secrets()
    elif args.action == "llm-create":
        create_global_llm_secrets()
    elif args.action == "llm-test":
        test_llm_key_retrieval()
