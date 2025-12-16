# PDF2BPMN 프로젝트 작업 요약

## 📋 프로젝트 개요
PDF 문서에서 비즈니스 프로세스를 추출하여 BPMN 다이어그램으로 변환하는 시스템 개발

---

## 🗂️ 작업 진행 과정

### 1. PDF 청킹 및 엔티티 추출 구조 분석
**프롬프트**: `pdf 문서 내용을 어떻게 청킹을 어떻게 하고 있나`

- `PDFExtractor`의 청킹 로직 분석
- `CHUNK_SIZE`: 1000자, `CHUNK_OVERLAP`: 200자
- 문단 단위로 분할 후 청크 생성

---

### 2. 청크 간 프로세스 연결 문제 분석
**프롬프트**: `기존 프로세스 정의에 보완되는 내용이 연속되지 않는 chunk에서 나타날때 graph 내에서 이미 선언된 프로세스 정의를 참고하는 것이 vector 검색을 통해 벌어지나?`

- 현재: 벡터 검색 없이 순차 처리
- 문제점: 떨어진 청크에서 동일 프로세스 인식 불가
- **해결책 제안**:
  1. 컨텍스트 주입 (기존 프로세스/역할 정보를 프롬프트에 포함)
  2. 후처리 병합 (유사 엔티티 통합)

---

### 3. 테스트 텍스트 및 단위 테스트 작성
**프롬프트**: `이러한 청크간에 떨어진 구조에서도 동일한 프로세스정의라고 판단되는 세부 요소들에 대하여 추출할 수 있는 테스트용 텍스트를 만들어보자`

- `tests/test_chunk_integration.py` 작성
- 분리된 3개 청크에서 동일 프로세스 추출 테스트

---

### 4. 컨텍스트 주입 구현
**프롬프트**: `첫번째 방법을 시도해보자`

- `EntityExtractor`에 `existing_processes`, `existing_roles`, `existing_tasks` 컨텍스트 주입
- `EXISTING_CONTEXT_TEMPLATE` 추가
- 프로세스/역할/태스크 중복 방지 규칙 프롬프트에 포함

---

### 5. 시퀀스 플로우(NEXT 관계) 테스트
**프롬프트**: `생성된 task 간에 next 관계가 없어서 시퀀스가 나타나있지 않으니 이것도 테스트에 포함`

- `_verify_task_sequences` 메서드 추가
- Task 간 NEXT 관계 생성 검증

---

### 6. BPMN 생성 테스트 분리
**프롬프트**: `bpmn 생성은 만들어진 neo4j 그래프에서 바로 수행하면 되므로 별도 테스트파일로 분리`

- `tests/test_bpmn_generation.py` 작성

---

### 7. 샘플 PDF 생성
**프롬프트**: `샘플 청크를 pdf 문서로 만들어서 uploads 폴더에 넣어줘`

- `reportlab`으로 한글 PDF 생성
- `uploads/process_sample1.pdf` 생성

---

### 8. Vue.js 프론트엔드 테스트
**프롬프트**: `vuejs 로 만든 frontend 로 테스트`

- BPMN 뷰어 로딩 문제 해결
- 백엔드-프론트엔드 연동 확인

---

### 9. 상세 진행상황 스트리밍 구현
**프롬프트**: `백엔드에서 프론트엔드로 좀더 상세한 진행상황이 stream 으로 전달되고 진행표시에 표시될 필요가 있다`

- SSE (Server-Sent Events) 구현
- 청크별 LLM 처리 상태 실시간 표시
- Neo4j 데이터 존재 시 확인 다이얼로그

---

### 10. SSE 실시간 스트리밍 문제 해결
**프롬프트**: `결과 로그가 나오긴한데 모든작업이 완료된 후에 한번에 쏟아지고 있어`

- `asyncio.to_thread.run_sync`로 동기 작업 분리
- `await asyncio.sleep(0)`으로 이벤트 루프 양보

---

### 11. BPMN 요소 클릭 시 상세정보 표시
**프롬프트**: `bpmn viewer에서 각 태스크를 클릭하면 해당 태스크에 대한 설명과 함께 해당 문서의 출처(페이지)와 출처 내용 일부를 발췌하여 표시`

- `/api/bpmn/element/{element_id}` API 추가
- 사이드 패널에 설명, 담당자, 출처 문서 표시

---

### 12. 태스크 중복 제거
**프롬프트**: `추출된 tasks 들을 보면 같은 의미를 같는 task 들이 중복하여 선언된 부분들이 보임`

- `_merge_similar_tasks` 메서드 구현
- 동일 역할의 연속 업무 병합 로직

---

### 13. Gateway 조건을 Sequence Flow로 이전
**프롬프트**: `현재 NEXT 가 하는 일이 BPMN의 Sequence 역할을 하는 Relation 이므로 현재 Gateway에 들어있떤 condition은 NEXT의 속성에 condition이 들어가도록 수정`

- `NEXT` 관계에 `condition` 속성 추가
- `link_task_sequence`, `link_gateway_to_task` 수정
- `get_sequence_flows` 메서드 추가

---

### 14. BPMN Sequence Flow 시각화
**프롬프트**: `bpmn 그림에 sequence 들이 보이지 않아. 아마 DI 요소들이 없는 이유인지..`

- `bpmndi:BPMNEdge` DI 요소 추가
- `di:waypoint` 좌표 계산 로직 구현

---

### 15. Sequence Flow 선 색상 개선
**프롬프트**: `선을 밝은색으로`, `선의 마커는 색이 밝아졌으나, 선 자체는 어두워서 안보임`

- CSS에서 `.djs-connection` 스타일 수정
- `path`, `polyline` 요소에 `stroke: #38bdf8` 적용

---

### 16. Sequence Flow 클릭 시 조건 표시
**프롬프트**: `각 시퀀스를 클릭했을때 컨디션이 포함되어있으면 화면에 출력`

- `ProcessView.vue`에서 SequenceFlow 클릭 핸들러 추가
- 사이드 패널에 조건(Condition) 표시

---

### 17. 조건 추출 프롬프트 개선
**프롬프트**: `현재 추출단계에서 컨디션 내용들이 하나도 추출되지 못했네. Gateway 에는 컨디션이 들어있는거 보니 컨디션은 Gateway로 추출하지 말고 Sequence 관계를 추출할때 같이 추출되어야 한다는 프롬프트로 전화해야 할거같아`

- `EXTRACTION_PROMPT` 수정:
  - Gateway: 분기점 이름만 추출
  - Sequence Flow: 조건(condition) 추출 강조

---

### 18. 조건 추출 테스트 및 검증
**프롬프트**: `여전이 원문에서 조건절을 추출해오지 못하고 있어 이것과 관련한 테스트를 작성하여 상황을 파악해보고 개선`

- `tests/test_condition_extraction.py` 작성
- **결과**: 조건 추출 성공 확인
  - "승인인 경우", "거부인 경우"
  - "예산이 충분한 경우", "예산이 부족한 경우"
  - "금액이 100만원 이상인 경우" 등

---

## 📁 수정된 주요 파일

| 파일 | 주요 변경 |
|------|----------|
| `entity_extractor.py` | 컨텍스트 주입, 조건 추출 프롬프트 |
| `workflow/graph.py` | 시퀀스 플로우 생성, 태스크 병합 |
| `neo4j_client.py` | NEXT 관계에 condition 추가 |
| `bpmn_generator.py` | DI 요소 생성, 조건 포함 |
| `api/main.py` | SSE 스트리밍, 요소 상세 API |
| `ProcessView.vue` | 시퀀스 클릭 시 조건 표시 |
| `HomeView.vue` | 진행상황 실시간 표시 |

---

## ✅ 최종 결과

1. **PDF → 청크 분할** → 컨텍스트 주입으로 일관된 추출
2. **엔티티 추출** → 프로세스, 태스크, 역할, 게이트웨이
3. **시퀀스 플로우** → 조건(Condition) 포함 추출
4. **Neo4j 저장** → NEXT 관계에 condition 속성
5. **BPMN 생성** → DI 요소 포함, 시각화
6. **프론트엔드** → 실시간 진행 표시, 요소 클릭 시 상세정보/조건 표시