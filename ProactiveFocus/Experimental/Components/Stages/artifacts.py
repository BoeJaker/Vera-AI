"""
Artifacts Generation Stage - ENHANCED
======================================
Generate artifacts with workspace awareness.

ENHANCED: Analyzes project structure to generate relevant artifacts like
documentation for undocumented code, READMEs, diagrams from actual structure.
"""

import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from Vera.ProactiveFocus.Experimental.Components.Stages.base import BaseStage, StageOutput
from Vera.Toolchain.sandbox import get_project_sandbox


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
        
        ideas = len(board_state.get('ideas', []))
        actions = len(board_state.get('actions', []))
        progress = len(board_state.get('progress', []))
        
        return ideas > 3 or actions > 2 or progress > 5
    
    def execute(self, focus_manager, context: Optional[Dict[str, Any]] = None) -> StageOutput:
        """Generate artifacts based on workspace analysis"""
        output = StageOutput()
        
        self._stream_output(focus_manager, "Analyzing project structure for artifacts...", "info")
        
        # Get project context
        project_context = self._get_project_context(focus_manager)
        
        # Identify what artifacts would be useful
        artifact_specs = self._identify_artifacts(focus_manager, project_context)
        
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
            
            artifact = self._generate_artifact(focus_manager, spec, project_context)
            
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
    
    def _get_project_context(self, focus_manager) -> Dict[str, Any]:
        """Get project workspace context"""
        sandbox = get_project_sandbox(focus_manager)
        
        if not sandbox:
            return {"available": False}
        
        try:
            from Vera.ProactiveFocus.Experimental.Components.project_context_analyzer import ProjectContextAnalyzer
            
            project_root = Path(sandbox.project_root)
            analyzer = ProjectContextAnalyzer(project_root)
            
            context = analyzer.get_full_context(
                include_file_tree=True,
                include_recent_changes=True,
                include_todos=False,  # Don't need TODOs for artifacts
                include_stats=True,
                max_files_to_scan=150
            )
            
            context["available"] = True
            context["analyzer"] = analyzer  # Keep for later use
            return context
            
        except Exception as e:
            self._stream_output(
                focus_manager,
                f"⚠️  Could not analyze workspace: {e}",
                "warning"
            )
            return {"available": False, "error": str(e)}
    
    def _identify_artifacts(
        self,
        focus_manager,
        project_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Identify what artifacts would be useful based on workspace"""
        
        board_state = focus_manager.board.get_all()
        
        # Build workspace summary for LLM
        workspace_summary = []
        
        if project_context.get("available"):
            stats = project_context.get("statistics", {})
            
            workspace_summary.append(f"Project Statistics:")
            workspace_summary.append(f"- Total Files: {stats.get('total_files', 0)}")
            workspace_summary.append(f"- Code Files: {stats.get('code_files', 0)}")
            workspace_summary.append(f"- Documentation Files: {stats.get('doc_files', 0)}")
            
            # File type breakdown
            file_types = stats.get('file_types', {})
            if file_types:
                workspace_summary.append(f"\nFile Types:")
                sorted_types = sorted(file_types.items(), key=lambda x: x[1], reverse=True)
                for ext, count in sorted_types[:5]:
                    workspace_summary.append(f"  - {ext or 'no extension'}: {count}")
            
            # Directory structure
            if "file_tree" in project_context:
                tree = project_context["file_tree"]
                if "children" in tree:
                    dirs = [c['name'] for c in tree['children'] if c.get('type') == 'directory']
                    if dirs:
                        workspace_summary.append(f"\nTop-level Directories:")
                        for d in dirs[:10]:
                            workspace_summary.append(f"  - {d}/")
            
            # Gap analysis
            gaps = []
            
            # Missing README
            has_readme = any(
                'readme' in str(f).lower() 
                for f in project_context.get("file_tree", {}).get("children", [])
            )
            if not has_readme:
                gaps.append("- No README.md in project root")
            
            # Under-documented
            if stats.get('code_files', 0) > 5 and stats.get('doc_files', 0) < 2:
                gaps.append(f"- Only {stats.get('doc_files', 0)} documentation files for {stats.get('code_files', 0)} code files")
            
            # Missing architecture docs
            has_arch_doc = any(
                'architecture' in str(f).lower() or 'design' in str(f).lower()
                for f in project_context.get("file_tree", {}).get("children", [])
            )
            if stats.get('code_files', 0) > 10 and not has_arch_doc:
                gaps.append("- No architecture/design documentation found")
            
            if gaps:
                workspace_summary.append(f"\nDocumentation Gaps:")
                workspace_summary.extend(gaps)
        
        prompt = f"""
Project: {focus_manager.focus}

Workspace Analysis:
{chr(10).join(workspace_summary)}

Current Board State:
{json.dumps(board_state, indent=2)}

Identify 1-3 artifacts that would be most valuable right now based on the workspace analysis.

Artifact types to consider:
- **readme**: README.md for project root or subdirectories
- **architecture_doc**: System architecture documentation
- **api_docs**: API documentation for code modules
- **contributing_guide**: Contributing guidelines
- **changelog**: CHANGELOG.md documenting project evolution
- **code_overview**: Overview of codebase structure
- **setup_guide**: Setup/installation instructions
- **architecture_diagram**: Visual system diagram (mermaid)
- **module_docs**: Documentation for specific modules/packages

Prioritize artifacts that:
1. Fill identified gaps (missing README, architecture docs, etc.)
2. Document existing but undocumented code
3. Help new contributors understand the project
4. Capture current project structure and design decisions

Respond with JSON array:
[
  {{
    "type": "artifact_type",
    "title": "Artifact Title",
    "description": "Why this artifact is needed",
    "priority": "high|medium|low",
    "target_location": "path/where/to/create/file.md"
  }}
]

Only suggest artifacts that are genuinely useful given the workspace state.
"""
        
        try:
            response = self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt, operation="identify_artifacts")
            
            specs = self._parse_json_response(response)
            
            # Validate and sort by priority
            validated = []
            for spec in specs:
                if isinstance(spec, dict) and 'type' in spec and 'title' in spec:
                    validated.append({
                        'type': spec['type'],
                        'title': spec['title'],
                        'description': spec.get('description', ''),
                        'priority': spec.get('priority', 'medium'),
                        'target_location': spec.get('target_location', '')
                    })
            
            # Sort by priority
            priority_order = {'high': 0, 'medium': 1, 'low': 2}
            validated.sort(key=lambda x: priority_order.get(x['priority'], 1))
            
            return validated[:3]  # Max 3 artifacts
            
        except Exception as e:
            self._stream_output(focus_manager, f"Failed to identify artifacts: {e}", "error")
            return []
    
    def _generate_artifact(
        self,
        focus_manager,
        spec: Dict[str, Any],
        project_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a specific artifact with workspace context"""
        
        artifact_type = spec['type']
        title = spec['title']
        
        # Map artifact types to generators
        generators = {
            'readme': self._generate_readme,
            'architecture_doc': self._generate_architecture_doc,
            'api_docs': self._generate_api_docs,
            'contributing_guide': self._generate_contributing_guide,
            'changelog': self._generate_changelog,
            'code_overview': self._generate_code_overview,
            'setup_guide': self._generate_setup_guide,
            'architecture_diagram': self._generate_architecture_diagram,
            'module_docs': self._generate_module_docs,
            
            # Fallback to base generators
            'requirements_doc': self._generate_requirements_doc,
            'design_doc': self._generate_design_doc,
            'task_breakdown': self._generate_task_breakdown,
            'progress_report': self._generate_progress_report,
        }
        
        generator = generators.get(artifact_type, self._generate_generic_artifact)
        
        try:
            content = generator(focus_manager, spec, project_context)
            
            # Determine filename
            if spec.get('target_location'):
                filename = spec['target_location']
            else:
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
    
    def _generate_readme(
        self,
        focus_manager,
        spec: Dict,
        project_context: Dict[str, Any]
    ) -> str:
        """Generate README.md based on actual project structure"""
        
        stats = project_context.get("statistics", {})
        file_tree = project_context.get("file_tree", {})
        
        # Extract directory structure
        directories = []
        if "children" in file_tree:
            directories = [
                c['name'] for c in file_tree['children'] 
                if c.get('type') == 'directory'
            ]
        
        prompt = f"""
Project: {focus_manager.focus}

Project Structure:
- Total Files: {stats.get('total_files', 0)}
- Code Files: {stats.get('code_files', 0)}
- Documentation Files: {stats.get('doc_files', 0)}

Top-level Directories:
{chr(10).join(f'- {d}/' for d in directories[:10])}

File Types Present:
{json.dumps(dict(sorted(stats.get('file_types', {}).items(), key=lambda x: x[1], reverse=True)[:8]), indent=2)}

Create a comprehensive README.md with:
1. Project Title and Description
2. Features (infer from project structure)
3. Installation Instructions (appropriate for detected languages/tools)
4. Usage Examples
5. Project Structure (describe the directories)
6. Contributing Guidelines
7. License Information

Base the content on the actual project structure. Be specific about the directories and file types present.
Write in clear, professional Markdown format.
"""
        
        return self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt, operation="generate_readme")
    
    def _generate_architecture_doc(
        self,
        focus_manager,
        spec: Dict,
        project_context: Dict[str, Any]
    ) -> str:
        """Generate architecture documentation from actual structure"""
        
        stats = project_context.get("statistics", {})
        file_tree = project_context.get("file_tree", {})
        
        # Build component list from directory structure
        components = []
        if "children" in file_tree:
            for child in file_tree['children']:
                if child.get('type') == 'directory':
                    name = child['name']
                    # Count files in directory
                    file_count = len([
                        c for c in child.get('children', []) 
                        if c.get('type') == 'file'
                    ])
                    components.append(f"- {name}/ ({file_count} files)")
        
        prompt = f"""
Project: {focus_manager.focus}

Project Components:
{chr(10).join(components) if components else "Single-directory structure"}

File Statistics:
- Total Files: {stats.get('total_files', 0)}
- Code Files: {stats.get('code_files', 0)}
- Languages: {', '.join(k for k in stats.get('file_types', {}).keys() if k in ['.py', '.js', '.ts', '.rs', '.go', '.java'])}

Create an architecture document with:
1. System Overview
2. Component Architecture (based on directory structure above)
3. Data Flow
4. Technology Stack (infer from file types)
5. Design Decisions and Rationale
6. Future Considerations

Include a mermaid diagram showing component relationships.
Base the architecture on the actual project structure shown above.
"""
        
        return self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt, operation="generate_architecture_doc")
    
    def _generate_api_docs(
        self,
        focus_manager,
        spec: Dict,
        project_context: Dict[str, Any]
    ) -> str:
        """Generate API documentation by analyzing code files"""
        
        # Try to read sample code files to understand API
        analyzer = project_context.get("analyzer")
        api_info = []
        
        if analyzer:
            # Search for API-related files
            api_files = analyzer.search_files(r'(api|router|endpoint|controller)', max_results=5)
            
            if api_files:
                api_info.append("Detected API Files:")
                for file in api_files:
                    api_info.append(f"- {file['path']}")
                    
                    # Try to read content
                    content = analyzer.get_file_content(file['path'], max_lines=50)
                    if content and content != "[Binary file]":
                        api_info.append(f"\nSample from {file['path']}:")
                        api_info.append(content[:500])
        
        prompt = f"""
Project: {focus_manager.focus}

{chr(10).join(api_info) if api_info else "Generate generic API documentation template"}

Create API documentation with:
1. API Overview
2. Authentication (if applicable)
3. Endpoints (infer from files or create template)
4. Request/Response Examples
5. Error Handling
6. Rate Limiting (if applicable)

Format as clear, professional Markdown.
"""
        
        return self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt, operation="generate_api_docs")
    
    def _generate_contributing_guide(
        self,
        focus_manager,
        spec: Dict,
        project_context: Dict[str, Any]
    ) -> str:
        """Generate contributing guidelines based on project"""
        
        stats = project_context.get("statistics", {})
        git_status = project_context.get("git_status")
        
        prompt = f"""
Project: {focus_manager.focus}

Project Type: {self._infer_project_type(stats)}
{"Current Branch: " + git_status.get('branch') if git_status else ""}

Create a CONTRIBUTING.md with:
1. Getting Started
2. Development Setup
3. Code Style Guidelines (appropriate for project languages)
4. Testing Requirements
5. Pull Request Process
6. Code Review Guidelines
7. Community Guidelines

Make it specific to this type of project.
"""
        
        return self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt, operation="generate_contributing_guide")
    
    def _generate_changelog(
        self,
        focus_manager,
        spec: Dict,
        project_context: Dict[str, Any]
    ) -> str:
        """Generate CHANGELOG from recent progress"""
        
        board = focus_manager.board.get_all()
        progress = board.get('progress', [])
        
        content = f"# Changelog - {focus_manager.focus}\n\n"
        content += "All notable changes to this project will be documented in this file.\n\n"
        content += f"## [Unreleased]\n\n"
        content += "### Added\n\n"
        
        for item in progress[-20:]:
            note = item.get('note', '') if isinstance(item, dict) else str(item)
            if note and not note.startswith('['):
                content += f"- {note}\n"
        
        return content
    
    def _generate_code_overview(
        self,
        focus_manager,
        spec: Dict,
        project_context: Dict[str, Any]
    ) -> str:
        """Generate code structure overview"""
        
        file_tree = project_context.get("file_tree", {})
        stats = project_context.get("statistics", {})
        
        prompt = f"""
Project: {focus_manager.focus}

Directory Structure:
{json.dumps(file_tree, indent=2)[:1000]}

Statistics:
{json.dumps(stats, indent=2)}

Create a CODE_OVERVIEW.md documenting:
1. Project Structure (explain the directory layout)
2. Key Components (main modules/packages)
3. Entry Points
4. Code Organization Principles
5. Important Files

Be specific about the actual structure shown above.
"""
        
        return self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt, operation="generate_code_overview")
    
    def _generate_setup_guide(
        self,
        focus_manager,
        spec: Dict,
        project_context: Dict[str, Any]
    ) -> str:
        """Generate setup instructions based on project type"""
        
        stats = project_context.get("statistics", {})
        project_type = self._infer_project_type(stats)
        
        prompt = f"""
Project: {focus_manager.focus}
Type: {project_type}

Create detailed SETUP.md with:
1. Prerequisites (tools, languages, dependencies)
2. Installation Steps (specific to {project_type})
3. Configuration
4. Verification (how to test setup worked)
5. Troubleshooting Common Issues

Make it beginner-friendly and specific to {project_type} projects.
"""
        
        return self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt, operation="generate_setup_guide")
    
    def _generate_architecture_diagram(
        self,
        focus_manager,
        spec: Dict,
        project_context: Dict[str, Any]
    ) -> str:
        """Generate mermaid diagram from actual structure"""
        
        file_tree = project_context.get("file_tree", {})
        
        # Extract components from directory structure
        components = []
        if "children" in file_tree:
            components = [
                c['name'] for c in file_tree['children'] 
                if c.get('type') == 'directory'
            ][:8]  # Limit to avoid overwhelming diagram
        
        prompt = f"""
Project: {focus_manager.focus}

Components (from directory structure):
{chr(10).join(f'- {c}' for c in components)}

Create a mermaid diagram showing:
{spec.get('description', 'Component relationships and data flow')}

Use the actual component names from above.
Output ONLY the mermaid code block with proper syntax.
"""
        
        diagram = self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt, operation="generate_architecture_diagram")
        
        # Wrap in markdown code block if not already
        if not diagram.strip().startswith('```'):
            diagram = f"```mermaid\n{diagram}\n```"
        
        return f"# {spec['title']}\n\n{diagram}\n"
    
    def _generate_module_docs(
        self,
        focus_manager,
        spec: Dict,
        project_context: Dict[str, Any]
    ) -> str:
        """Generate documentation for specific module"""
        
        analyzer = project_context.get("analyzer")
        module_name = spec.get('target_location', '').split('/')[0]
        
        prompt = f"""
Project: {focus_manager.focus}
Module: {module_name}

Create module documentation with:
1. Module Purpose
2. Public API
3. Usage Examples
4. Dependencies
5. Internal Components

Format as Markdown.
"""
        
        return self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt, operation="generate_module_docs")
    
    def _infer_project_type(self, stats: Dict[str, Any]) -> str:
        """Infer project type from file statistics"""
        file_types = stats.get('file_types', {})
        
        if '.py' in file_types:
            return 'Python'
        elif '.js' in file_types or '.jsx' in file_types:
            return 'JavaScript/Node.js'
        elif '.ts' in file_types or '.tsx' in file_types:
            return 'TypeScript'
        elif '.rs' in file_types:
            return 'Rust'
        elif '.go' in file_types:
            return 'Go'
        elif '.java' in file_types:
            return 'Java'
        else:
            return 'Mixed/Generic'
    
    # Base generators (for backward compatibility)
    def _generate_requirements_doc(self, focus_manager, spec: Dict, project_context: Dict) -> str:
        board_state = focus_manager.board.get_all()
        prompt = f"""
Project: {focus_manager.focus}
Context: {json.dumps(board_state, indent=2)[:500]}

Create a requirements document with functional and non-functional requirements.
"""
        return self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt, operation="generate_requirements_doc")
    
    def _generate_design_doc(self, focus_manager, spec: Dict, project_context: Dict) -> str:
        board_state = focus_manager.board.get_all()
        prompt = f"""
Project: {focus_manager.focus}
Context: {json.dumps(board_state, indent=2)[:500]}

Create a technical design document.
"""
        return self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt, operation="generate_design_doc")
    
    def _generate_task_breakdown(self, focus_manager, spec: Dict, project_context: Dict) -> str:
        board_state = focus_manager.board.get_all()
        prompt = f"""
Project: {focus_manager.focus}
Context: {json.dumps(board_state, indent=2)[:500]}

Create a detailed task breakdown.
"""
        return self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt, operation="generate_task_breakdown")
    
    def _generate_progress_report(self, focus_manager, spec: Dict, project_context: Dict) -> str:
        stats = focus_manager.board.get_stats()
        prompt = f"""
Project: {focus_manager.focus}
Stats: {json.dumps(stats, indent=2)}

Create a progress report.
"""
        return self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt, operation="generate_progress_report")
    
    def _generate_generic_artifact(self, focus_manager, spec: Dict, project_context: Dict) -> str:
        board_state = focus_manager.board.get_all()
        prompt = f"""
Project: {focus_manager.focus}
Create: {spec['title']}
Description: {spec.get('description', '')}

Generate comprehensive document in Markdown.
"""
        return self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt, operation=f"generate_{spec['type']}")
    
    def _generate_filename(self, artifact_type: str, title: str) -> str:
        """Generate appropriate filename for artifact"""
        import re
        clean_title = re.sub(r'[^\w\s-]', '', title.lower())
        clean_title = re.sub(r'[-\s]+', '_', clean_title)
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        extension_map = {
            'readme': 'md',
            'architecture_doc': 'md',
            'architecture_diagram': 'md',
            'default': 'md'
        }
        
        ext = extension_map.get(artifact_type, extension_map['default'])
        
        return f"{clean_title}_{timestamp}.{ext}"
    
    def _parse_json_response(self, response: str):
        """Parse JSON response with fallbacks"""
        cleaned = response.strip()
        
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