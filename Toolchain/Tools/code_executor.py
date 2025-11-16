"""
Ad-Hoc Code Writing and Execution System
Enables LLM to write, execute, test, and manage code dynamically
Supports any programming language and use case
"""

import os
import sys
import subprocess
import tempfile
import json
import ast
import traceback
from typing import List, Dict, Any, Optional, Literal
from pathlib import Path
from pydantic import BaseModel, Field
import docker
from datetime import datetime

# ============================================================================
# INPUT SCHEMAS
# ============================================================================

class CodeGenerateInput(BaseModel):
    """Input schema for generating code."""
    task: str = Field(..., description="What the code should accomplish")
    language: str = Field(
        default="python",
        description="Programming language (python, javascript, bash, go, rust, etc.)"
    )
    style: Literal["script", "function", "class", "module", "full_project"] = Field(
        default="script",
        description="Code style/structure"
    )
    include_tests: bool = Field(
        default=False,
        description="Generate unit tests"
    )
    include_docs: bool = Field(
        default=True,
        description="Include documentation/comments"
    )
    constraints: Optional[str] = Field(
        default=None,
        description="Constraints or requirements"
    )


class CodeExecuteInput(BaseModel):
    """Input schema for executing code."""
    code: Optional[str] = Field(
        default=None,
        description="Code to execute (or use code_file)"
    )
    code_file: Optional[str] = Field(
        default=None,
        description="Path to code file to execute"
    )
    language: str = Field(
        default="python",
        description="Programming language"
    )
    args: Optional[List[str]] = Field(
        default=None,
        description="Command line arguments"
    )
    stdin: Optional[str] = Field(
        default=None,
        description="Standard input for the program"
    )
    timeout: int = Field(
        default=30,
        description="Execution timeout in seconds"
    )
    sandbox: bool = Field(
        default=True,
        description="Execute in sandboxed Docker container"
    )


class TemplateCreateInput(BaseModel):
    """Input schema for creating templates."""
    template_name: str = Field(..., description="Name for the template")
    description: str = Field(..., description="What this template does")
    language: str = Field(..., description="Programming language")
    template_code: str = Field(..., description="Template code with placeholders")
    placeholders: Dict[str, str] = Field(
        default_factory=dict,
        description="Placeholder descriptions {name: description}"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Tags for categorization"
    )


class TemplateUseInput(BaseModel):
    """Input schema for using templates."""
    template_name: str = Field(..., description="Template to use")
    values: Dict[str, str] = Field(
        ...,
        description="Values for template placeholders"
    )
    save_as: Optional[str] = Field(
        default=None,
        description="Save generated code to file"
    )


class CodeRefactorInput(BaseModel):
    """Input schema for code refactoring."""
    code: str = Field(..., description="Code to refactor")
    language: str = Field(default="python", description="Programming language")
    refactor_goal: str = Field(
        ...,
        description="What to improve (e.g., 'optimize performance', 'improve readability')"
    )


class CodeDebugInput(BaseModel):
    """Input schema for debugging code."""
    code: str = Field(..., description="Code with bugs")
    language: str = Field(default="python", description="Programming language")
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if available"
    )
    expected_behavior: Optional[str] = Field(
        default=None,
        description="What the code should do"
    )


class ProjectScaffoldInput(BaseModel):
    """Input schema for project scaffolding."""
    project_name: str = Field(..., description="Project name")
    project_type: str = Field(
        ...,
        description="Type of project (e.g., 'python-package', 'web-app', 'api-service')"
    )
    language: str = Field(default="python", description="Primary language")
    features: Optional[List[str]] = Field(
        default=None,
        description="Features to include (e.g., 'testing', 'docker', 'ci-cd')"
    )


# ============================================================================
# CODE EXECUTION ENGINES
# ============================================================================

class CodeExecutor:
    """Executes code in various languages with sandboxing support."""
    
    def __init__(self):
        self.docker_available = self._check_docker()
        
        # Language execution commands
        self.executors = {
            "python": ["python3", "-u"],
            "python2": ["python2", "-u"],
            "javascript": ["node"],
            "typescript": ["ts-node"],
            "bash": ["bash"],
            "sh": ["sh"],
            "ruby": ["ruby"],
            "perl": ["perl"],
            "php": ["php"],
            "go": ["go", "run"],
            "rust": ["rustc", "--edition", "2021"],  # Compiles then runs
            "c": ["gcc", "-x", "c", "-o", "/tmp/prog", "-", "&&", "/tmp/prog"],
            "cpp": ["g++", "-x", "c++", "-o", "/tmp/prog", "-", "&&", "/tmp/prog"],
            "java": None,  # Special handling
            "r": ["Rscript"],
            "lua": ["lua"],
            "swift": ["swift"],
        }
    
    def _check_docker(self) -> bool:
        """Check if Docker is available."""
        try:
            docker.from_env()
            return True
        except:
            return False
    
    def execute_local(self, code: str, language: str, args: List[str] = None,
                     stdin: str = None, timeout: int = 30) -> Dict[str, Any]:
        """Execute code locally (NOT sandboxed)."""
        
        if language not in self.executors:
            return {
                "success": False,
                "error": f"Unsupported language: {language}",
                "stdout": "",
                "stderr": ""
            }
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix=self._get_extension(language), 
                                        delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            cmd = self.executors[language].copy()
            
            # Special handling for compiled languages
            if language in ["rust", "c", "cpp"]:
                if language == "rust":
                    # Compile
                    compile_cmd = ["rustc", temp_file, "-o", temp_file + ".out"]
                    result = subprocess.run(compile_cmd, capture_output=True, 
                                          text=True, timeout=timeout)
                    if result.returncode != 0:
                        return {
                            "success": False,
                            "error": "Compilation failed",
                            "stdout": result.stdout,
                            "stderr": result.stderr
                        }
                    cmd = [temp_file + ".out"]
                else:
                    cmd.append(temp_file)
            else:
                cmd.append(temp_file)
            
            # Add arguments
            if args:
                cmd.extend(args)
            
            # Execute
            result = subprocess.run(
                cmd,
                input=stdin,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Execution timeout ({timeout}s)",
                "stdout": "",
                "stderr": ""
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": traceback.format_exc()
            }
        finally:
            # Cleanup
            try:
                os.unlink(temp_file)
                if language == "rust":
                    os.unlink(temp_file + ".out")
            except:
                pass
    
    def execute_sandboxed(self, code: str, language: str, args: List[str] = None,
                         stdin: str = None, timeout: int = 30) -> Dict[str, Any]:
        """Execute code in Docker sandbox."""
        
        if not self.docker_available:
            return {
                "success": False,
                "error": "Docker not available",
                "stdout": "",
                "stderr": ""
            }
        
        # Language to Docker image mapping
        images = {
            "python": "python:3.11-slim",
            "javascript": "node:18-alpine",
            "ruby": "ruby:3.2-alpine",
            "go": "golang:1.21-alpine",
            "rust": "rust:1.75-alpine",
        }
        
        image = images.get(language, "python:3.11-slim")
        
        try:
            client = docker.from_env()
            
            # Create temporary file for code
            with tempfile.NamedTemporaryFile(mode='w', suffix=self._get_extension(language),
                                            delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            # Run in container
            container = client.containers.run(
                image,
                command=self._get_docker_command(language, "/code/script" + self._get_extension(language)),
                volumes={temp_file: {'bind': '/code/script' + self._get_extension(language), 'mode': 'ro'}},
                remove=True,
                detach=False,
                stdout=True,
                stderr=True,
                mem_limit="256m",
                cpu_quota=50000,  # 50% CPU
                network_disabled=True,
                timeout=timeout
            )
            
            output = container.decode('utf-8')
            
            return {
                "success": True,
                "stdout": output,
                "stderr": "",
                "returncode": 0
            }
            
        except docker.errors.ContainerError as e:
            return {
                "success": False,
                "error": "Container execution failed",
                "stdout": e.stdout.decode('utf-8') if e.stdout else "",
                "stderr": e.stderr.decode('utf-8') if e.stderr else ""
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": traceback.format_exc()
            }
        finally:
            try:
                os.unlink(temp_file)
            except:
                pass
    
    def _get_extension(self, language: str) -> str:
        """Get file extension for language."""
        extensions = {
            "python": ".py",
            "javascript": ".js",
            "typescript": ".ts",
            "bash": ".sh",
            "ruby": ".rb",
            "go": ".go",
            "rust": ".rs",
            "c": ".c",
            "cpp": ".cpp",
            "java": ".java",
        }
        return extensions.get(language, ".txt")
    
    def _get_docker_command(self, language: str, filepath: str) -> str:
        """Get Docker execution command."""
        commands = {
            "python": f"python {filepath}",
            "javascript": f"node {filepath}",
            "ruby": f"ruby {filepath}",
            "go": f"go run {filepath}",
            "rust": f"rustc {filepath} -o /tmp/prog && /tmp/prog",
        }
        return commands.get(language, f"python {filepath}")


# ============================================================================
# TEMPLATE MANAGER
# ============================================================================

class CodeTemplateManager:
    """Manages code templates for reuse."""
    
    def __init__(self, templates_dir: str = "./code_templates"):
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(exist_ok=True)
        
        self.templates_file = self.templates_dir / "templates.json"
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict:
        """Load templates from file."""
        if self.templates_file.exists():
            return json.loads(self.templates_file.read_text())
        return {}
    
    def _save_templates(self):
        """Save templates to file."""
        self.templates_file.write_text(json.dumps(self.templates, indent=2))
    
    def create_template(self, name: str, description: str, language: str,
                       code: str, placeholders: Dict[str, str],
                       tags: List[str] = None) -> bool:
        """Create a new template."""
        self.templates[name] = {
            "description": description,
            "language": language,
            "code": code,
            "placeholders": placeholders,
            "tags": tags or [],
            "created_at": datetime.now().isoformat()
        }
        
        self._save_templates()
        return True
    
    def get_template(self, name: str) -> Optional[Dict]:
        """Get a template by name."""
        return self.templates.get(name)
    
    def list_templates(self, language: str = None, tags: List[str] = None) -> List[Dict]:
        """List templates with optional filtering."""
        results = []
        
        for name, template in self.templates.items():
            # Filter by language
            if language and template["language"] != language:
                continue
            
            # Filter by tags
            if tags and not any(tag in template.get("tags", []) for tag in tags):
                continue
            
            results.append({
                "name": name,
                **template
            })
        
        return results
    
    def use_template(self, name: str, values: Dict[str, str]) -> Optional[str]:
        """Use a template by filling in placeholders."""
        template = self.get_template(name)
        
        if not template:
            return None
        
        code = template["code"]
        
        # Replace placeholders
        for placeholder, value in values.items():
            code = code.replace(f"{{{{{placeholder}}}}}", value)
        
        return code
    
    def delete_template(self, name: str) -> bool:
        """Delete a template."""
        if name in self.templates:
            del self.templates[name]
            self._save_templates()
            return True
        return False


# ============================================================================
# AD-HOC CODE TOOLS
# ============================================================================

class AdHocCodeTools:
    """Tools for ad-hoc code writing and execution."""
    
    def __init__(self, agent):
        self.agent = agent
        self.executor = CodeExecutor()
        self.template_manager = CodeTemplateManager()
    
    def generate_code(self, task: str, language: str = "python",
                     style: str = "script", include_tests: bool = False,
                     include_docs: bool = True, constraints: str = None) -> str:
        """
        Generate code for any task in any language.
        
        The LLM writes complete, production-ready code based on your description.
        
        Args:
            task: What the code should do
            language: Programming language
            style: Code structure (script, function, class, module, full_project)
            include_tests: Generate unit tests
            include_docs: Include documentation
            constraints: Special requirements or constraints
        
        Examples:
            "Parse CSV file and generate summary statistics"
            "Create REST API endpoint for user authentication"
            "Implement binary search tree with insert, delete, search"
            "Web scraper that extracts product prices from Amazon"
            "Discord bot that responds to commands"
        
        Returns generated code with explanations.
        """
        
        prompt = f"""
Generate complete, production-ready {language} code for this task:

Task: {task}

Style: {style}
Include Tests: {include_tests}
Include Documentation: {include_docs}
Constraints: {constraints or "None"}

Requirements:
1. Write clean, idiomatic {language} code
2. Include error handling
3. Add helpful comments
4. Follow best practices for {language}
5. Make code immediately usable
{"6. Include unit tests" if include_tests else ""}
{"7. Add comprehensive docstrings/documentation" if include_docs else ""}

Please provide:
1. Main code
{"2. Test code (separate section)" if include_tests else ""}
{f"{3 if include_tests else 2}. Brief explanation of how it works"}
{f"{4 if include_tests else 3}. Usage examples"}

Format:
CODE:
```{language}
[your code here]
```

{"TESTS:" if include_tests else ""}
{"```" + language if include_tests else ""}
{"[test code here]" if include_tests else ""}
{"```" if include_tests else ""}

EXPLANATION:
[how it works]

USAGE:
[usage examples]
"""
        
        # Generate with LLM
        response = self.agent.deep_llm.invoke(prompt)
        
        # Parse response
        code_start = response.find("CODE:") + 5
        tests_marker = "TESTS:" if include_tests else "EXPLANATION:"
        tests_start = response.find(tests_marker)
        
        code_section = response[code_start:tests_start].strip()
        
        # Extract code from markdown blocks
        import re
        code_match = re.search(r'```\w*\n(.*?)```', code_section, re.DOTALL)
        if code_match:
            code = code_match.group(1).strip()
        else:
            code = code_section.strip()
        
        # Save to file
        timestamp = int(time.time())
        filename = f"generated_{language}_{timestamp}{self.executor._get_extension(language)}"
        filepath = Path("./generated_code") / filename
        filepath.parent.mkdir(exist_ok=True)
        filepath.write_text(code)
        
        # Store in memory
        self.agent.mem.add_session_memory(
            self.agent.sess.id,
            task,
            "code_generated",
            metadata={
                "language": language,
                "filepath": str(filepath),
                "style": style
            }
        )
        
        output = [
            f"✓ Generated {language} code: {filename}",
            f"Task: {task}",
            f"Style: {style}",
            f"Saved to: {filepath}",
            "",
            "=" * 60,
            "CODE:",
            "=" * 60,
            code,
            "",
            "=" * 60,
            "FULL RESPONSE:",
            "=" * 60,
            response
        ]
        
        return "\n".join(output)
    
    def execute_code(self, code: str = None, code_file: str = None,
                    language: str = "python", args: List[str] = None,
                    stdin: str = None, timeout: int = 30,
                    sandbox: bool = True) -> str:
        """
        Execute code and return results.
        
        Can execute code directly or from a file.
        Supports sandboxed execution for safety.
        
        Args:
            code: Code to execute (or use code_file)
            code_file: Path to code file
            language: Programming language
            args: Command line arguments
            stdin: Standard input
            timeout: Execution timeout
            sandbox: Run in Docker sandbox (safer)
        
        Examples:
            execute_code(code="print('Hello')", language="python")
            execute_code(code_file="script.py", args=["--verbose"])
        
        Returns stdout, stderr, and exit status.
        """
        
        # Get code
        if code_file:
            code = Path(code_file).read_text()
        
        if not code:
            return "[Error] No code provided"
        
        # Execute
        if sandbox and self.executor.docker_available:
            result = self.executor.execute_sandboxed(
                code, language, args, stdin, timeout
            )
        else:
            if sandbox:
                print("[Warning] Docker not available, executing locally without sandbox")
            result = self.executor.execute_local(
                code, language, args, stdin, timeout
            )
        
        # Format output
        output = [
            "Execution Results:",
            "=" * 60,
            f"Language: {language}",
            f"Success: {'✓' if result['success'] else '✗'}",
            ""
        ]
        
        if result.get("stdout"):
            output.extend([
                "STDOUT:",
                "-" * 60,
                result["stdout"],
                ""
            ])
        
        if result.get("stderr"):
            output.extend([
                "STDERR:",
                "-" * 60,
                result["stderr"],
                ""
            ])
        
        if result.get("error"):
            output.extend([
                "ERROR:",
                "-" * 60,
                result["error"],
                ""
            ])
        
        output.append("=" * 60)
        
        return "\n".join(output)
    
    def create_template(self, template_name: str, description: str,
                       language: str, template_code: str,
                       placeholders: Dict[str, str],
                       tags: List[str] = None) -> str:
        """
        Create a reusable code template.
        
        Templates use {{PLACEHOLDER}} syntax for values that change.
        
        Args:
            template_name: Unique name for template
            description: What this template does
            language: Programming language
            template_code: Code with {{PLACEHOLDERS}}
            placeholders: Description of each placeholder
            tags: Tags for organization
        
        Example:
            create_template(
                template_name="api_endpoint",
                description="Flask API endpoint template",
                language="python",
                template_code='''
@app.route('/{{ENDPOINT_PATH}}', methods=['{{HTTP_METHOD}}'])
def {{FUNCTION_NAME}}():
    # {{DESCRIPTION}}
    return jsonify({"status": "ok"})
''',
                placeholders={
                    "ENDPOINT_PATH": "API endpoint path",
                    "HTTP_METHOD": "HTTP method (GET, POST, etc.)",
                    "FUNCTION_NAME": "Function name",
                    "DESCRIPTION": "What this endpoint does"
                },
                tags=["api", "flask", "web"]
            )
        
        Templates can be reused with different values using use_template.
        """
        
        success = self.template_manager.create_template(
            template_name, description, language,
            template_code, placeholders, tags
        )
        
        if success:
            output = [
                f"✓ Created template: {template_name}",
                f"Language: {language}",
                f"Description: {description}",
                "",
                "Placeholders:"
            ]
            
            for name, desc in placeholders.items():
                output.append(f"  {{{{{{name}}}}}}: {desc}")
            
            if tags:
                output.append(f"\nTags: {', '.join(tags)}")
            
            output.append(f"\nUse with: use_template('{template_name}', values={{...}})")
            
            return "\n".join(output)
        
        return "[Error] Failed to create template"
    
    def use_template(self, template_name: str, values: Dict[str, str],
                    save_as: str = None) -> str:
        """
        Use a template by filling in placeholder values.
        
        Args:
            template_name: Name of template to use
            values: Values for each placeholder
            save_as: Optional filename to save generated code
        
        Example:
            use_template(
                template_name="api_endpoint",
                values={
                    "ENDPOINT_PATH": "/api/users",
                    "HTTP_METHOD": "GET",
                    "FUNCTION_NAME": "get_users",
                    "DESCRIPTION": "Retrieve list of users"
                },
                save_as="users_endpoint.py"
            )
        
        Returns generated code.
        """
        
        code = self.template_manager.use_template(template_name, values)
        
        if not code:
            return f"[Error] Template '{template_name}' not found"
        
        # Save if requested
        if save_as:
            filepath = Path("./generated_code") / save_as
            filepath.parent.mkdir(exist_ok=True)
            filepath.write_text(code)
            
            output = [
                f"✓ Generated code from template: {template_name}",
                f"Saved to: {filepath}",
                "",
                "=" * 60,
                code,
                "=" * 60
            ]
        else:
            output = [
                f"✓ Generated code from template: {template_name}",
                "",
                "=" * 60,
                code,
                "=" * 60
            ]
        
        return "\n".join(output)
    
    def list_templates(self, language: str = None, tags: List[str] = None) -> str:
        """
        List available templates.
        
        Args:
            language: Filter by programming language
            tags: Filter by tags
        
        Shows all templates with descriptions and usage info.
        """
        
        templates = self.template_manager.list_templates(language, tags)
        
        if not templates:
            filter_desc = []
            if language:
                filter_desc.append(f"language={language}")
            if tags:
                filter_desc.append(f"tags={tags}")
            filter_str = " (" + ", ".join(filter_desc) + ")" if filter_desc else ""
            return f"No templates found{filter_str}"
        
        output = [f"Available Templates ({len(templates)}):\n"]
        
        for template in templates:
            output.append(f"📝 {template['name']}")
            output.append(f"   Language: {template['language']}")
            output.append(f"   Description: {template['description']}")
            
            if template.get('placeholders'):
                output.append(f"   Placeholders: {', '.join(template['placeholders'].keys())}")
            
            if template.get('tags'):
                output.append(f"   Tags: {', '.join(template['tags'])}")
            
            output.append("")
        
        return "\n".join(output)
    
    def refactor_code(self, code: str, language: str = "python",
                     refactor_goal: str = "") -> str:
        """
        Refactor code to improve it.
        
        The LLM analyzes code and rewrites it to be better.
        
        Args:
            code: Code to refactor
            language: Programming language
            refactor_goal: What to improve (performance, readability, etc.)
        
        Examples of refactor goals:
            "Optimize for performance"
            "Improve readability and add comments"
            "Convert to use async/await"
            "Add error handling"
            "Follow PEP 8 style guide"
            "Remove code duplication"
        
        Returns refactored code with explanation of changes.
        """
        
        prompt = f"""
Refactor this {language} code to {refactor_goal}:

ORIGINAL CODE:
```{language}
{code}
```

Please provide:
1. Refactored code
2. Explanation of changes made
3. Why these changes improve the code

Format:
REFACTORED CODE:
```{language}
[refactored code]
```

CHANGES:
[explanation of what was changed]

IMPROVEMENTS:
[why these changes make the code better]
"""
        
        response = self.agent.deep_llm.invoke(prompt)
        
        # Parse response
        import re
        code_match = re.search(r'```\w*\n(.*?)```', response, re.DOTALL)
        if code_match:
            refactored = code_match.group(1).strip()
        else:
            refactored = response
        
        output = [
            f"✓ Refactored {language} code",
            f"Goal: {refactor_goal}",
            "",
            "=" * 60,
            "FULL RESPONSE:",
            "=" * 60,
            response
        ]
        
        return "\n".join(output)
    
    def debug_code(self, code: str, language: str = "python",
                  error_message: str = None, expected_behavior: str = None) -> str:
        """
        Debug code and fix issues.
        
        The LLM analyzes buggy code and provides fixes.
        
        Args:
            code: Code with bugs
            language: Programming language
            error_message: Error message if available
            expected_behavior: What the code should do
        
        Example:
            debug_code(
                code="def divide(a, b): return a/b",
                error_message="ZeroDivisionError: division by zero",
                expected_behavior="Handle division by zero gracefully"
            )
        
        Returns fixed code with explanation.
        """
        
        prompt = f"""
Debug and fix this {language} code:

CODE WITH BUGS:
```{language}
{code}
```

{"Error Message: " + error_message if error_message else ""}
{"Expected Behavior: " + expected_behavior if expected_behavior else ""}

Please provide:
1. Fixed code
2. Explanation of the bug
3. Why your fix works

Format:
FIXED CODE:
```{language}
[fixed code]
```

BUG EXPLANATION:
[what was wrong]

FIX EXPLANATION:
[how the fix works]
"""
        
        response = self.agent.deep_llm.invoke(prompt)
        
        output = [
            f"✓ Debugged {language} code",
            "",
            "=" * 60,
            "DEBUG RESULTS:",
            "=" * 60,
            response
        ]
        
        return "\n".join(output)
    
    def scaffold_project(self, project_name: str, project_type: str,
                        language: str = "python",
                        features: List[str] = None) -> str:
        """
        Generate complete project structure.
        
        Creates directories, files, configs for a new project.
        
        Args:
            project_name: Name of the project
            project_type: Type (python-package, web-app, api-service, cli-tool, etc.)
            language: Primary language
            features: Additional features (testing, docker, ci-cd, linting)
        
        Example:
            scaffold_project(
                project_name="my_awesome_api",
                project_type="api-service",
                language="python",
                features=["testing", "docker", "ci-cd"]
            )
        
        Generates complete project with:
        - Directory structure
        - Configuration files
        - Example code
        - Documentation
        - Tests (if requested)
        - CI/CD (if requested)
        """
        
        prompt = f"""
Generate a complete project structure for:

Project Name: {project_name}
Type: {project_type}
Language: {language}
Features: {', '.join(features) if features else 'None'}

Create a professional project structure with:
1. Directory layout
2. Configuration files (package.json, requirements.txt, Dockerfile, etc.)
3. Example source files
4. README with setup instructions
5. Tests (if testing feature requested)
6. CI/CD config (if ci-cd feature requested)

Provide the complete file structure and contents.

Format:
PROJECT STRUCTURE:
[directory tree]

FILES:
--- path/to/file1 ---
[file contents]

--- path/to/file2 ---
[file contents]

[etc.]

SETUP INSTRUCTIONS:
[how to set up and run the project]
"""
        
        response = self.agent.deep_llm.invoke(prompt)
        
        # Parse and create files
        project_dir = Path("./projects") / project_name
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Parse file sections
        import re
        file_pattern = r'--- (.*?) ---\n(.*?)(?=\n--- |$)'
        files = re.findall(file_pattern, response, re.DOTALL)
        
        created_files = []
        for filepath, content in files:
            filepath = filepath.strip()
            file_path = project_dir / filepath
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content.strip())
            created_files.append(filepath)
        
        output = [
            f"✓ Scaffolded project: {project_name}",
            f"Type: {project_type}",
            f"Location: {project_dir}",
            f"Files created: {len(created_files)}",
            "",
            "Created files:",
        ]
        
        for f in created_files:
            output.append(f"  - {f}")
        
        output.extend([
            "",
            "=" * 60,
            "PROJECT DETAILS:",
            "=" * 60,
            response
        ])
        
        return "\n".join(output)


# ============================================================================
# ADD TO TOOLLOADER FUNCTION
# ============================================================================

def add_adhoc_code_tools(tool_list: List, agent):
    """
    Add ad-hoc code writing and execution tools.
    
    Enables LLM to:
    - Write code in any language for any task
    - Execute code safely (sandboxed)
    - Create and use reusable templates
    - Refactor and optimize code
    - Debug and fix code
    - Generate complete project structures
    
    The LLM can now write code dynamically for any purpose!
    
    Requirements:
    - docker (optional, for sandboxed execution): docker.io
    
    Call in ToolLoader:
        add_adhoc_code_tools(tool_list, agent)
    """
    
    adhoc_tools = AdHocCodeTools(agent)
    
    tool_list.extend([
        StructuredTool.from_function(
            func=adhoc_tools.generate_code,
            name="generate_code",
            description=(
                "Generate code for ANY task in ANY language. "
                "LLM writes complete, production-ready code based on description. "
                "Supports scripts, functions, classes, full modules. "
                "Example: 'Parse CSV and generate statistics in Python'"
            ),
            args_schema=CodeGenerateInput
        ),
        
        StructuredTool.from_function(
            func=adhoc_tools.execute_code,
            name="execute_code",
            description=(
                "Execute code and get results. "
                "Runs code in sandbox (Docker) or locally. "
                "Returns stdout, stderr, exit status. "
                "Use to test generated code or run scripts."
            ),
            args_schema=CodeExecuteInput
        ),
        
        StructuredTool.from_function(
            func=adhoc_tools.create_template,
            name="create_code_template",
            description=(
                "Create reusable code template with placeholders. "
                "Templates use {{PLACEHOLDER}} syntax. "
                "Save patterns for repeated use. "
                "Example: API endpoint template, test template, etc."
            ),
            args_schema=TemplateCreateInput
        ),
        
        StructuredTool.from_function(
            func=adhoc_tools.use_template,
            name="use_code_template",
            description=(
                "Generate code from template by filling placeholders. "
                "Quick way to create code from saved patterns. "
                "Optionally save generated code to file."
            ),
            args_schema=TemplateUseInput
        ),
        
        StructuredTool.from_function(
            func=adhoc_tools.list_templates,
            name="list_code_templates",
            description=(
                "List available code templates. "
                "Filter by language or tags. "
                "Shows what templates are available for reuse."
            ),
            args_schema=FileHistoryQueryInput
        ),
        
        StructuredTool.from_function(
            func=adhoc_tools.refactor_code,
            name="refactor_code",
            description=(
                "Refactor code to improve it. "
                "LLM analyzes and rewrites code for performance, readability, etc. "
                "Examples: 'optimize performance', 'improve readability', 'add error handling'"
            ),
            args_schema=CodeRefactorInput
        ),
        
        StructuredTool.from_function(
            func=adhoc_tools.debug_code,
            name="debug_code",
            description=(
                "Debug code and fix bugs. "
                "LLM analyzes buggy code and provides fixes. "
                "Provide error message and expected behavior for best results."
            ),
            args_schema=CodeDebugInput
        ),
        
        StructuredTool.from_function(
            func=adhoc_tools.scaffold_project,
            name="scaffold_project",
            description=(
                "Generate complete project structure. "
                "Creates directories, configs, example code, tests, CI/CD. "
                "Professional project setup in seconds. "
                "Types: python-package, web-app, api-service, cli-tool, etc."
            ),
            args_schema=ProjectScaffoldInput
        ),
    ])
    
    return tool_list