"""
중앙집중식 설정 관리 시스템

개발 환경에서는 YAML 파일과 환경변수를 사용하고,
클라우드 배포시에는 AWS Secrets Manager, Azure Key Vault, 
Kubernetes ConfigMap/Secret 등을 지원합니다.
"""

import os
import yaml
import json
import logging
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import asyncio
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class ConfigSource(Enum):
    """설정 소스 타입"""
    YAML_FILE = "yaml_file"
    ENVIRONMENT_VARS = "environment_vars"
    AWS_SECRETS_MANAGER = "aws_secrets_manager"
    AZURE_KEY_VAULT = "azure_key_vault"
    KUBERNETES_CONFIGMAP = "kubernetes_configmap"
    KUBERNETES_SECRET = "kubernetes_secret"
    CONSUL = "consul"
    ETCD = "etcd"


@dataclass
class ConfigSourceInfo:
    """설정 소스 정보"""
    source_type: ConfigSource
    priority: int  # 낮을수록 높은 우선순위
    enabled: bool
    config: Dict[str, Any]


class ConfigProvider(ABC):
    """설정 제공자 추상 클래스"""
    
    @abstractmethod
    async def load_config(self, key: str) -> Optional[Dict[str, Any]]:
        """설정 로드"""
        pass
    
    @abstractmethod
    async def save_config(self, key: str, config: Dict[str, Any]) -> bool:
        """설정 저장"""
        pass
    
    @abstractmethod
    async def list_keys(self) -> List[str]:
        """사용 가능한 키 목록"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """헬스체크"""
        pass


class YamlFileProvider(ConfigProvider):
    """YAML 파일 기반 설정 제공자"""
    
    def __init__(self, config_dir: str):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    async def load_config(self, key: str) -> Optional[Dict[str, Any]]:
        """YAML 파일에서 설정 로드"""
        try:
            config_file = self.config_dir / f"{key}.yaml"
            if not config_file.exists():
                return None
            
            with open(config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"YAML 파일 로드 실패 {key}: {e}")
            return None
    
    async def save_config(self, key: str, config: Dict[str, Any]) -> bool:
        """YAML 파일에 설정 저장"""
        try:
            config_file = self.config_dir / f"{key}.yaml"
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)
            return True
        except Exception as e:
            logger.error(f"YAML 파일 저장 실패 {key}: {e}")
            return False
    
    async def list_keys(self) -> List[str]:
        """YAML 파일 목록"""
        try:
            return [f.stem for f in self.config_dir.glob("*.yaml")]
        except Exception:
            return []
    
    async def health_check(self) -> bool:
        """디렉토리 접근 가능 여부 확인"""
        return self.config_dir.exists() and os.access(self.config_dir, os.R_OK | os.W_OK)


class EnvironmentVarProvider(ConfigProvider):
    """환경변수 기반 설정 제공자"""
    
    def __init__(self, prefix: str = "LLM_"):
        self.prefix = prefix
    
    async def load_config(self, key: str) -> Optional[Dict[str, Any]]:
        """환경변수에서 설정 로드"""
        try:
            # JSON 형태의 환경변수 지원
            env_key = f"{self.prefix}{key.upper()}"
            env_value = os.getenv(env_key)
            
            if env_value:
                try:
                    return json.loads(env_value)
                except json.JSONDecodeError:
                    # 단일 값인 경우
                    return {"value": env_value}
            
            # 개별 환경변수들을 딕셔너리로 수집
            config = {}
            env_prefix = f"{self.prefix}{key.upper()}_"
            
            for env_var, value in os.environ.items():
                if env_var.startswith(env_prefix):
                    config_key = env_var[len(env_prefix):].lower()
                    config[config_key] = value
            
            return config if config else None
            
        except Exception as e:
            logger.error(f"환경변수 로드 실패 {key}: {e}")
            return None
    
    async def save_config(self, key: str, config: Dict[str, Any]) -> bool:
        """환경변수에 설정 저장 (JSON 형태)"""
        try:
            env_key = f"{self.prefix}{key.upper()}"
            os.environ[env_key] = json.dumps(config)
            return True
        except Exception as e:
            logger.error(f"환경변수 저장 실패 {key}: {e}")
            return False
    
    async def list_keys(self) -> List[str]:
        """환경변수 키 목록"""
        keys = set()
        for env_var in os.environ.keys():
            if env_var.startswith(self.prefix):
                # LLM_MODEL_REGISTRY -> model_registry
                key = env_var[len(self.prefix):].split('_')[0].lower()
                keys.add(key)
        return list(keys)
    
    async def health_check(self) -> bool:
        """항상 사용 가능"""
        return True


class AWSSecretsManagerProvider(ConfigProvider):
    """AWS Secrets Manager 기반 설정 제공자"""
    
    def __init__(self, region_name: str = "us-east-1", prefix: str = "llm/"):
        self.region_name = region_name
        self.prefix = prefix
        self.client = None
        
    def _get_client(self):
        """AWS 클라이언트 초기화"""
        if self.client is None:
            try:
                import boto3
                self.client = boto3.client('secretsmanager', region_name=self.region_name)
            except ImportError:
                logger.error("boto3가 설치되지 않았습니다: pip install boto3")
                raise
            except Exception as e:
                logger.error(f"AWS Secrets Manager 클라이언트 생성 실패: {e}")
                raise
        return self.client
    
    async def load_config(self, key: str) -> Optional[Dict[str, Any]]:
        """AWS Secrets Manager에서 설정 로드"""
        try:
            client = self._get_client()
            secret_name = f"{self.prefix}{key}"
            
            response = client.get_secret_value(SecretId=secret_name)
            secret_value = response['SecretString']
            
            return json.loads(secret_value)
            
        except Exception as e:
            logger.error(f"AWS Secrets Manager 로드 실패 {key}: {e}")
            return None
    
    async def save_config(self, key: str, config: Dict[str, Any]) -> bool:
        """AWS Secrets Manager에 설정 저장"""
        try:
            client = self._get_client()
            secret_name = f"{self.prefix}{key}"
            secret_value = json.dumps(config, ensure_ascii=False)
            
            try:
                # 기존 시크릿 업데이트
                client.update_secret(
                    SecretId=secret_name,
                    SecretString=secret_value
                )
            except client.exceptions.ResourceNotFoundException:
                # 새 시크릿 생성
                client.create_secret(
                    Name=secret_name,
                    SecretString=secret_value,
                    Description=f"LLM configuration for {key}"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"AWS Secrets Manager 저장 실패 {key}: {e}")
            return False
    
    async def list_keys(self) -> List[str]:
        """AWS Secrets Manager 키 목록"""
        try:
            client = self._get_client()
            paginator = client.get_paginator('list_secrets')
            
            keys = []
            for page in paginator.paginate():
                for secret in page['SecretList']:
                    name = secret['Name']
                    if name.startswith(self.prefix):
                        key = name[len(self.prefix):]
                        keys.append(key)
            
            return keys
            
        except Exception as e:
            logger.error(f"AWS Secrets Manager 키 목록 조회 실패: {e}")
            return []
    
    async def health_check(self) -> bool:
        """AWS Secrets Manager 연결 확인"""
        try:
            client = self._get_client()
            client.list_secrets(MaxResults=1)
            return True
        except Exception:
            return False


class KubernetesProvider(ConfigProvider):
    """Kubernetes ConfigMap/Secret 기반 설정 제공자"""
    
    def __init__(self, namespace: str = "default", use_secrets: bool = False):
        self.namespace = namespace
        self.use_secrets = use_secrets
        self.client = None
        
    def _get_client(self):
        """Kubernetes 클라이언트 초기화"""
        if self.client is None:
            try:
                from kubernetes import client, config
                
                # 클러스터 내부에서 실행 중인지 확인
                try:
                    config.load_incluster_config()
                except config.ConfigException:
                    # 로컬 개발 환경
                    config.load_kube_config()
                
                self.client = client.CoreV1Api()
                
            except ImportError:
                logger.error("kubernetes 패키지가 설치되지 않았습니다: pip install kubernetes")
                raise
            except Exception as e:
                logger.error(f"Kubernetes 클라이언트 생성 실패: {e}")
                raise
                
        return self.client
    
    async def load_config(self, key: str) -> Optional[Dict[str, Any]]:
        """Kubernetes ConfigMap/Secret에서 설정 로드"""
        try:
            client = self._get_client()
            
            if self.use_secrets:
                response = client.read_namespaced_secret(
                    name=f"llm-{key}",
                    namespace=self.namespace
                )
                # Secret 데이터는 base64 인코딩됨
                import base64
                data = {}
                for k, v in response.data.items():
                    decoded_value = base64.b64decode(v).decode('utf-8')
                    try:
                        data[k] = json.loads(decoded_value)
                    except json.JSONDecodeError:
                        data[k] = decoded_value
                return data
            else:
                response = client.read_namespaced_config_map(
                    name=f"llm-{key}",
                    namespace=self.namespace
                )
                data = {}
                for k, v in response.data.items():
                    try:
                        data[k] = json.loads(v)
                    except json.JSONDecodeError:
                        data[k] = v
                return data
                
        except Exception as e:
            logger.error(f"Kubernetes 로드 실패 {key}: {e}")
            return None
    
    async def save_config(self, key: str, config: Dict[str, Any]) -> bool:
        """Kubernetes ConfigMap/Secret에 설정 저장"""
        try:
            client = self._get_client()
            
            # 데이터 준비
            data = {}
            for k, v in config.items():
                if isinstance(v, (dict, list)):
                    data[k] = json.dumps(v, ensure_ascii=False)
                else:
                    data[k] = str(v)
            
            if self.use_secrets:
                # Secret 생성/업데이트
                import base64
                encoded_data = {k: base64.b64encode(v.encode('utf-8')).decode('utf-8') 
                              for k, v in data.items()}
                
                secret_body = client.V1Secret(
                    metadata=client.V1ObjectMeta(name=f"llm-{key}"),
                    data=encoded_data
                )
                
                try:
                    client.replace_namespaced_secret(
                        name=f"llm-{key}",
                        namespace=self.namespace,
                        body=secret_body
                    )
                except client.rest.ApiException as e:
                    if e.status == 404:
                        client.create_namespaced_secret(
                            namespace=self.namespace,
                            body=secret_body
                        )
                    else:
                        raise
            else:
                # ConfigMap 생성/업데이트
                configmap_body = client.V1ConfigMap(
                    metadata=client.V1ObjectMeta(name=f"llm-{key}"),
                    data=data
                )
                
                try:
                    client.replace_namespaced_config_map(
                        name=f"llm-{key}",
                        namespace=self.namespace,
                        body=configmap_body
                    )
                except client.rest.ApiException as e:
                    if e.status == 404:
                        client.create_namespaced_config_map(
                            namespace=self.namespace,
                            body=configmap_body
                        )
                    else:
                        raise
            
            return True
            
        except Exception as e:
            logger.error(f"Kubernetes 저장 실패 {key}: {e}")
            return False
    
    async def list_keys(self) -> List[str]:
        """Kubernetes ConfigMap/Secret 키 목록"""
        try:
            client = self._get_client()
            
            if self.use_secrets:
                response = client.list_namespaced_secret(namespace=self.namespace)
                items = response.items
            else:
                response = client.list_namespaced_config_map(namespace=self.namespace)
                items = response.items
            
            keys = []
            for item in items:
                name = item.metadata.name
                if name.startswith("llm-"):
                    key = name[4:]  # "llm-" 제거
                    keys.append(key)
            
            return keys
            
        except Exception as e:
            logger.error(f"Kubernetes 키 목록 조회 실패: {e}")
            return []
    
    async def health_check(self) -> bool:
        """Kubernetes API 연결 확인"""
        try:
            client = self._get_client()
            client.list_namespace(limit=1)
            return True
        except Exception:
            return False


class CentralizedConfigManager:
    """중앙집중식 설정 관리자"""
    
    def __init__(self):
        self.providers: List[ConfigProvider] = []
        self.source_info: Dict[ConfigSource, ConfigSourceInfo] = {}
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 300  # 5분
        self.last_cache_time: Dict[str, float] = {}
        
        self._initialize_providers()
    
    def _initialize_providers(self):
        """설정 제공자들 초기화"""
        # 환경에 따른 설정 소스 결정
        deployment_env = os.getenv('DEPLOYMENT_ENVIRONMENT', 'local')
        
        if deployment_env == 'local':
            self._setup_local_providers()
        elif deployment_env == 'aws':
            self._setup_aws_providers()
        elif deployment_env == 'azure':
            self._setup_azure_providers()
        elif deployment_env == 'kubernetes':
            self._setup_kubernetes_providers()
        else:
            # 기본값: 로컬 개발 환경
            self._setup_local_providers()
        
        logger.info(f"설정 제공자 초기화 완료 - 배포 환경: {deployment_env}")
    
    def _setup_local_providers(self):
        """로컬 개발 환경 설정"""
        # 1순위: 환경변수 (개발자 로컬 오버라이드)
        env_provider = EnvironmentVarProvider()
        self.providers.append(env_provider)
        self.source_info[ConfigSource.ENVIRONMENT_VARS] = ConfigSourceInfo(
            source_type=ConfigSource.ENVIRONMENT_VARS,
            priority=1,
            enabled=True,
            config={}
        )
        
        # 2순위: YAML 파일 (기본 설정)
        config_dir = os.path.join(os.path.dirname(__file__), "centralized")
        yaml_provider = YamlFileProvider(config_dir)
        self.providers.append(yaml_provider)
        self.source_info[ConfigSource.YAML_FILE] = ConfigSourceInfo(
            source_type=ConfigSource.YAML_FILE,
            priority=2,
            enabled=True,
            config={"config_dir": config_dir}
        )
    
    def _setup_aws_providers(self):
        """AWS 클라우드 환경 설정"""
        # 1순위: AWS Secrets Manager (민감한 정보)
        region = os.getenv('AWS_REGION', 'us-east-1')
        aws_provider = AWSSecretsManagerProvider(region_name=region)
        self.providers.append(aws_provider)
        self.source_info[ConfigSource.AWS_SECRETS_MANAGER] = ConfigSourceInfo(
            source_type=ConfigSource.AWS_SECRETS_MANAGER,
            priority=1,
            enabled=True,
            config={"region": region}
        )
        
        # 2순위: 환경변수 (폴백)
        env_provider = EnvironmentVarProvider()
        self.providers.append(env_provider)
        self.source_info[ConfigSource.ENVIRONMENT_VARS] = ConfigSourceInfo(
            source_type=ConfigSource.ENVIRONMENT_VARS,
            priority=2,
            enabled=True,
            config={}
        )
    
    def _setup_azure_providers(self):
        """Azure 클라우드 환경 설정"""
        # Azure Key Vault 구현 (현재는 환경변수로 폴백)
        env_provider = EnvironmentVarProvider()
        self.providers.append(env_provider)
        self.source_info[ConfigSource.ENVIRONMENT_VARS] = ConfigSourceInfo(
            source_type=ConfigSource.ENVIRONMENT_VARS,
            priority=1,
            enabled=True,
            config={}
        )
        
        logger.warning("Azure Key Vault 지원은 향후 구현 예정입니다")
    
    def _setup_kubernetes_providers(self):
        """Kubernetes 환경 설정"""
        # 1순위: Kubernetes Secret (민감한 정보)
        namespace = os.getenv('K8S_NAMESPACE', 'default')
        secret_provider = KubernetesProvider(namespace=namespace, use_secrets=True)
        self.providers.append(secret_provider)
        self.source_info[ConfigSource.KUBERNETES_SECRET] = ConfigSourceInfo(
            source_type=ConfigSource.KUBERNETES_SECRET,
            priority=1,
            enabled=True,
            config={"namespace": namespace}
        )
        
        # 2순위: Kubernetes ConfigMap (일반 설정)
        configmap_provider = KubernetesProvider(namespace=namespace, use_secrets=False)
        self.providers.append(configmap_provider)
        self.source_info[ConfigSource.KUBERNETES_CONFIGMAP] = ConfigSourceInfo(
            source_type=ConfigSource.KUBERNETES_CONFIGMAP,
            priority=2,
            enabled=True,
            config={"namespace": namespace}
        )
        
        # 3순위: 환경변수 (폴백)
        env_provider = EnvironmentVarProvider()
        self.providers.append(env_provider)
        self.source_info[ConfigSource.ENVIRONMENT_VARS] = ConfigSourceInfo(
            source_type=ConfigSource.ENVIRONMENT_VARS,
            priority=3,
            enabled=True,
            config={}
        )
    
    async def get_config(self, key: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """설정 조회 (우선순위에 따라 병합)"""
        import time
        
        # 캐시 확인
        if use_cache and key in self.cache:
            cache_time = self.last_cache_time.get(key, 0)
            if time.time() - cache_time < self.cache_ttl:
                return self.cache[key]
        
        # 모든 제공자에서 설정 로드 (우선순위 순)
        merged_config = {}
        
        # 우선순위 역순으로 로드 (낮은 우선순위부터 높은 우선순위로 덮어씀)
        sorted_providers = sorted(
            zip(self.providers, self.source_info.values()),
            key=lambda x: x[1].priority,
            reverse=True
        )
        
        for provider, source_info in sorted_providers:
            if not source_info.enabled:
                continue
                
            try:
                config = await provider.load_config(key)
                if config:
                    # 딕셔너리 병합 (높은 우선순위가 낮은 우선순위를 덮어씀)
                    merged_config = self._merge_configs(merged_config, config)
                    logger.debug(f"설정 로드 완료: {key} from {source_info.source_type.value}")
            except Exception as e:
                logger.error(f"설정 로드 실패: {key} from {source_info.source_type.value}: {e}")
                continue
        
        if merged_config:
            # 캐시 저장
            self.cache[key] = merged_config
            self.last_cache_time[key] = time.time()
            return merged_config
        
        return None
    
    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """설정 딕셔너리 병합"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # 중첩된 딕셔너리는 재귀적으로 병합
                result[key] = self._merge_configs(result[key], value)
            else:
                # 단순 값은 덮어쓰기
                result[key] = value
        
        return result
    
    async def set_config(self, key: str, config: Dict[str, Any], 
                        target_source: Optional[ConfigSource] = None) -> bool:
        """설정 저장"""
        if target_source:
            # 특정 소스에만 저장
            for provider, source_info in zip(self.providers, self.source_info.values()):
                if source_info.source_type == target_source and source_info.enabled:
                    success = await provider.save_config(key, config)
                    if success:
                        # 캐시 무효화
                        self.cache.pop(key, None)
                        self.last_cache_time.pop(key, None)
                    return success
            return False
        else:
            # 첫 번째 사용 가능한 제공자에 저장
            for provider, source_info in zip(self.providers, self.source_info.values()):
                if source_info.enabled:
                    try:
                        success = await provider.save_config(key, config)
                        if success:
                            # 캐시 무효화
                            self.cache.pop(key, None)
                            self.last_cache_time.pop(key, None)
                            return True
                    except Exception as e:
                        logger.error(f"설정 저장 실패: {source_info.source_type.value}: {e}")
                        continue
            return False
    
    async def list_all_keys(self) -> List[str]:
        """모든 설정 키 목록"""
        all_keys = set()
        
        for provider in self.providers:
            try:
                keys = await provider.list_keys()
                all_keys.update(keys)
            except Exception as e:
                logger.error(f"키 목록 조회 실패: {e}")
                continue
        
        return sorted(list(all_keys))
    
    async def health_check(self) -> Dict[str, bool]:
        """모든 제공자 헬스체크"""
        health_status = {}
        
        for provider, source_info in zip(self.providers, self.source_info.values()):
            try:
                is_healthy = await provider.health_check()
                health_status[source_info.source_type.value] = is_healthy
            except Exception as e:
                logger.error(f"헬스체크 실패 {source_info.source_type.value}: {e}")
                health_status[source_info.source_type.value] = False
        
        return health_status
    
    def get_source_priority(self) -> List[Dict[str, Any]]:
        """설정 소스 우선순위 정보"""
        return [
            {
                "source": source_info.source_type.value,
                "priority": source_info.priority,
                "enabled": source_info.enabled,
                "config": source_info.config
            }
            for source_info in sorted(self.source_info.values(), key=lambda x: x.priority)
        ]
    
    def clear_cache(self, key: Optional[str] = None):
        """캐시 클리어"""
        if key:
            self.cache.pop(key, None)
            self.last_cache_time.pop(key, None)
        else:
            self.cache.clear()
            self.last_cache_time.clear()
        
        logger.info(f"캐시 클리어 완료: {key or 'all'}")


# 싱글톤 인스턴스
_centralized_config_manager = None

def get_centralized_config_manager() -> CentralizedConfigManager:
    """중앙집중식 설정 관리자 싱글톤 인스턴스"""
    global _centralized_config_manager
    
    if _centralized_config_manager is None:
        _centralized_config_manager = CentralizedConfigManager()
    
    return _centralized_config_manager