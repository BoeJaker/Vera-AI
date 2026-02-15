"""
Proactive Focus Stages
=======================
Modular stage system for proactive focus management.

Each stage is responsible for a specific type of proactive thinking:
- Ideas: Generate creative ideas
- Questions: Ask clarifying questions via Telegram
- Next Steps: Determine actionable steps
- Actions: Generate executable actions
- Execution: Execute actions via toolchain
- Artifacts: Generate project artifacts
- Review: Analyze project state
"""

from .base import BaseStage, StageOutput
from .ideas import IdeasStage
from .questions import QuestionsStage
from .next_steps import NextStepsStage
from .actions import ActionsStage
from .artifacts import ArtifactsStage


class StageRegistry:
    """
    Central registry for all available stages.
    
    Allows dynamic stage registration and discovery.
    """
    
    def __init__(self):
        self.stages = {}
        self._register_default_stages()
    
    def _register_default_stages(self):
        """Register all default stages"""
        self.register(IdeasStage())
        self.register(QuestionsStage())
        self.register(NextStepsStage())
        self.register(ActionsStage())
        self.register(ArtifactsStage())
    
    def register(self, stage: BaseStage):
        """Register a stage"""
        self.stages[stage.name] = stage
    
    def get(self, name: str) -> BaseStage:
        """Get stage by name"""
        return self.stages.get(name)
    
    def list_all(self):
        """List all registered stages"""
        return list(self.stages.values())
    
    def execute_stage(self, name: str, focus_manager, context=None):
        """Execute a specific stage"""
        stage = self.get(name)
        if not stage:
            raise ValueError(f"Stage '{name}' not found")
        
        if not stage.should_execute(focus_manager):
            return None
        
        return stage.execute(focus_manager, context)


# Global registry instance
_registry = StageRegistry()


def get_stage(name: str) -> BaseStage:
    """Get a stage by name"""
    return _registry.get(name)


def list_stages():
    """List all available stages"""
    return _registry.list_all()


def execute_stage(name: str, focus_manager, context=None):
    """Execute a specific stage"""
    return _registry.execute_stage(name, focus_manager, context)


def register_custom_stage(stage: BaseStage):
    """Register a custom stage"""
    _registry.register(stage)


__all__ = [
    'BaseStage',
    'StageOutput',
    'IdeasStage',
    'QuestionsStage',
    'NextStepsStage',
    'ActionsStage',
    'ArtifactsStage',
    'StageRegistry',
    'get_stage',
    'list_stages',
    'execute_stage',
    'register_custom_stage'
]