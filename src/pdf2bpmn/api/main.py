"""FastAPI backend for PDF2BPMN frontend."""
import asyncio
import json
import os
from pathlib import Path
from typing import Optional
from datetime import datetime
import uuid

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..config import Config
from ..graph.neo4j_client import Neo4jClient
from ..workflow.graph import PDF2BPMNWorkflow

app = FastAPI(
    title="PDF2BPMN API",
    description="PDF to BPMN Converter API",
    version="0.1.0"
)

# CORS for Vue.js frontend - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Store for job progress
job_progress = {}


class JobStatus(BaseModel):
    job_id: str
    status: str  # pending, processing, completed, error
    current_step: str
    progress: int  # 0-100
    steps: list[dict]
    error: Optional[str] = None
    result: Optional[dict] = None


class EntityResponse(BaseModel):
    id: str
    name: str
    type: str
    description: Optional[str] = None
    evidence: Optional[dict] = None


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    neo4j = Neo4jClient()
    neo4j_ok = neo4j.verify_connection()
    neo4j.close()
    return {
        "status": "ok",
        "neo4j": "connected" if neo4j_ok else "disconnected"
    }


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a PDF file for processing."""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(400, "Only PDF files are allowed")
    
    # Save file
    Config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path = Config.UPLOAD_DIR / file.filename
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Create job ID
    job_id = str(uuid.uuid4())
    
    # Initialize job status
    job_progress[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "current_step": "uploaded",
        "progress": 0,
        "steps": [],
        "file_path": str(file_path),
        "file_name": file.filename
    }
    
    return {
        "job_id": job_id,
        "file_name": file.filename,
        "message": "File uploaded successfully"
    }


@app.post("/api/process/{job_id}")
async def start_processing(job_id: str, background_tasks: BackgroundTasks):
    """Start processing an uploaded file."""
    if job_id not in job_progress:
        raise HTTPException(404, "Job not found")
    
    job = job_progress[job_id]
    if job["status"] == "processing":
        raise HTTPException(400, "Job already processing")
    
    # Start background processing
    background_tasks.add_task(process_pdf_background, job_id)
    
    job["status"] = "processing"
    return {"message": "Processing started", "job_id": job_id}


async def process_pdf_background(job_id: str):
    """Background task for PDF processing."""
    job = job_progress[job_id]
    file_path = job["file_path"]
    
    steps = [
        {"name": "ingest_pdf", "label": "PDF 파싱", "status": "pending"},
        {"name": "segment_sections", "label": "섹션 분석 및 임베딩", "status": "pending"},
        {"name": "extract_candidates", "label": "엔티티 추출", "status": "pending"},
        {"name": "normalize_entities", "label": "정규화 및 중복 제거", "status": "pending"},
        {"name": "create_relationships", "label": "관계 생성", "status": "pending"},
        {"name": "generate_bpmn", "label": "BPMN 생성", "status": "pending"},
        {"name": "generate_dmn", "label": "DMN 생성", "status": "pending"},
        {"name": "export", "label": "결과 저장", "status": "pending"},
    ]
    job["steps"] = steps
    
    try:
        workflow = PDF2BPMNWorkflow()
        workflow.neo4j.init_schema()
        
        # Step 1: Ingest PDF
        update_step(job, 0, "processing", 10)
        state = {
            "pdf_paths": [file_path],
            "documents": [],
            "sections": [],
            "reference_chunks": [],
            "processes": [],
            "tasks": [],
            "roles": [],
            "gateways": [],
            "events": [],
            "skills": [],
            "dmn_decisions": [],
            "dmn_rules": [],
            "evidences": [],
            "open_questions": [],
            "resolved_questions": [],
            "current_question": None,
            "user_answer": None,
            "confidence_threshold": 0.8,
            "current_step": "ingest_pdf",
            "error": None,
            "bpmn_xml": None,
            "skill_docs": {},
            "dmn_xml": None
        }
        result = workflow.ingest_pdf(state)
        state.update(result)
        update_step(job, 0, "completed", 15)
        
        # Step 2: Segment sections
        update_step(job, 1, "processing", 20)
        result = workflow.segment_sections(state)
        state.update(result)
        update_step(job, 1, "completed", 30)
        
        # Step 3: Extract candidates
        update_step(job, 2, "processing", 35)
        result = workflow.extract_candidates(state)
        state.update(result)
        update_step(job, 2, "completed", 50)
        
        # Step 4: Normalize
        update_step(job, 3, "processing", 55)
        result = workflow.normalize_entities(state)
        state.update(result)
        update_step(job, 3, "completed", 65)
        
        # Step 5: Relationships (done in normalize)
        update_step(job, 4, "processing", 70)
        update_step(job, 4, "completed", 75)
        
        # Step 6: Generate BPMN
        update_step(job, 5, "processing", 80)
        result = workflow.generate_skills(state)
        state.update(result)
        result = workflow.assemble_bpmn(state)
        state.update(result)
        update_step(job, 5, "completed", 85)
        
        # Step 7: Generate DMN
        update_step(job, 6, "processing", 88)
        result = workflow.generate_dmn(state)
        state.update(result)
        update_step(job, 6, "completed", 92)
        
        # Step 8: Export
        update_step(job, 7, "processing", 95)
        result = workflow.export_artifacts(state)
        state.update(result)
        update_step(job, 7, "completed", 100)
        
        # Store result summary
        job["status"] = "completed"
        job["result"] = {
            "processes": len(state.get("processes", [])),
            "tasks": len(state.get("tasks", [])),
            "roles": len(state.get("roles", [])),
            "gateways": len(state.get("gateways", [])),
            "decisions": len(state.get("dmn_decisions", [])),
            "bpmn_path": str(Config.OUTPUT_DIR / "process.bpmn"),
            "dmn_path": str(Config.OUTPUT_DIR / "decisions.dmn")
        }
        
        workflow.neo4j.close()
        
    except Exception as e:
        import traceback
        job["status"] = "error"
        job["error"] = str(e)
        job["current_step"] = "error"
        print(f"Error in background processing: {e}")
        traceback.print_exc()


def update_step(job: dict, step_index: int, status: str, progress: int):
    """Update step status and overall progress."""
    if step_index < len(job["steps"]):
        job["steps"][step_index]["status"] = status
    job["progress"] = progress
    job["current_step"] = job["steps"][step_index]["name"] if step_index < len(job["steps"]) else "completed"


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get job processing status."""
    if job_id not in job_progress:
        raise HTTPException(404, "Job not found")
    return job_progress[job_id]


@app.get("/api/jobs/{job_id}/stream")
async def stream_job_status(job_id: str):
    """Stream job status updates via SSE."""
    if job_id not in job_progress:
        raise HTTPException(404, "Job not found")
    
    async def event_generator():
        last_progress = -1
        while True:
            job = job_progress.get(job_id)
            if not job:
                break
            
            if job["progress"] != last_progress or job["status"] in ["completed", "error"]:
                last_progress = job["progress"]
                yield f"data: {json.dumps(job)}\n\n"
            
            if job["status"] in ["completed", "error"]:
                break
            
            await asyncio.sleep(0.5)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


# ==================== Entity APIs ====================

@app.get("/api/processes")
async def get_processes():
    """Get all processes."""
    neo4j = Neo4jClient()
    try:
        with neo4j.session() as session:
            result = session.run("""
                MATCH (p:Process)
                OPTIONAL MATCH (p)-[:HAS_TASK]->(t:Task)
                OPTIONAL MATCH (p)<-[:SUPPORTED_BY]-(c:ReferenceChunk)
                RETURN p {.*, taskCount: count(DISTINCT t)} as process,
                       collect(DISTINCT {page: c.page, text: c.text})[0] as evidence
                ORDER BY p.name
            """)
            processes = []
            for record in result:
                proc = record["process"]
                proc["evidence"] = record["evidence"]
                processes.append(proc)
            return {"processes": processes}
    finally:
        neo4j.close()


@app.get("/api/processes/{proc_id}")
async def get_process_detail(proc_id: str):
    """Get process with all related entities."""
    neo4j = Neo4jClient()
    try:
        data = neo4j.get_process_with_details(proc_id)
        if not data:
            raise HTTPException(404, "Process not found")
        return data
    finally:
        neo4j.close()


@app.get("/api/tasks")
async def get_tasks():
    """Get all tasks with relationships."""
    neo4j = Neo4jClient()
    try:
        with neo4j.session() as session:
            result = session.run("""
                MATCH (t:Task)
                OPTIONAL MATCH (t)-[:PERFORMED_BY]->(r:Role)
                OPTIONAL MATCH (p:Process)-[:HAS_TASK]->(t)
                OPTIONAL MATCH (t)-[:SUPPORTED_BY]->(c:ReferenceChunk)
                OPTIONAL MATCH (t)-[:NEXT]->(next:Task)
                OPTIONAL MATCH (prev:Task)-[:NEXT]->(t)
                RETURN t {.*} as task,
                       r.name as role_name,
                       p.name as process_name,
                       p.proc_id as process_id,
                       collect(DISTINCT {page: c.page, text: left(c.text, 200)})[0] as evidence,
                       collect(DISTINCT next.name) as next_tasks,
                       collect(DISTINCT prev.name) as prev_tasks
                ORDER BY t.order
            """)
            tasks = []
            for record in result:
                task = record["task"]
                task["role_name"] = record["role_name"]
                task["process_name"] = record["process_name"]
                task["process_id"] = record["process_id"]
                task["evidence"] = record["evidence"]
                task["next_tasks"] = [n for n in record["next_tasks"] if n]
                task["prev_tasks"] = [p for p in record["prev_tasks"] if p]
                tasks.append(task)
            return {"tasks": tasks}
    finally:
        neo4j.close()


@app.get("/api/roles")
async def get_roles():
    """Get all roles."""
    neo4j = Neo4jClient()
    try:
        with neo4j.session() as session:
            result = session.run("""
                MATCH (r:Role)
                OPTIONAL MATCH (t:Task)-[:PERFORMED_BY]->(r)
                OPTIONAL MATCH (r)-[:MAKES_DECISION]->(d:DMNDecision)
                OPTIONAL MATCH (r)-[:SUPPORTED_BY]->(c:ReferenceChunk)
                RETURN r {.*, taskCount: count(DISTINCT t), decisionCount: count(DISTINCT d)} as role,
                       collect(DISTINCT {page: c.page, text: left(c.text, 200)})[0] as evidence
                ORDER BY r.name
            """)
            roles = []
            for record in result:
                role = record["role"]
                role["evidence"] = record["evidence"]
                roles.append(role)
            return {"roles": roles}
    finally:
        neo4j.close()


@app.get("/api/decisions")
async def get_decisions():
    """Get all DMN decisions."""
    neo4j = Neo4jClient()
    try:
        with neo4j.session() as session:
            result = session.run("""
                MATCH (d:DMNDecision)
                OPTIONAL MATCH (d)-[:HAS_RULE]->(rule:DMNRule)
                OPTIONAL MATCH (r:Role)-[:MAKES_DECISION]->(d)
                OPTIONAL MATCH (d)-[:SUPPORTED_BY]->(c:ReferenceChunk)
                RETURN d {.*, ruleCount: count(DISTINCT rule)} as decision,
                       collect(DISTINCT r.name) as roles,
                       collect(DISTINCT {page: c.page, text: left(c.text, 200)})[0] as evidence
                ORDER BY d.name
            """)
            decisions = []
            for record in result:
                dec = record["decision"]
                dec["roles"] = [r for r in record["roles"] if r]
                dec["evidence"] = record["evidence"]
                decisions.append(dec)
            return {"decisions": decisions}
    finally:
        neo4j.close()


@app.get("/api/sequence-flows")
async def get_sequence_flows():
    """Get all sequence flows (NEXT relationships)."""
    neo4j = Neo4jClient()
    try:
        with neo4j.session() as session:
            result = session.run("""
                MATCH (t1:Task)-[r:NEXT]->(t2:Task)
                OPTIONAL MATCH (p:Process)-[:HAS_TASK]->(t1)
                RETURN t1.name as from_task,
                       t1.task_id as from_task_id,
                       t2.name as to_task,
                       t2.task_id as to_task_id,
                       r.condition as condition,
                       p.name as process_name
                ORDER BY p.name, t1.order
            """)
            flows = []
            for record in result:
                flows.append({
                    "from_task": record["from_task"],
                    "from_task_id": record["from_task_id"],
                    "to_task": record["to_task"],
                    "to_task_id": record["to_task_id"],
                    "condition": record["condition"],
                    "process_name": record["process_name"]
                })
            return {"flows": flows}
    finally:
        neo4j.close()


@app.get("/api/graph-stats")
async def get_graph_stats():
    """Get graph statistics."""
    neo4j = Neo4jClient()
    try:
        with neo4j.session() as session:
            stats = {}
            
            queries = {
                "processes": "MATCH (n:Process) RETURN count(n) as count",
                "tasks": "MATCH (n:Task) RETURN count(n) as count",
                "roles": "MATCH (n:Role) RETURN count(n) as count",
                "gateways": "MATCH (n:Gateway) RETURN count(n) as count",
                "events": "MATCH (n:Event) RETURN count(n) as count",
                "decisions": "MATCH (n:DMNDecision) RETURN count(n) as count",
                "rules": "MATCH (n:DMNRule) RETURN count(n) as count",
                "skills": "MATCH (n:Skill) RETURN count(n) as count",
                "documents": "MATCH (n:Document) RETURN count(n) as count",
                "chunks": "MATCH (n:ReferenceChunk) RETURN count(n) as count",
            }
            
            for key, query in queries.items():
                result = session.run(query)
                stats[key] = result.single()["count"]
            
            # Relationship counts
            rel_queries = {
                "has_task": "MATCH ()-[r:HAS_TASK]->() RETURN count(r) as count",
                "performed_by": "MATCH ()-[r:PERFORMED_BY]->() RETURN count(r) as count",
                "next": "MATCH ()-[r:NEXT]->() RETURN count(r) as count",
                "supported_by": "MATCH ()-[r:SUPPORTED_BY]->() RETURN count(r) as count",
                "makes_decision": "MATCH ()-[r:MAKES_DECISION]->() RETURN count(r) as count",
            }
            
            stats["relationships"] = {}
            for key, query in rel_queries.items():
                result = session.run(query)
                stats["relationships"][key] = result.single()["count"]
            
            return stats
    finally:
        neo4j.close()


# ==================== File APIs ====================

@app.get("/api/files/bpmn")
async def get_bpmn_file():
    """Get the generated BPMN file."""
    bpmn_path = Config.OUTPUT_DIR / "process.bpmn"
    if not bpmn_path.exists():
        raise HTTPException(404, "BPMN file not found")
    return FileResponse(bpmn_path, media_type="application/xml", filename="process.bpmn")


@app.get("/api/files/bpmn/content")
async def get_bpmn_content():
    """Get BPMN file content as text."""
    bpmn_path = Config.OUTPUT_DIR / "process.bpmn"
    if not bpmn_path.exists():
        raise HTTPException(404, "BPMN file not found")
    return {"content": bpmn_path.read_text(encoding="utf-8")}


@app.get("/api/files/dmn")
async def get_dmn_file():
    """Get the generated DMN file."""
    dmn_path = Config.OUTPUT_DIR / "decisions.dmn"
    if not dmn_path.exists():
        raise HTTPException(404, "DMN file not found")
    return FileResponse(dmn_path, media_type="application/xml", filename="decisions.dmn")


@app.get("/api/files/pdf/{filename}")
async def get_pdf_file(filename: str):
    """Get uploaded PDF file."""
    pdf_path = Config.UPLOAD_DIR / filename
    if not pdf_path.exists():
        raise HTTPException(404, "PDF file not found")
    return FileResponse(pdf_path, media_type="application/pdf")


def run_server():
    """Run the FastAPI server."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run_server()

