#!/usr/bin/env python3
"""
AWS 배포용 설정 관리 스크립트

이 스크립트는 개발 환경의 YAML 설정을 AWS Secrets Manager로 자동 동기화합니다.
"""

import os
import json
import yaml
import boto3
import argparse
import logging
from typing import Dict, Any, List
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AWSConfigDeployer:
    """AWS 환경으로 설정 배포 관리자"""
    
    def __init__(self, region: str = "us-east-1", environment: str = "dev"):
        self.region = region
        self.environment = environment
        self.secrets_client = boto3.client('secretsmanager', region_name=region)
        self.parameter_client = boto3.client('ssm', region_name=region)
        
        # 설정 파일 경로
        self.config_dir = Path(__file__).parent.parent.parent / "backend/core/llm/config/centralized"
        
        logger.info(f"AWS 배포 관리자 초기화 - 리전: {region}, 환경: {environment}")
    
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
    
    def deploy_to_secrets_manager(self, configs: Dict[str, Any]) -> Dict[str, bool]:
        """AWS Secrets Manager에 설정 배포"""
        results = {}
        
        for config_name, config_data in configs.items():
            secret_name = f"llm/{self.environment}/{config_name}"
            
            try:
                # 시크릿 값 준비
                secret_value = json.dumps(config_data, ensure_ascii=False, indent=2)
                
                # 기존 시크릿 확인
                try:
                    self.secrets_client.describe_secret(SecretId=secret_name)
                    # 기존 시크릿 업데이트
                    self.secrets_client.update_secret(
                        SecretId=secret_name,
                        SecretString=secret_value
                    )
                    logger.info(f"시크릿 업데이트 완료: {secret_name}")
                    
                except self.secrets_client.exceptions.ResourceNotFoundException:
                    # 새 시크릿 생성
                    self.secrets_client.create_secret(
                        Name=secret_name,
                        SecretString=secret_value,
                        Description=f"LLM configuration for {config_name} in {self.environment} environment"
                    )
                    logger.info(f"새 시크릿 생성 완료: {secret_name}")
                
                results[config_name] = True
                
            except Exception as e:
                logger.error(f"시크릿 배포 실패 {secret_name}: {e}")
                results[config_name] = False
        
        return results
    
    def deploy_to_parameter_store(self, configs: Dict[str, Any]) -> Dict[str, bool]:
        """AWS Systems Manager Parameter Store에 설정 배포"""
        results = {}
        
        for config_name, config_data in configs.items():
            # 비민감 정보만 Parameter Store에 저장
            if config_name in ['model_registry', 'environment_configs']:
                parameter_name = f"/llm/{self.environment}/{config_name}"
                
                try:
                    parameter_value = json.dumps(config_data, ensure_ascii=False)
                    
                    # 파라미터 크기 제한 확인 (4KB)
                    if len(parameter_value.encode('utf-8')) > 4096:
                        logger.warning(f"파라미터 크기 초과, Secrets Manager 사용 권장: {parameter_name}")
                        continue
                    
                    # 파라미터 생성/업데이트
                    self.parameter_client.put_parameter(
                        Name=parameter_name,
                        Value=parameter_value,
                        Type='String',
                        Overwrite=True,
                        Description=f"LLM {config_name} configuration for {self.environment}"
                    )
                    
                    logger.info(f"파라미터 배포 완료: {parameter_name}")
                    results[config_name] = True
                    
                except Exception as e:
                    logger.error(f"파라미터 배포 실패 {parameter_name}: {e}")
                    results[config_name] = False
        
        return results
    
    def create_iam_policies(self) -> Dict[str, str]:
        """필요한 IAM 정책 템플릿 생성"""
        policies = {}
        
        # Secrets Manager 접근 정책
        secrets_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "secretsmanager:GetSecretValue",
                        "secretsmanager:DescribeSecret"
                    ],
                    "Resource": f"arn:aws:secretsmanager:{self.region}:*:secret:llm/{self.environment}/*"
                }
            ]
        }
        policies['secrets_read_policy'] = json.dumps(secrets_policy, indent=2)
        
        # Parameter Store 접근 정책
        parameter_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ssm:GetParameter",
                        "ssm:GetParameters",
                        "ssm:GetParametersByPath"
                    ],
                    "Resource": f"arn:aws:ssm:{self.region}:*:parameter/llm/{self.environment}/*"
                }
            ]
        }
        policies['parameter_read_policy'] = json.dumps(parameter_policy, indent=2)
        
        return policies
    
    def generate_terraform_config(self) -> str:
        """Terraform 설정 생성"""
        terraform_config = f"""
# LLM 설정을 위한 Terraform 구성
terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region = "{self.region}"
}}

# Secrets Manager에서 LLM 설정 읽기
data "aws_secretsmanager_secret" "llm_model_registry" {{
  name = "llm/{self.environment}/model_registry"
}}

data "aws_secretsmanager_secret_version" "llm_model_registry" {{
  secret_id = data.aws_secretsmanager_secret.llm_model_registry.id
}}

data "aws_secretsmanager_secret" "llm_environment_configs" {{
  name = "llm/{self.environment}/environment_configs"
}}

data "aws_secretsmanager_secret_version" "llm_environment_configs" {{
  secret_id = data.aws_secretsmanager_secret.llm_environment_configs.id
}}

# Parameter Store에서 설정 읽기
data "aws_ssm_parameter" "llm_model_registry" {{
  name = "/llm/{self.environment}/model_registry"
}}

# IAM 역할 및 정책
resource "aws_iam_role" "llm_application_role" {{
  name = "llm-application-role-{self.environment}"
  
  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [
      {{
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {{
          Service = "ec2.amazonaws.com"
        }}
      }}
    ]
  }})
}}

resource "aws_iam_role_policy" "llm_secrets_access" {{
  name = "llm-secrets-access-{self.environment}"
  role = aws_iam_role.llm_application_role.id
  
  policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [
      {{
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = "arn:aws:secretsmanager:{self.region}:*:secret:llm/{self.environment}/*"
      }},
      {{
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]
        Resource = "arn:aws:ssm:{self.region}:*:parameter/llm/{self.environment}/*"
      }}
    ]
  }})
}}

# 출력 값
output "llm_configs" {{
  value = {{
    secrets_manager = {{
      model_registry_arn = data.aws_secretsmanager_secret.llm_model_registry.arn
      environment_configs_arn = data.aws_secretsmanager_secret.llm_environment_configs.arn
    }}
    parameter_store = {{
      model_registry_name = data.aws_ssm_parameter.llm_model_registry.name
    }}
    iam_role_arn = aws_iam_role.llm_application_role.arn
  }}
}}
"""
        return terraform_config
    
    def generate_docker_env_file(self, configs: Dict[str, Any]) -> str:
        """Docker 배포용 환경변수 파일 생성"""
        env_content = f"""# LLM 설정 - AWS {self.environment} 환경
# 이 파일은 자동 생성되었습니다. 수동 편집하지 마세요.

# 배포 환경 설정
DEPLOYMENT_ENVIRONMENT=aws
AWS_REGION={self.region}
ENVIRONMENT={self.environment}

# Secrets Manager 설정
LLM_MODEL_REGISTRY_SECRET=llm/{self.environment}/model_registry
LLM_ENVIRONMENT_CONFIGS_SECRET=llm/{self.environment}/environment_configs
LLM_SECRETS_TEMPLATE_SECRET=llm/{self.environment}/secrets_template

# Parameter Store 설정 (비민감 정보)
LLM_MODEL_REGISTRY_PARAMETER=/llm/{self.environment}/model_registry
LLM_ENVIRONMENT_CONFIGS_PARAMETER=/llm/{self.environment}/environment_configs

# 로깅 설정
LOG_LEVEL=INFO
AWS_LOGS_GROUP=/aws/llm/{self.environment}

# 모니터링 설정
ENABLE_CLOUDWATCH_METRICS=true
CLOUDWATCH_NAMESPACE=LLM/{self.environment.upper()}
"""
        return env_content
    
    def validate_deployment(self) -> Dict[str, bool]:
        """배포된 설정 검증"""
        validation_results = {}
        
        # Secrets Manager 검증
        secrets_to_check = [
            f"llm/{self.environment}/model_registry",
            f"llm/{self.environment}/environment_configs",
            f"llm/{self.environment}/secrets_template"
        ]
        
        for secret_name in secrets_to_check:
            try:
                response = self.secrets_client.get_secret_value(SecretId=secret_name)
                # JSON 파싱 테스트
                json.loads(response['SecretString'])
                validation_results[f"secret_{secret_name}"] = True
                logger.info(f"시크릿 검증 성공: {secret_name}")
            except Exception as e:
                validation_results[f"secret_{secret_name}"] = False
                logger.error(f"시크릿 검증 실패 {secret_name}: {e}")
        
        # Parameter Store 검증
        parameters_to_check = [
            f"/llm/{self.environment}/model_registry",
            f"/llm/{self.environment}/environment_configs"
        ]
        
        for param_name in parameters_to_check:
            try:
                response = self.parameter_client.get_parameter(Name=param_name)
                # JSON 파싱 테스트
                json.loads(response['Parameter']['Value'])
                validation_results[f"parameter_{param_name}"] = True
                logger.info(f"파라미터 검증 성공: {param_name}")
            except Exception as e:
                validation_results[f"parameter_{param_name}"] = False
                logger.error(f"파라미터 검증 실패 {param_name}: {e}")
        
        return validation_results
    
    def deploy_all(self) -> Dict[str, Any]:
        """전체 배포 프로세스 실행"""
        logger.info("AWS 배포 프로세스 시작")
        
        # 1. 로컬 설정 로드
        configs = self.load_local_configs()
        if not configs:
            return {"success": False, "error": "로컬 설정 파일을 찾을 수 없습니다"}
        
        # 2. Secrets Manager 배포
        secrets_results = self.deploy_to_secrets_manager(configs)
        
        # 3. Parameter Store 배포
        parameter_results = self.deploy_to_parameter_store(configs)
        
        # 4. IAM 정책 생성
        iam_policies = self.create_iam_policies()
        
        # 5. Terraform 설정 생성
        terraform_config = self.generate_terraform_config()
        
        # 6. Docker 환경변수 파일 생성
        docker_env = self.generate_docker_env_file(configs)
        
        # 7. 배포 검증
        validation_results = self.validate_deployment()
        
        # 결과 정리
        all_successful = (
            all(secrets_results.values()) and
            all(parameter_results.values()) and
            all(validation_results.values())
        )
        
        return {
            "success": all_successful,
            "secrets_manager_results": secrets_results,
            "parameter_store_results": parameter_results,
            "iam_policies": iam_policies,
            "terraform_config": terraform_config,
            "docker_env": docker_env,
            "validation_results": validation_results
        }


def main():
    parser = argparse.ArgumentParser(description="AWS 배포용 설정 관리")
    parser.add_argument("--region", default="us-east-1", help="AWS 리전")
    parser.add_argument("--environment", default="dev", choices=["dev", "staging", "prod"], help="배포 환경")
    parser.add_argument("--validate-only", action="store_true", help="배포 없이 검증만 수행")
    parser.add_argument("--output-dir", help="Terraform/Docker 파일 출력 디렉토리")
    
    args = parser.parse_args()
    
    deployer = AWSConfigDeployer(region=args.region, environment=args.environment)
    
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
        print("✅ AWS 배포 완료!")
        
        # 파일 출력
        if args.output_dir:
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Terraform 파일 저장
            with open(output_dir / "main.tf", "w") as f:
                f.write(results["terraform_config"])
            
            # Docker 환경변수 파일 저장
            with open(output_dir / ".env.aws", "w") as f:
                f.write(results["docker_env"])
            
            # IAM 정책 파일들 저장
            for policy_name, policy_content in results["iam_policies"].items():
                with open(output_dir / f"{policy_name}.json", "w") as f:
                    f.write(policy_content)
            
            print(f"📁 설정 파일들이 {output_dir}에 저장되었습니다")
        
    else:
        print("❌ AWS 배포 실패")
        print("상세 결과:")
        for category, category_results in results.items():
            if isinstance(category_results, dict):
                print(f"  {category}:")
                for key, result in category_results.items():
                    status = "✅" if result else "❌"
                    print(f"    {status} {key}")


if __name__ == "__main__":
    main()