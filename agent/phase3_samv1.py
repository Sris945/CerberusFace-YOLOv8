# -----------------------------------------------------------------------------
# Phase 3: AI Struct Agent - Documentation & File Generation v1.0.3
# -----------------------------------------------------------------------------
# This module implements the third phase of the AI Struct Agent, focusing on
# comprehensive project documentation, missing file generation, and smoke testing.
# v1.0.3: Implemented advanced summarization for very large projects to prevent
#         context window limit errors.
# -----------------------------------------------------------------------------

import os
import sys
import json
import subprocess
from pathlib import Path
import ast
from typing import Dict, List, Set, Tuple

# LANGCHAIN CHANGE: Import LangChain components for IBM Watsonx.ai
from langchain_ibm import WatsonxLLM

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
AGENT_VERSION = "1.0.0" # Updated version for IBM Watsonx.ai integration

# Configuration for IBM Watsonx.ai
# NOTE: It is recommended to use environment variables for security.
# Configuration for IBM Watsonx.ai - Get from environment variables
IBM_API_KEY = os.getenv("IBM_API_KEY", "jImzU56SoPzBgqpYcN6XcYmOnA1QQuB3ATeRk_81B7pm")
IBM_URL = os.getenv("IBM_URL", "https://us-south.ml.cloud.ibm.com")
IBM_PROJECT_ID = os.getenv("IBM_PROJECT_ID", "9229f6e3-2ad7-45eb-ab0e-333dc7723dfb")
MODEL_ID = "ibm/granite-3-3-8b-instruct"
if not all([IBM_API_KEY, IBM_URL, IBM_PROJECT_ID]):
    raise RuntimeError("Please set the IBM_API_KEY, IBM_URL, and IBM_PROJECT_ID.")

PHASE2_OUTPUT_ROOT = Path("./structured_project")
PHASE1_METADATA_JSON = Path("phase1_metadata.json")

# -----------------------------------------------------------------------------
# 1. AST-based Code Analysis & Dependency Graph Builder
# (This class remains unchanged)
# -----------------------------------------------------------------------------
class CodeAnalyzer:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.file_metadata = {}
        self.dependency_graph = {}
        self.entry_points = []
        self.all_classes = []
        self.all_functions = []
        
    def analyze_project(self) -> Dict:
        python_files = list(self.project_root.rglob("*.py"))
        for py_file in python_files:
            rel_path = py_file.relative_to(self.project_root).as_posix()
            metadata = self._analyze_file(py_file, rel_path)
            self.file_metadata[rel_path] = metadata
            if metadata['entry_point']:
                self.entry_points.append(rel_path)
            self.all_classes.extend(metadata['classes'])
            self.all_functions.extend(metadata['functions'])
        self._build_dependency_graph()
        return self._generate_analysis_summary()
    
    def _analyze_file(self, file_path: Path, rel_path: str) -> Dict:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            tree = ast.parse(source)
        except Exception as e:
            print(f"⚠️ Could not parse {rel_path}: {e}")
            return self._empty_metadata()
        
        imports, classes, functions = [], [], []
        docstring = ast.get_docstring(tree) or ""
        entry_point = False
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend([alias.name for alias in node.names])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
            elif isinstance(node, ast.ClassDef):
                classes.append({'name': node.name, 'docstring': ast.get_docstring(node) or "", 'methods': [n.name for n in node.body if isinstance(n, ast.FunctionDef)]})
            elif isinstance(node, ast.FunctionDef):
                functions.append({'name': node.name, 'docstring': ast.get_docstring(node) or "", 'args': [arg.arg for arg in node.args.args]})
            elif isinstance(node, ast.If) and self._is_main_guard(node):
                entry_point = True
                
        return {'imports': list(set(imports)), 'classes': classes, 'functions': functions, 'docstring': docstring, 'entry_point': entry_point, 'role': self._classify_file_role(rel_path, classes, functions, entry_point)}
    
    def _is_main_guard(self, node: ast.If) -> bool:
        try:
            return (isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__" and any(isinstance(c, ast.Constant) and c.value == "__main__" for c in node.test.comparators))
        except:
            return False
    
    def _classify_file_role(self, rel_path: str, classes: List, functions: List, entry_point: bool) -> str:
        path_lower = rel_path.lower()
        if 'test' in path_lower: return 'test'
        elif '__init__' in path_lower: return 'package_init'
        elif entry_point: return 'entry_point'
        elif 'main' in path_lower: return 'main_module'
        elif 'config' in path_lower or 'setting' in path_lower: return 'configuration'
        elif 'util' in path_lower or 'helper' in path_lower: return 'utility'
        elif classes and not functions: return 'class_definition'
        elif functions and not classes: return 'function_module'
        else: return 'mixed_module'
    
    def _build_dependency_graph(self):
        for file_path, metadata in self.file_metadata.items():
            deps = []
            for imp in metadata['imports']:
                for other_file in self.file_metadata:
                    if imp in other_file.replace('/', '.').replace('.py', ''):
                        deps.append(other_file)
            self.dependency_graph[file_path] = deps
    
    def _generate_analysis_summary(self) -> Dict:
        return {'total_files': len(self.file_metadata), 'entry_points': self.entry_points, 'total_classes': len(self.all_classes), 'total_functions': len(self.all_functions), 'file_roles': {role: [f for f, m in self.file_metadata.items() if m['role'] == role] for role in set(m['role'] for m in self.file_metadata.values())}, 'dependency_graph': self.dependency_graph, 'detailed_metadata': self.file_metadata}
    
    def _empty_metadata(self) -> Dict:
        return {'imports': [], 'classes': [], 'functions': [], 'docstring': '', 'entry_point': False, 'role': 'unknown'}

# -----------------------------------------------------------------------------
# 2. Missing File Generator
# (This class remains unchanged)
# -----------------------------------------------------------------------------
class MissingFileGenerator:
    def __init__(self, project_root: Path, analysis: Dict):
        self.project_root = project_root
        self.analysis = analysis
        
    def generate_missing_files(self):
        print("🔧 Generating missing core files...")
        self._generate_init_files()
        self._generate_main_file()
        self._generate_gitignore()
        self._generate_setup_py()
        print("✅ Missing files generated.")
        
    def _generate_init_files(self):
        for root, dirs, files in os.walk(self.project_root):
            if '__init__.py' in files or not any(f.endswith('.py') for f in files): continue
            init_path = Path(root) / '__init__.py'
            modules = [f[:-3] for f in files if f.endswith('.py') and f != '__init__.py']
            content = f'"""Package initialization for {Path(root).name}."""\n\n'
            if modules:
                content += "# Auto-generated imports\n"
                for module in modules: content += f"from .{module} import *\n"
                content += f"\n__all__ = {modules}\n"
            init_path.write_text(content, encoding='utf-8')
            print(f"Created: {init_path.relative_to(self.project_root)}")
    
    def _generate_main_file(self):
        if self.analysis['entry_points'] or (self.project_root / 'main.py').exists(): return
        content = '''"""Main application entry point."""\ndef main():\n    print("Hello from your restructured project!")\n\nif __name__ == "__main__":\n    main()\n'''
        (self.project_root / 'main.py').write_text(content, encoding='utf-8')
        print("Created: main.py")
    
    def _generate_gitignore(self):
        if (self.project_root / '.gitignore').exists(): return
        content = '''# Python\n__pycache__/\n*.py[cod]\n*$py.class\n*.so\n.Python\nbuild/\ndevelop-eggs/\ndist/\ndownloads/\neggs/\n.eggs/\nlib/\nlib64/\nparts/\nsdist/\nvar/\nwheels/\npip-wheel-metadata/\nshare/python-wheels/\n*.egg-info/\n.installed.cfg\n*.egg\n# Virtual environments\nvenv/\nenv/\nENV/\n# IDE\n.vscode/\n.idea/\n*.swp\n*.swo\n# OS\n.DS_Store\nThumbs.db\n# Logs\n*.log\n'''
        (self.project_root / '.gitignore').write_text(content, encoding='utf-8')
        print("Created: .gitignore")
    
    def _generate_setup_py(self):
        if (self.project_root / 'setup.py').exists(): return
        project_name = self.project_root.name
        content = f'''"""Setup script for {project_name}."""\n\nfrom setuptools import setup, find_packages\n\nsetup(\n    name="{project_name}",\n    version="1.0.0",\n    packages=find_packages(),\n    install_requires=[],\n)\n'''
        (self.project_root / 'setup.py').write_text(content, encoding='utf-8')
        print("Created: setup.py")

# -----------------------------------------------------------------------------
# 3. AI-Powered Documentation Agent
# -----------------------------------------------------------------------------
class DocumentationAgent:
    def __init__(self, project_root: Path, analysis: Dict, phase1_metadata: Dict):
        self.project_root = project_root
        self.analysis = analysis
        self.phase1_metadata = phase1_metadata

    # ==================== UPDATED METHOD TO FIX THE ERROR ====================
    def _create_prompt_context(self) -> Dict:
        """
        Creates a highly summarized version of the analysis for the LLM prompt
        to avoid exceeding the token limit, even for large projects.
        """
        analysis = self.analysis

        # 1. Basic project stats (low token cost)
        prompt_context = {
            'total_files': analysis.get('total_files'),
            'total_classes': analysis.get('total_classes'),
            'total_functions': analysis.get('total_functions'),
            'entry_points': analysis.get('entry_points', [])
        }

        # 2. Summarize file roles by COUNTING files per role
        if 'file_roles' in analysis:
            prompt_context['file_role_counts'] = {
                role: len(files) for role, files in analysis['file_roles'].items()
            }

        # 3. Create an ADVANCED summary of the dependency graph
        if 'dependency_graph' in analysis and analysis['dependency_graph']:
            graph = analysis['dependency_graph']
            
            # Calculate dependencies (outgoing) and dependents (incoming)
            dependencies = {file: len(deps) for file, deps in graph.items()}
            dependents = {file: 0 for file in graph.keys()}
            for deps_list in graph.values():
                for dep in deps_list:
                    if dep in dependents:
                        dependents[dep] += 1
            
            # Get top 5 most complex files (many outgoing dependencies)
            most_complex = sorted(dependencies.items(), key=lambda item: item[1], reverse=True)
            
            # Get top 5 most important/central files (many incoming dependencies)
            most_important = sorted(dependents.items(), key=lambda item: item[1], reverse=True)

            prompt_context['dependency_summary'] = {
                'total_internal_imports': sum(len(v) for v in graph.values()),
                'top_5_most_complex_files': [item[0] for item in most_complex[:5]],
                'top_5_most_important_files': [item[0] for item in most_important[:5]]
            }

        return prompt_context
    # =====================================================================
        
    def generate_documentation(self):
        print("📝 Generating professional README and documentation...")
        readme_content = self._generate_readme()
        self._write_readme(readme_content)
        workflow_content = self._generate_workflow_doc()
        self._write_workflow_doc(workflow_content)
        print("✅ Documentation generated.")
    
    def _generate_readme(self) -> str:
        prompt_context = self._create_prompt_context()
        prompt = f"""
Generate a professional, comprehensive README.md for this Python project.

**Project Analysis Summary:**
{json.dumps(prompt_context, indent=2)}

**User Context:**
- Persona: {self.phase1_metadata.get('persona', 'Developer')}
- Pain Points: {self.phase1_metadata.get('pain_points', {})}
- Use Cases: {self.phase1_metadata.get('use_cases', [])}

Create a README that includes:
1. Project title and description
2. Features and capabilities (inferred from the analysis summary)
3. Installation instructions
4. Usage examples (based on entry points found)
5. Project structure overview (based on file role counts and dependency summary)
6. Contributing guidelines
7. License information

Make it professional and clear. Output only the README content in Markdown format.
"""
        try:
            parameters = {"decoding_method": "greedy", "max_new_tokens": 2048, "min_new_tokens": 200, "temperature": 0.65}
            llm = WatsonxLLM(model_id=MODEL_ID, url=IBM_URL, apikey=IBM_API_KEY, project_id=IBM_PROJECT_ID, params=parameters)
            return llm.invoke(prompt).strip()
        except Exception as e:
            print(f"❌ AI README generation failed: {e}")
            return self._fallback_readme()
    
    def _generate_workflow_doc(self) -> str:
        prompt_context = self._create_prompt_context()
        prompt = f"""
Create a detailed PROJECT_WORKFLOW.md document explaining how this Python project works based on the provided analysis summary.

**Project Analysis Summary:**
{json.dumps(prompt_context, indent=2)}

Include:
1. Project architecture overview (infer from dependencies and file roles)
2. File organization and responsibilities (based on 'file_role_counts')
3. Key Modules (describe the roles of the 'top_5_most_important_files')
4. Entry points and how to run the project
5. Development workflow suggestions
6. Testing approach suggestions

Make it technical but accessible. Output only the workflow document in Markdown format.
"""
        try:
            parameters = {"decoding_method": "greedy", "max_new_tokens": 2048, "min_new_tokens": 200, "temperature": 0.65}
            llm = WatsonxLLM(model_id=MODEL_ID, url=IBM_URL, apikey=IBM_API_KEY, project_id=IBM_PROJECT_ID, params=parameters)
            return llm.invoke(prompt).strip()
        except Exception as e:
            print(f"❌ Workflow generation failed: {e}")
            return self._fallback_workflow()
    
    def _fallback_readme(self) -> str:
        project_name = self.project_root.name
        return f'''# {project_name}\n\n## Description\nAI documentation failed. This is a fallback README.\n\n## Usage\nRun the main entry point: `python {self.analysis.get('entry_points', ['main.py'])[0]}`\n'''
    
    def _fallback_workflow(self) -> str:
        return f'''# Project Workflow\n\nAI workflow generation failed.\n\n## Entry Points\n{chr(10).join(f"- `{ep}`" for ep in self.analysis['entry_points']) or "- `main.py` (assumed)"}\n'''
    
    def _write_readme(self, content: str):
        (self.project_root / 'README.md').write_text(content, encoding='utf-8')
        print(f"Created: README.md")
    
    def _write_workflow_doc(self, content: str):
        (self.project_root / 'PROJECT_WORKFLOW.md').write_text(content, encoding='utf-8')
        print(f"Created: PROJECT_WORKFLOW.md")

# -----------------------------------------------------------------------------
# 4. Smoke Test Suite & 5. Main Execution
# (These sections remain unchanged)
# -----------------------------------------------------------------------------
class SmokeTestSuite:
    def __init__(self, project_root: Path, analysis: Dict):
        self.project_root = project_root
        self.analysis = analysis
        
    def run_smoke_tests(self) -> Tuple[bool, List[str]]:
        print("🧪 Running smoke tests...")
        issues = []
        issues.extend(self._test_import_syntax())
        issues.extend(self._test_entry_points())
        issues.extend(self._test_required_files())
        success = len(issues) == 0
        print(f"{'✅' if success else '⚠️'} Smoke tests {'passed' if success else 'completed with issues'}")
        return success, issues
    
    def _test_import_syntax(self) -> List[str]:
        issues = []
        for py_file in self.project_root.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f: ast.parse(f.read())
            except SyntaxError as e:
                issues.append(f"Syntax error in {py_file.relative_to(self.project_root)}: {e}")
        return issues
    
    def _test_entry_points(self) -> List[str]:
        issues = []
        entry_points = self.analysis['entry_points'] or (['main.py'] if (self.project_root / 'main.py').exists() else [])
        for entry_point in entry_points:
            try:
                result = subprocess.run([sys.executable, str(self.project_root / entry_point)], capture_output=True, text=True, timeout=10, cwd=self.project_root)
                if result.returncode != 0: issues.append(f"Entry point {entry_point} failed. Stderr: {result.stderr.strip()}")
            except Exception as e:
                issues.append(f"Could not execute {entry_point}: {e}")
        return issues
    
    def _test_required_files(self) -> List[str]:
        issues = []
        for req_file in ['README.md']:
            if not (self.project_root / req_file).exists(): issues.append(f"Missing required file: {req_file}")
        return issues

def execute_phase3() -> bool:
    print(f"🚀 AI Structure Agent Phase 3: Documentation & File Generation v{AGENT_VERSION}")
    if not PHASE2_OUTPUT_ROOT.exists():
        print(f"❌ Phase 2 output not found at {PHASE2_OUTPUT_ROOT}. Please run Phase 2 first.")
        return False
    
    phase1_metadata = {}
    if PHASE1_METADATA_JSON.exists():
        try:
            phase1_metadata = json.loads(PHASE1_METADATA_JSON.read_text(encoding="utf-8")).get("metadata", {})
        except Exception as e:
            print(f"⚠️ Could not load Phase 1 metadata: {e}")
    
    print(f"📁 Analyzing structured project at: {PHASE2_OUTPUT_ROOT}")
    analyzer = CodeAnalyzer(PHASE2_OUTPUT_ROOT)
    analysis = analyzer.analyze_project()
    print(f"📊 Analysis complete: {analysis['total_files']} files, {analysis['total_classes']} classes, {analysis['total_functions']} functions.")
    
    file_generator = MissingFileGenerator(PHASE2_OUTPUT_ROOT, analysis)
    file_generator.generate_missing_files()
    
    doc_agent = DocumentationAgent(PHASE2_OUTPUT_ROOT, analysis, phase1_metadata)
    doc_agent.generate_documentation()
    
    test_suite = SmokeTestSuite(PHASE2_OUTPUT_ROOT, analysis)
    success, issues = test_suite.run_smoke_tests()
    
    if issues:
        print("\n⚠️ Issues detected during smoke tests:")
        for issue in issues: print(f"   - {issue}")
    
    print(f"\n✅ Phase 3 complete!")
    print(f"📁 Enhanced project available at: {PHASE2_OUTPUT_ROOT.resolve()}")
    return True

def main():
    if not execute_phase3(): sys.exit(1)

if __name__ == "__main__":
    main()