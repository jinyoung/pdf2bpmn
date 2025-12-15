"""LangGraph workflow definition for PDF to BPMN conversion."""
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..models.state import GraphState
from ..models.entities import (
    Process, Task, Role, Gateway, Event, 
    Skill, DMNDecision, DMNRule, Evidence, Ambiguity,
    AmbiguityStatus, TaskType, generate_id
)
from ..extractors.pdf_extractor import PDFExtractor
from ..extractors.entity_extractor import EntityExtractor
from ..graph.neo4j_client import Neo4jClient
from ..graph.vector_search import VectorSearch
from ..generators.bpmn_generator import BPMNGenerator
from ..generators.dmn_generator import DMNGenerator
from ..generators.skill_generator import SkillGenerator
from ..config import Config


class PDF2BPMNWorkflow:
    """Orchestrates the PDF to BPMN conversion workflow."""
    
    def __init__(self):
        self.pdf_extractor = PDFExtractor()
        self.entity_extractor = EntityExtractor()
        self.neo4j = Neo4jClient()
        self.vector_search = VectorSearch(self.neo4j)
        self.bpmn_generator = BPMNGenerator()
        self.dmn_generator = DMNGenerator()
        self.skill_generator = SkillGenerator()
        
        # Accumulated relationship maps
        self.task_role_map = {}  # task_id -> role_id
        self.task_process_map = {}  # task_id -> process_id
        self.role_decision_map = {}  # role_id -> [decision_ids]
        self.entity_chunk_map = {}  # entity_id -> chunk_id
        self.role_skill_map = {}  # role_id -> [skill_ids]
        self.sequence_flows = []  # list of {from_task_id, to_task_id, condition}
        
        # Name -> ID mappings for lookup
        self.process_name_to_id = {}
        self.role_name_to_id = {}
        self.task_name_to_id = {}
    
    def ingest_pdf(self, state: GraphState) -> GraphState:
        """Node: Ingest PDF and extract document structure."""
        print("📄 Ingesting PDF documents...")
        
        documents = []
        sections = []
        chunks = []
        
        for pdf_path in state.get("pdf_paths", []):
            doc, doc_sections, doc_chunks = self.pdf_extractor.extract_document(pdf_path)
            documents.append(doc)
            sections.extend(doc_sections)
            chunks.extend(doc_chunks)
            
            # Store in Neo4j
            self.neo4j.create_document(doc)
            for section in doc_sections:
                self.neo4j.create_section(section)
        
        return {
            "documents": documents,
            "sections": sections,
            "reference_chunks": chunks,
            "current_step": "segment_sections"
        }
    
    def segment_sections(self, state: GraphState) -> GraphState:
        """Node: Process and embed sections."""
        print("📑 Segmenting and embedding sections...")
        
        chunks = state.get("reference_chunks", [])
        documents = state.get("documents", [])
        doc_id = documents[0].doc_id if documents else ""
        
        # Batch embed chunks (in smaller batches to avoid rate limits)
        batch_size = 50
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            self.vector_search.batch_embed_chunks(batch)
            
            # Store in Neo4j and link to document
            for chunk in batch:
                self.neo4j.create_chunk(chunk)
                if doc_id:
                    self.neo4j.link_chunk_to_document(chunk.chunk_id, doc_id)
        
        return {
            "reference_chunks": chunks,
            "current_step": "extract_candidates"
        }
    
    def extract_candidates(self, state: GraphState) -> GraphState:
        """Node: Extract process/task/role candidates from sections."""
        print("🔍 Extracting candidate entities...")
        
        all_processes = []
        all_tasks = []
        all_roles = []
        all_gateways = []
        all_events = []
        all_decisions = []
        all_rules = []
        
        sections = state.get("sections", [])
        documents = state.get("documents", [])
        chunks = state.get("reference_chunks", [])
        doc_id = documents[0].doc_id if documents else ""
        
        # Create chunk index for linking
        chunk_by_page = {}
        for chunk in chunks:
            if chunk.page not in chunk_by_page:
                chunk_by_page[chunk.page] = []
            chunk_by_page[chunk.page].append(chunk)
        
        for section in sections:
            if not section.content or len(section.content.strip()) < 50:
                continue
            
            # Find relevant chunk for this section (for evidence linking)
            section_chunk_id = ""
            if section.page_from in chunk_by_page and chunk_by_page[section.page_from]:
                section_chunk_id = chunk_by_page[section.page_from][0].chunk_id
            
            # Extract entities from section content
            extracted = self.entity_extractor.extract_from_text(section.content)
            
            # Convert to entity objects with relationships
            entities = self.entity_extractor.convert_to_entities(
                extracted, 
                doc_id,
                chunk_id=section_chunk_id,
                existing_processes=self.process_name_to_id,
                existing_roles=self.role_name_to_id
            )
            
            # Collect entities
            all_processes.extend(entities["processes"])
            all_tasks.extend(entities["tasks"])
            all_roles.extend(entities["roles"])
            all_gateways.extend(entities["gateways"])
            all_events.extend(entities["events"])
            all_decisions.extend(entities["decisions"])
            all_rules.extend(entities["rules"])
            
            # Accumulate relationship mappings
            self.task_role_map.update(entities.get("task_role_map", {}))
            self.task_process_map.update(entities.get("task_process_map", {}))
            self.entity_chunk_map.update(entities.get("entity_chunk_map", {}))
            
            # Accumulate sequence flows
            self.sequence_flows.extend(entities.get("sequence_flows", []))
            
            for role_id, decision_ids in entities.get("role_decision_map", {}).items():
                if role_id not in self.role_decision_map:
                    self.role_decision_map[role_id] = []
                self.role_decision_map[role_id].extend(decision_ids)
            
            # Update name -> ID mappings
            for proc in entities["processes"]:
                self.process_name_to_id[proc.name.lower()] = proc.proc_id
            for role in entities["roles"]:
                self.role_name_to_id[role.name.lower()] = role.role_id
            for task in entities["tasks"]:
                self.task_name_to_id[task.name.lower()] = task.task_id
        
        return {
            "processes": all_processes,
            "tasks": all_tasks,
            "roles": all_roles,
            "gateways": all_gateways,
            "events": all_events,
            "dmn_decisions": all_decisions,
            "dmn_rules": all_rules,
            "current_step": "normalize_entities"
        }
    
    def normalize_entities(self, state: GraphState) -> GraphState:
        """Node: Normalize and deduplicate entities using vector search."""
        print("🔄 Normalizing and deduplicating entities...")
        
        processes = state.get("processes", [])
        tasks = state.get("tasks", [])
        roles = state.get("roles", [])
        gateways = state.get("gateways", [])
        events = state.get("events", [])
        decisions = state.get("dmn_decisions", [])
        
        # Deduplicate processes
        unique_processes = self._deduplicate_entities(processes, "Process")
        
        # Deduplicate tasks
        unique_tasks = self._deduplicate_entities(tasks, "Task")
        
        # Deduplicate roles
        unique_roles = self._deduplicate_entities(roles, "Role")
        
        # Deduplicate decisions
        unique_decisions = self._deduplicate_entities(decisions, "Decision")
        
        print(f"   Processes: {len(processes)} → {len(unique_processes)}")
        print(f"   Tasks: {len(tasks)} → {len(unique_tasks)}")
        print(f"   Roles: {len(roles)} → {len(unique_roles)}")
        print(f"   Decisions: {len(decisions)} → {len(unique_decisions)}")
        
        # Store in Neo4j
        for proc in unique_processes:
            self.neo4j.create_process(proc)
        
        for task in unique_tasks:
            self.neo4j.create_task(task)
        
        for role in unique_roles:
            self.neo4j.create_role(role)
        
        for gateway in gateways:
            self.neo4j.create_gateway(gateway)
        
        for event in events:
            self.neo4j.create_event(event)
        
        for decision in unique_decisions:
            self.neo4j.create_decision(decision)
        
        for rule in state.get("dmn_rules", []):
            self.neo4j.create_rule(rule)
        
        # Create relationships in batch
        print("🔗 Creating entity relationships...")
        self.neo4j.create_all_relationships(
            task_role_map=self.task_role_map,
            task_process_map=self.task_process_map,
            role_decision_map=self.role_decision_map,
            entity_chunk_map=self.entity_chunk_map
        )
        
        # Create sequence flows (NEXT relationships between tasks)
        print("➡️ Creating sequence flows...")
        self._create_sequence_flows(unique_tasks, unique_processes)
        
        # Infer missing Task-Role relationships based on name matching
        self._infer_task_role_relationships(unique_tasks, unique_roles)
        
        # Infer missing Task-Process relationships 
        self._infer_task_process_relationships(unique_tasks, unique_processes)
        
        return {
            "processes": unique_processes,
            "tasks": unique_tasks,
            "roles": unique_roles,
            "dmn_decisions": unique_decisions,
            "current_step": "detect_ambiguities"
        }
    
    def _create_sequence_flows(self, tasks: list, processes: list):
        """Create NEXT relationships between tasks based on extracted and inferred sequence flows."""
        created_flows = set()
        
        # First, create explicit sequence flows from extraction
        for flow in self.sequence_flows:
            from_id = flow.get("from_task_id")
            to_id = flow.get("to_task_id")
            condition = flow.get("condition", "")
            
            if from_id and to_id and (from_id, to_id) not in created_flows:
                self.neo4j.link_task_sequence(from_id, to_id, condition)
                created_flows.add((from_id, to_id))
        
        # Group tasks by process
        tasks_by_process = {}
        for task in tasks:
            proc_id = task.process_id or "default"
            if proc_id not in tasks_by_process:
                tasks_by_process[proc_id] = []
            tasks_by_process[proc_id].append(task)
        
        # Create sequence flows for each process based on task order
        for proc_id, proc_tasks in tasks_by_process.items():
            sorted_tasks = sorted(proc_tasks, key=lambda t: t.order)
            
            for i in range(len(sorted_tasks) - 1):
                from_task = sorted_tasks[i]
                to_task = sorted_tasks[i + 1]
                
                if (from_task.task_id, to_task.task_id) not in created_flows:
                    self.neo4j.link_task_sequence(from_task.task_id, to_task.task_id)
                    created_flows.add((from_task.task_id, to_task.task_id))
        
        # Also use Neo4j to create sequences for each process
        for proc in processes:
            self.neo4j.create_task_sequence_for_process(proc.proc_id)
        
        print(f"   Created {len(created_flows)} sequence flows (NEXT relationships)")
    
    def _infer_task_role_relationships(self, tasks: list, roles: list):
        """Infer Task-Role relationships based on task descriptions."""
        role_keywords = {}
        for role in roles:
            keywords = [role.name.lower()]
            if role.org_unit:
                keywords.append(role.org_unit.lower())
            role_keywords[role.role_id] = keywords
        
        for task in tasks:
            if task.task_id in self.task_role_map:
                continue  # Already has a role
            
            task_text = (task.name + " " + task.description).lower()
            
            for role_id, keywords in role_keywords.items():
                for keyword in keywords:
                    if keyword in task_text and len(keyword) > 2:
                        self.neo4j.link_task_to_role(task.task_id, role_id)
                        self.task_role_map[task.task_id] = role_id
                        break
                if task.task_id in self.task_role_map:
                    break
    
    def _infer_task_process_relationships(self, tasks: list, processes: list):
        """Ensure all tasks are linked to a process."""
        if not processes:
            return
        
        default_process_id = processes[0].proc_id
        
        for task in tasks:
            if not task.process_id:
                task.process_id = default_process_id
                self.neo4j.link_task_to_role  # Link via HAS_TASK
                with self.neo4j.session() as session:
                    session.run("""
                        MATCH (p:Process {proc_id: $proc_id})
                        MATCH (t:Task {task_id: $task_id})
                        MERGE (p)-[:HAS_TASK]->(t)
                    """, {"proc_id": default_process_id, "task_id": task.task_id})
    
    def _deduplicate_entities(self, entities: list, entity_type: str) -> list:
        """Deduplicate entities based on name similarity."""
        seen_names = {}
        unique = []
        
        for entity in entities:
            name = entity.name.lower().strip()
            
            if name in seen_names:
                continue
            
            # Check for similar existing entities
            try:
                match, score, action = self.vector_search.find_similar_entity(
                    entity_type, entity.name, getattr(entity, 'description', '')
                )
                
                if action == "merge" and match:
                    continue
            except:
                pass
            
            seen_names[name] = entity
            unique.append(entity)
        
        return unique
    
    def detect_ambiguities(self, state: GraphState) -> GraphState:
        """Node: Detect ambiguities that need human resolution."""
        print("❓ Detecting ambiguities...")
        
        questions = []
        
        tasks = state.get("tasks", [])
        roles = state.get("roles", [])
        processes = state.get("processes", [])
        gateways = state.get("gateways", [])
        
        # Count tasks without roles
        tasks_without_roles = [t for t in tasks if t.task_id not in self.task_role_map]
        
        if tasks_without_roles and roles:
            # Create batch question for role assignment
            role_names = [r.name for r in roles]
            for task in tasks_without_roles[:10]:  # Limit to 10 questions
                questions.append(Ambiguity(
                    amb_id=generate_id(),
                    entity_type="Task",
                    entity_id=task.task_id,
                    question=f"'{task.name}' 태스크의 담당 역할은 누구인가요?",
                    options=role_names + ["새 역할 추가", "미정"],
                    status=AmbiguityStatus.OPEN
                ))
        
        # Store ambiguities in Neo4j
        for q in questions:
            self.neo4j.create_ambiguity(q)
        
        print(f"   {len(questions)} questions generated")
        print(f"   Tasks without roles: {len(tasks_without_roles)}")
        
        return {
            "open_questions": questions,
            "current_step": "ask_user" if questions else "generate_skills"
        }
    
    def ask_user(self, state: GraphState) -> GraphState:
        """Node: Wait for user input on ambiguities (HITL interrupt point)."""
        print("🙋 Waiting for user input...")
        
        questions = state.get("open_questions", [])
        open_questions = [q for q in questions if q.status == AmbiguityStatus.OPEN]
        
        if open_questions:
            current = open_questions[0]
            return {
                "current_question": current,
                "current_step": "waiting_for_user"
            }
        
        return {
            "current_question": None,
            "current_step": "generate_skills"
        }
    
    def apply_user_answer(self, state: GraphState) -> GraphState:
        """Node: Apply user's answer to resolve ambiguity."""
        print("✅ Applying user answer...")
        
        current_question = state.get("current_question")
        user_answer = state.get("user_answer")
        
        if current_question and user_answer:
            current_question.status = AmbiguityStatus.RESOLVED
            current_question.answer = user_answer
            
            self.neo4j.resolve_ambiguity(current_question.amb_id, user_answer)
            
            # Apply answer - link task to selected role
            if current_question.entity_type == "Task":
                role_name = user_answer.lower()
                if role_name in self.role_name_to_id:
                    role_id = self.role_name_to_id[role_name]
                    self.neo4j.link_task_to_role(current_question.entity_id, role_id)
                    self.task_role_map[current_question.entity_id] = role_id
            
            resolved = state.get("resolved_questions", [])
            resolved.append(current_question)
            
            open_questions = [
                q for q in state.get("open_questions", [])
                if q.amb_id != current_question.amb_id
            ]
            
            return {
                "resolved_questions": resolved,
                "open_questions": open_questions,
                "current_question": None,
                "user_answer": None,
                "current_step": "detect_ambiguities"
            }
        
        return {"current_step": "generate_skills"}
    
    def generate_skills(self, state: GraphState) -> GraphState:
        """Node: Generate skill documents for agent tasks."""
        print("📝 Generating skill documents...")
        
        tasks = state.get("tasks", [])
        roles = state.get("roles", [])
        skills = []
        skill_docs = {}
        
        for task in tasks:
            if task.task_type == TaskType.AGENT:
                skill, markdown = self.skill_generator.generate_from_task(task)
                
                safe_name = "".join(
                    c if c.isalnum() or c in "._-" else "_" 
                    for c in task.name
                )
                filename = f"{safe_name}.skill.md"
                filepath = Config.OUTPUT_DIR / filename
                
                self.skill_generator.save(markdown, str(filepath))
                skill.md_path = str(filepath)
                skill_docs[task.task_id] = markdown
                
                self.neo4j.create_skill(skill)
                self.neo4j.link_task_to_skill(task.task_id, skill.skill_id)
                
                # Link skill to role if task has a role
                if task.task_id in self.task_role_map:
                    role_id = self.task_role_map[task.task_id]
                    self.neo4j.link_role_to_skill(role_id, skill.skill_id)
                    
                    if role_id not in self.role_skill_map:
                        self.role_skill_map[role_id] = []
                    self.role_skill_map[role_id].append(skill.skill_id)
                
                skills.append(skill)
        
        print(f"   Generated {len(skills)} skill documents")
        
        return {
            "skills": skills,
            "skill_docs": skill_docs,
            "current_step": "generate_dmn"
        }
    
    def generate_dmn(self, state: GraphState) -> GraphState:
        """Node: Generate DMN decision tables."""
        print("📊 Generating DMN decision tables...")
        
        decisions = state.get("dmn_decisions", [])
        rules = state.get("dmn_rules", [])
        
        if decisions:
            dmn_xml = self.dmn_generator.generate(decisions, rules)
            
            dmn_path = Config.OUTPUT_DIR / "decisions.dmn"
            self.dmn_generator.save(dmn_xml, str(dmn_path))
            
            dmn_json = self.dmn_generator.generate_json(decisions, rules)
            json_path = Config.OUTPUT_DIR / "decisions.json"
            self.dmn_generator.save(dmn_json, str(json_path))
            
            # Link decisions to roles that make them
            for role_id, decision_ids in self.role_decision_map.items():
                for decision_id in decision_ids:
                    self.neo4j.link_role_to_decision(role_id, decision_id)
            
            print(f"   Generated {len(decisions)} decision tables")
            
            return {
                "dmn_xml": dmn_xml,
                "current_step": "assemble_bpmn"
            }
        
        return {
            "dmn_xml": None,
            "current_step": "assemble_bpmn"
        }
    
    def assemble_bpmn(self, state: GraphState) -> GraphState:
        """Node: Assemble final BPMN XML."""
        print("🔧 Assembling BPMN XML...")
        
        processes = state.get("processes", [])
        tasks = state.get("tasks", [])
        roles = state.get("roles", [])
        gateways = state.get("gateways", [])
        events = state.get("events", [])
        
        if not processes:
            processes = [Process(
                name="Extracted Process",
                purpose="Automatically extracted from document",
                description="Process extracted from PDF document"
            )]
        
        main_process = processes[0]
        process_tasks = [t for t in tasks if t.process_id == main_process.proc_id or not t.process_id]
        
        for task in process_tasks:
            task.process_id = main_process.proc_id
        
        bpmn_xml = self.bpmn_generator.generate(
            process=main_process,
            tasks=process_tasks,
            roles=roles,
            gateways=gateways,
            events=events,
            task_role_map=self.task_role_map
        )
        
        bpmn_path = Config.OUTPUT_DIR / "process.bpmn"
        self.bpmn_generator.save(bpmn_xml, str(bpmn_path))
        
        return {
            "bpmn_xml": bpmn_xml,
            "current_step": "validate_consistency"
        }
    
    def validate_consistency(self, state: GraphState) -> GraphState:
        """Node: Validate consistency of generated artifacts."""
        print("✔️ Validating consistency...")
        
        errors = []
        tasks = state.get("tasks", [])
        roles = state.get("roles", [])
        
        task_role_coverage = len(self.task_role_map)
        if tasks and task_role_coverage < len(tasks) * 0.3:
            errors.append(f"경고: {len(tasks) - task_role_coverage}개 태스크에 역할이 지정되지 않았습니다.")
        
        if len(roles) == 0 and len(tasks) > 0:
            errors.append("역할(Role)이 추출되지 않았습니다.")
        
        if errors:
            for err in errors:
                print(f"   ⚠️ {err}")
            return {
                "error": "; ".join(errors),
                "current_step": "export_artifacts"
            }
        
        print("   ✅ All validations passed")
        return {
            "error": None,
            "current_step": "export_artifacts"
        }
    
    def export_artifacts(self, state: GraphState) -> GraphState:
        """Node: Export final artifacts."""
        print("📦 Exporting artifacts...")
        
        # Print relationship statistics
        print(f"\n📊 Relationship Statistics:")
        print(f"   - Task → Task (NEXT/Sequence): {len(self.sequence_flows)}")
        print(f"   - Task → Role (PERFORMED_BY): {len(self.task_role_map)}")
        print(f"   - Task → Process (HAS_TASK): {len(self.task_process_map)}")
        print(f"   - Role → Decision (MAKES_DECISION): {sum(len(v) for v in self.role_decision_map.values())}")
        print(f"   - Entity → Document (SUPPORTED_BY): {len(self.entity_chunk_map)}")
        print(f"   - Role → Skill (HAS_SKILL): {sum(len(v) for v in self.role_skill_map.values())}")
        
        output_summary = {
            "bpmn_path": str(Config.OUTPUT_DIR / "process.bpmn"),
            "dmn_path": str(Config.OUTPUT_DIR / "decisions.dmn") if state.get("dmn_xml") else None,
            "skill_count": len(state.get("skills", [])),
            "process_count": len(state.get("processes", [])),
            "task_count": len(state.get("tasks", [])),
            "role_count": len(state.get("roles", []))
        }
        
        print(f"\n✅ Export complete!")
        print(f"   - BPMN: {output_summary['bpmn_path']}")
        if output_summary['dmn_path']:
            print(f"   - DMN: {output_summary['dmn_path']}")
        print(f"   - Skills: {output_summary['skill_count']} documents")
        print(f"   - Processes: {output_summary['process_count']}")
        print(f"   - Tasks: {output_summary['task_count']}")
        print(f"   - Roles: {output_summary['role_count']}")
        
        return {
            "current_step": "completed"
        }


def should_ask_user(state: GraphState) -> Literal["ask_user", "generate_skills"]:
    """Routing function: determine if we need user input."""
    open_questions = state.get("open_questions", [])
    unresolved = [q for q in open_questions if q.status == AmbiguityStatus.OPEN]
    
    if unresolved:
        return "ask_user"
    return "generate_skills"


def has_more_questions(state: GraphState) -> Literal["ask_user", "generate_skills"]:
    """Check if there are more questions to ask."""
    open_questions = state.get("open_questions", [])
    unresolved = [q for q in open_questions if q.status == AmbiguityStatus.OPEN]
    
    if unresolved:
        return "ask_user"
    return "generate_skills"


def create_workflow() -> StateGraph:
    """Create the LangGraph workflow."""
    
    workflow_handler = PDF2BPMNWorkflow()
    
    workflow = StateGraph(GraphState)
    
    workflow.add_node("ingest_pdf", workflow_handler.ingest_pdf)
    workflow.add_node("segment_sections", workflow_handler.segment_sections)
    workflow.add_node("extract_candidates", workflow_handler.extract_candidates)
    workflow.add_node("normalize_entities", workflow_handler.normalize_entities)
    workflow.add_node("detect_ambiguities", workflow_handler.detect_ambiguities)
    workflow.add_node("ask_user", workflow_handler.ask_user)
    workflow.add_node("apply_user_answer", workflow_handler.apply_user_answer)
    workflow.add_node("generate_skills", workflow_handler.generate_skills)
    workflow.add_node("generate_dmn", workflow_handler.generate_dmn)
    workflow.add_node("assemble_bpmn", workflow_handler.assemble_bpmn)
    workflow.add_node("validate_consistency", workflow_handler.validate_consistency)
    workflow.add_node("export_artifacts", workflow_handler.export_artifacts)
    
    workflow.set_entry_point("ingest_pdf")
    
    workflow.add_edge("ingest_pdf", "segment_sections")
    workflow.add_edge("segment_sections", "extract_candidates")
    workflow.add_edge("extract_candidates", "normalize_entities")
    workflow.add_edge("normalize_entities", "detect_ambiguities")
    
    workflow.add_conditional_edges(
        "detect_ambiguities",
        should_ask_user,
        {
            "ask_user": "ask_user",
            "generate_skills": "generate_skills"
        }
    )
    
    workflow.add_edge("ask_user", "apply_user_answer")
    
    workflow.add_conditional_edges(
        "apply_user_answer",
        has_more_questions,
        {
            "ask_user": "ask_user",
            "generate_skills": "generate_skills"
        }
    )
    
    workflow.add_edge("generate_skills", "generate_dmn")
    workflow.add_edge("generate_dmn", "assemble_bpmn")
    workflow.add_edge("assemble_bpmn", "validate_consistency")
    workflow.add_edge("validate_consistency", "export_artifacts")
    workflow.add_edge("export_artifacts", END)
    
    return workflow


def compile_workflow_with_checkpointer():
    """Compile workflow with memory checkpointer for HITL support."""
    workflow = create_workflow()
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)
