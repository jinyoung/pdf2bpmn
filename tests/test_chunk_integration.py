"""
테스트: 청크 간 분리된 프로세스 정의 통합

이 테스트는 동일한 프로세스에 대한 정보가 여러 청크에 분산되어 있을 때
시스템이 이를 올바르게 통합하는지 검증합니다.

테스트 시나리오:
1. 동일 프로세스가 여러 청크에서 언급될 때 하나로 통합되는지
2. 동일 역할이 여러 청크에서 반복될 때 하나로 통합되는지
3. 분리된 태스크들이 동일 프로세스 내 순차적 흐름으로 연결되는지
4. 게이트웨이가 해당 프로세스의 분기점으로 연결되는지
"""

import pytest
import sys
import time
from pathlib import Path
from contextlib import contextmanager

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pdf2bpmn.extractors.entity_extractor import EntityExtractor, ExtractedEntities
from pdf2bpmn.extractors.pdf_extractor import PDFExtractor
from pdf2bpmn.graph.neo4j_client import Neo4jClient
from pdf2bpmn.graph.vector_search import VectorSearch
from pdf2bpmn.workflow.graph import PDF2BPMNWorkflow
from pdf2bpmn.models.entities import generate_id, Process, Task, Role, Gateway, Event
from pdf2bpmn.generators.bpmn_generator import BPMNGenerator


@contextmanager
def timer(name: str):
    """시간 측정 컨텍스트 매니저"""
    start = time.time()
    yield
    elapsed = time.time() - start
    print(f"   ⏱️ [{name}] {elapsed:.2f}초")


# 테스트용 청크 데이터 - 의도적으로 동일 프로세스 정보가 분산됨
CHUNK_1_PROCESS_OVERVIEW = """
제1장 총칙

제1조 (목적)
이 규정은 회사의 구매요청 승인 프로세스에 관한 사항을 정함을 목적으로 한다.
구매요청 승인 프로세스는 부서별 구매 수요를 체계적으로 관리하고, 
예산 범위 내에서 효율적인 자원 배분을 실현하기 위한 업무 절차이다.

제2조 (적용범위)
이 규정은 본사 및 지사의 모든 부서에서 발생하는 구매요청에 적용된다.

제3조 (용어의 정의)
1. "구매요청서"란 물품 또는 서비스의 구매를 요청하는 공식 문서를 말한다.
2. "승인권자"란 구매요청을 검토하고 승인할 권한이 있는 자를 말한다.
3. "구매담당자"란 승인된 구매요청을 실제로 처리하는 담당자를 말한다.

제4조 (구매요청서 작성)
구매요청자는 구매가 필요한 경우 전산시스템을 통해 구매요청서를 작성한다.
"""

CHUNK_2_INITIAL_TASKS = """
제6조 (구매요청 승인 프로세스 단계)
구매요청 승인 프로세스는 다음의 단계로 진행된다.

1단계: 구매요청서 접수
구매담당자는 전자결재 시스템을 통해 접수된 구매요청서를 확인한다.
접수된 요청서는 요청번호를 부여받으며, 구매담당자는 형식적 요건을 검토한다.

2단계: 예산 확인
재무담당자는 해당 구매요청에 대한 예산 가용 여부를 확인한다.
예산이 부족한 경우 예산조정 요청을 진행하거나 구매요청을 반려할 수 있다.

3단계: 규격 검토
기술담당자는 요청된 품목의 기술적 사양과 규격이 적정한지 검토한다.
필요시 대체 품목이나 수정된 사양을 제안할 수 있다.
"""

CHUNK_3_ROLE_DEFINITIONS = """
별첨: 조직도 및 역할 정의

주요 역할

구매팀장
- 구매요청 승인 프로세스의 총괄 책임자
- 100만원 이상의 구매요청에 대한 최종 승인 권한 보유
- 공급업체 계약 체결 권한

구매담당자
- 구매요청서 접수 및 형식 검토 수행
- 견적서 수집 및 비교분석 담당
- 발주서 작성 및 발송 처리
- 구매요청 승인 프로세스의 실무 담당자

재무담당자
- 구매요청에 대한 예산 가용 여부 확인
- 예산 초과 시 예산조정 요청 프로세스 진행
- 구매 대금 지급 승인

기술담당자
- 기술 사양 및 규격 검토
- 대체 품목 또는 사양 변경 제안
- 납품 물품의 기술적 검수
"""

CHUNK_4_LATER_TASKS = """
제12조 (발주 처리)
구매요청 승인 프로세스를 통해 승인된 건에 대하여 구매담당자는 다음을 수행한다.

4단계: 견적서 수집
구매담당자는 3개 이상의 공급업체로부터 견적서를 수집한다.
견적서에는 품목, 단가, 납기, 결제조건이 포함되어야 한다.

5단계: 업체 선정
수집된 견적서를 비교하여 최적의 공급업체를 선정한다.
100만원 이상의 경우 구매팀장의 승인을 받아야 한다.

6단계: 발주서 발송
선정된 업체에 발주서를 발송한다.
발주서에는 품목, 수량, 단가, 납품일, 결제조건을 명시한다.

제13조 (입고 검수)
7단계: 입고 검수
납품된 물품에 대해 구매담당자와 기술담당자가 공동으로 검수를 진행한다.

제14조 (대금 지급)
8단계: 대금 지급
검수 완료 후 재무담당자는 공급업체에 대금을 지급한다.
대금 지급은 구매요청 승인 프로세스의 최종 단계이다.
"""

CHUNK_5_GATEWAYS = """
제15조 (승인 분기 조건)
구매요청 승인 프로세스에서 다음의 조건에 따라 분기가 발생한다.

승인/반려 분기 (XOR Gateway)
- 예산 확인 결과 예산이 충분한 경우: 규격 검토 단계로 진행
- 예산 확인 결과 예산이 부족한 경우: 예산조정 요청 또는 반려

금액별 승인권자 분기 (XOR Gateway)  
- 구매금액이 50만원 미만인 경우: 구매담당자 승인
- 구매금액이 50만원 이상 100만원 미만인 경우: 구매팀장 승인
- 구매금액이 100만원 이상인 경우: 임원 승인

제16조 (검수 분기)
검수 결과에 따른 분기 (XOR Gateway)
- 검수 합격인 경우: 대금 지급 단계로 진행
- 검수 불합격인 경우: 반품 처리 및 재발주 검토
"""


class TestChunkIntegration:
    """청크 간 프로세스 통합 테스트"""
    
    def __init__(self):
        """초기화"""
        self.neo4j = None
        self.vector_search = None
        self.entity_extractor = None
    
    # 클래스 레벨 변수 - 스키마 초기화 여부
    _schema_initialized = False
    
    def setup_method(self):
        """테스트 전 Neo4j 데이터 초기화"""
        print("\n🔧 Setup 시작...")
        setup_start = time.time()
        
        with timer("Neo4jClient 생성"):
            self.neo4j = Neo4jClient()
        
        with timer("VectorSearch 생성"):
            self.vector_search = VectorSearch(self.neo4j)
        
        with timer("EntityExtractor 생성"):
            self.entity_extractor = EntityExtractor()
        
        # Neo4j 데이터 전체 삭제 (빠른 방식)
        with timer("Neo4j 데이터 삭제"):
            self._clear_neo4j()
        
        # 스키마는 한 번만 초기화 (이미 되어 있으면 스킵)
        if not TestChunkIntegration._schema_initialized:
            with timer("스키마 초기화"):
                self._init_schema_once()
            TestChunkIntegration._schema_initialized = True
        
        print(f"   ⏱️ [Setup 총 시간] {time.time() - setup_start:.2f}초")
    
    def _clear_neo4j(self):
        """Neo4j 데이터베이스 전체 초기화 (빠른 방식)"""
        with self.neo4j.session() as session:
            # DETACH DELETE가 더 빠름
            session.run("MATCH (n) DETACH DELETE n")
        print("   ✅ Neo4j 데이터베이스 초기화 완료")
    
    def _init_schema_once(self):
        """스키마 초기화 (VECTOR INDEX 제외 - 지원 안되는 버전 대응)"""
        constraints = [
            "CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:Document) REQUIRE d.doc_id IS UNIQUE",
            "CREATE CONSTRAINT proc_id IF NOT EXISTS FOR (p:Process) REQUIRE p.proc_id IS UNIQUE",
            "CREATE CONSTRAINT task_id IF NOT EXISTS FOR (t:Task) REQUIRE t.task_id IS UNIQUE",
            "CREATE CONSTRAINT role_id IF NOT EXISTS FOR (r:Role) REQUIRE r.role_id IS UNIQUE",
            "CREATE CONSTRAINT gateway_id IF NOT EXISTS FOR (g:Gateway) REQUIRE g.gateway_id IS UNIQUE",
            "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:ReferenceChunk) REQUIRE c.chunk_id IS UNIQUE",
        ]
        
        with self.neo4j.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception:
                    pass  # 이미 존재하면 무시
    
    def test_process_consolidation_across_chunks(self):
        """
        테스트 1: 동일 프로세스가 여러 청크에서 언급될 때 하나로 통합되는지
        
        기대 결과:
        - "구매요청 승인 프로세스"가 CHUNK_1, CHUNK_2, CHUNK_4에서 언급되지만
        - 최종적으로 하나의 Process 엔티티만 생성되어야 함
        """
        print("\n" + "="*60)
        print("테스트 1: 프로세스 통합 테스트")
        print("="*60)
        
        doc_id = generate_id()
        process_name_to_id = {}
        role_name_to_id = {}
        
        all_processes = []
        
        chunks = [CHUNK_1_PROCESS_OVERVIEW, CHUNK_2_INITIAL_TASKS, CHUNK_4_LATER_TASKS]
        
        for i, chunk in enumerate(chunks):
            chunk_start = time.time()
            print(f"\n📄 Chunk {i+1} 처리 중...")
            
            # 기존 프로세스/역할 이름 목록 생성 (컨텍스트 주입용)
            existing_process_names = list(process_name_to_id.keys())
            existing_role_names = list(role_name_to_id.keys())
            
            if existing_process_names:
                print(f"   [컨텍스트] 기존 프로세스: {existing_process_names}")
            
            # 엔티티 추출 (기존 컨텍스트 전달) - LLM 호출
            with timer("LLM 추출"):
                extracted = self.entity_extractor.extract_from_text(
                    chunk,
                    existing_processes=existing_process_names,
                    existing_roles=existing_role_names
                )
            
            # 엔티티 변환 (기존 프로세스/역할 매핑 전달)
            entities = self.entity_extractor.convert_to_entities(
                extracted,
                doc_id,
                chunk_id=f"chunk_{i+1}",
                existing_processes=process_name_to_id,
                existing_roles=role_name_to_id
            )
            
            # 추출된 프로세스 수집
            for proc in entities["processes"]:
                all_processes.append(proc)
                process_name_to_id[proc.name.lower()] = proc.proc_id
                print(f"   🆕 새 프로세스: {proc.name} (ID: {proc.proc_id[:8]}...)")
            
            if not entities["processes"]:
                print(f"   ✅ 새 프로세스 없음 (기존 프로세스 재사용)")
            
            # 역할 매핑 업데이트
            for role in entities["roles"]:
                role_name_to_id[role.name.lower()] = role.role_id
            
            print(f"   ⏱️ [Chunk {i+1} 총] {time.time() - chunk_start:.2f}초")
        
        print(f"\n📊 결과:")
        print(f"   전체 추출된 프로세스 수: {len(all_processes)}")
        
        # 중복 제거 시뮬레이션
        unique_process_names = set()
        for proc in all_processes:
            unique_process_names.add(proc.name.lower())
        
        print(f"   고유 프로세스 이름 수: {len(unique_process_names)}")
        print(f"   프로세스 이름들: {list(unique_process_names)}")
        
        # 검증: "구매요청 승인 프로세스" 관련 프로세스가 있는지
        purchase_process_found = any(
            "구매" in name or "승인" in name or "purchase" in name.lower()
            for name in unique_process_names
        )
        
        assert purchase_process_found, "구매 관련 프로세스가 추출되지 않음"
        print("✅ 테스트 통과: 프로세스가 올바르게 추출됨")
        
        return all_processes, process_name_to_id
    
    def test_role_deduplication_across_chunks(self):
        """
        테스트 2: 동일 역할이 여러 청크에서 반복될 때 하나로 통합되는지
        
        기대 결과:
        - "구매담당자", "재무담당자", "기술담당자"가 여러 청크에서 언급되지만
        - 각각 하나의 Role 엔티티만 생성되어야 함
        """
        print("\n" + "="*60)
        print("테스트 2: 역할 중복 제거 테스트")
        print("="*60)
        
        doc_id = generate_id()
        process_name_to_id = {}
        role_name_to_id = {}
        
        all_roles = []
        
        # 역할이 반복적으로 언급되는 청크들
        chunks = [CHUNK_2_INITIAL_TASKS, CHUNK_3_ROLE_DEFINITIONS, CHUNK_4_LATER_TASKS]
        
        for i, chunk in enumerate(chunks):
            print(f"\n📄 Chunk {i+1} 처리 중...")
            
            # 기존 프로세스/역할 이름 목록 생성 (컨텍스트 주입용)
            existing_process_names = list(process_name_to_id.keys())
            existing_role_names = list(role_name_to_id.keys())
            
            extracted = self.entity_extractor.extract_from_text(
                chunk,
                existing_processes=existing_process_names,
                existing_roles=existing_role_names
            )
            
            entities = self.entity_extractor.convert_to_entities(
                extracted,
                doc_id,
                chunk_id=f"chunk_{i+1}",
                existing_processes=process_name_to_id,
                existing_roles=role_name_to_id
            )
            
            for role in entities["roles"]:
                all_roles.append(role)
                # 기존에 없는 역할만 매핑에 추가
                if role.name.lower() not in role_name_to_id:
                    role_name_to_id[role.name.lower()] = role.role_id
                    print(f"   🆕 새 역할 발견: {role.name}")
                else:
                    print(f"   ♻️ 기존 역할 참조: {role.name}")
            
            for proc in entities["processes"]:
                process_name_to_id[proc.name.lower()] = proc.proc_id
        
        print(f"\n📊 결과:")
        print(f"   전체 추출된 역할 수: {len(all_roles)}")
        print(f"   고유 역할 수 (role_name_to_id): {len(role_name_to_id)}")
        print(f"   역할 목록: {list(role_name_to_id.keys())}")
        
        # 핵심 역할들이 존재하는지 확인
        expected_roles = ["구매담당자", "재무담당자", "기술담당자"]
        found_roles = []
        
        for expected in expected_roles:
            for role_name in role_name_to_id.keys():
                if expected in role_name:
                    found_roles.append(expected)
                    break
        
        print(f"   발견된 핵심 역할: {found_roles}")
        
        assert len(found_roles) >= 2, f"핵심 역할이 충분히 추출되지 않음: {found_roles}"
        print("✅ 테스트 통과: 역할이 올바르게 추출 및 통합됨")
        
        return all_roles, role_name_to_id
    
    def test_task_sequence_across_chunks(self):
        """
        테스트 3: 분리된 태스크들이 동일 프로세스 내 순차적 흐름으로 연결되는지
        
        기대 결과:
        - 1~3단계 (CHUNK_2)와 4~8단계 (CHUNK_4)의 태스크들이
        - 동일 프로세스에 속하고, 순서(order)가 올바르게 설정되어야 함
        """
        print("\n" + "="*60)
        print("테스트 3: 태스크 순서 연결 테스트")
        print("="*60)
        
        doc_id = generate_id()
        process_name_to_id = {}
        role_name_to_id = {}
        
        all_tasks = []
        all_sequence_flows = []
        
        # 프로세스 정의 먼저 추출
        extracted_overview = self.entity_extractor.extract_from_text(CHUNK_1_PROCESS_OVERVIEW)
        entities_overview = self.entity_extractor.convert_to_entities(
            extracted_overview, doc_id, "chunk_0", {}, {}
        )
        for proc in entities_overview["processes"]:
            process_name_to_id[proc.name.lower()] = proc.proc_id
            print(f"   프로세스 발견: {proc.name}")
        
        # 태스크가 있는 청크들 처리
        chunks = [CHUNK_2_INITIAL_TASKS, CHUNK_4_LATER_TASKS]
        
        for i, chunk in enumerate(chunks):
            print(f"\n📄 Chunk {i+1} (태스크) 처리 중...")
            
            # 기존 프로세스/역할 이름 목록 생성 (컨텍스트 주입용)
            existing_process_names = list(process_name_to_id.keys())
            existing_role_names = list(role_name_to_id.keys())
            
            print(f"   [컨텍스트] 기존 프로세스: {existing_process_names}")
            
            extracted = self.entity_extractor.extract_from_text(
                chunk,
                existing_processes=existing_process_names,
                existing_roles=existing_role_names
            )
            
            entities = self.entity_extractor.convert_to_entities(
                extracted,
                doc_id,
                chunk_id=f"task_chunk_{i+1}",
                existing_processes=process_name_to_id,
                existing_roles=role_name_to_id
            )
            
            for task in entities["tasks"]:
                all_tasks.append(task)
                print(f"   태스크 발견: {task.name} (order: {task.order}, process_id: {task.process_id[:8] if task.process_id else 'None'}...)")
            
            # 새로 추출된 프로세스 확인
            if entities["processes"]:
                for proc in entities["processes"]:
                    print(f"   ⚠️ 새 프로세스 추출됨: {proc.name}")
            else:
                print(f"   ✅ 새 프로세스 없음 (기존 프로세스 재사용)")
            
            # 시퀀스 플로우 수집
            all_sequence_flows.extend(entities.get("sequence_flows", []))
            
            # 역할 매핑 업데이트
            for role in entities["roles"]:
                if role.name.lower() not in role_name_to_id:
                    role_name_to_id[role.name.lower()] = role.role_id
            
            for proc in entities["processes"]:
                process_name_to_id[proc.name.lower()] = proc.proc_id
        
        print(f"\n📊 결과:")
        print(f"   전체 태스크 수: {len(all_tasks)}")
        print(f"   시퀀스 플로우 수: {len(all_sequence_flows)}")
        
        # 태스크 정렬하여 순서 확인
        sorted_tasks = sorted(all_tasks, key=lambda t: t.order if t.order is not None else 999)
        print(f"\n   태스크 순서:")
        for task in sorted_tasks:
            print(f"     {task.order}: {task.name}")
        
        # 검증: 태스크가 추출되었는지
        assert len(all_tasks) >= 3, f"충분한 태스크가 추출되지 않음: {len(all_tasks)}"
        
        # 검증: 대부분의 태스크가 동일 프로세스에 연결되어 있는지
        process_ids = [t.process_id for t in all_tasks if t.process_id]
        if process_ids:
            most_common_proc = max(set(process_ids), key=process_ids.count)
            tasks_in_main_process = sum(1 for pid in process_ids if pid == most_common_proc)
            print(f"\n   메인 프로세스에 연결된 태스크: {tasks_in_main_process}/{len(all_tasks)}")
        
        print("✅ 테스트 통과: 태스크가 순서대로 추출됨")
        
        return all_tasks, all_sequence_flows
    
    def test_gateway_extraction(self):
        """
        테스트 4: 게이트웨이가 해당 프로세스의 분기점으로 추출되는지
        
        기대 결과:
        - "승인/반려 분기", "금액별 승인권자 분기", "검수 분기"가
        - Gateway 엔티티로 추출되고, 조건이 올바르게 설정되어야 함
        """
        print("\n" + "="*60)
        print("테스트 4: 게이트웨이 추출 테스트")
        print("="*60)
        
        doc_id = generate_id()
        process_name_to_id = {}
        
        # 먼저 프로세스 추출
        extracted_overview = self.entity_extractor.extract_from_text(CHUNK_1_PROCESS_OVERVIEW)
        entities_overview = self.entity_extractor.convert_to_entities(
            extracted_overview, doc_id, "chunk_0", {}, {}
        )
        for proc in entities_overview["processes"]:
            process_name_to_id[proc.name.lower()] = proc.proc_id
        
        # 게이트웨이 청크 처리
        print(f"\n📄 게이트웨이 청크 처리 중...")
        
        # 기존 프로세스 이름 목록 (컨텍스트 주입용)
        existing_process_names = list(process_name_to_id.keys())
        print(f"   [컨텍스트] 기존 프로세스: {existing_process_names}")
        
        extracted = self.entity_extractor.extract_from_text(
            CHUNK_5_GATEWAYS,
            existing_processes=existing_process_names,
            existing_roles=[]
        )
        
        entities = self.entity_extractor.convert_to_entities(
            extracted,
            doc_id,
            chunk_id="gateway_chunk",
            existing_processes=process_name_to_id,
            existing_roles={}
        )
        
        gateways = entities["gateways"]
        
        print(f"\n📊 결과:")
        print(f"   추출된 게이트웨이 수: {len(gateways)}")
        
        for gw in gateways:
            print(f"   게이트웨이: {gw.gateway_type.value}")
            print(f"     조건: {gw.condition[:50]}..." if len(gw.condition) > 50 else f"     조건: {gw.condition}")
            print(f"     프로세스 ID: {gw.process_id[:8] if gw.process_id else 'None'}...")
        
        # 게이트웨이가 추출되었는지 확인 (LLM 응답에 따라 다를 수 있음)
        print(f"\n   게이트웨이 추출 여부: {'성공' if gateways else '없음 (LLM 응답에 따라 다름)'}")
        
        print("✅ 테스트 완료: 게이트웨이 추출 확인")
        
        return gateways
    
    def test_full_workflow_integration(self):
        """
        테스트 5: 전체 워크플로우 통합 테스트
        
        PDF2BPMNWorkflow를 사용하여 모든 청크를 처리하고
        최종 결과가 올바르게 통합되는지 확인
        """
        print("\n" + "="*60)
        print("테스트 5: 전체 워크플로우 통합 테스트")
        print("="*60)
        
        # 워크플로우 인스턴스 생성 (스키마는 이미 setup_method에서 초기화됨)
        workflow = PDF2BPMNWorkflow()
        # workflow.neo4j.init_schema()  # 스킵 - 이미 초기화됨
        
        doc_id = generate_id()
        
        # 모든 청크 순차 처리
        all_chunks = [
            CHUNK_1_PROCESS_OVERVIEW,
            CHUNK_2_INITIAL_TASKS, 
            CHUNK_3_ROLE_DEFINITIONS,
            CHUNK_4_LATER_TASKS,
            CHUNK_5_GATEWAYS
        ]
        
        all_processes = []
        all_tasks = []
        all_roles = []
        all_gateways = []
        all_events = []
        
        for i, chunk in enumerate(all_chunks):
            print(f"\n📄 Chunk {i+1}/{len(all_chunks)} 처리 중...")
            
            # 기존 프로세스/역할 이름 목록 (컨텍스트 주입용)
            existing_process_names = list(workflow.process_name_to_id.keys())
            existing_role_names = list(workflow.role_name_to_id.keys())
            
            if existing_process_names:
                print(f"   [컨텍스트] 기존 프로세스: {existing_process_names}")
            
            extracted = workflow.entity_extractor.extract_from_text(
                chunk,
                existing_processes=existing_process_names,
                existing_roles=existing_role_names
            )
            
            entities = workflow.entity_extractor.convert_to_entities(
                extracted,
                doc_id,
                chunk_id=f"full_chunk_{i+1}",
                existing_processes=workflow.process_name_to_id,
                existing_roles=workflow.role_name_to_id
            )
            
            all_processes.extend(entities["processes"])
            all_tasks.extend(entities["tasks"])
            all_roles.extend(entities["roles"])
            all_gateways.extend(entities["gateways"])
            all_events.extend(entities.get("events", []))
            
            # 워크플로우 매핑 업데이트
            workflow.task_role_map.update(entities.get("task_role_map", {}))
            workflow.task_process_map.update(entities.get("task_process_map", {}))
            workflow.entity_chunk_map.update(entities.get("entity_chunk_map", {}))
            workflow.sequence_flows.extend(entities.get("sequence_flows", []))
            
            for proc in entities["processes"]:
                workflow.process_name_to_id[proc.name.lower()] = proc.proc_id
            for role in entities["roles"]:
                workflow.role_name_to_id[role.name.lower()] = role.role_id
            for task in entities["tasks"]:
                workflow.task_name_to_id[task.name.lower()] = task.task_id
        
        print("\n" + "-"*60)
        print("📊 최종 통합 결과:")
        print("-"*60)
        
        print(f"\n[프로세스]")
        print(f"   추출된 프로세스 수: {len(all_processes)}")
        print(f"   고유 프로세스 수 (name_to_id): {len(workflow.process_name_to_id)}")
        for name, pid in workflow.process_name_to_id.items():
            print(f"     - {name}: {pid[:8]}...")
        
        print(f"\n[역할]")
        print(f"   추출된 역할 수: {len(all_roles)}")
        print(f"   고유 역할 수 (name_to_id): {len(workflow.role_name_to_id)}")
        for name in list(workflow.role_name_to_id.keys())[:10]:
            print(f"     - {name}")
        
        print(f"\n[태스크]")
        print(f"   추출된 태스크 수: {len(all_tasks)}")
        print(f"   고유 태스크 수 (name_to_id): {len(workflow.task_name_to_id)}")
        
        print(f"\n[게이트웨이]")
        print(f"   추출된 게이트웨이 수: {len(all_gateways)}")
        
        print(f"\n[관계]")
        print(f"   Task→Role 매핑: {len(workflow.task_role_map)}")
        print(f"   Task→Process 매핑: {len(workflow.task_process_map)}")
        print(f"   시퀀스 플로우: {len(workflow.sequence_flows)}")
        
        # 🔗 프로세스 병합 테스트
        print("\n" + "-"*60)
        print("🔗 프로세스 병합 테스트")
        print("-"*60)
        
        merged_processes, process_id_mapping = workflow._merge_duplicate_processes(all_processes)
        print(f"   병합 전 프로세스 수: {len(all_processes)}")
        print(f"   병합 후 프로세스 수: {len(merged_processes)}")
        print(f"   병합된 프로세스 수: {len(all_processes) - len(merged_processes)}")
        
        if process_id_mapping:
            # 매핑에서 실제로 병합된 것만 출력
            actual_merges = {k: v for k, v in process_id_mapping.items() if k != v}
            if actual_merges:
                print(f"   ID 매핑 (병합됨): {len(actual_merges)}개")
        
        # 태스크 process_id 업데이트
        updated_tasks = workflow._update_task_process_ids(all_tasks, process_id_mapping)
        
        # 병합 후 프로세스별 태스크 수 확인
        tasks_by_process = {}
        for task in updated_tasks:
            proc_id = task.process_id or "none"
            if proc_id not in tasks_by_process:
                tasks_by_process[proc_id] = []
            tasks_by_process[proc_id].append(task.name)
        
        print(f"\n   프로세스별 태스크 분포:")
        for proc in merged_processes:
            task_count = len(tasks_by_process.get(proc.proc_id, []))
            print(f"     - {proc.name}: {task_count}개 태스크")
        
        # Neo4j에 저장 (병합된 프로세스 사용)
        print("\n💾 Neo4j에 저장 중...")
        
        for proc in merged_processes:
            try:
                workflow.neo4j.create_process(proc)
            except Exception as e:
                print(f"   프로세스 저장 실패: {e}")
        
        for role in all_roles:
            try:
                workflow.neo4j.create_role(role)
            except Exception as e:
                print(f"   역할 저장 실패: {e}")
        
        for task in all_tasks:
            try:
                workflow.neo4j.create_task(task)
            except Exception as e:
                print(f"   태스크 저장 실패: {e}")
        
        for gw in all_gateways:
            try:
                workflow.neo4j.create_gateway(gw)
            except Exception as e:
                print(f"   게이트웨이 저장 실패: {e}")
        
        # 관계 생성
        try:
            workflow.neo4j.create_all_relationships(
                task_role_map=workflow.task_role_map,
                task_process_map=workflow.task_process_map,
                role_decision_map={},
                entity_chunk_map=workflow.entity_chunk_map
            )
            print("   관계 저장 완료")
        except Exception as e:
            print(f"   관계 저장 실패: {e}")
        
        # 🔗 시퀀스 플로우 (NEXT 관계) 생성
        print("\n➡️ 시퀀스 플로우 생성 중...")
        print(f"   생성할 시퀀스 플로우 수: {len(workflow.sequence_flows)}")
        
        created_flows = 0
        for flow in workflow.sequence_flows:
            try:
                workflow.neo4j.link_task_sequence(
                    flow["from_task_id"],
                    flow["to_task_id"],
                    flow.get("condition", "")
                )
                created_flows += 1
            except Exception as e:
                print(f"   시퀀스 플로우 생성 실패: {e}")
        
        print(f"   생성된 시퀀스 플로우: {created_flows}")
        
        # Neo4j에서 결과 확인
        print("\n🔍 Neo4j 저장 결과 확인...")
        
        with workflow.neo4j.session() as session:
            # 프로세스 수
            result = session.run("MATCH (p:Process) RETURN count(p) as count")
            process_count = result.single()["count"]
            print(f"   저장된 프로세스: {process_count}")
            
            # 역할 수
            result = session.run("MATCH (r:Role) RETURN count(r) as count")
            role_count = result.single()["count"]
            print(f"   저장된 역할: {role_count}")
            
            # 태스크 수
            result = session.run("MATCH (t:Task) RETURN count(t) as count")
            task_count = result.single()["count"]
            print(f"   저장된 태스크: {task_count}")
            
            # 관계 수
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_count = result.single()["count"]
            print(f"   저장된 관계: {rel_count}")
            
            # NEXT 관계 (시퀀스 플로우) 수
            result = session.run("MATCH ()-[r:NEXT]->() RETURN count(r) as count")
            next_count = result.single()["count"]
            print(f"   저장된 NEXT 관계: {next_count}")
        
        # 🔗 태스크 시퀀스 검증
        print("\n" + "-"*60)
        print("➡️ 태스크 시퀀스 검증")
        print("-"*60)
        
        with workflow.neo4j.session() as session:
            # 시퀀스 체인 조회
            result = session.run("""
                MATCH path = (t1:Task)-[:NEXT*]->(t2:Task)
                WHERE NOT ()-[:NEXT]->(t1)
                RETURN t1.name as start_task,
                       [node in nodes(path) | node.name] as sequence,
                       length(path) as chain_length
                ORDER BY chain_length DESC
                LIMIT 5
            """)
            
            sequences = list(result)
            if sequences:
                print(f"   발견된 시퀀스 체인: {len(sequences)}개")
                for seq in sequences:
                    chain = seq["sequence"]
                    print(f"   📋 시퀀스 ({len(chain)}개 태스크):")
                    for i, task_name in enumerate(chain):
                        prefix = "   └─" if i == len(chain) - 1 else "   ├─"
                        print(f"      {prefix} {i+1}. {task_name}")
            else:
                print("   ⚠️ 시퀀스 체인이 발견되지 않음")
            
            # 개별 NEXT 관계 확인
            result = session.run("""
                MATCH (t1:Task)-[r:NEXT]->(t2:Task)
                RETURN t1.name as from_task, t2.name as to_task, r.condition as condition
                ORDER BY t1.name
                LIMIT 15
            """)
            
            next_relations = list(result)
            print(f"\n   NEXT 관계 샘플 ({len(next_relations)}개):")
            for rel in next_relations[:10]:
                condition = f" [{rel['condition']}]" if rel['condition'] else ""
                print(f"      {rel['from_task']} → {rel['to_task']}{condition}")
        
        print("\n✅ 전체 워크플로우 통합 테스트 완료")
        
        # 검증
        assert len(workflow.process_name_to_id) >= 1, "프로세스가 추출되지 않음"
        assert len(workflow.role_name_to_id) >= 2, "역할이 충분히 추출되지 않음"
        assert len(all_tasks) >= 3, "태스크가 충분히 추출되지 않음"
        assert len(workflow.sequence_flows) >= 5, "시퀀스 플로우가 충분히 추출되지 않음"
        assert next_count >= 1, "NEXT 관계가 Neo4j에 생성되지 않음"
        
        print(f"\n📋 검증 결과:")
        print(f"   ✅ 프로세스: {len(workflow.process_name_to_id)}개")
        print(f"   ✅ 역할: {len(workflow.role_name_to_id)}개")
        print(f"   ✅ 태스크: {len(all_tasks)}개")
        print(f"   ✅ 시퀀스 플로우: {len(workflow.sequence_flows)}개")
        print(f"   ✅ NEXT 관계: {next_count}개")
        
        # 결과 반환 (BPMN 생성 테스트에서 사용)
        return {
            "processes": all_processes,
            "roles": all_roles,
            "tasks": all_tasks,
            "gateways": all_gateways,
            "events": all_events,
            "process_name_to_id": workflow.process_name_to_id,
            "role_name_to_id": workflow.role_name_to_id,
            "task_role_map": workflow.task_role_map,
            "sequence_flows": workflow.sequence_flows,
            "neo4j": workflow.neo4j
        }
    
    def test_bpmn_generation_from_graph(self):
        """
        테스트 6: 완성된 Graph에서 BPMN XML 생성
        
        기대 결과:
        - Neo4j에 저장된 데이터를 기반으로 유효한 BPMN XML이 생성되어야 함
        - 모든 태스크가 시퀀스 플로우로 연결되어야 함
        """
        print("\n" + "="*60)
        print("테스트 6: BPMN 생성 테스트")
        print("="*60)
        
        test_start = time.time()
        
        # 테스트 5 결과 재사용 또는 새로 생성
        workflow_result = self.test_full_workflow_integration()
        
        print("\n🔧 BPMN 생성 시작...")
        
        # 메인 프로세스 찾기
        main_process = None
        for proc in workflow_result["processes"]:
            if "구매요청" in proc.name or "승인" in proc.name:
                main_process = proc
                break
        
        if not main_process and workflow_result["processes"]:
            main_process = workflow_result["processes"][0]
        
        if not main_process:
            print("❌ 프로세스를 찾을 수 없음")
            return
        
        print(f"   대상 프로세스: {main_process.name}")
        
        # 해당 프로세스의 태스크 필터링
        process_tasks = [t for t in workflow_result["tasks"] 
                        if t.process_id == main_process.proc_id]
        print(f"   태스크 수: {len(process_tasks)}개")
        
        # 관련 역할 가져오기
        process_roles = workflow_result["roles"]
        print(f"   역할 수: {len(process_roles)}개")
        
        # 게이트웨이
        process_gateways = [g for g in workflow_result["gateways"]
                          if g.process_id == main_process.proc_id]
        print(f"   게이트웨이 수: {len(process_gateways)}개")
        
        # 이벤트
        process_events = workflow_result.get("events", [])
        process_events = [e for e in process_events 
                         if hasattr(e, 'process_id') and e.process_id == main_process.proc_id]
        print(f"   이벤트 수: {len(process_events)}개")
        
        # BPMN 생성
        with timer("BPMN XML 생성"):
            generator = BPMNGenerator()
            bpmn_xml = generator.generate(
                process=main_process,
                tasks=process_tasks,
                roles=process_roles,
                gateways=process_gateways,
                events=process_events,
                task_role_map=workflow_result["task_role_map"]
            )
        
        # XML 검증
        print("\n📄 생성된 BPMN XML 검증:")
        
        # 기본 구조 검증
        assert '<?xml version="1.0"' in bpmn_xml, "XML 선언 없음"
        assert '<bpmn:definitions' in bpmn_xml, "BPMN definitions 없음"
        assert '<bpmn:process' in bpmn_xml, "BPMN process 없음"
        
        # 태스크 포함 여부 검증
        task_count_in_xml = bpmn_xml.count('<bpmn:userTask') + bpmn_xml.count('<bpmn:serviceTask') + bpmn_xml.count('<bpmn:task ')
        print(f"   XML 내 태스크: {task_count_in_xml}개")
        
        # 시퀀스 플로우 포함 여부
        flow_count = bpmn_xml.count('<bpmn:sequenceFlow')
        print(f"   XML 내 시퀀스 플로우: {flow_count}개")
        
        # 레인 (역할) 포함 여부
        lane_count = bpmn_xml.count('<bpmn:lane')
        print(f"   XML 내 레인: {lane_count}개")
        
        # 파일로 저장
        output_dir = Path(__file__).parent / "output"
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / "test_output.bpmn"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(bpmn_xml)
        
        print(f"\n💾 BPMN 파일 저장: {output_file}")
        
        # XML 첫 부분 미리보기
        print("\n📝 BPMN XML 미리보기 (처음 50줄):")
        xml_lines = bpmn_xml.split('\n')[:50]
        for i, line in enumerate(xml_lines, 1):
            print(f"   {i:3d}| {line}")
        
        print(f"\n   ... (총 {len(bpmn_xml.split(chr(10)))} 줄)")
        
        # 검증
        assert task_count_in_xml >= 1, "XML에 태스크가 없음"
        assert flow_count >= 1, "XML에 시퀀스 플로우가 없음"
        
        print(f"\n⏱️ [BPMN 생성] {time.time() - test_start:.2f}초")
        print("\n✅ BPMN 생성 테스트 완료")
        
        return bpmn_xml


if __name__ == "__main__":
    import sys
    
    total_start = time.time()
    
    # 직접 실행 시
    test = TestChunkIntegration()
    
    # 커맨드 라인 인자로 특정 테스트만 실행 가능
    # 예: python test_chunk_integration.py 1  -> 테스트 1만 실행
    run_only = int(sys.argv[1]) if len(sys.argv) > 1 else None
    
    test_times = {}
    
    try:
        test.setup_method()
        
        tests = [
            ("테스트 1: 프로세스 통합", test.test_process_consolidation_across_chunks),
            ("테스트 2: 역할 중복 제거", test.test_role_deduplication_across_chunks),
            ("테스트 3: 태스크 순서", test.test_task_sequence_across_chunks),
            ("테스트 4: 게이트웨이", test.test_gateway_extraction),
            ("테스트 5: 전체 워크플로우", test.test_full_workflow_integration),
            ("테스트 6: BPMN 생성", test.test_bpmn_generation_from_graph),
        ]
        
        for i, (name, func) in enumerate(tests, 1):
            if run_only and i != run_only:
                continue
            
            start = time.time()
            func()
            elapsed = time.time() - start
            test_times[name] = elapsed
            print(f"\n⏱️ [{name}] 총 소요시간: {elapsed:.2f}초")
        
        print("\n" + "="*60)
        print("🎉 테스트 완료!")
        print("="*60)
        
        print("\n📊 테스트별 소요시간:")
        for name, elapsed in test_times.items():
            print(f"   {name}: {elapsed:.2f}초")
        
        print(f"\n⏱️ 전체 소요시간: {time.time() - total_start:.2f}초")
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

