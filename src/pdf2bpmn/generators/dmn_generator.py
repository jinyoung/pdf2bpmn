"""DMN XML generator."""
import json
from pathlib import Path
from jinja2 import Template

from ..models.entities import DMNDecision, DMNRule


DMN_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<dmn:definitions xmlns:dmn="https://www.omg.org/spec/DMN/20191111/MODEL/"
                 xmlns:dmndi="https://www.omg.org/spec/DMN/20191111/DMNDI/"
                 xmlns:dc="http://www.omg.org/spec/DMN/20180521/DC/"
                 xmlns:di="http://www.omg.org/spec/DMN/20180521/DI/"
                 id="Definitions_DMN"
                 name="Decision Model"
                 namespace="http://camunda.org/schema/1.0/dmn">
  
  {% for decision in decisions %}
  <dmn:decision id="Decision_{{ decision.decision_id }}" name="{{ decision.name }}">
    {% if decision.description %}
    <dmn:description>{{ decision.description }}</dmn:description>
    {% endif %}
    
    <!-- Input Data -->
    {% for input_name in decision.input_data %}
    <dmn:informationRequirement id="InformationRequirement_{{ decision.decision_id }}_{{ loop.index }}">
      <dmn:requiredInput href="#InputData_{{ input_name | replace(' ', '_') }}" />
    </dmn:informationRequirement>
    {% endfor %}
    
    <dmn:decisionTable id="DecisionTable_{{ decision.decision_id }}" hitPolicy="FIRST">
      
      <!-- Input Columns -->
      {% for input_name in decision.input_data %}
      <dmn:input id="Input_{{ decision.decision_id }}_{{ loop.index }}" label="{{ input_name }}">
        <dmn:inputExpression id="InputExpression_{{ decision.decision_id }}_{{ loop.index }}" typeRef="string">
          <dmn:text>{{ input_name | replace(' ', '_') }}</dmn:text>
        </dmn:inputExpression>
      </dmn:input>
      {% endfor %}
      
      <!-- Output Columns -->
      {% for output_name in decision.output_data %}
      <dmn:output id="Output_{{ decision.decision_id }}_{{ loop.index }}" 
                  label="{{ output_name }}" 
                  name="{{ output_name | replace(' ', '_') }}" 
                  typeRef="string" />
      {% endfor %}
      
      <!-- Rules -->
      {% for rule in rules_by_decision.get(decision.decision_id, []) %}
      <dmn:rule id="Rule_{{ rule.rule_id }}">
        <dmn:description>Confidence: {{ rule.confidence }}</dmn:description>
        <dmn:inputEntry id="InputEntry_{{ rule.rule_id }}">
          <dmn:text>{{ rule.when | e }}</dmn:text>
        </dmn:inputEntry>
        <dmn:outputEntry id="OutputEntry_{{ rule.rule_id }}">
          <dmn:text>"{{ rule.then | e }}"</dmn:text>
        </dmn:outputEntry>
      </dmn:rule>
      {% endfor %}
      
    </dmn:decisionTable>
  </dmn:decision>
  {% endfor %}
  
  <!-- Input Data Definitions -->
  {% for input_name in all_inputs %}
  <dmn:inputData id="InputData_{{ input_name | replace(' ', '_') }}" name="{{ input_name }}" />
  {% endfor %}
  
</dmn:definitions>
"""


class DMNGenerator:
    """Generate DMN XML from extracted decision data."""
    
    def __init__(self):
        self.template = Template(DMN_TEMPLATE)
    
    def generate(
        self,
        decisions: list[DMNDecision],
        rules: list[DMNRule]
    ) -> str:
        """Generate DMN XML."""
        
        # Organize rules by decision
        rules_by_decision = {}
        for rule in rules:
            if rule.decision_id not in rules_by_decision:
                rules_by_decision[rule.decision_id] = []
            rules_by_decision[rule.decision_id].append(rule)
        
        # Collect all unique input names
        all_inputs = set()
        for decision in decisions:
            all_inputs.update(decision.input_data)
        
        # Render template
        dmn_xml = self.template.render(
            decisions=decisions,
            rules_by_decision=rules_by_decision,
            all_inputs=sorted(all_inputs)
        )
        
        return dmn_xml
    
    def generate_json(
        self,
        decisions: list[DMNDecision],
        rules: list[DMNRule]
    ) -> str:
        """Generate DMN as JSON (alternative format)."""
        
        dmn_data = {
            "decisions": [],
            "rules": []
        }
        
        for decision in decisions:
            dmn_data["decisions"].append({
                "id": decision.decision_id,
                "name": decision.name,
                "description": decision.description,
                "inputs": decision.input_data,
                "outputs": decision.output_data
            })
        
        for rule in rules:
            dmn_data["rules"].append({
                "id": rule.rule_id,
                "decision_id": rule.decision_id,
                "when": rule.when,
                "then": rule.then,
                "confidence": rule.confidence
            })
        
        return json.dumps(dmn_data, indent=2, ensure_ascii=False)
    
    def save(self, content: str, output_path: str) -> str:
        """Save DMN content to file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path)




