#!/usr/bin/env python3
"""
Kubernetes 배포용 설정 관리 스크립트

이 스크립트는 개발 환경의 YAML 설정을 Kubernetes ConfigMap과 Secret으로 자동 동기화합니다.
"""

import os
import json
import yaml
import base64
import argparse
import logging
from typing import Dict, Any, List
from pathlib import Path
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KubernetesConfigDeployer:
    """Kubernetes 환경으로 설정 배포 관리자"""
    
    def __init__(self, namespace: str = "default", environment: str = "dev"):
        self.namespace = namespace
        self.environment = environment
        
        # Kubernetes 클라이언트 초기화
        try:
            # 클러스터 내부에서 실행 중인지 확인
            config.load_incluster_config()
            logger.info("클러스터 내부 설정 로드")
        except config.ConfigException:
            try:
                # 로컬 개발 환경
                config.load_kube_config()
                logger.info("로컬 kubeconfig 로드")
            except config.ConfigException as e:
                logger.error(f"Kubernetes 설정 로드 실패: {e}")
                raise
        
        self.core_v1 = client.CoreV1Api()
        
        # 설정 파일 경로
        self.config_dir = Path(__file__).parent.parent.parent / "backend/core/llm/config/centralized"
        
        logger.info(f"Kubernetes 배포 관리자 초기화 - 네임스페이스: {namespace}, 환경: {environment}")
    
    def load_local_configs(self) -> Dict[str, Any]:
        """로컬 YAML 설정 파일들 로드"""
        configs = {}
        
        config_files = [
            "model_registry.yaml",
            "environment_configs.yaml",
            "secrets_template.yaml"
        ]
        
        for config_file in config_files:
            file_path = self.config_dir / config_file
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        configs[config_file.replace('.yaml', '')] = yaml.safe_load(f)
                    logger.info(f"설정 파일 로드 완료: {config_file}")
                except Exception as e:
                    logger.error(f"설정 파일 로드 실패 {config_file}: {e}")
            else:
                logger.warning(f"설정 파일을 찾을 수 없음: {config_file}")
        
        return configs
    
    def deploy_to_configmaps(self, configs: Dict[str, Any]) -> Dict[str, bool]:
        """Kubernetes ConfigMap에 설정 배포 (비민감 정보)"""
        results = {}
        
        # 비민감 정보만 ConfigMap에 저장
        non_sensitive_configs = {
            k: v for k, v in configs.items() 
            if k in ['model_registry', 'environment_configs']
        }
        
        for config_name, config_data in non_sensitive_configs.items():
            configmap_name = f"llm-{config_name}-{self.environment}"
            
            try:
                # 데이터 준비
                data = {
                    f"{config_name}.yaml": yaml.dump(config_data, default_flow_style=False, allow_unicode=True),
                    f"{config_name}.json": json.dumps(config_data, ensure_ascii=False, indent=2)
                }
                
                # ConfigMap 객체 생성
                configmap = client.V1ConfigMap(
                    metadata=client.V1ObjectMeta(
                        name=configmap_name,
                        namespace=self.namespace,
                        labels={
                            "app": "llm",
                            "component": "config",
                            "environment": self.environment,
                            "config-type": config_name
                        }
                    ),
                    data=data
                )
                
                # ConfigMap 생성/업데이트
                try:
                    self.core_v1.read_namespaced_config_map(
                        name=configmap_name,
                        namespace=self.namespace
                    )
                    # 기존 ConfigMap 업데이트
                    self.core_v1.replace_namespaced_config_map(
                        name=configmap_name,
                        namespace=self.namespace,
                        body=configmap
                    )
                    logger.info(f"ConfigMap 업데이트 완료: {configmap_name}")
                    
                except ApiException as e:
                    if e.status == 404:
                        # 새 ConfigMap 생성
                        self.core_v1.create_namespaced_config_map(
                            namespace=self.namespace,
                            body=configmap
                        )
                        logger.info(f"새 ConfigMap 생성 완료: {configmap_name}")
                    else:
                        raise
                
                results[config_name] = True
                
            except Exception as e:
                logger.error(f"ConfigMap 배포 실패 {configmap_name}: {e}")
                results[config_name] = False
        
        return results
    
    def deploy_to_secrets(self, configs: Dict[str, Any]) -> Dict[str, bool]:
        """Kubernetes Secret에 설정 배포 (민감 정보)"""
        results = {}
        
        # 민감 정보는 Secret에 저장
        sensitive_configs = {
            k: v for k, v in configs.items() 
            if k in ['secrets_template']
        }
        
        for config_name, config_data in sensitive_configs.items():
            secret_name = f"llm-{config_name}-{self.environment}"
            
            try:
                # 데이터 준비 (base64 인코딩)
                data = {}
                
                # YAML 형태로 저장
                yaml_content = yaml.dump(config_data, default_flow_style=False, allow_unicode=True)
                data[f"{config_name}.yaml"] = base64.b64encode(yaml_content.encode('utf-8')).decode('utf-8')
                
                # JSON 형태로도 저장
                json_content = json.dumps(config_data, ensure_ascii=False, indent=2)
                data[f"{config_name}.json"] = base64.b64encode(json_content.encode('utf-8')).decode('utf-8')
                
                # 개별 API 키들도 별도로 저장 (환경변수로 직접 사용 가능)
                if 'api_keys' in config_data:
                    for provider, keys in config_data['api_keys'].items():
                        for key_type, key_value in keys.items():
                            if isinstance(key_value, str) and not key_value.startswith('${'):
                                # 환경변수 참조가 아닌 실제 값만 저장
                                key_name = f"{provider}_{key_type}_api_key".upper()
                                data[key_name] = base64.b64encode(key_value.encode('utf-8')).decode('utf-8')
                
                # Secret 객체 생성
                secret = client.V1Secret(
                    metadata=client.V1ObjectMeta(
                        name=secret_name,
                        namespace=self.namespace,
                        labels={
                            "app": "llm",
                            "component": "secret",
                            "environment": self.environment,
                            "config-type": config_name
                        }
                    ),
                    type="Opaque",
                    data=data
                )
                
                # Secret 생성/업데이트
                try:
                    self.core_v1.read_namespaced_secret(
                        name=secret_name,
                        namespace=self.namespace
                    )
                    # 기존 Secret 업데이트
                    self.core_v1.replace_namespaced_secret(
                        name=secret_name,
                        namespace=self.namespace,
                        body=secret
                    )
                    logger.info(f"Secret 업데이트 완료: {secret_name}")
                    
                except ApiException as e:
                    if e.status == 404:
                        # 새 Secret 생성
                        self.core_v1.create_namespaced_secret(
                            namespace=self.namespace,
                            body=secret
                        )
                        logger.info(f"새 Secret 생성 완료: {secret_name}")
                    else:
                        raise
                
                results[config_name] = True
                
            except Exception as e:
                logger.error(f"Secret 배포 실패 {secret_name}: {e}")
                results[config_name] = False
        
        return results
    
    def generate_deployment_yaml(self) -> str:
        """애플리케이션 배포용 YAML 생성"""
        deployment_yaml = f"""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-application-{self.environment}
  namespace: {self.namespace}
  labels:
    app: llm
    environment: {self.environment}
spec:
  replicas: 3
  selector:
    matchLabels:
      app: llm
      environment: {self.environment}
  template:
    metadata:
      labels:
        app: llm
        environment: {self.environment}
    spec:
      containers:
      - name: llm-application
        image: llm-application:latest
        ports:
        - containerPort: 8000
        env:
        # 배포 환경 설정
        - name: DEPLOYMENT_ENVIRONMENT
          value: "kubernetes"
        - name: K8S_NAMESPACE
          value: "{self.namespace}"
        - name: ENVIRONMENT
          value: "{self.environment}"
        
        # ConfigMap에서 설정 로드
        - name: LLM_CONFIG_PATH
          value: "/etc/llm/config"
        
        # Secret에서 API 키 로드
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: llm-secrets-template-{self.environment}
              key: OPENAI_DEV_KEY_API_KEY
              optional: true
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: llm-secrets-template-{self.environment}
              key: ANTHROPIC_DEV_KEY_API_KEY
              optional: true
        - name: GEMINI_API_KEY
          valueFrom:
            secretKeyRef:
              name: llm-secrets-template-{self.environment}
              key: GEMINI_DEV_KEY_API_KEY
              optional: true
        
        volumeMounts:
        # ConfigMap 마운트
        - name: model-registry-config
          mountPath: /etc/llm/config/model_registry.yaml
          subPath: model_registry.yaml
          readOnly: true
        - name: environment-configs
          mountPath: /etc/llm/config/environment_configs.yaml
          subPath: environment_configs.yaml
          readOnly: true
        
        # Secret 마운트
        - name: secrets-config
          mountPath: /etc/llm/secrets/secrets_template.yaml
          subPath: secrets_template.yaml
          readOnly: true
        
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
      
      volumes:
      # ConfigMap 볼륨
      - name: model-registry-config
        configMap:
          name: llm-model-registry-{self.environment}
      - name: environment-configs
        configMap:
          name: llm-environment-configs-{self.environment}
      
      # Secret 볼륨
      - name: secrets-config
        secret:
          secretName: llm-secrets-template-{self.environment}

---
apiVersion: v1
kind: Service
metadata:
  name: llm-application-service-{self.environment}
  namespace: {self.namespace}
  labels:
    app: llm
    environment: {self.environment}
spec:
  selector:
    app: llm
    environment: {self.environment}
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP

---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: llm-application-ingress-{self.environment}
  namespace: {self.namespace}
  labels:
    app: llm
    environment: {self.environment}
  annotations:
    kubernetes.io/ingress.class: "nginx"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - llm-{self.environment}.yourdomain.com
    secretName: llm-{self.environment}-tls
  rules:
  - host: llm-{self.environment}.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: llm-application-service-{self.environment}
            port:
              number: 80
"""
        return deployment_yaml
    
    def generate_rbac_yaml(self) -> str:
        """RBAC 권한 설정 YAML 생성"""
        rbac_yaml = f"""
apiVersion: v1
kind: ServiceAccount
metadata:
  name: llm-application-sa-{self.environment}
  namespace: {self.namespace}
  labels:
    app: llm
    environment: {self.environment}

---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: llm-config-reader-{self.environment}
  namespace: {self.namespace}
  labels:
    app: llm
    environment: {self.environment}
rules:
- apiGroups: [""]
  resources: ["configmaps", "secrets"]
  verbs: ["get", "list", "watch"]
  resourceNames: 
  - "llm-model-registry-{self.environment}"
  - "llm-environment-configs-{self.environment}"
  - "llm-secrets-template-{self.environment}"

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: llm-config-reader-binding-{self.environment}
  namespace: {self.namespace}
  labels:
    app: llm
    environment: {self.environment}
subjects:
- kind: ServiceAccount
  name: llm-application-sa-{self.environment}
  namespace: {self.namespace}
roleRef:
  kind: Role
  name: llm-config-reader-{self.environment}
  apiGroup: rbac.authorization.k8s.io
"""
        return rbac_yaml
    
    def validate_deployment(self) -> Dict[str, bool]:
        """배포된 설정 검증"""
        validation_results = {}
        
        # ConfigMap 검증
        configmaps_to_check = [
            f"llm-model-registry-{self.environment}",
            f"llm-environment-configs-{self.environment}"
        ]
        
        for configmap_name in configmaps_to_check:
            try:
                configmap = self.core_v1.read_namespaced_config_map(
                    name=configmap_name,
                    namespace=self.namespace
                )
                # YAML 파싱 테스트
                yaml.safe_load(configmap.data[f"{configmap_name.split('-')[1]}.yaml"])
                validation_results[f"configmap_{configmap_name}"] = True
                logger.info(f"ConfigMap 검증 성공: {configmap_name}")
            except Exception as e:
                validation_results[f"configmap_{configmap_name}"] = False
                logger.error(f"ConfigMap 검증 실패 {configmap_name}: {e}")
        
        # Secret 검증
        secrets_to_check = [
            f"llm-secrets-template-{self.environment}"
        ]
        
        for secret_name in secrets_to_check:
            try:
                secret = self.core_v1.read_namespaced_secret(
                    name=secret_name,
                    namespace=self.namespace
                )
                # base64 디코딩 및 YAML 파싱 테스트
                yaml_data = base64.b64decode(secret.data['secrets_template.yaml']).decode('utf-8')
                yaml.safe_load(yaml_data)
                validation_results[f"secret_{secret_name}"] = True
                logger.info(f"Secret 검증 성공: {secret_name}")
            except Exception as e:
                validation_results[f"secret_{secret_name}"] = False
                logger.error(f"Secret 검증 실패 {secret_name}: {e}")
        
        return validation_results
    
    def deploy_all(self) -> Dict[str, Any]:
        """전체 배포 프로세스 실행"""
        logger.info("Kubernetes 배포 프로세스 시작")
        
        # 1. 로컬 설정 로드
        configs = self.load_local_configs()
        if not configs:
            return {"success": False, "error": "로컬 설정 파일을 찾을 수 없습니다"}
        
        # 2. ConfigMap 배포
        configmap_results = self.deploy_to_configmaps(configs)
        
        # 3. Secret 배포
        secret_results = self.deploy_to_secrets(configs)
        
        # 4. 배포 YAML 생성
        deployment_yaml = self.generate_deployment_yaml()
        rbac_yaml = self.generate_rbac_yaml()
        
        # 5. 배포 검증
        validation_results = self.validate_deployment()
        
        # 결과 정리
        all_successful = (
            all(configmap_results.values()) and
            all(secret_results.values()) and
            all(validation_results.values())
        )
        
        return {
            "success": all_successful,
            "configmap_results": configmap_results,
            "secret_results": secret_results,
            "deployment_yaml": deployment_yaml,
            "rbac_yaml": rbac_yaml,
            "validation_results": validation_results
        }


def main():
    parser = argparse.ArgumentParser(description="Kubernetes 배포용 설정 관리")
    parser.add_argument("--namespace", default="default", help="Kubernetes 네임스페이스")
    parser.add_argument("--environment", default="dev", choices=["dev", "staging", "prod"], help="배포 환경")
    parser.add_argument("--validate-only", action="store_true", help="배포 없이 검증만 수행")
    parser.add_argument("--output-dir", help="YAML 파일 출력 디렉토리")
    
    args = parser.parse_args()
    
    deployer = KubernetesConfigDeployer(namespace=args.namespace, environment=args.environment)
    
    if args.validate_only:
        # 검증만 수행
        validation_results = deployer.validate_deployment()
        print("🔍 배포 검증 결과:")
        for key, result in validation_results.items():
            status = "✅" if result else "❌"
            print(f"  {status} {key}")
        return
    
    # 전체 배포 수행
    results = deployer.deploy_all()
    
    if results["success"]:
        print("✅ Kubernetes 배포 완료!")
        
        # 파일 출력
        if args.output_dir:
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 배포 YAML 파일 저장
            with open(output_dir / "deployment.yaml", "w") as f:
                f.write(results["deployment_yaml"])
            
            # RBAC YAML 파일 저장
            with open(output_dir / "rbac.yaml", "w") as f:
                f.write(results["rbac_yaml"])
            
            print(f"📁 배포 파일들이 {output_dir}에 저장되었습니다")
            print("다음 명령어로 배포하세요:")
            print(f"  kubectl apply -f {output_dir}/rbac.yaml")
            print(f"  kubectl apply -f {output_dir}/deployment.yaml")
        
    else:
        print("❌ Kubernetes 배포 실패")
        print("상세 결과:")
        for category, category_results in results.items():
            if isinstance(category_results, dict):
                print(f"  {category}:")
                for key, result in category_results.items():
                    status = "✅" if result else "❌"
                    print(f"    {status} {key}")


if __name__ == "__main__":
    main()