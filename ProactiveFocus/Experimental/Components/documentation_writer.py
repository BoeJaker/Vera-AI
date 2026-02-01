# documentation_generator.py
"""Generates readable documentation for project progress."""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional


class DocumentationGenerator:
    """Generates curated prose documentation for projects."""
    
    def __init__(self, focus_manager):
        self.fm = focus_manager
        self.base_dir = Path("./Output/projects")
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def ensure_project_dir(self, project_id: str, focus: str):
        """Ensure project directory exists."""
        safe_name = self._sanitize_filename(focus)
        project_dir = self.base_dir / f"{safe_name}_{project_id}"
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (project_dir / "iterations").mkdir(exist_ok=True)
        (project_dir / "summaries").mkdir(exist_ok=True)
        (project_dir / "artifacts").mkdir(exist_ok=True)
        
        return project_dir
    
    def generate_iteration_summary(
        self,
        iteration: int,
        analysis: Dict[str, Any],
        stages: List[str],
        results: Dict[str, Any]
    ):
        """Generate readable summary for iteration."""
        if not self.fm.project_id or not self.fm.focus:
            return
        
        project_dir = self.ensure_project_dir(self.fm.project_id, self.fm.focus)
        
        # Generate prose summary
        summary = self._generate_prose_summary(iteration, analysis, stages, results)
        
        # Save iteration summary
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = project_dir / "iterations" / f"iteration_{iteration:03d}_{timestamp}.md"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(summary)
        
        # Update project README
        self._update_project_readme(project_dir, iteration, analysis)
        
        print(f"[DocGen] Saved iteration summary: {filepath}")
    
    def _generate_prose_summary(
        self,
        iteration: int,
        analysis: Dict[str, Any],
        stages: List[str],
        results: Dict[str, Any]
    ) -> str:
        """Generate readable prose summary."""
        lines = []
        
        # Header
        lines.append(f"# Iteration {iteration} - {self.fm.focus}")
        lines.append(f"\n**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Project ID**: `{self.fm.project_id}`\n")
        
        # State Overview
        lines.append("## State Overview\n")
        lines.append(analysis['summary'])
        lines.append("")
        
        stats = analysis['stats']
        lines.append("### Board Statistics\n")
        lines.append(f"- **Total Items**: {analysis['total_items']}")
        lines.append(f"- **Progress**: {stats.get('progress', 0)} items")
        lines.append(f"- **Actions**: {stats.get('actions', 0)} pending")
        lines.append(f"- **Next Steps**: {stats.get('next_steps', 0)} identified")
        lines.append(f"- **Ideas**: {stats.get('ideas', 0)} captured")
        lines.append(f"- **Issues**: {stats.get('issues', 0)} open")
        lines.append(f"- **Completed**: {stats.get('completed', 0)} items")
        lines.append("")
        
        # Stages Executed
        lines.append("## Stages Executed\n")
        for stage in stages:
            lines.append(f"- **{stage.title()}**")
            
            # Add stage results
            stage_result = results.get(stage)
            if isinstance(stage_result, list):
                lines.append(f"  - Generated {len(stage_result)} items")
                for idx, item in enumerate(stage_result[:3], 1):
                    item_text = item if isinstance(item, str) else item.get('description', str(item))
                    lines.append(f"    {idx}. {item_text[:100]}")
                if len(stage_result) > 3:
                    lines.append(f"    ... and {len(stage_result) - 3} more")
            elif isinstance(stage_result, int):
                lines.append(f"  - Executed {stage_result} actions")
            elif isinstance(stage_result, str):
                lines.append(f"  - {stage_result[:200]}")
        
        lines.append("")
        
        # Recent Progress
        progress = self.fm.board.get_category("progress")[-5:]
        if progress:
            lines.append("## Recent Progress\n")
            for item in progress:
                note = item.get("note", "") if isinstance(item, dict) else str(item)
                timestamp = item.get("timestamp", "") if isinstance(item, dict) else ""
                lines.append(f"- {note}")
                if timestamp:
                    lines.append(f"  *{timestamp}*")
            lines.append("")
        
        # Current Focus Areas
        next_steps = self.fm.board.get_category("next_steps")[:5]
        if next_steps:
            lines.append("## Current Focus Areas\n")
            for item in next_steps:
                note = item.get("note", "") if isinstance(item, dict) else str(item)
                lines.append(f"- {note}")
            lines.append("")
        
        # Outstanding Issues
        issues = self.fm.board.get_category("issues")
        if issues:
            lines.append("## Outstanding Issues\n")
            for item in issues:
                note = item.get("note", "") if isinstance(item, dict) else str(item)
                lines.append(f"- {note}")
            lines.append("")
        
        # Footer
        lines.append("---")
        lines.append(f"\n*Generated by ProactiveFocusManager on {datetime.now().isoformat()}*")
        
        return "\n".join(lines)
    
    def _update_project_readme(
        self,
        project_dir: Path,
        iteration: int,
        analysis: Dict[str, Any]
    ):
        """Update project README with latest status."""
        readme_path = project_dir / "README.md"
        
        lines = []
        
        # Header
        lines.append(f"# {self.fm.focus}")
        lines.append(f"\n**Project ID**: `{self.fm.project_id}`")
        lines.append(f"**Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Current Iteration**: {iteration}\n")
        
        # Quick Stats
        lines.append("## Quick Stats\n")
        stats = analysis['stats']
        lines.append(f"- Total Iterations: {iteration}")
        lines.append(f"- Progress Items: {stats.get('progress', 0)}")
        lines.append(f"- Completed: {stats.get('completed', 0)}")
        lines.append(f"- Pending Actions: {stats.get('actions', 0)}")
        lines.append(f"- Open Issues: {stats.get('issues', 0)}")
        lines.append("")
        
        # Current State
        lines.append("## Current State\n")
        lines.append(analysis['summary'])
        lines.append("")
        
        # Latest Progress
        progress = self.fm.board.get_category("progress")[-10:]
        if progress:
            lines.append("## Latest Progress\n")
            for item in reversed(progress):
                note = item.get("note", "") if isinstance(item, dict) else str(item)
                lines.append(f"- {note}")
            lines.append("")
        
        # Documentation Structure
        lines.append("## Documentation\n")
        lines.append("- `iterations/` - Detailed iteration summaries")
        lines.append("- `summaries/` - High-level project summaries")
        lines.append("- `artifacts/` - Generated artifacts and outputs")
        lines.append("")
        
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize string for use as filename."""
        import re
        return re.sub(r'[^\w\-_]', '_', name)[:50]