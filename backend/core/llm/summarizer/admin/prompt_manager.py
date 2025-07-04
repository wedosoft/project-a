"""
관리자 친화적 프롬프트 관리 시스템

코드 수정 없이 웹 인터페이스나 API를 통해 프롬프트를 편집할 수 있는 시스템입니다.
실시간 미리보기, 버전 관리, 자동 백업, 품질 검증 등의 기능을 제공합니다.
"""

import os
import yaml
import json
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import hashlib
import asyncio
from dataclasses import dataclass, asdict

from ..config.settings import anthropic_settings
from ..prompt.anthropic_builder import AnthropicPromptBuilder
from ..quality.anthropic_validator import AnthropicQualityValidator

logger = logging.getLogger(__name__)


@dataclass
class PromptChangeLog:
    """프롬프트 변경 로그"""
    timestamp: str
    user_id: str
    action: str  # create, update, delete, rollback
    template_name: str
    template_type: str  # system, user, admin
    old_version: Optional[str]
    new_version: str
    changes_summary: str
    validation_passed: bool
    auto_backup_created: bool


@dataclass
class ValidationResult:
    """검증 결과"""
    valid: bool
    score: float
    errors: List[str]
    warnings: List[str]
    recommendations: List[str]


class PromptManager:
    """관리자 친화적 프롬프트 관리 시스템"""
    
    def __init__(self):
        """프롬프트 관리자 초기화"""
        self.settings = anthropic_settings
        self.templates_dir = Path(__file__).parent.parent / "prompt" / "templates"
        self.backups_dir = Path(__file__).parent.parent / "backups"
        self.logs_dir = Path(__file__).parent.parent / "logs"
        
        # 디렉토리 생성
        self.backups_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
        
        # 컴포넌트 초기화
        self.prompt_builder = AnthropicPromptBuilder()
        self.quality_validator = AnthropicQualityValidator()
        
        # 변경 로그
        self.change_logs: List[PromptChangeLog] = []
        self._load_change_logs()
        
        # 관리 설정
        self.admin_settings = self.settings.get_admin_settings()
        
        logger.info("PromptManager 초기화 완료")
    
    async def get_available_templates(self) -> Dict[str, List[str]]:
        """사용 가능한 템플릿 목록 조회"""
        try:
            templates = {
                "system": [],
                "user": [],
                "admin": []
            }
            
            for template_type in templates.keys():
                template_dir = self.templates_dir / template_type
                if template_dir.exists():
                    for file_path in template_dir.glob("*.yaml"):
                        templates[template_type].append(file_path.stem)
            
            return templates
            
        except Exception as e:
            logger.error(f"템플릿 목록 조회 실패: {e}")
            return {"system": [], "user": [], "admin": []}
    
    async def get_template_content(self, 
                                 template_name: str, 
                                 template_type: str = "system") -> Optional[Dict[str, Any]]:
        """템플릿 내용 조회"""
        try:
            template_path = self.templates_dir / template_type / f"{template_name}.yaml"
            
            if not template_path.exists():
                logger.error(f"템플릿 파일 없음: {template_path}")
                return None
            
            with open(template_path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f)
            
            # 메타데이터 추가
            content['_metadata'] = {
                "file_path": str(template_path),
                "last_modified": datetime.fromtimestamp(template_path.stat().st_mtime).isoformat(),
                "file_size": template_path.stat().st_size,
                "template_type": template_type,
                "template_name": template_name
            }
            
            return content
            
        except Exception as e:
            logger.error(f"템플릿 내용 조회 실패: {e}")
            return None
    
    async def update_template(self,
                            template_name: str,
                            template_type: str,
                            content: Dict[str, Any],
                            user_id: str = "admin",
                            validate: bool = True) -> Dict[str, Any]:
        """
        템플릿 업데이트
        
        Args:
            template_name: 템플릿 이름
            template_type: 템플릿 타입 (system, user, admin)
            content: 새로운 내용
            user_id: 변경한 사용자 ID
            validate: 검증 수행 여부
            
        Returns:
            Dict[str, Any]: 업데이트 결과
        """
        try:
            template_path = self.templates_dir / template_type / f"{template_name}.yaml"
            
            # 기존 내용 백업
            old_content = None
            if template_path.exists():
                old_content = await self.get_template_content(template_name, template_type)
            
            # 자동 백업 생성
            backup_created = False
            if self.admin_settings['backup_on_change'] and old_content:
                backup_created = await self._create_backup(template_name, template_type, old_content)
            
            # 검증 수행
            validation_result = None
            if validate and self.admin_settings['auto_validate']:
                validation_result = await self._validate_template_content(content, template_type)
                
                if not validation_result.valid and self.admin_settings['rollback_on_failure']:
                    return {
                        "success": False,
                        "error": "검증 실패로 인한 업데이트 취소",
                        "validation": asdict(validation_result)
                    }
            
            # 테스트 실행
            test_result = None
            if self.admin_settings['test_before_apply']:
                test_result = await self._test_template(content, template_type)
                
                if not test_result['success'] and self.admin_settings['rollback_on_failure']:
                    return {
                        "success": False,
                        "error": "테스트 실패로 인한 업데이트 취소",
                        "test_result": test_result
                    }
            
            # 메타데이터 업데이트
            content['last_updated'] = datetime.now().isoformat()
            if 'version' in content:
                try:
                    version_parts = content['version'].split('.')
                    version_parts[-1] = str(int(version_parts[-1]) + 1)
                    content['version'] = '.'.join(version_parts)
                except:
                    content['version'] = "1.0.1"
            else:
                content['version'] = "1.0.0"
            
            # 파일 저장
            with open(template_path, 'w', encoding='utf-8') as f:
                yaml.dump(content, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            
            # 변경 로그 기록
            change_log = PromptChangeLog(
                timestamp=datetime.now().isoformat(),
                user_id=user_id,
                action="update" if old_content else "create",
                template_name=template_name,
                template_type=template_type,
                old_version=old_content.get('version') if old_content else None,
                new_version=content['version'],
                changes_summary=self._generate_changes_summary(old_content, content),
                validation_passed=validation_result.valid if validation_result else True,
                auto_backup_created=backup_created
            )
            
            self.change_logs.append(change_log)
            await self._save_change_logs()
            
            # 실시간 리로드
            if self.admin_settings['hot_reload_enabled']:
                await self._trigger_hot_reload()
            
            # 알림 발송
            if self.settings.get_notification_settings()['notify_on']['prompt_changes']:
                await self._send_change_notification(change_log)
            
            result = {
                "success": True,
                "message": "템플릿 업데이트 성공",
                "template_name": template_name,
                "template_type": template_type,
                "new_version": content['version'],
                "backup_created": backup_created,
                "change_log_id": len(self.change_logs)
            }
            
            if validation_result:
                result['validation'] = asdict(validation_result)
            
            if test_result:
                result['test_result'] = test_result
            
            logger.info(f"✅ 템플릿 업데이트 성공: {template_name} ({template_type})")
            return result
            
        except Exception as e:
            logger.error(f"❌ 템플릿 업데이트 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "template_name": template_name,
                "template_type": template_type
            }
    
    async def preview_template(self,
                             template_name: str,
                             template_type: str,
                             content: Dict[str, Any],
                             test_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        템플릿 미리보기 생성
        
        Args:
            template_name: 템플릿 이름
            template_type: 템플릿 타입
            content: 템플릿 내용
            test_data: 테스트 데이터
            
        Returns:
            Dict[str, Any]: 미리보기 결과
        """
        try:
            # 임시 파일 생성
            temp_path = self.templates_dir / "temp" / f"{template_name}_preview.yaml"
            temp_path.parent.mkdir(exist_ok=True)
            
            with open(temp_path, 'w', encoding='utf-8') as f:
                yaml.dump(content, f, allow_unicode=True, default_flow_style=False)
            
            # 테스트 데이터가 없으면 기본 데이터 사용
            if not test_data:
                test_data = await self._get_default_test_data(template_type)
            
            # 프롬프트 생성 테스트
            preview_result = await self._generate_preview(content, template_type, test_data)
            
            # 임시 파일 정리
            temp_path.unlink(missing_ok=True)
            
            return {
                "success": True,
                "preview": preview_result,
                "test_data": test_data,
                "template_type": template_type
            }
            
        except Exception as e:
            logger.error(f"템플릿 미리보기 생성 실패: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def rollback_template(self,
                              template_name: str,
                              template_type: str,
                              target_version: str,
                              user_id: str = "admin") -> Dict[str, Any]:
        """
        템플릿 버전 롤백
        
        Args:
            template_name: 템플릿 이름
            template_type: 템플릿 타입
            target_version: 롤백 대상 버전
            user_id: 사용자 ID
            
        Returns:
            Dict[str, Any]: 롤백 결과
        """
        try:
            # 백업에서 대상 버전 찾기
            backup_path = await self._find_backup_by_version(template_name, template_type, target_version)
            
            if not backup_path:
                return {
                    "success": False,
                    "error": f"버전 {target_version}의 백업을 찾을 수 없음"
                }
            
            # 백업 내용 로드
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_content = yaml.safe_load(f)
            
            # 현재 버전 백업
            current_content = await self.get_template_content(template_name, template_type)
            if current_content:
                await self._create_backup(template_name, template_type, current_content, "pre_rollback")
            
            # 롤백 실행
            rollback_result = await self.update_template(
                template_name=template_name,
                template_type=template_type,
                content=backup_content,
                user_id=user_id,
                validate=True
            )
            
            if rollback_result['success']:
                # 롤백 로그 추가
                change_log = PromptChangeLog(
                    timestamp=datetime.now().isoformat(),
                    user_id=user_id,
                    action="rollback",
                    template_name=template_name,
                    template_type=template_type,
                    old_version=current_content.get('version') if current_content else None,
                    new_version=target_version,
                    changes_summary=f"Rolled back to version {target_version}",
                    validation_passed=True,
                    auto_backup_created=True
                )
                
                self.change_logs.append(change_log)
                await self._save_change_logs()
            
            return rollback_result
            
        except Exception as e:
            logger.error(f"템플릿 롤백 실패: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_change_history(self,
                               template_name: Optional[str] = None,
                               template_type: Optional[str] = None,
                               limit: int = 50) -> List[Dict[str, Any]]:
        """변경 이력 조회"""
        try:
            filtered_logs = self.change_logs
            
            # 필터링
            if template_name:
                filtered_logs = [log for log in filtered_logs if log.template_name == template_name]
            
            if template_type:
                filtered_logs = [log for log in filtered_logs if log.template_type == template_type]
            
            # 최신순 정렬 및 제한
            filtered_logs = sorted(filtered_logs, key=lambda x: x.timestamp, reverse=True)[:limit]
            
            return [asdict(log) for log in filtered_logs]
            
        except Exception as e:
            logger.error(f"변경 이력 조회 실패: {e}")
            return []
    
    async def get_backup_list(self,
                            template_name: Optional[str] = None,
                            template_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """백업 목록 조회"""
        try:
            backups = []
            
            for backup_file in self.backups_dir.glob("*.yaml"):
                # 파일명에서 정보 추출: {template_name}_{template_type}_{timestamp}.yaml
                parts = backup_file.stem.split('_')
                if len(parts) >= 3:
                    file_template_name = parts[0]
                    file_template_type = parts[1]
                    timestamp = '_'.join(parts[2:])
                    
                    # 필터링
                    if template_name and file_template_name != template_name:
                        continue
                    if template_type and file_template_type != template_type:
                        continue
                    
                    # 백업 정보 로드
                    with open(backup_file, 'r', encoding='utf-8') as f:
                        backup_content = yaml.safe_load(f)
                    
                    backups.append({
                        "file_name": backup_file.name,
                        "template_name": file_template_name,
                        "template_type": file_template_type,
                        "timestamp": timestamp,
                        "version": backup_content.get('version', 'unknown'),
                        "file_size": backup_file.stat().st_size,
                        "created_at": datetime.fromtimestamp(backup_file.stat().st_ctime).isoformat()
                    })
            
            # 최신순 정렬
            backups.sort(key=lambda x: x['created_at'], reverse=True)
            
            return backups
            
        except Exception as e:
            logger.error(f"백업 목록 조회 실패: {e}")
            return []
    
    async def export_templates(self, 
                             template_names: Optional[List[str]] = None,
                             template_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """템플릿 내보내기"""
        try:
            export_data = {
                "export_metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "version": "1.0.0",
                    "exported_by": "PromptManager"
                },
                "templates": {}
            }
            
            available_templates = await self.get_available_templates()
            
            for template_type, templates in available_templates.items():
                if template_types and template_type not in template_types:
                    continue
                
                export_data["templates"][template_type] = {}
                
                for template_name in templates:
                    if template_names and template_name not in template_names:
                        continue
                    
                    content = await self.get_template_content(template_name, template_type)
                    if content:
                        export_data["templates"][template_type][template_name] = content
            
            return {
                "success": True,
                "data": export_data,
                "total_templates": sum(len(templates) for templates in export_data["templates"].values())
            }
            
        except Exception as e:
            logger.error(f"템플릿 내보내기 실패: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def import_templates(self, 
                             import_data: Dict[str, Any],
                             user_id: str = "admin",
                             overwrite: bool = False) -> Dict[str, Any]:
        """템플릿 가져오기"""
        try:
            results = {
                "success": True,
                "imported": 0,
                "skipped": 0,
                "errors": []
            }
            
            templates_data = import_data.get("templates", {})
            
            for template_type, templates in templates_data.items():
                for template_name, content in templates.items():
                    try:
                        # 기존 템플릿 확인
                        existing = await self.get_template_content(template_name, template_type)
                        
                        if existing and not overwrite:
                            results["skipped"] += 1
                            continue
                        
                        # 템플릿 업데이트
                        result = await self.update_template(
                            template_name=template_name,
                            template_type=template_type,
                            content=content,
                            user_id=user_id,
                            validate=True
                        )
                        
                        if result["success"]:
                            results["imported"] += 1
                        else:
                            results["errors"].append(f"{template_name}: {result.get('error', 'Unknown error')}")
                            
                    except Exception as e:
                        results["errors"].append(f"{template_name}: {str(e)}")
            
            if results["errors"]:
                results["success"] = len(results["errors"]) < (results["imported"] + results["skipped"])
            
            return results
            
        except Exception as e:
            logger.error(f"템플릿 가져오기 실패: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_system_status(self) -> Dict[str, Any]:
        """시스템 상태 조회"""
        try:
            available_templates = await self.get_available_templates()
            total_templates = sum(len(templates) for templates in available_templates.values())
            
            backup_count = len(list(self.backups_dir.glob("*.yaml")))
            
            return {
                "status": "healthy",
                "templates": {
                    "total": total_templates,
                    "by_type": {k: len(v) for k, v in available_templates.items()}
                },
                "backups": {
                    "total": backup_count,
                    "directory": str(self.backups_dir)
                },
                "change_logs": {
                    "total": len(self.change_logs),
                    "recent": len([log for log in self.change_logs 
                                 if (datetime.now() - datetime.fromisoformat(log.timestamp)).days <= 7])
                },
                "admin_settings": self.admin_settings,
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"시스템 상태 조회 실패: {e}")
            return {
                "status": "error",
                "error": str(e),
                "last_updated": datetime.now().isoformat()
            }
    
    # 내부 메서드들
    
    async def _create_backup(self, 
                           template_name: str, 
                           template_type: str, 
                           content: Dict[str, Any],
                           suffix: str = "") -> bool:
        """자동 백업 생성"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if suffix:
                backup_filename = f"{template_name}_{template_type}_{timestamp}_{suffix}.yaml"
            else:
                backup_filename = f"{template_name}_{template_type}_{timestamp}.yaml"
            
            backup_path = self.backups_dir / backup_filename
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                yaml.dump(content, f, allow_unicode=True, default_flow_style=False)
            
            logger.info(f"백업 생성: {backup_filename}")
            return True
            
        except Exception as e:
            logger.error(f"백업 생성 실패: {e}")
            return False
    
    async def _validate_template_content(self, 
                                       content: Dict[str, Any], 
                                       template_type: str) -> ValidationResult:
        """템플릿 내용 검증"""
        try:
            errors = []
            warnings = []
            recommendations = []
            score = 1.0
            
            # 기본 구조 검증
            if 'version' not in content:
                warnings.append("버전 정보가 없습니다")
                score -= 0.1
            
            if 'last_updated' not in content:
                warnings.append("마지막 업데이트 시간이 없습니다")
                score -= 0.05
            
            # 템플릿 타입별 검증
            if template_type == "system":
                if 'system_prompts' not in content:
                    errors.append("시스템 프롬프트가 없습니다")
                    score -= 0.3
                
                if 'constitutional_principles' in content:
                    principles = content['constitutional_principles']
                    for principle in ['helpful', 'harmless', 'honest']:
                        if principle not in principles:
                            warnings.append(f"Constitutional AI 원칙 '{principle}'가 없습니다")
                            score -= 0.1
            
            elif template_type == "user":
                if 'template' not in content and 'instructions' not in content:
                    errors.append("사용자 프롬프트 템플릿이 없습니다")
                    score -= 0.3
            
            # YAML 구조 유효성 확인
            try:
                yaml.dump(content)
            except Exception as e:
                errors.append(f"YAML 구조 오류: {str(e)}")
                score -= 0.5
            
            # 점수 범위 조정
            score = max(0.0, min(1.0, score))
            
            return ValidationResult(
                valid=len(errors) == 0,
                score=score,
                errors=errors,
                warnings=warnings,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"템플릿 검증 실패: {e}")
            return ValidationResult(
                valid=False,
                score=0.0,
                errors=[f"검증 중 오류 발생: {str(e)}"],
                warnings=[],
                recommendations=[]
            )
    
    async def _test_template(self, content: Dict[str, Any], template_type: str) -> Dict[str, Any]:
        """템플릿 테스트"""
        try:
            # 기본 테스트: 프롬프트 생성 가능 여부
            if template_type == "system":
                # 시스템 프롬프트 생성 테스트
                system_prompts = content.get('system_prompts', {})
                if 'ko' in system_prompts:
                    test_prompt = system_prompts['ko']
                    if len(test_prompt) < 50:
                        return {
                            "success": False,
                            "error": "시스템 프롬프트가 너무 짧습니다"
                        }
            
            return {
                "success": True,
                "message": "기본 테스트 통과"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"테스트 실패: {str(e)}"
            }
    
    async def _generate_preview(self, 
                              content: Dict[str, Any], 
                              template_type: str, 
                              test_data: Dict[str, Any]) -> Dict[str, Any]:
        """미리보기 생성"""
        try:
            if template_type == "system":
                system_prompts = content.get('system_prompts', {})
                return {
                    "korean_prompt": system_prompts.get('ko', ''),
                    "english_prompt": system_prompts.get('en', ''),
                    "constitutional_principles": content.get('constitutional_principles', {}),
                    "role_definition": content.get('role_definition', {})
                }
            
            elif template_type == "user":
                template_str = content.get('template', '')
                instructions = content.get('instructions', {})
                
                return {
                    "template": template_str,
                    "korean_instructions": instructions.get('ko', ''),
                    "english_instructions": instructions.get('en', ''),
                    "rendered_preview": "템플릿 렌더링 미리보기 (테스트 데이터 적용)"
                }
            
            return {"preview": "미리보기 생성 중..."}
            
        except Exception as e:
            logger.error(f"미리보기 생성 실패: {e}")
            return {"error": str(e)}
    
    async def _get_default_test_data(self, template_type: str) -> Dict[str, Any]:
        """기본 테스트 데이터 조회"""
        if template_type == "user":
            return {
                "subject": "테스트 티켓 제목",
                "content": "테스트 티켓 내용입니다.",
                "metadata": {"priority": "high", "category": "technical"}
            }
        
        return {}
    
    async def _find_backup_by_version(self, 
                                    template_name: str, 
                                    template_type: str, 
                                    version: str) -> Optional[Path]:
        """버전별 백업 파일 찾기"""
        try:
            for backup_file in self.backups_dir.glob(f"{template_name}_{template_type}_*.yaml"):
                with open(backup_file, 'r', encoding='utf-8') as f:
                    backup_content = yaml.safe_load(f)
                
                if backup_content.get('version') == version:
                    return backup_file
            
            return None
            
        except Exception as e:
            logger.error(f"백업 파일 검색 실패: {e}")
            return None
    
    def _generate_changes_summary(self, 
                                old_content: Optional[Dict[str, Any]], 
                                new_content: Dict[str, Any]) -> str:
        """변경사항 요약 생성"""
        if not old_content:
            return "새 템플릿 생성"
        
        changes = []
        
        # 버전 변경
        old_version = old_content.get('version', 'unknown')
        new_version = new_content.get('version', 'unknown')
        if old_version != new_version:
            changes.append(f"버전: {old_version} → {new_version}")
        
        # 주요 섹션 변경 확인
        important_keys = ['system_prompts', 'constitutional_principles', 'template', 'instructions']
        for key in important_keys:
            if key in old_content and key in new_content:
                if old_content[key] != new_content[key]:
                    changes.append(f"{key} 수정됨")
            elif key in new_content and key not in old_content:
                changes.append(f"{key} 추가됨")
            elif key in old_content and key not in new_content:
                changes.append(f"{key} 제거됨")
        
        return "; ".join(changes) if changes else "내용 변경"
    
    async def _trigger_hot_reload(self):
        """실시간 리로드 트리거"""
        try:
            # AnthropicPromptBuilder 템플릿 다시 로드
            self.prompt_builder.reload_templates()
            logger.info("실시간 리로드 완료")
            
        except Exception as e:
            logger.error(f"실시간 리로드 실패: {e}")
    
    async def _send_change_notification(self, change_log: PromptChangeLog):
        """변경 알림 발송"""
        try:
            notification_settings = self.settings.get_notification_settings()
            
            if not notification_settings['enabled']:
                return
            
            message = f"""
프롬프트 템플릿 변경 알림

템플릿: {change_log.template_name} ({change_log.template_type})
작업: {change_log.action}
사용자: {change_log.user_id}
시간: {change_log.timestamp}
버전: {change_log.old_version} → {change_log.new_version}
변경사항: {change_log.changes_summary}
검증 통과: {'예' if change_log.validation_passed else '아니오'}
자동 백업: {'생성됨' if change_log.auto_backup_created else '생성 안됨'}
            """.strip()
            
            # 실제 알림 발송 로직 (이메일, Slack 등)
            logger.info(f"알림 발송: {change_log.template_name} 변경")
            
        except Exception as e:
            logger.error(f"변경 알림 발송 실패: {e}")
    
    def _load_change_logs(self):
        """변경 로그 로드"""
        try:
            log_file = self.logs_dir / "change_logs.json"
            
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    logs_data = json.load(f)
                
                self.change_logs = [
                    PromptChangeLog(**log_data) for log_data in logs_data
                ]
                
                logger.info(f"변경 로그 {len(self.change_logs)}개 로드")
            
        except Exception as e:
            logger.error(f"변경 로그 로드 실패: {e}")
            self.change_logs = []
    
    async def _save_change_logs(self):
        """변경 로그 저장"""
        try:
            log_file = self.logs_dir / "change_logs.json"
            
            # 최대 보관 수 제한
            max_entries = self.admin_settings['max_history_entries']
            if len(self.change_logs) > max_entries:
                self.change_logs = self.change_logs[-max_entries:]
            
            logs_data = [asdict(log) for log in self.change_logs]
            
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(logs_data, f, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"변경 로그 저장 실패: {e}")


# 전역 프롬프트 관리자 인스턴스
prompt_manager = PromptManager()