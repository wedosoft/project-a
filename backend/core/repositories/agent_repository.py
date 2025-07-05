"""
에이전트 데이터 저장 리포지토리

멀티테넌트 환경에서 에이전트 데이터를 저장하고 관리하는 리포지토리입니다.
"""

import logging
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import and_

from ..database.models.agent import Agent

logger = logging.getLogger(__name__)


class AgentRepository:
    """에이전트 데이터 저장 리포지토리"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def upsert_agent(self, agent_data: Dict[str, Any]) -> Agent:
        """
        에이전트 데이터를 저장하거나 업데이트합니다.
        tenant_id + freshdesk_id 조합으로 중복 체크를 합니다.
        
        Args:
            agent_data: 정규화된 에이전트 데이터
            
        Returns:
            Agent: 저장된 에이전트 객체
        """
        try:
            # 기존 에이전트 확인 (tenant_id + id 조합)
            existing_agent = self.session.query(Agent).filter(
                and_(
                    Agent.tenant_id == agent_data["tenant_id"],
                    Agent.id == agent_data["id"]
                )
            ).first()
            
            if existing_agent:
                # 업데이트
                logger.info(f"에이전트 업데이트: {agent_data['email']} (ID: {agent_data['id']})")
                for key, value in agent_data.items():
                    if key != "tenant_id" and key != "id":  # 키 필드는 업데이트하지 않음
                        setattr(existing_agent, key, value)
                
                self.session.commit()
                return existing_agent
            else:
                # 새로 생성
                logger.info(f"에이전트 생성: {agent_data['email']} (ID: {agent_data['id']})")
                new_agent = Agent(**agent_data)
                self.session.add(new_agent)
                self.session.commit()
                self.session.refresh(new_agent)
                return new_agent
                
        except IntegrityError as e:
            self.session.rollback()
            logger.error(f"에이전트 저장 중 무결성 오류: {e}")
            raise
        except Exception as e:
            self.session.rollback()
            logger.error(f"에이전트 저장 중 오류: {e}")
            raise
    
    def bulk_upsert_agents(self, agents_data: List[Dict[str, Any]]) -> List[Agent]:
        """
        여러 에이전트를 배치로 저장합니다.
        
        Args:
            agents_data: 정규화된 에이전트 데이터 리스트
            
        Returns:
            List[Agent]: 저장된 에이전트 객체 리스트
        """
        saved_agents = []
        
        for agent_data in agents_data:
            try:
                saved_agent = self.upsert_agent(agent_data)
                saved_agents.append(saved_agent)
            except Exception as e:
                logger.error(f"에이전트 배치 저장 중 오류 (ID: {agent_data.get('id')}): {e}")
                # 개별 에이전트 오류는 건너뛰고 계속 진행
                continue
        
        logger.info(f"에이전트 배치 저장 완료: {len(saved_agents)}/{len(agents_data)}개")
        return saved_agents
    
    def get_agents_by_tenant(self, tenant_id: str) -> List[Agent]:
        """
        특정 테넌트의 모든 에이전트를 조회합니다.
        
        Args:
            tenant_id: 테넌트 ID
            
        Returns:
            List[Agent]: 에이전트 리스트
        """
        return self.session.query(Agent).filter(Agent.tenant_id == tenant_id).all()
    
    def get_agent_by_id(self, tenant_id: str, agent_id: int) -> Optional[Agent]:
        """
        ID로 에이전트를 조회합니다.
        
        Args:
            tenant_id: 테넌트 ID
            agent_id: 에이전트 ID
            
        Returns:
            Optional[Agent]: 에이전트 객체 또는 None
        """
        return self.session.query(Agent).filter(
            and_(
                Agent.tenant_id == tenant_id,
                Agent.id == agent_id
            )
        ).first()
    
    def get_active_agents_by_tenant(self, tenant_id: str) -> List[Agent]:
        """
        특정 테넌트의 활성 에이전트만 조회합니다.
        
        Args:
            tenant_id: 테넌트 ID
            
        Returns:
            List[Agent]: 활성 에이전트 리스트
        """
        return self.session.query(Agent).filter(
            and_(
                Agent.tenant_id == tenant_id,
                Agent.license_active == True,
                Agent.active == True,
                Agent.available == True
            )
        ).all()
    
    def update_license_status(self, tenant_id: str, agent_id: int, license_active: bool) -> bool:
        """
        에이전트의 라이선스 상태를 업데이트합니다.
        
        Args:
            tenant_id: 테넌트 ID
            agent_id: 에이전트 ID
            license_active: 라이선스 활성화 여부
            
        Returns:
            bool: 업데이트 성공 여부
        """
        try:
            agent = self.get_agent_by_id(tenant_id, agent_id)
            if agent:
                agent.license_active = license_active
                self.session.commit()
                logger.info(f"에이전트 라이선스 상태 업데이트: {agent.email} -> {license_active}")
                return True
            else:
                logger.warning(f"에이전트를 찾을 수 없음: tenant_id={tenant_id}, id={agent_id}")
                return False
        except Exception as e:
            self.session.rollback()
            logger.error(f"라이선스 상태 업데이트 중 오류: {e}")
            return False
    
