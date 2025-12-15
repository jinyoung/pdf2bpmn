"""
테스트: Neo4j 그래프에서 BPMN XML 생성

이 테스트는 Neo4j에 저장된 프로세스/태스크/역할 데이터를 조회하여
BPMN XML을 생성하는 기능을 검증합니다.

사전 조건: Neo4j에 프로세스 데이터가 저장되어 있어야 함
"""

import sys
import time
from pathlib import Path
from contextlib import contextmanager

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pdf2bpmn.graph.neo4j_client import Neo4jClient
from pdf2bpmn.generators.bpmn_generator import BPMNGenerator
from pdf2bpmn.models.entities import (
    Process, Task, Role, Gateway, Event, 
    TaskType, GatewayType, EventType
)


@contextmanager
def timer(name: str):
    """시간 측정 컨텍스트 매니저"""
    start = time.time()
    yield
    elapsed = time.time() - start
    print(f"   ⏱️ [{name}] {elapsed:.2f}초")


class TestBPMNGeneration:
    """Neo4j 그래프 기반 BPMN 생성 테스트"""
    
    def __init__(self):
        self.neo4j = None
    
    def setup(self):
        """Neo4j 연결"""
        print("🔧 Neo4j 연결 중...")
        with timer("Neo4j 연결"):
            self.neo4j = Neo4jClient()
    
    def teardown(self):
        """리소스 정리"""
        if self.neo4j:
            self.neo4j.close()
    
    def get_all_processes(self) -> list[Process]:
        """Neo4j에서 모든 프로세스 조회"""
        query = """
        MATCH (p:Process)
        RETURN p.proc_id as proc_id, 
               p.name as name, 
               p.description as description,
               p.purpose as purpose,
               p.doc_id as doc_id
        """
        processes = []
        with self.neo4j.session() as session:
            result = session.run(query)
            for record in result:
                proc = Process(
                    proc_id=record["proc_id"],
                    name=record["name"] or "Unknown Process",
                    description=record["description"] or "",
                    purpose=record["purpose"] or "",
                    doc_id=record["doc_id"] or ""
                )
                processes.append(proc)
        return processes
    
    def get_tasks_by_process(self, process_id: str) -> list[Task]:
        """프로세스에 속한 태스크 조회"""
        query = """
        MATCH (p:Process {proc_id: $process_id})-[:HAS_TASK]->(t:Task)
        RETURN t.task_id as task_id,
               t.name as name,
               t.description as description,
               t.task_type as task_type,
               t.order as order_num,
               t.process_id as process_id
        ORDER BY t.order
        """
        tasks = []
        with self.neo4j.session() as session:
            result = session.run(query, {"process_id": process_id})
            for record in result:
                task_type_str = record["task_type"] or "human"
                try:
                    task_type = TaskType(task_type_str)
                except ValueError:
                    task_type = TaskType.HUMAN
                
                task = Task(
                    task_id=record["task_id"],
                    name=record["name"] or "Unknown Task",
                    description=record["description"] or "",
                    task_type=task_type,
                    order=record["order_num"] or 0,
                    process_id=record["process_id"] or process_id
                )
                tasks.append(task)
        return tasks
    
    def get_roles(self) -> list[Role]:
        """모든 역할 조회"""
        query = """
        MATCH (r:Role)
        RETURN r.role_id as role_id,
               r.name as name,
               r.description as description,
               r.org_unit as org_unit
        """
        roles = []
        with self.neo4j.session() as session:
            result = session.run(query)
            for record in result:
                role = Role(
                    role_id=record["role_id"],
                    name=record["name"] or "Unknown Role",
                    description=record["description"] or "",
                    org_unit=record["org_unit"] or ""
                )
                roles.append(role)
        return roles
    
    def get_task_role_map(self, process_id: str) -> dict[str, str]:
        """태스크-역할 매핑 조회"""
        query = """
        MATCH (p:Process {proc_id: $process_id})-[:HAS_TASK]->(t:Task)-[:PERFORMED_BY]->(r:Role)
        RETURN t.task_id as task_id, r.role_id as role_id
        """
        mapping = {}
        with self.neo4j.session() as session:
            result = session.run(query, {"process_id": process_id})
            for record in result:
                mapping[record["task_id"]] = record["role_id"]
        return mapping
    
    def get_gateways_by_process(self, process_id: str) -> list[Gateway]:
        """프로세스에 속한 게이트웨이 조회"""
        query = """
        MATCH (p:Process {proc_id: $process_id})-[:HAS_GATEWAY]->(g:Gateway)
        RETURN g.gateway_id as gateway_id,
               g.gateway_type as gateway_type,
               g.condition as condition,
               g.description as description,
               g.process_id as process_id
        """
        gateways = []
        with self.neo4j.session() as session:
            result = session.run(query, {"process_id": process_id})
            for record in result:
                gw_type_str = record["gateway_type"] or "exclusive"
                try:
                    gw_type = GatewayType(gw_type_str)
                except ValueError:
                    gw_type = GatewayType.EXCLUSIVE
                
                gateway = Gateway(
                    gateway_id=record["gateway_id"],
                    gateway_type=gw_type,
                    condition=record["condition"] or "",
                    description=record["description"] or "",
                    process_id=record["process_id"] or process_id
                )
                gateways.append(gateway)
        return gateways
    
    def get_sequence_flows(self, process_id: str) -> list[dict]:
        """NEXT 관계 (시퀀스 플로우) 조회"""
        query = """
        MATCH (p:Process {proc_id: $process_id})-[:HAS_TASK]->(t1:Task)-[r:NEXT]->(t2:Task)
        RETURN t1.task_id as from_task, 
               t2.task_id as to_task, 
               t1.name as from_name,
               t2.name as to_name,
               r.condition as condition
        ORDER BY t1.order
        """
        flows = []
        with self.neo4j.session() as session:
            result = session.run(query, {"process_id": process_id})
            for record in result:
                flows.append({
                    "from_task_id": record["from_task"],
                    "to_task_id": record["to_task"],
                    "from_name": record["from_name"],
                    "to_name": record["to_name"],
                    "condition": record["condition"]
                })
        return flows
    
    def test_generate_bpmn_from_neo4j(self):
        """
        테스트: Neo4j 그래프에서 BPMN XML 생성
        """
        print("\n" + "="*60)
        print("🔧 Neo4j 그래프 → BPMN 생성 테스트")
        print("="*60)
        
        test_start = time.time()
        
        # 1. 프로세스 조회
        print("\n📊 Neo4j 데이터 조회 중...")
        
        with timer("프로세스 조회"):
            processes = self.get_all_processes()
        
        if not processes:
            print("❌ Neo4j에 프로세스가 없습니다. 먼저 테스트 5를 실행하세요.")
            return None
        
        print(f"   발견된 프로세스: {len(processes)}개")
        for proc in processes:
            print(f"     - {proc.name} ({proc.proc_id[:8]}...)")
        
        # 메인 프로세스 선택
        main_process = processes[0]
        print(f"\n   🎯 대상 프로세스: {main_process.name}")
        
        # 2. 관련 데이터 조회
        with timer("태스크 조회"):
            tasks = self.get_tasks_by_process(main_process.proc_id)
        print(f"   태스크: {len(tasks)}개")
        
        with timer("역할 조회"):
            roles = self.get_roles()
        print(f"   역할: {len(roles)}개")
        
        with timer("태스크-역할 매핑 조회"):
            task_role_map = self.get_task_role_map(main_process.proc_id)
        print(f"   태스크-역할 매핑: {len(task_role_map)}개")
        
        with timer("게이트웨이 조회"):
            gateways = self.get_gateways_by_process(main_process.proc_id)
        print(f"   게이트웨이: {len(gateways)}개")
        
        with timer("시퀀스 플로우 조회"):
            sequence_flows = self.get_sequence_flows(main_process.proc_id)
        print(f"   시퀀스 플로우 (NEXT 관계): {len(sequence_flows)}개")
        
        # 시퀀스 플로우 미리보기
        if sequence_flows:
            print("\n   📋 시퀀스 플로우 샘플:")
            for flow in sequence_flows[:10]:
                cond = f" [{flow['condition']}]" if flow['condition'] else ""
                print(f"      {flow['from_name']} → {flow['to_name']}{cond}")
            if len(sequence_flows) > 10:
                print(f"      ... 외 {len(sequence_flows) - 10}개")
        
        # 3. BPMN 생성
        print("\n🔧 BPMN XML 생성 중...")
        
        with timer("BPMN 생성"):
            generator = BPMNGenerator()
            bpmn_xml = generator.generate(
                process=main_process,
                tasks=tasks,
                roles=roles,
                gateways=gateways,
                events=[],  # 이벤트는 아직 없음
                task_role_map=task_role_map
            )
        
        # 4. 검증
        print("\n📄 생성된 BPMN XML 검증:")
        
        # 기본 구조 검증
        has_xml_decl = '<?xml version="1.0"' in bpmn_xml
        has_definitions = '<bpmn:definitions' in bpmn_xml
        has_process = '<bpmn:process' in bpmn_xml
        has_diagram = '<bpmndi:BPMNDiagram' in bpmn_xml
        
        print(f"   ✅ XML 선언: {'있음' if has_xml_decl else '없음'}")
        print(f"   ✅ BPMN definitions: {'있음' if has_definitions else '없음'}")
        print(f"   ✅ BPMN process: {'있음' if has_process else '없음'}")
        print(f"   ✅ BPMN diagram: {'있음' if has_diagram else '없음'}")
        
        # 요소 개수 확인
        task_count = bpmn_xml.count('<bpmn:userTask') + bpmn_xml.count('<bpmn:serviceTask') + bpmn_xml.count('<bpmn:task ')
        flow_count = bpmn_xml.count('<bpmn:sequenceFlow')
        lane_count = bpmn_xml.count('<bpmn:lane')
        gateway_count = bpmn_xml.count('Gateway')
        
        print(f"\n   XML 내 요소:")
        print(f"     - 태스크: {task_count}개")
        print(f"     - 시퀀스 플로우: {flow_count}개")
        print(f"     - 레인 (역할): {lane_count}개")
        print(f"     - 게이트웨이: {gateway_count}개")
        
        # 5. 파일 저장
        output_dir = Path(__file__).parent / "output"
        output_dir.mkdir(exist_ok=True)
        
        # 프로세스 이름으로 파일명 생성
        safe_name = main_process.name.replace(" ", "_").replace("/", "_")[:30]
        output_file = output_dir / f"{safe_name}.bpmn"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(bpmn_xml)
        
        print(f"\n💾 BPMN 파일 저장: {output_file}")
        print(f"   파일 크기: {len(bpmn_xml):,} bytes")
        print(f"   라인 수: {len(bpmn_xml.splitlines())} lines")
        
        # XML 미리보기
        print("\n📝 BPMN XML 미리보기 (처음 40줄):")
        xml_lines = bpmn_xml.split('\n')[:40]
        for i, line in enumerate(xml_lines, 1):
            print(f"   {i:3d}| {line[:100]}")
        
        if len(bpmn_xml.split('\n')) > 40:
            print(f"   ... (총 {len(bpmn_xml.splitlines())} 줄)")
        
        # 검증
        assert has_xml_decl, "XML 선언이 없음"
        assert has_definitions, "BPMN definitions가 없음"
        assert has_process, "BPMN process가 없음"
        assert task_count >= 1, "태스크가 없음"
        
        print(f"\n⏱️ [총 소요시간] {time.time() - test_start:.2f}초")
        print("\n✅ BPMN 생성 테스트 완료!")
        
        return bpmn_xml
    
    def test_list_all_data(self):
        """
        Neo4j에 저장된 모든 데이터 확인
        """
        print("\n" + "="*60)
        print("📊 Neo4j 데이터 현황")
        print("="*60)
        
        with self.neo4j.session() as session:
            # 노드 개수
            result = session.run("MATCH (p:Process) RETURN count(p) as count")
            process_count = result.single()["count"]
            
            result = session.run("MATCH (t:Task) RETURN count(t) as count")
            task_count = result.single()["count"]
            
            result = session.run("MATCH (r:Role) RETURN count(r) as count")
            role_count = result.single()["count"]
            
            result = session.run("MATCH (g:Gateway) RETURN count(g) as count")
            gateway_count = result.single()["count"]
            
            # 관계 개수
            result = session.run("MATCH ()-[r:HAS_TASK]->() RETURN count(r) as count")
            has_task_count = result.single()["count"]
            
            result = session.run("MATCH ()-[r:PERFORMED_BY]->() RETURN count(r) as count")
            performed_by_count = result.single()["count"]
            
            result = session.run("MATCH ()-[r:NEXT]->() RETURN count(r) as count")
            next_count = result.single()["count"]
        
        print(f"\n📦 노드:")
        print(f"   Process: {process_count}개")
        print(f"   Task: {task_count}개")
        print(f"   Role: {role_count}개")
        print(f"   Gateway: {gateway_count}개")
        
        print(f"\n🔗 관계:")
        print(f"   HAS_TASK: {has_task_count}개")
        print(f"   PERFORMED_BY: {performed_by_count}개")
        print(f"   NEXT (시퀀스 플로우): {next_count}개")
        
        if process_count == 0:
            print("\n⚠️ Neo4j에 데이터가 없습니다.")
            print("   먼저 test_chunk_integration.py 테스트 5를 실행하세요:")
            print("   $ uv run python tests/test_chunk_integration.py 5")
        
        return {
            "processes": process_count,
            "tasks": task_count,
            "roles": role_count,
            "gateways": gateway_count,
            "next_relations": next_count
        }


if __name__ == "__main__":
    test = TestBPMNGeneration()
    
    try:
        test.setup()
        
        # 데이터 현황 확인
        data_status = test.test_list_all_data()
        
        if data_status["processes"] > 0:
            # BPMN 생성
            test.test_generate_bpmn_from_neo4j()
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
    finally:
        test.teardown()

