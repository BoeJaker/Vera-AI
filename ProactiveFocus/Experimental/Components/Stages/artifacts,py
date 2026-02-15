"""
Artifacts Generation Stage
===========================
Generate or refine useful artifacts (documents, diagrams, code, etc.).
"""

import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from Vera.ProactiveFocus.Experimental.Components.Stages.base import BaseStage, StageOutput


class ArtifactsStage(BaseStage):
    """Generate and refine project artifacts"""
    
    def __init__(self):
        super().__init__(
            name="Artifacts Generation",
            icon="📄",
            description="Generate and refine useful project artifacts"
        )
    
    def should_execute(self, focus_manager) -> bool:
        """Execute if we have enough context to create artifacts"""
        board_state = focus_manager.board.get_all()
        
        # Execute if:
        # - We have ideas that could be documented
        # - We have actions that need specifications
        # - Progress suggests we're ready for deliverables
        
        ideas = len(board_state.get('ideas', []))
        actions = len(board_state.get('actions', []))
        progress = len(board_state.get('progress', []))
        
        return ideas > 3 or actions > 2 or progress > 5
    
    def execute(self, focus_manager, context: Optional[Dict[str, Any]] = None) -> StageOutput:
        """Generate artifacts based on current project state"""
        output = StageOutput()
        
        self._stream_output(focus_manager, "Analyzing artifact opportunities...", "info")
        
        # Identify what artifacts would be useful
        artifact_specs = self._identify_artifacts(focus_manager)
        
        if not artifact_specs:
            self._stream_output(focus_manager, "No artifacts needed at this time", "info")
            return output
        
        self._stream_output(focus_manager, f"Identified {len(artifact_specs)} potential artifacts", "success")
        
        # Generate each artifact
        for spec in artifact_specs:
            self._stream_output(
                focus_manager,
                f"Generating {spec['type']}: {spec['title']}",
                "info"
            )
            
            artifact = self._generate_artifact(focus_manager, spec)
            
            if artifact['success']:
                output.artifacts.append(artifact)
                
                self._stream_output(
                    focus_manager,
                    f"Created: {artifact['filename']}",
                    "success"
                )
                
                # Add to focus board
                self._add_to_board(
                    focus_manager,
                    "progress",
                    f"[Artifact] Created {spec['type']}: {spec['title']}",
                    metadata=artifact
                )
                
            else:
                self._stream_output(
                    focus_manager,
                    f"Failed to create artifact: {artifact.get('error')}",
                    "error"
                )
        
        # Notify via Telegram
        if output.artifacts:
            summary = f"{self.icon} Artifacts Generated\n\n"
            for artifact in output.artifacts:
                summary += f"• {artifact['artifact_type']}: {artifact['filename']}\n"
            
            self._notify_telegram(focus_manager, summary)
        
        return output
    
    def _identify_artifacts(self, focus_manager) -> List[Dict[str, Any]]:
        """Identify what artifacts would be useful"""
        
        board_state = focus_manager.board.get_all()
        
        prompt = f"""
Project: {focus_manager.focus}

Current State:
{json.dumps(board_state, indent=2)}

Identify 1-3 artifacts that would be most valuable right now.

Artifact types to consider:
- **requirements_doc**: Requirements specification
- **design_doc**: Design document or architecture
- **task_breakdown**: Detailed task breakdown
- **progress_report**: Progress summary
- **decision_log**: Key decisions and rationale
- **code_template**: Code scaffolding or template
- **diagram**: System diagram (mermaid syntax)
- **user_guide**: User documentation
- **test_plan**: Testing strategy

Respond with JSON array:
[
  {{
    "type": "artifact_type",
    "title": "Artifact Title",
    "description": "Why this artifact is needed",
    "priority": "high|medium|low"
  }}
]

Only suggest artifacts that are genuinely useful given the current state.
"""
        
        try:
            response = self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt)
            
            specs = self._parse_json_response(response)
            
            # Validate and sort by priority
            validated = []
            for spec in specs:
                if isinstance(spec, dict) and 'type' in spec and 'title' in spec:
                    validated.append({
                        'type': spec['type'],
                        'title': spec['title'],
                        'description': spec.get('description', ''),
                        'priority': spec.get('priority', 'medium')
                    })
            
            # Sort by priority
            priority_order = {'high': 0, 'medium': 1, 'low': 2}
            validated.sort(key=lambda x: priority_order.get(x['priority'], 1))
            
            return validated[:3]  # Max 3 artifacts
            
        except Exception as e:
            self._stream_output(focus_manager, f"Failed to identify artifacts: {e}", "error")
            return []
    
    def _generate_artifact(self, focus_manager, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a specific artifact"""
        
        artifact_type = spec['type']
        title = spec['title']
        
        # Map artifact types to generators
        generators = {
            'requirements_doc': self._generate_requirements_doc,
            'design_doc': self._generate_design_doc,
            'task_breakdown': self._generate_task_breakdown,
            'progress_report': self._generate_progress_report,
            'decision_log': self._generate_decision_log,
            'code_template': self._generate_code_template,
            'diagram': self._generate_diagram,
            'user_guide': self._generate_user_guide,
            'test_plan': self._generate_test_plan
        }
        
        generator = generators.get(artifact_type, self._generate_generic_artifact)
        
        try:
            content = generator(focus_manager, spec)
            
            # Save artifact
            filename = self._generate_filename(artifact_type, title)
            
            result = self._save_artifact(
                focus_manager,
                artifact_type=artifact_type,
                content=content,
                filename=filename,
                metadata={
                    'title': title,
                    'description': spec.get('description', ''),
                    'priority': spec.get('priority', 'medium'),
                    'generated_at': datetime.utcnow().isoformat()
                }
            )
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "artifact_type": artifact_type,
                "title": title
            }
    
    def _generate_requirements_doc(self, focus_manager, spec: Dict) -> str:
        """Generate requirements document"""
        
        board_state = focus_manager.board.get_all()
        
        prompt = f"""
Project: {focus_manager.focus}

Current State:
- Ideas: {json.dumps(board_state.get('ideas', []), indent=2)}
- Issues: {json.dumps(board_state.get('issues', []), indent=2)}
- Progress: {json.dumps(board_state.get('progress', [])[-5:], indent=2)}

Create a comprehensive requirements document with:
1. Project Overview
2. Functional Requirements
3. Non-Functional Requirements
4. Constraints and Assumptions
5. Success Criteria

Write in clear, professional Markdown format.
"""
        
        return self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt)
    
    def _generate_design_doc(self, focus_manager, spec: Dict) -> str:
        """Generate design document"""
        
        board_state = focus_manager.board.get_all()
        
        prompt = f"""
Project: {focus_manager.focus}

Requirements and Context:
{json.dumps(board_state, indent=2)}

Create a technical design document with:
1. Architecture Overview
2. Component Design
3. Data Models
4. API Specifications (if applicable)
5. Technology Stack
6. Design Decisions and Rationale

Write in clear Markdown format with mermaid diagrams where helpful.
"""
        
        return self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt)
    
    def _generate_task_breakdown(self, focus_manager, spec: Dict) -> str:
        """Generate detailed task breakdown"""
        
        board_state = focus_manager.board.get_all()
        
        prompt = f"""
Project: {focus_manager.focus}

Context:
- Actions: {json.dumps(board_state.get('actions', []), indent=2)}
- Next Steps: {json.dumps(board_state.get('next_steps', []), indent=2)}

Create a detailed task breakdown with:
1. Task hierarchy (epics -> stories -> tasks)
2. Dependencies between tasks
3. Effort estimates
4. Priority ordering
5. Suggested sprint/phase grouping

Format as Markdown with clear task structure.
"""
        
        return self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt)
    
    def _generate_progress_report(self, focus_manager, spec: Dict) -> str:
        """Generate progress report"""
        
        stats = focus_manager.board.get_stats()
        board_state = focus_manager.board.get_all()
        
        prompt = f"""
Project: {focus_manager.focus}

Statistics:
{json.dumps(stats, indent=2)}

Recent Progress:
{json.dumps(board_state.get('progress', [])[-10:], indent=2)}

Create a concise progress report with:
1. Summary of Progress
2. Key Achievements
3. Current Challenges
4. Next Priorities
5. Risk Assessment

Write in clear, executive-friendly Markdown.
"""
        
        return self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt)
    
    def _generate_decision_log(self, focus_manager, spec: Dict) -> str:
        """Generate decision log"""
        
        board_state = focus_manager.board.get_all()
        
        # Extract decisions from progress and ideas
        content = f"# Decision Log - {focus_manager.focus}\n\n"
        content += f"**Generated**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        content += "## Key Decisions\n\n"
        
        # This could be enhanced to extract actual decisions from board
        for idx, progress in enumerate(board_state.get('progress', []), 1):
            if isinstance(progress, dict):
                note = progress.get('note', '')
            else:
                note = str(progress)
            
            content += f"### Decision {idx}\n"
            content += f"{note}\n\n"
        
        return content
    
    def _generate_code_template(self, focus_manager, spec: Dict) -> str:
        """Generate code template"""
        
        prompt = f"""
Project: {focus_manager.focus}
Template Type: {spec.get('description', 'Code scaffolding')}

Generate a well-structured code template with:
1. Clear file/module structure
2. Docstrings and comments
3. Type hints (if applicable)
4. Error handling patterns
5. Best practices

Include implementation notes as comments.
"""
        
        return self._stream_llm(focus_manager, focus_manager.agent.coding_llm_llm, prompt)
    
    def _generate_diagram(self, focus_manager, spec: Dict) -> str:
        """Generate mermaid diagram"""
        
        board_state = focus_manager.board.get_all()
        
        prompt = f"""
Project: {focus_manager.focus}

Context:
{json.dumps(board_state, indent=2)}

Create a mermaid diagram showing:
{spec.get('description', 'System architecture')}

Output ONLY the mermaid code block with proper syntax.
"""
        
        diagram = self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt)
        
        # Wrap in markdown code block if not already
        if not diagram.strip().startswith('```'):
            diagram = f"```mermaid\n{diagram}\n```"
        
        return f"# {spec['title']}\n\n{diagram}\n"
    
    def _generate_user_guide(self, focus_manager, spec: Dict) -> str:
        """Generate user guide"""
        
        prompt = f"""
Project: {focus_manager.focus}

Create a user-friendly guide with:
1. Getting Started
2. Key Features
3. Common Tasks
4. Troubleshooting
5. FAQ

Write for non-technical users, use clear examples.
"""
        
        return self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt)
    
    def _generate_test_plan(self, focus_manager, spec: Dict) -> str:
        """Generate test plan"""
        
        board_state = focus_manager.board.get_all()
        
        prompt = f"""
Project: {focus_manager.focus}

Requirements:
{json.dumps(board_state.get('actions', []), indent=2)}

Create a test plan with:
1. Test Strategy
2. Test Cases (unit, integration, E2E)
3. Test Data Requirements
4. Success Criteria
5. Test Schedule

Format as Markdown.
"""
        
        return self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt)
    
    def _generate_generic_artifact(self, focus_manager, spec: Dict) -> str:
        """Fallback generic artifact generator"""
        
        board_state = focus_manager.board.get_all()
        
        prompt = f"""
Project: {focus_manager.focus}

Create: {spec['title']}
Description: {spec.get('description', '')}

Context:
{json.dumps(board_state, indent=2)}

Generate a comprehensive document in Markdown format.
"""
        
        return self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt)
    
    def _generate_filename(self, artifact_type: str, title: str) -> str:
        """Generate appropriate filename for artifact"""
        
        # Clean title for filename
        import re
        clean_title = re.sub(r'[^\w\s-]', '', title.lower())
        clean_title = re.sub(r'[-\s]+', '_', clean_title)
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        # Map types to extensions
        extension_map = {
            'code_template': 'py',
            'diagram': 'md',
            'default': 'md'
        }
        
        ext = extension_map.get(artifact_type, extension_map['default'])
        
        return f"{clean_title}_{timestamp}.{ext}"
    
    def _parse_json_response(self, response: str):
        """Parse JSON response with fallbacks"""
        cleaned = response.strip()
        
        # Remove markdown fences
        if cleaned.startswith('```'):
            lines = cleaned.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            cleaned = '\n'.join(lines)
        
        try:
            return json.loads(cleaned)
        except:
            return []