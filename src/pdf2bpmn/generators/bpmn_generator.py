"""BPMN XML generator."""
from typing import Optional
from pathlib import Path
from jinja2 import Template

from ..models.entities import Process, Task, Role, Gateway, Event, GatewayType, EventType


BPMN_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  id="Definitions_{{ process.proc_id }}"
                  targetNamespace="http://bpmn.io/schema/bpmn">
  
  <bpmn:collaboration id="Collaboration_{{ process.proc_id }}">
    <bpmn:participant id="Participant_{{ process.proc_id }}" 
                      name="{{ process.name }}" 
                      processRef="Process_{{ process.proc_id }}" />
  </bpmn:collaboration>
  
  <bpmn:process id="Process_{{ process.proc_id }}" 
                name="{{ process.name }}" 
                isExecutable="true">
    
    <!-- Lanes for Roles -->
    <bpmn:laneSet id="LaneSet_{{ process.proc_id }}">
      {% for role in roles %}
      <bpmn:lane id="Lane_{{ role.role_id }}" name="{{ role.name }}">
        {% for task in tasks_by_role.get(role.role_id, []) %}
        <bpmn:flowNodeRef>Task_{{ task.task_id }}</bpmn:flowNodeRef>
        {% endfor %}
      </bpmn:lane>
      {% endfor %}
      {% if unassigned_tasks %}
      <bpmn:lane id="Lane_Unassigned" name="Unassigned">
        {% for task in unassigned_tasks %}
        <bpmn:flowNodeRef>Task_{{ task.task_id }}</bpmn:flowNodeRef>
        {% endfor %}
      </bpmn:lane>
      {% endif %}
    </bpmn:laneSet>
    
    <!-- Start Events -->
    {% for event in events if event.event_type.value == 'start' %}
    <bpmn:startEvent id="StartEvent_{{ event.event_id }}" name="{{ event.name }}">
      {% if event.trigger %}
      <bpmn:documentation>{{ event.trigger }}</bpmn:documentation>
      {% endif %}
      <bpmn:outgoing>Flow_Start_{{ event.event_id }}</bpmn:outgoing>
    </bpmn:startEvent>
    {% endfor %}
    
    {% if not start_events %}
    <bpmn:startEvent id="StartEvent_Default" name="Start">
      <bpmn:outgoing>Flow_Start_Default</bpmn:outgoing>
    </bpmn:startEvent>
    {% endif %}
    
    <!-- Tasks -->
    {% for task in tasks %}
    <bpmn:{% if task.task_type.value == 'human' %}userTask{% elif task.task_type.value == 'system' %}serviceTask{% else %}task{% endif %} 
         id="Task_{{ task.task_id }}" 
         name="{{ task.name }}">
      {% if task.description %}
      <bpmn:documentation>{{ task.description }}</bpmn:documentation>
      {% endif %}
      <bpmn:incoming>Flow_To_{{ task.task_id }}</bpmn:incoming>
      <bpmn:outgoing>Flow_From_{{ task.task_id }}</bpmn:outgoing>
    </bpmn:{% if task.task_type.value == 'human' %}userTask{% elif task.task_type.value == 'system' %}serviceTask{% else %}task{% endif %}>
    {% endfor %}
    
    <!-- Gateways -->
    {% for gateway in gateways %}
    <bpmn:{% if gateway.gateway_type.value == 'exclusive' %}exclusiveGateway{% elif gateway.gateway_type.value == 'parallel' %}parallelGateway{% else %}inclusiveGateway{% endif %}
         id="Gateway_{{ gateway.gateway_id }}"
         name="{{ gateway.condition or gateway.description }}">
      <bpmn:incoming>Flow_To_Gateway_{{ gateway.gateway_id }}</bpmn:incoming>
      <bpmn:outgoing>Flow_From_Gateway_{{ gateway.gateway_id }}_Yes</bpmn:outgoing>
      <bpmn:outgoing>Flow_From_Gateway_{{ gateway.gateway_id }}_No</bpmn:outgoing>
    </bpmn:{% if gateway.gateway_type.value == 'exclusive' %}exclusiveGateway{% elif gateway.gateway_type.value == 'parallel' %}parallelGateway{% else %}inclusiveGateway{% endif %}>
    {% endfor %}
    
    <!-- End Events -->
    {% for event in events if event.event_type.value == 'end' %}
    <bpmn:endEvent id="EndEvent_{{ event.event_id }}" name="{{ event.name }}">
      <bpmn:incoming>Flow_End_{{ event.event_id }}</bpmn:incoming>
    </bpmn:endEvent>
    {% endfor %}
    
    {% if not end_events %}
    <bpmn:endEvent id="EndEvent_Default" name="End">
      <bpmn:incoming>Flow_End_Default</bpmn:incoming>
    </bpmn:endEvent>
    {% endif %}
    
    <!-- Sequence Flows -->
    {% for flow in sequence_flows %}
    <bpmn:sequenceFlow id="{{ flow.id }}" 
                       sourceRef="{{ flow.source }}" 
                       targetRef="{{ flow.target }}"
                       {% if flow.name %}name="{{ flow.name }}"{% endif %} />
    {% endfor %}
    
  </bpmn:process>
  
  <!-- Diagram -->
  <bpmndi:BPMNDiagram id="BPMNDiagram_{{ process.proc_id }}">
    <bpmndi:BPMNPlane id="BPMNPlane_{{ process.proc_id }}" 
                      bpmnElement="Collaboration_{{ process.proc_id }}">
      
      <bpmndi:BPMNShape id="Participant_{{ process.proc_id }}_di" 
                        bpmnElement="Participant_{{ process.proc_id }}" 
                        isHorizontal="true">
        <dc:Bounds x="160" y="80" width="{{ 200 + tasks|length * 180 }}" height="{{ 100 + roles|length * 120 }}" />
      </bpmndi:BPMNShape>
      
      {% for i, role in enumerate(roles) %}
      <bpmndi:BPMNShape id="Lane_{{ role.role_id }}_di" 
                        bpmnElement="Lane_{{ role.role_id }}" 
                        isHorizontal="true">
        <dc:Bounds x="190" y="{{ 80 + i * 120 }}" width="{{ 170 + tasks|length * 180 }}" height="120" />
      </bpmndi:BPMNShape>
      {% endfor %}
      
      {% for i, task in enumerate(tasks) %}
      <bpmndi:BPMNShape id="Task_{{ task.task_id }}_di" bpmnElement="Task_{{ task.task_id }}">
        <dc:Bounds x="{{ 300 + i * 180 }}" y="{{ 110 + task_lane_index.get(task.task_id, 0) * 120 }}" width="100" height="80" />
      </bpmndi:BPMNShape>
      {% endfor %}
      
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
  
</bpmn:definitions>
"""


class BPMNGenerator:
    """Generate BPMN XML from extracted process data."""
    
    def __init__(self):
        self.template = Template(BPMN_TEMPLATE)
    
    def generate(
        self,
        process: Process,
        tasks: list[Task],
        roles: list[Role],
        gateways: list[Gateway],
        events: list[Event],
        task_role_map: dict[str, str] = None
    ) -> str:
        """Generate BPMN XML for a process."""
        
        task_role_map = task_role_map or {}
        
        # Organize tasks by role
        tasks_by_role = {}
        unassigned_tasks = []
        task_lane_index = {}
        
        for i, task in enumerate(sorted(tasks, key=lambda t: t.order)):
            role_id = task_role_map.get(task.task_id)
            if role_id:
                if role_id not in tasks_by_role:
                    tasks_by_role[role_id] = []
                tasks_by_role[role_id].append(task)
                # Find lane index
                for j, role in enumerate(roles):
                    if role.role_id == role_id:
                        task_lane_index[task.task_id] = j
                        break
            else:
                unassigned_tasks.append(task)
                task_lane_index[task.task_id] = len(roles)  # Unassigned lane
        
        # Separate start and end events
        start_events = [e for e in events if e.event_type == EventType.START]
        end_events = [e for e in events if e.event_type == EventType.END]
        
        # Generate sequence flows
        sequence_flows = self._generate_sequence_flows(
            tasks, gateways, start_events, end_events
        )
        
        # Render template
        bpmn_xml = self.template.render(
            process=process,
            tasks=sorted(tasks, key=lambda t: t.order),
            roles=roles,
            gateways=gateways,
            events=events,
            tasks_by_role=tasks_by_role,
            unassigned_tasks=unassigned_tasks,
            start_events=start_events,
            end_events=end_events,
            sequence_flows=sequence_flows,
            task_lane_index=task_lane_index,
            enumerate=enumerate
        )
        
        return bpmn_xml
    
    def _generate_sequence_flows(
        self,
        tasks: list[Task],
        gateways: list[Gateway],
        start_events: list[Event],
        end_events: list[Event]
    ) -> list[dict]:
        """Generate sequence flow connections."""
        flows = []
        sorted_tasks = sorted(tasks, key=lambda t: t.order)
        
        # Flow from start event to first task
        if sorted_tasks:
            first_task = sorted_tasks[0]
            if start_events:
                for event in start_events:
                    flows.append({
                        "id": f"Flow_Start_{event.event_id}",
                        "source": f"StartEvent_{event.event_id}",
                        "target": f"Task_{first_task.task_id}",
                        "name": None
                    })
            else:
                flows.append({
                    "id": "Flow_Start_Default",
                    "source": "StartEvent_Default",
                    "target": f"Task_{first_task.task_id}",
                    "name": None
                })
            
            # Flow to first task (incoming)
            flows.append({
                "id": f"Flow_To_{first_task.task_id}",
                "source": start_events[0].event_id if start_events else "StartEvent_Default",
                "target": f"Task_{first_task.task_id}",
                "name": None
            })
        
        # Flows between tasks
        for i, task in enumerate(sorted_tasks):
            if i < len(sorted_tasks) - 1:
                next_task = sorted_tasks[i + 1]
                flows.append({
                    "id": f"Flow_From_{task.task_id}",
                    "source": f"Task_{task.task_id}",
                    "target": f"Task_{next_task.task_id}",
                    "name": None
                })
                flows.append({
                    "id": f"Flow_To_{next_task.task_id}",
                    "source": f"Task_{task.task_id}",
                    "target": f"Task_{next_task.task_id}",
                    "name": None
                })
        
        # Flow from last task to end event
        if sorted_tasks:
            last_task = sorted_tasks[-1]
            if end_events:
                for event in end_events:
                    flows.append({
                        "id": f"Flow_End_{event.event_id}",
                        "source": f"Task_{last_task.task_id}",
                        "target": f"EndEvent_{event.event_id}",
                        "name": None
                    })
            else:
                flows.append({
                    "id": "Flow_End_Default",
                    "source": f"Task_{last_task.task_id}",
                    "target": "EndEvent_Default",
                    "name": None
                })
            
            # Outgoing flow from last task
            flows.append({
                "id": f"Flow_From_{last_task.task_id}",
                "source": f"Task_{last_task.task_id}",
                "target": end_events[0].event_id if end_events else "EndEvent_Default",
                "name": None
            })
        
        return flows
    
    def save(self, bpmn_xml: str, output_path: str) -> str:
        """Save BPMN XML to file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(bpmn_xml, encoding="utf-8")
        return str(path)




