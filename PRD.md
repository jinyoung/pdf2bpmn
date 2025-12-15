

## 1) 제품 목표와 산출물

### 목표

* 업무 편람/업무 정의서(PDF)에서 **프로세스 / 액티비티(태스크) / 역할(Role)** 을 추출
* 태스크의 “세부 지침”을 **Agent Skill 문서(Claude Skills 문법의 Markdown)** 로 생성
* 규칙/분기/판단 로직이 있으면 **DMN 규칙 후보**를 추출하여 연결
* 모든 산출물을 **Neo4j 지식그래프(온톨로지 형태)** 로 저장
* 최종적으로 **ProcessGPT에 투입 가능한 BPMN XML(및 DMN, Skill 문서)** 를 자동 생성
* 모호/누락/충돌은 **Human-in-the-loop(HITL)** 로 사용자에게 질문해 확정

### 최종 출력(Artifacts)

1. `process.bpmn` (BPMN XML)
2. `*.skill.md` (태스크별 스킬 문서: 재사용 가능)
3. `*.dmn` 또는 `dmn.json` (룰 후보 + 근거)
4. Neo4j 그래프(노드/엣지 + 근거 링크 + 버전)
5. 생성/검증 로그(추출 근거, 사용자 승인 히스토리)

---

## 2) 입력 범위 / 지원 문서 형태

* PDF 1개 이상 (다중 문서 입력 지원)
* 문서 유형: 업무편람, SOP, 정책/규정, 체크리스트, 매뉴얼, 가이드, R&R 문서
* 문서 품질: 텍스트 PDF 우선(스캔 PDF는 OCR 파이프라인 옵션)

---

## 3) 핵심 유저 플로우

1. 사용자가 PDF 업로드(1~N개)
2. 시스템이 “문서 구조”를 잡음 (목차/섹션/표/도식/부록)
3. 후보 프로세스(메가/메이저/프로세스)와 태스크 목록을 1차 생성
4. **사용자에게 검증 질문**

   * “이 섹션은 프로세스가 맞나요, 단순 설명인가요?”
   * “이 활동의 담당 역할은 A/B/C 중 무엇인가요?”
   * “이 조건 분기는 규칙(룰)로 고정인가요, 재량인가요?”
5. 확정된 구조를 바탕으로:

   * BPMN 생성(풀/레인/태스크/게이트웨이/이벤트)
   * 태스크별 Skill 문서 생성(지침/입력/출력/예외/툴 호출)
   * DMN 후보 생성(조건-결과 테이블 + 근거 문장 링크)
6. Neo4j에 저장 및 “재사용 연결(스킬/룰 공용화)” 수행
7. 최종 결과를 ProcessGPT로 Export

---

## 4) 추출 파이프라인(에이전트 구조)

### A. 문서 인제스트/정규화

* PDF → (텍스트/레이아웃) 추출
* 섹션 트리 생성: heading hierarchy + 페이지 범위 + 표/리스트 감지
* “문서 단위 Evidence” 생성: `(doc_id, page, bbox(optional), text_span)`

### B. 후보 엔티티 추출 (LLM + 규칙 혼합)

* Process 후보: “절차/업무 흐름/처리 단계/프로세스 개요/업무 절차” 등 패턴
* Task 후보: “~한다/~해야 한다/점검/승인/검토/접수/등록/통보/보고” 등 행위 중심
* Role 후보: “담당/승인권자/검토자/부서명/직책/시스템/대행/외부기관”
* Gateway 후보: 조건문(“~인 경우/아닌 경우/다만/예외적으로/필요 시”)
* Event 후보: 시작 트리거(“요청 접수 시/신청서 제출 후/정기적으로”), 종료 조건

### C. 태스크 지침 캡처 → Skill 후보 생성

* 태스크 설명 주변 문장/표/체크리스트를 “지침 블록”으로 캡처
* “사람 수행 vs 에이전트 수행” 분기:

  * 사람이면: 작업 안내서(참고용)
  * 에이전트면: Claude Skills 문법 스킬 마크다운 생성

### D. DMN 후보 추출

* 의사결정 로직이 명확하면:

  * 입력 데이터 항목 추출(예: 금액, 기간, 등급, 서류 유무)
  * 결과/조치 추출(승인/반려/추가 서류 요청)
  * 룰 테이블 후보 생성 + 근거(Evidence) 링크

### E. 그래프 저장 + 재사용 연결

* 스킬 유사도/동일성 판정:

  * “동일/유사 스킬”을 여러 태스크에서 재사용 연결
* DMN 동일성 판정:

  * 동일한 결정(Decision) 구조면 공유

### F. BPMN 조립 + 검증

* Lane = Role, Task는 해당 Lane에 배치
* Gateway 연결, 시퀀스 흐름 구성
* 불완전 연결/미정 Role/미정 조건은 HITL 질문 생성

---

## 5) Human-in-the-loop 질문 설계 (LangGraph에 내장)

### 질문이 필요한 대표 케이스

1. **경계가 모호함**: “이 섹션은 프로세스인가요? 지침인가요?”
2. **역할 불명확**: “검토자는 누구인가요? (부서/직책 선택)”
3. **순서 불명확**: “A 다음에 B인가요? 병렬인가요?”
4. **조건 분기 불명확**: “이 판단은 룰로 고정? 담당자 재량?”
5. **입출력 미정**: “이 태스크의 입력 문서/시스템 값은 무엇?”
6. **예외 처리**: “예외 시 종료/재시도/상위 보고 중 무엇?”

### 질문 형태(UX)

* 선택형(라디오/드롭다운) 우선 → 자유 서술 최소화
* 질문은 항상 **근거 문장/페이지**를 함께 보여줌
* 답변은 즉시 그래프/BPMN에 반영(상태 전이)

---

## 6) Neo4j 그래프 스키마(초안)

### 노드(Labels) 예시

* `Document {doc_id, title, version, source, uploaded_at}`
* `Section {section_id, heading, level, page_from, page_to}`
* `MegaProcess {mp_id, name, description}`
* `MajorProcess {maj_id, name}`
* `Process {proc_id, name, purpose, triggers, outcomes, version}`
* `Task {task_id, name, type(human|agent|system), description}`
* `Role {role_id, name, org_unit, persona_hint}`
* `Agent {agent_id, name, persona, toolset_ref, memory_policy}`
* `Skill {skill_id, name, md_path, inputs, outputs, preconditions}`
* `DMNDecision {decision_id, name}`
* `DMNRule {rule_id, when, then, confidence}`
* `Evidence {evi_id, doc_id, page, text_span, locator}`
* `Ambiguity {amb_id, question, options, status(open|resolved)}`

### 관계(Relationships) 예시

* `(Document)-[:HAS_SECTION]->(Section)`
* `(Section)-[:MENTIONS]->(Process|Task|Role|DMNDecision)`
* `(MegaProcess)-[:HAS_MAJOR]->(MajorProcess)-[:HAS_PROCESS]->(Process)`
* `(Process)-[:HAS_TASK]->(Task)`
* `(Task)-[:PERFORMED_BY]->(Role)` 또는 `(Task)-[:PERFORMED_BY]->(Agent)`
* `(Task)-[:USES_SKILL]->(Skill)` (agent task일 때)
* `(Process)-[:USES_DECISION]->(DMNDecision)-[:HAS_RULE]->(DMNRule)`
* `(Task|Process|DMNRule|Skill)-[:SUPPORTED_BY]->(Evidence)`
* `(Ambiguity)-[:ABOUT]->(Task|Role|Gateway|DMNDecision)`
* `(Skill)-[:REUSED_BY]->(Task)` (재사용 추적)

### 버전/감사(Audit)

* 모든 핵심 노드에 `version`, `created_by(agent|user)`, `approved_by`, `approved_at`
* 사용자 응답은 `(UserAnswer)` 노드로 남기거나 이벤트 로그로 남김

---

## 7) Skill Markdown(Claude Skills 문법) 생성 규격 제안

태스크의 “세부 지침”을 스킬로 만들 때, 최소 아래 구조를 고정하면 재사용/검증이 쉬워집니다.

```md
# Skill: <skill_name>

## Purpose
- 이 스킬이 해결하는 업무 목적

## Inputs
- required:
  - <field>: <type> - <설명>
- optional:
  - ...

## Outputs
- <field>: <type> - <설명>

## Preconditions
- 실행 전 만족해야 하는 조건

## Procedure
1. 단계별 수행 절차(문서 지침 기반)
2. 시스템 조회/검증/등록 단계
3. 분기 조건(가능하면 Decision으로 분리)

## Exceptions & Handling
- 예외 케이스와 대응

## Tools
- 사용할 MCP/내부 API/DB 조회 등 (있다면)

## Evidence
- doc_id / page / 근거 문장 요약
```

> 포인트: “Procedure”에 문서 지침을 그대로 길게 붙이기보다, **정규화된 단계**로 바꾸고, 룰은 가능하면 DMN으로 분리해 “Skill은 실행 절차”에 집중시키는 구성이 좋습니다.

---

## 8) LangGraph 아키텍처(상태 머신)

### 상태(State) 핵심 필드

* `docs[]`, `sections[]`
* `candidates.processes/tasks/roles/gateways/decisions`
* `graph_draft` (Neo4j upsert 초안)
* `bpmn_draft`, `dmn_draft`, `skills_draft`
* `open_questions[]` (Ambiguity)
* `user_answers[]`
* `confidence_scores`

### 노드(그래프 실행 노드) 예시

1. `ingest_pdf`
2. `segment_sections`
3. `extract_candidates`
4. `normalize_entities`
5. `detect_ambiguities`
6. `ask_user` (HITL)
7. `apply_user_answer`
8. `generate_skills`
9. `generate_dmn`
10. `assemble_bpmn`
11. `validate_consistency`
12. `persist_to_neo4j`
13. `export_artifacts`

### 라우팅(조건)

* `if open_questions > 0` → `ask_user` 반복
* `if confidence < threshold` → `ask_user`
* `if user approves` → export/persist 확정

---

## 9) 품질/정확도 전략(현실적인 운영 포인트)

* **근거 기반 생성**: 모든 Task/Role/Rule/Skill은 Evidence 링크가 없으면 “미확정” 처리
* **Confidence + HITL**: 신뢰도 낮으면 자동 질문 생성
* **중복/재사용 자동화**: 스킬/룰은 “완전 동일” + “의미 유사” 두 단계로 연결
* **문서 간 충돌 처리**: 다중 PDF에서 같은 프로세스가 다르게 쓰이면 “conflict”로 표기하고 질문

---

좋아. 지금 말씀하신 핵심은 PRD에 **“문서가 흩어져 있어도(앞·뒤·부록) 기존 노드와 끊김 없이 합쳐지는 그래프 구축 방식”**을 **1급 요구사항**으로 넣는 거고, 그 핵심 기술이 **Neo4j 계층형 노드 분해 + Evidence 노드화 + Vector Embedding 기반 그래프 탐색/매칭**이야. 아래를 PRD에 바로 들어갈 수 있는 형태로 정리해줄게.

---

## 1) 그래프 모델링 원칙 (PRD 반영)

### 1.1 Skill 문서도 “헤드 + 하위 레퍼런스” 계층 구조로 분리

* `Skill` 노드는 “헤더(정의/목적/입출력/절차/예외/툴)”만 가진다.
* Skill 아래에는 문서 근거를 **문장/문단 단위로 쪼갠 Reference 노드**가 매달린다.
* 즉, “스킬 문서(결론)”과 “근거(문서 조각)”를 절대 섞지 않고, 근거는 항상 별도 노드로 분리한다.

**예시 노드**

* `Skill {skill_id, name, summary, io_schema, version}`
* `SkillSection {section_type: Purpose|Inputs|Procedure|Exceptions|Tools, text}`  ← Skill 내부도 더 쪼개고 싶으면
* `ReferenceChunk {chunk_id, doc_id, page, span, text, hash}`
* `EvidenceQuote {quote_id, normalized_text, confidence}` (선택)

**예시 관계**

* `(Task)-[:USES_SKILL]->(Skill)`
* `(Skill)-[:HAS_SECTION]->(SkillSection)`
* `(SkillSection)-[:SUPPORTED_BY]->(ReferenceChunk)`
* `(ReferenceChunk)-[:FROM_DOCUMENT]->(Document)`
* `(ReferenceChunk)-[:LOCATED_IN]->(Section)`

> 효과: Skill은 “실행 가능한 지식”으로 깔끔하고, 근거는 끝까지 추적/감사 가능.

---

## 2) “흩어진 설명”을 끊김 없이 합치는 기능 요구사항

### 2.1 분산 서술(Scattered Definition) 통합

문서에서 프로세스 정의가:

* 앞부분(개요)에서 1번 나오고,
* 뒤(상세)에서 다시 보강되고,
* 부록/표/FAQ에 예외 규정이 흩어져 등장하는 경우가 많다.

**PRD 요구사항**

* 시스템은 문서를 순차 탐색하면서, 새로 발견되는 후보 정의/태스크/역할/규칙이

  * **기존 그래프의 어떤 노드와 동일/유사한지 찾아 붙이거나**
  * **없으면 새로 만들고**
  * **충돌이 있으면 “Conflict/Ambiguity”로 기록**해야 한다.

### 2.2 “그래프 내 기존 노드 찾기”는 Vector 기반으로 수행

* Neo4j 내부에 **임베딩 인덱스(Vector Index)** 를 두고,
* 새로 파싱되는 `CandidateChunk`(문장/문단)가 들어오면:

  1. **후보 타입 분류**(Process/Task/Role/Decision/SkillRef)
  2. 해당 타입의 노드 집합에서 **Top-K 유사도 검색**
  3. 임계치/규칙에 따라 **MERGE / LINK / NEW / CONFLICT** 결정

**결정 규칙(초안)**

* similarity ≥ 0.90 : 동일(merge evidence)
* 0.80~0.90 : 유사(사용자 확인 질문 생성)
* < 0.80 : 신규 노드 생성
* 단, 이름/번호/코드가 일치하면 similarity가 낮아도 “강제 매칭” 후보로 올림

---

## 3) PRD에 들어갈 “그래프 확장 알고리즘” 섹션(명시적으로)

### 3.1 Incremental Graph Construction (스트리밍/증분 구축)

* 문서를 “섹션→문단→문장” 단위로 스트리밍 처리
* 각 단위마다 아래 상태전이를 수행:

**상태전이**

1. `ExtractCandidate` : 후보 엔티티/관계 추출
2. `ResolveToGraph` : 기존 그래프에서 매칭 노드 탐색(Vector + 규칙)
3. `UpsertGraph` : 연결/병합/신규 생성
4. `RecordEvidence` : 항상 ReferenceChunk로 근거 저장
5. `DetectConflict` : 정의/역할/순서가 충돌하면 Conflict 노드 생성
6. `HITLQuestion` : 모호/충돌이면 질문 큐 적재

### 3.2 정의/보강/예외가 “한 노드에 누적”되는 구조

* `ProcessDefinition` 노드는 단일 텍스트가 아니라 “정의 조각(definition fragments)”의 집합으로 구성

**예시**

* `Process`

  * `ProcessDefFragment`(개요 정의)
  * `ProcessDefFragment`(상세 보강)
  * `ProcessDefFragment`(예외/주의)

각 fragment는 항상 `ReferenceChunk`와 연결되어 출처가 남는다.

---

## 4) Neo4j 스키마 확장 제안 (이 요구를 만족시키기 위한 최소 추가)

### 4.1 “정의 조각” 계층

* `ProcessDefFragment {type: overview|detail|exception|note, text, confidence}`
* `(Process)-[:HAS_DEF]->(ProcessDefFragment)-[:SUPPORTED_BY]->(ReferenceChunk)`

### 4.2 “동일성/동의어/별칭” 계층

문서에서 같은 대상을 다르게 부를 수 있음(약칭/정식명/코드).

* `Alias {text, normalized}`
* `(Process|Task|Role)-[:HAS_ALIAS]->(Alias)`
* 별칭도 임베딩/룰 매칭에 포함

### 4.3 “충돌” 모델

* `Conflict {type, description, severity, status}`
* `(Conflict)-[:BETWEEN]->(ProcessDefFragment)` 혹은 `(Conflict)-[:ABOUT]->(Task|Role|Decision)`

---

## 5) LangGraph(또는 LangChain)에서의 구현 요구사항 문장(PRD 표현)

PRD에 아래처럼 **명확한 시스템 요구사항**으로 박아두면 좋아:

* 시스템은 PDF의 각 문장/문단을 처리할 때마다, **기존 Neo4j 그래프에서 동형 노드를 검색**해야 한다.
* 검색은 **벡터 유사도 기반(Top-K) + 키워드/별칭 룰**의 하이브리드여야 한다.
* 동일 엔티티로 판정되면 **엔티티 노드를 수정하지 않고**, 새로운 근거(`ReferenceChunk`)를 추가 연결하여 **증분 학습(근거 누적)** 형태로 확장해야 한다.
* 유사하지만 확정 불가한 경우는 **자동 병합 금지**, `Ambiguity`로 기록하고 **HITL 질문을 생성**해야 한다.
* 프로세스 정의/태스크 지침이 문서 곳곳에 흩어진 경우에도, 동일 엔티티에 대한 fragment들이 **하나의 엔티티 아래 계층적으로 축적**되도록 해야 한다.


