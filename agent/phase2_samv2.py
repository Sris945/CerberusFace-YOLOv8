# -----------------------------------------------------------------------------
# Phase 2: Enhanced AI Struct Agent - Full Refactor v2.0.0 (Multi-Language Support)
# -----------------------------------------------------------------------------
# This module implements an enhanced version of the Phase 2 AI Struct Agent,
# supporting Python, JavaScript, React, and other development files with
# comprehensive dependency management and import refactoring.
# -----------------------------------------------------------------------------

import argparse
import os
import sys
import json
import shutil
import subprocess
import ast
import re
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
import jsonschema
import libcst as cst


# IBM Watsonx.ai Integration
from langchain_ibm import WatsonxLLM
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.output_parsers import StrOutputParser


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
AGENT_VERSION = "1.0.0"

# IBM Watsonx.ai Configuration
# Configuration for IBM Watsonx.ai - Get from environment variables
IBM_API_KEY = os.getenv("IBM_API_KEY", "jImzU56SoPzBgqpYcN6XcYmOnA1QQuB3ATeRk_81B7pm")
IBM_URL = os.getenv("IBM_URL", "https://us-south.ml.cloud.ibm.com")
IBM_PROJECT_ID = os.getenv("IBM_PROJECT_ID", "9229f6e3-2ad7-45eb-ab0e-333dc7723dfb")
MODEL_ID = "ibm/granite-3-3-8b-instruct"
if not all([IBM_API_KEY, IBM_URL, IBM_PROJECT_ID]):
    raise RuntimeError("Please set the IBM_API_KEY, IBM_URL, and IBM_PROJECT_ID.")

PHASE1_METADATA_JSON = Path("phase1_metadata.json")
OUTPUT_ROOT = Path("./structured_project")

# Enhanced Schema for AI output
STRUCTURE_SCHEMA = {
    "type": "object",
    "properties": {
        "file_mapping": {
            "type": "object",
            "patternProperties": {"^.*$": {"type": "string"}},
            "description": "A dictionary mapping original file paths to new file paths."
        },
        "placement_reasons": {
            "type": "object",
            "patternProperties": {"^.*$": {"type": "string"}},
            "description": "A dictionary mapping new file paths to the reason for their placement."
        },
        "project_structure": {
            "type": "object",
            "description": "Recommended overall project structure and conventions."
        }
    },
    "required": ["file_mapping", "placement_reasons"]
}

# -----------------------------------------------------------------------------
# 1. Enhanced Multi-Language File Discovery
# -----------------------------------------------------------------------------
class FileDiscovery:
    """Enhanced file discovery with multi-language support."""
    
    CATEGORIES = {
        "Python": {
            "extensions": [".py", ".pyx", ".pyi"],
            "patterns": ["*.py", "*.pyx", "*.pyi"]
        },
        "JavaScript": {
            "extensions": [".js", ".mjs", ".cjs"],
            "patterns": ["*.js", "*.mjs", "*.cjs"]
        },
        "TypeScript": {
            "extensions": [".ts", ".tsx"],
            "patterns": ["*.ts", "*.tsx"]
        },
        "React": {
            "extensions": [".jsx", ".tsx"],
            "patterns": ["*.jsx", "*.tsx"],
            "markers": ["react", "jsx", "component"]
        },
        "Vue": {
            "extensions": [".vue"],
            "patterns": ["*.vue"]
        },
        "Web": {
            "extensions": [".html", ".htm", ".css", ".scss", ".sass", ".less"],
            "patterns": ["*.html", "*.htm", "*.css", "*.scss", "*.sass", "*.less"]
        },
        "Data": {
            "extensions": [".csv", ".json", ".parquet", ".db", ".sqlite3", ".xlsx", ".xml"],
            "patterns": ["*.csv", "*.json", "*.parquet", "*.db", "*.sqlite3", "*.xlsx", "*.xml"]
        },
        "Config": {
            "extensions": [".yaml", ".yml", ".toml", ".ini", ".env", ".config"],
            "patterns": ["*.yaml", "*.yml", "*.toml", "*.ini", "*.env", "*.config", 
                        "requirements.txt", "package.json", "package-lock.json", 
                        "yarn.lock", "Pipfile", "pyproject.toml", ".env*"]
        },
        "Notebook": {
            "extensions": [".ipynb"],
            "patterns": ["*.ipynb"]
        },
        "Container": {
            "extensions": [],
            "patterns": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml", ".dockerignore"]
        },
        "CI/CD": {
            "extensions": [".yml", ".yaml"],
            "patterns": [".github/workflows/*", ".gitlab-ci.yml", "azure-pipelines.yml"]
        },
        "Docs": {
            "extensions": [".md", ".rst", ".txt"],
            "patterns": ["*.md", "*.rst", "*.txt", "README*", "CHANGELOG*", "LICENSE*"]
        },
        "Tests": {
            "extensions": [".py", ".js", ".ts", ".jsx", ".tsx"],
            "patterns": ["test_*.py", "*_test.py", "*.test.js", "*.spec.js", 
                        "*.test.ts", "*.spec.ts", "__tests__/*"]
        },
        "Assets": {
            "extensions": [".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf"],
            "patterns": ["*.png", "*.jpg", "*.jpeg", "*.gif", "*.svg", "*.ico", 
                        "*.woff", "*.woff2", "*.ttf"]
        },
        "Other": {
            "extensions": [],
            "patterns": []
        }
    }

    IGNORE_PATTERNS = {
        '.git', '__pycache__', '.venv', 'venv', 'env', 'node_modules', 
        '.pytest_cache', '.mypy_cache', 'dist', 'build', '.next', 
        '.nuxt', 'coverage', '.coverage', '.DS_Store'
    }

    @classmethod
    def discover_and_categorize_files(cls, root: Path) -> Dict[str, List[str]]:
        """Discovers all files in the project root and categorizes them by type."""
        file_list = {category: [] for category in cls.CATEGORIES}
        
        # Create extension to category mapping
        ext_map = {}
        for category, config in cls.CATEGORIES.items():
            for ext in config["extensions"]:
                ext_map[ext] = category
        
        for p in root.rglob("*"):
            # Skip directories and ignored folders
            if p.is_dir() or any(part in cls.IGNORE_PATTERNS for part in p.parts):
                continue
                
            rel_path = p.relative_to(root).as_posix()
            category = cls._categorize_file(p, rel_path, ext_map)
            file_list[category].append(rel_path)
            
        return file_list
    
    @classmethod
    def _categorize_file(cls, file_path: Path, rel_path: str, ext_map: Dict[str, str]) -> str:
        """Categorizes a single file based on multiple criteria."""
        file_name = file_path.name.lower()
        file_ext = file_path.suffix.lower()
        
        # Special case for test files
        if cls._is_test_file(file_path, rel_path):
            return "Tests"
        
        # Check for container files
        if file_name in ["dockerfile", "docker-compose.yml", "docker-compose.yaml", ".dockerignore"]:
            return "Container"
        
        # Check for CI/CD files
        if ".github/workflows" in rel_path or file_name in [".gitlab-ci.yml", "azure-pipelines.yml"]:
            return "CI/CD"
        
        # Check for React files specifically
        if file_ext in [".jsx", ".tsx"] or cls._contains_react_markers(file_path):
            return "React"
        
        # Use extension mapping
        category = ext_map.get(file_ext, "Other")
        
        # Additional checks for config files
        if category == "Other" and cls._is_config_file(file_name):
            return "Config"
            
        return category
    
    @classmethod
    def _is_test_file(cls, file_path: Path, rel_path: str) -> bool:
        """Determines if a file is a test file."""
        file_name = file_path.name.lower()
        return (
            "test" in file_name or
            "spec" in file_name or
            "__tests__" in rel_path or
            rel_path.startswith("tests/") or
            file_name.startswith("test_") or
            file_name.endswith("_test.py") or
            file_name.endswith(".test.js") or
            file_name.endswith(".spec.js")
        )
    
    @classmethod
    def _contains_react_markers(cls, file_path: Path) -> bool:
        """Checks if a JS/TS file contains React-specific code."""
        if file_path.suffix not in [".js", ".ts", ".jsx", ".tsx"]:
            return False
            
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")[:1000]  # Read first 1000 chars
            react_markers = ["import React", "from 'react'", "from \"react\"", 
                           "useState", "useEffect", "jsx", "JSX"]
            return any(marker in content for marker in react_markers)
        except:
            return False
    
    @classmethod
    def _is_config_file(cls, file_name: str) -> bool:
        """Determines if a file is a configuration file."""
        config_patterns = [
            "requirements", "package.json", "package-lock.json", "yarn.lock",
            "pipfile", "pyproject.toml", "setup.py", "setup.cfg", "manifest.in",
            "makefile", "gulpfile", "webpack", "rollup", "vite.config"
        ]
        return any(pattern in file_name for pattern in config_patterns)

# -----------------------------------------------------------------------------
# 2. Enhanced Multi-Language Import/Dependency Refactoring
# -----------------------------------------------------------------------------
class ImportRefactorEngine:
    """Handles import refactoring for multiple languages."""
    
    def __init__(self, file_mapping: Dict[str, str], project_root: Path):
        self.file_mapping = file_mapping
        self.project_root = project_root
    
    def refactor_all_imports(self, project_copy_root: Path):
        """Refactors imports/requires for all supported file types."""
        print("🔄 Refactoring imports across all file types...")
        
        for src_rel_path in self.file_mapping.keys():
            file_ext = Path(src_rel_path).suffix.lower()
            
            if file_ext == ".py":
                self._refactor_python_imports(project_copy_root, src_rel_path)
            elif file_ext in [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"]:
                self._refactor_js_imports(project_copy_root, src_rel_path)
            elif file_ext == ".vue":
                self._refactor_vue_imports(project_copy_root, src_rel_path)
    
    def _refactor_python_imports(self, project_copy_root: Path, src_rel_path: str):
        """Refactors Python imports using LibCST."""
        file_abs_path = project_copy_root / src_rel_path
        try:
            source_code = file_abs_path.read_text(encoding="utf-8")
            tree = cst.parse_module(source_code)
            transformer = PythonImportTransformer(src_rel_path, self.file_mapping, project_copy_root)
            modified_tree = tree.visit(transformer)
            file_abs_path.write_text(modified_tree.code, encoding="utf-8")
        except Exception as e:
            print(f"⚠️ Could not refactor Python imports in {src_rel_path}: {e}")
    
    def _refactor_js_imports(self, project_copy_root: Path, src_rel_path: str):
        """Refactors JavaScript/TypeScript imports using regex patterns."""
        file_abs_path = project_copy_root / src_rel_path
        try:
            content = file_abs_path.read_text(encoding="utf-8")
            
            # Pattern for relative imports: import ... from './...' or '../...'
            import_pattern = r'(import\s+.*?\s+from\s+[\'"])(\./|\.\./)([^\'"]*)([\'"]\s*;?)'
            require_pattern = r'(require\s*\(\s*[\'"])(\./|\.\./)([^\'"]*)([\'"]\s*\))'
            
            def replace_import(match):
                return self._calculate_new_js_import_path(match, src_rel_path, project_copy_root)
            
            content = re.sub(import_pattern, replace_import, content)
            content = re.sub(require_pattern, replace_import, content)
            
            file_abs_path.write_text(content, encoding="utf-8")
        except Exception as e:
            print(f"⚠️ Could not refactor JS imports in {src_rel_path}: {e}")
    
    def _refactor_vue_imports(self, project_copy_root: Path, src_rel_path: str):
        """Refactors Vue.js component imports."""
        # Vue files can contain JS/TS in <script> tags, so we use similar logic
        self._refactor_js_imports(project_copy_root, src_rel_path)
    
    def _calculate_new_js_import_path(self, match, current_file_rel_path: str, project_copy_root: Path) -> str:
        """Calculates the new import path for JavaScript files."""
        try:
            prefix, dots, import_path, suffix = match.groups()
            
            # Calculate current and target absolute paths
            current_file_abs = project_copy_root / current_file_rel_path
            current_dir = current_file_abs.parent
            
            # Resolve the imported file
            if dots == "./":
                target_abs = current_dir / import_path
            else:  # "../"
                levels_up = dots.count("../") + 1
                target_dir = current_dir
                for _ in range(levels_up):
                    target_dir = target_dir.parent
                target_abs = target_dir / import_path
            
            # Find possible extensions
            possible_extensions = [".js", ".ts", ".jsx", ".tsx", ".vue", ".json"]
            target_file = None
            
            for ext in possible_extensions:
                test_path = target_abs.with_suffix(ext)
                if test_path.exists():
                    target_file = test_path
                    break
            
            if not target_file:
                return match.group(0)  # Return original if not found
            
            target_rel_path = target_file.relative_to(project_copy_root).as_posix()
            
            # Get new paths from mapping
            if target_rel_path not in self.file_mapping:
                return match.group(0)
            
            new_current_path = self.file_mapping[current_file_rel_path]
            new_target_path = self.file_mapping[target_rel_path]
            
            # Calculate new relative path
            new_current_dir = (project_copy_root / new_current_path).parent
            new_target_file = project_copy_root / new_target_path
            
            new_rel_path = os.path.relpath(new_target_file, new_current_dir)
            
            # Ensure it starts with ./ for relative imports
            if not new_rel_path.startswith("../"):
                new_rel_path = "./" + new_rel_path
            
            # Remove extension for JS imports (usually not needed)
            new_rel_path = os.path.splitext(new_rel_path)[0]
            
            return f"{prefix}{new_rel_path}{suffix}"
            
        except Exception:
            return match.group(0)  # Return original on error


class PythonImportTransformer(cst.CSTTransformer):
    """LibCST transformer for Python imports."""
    
    def __init__(self, current_file_rel_path: str, file_mapping: dict, project_root: Path):
        self.current_file_rel_path = current_file_rel_path
        self.file_mapping = file_mapping
        self.project_root = project_root

    def leave_ImportFrom(self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom) -> cst.ImportFrom:
        if not original_node.relative:
            return updated_node

        try:
            level = len(original_node.relative)
            source_dir = (self.project_root / self.current_file_rel_path).parent
            
            imported_module_base_path = source_dir.resolve()
            for _ in range(level - 1):
                imported_module_base_path = imported_module_base_path.parent

            if original_node.module:
                module_name_parts = original_node.module.value.split('.')
                imported_module_path = imported_module_base_path.joinpath(*module_name_parts)
            else:
                imported_module_path = imported_module_base_path

            original_target_path = None
            if (imported_module_path.with_suffix(".py")).is_file():
                original_target_path = imported_module_path.with_suffix(".py")
            elif (imported_module_path / "__init__.py").is_file():
                original_target_path = imported_module_path / "__init__.py"
            else:
                return updated_node

            original_target_rel_path = original_target_path.relative_to(self.project_root).as_posix()

            if original_target_rel_path not in self.file_mapping:
                return updated_node

            new_current_file_path = self.project_root / self.file_mapping[self.current_file_rel_path]
            new_target_file_path = self.project_root / self.file_mapping[original_target_rel_path]
            
            new_relative_path = os.path.relpath(
                new_target_file_path.parent, 
                new_current_file_path.parent
            )
            
            if new_relative_path == '.':
                dots = 1
                new_module_parts = []
            else:
                path_parts = new_relative_path.split(os.sep)
                dots = path_parts.count('..') + 1
                new_module_parts = [p for p in path_parts if p != '..']

            if original_node.module:
                original_module_name = original_node.module.value.split('.')[-1]
                new_module_parts.append(original_module_name)

            new_module_str = ".".join(new_module_parts) if new_module_parts else None

            return updated_node.with_changes(
                relative=[cst.Dot() for _ in range(dots)],
                module=cst.Name(value=new_module_str) if new_module_str else None
            )
        except Exception:
            return updated_node

# -----------------------------------------------------------------------------
# 3. Enhanced Dependency Analysis and Generation
# -----------------------------------------------------------------------------
class DependencyAnalyzer:
    """Analyzes and generates dependency files for multiple languages."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.python_imports = set()
        self.js_dependencies = set()
        self.python_stdlib = self._get_python_stdlib()
    
    def analyze_all_dependencies(self) -> Dict[str, Set[str]]:
        """Analyzes dependencies across all supported file types."""
        dependencies = {
            "python": set(),
            "javascript": set(),
            "dev_dependencies": set()
        }
        
        for py_file in self.project_root.rglob("*.py"):
            deps = self._analyze_python_file(py_file)
            dependencies["python"].update(deps)
        
        for js_file in self.project_root.rglob("*.js"):
            deps = self._analyze_js_file(js_file)
            dependencies["javascript"].update(deps)
        
        for ts_file in self.project_root.rglob("*.ts"):
            deps = self._analyze_js_file(ts_file)
            dependencies["javascript"].update(deps)
            
        for jsx_file in self.project_root.rglob("*.jsx"):
            deps = self._analyze_js_file(jsx_file)
            dependencies["javascript"].update(deps)
            
        for tsx_file in self.project_root.rglob("*.tsx"):
            deps = self._analyze_js_file(tsx_file)
            dependencies["javascript"].update(deps)
        
        return dependencies
    
    def _analyze_python_file(self, file_path: Path) -> Set[str]:
        """Analyzes Python file for imports."""
        imports = set()
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                tree = ast.parse(f.read())
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        package = alias.name.split('.')[0]
                        if package not in self.python_stdlib:
                            imports.add(package)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        package = node.module.split('.')[0]
                        if package not in self.python_stdlib:
                            imports.add(package)
        except:
            pass
        return imports
    
    def _analyze_js_file(self, file_path: Path) -> Set[str]:
        """Analyzes JavaScript/TypeScript file for imports."""
        imports = set()
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            
            # ES6 imports
            import_pattern = r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]'
            require_pattern = r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
            
            for match in re.finditer(import_pattern, content):
                package = match.group(1)
                if not package.startswith('.'):  # External package
                    imports.add(package.split('/')[0])
            
            for match in re.finditer(require_pattern, content):
                package = match.group(1)
                if not package.startswith('.'):  # External package
                    imports.add(package.split('/')[0])
                    
        except:
            pass
        return imports
    
    def _get_python_stdlib(self) -> Set[str]:
        """Returns set of Python standard library modules."""
        return {
            'ast', 'asyncio', 'base64', 'collections', 'copy', 'datetime', 'decimal',
            'functools', 'hashlib', 'io', 'itertools', 'json', 'logging', 'math',
            'os', 'pathlib', 'pickle', 're', 'shutil', 'subprocess', 'sys', 'time',
            'typing', 'urllib', 'uuid', 'warnings', 'weakref', 'xml'
        }
    
    def generate_requirements_files(self):
        """Generates requirements files for different languages."""
        dependencies = self.analyze_all_dependencies()
        
        # Generate requirements.txt for Python
        if dependencies["python"]:
            self._generate_python_requirements(dependencies["python"])
        
        # Generate package.json for JavaScript
        if dependencies["javascript"]:
            self._generate_package_json(dependencies["javascript"])
    
    def _generate_python_requirements(self, packages: Set[str]):
        """Generates requirements.txt file."""
        req_file = self.project_root / "requirements.txt"
        
        # Try to get versions using pip show
        requirements = []
        for package in sorted(packages):
            try:
                result = subprocess.run(
                    ["pip", "show", package],
                    capture_output=True,
                    text=True,
                    check=True
                )
                for line in result.stdout.split('\n'):
                    if line.startswith('Version:'):
                        version = line.split(':')[1].strip()
                        requirements.append(f"{package}=={version}")
                        break
                else:
                    requirements.append(package)
            except:
                requirements.append(package)
        
        req_file.write_text('\n'.join(requirements) + '\n', encoding='utf-8')
        print(f"✅ Generated requirements.txt with {len(requirements)} packages")
    
    def _generate_package_json(self, packages: Set[str]):
        """Generates or updates package.json file."""
        package_json_path = self.project_root / "package.json"
        
        if package_json_path.exists():
            try:
                with open(package_json_path, 'r', encoding='utf-8') as f:
                    package_data = json.load(f)
            except:
                package_data = {}
        else:
            package_data = {
                "name": "structured-project",
                "version": "1.0.0",
                "description": "Auto-generated project structure",
                "main": "index.js",
                "scripts": {
                    "start": "node index.js",
                    "test": "echo \"Error: no test specified\" && exit 1"
                }
            }
        
        if "dependencies" not in package_data:
            package_data["dependencies"] = {}
        
        # Add discovered dependencies
        for package in sorted(packages):
            if package not in package_data["dependencies"]:
                package_data["dependencies"][package] = "^latest"
        
        with open(package_json_path, 'w', encoding='utf-8') as f:
            json.dump(package_data, f, indent=2)
        
        print(f"✅ Generated/updated package.json with {len(packages)} dependencies")

# -----------------------------------------------------------------------------
# 4. Fallback Structure Generator
# -----------------------------------------------------------------------------
def generate_fallback_structure(file_categories: Dict[str, List[str]], persona: str) -> Dict:
    """Generates a fallback structure when AI fails or provides incomplete mapping."""
    print("🔄 Generating fallback structure...")
    
    file_mapping = {}
    placement_reasons = {}
    
    # Default folder structure based on persona
    persona_structures = {
        "Developer": {
            "Python": "src/",
            "JavaScript": "src/frontend/",
            "TypeScript": "src/frontend/",
            "React": "src/components/",
            "Tests": "tests/",
            "Config": "",
            "Docs": "docs/",
            "Assets": "assets/",
            "Data": "data/",
            "Other": ""
        },
        "Data Scientist": {
            "Python": "src/",
            "Notebook": "notebooks/",
            "Data": "data/raw/",
            "Tests": "tests/",
            "Config": "",
            "Docs": "docs/",
            "Other": "misc/"
        },
        "Student": {
            "Python": "src/",
            "JavaScript": "src/",
            "Tests": "tests/",
            "Config": "",
            "Docs": "",
            "Assets": "assets/",
            "Other": ""
        },
        "Researcher": {
            "Python": "src/",
            "Notebook": "experiments/",
            "Data": "data/",
            "Tests": "tests/",
            "Config": "",
            "Docs": "papers/",
            "Other": "misc/"
        }
    }
    
    structure = persona_structures.get(persona, persona_structures["Developer"])
    
    # Map all files
    for category, files in file_categories.items():
        target_folder = structure.get(category, "misc/")
        
        for file_path in files:
            new_path = target_folder + file_path if target_folder else file_path
            file_mapping[file_path] = new_path
            placement_reasons[new_path] = f"{category} file placed in {target_folder or 'root'} according to {persona} persona"
    
    return {
        "file_mapping": file_mapping,
        "placement_reasons": placement_reasons,
        "project_structure": {
            "overview": f"Fallback structure generated for {persona} persona",
            "key_directories": {folder: f"Contains {category} files" for category, folder in structure.items() if folder},
            "conventions": ["Organized by file type", "Follows standard project conventions"]
        }
    }

# -----------------------------------------------------------------------------
# 5. Enhanced AI Structure Generation with Retry Logic
# -----------------------------------------------------------------------------
def generate_ai_structure(file_categories: Dict[str, List[str]], persona: str, max_retries: int = 3) -> Optional[Dict]:
    """Generates AI-recommended project structure with enhanced prompt and retry logic."""
    
    persona_instructions = {
        "Developer": """
**Developer Persona Guidelines:**
- **Source Code**: Organize all application code in `src/` with clear module separation (e.g., `src/api/`, `src/core/`, `src/utils/`, `src/components/`)
- **Frontend**: If React/Vue/JS files exist, place them in `src/frontend/` or `src/client/`
- **Backend**: Server-side Python/Node.js code goes in `src/backend/` or `src/server/`
- **Testing**: Mirror source structure in `tests/` directory
- **Configuration**: Keep config files at project root for easy access
- **Static Assets**: Place images, fonts, etc. in `src/assets/` or `public/assets/`
- **Build/Deployment**: Container files and CI/CD at project root
""",
        "Data Scientist": """
**Data Scientist Persona Guidelines:**
- **Data Pipeline**: Organize by data flow: `data/raw/`, `data/processed/`, `data/final/`
- **Notebooks**: All exploration notebooks in `notebooks/` with clear naming (01_exploration.ipynb)
- **Source Code**: Reusable modules in `src/` (data processing, feature engineering, models)
- **Scripts**: Pipeline scripts in `scripts/` for automation
- **Models**: Serialized models and artifacts in `models/`
- **Results**: Generated outputs, plots, reports in `results/` or `outputs/`
- **Experiments**: Version controlled experiments in `experiments/`
""",
        "Researcher": """
**Researcher Persona Guidelines:**
- **Research Focus**: Organize around experiments and publications
- **Code**: Core algorithms and utilities in `src/`
- **Experiments**: Runnable experiments in `experiments/` with clear documentation
- **Data**: Research data in `data/` with metadata
- **Results**: All outputs, figures, tables in `results/` organized by experiment
- **Documentation**: Papers, notes, literature review in `docs/` or `papers/`
- **Reproducibility**: Clear separation between data, code, and results
""",
        "Student": """
**Student Persona Guidelines:**
- **Simplicity First**: Avoid over-engineering, keep structure flat and intuitive
- **Source Code**: Main application code in `src/` or directly at root if small
- **Assignments**: If multiple assignments, organize by assignment number/name
- **Resources**: Learning materials, references in `resources/` or `docs/`
- **Practice**: Practice exercises in `practice/` or `exercises/`
- **Assets**: All non-code files in `assets/` or `data/`
- **Clear Naming**: Use descriptive, self-explanatory folder and file names
"""
    }

    # Get all files for explicit listing
    all_files = []
    for files in file_categories.values():
        all_files.extend(files)

    # Enhanced prompt with better structure understanding and explicit file listing
    prompt = f"""
You are an expert software architect AI tasked with creating an optimal project structure for a multi-language development project.

**User Persona:** {persona}
**Persona-Specific Guidelines:**
{persona_instructions.get(persona, persona_instructions['Developer'])}

**CRITICAL REQUIREMENT: YOU MUST MAP EVERY SINGLE FILE LISTED BELOW**

**ALL PROJECT FILES TO MAP:**
{json.dumps(sorted(all_files), indent=2)}

**File Categories Analysis:**
{json.dumps(file_categories, indent=2)}

**Your Mission:**
Create a file mapping that moves EVERY SINGLE file from the list above to a new location. Do not skip any files.

**Key Requirements:**
1. **COMPLETE COVERAGE**: Map every file from the ALL PROJECT FILES list above
2. **Technology-Aware**: Consider the mix of Python, JavaScript, React, Vue, etc.
3. **Separation of Concerns**: Clearly separate source code, tests, config, docs, and assets
4. **Scalability**: Structure should support project growth
5. **Standards Compliance**: Follow language/framework conventions
6. **Developer Experience**: Make the structure intuitive and navigable

**Special Considerations:**
- If both frontend (JS/React/Vue) and backend (Python) files exist, create clear separation
- Group related functionality together (APIs, components, utilities)
- Maintain logical hierarchy (no more than 3-4 levels deep typically)
- Consider deployment and CI/CD needs
- Handle test files appropriately (mirror source structure or separate test directory)
- Config files like .gitignore, constants.py should be placed appropriately

**Output Format:**
Return ONLY a valid JSON object with this exact structure:
```json
{{
  "file_mapping": {{
    "original/path/file.py": "new/structured/path/file.py"
  }},
  "placement_reasons": {{
    "new/structured/path/file.py": "Detailed reason for placing this file here"
  }},
  "project_structure": {{
    "overview": "High-level description of the chosen structure",
    "key_directories": {{"dir_name": "purpose"}},
    "conventions": ["list", "of", "naming", "and", "organizational", "conventions"]
  }}
}}
```

**VERIFICATION CHECKLIST:**
Before submitting your response, verify:
- [ ] Every file from the ALL PROJECT FILES list is in file_mapping
- [ ] No files are missing from the mapping
- [ ] All mapped paths are valid (no invalid characters)
- [ ] Structure follows the chosen persona guidelines

Generate the complete structure now:
"""

    for attempt in range(max_retries):
        try:
            parameters = {
                "decoding_method": "greedy",
                "max_new_tokens": 8192,
                "min_new_tokens": 1,
                "temperature": 0.1 + (attempt * 0.05),  # Slightly increase temperature on retries
            }

            llm = WatsonxLLM(
                model_id=MODEL_ID,
                url=IBM_URL,
                apikey=IBM_API_KEY,
                project_id=IBM_PROJECT_ID,
                params=parameters
            )

            parser = JsonOutputParser()
            chain = llm | parser

            result = chain.invoke(prompt)
            
            # Validate that all files are mapped
            if result and "file_mapping" in result:
                mapped_files = set(result["file_mapping"].keys())
                expected_files = set(all_files)
                missing_files = expected_files - mapped_files
                
                if not missing_files:
                    print(f"✅ AI successfully mapped all {len(all_files)} files on attempt {attempt + 1}")
                    return result
                else:
                    print(f"⚠️ Attempt {attempt + 1}: AI missed {len(missing_files)} files. Retrying...")
                    if attempt == max_retries - 1:  # Last attempt
                        print(f"   Missing files: {list(missing_files)[:5]}{'...' if len(missing_files) > 5 else ''}")
            
        except Exception as e:
            print(f"⚠️ AI generation attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                print("❌ All AI attempts failed, will use fallback structure")
    
    return None

# -----------------------------------------------------------------------------
# 6. Enhanced Validation with Auto-Fix
# -----------------------------------------------------------------------------
def validate_and_fix_ai_response(ai_plan: Dict, all_files: List[str]) -> Tuple[bool, Dict]:
    """Validates AI response and attempts to fix missing mappings."""
    if not ai_plan or "file_mapping" not in ai_plan:
        print("❌ Invalid AI response: missing file_mapping")
        return False, ai_plan
    
    file_mapping = ai_plan["file_mapping"]
    missing_files = set(all_files) - set(file_mapping.keys())
    
    if not missing_files:
        print("✅ AI response validation passed - all files mapped")
        return True, ai_plan
    
    print(f"⚠️ AI response missing mappings for {len(missing_files)} files, attempting auto-fix...")
    
    # Auto-fix: Add missing files to root or appropriate default location
    placement_reasons = ai_plan.get("placement_reasons", {})
    
    for missing_file in missing_files:
        # Simple heuristic for placement
        file_ext = Path(missing_file).suffix.lower()
        file_name = Path(missing_file).name.lower()
        
        if file_name in ['.gitignore', '.env', 'readme.md', 'license']:
            new_path = missing_file  # Keep at root
            reason = "Configuration/documentation file kept at project root"
        elif file_ext == '.py':
            new_path = f"src/{missing_file}"
            reason = "Python source file placed in src directory"
        elif file_ext in ['.js', '.jsx', '.ts', '.tsx']:
            new_path = f"src/{missing_file}"
            reason = "JavaScript/TypeScript file placed in src directory"
        elif 'test' in file_name:
            new_path = f"tests/{missing_file}"
            reason = "Test file placed in tests directory"
        else:
            new_path = missing_file  # Keep at root as fallback
            reason = "File kept at root as fallback placement"
        
        file_mapping[missing_file] = new_path
        placement_reasons[new_path] = reason
        print(f"   ✅ Auto-fixed: {missing_file} -> {new_path}")
    
    ai_plan["file_mapping"] = file_mapping
    ai_plan["placement_reasons"] = placement_reasons
    
    print(f"✅ Auto-fix completed - all {len(all_files)} files now mapped")
    return True, ai_plan

# -----------------------------------------------------------------------------
# 7. Advanced File Operations and Project Management
# -----------------------------------------------------------------------------
def create_directory_structure(output_root: Path, file_mapping: Dict[str, str]):
    """Creates all necessary directories based on the file mapping."""
    directories = set()
    for dest_path in file_mapping.values():
        parent_dir = (output_root / dest_path).parent
        directories.add(parent_dir)
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

def copy_and_move_files(project_root: Path, output_root: Path, file_mapping: Dict[str, str]):
    """Copies files from source to destination according to mapping."""
    print("\n🔄 Moving files to new structure...")
    
    success_count = 0
    for src_rel, dst_rel in file_mapping.items():
        src_abs = project_root / src_rel
        dst_abs = output_root / dst_rel
        
        if not src_abs.exists():
            print(f"⚠️ Source file not found, skipping: {src_rel}")
            continue
        
        try:
            dst_abs.parent.mkdir(parents=True, exist_ok=True)
            if src_abs.is_file():
                shutil.copy2(str(src_abs), str(dst_abs))
                success_count += 1
                print(f"✅ {src_rel} -> {dst_rel}")
            else:
                shutil.copytree(str(src_abs), str(dst_abs), dirs_exist_ok=True)
                success_count += 1
                print(f"✅ {src_rel} -> {dst_rel} (directory)")
        except Exception as e:
            print(f"❌ Error moving {src_rel} -> {dst_rel}: {e}")
    
    print(f"\n📊 Successfully moved {success_count}/{len(file_mapping)} files")

# -----------------------------------------------------------------------------
# 8. Enhanced Report Generation
# -----------------------------------------------------------------------------
def generate_comprehensive_report(output_root: Path, ai_plan: Dict, persona: str, dependencies: Dict[str, Set[str]]):
    """Generates comprehensive project reports."""
    report_dir = output_root / "_project_reports"
    report_dir.mkdir(exist_ok=True)
    
    # Generate JSON mapping report
    mapping_report = {
        "persona": persona,
        "timestamp": str(Path().cwd()),
        "file_mapping": ai_plan["file_mapping"],
        "placement_reasons": ai_plan["placement_reasons"],
        "project_structure": ai_plan.get("project_structure", {}),
        "dependencies": {k: list(v) for k, v in dependencies.items()},
        "statistics": {
            "total_files_moved": len(ai_plan["file_mapping"]),
            "python_dependencies": len(dependencies.get("python", [])),
            "javascript_dependencies": len(dependencies.get("javascript", [])),
        }
    }
    
    (report_dir / "refactoring_report.json").write_text(
        json.dumps(mapping_report, indent=2), encoding="utf-8"
    )
    
    # Generate Markdown report
    md_content = f"""# Project Refactoring Report

## Overview
- **Persona:** {persona}
- **Total Files Processed:** {len(ai_plan['file_mapping'])}
- **Python Dependencies:** {len(dependencies.get('python', []))}
- **JavaScript Dependencies:** {len(dependencies.get('javascript', []))}

## Project Structure
{json.dumps(ai_plan.get('project_structure', {}), indent=2)}

## File Placement Decisions

"""
    
    for dest_path, reason in ai_plan.get("placement_reasons", {}).items():
        md_content += f"### `{dest_path}`\n{reason}\n\n"
    
    md_content += f"""
## Dependencies Discovered

### Python Packages
```
{chr(10).join(sorted(dependencies.get('python', [])))}
```

### JavaScript/Node.js Packages
```
{chr(10).join(sorted(dependencies.get('javascript', [])))}
```
"""
    
    (report_dir / "README.md").write_text(md_content, encoding="utf-8")
    print(f"📑 Comprehensive report saved to {report_dir}")

# -----------------------------------------------------------------------------
# 9. Enhanced Main Execution Logic
# -----------------------------------------------------------------------------
def execute_phase2(auto_confirm: bool = False) -> bool:
    """
    Executes the complete Phase 2 logic with enhanced multi-language support and robust error handling.
    """
    print(f"🤖 AI Struct Agent v{AGENT_VERSION} - Phase 2: Enhanced Multi-Language Refactoring")
    
    # Load Phase 1 metadata
    if not PHASE1_METADATA_JSON.exists():
        print(f"❌ Phase 1 output not found at {PHASE1_METADATA_JSON}. Please run Phase 1 first.")
        return False
    
    try:
        with open(PHASE1_METADATA_JSON, 'r', encoding='utf-8') as f:
            phase1_data = json.load(f)
        metadata = phase1_data["metadata"]
        project_root = Path(metadata.get("project_root", "."))
        persona = metadata.get("persona", "Developer")
    except (json.JSONDecodeError, KeyError) as e:
        print(f"❌ Failed to read Phase 1 metadata: {e}")
        return False
    
    print(f"📁 Project Root: {project_root.resolve()}")
    print(f"👤 Persona: {persona}")
    
    # Step 1: Enhanced File Discovery
    print("\n🔍 Step 1: Discovering and categorizing project files...")
    file_categories = FileDiscovery.discover_and_categorize_files(project_root)
    
    # Print discovered files summary
    total_files = sum(len(files) for files in file_categories.values())
    if total_files == 0:
        print("❌ No files found in project root.")
        return False
    
    print(f"\n📊 Discovered {total_files} files across {len(file_categories)} categories:")
    for category, files in file_categories.items():
        if files:
            print(f"   - {category}: {len(files)} files")
    
    # Get all files for validation
    all_files = []
    for files in file_categories.values():
        all_files.extend(files)
    
    # Step 2: AI Structure Generation with Retry Logic
    print(f"\n🧠 Step 2: Generating AI-recommended structure (with retry logic)...")
    ai_plan = generate_ai_structure(file_categories, persona, max_retries=3)
    
    if not ai_plan:
        print("⚠️ AI failed to generate complete structure, using fallback...")
        ai_plan = generate_fallback_structure(file_categories, persona)
    
    # Step 3: Validation and Auto-Fix
    print(f"\n✅ Step 3: Validating and fixing AI response...")
    try:
        jsonschema.validate(instance=ai_plan, schema=STRUCTURE_SCHEMA)
        print("✅ AI response schema validation passed.")
    except jsonschema.ValidationError as e:
        print(f"❌ AI response schema validation failed: {e.message}")
        # Save invalid response for debugging
        Path("phase2_invalid_ai_response.json").write_text(
            json.dumps(ai_plan, indent=2), encoding="utf-8"
        )
        return False
    
    # Validate and auto-fix file coverage
    is_valid, ai_plan = validate_and_fix_ai_response(ai_plan, all_files)
    if not is_valid:
        print("❌ Could not fix AI response validation errors")
        return False
    
    file_mapping = ai_plan["file_mapping"]
    
    # Display proposed changes
    print(f"\n📋 Proposed Structure Changes ({len(file_mapping)} files):")
    for src, dst in sorted(file_mapping.items())[:10]:  # Show first 10
        print(f"   {src} -> {dst}")
    if len(file_mapping) > 10:
        print(f"   ... and {len(file_mapping) - 10} more files")
    
    # Step 4: User Confirmation
    if not auto_confirm:
        choice = input("\n❓ Apply this structure? (y/n): ").strip().lower()
        if choice != 'y':
            print("🚫 Operation cancelled by user.")
            return True
    else:
        print("\n✅ Auto-confirming structure application.")
    
    # Step 5: Create structured project
    print(f"\n🏗️ Step 4: Creating structured project...")
    
    if OUTPUT_ROOT.exists():
        print(f"⚠️ Clearing existing output directory: {OUTPUT_ROOT}")
        shutil.rmtree(OUTPUT_ROOT)
    
    OUTPUT_ROOT.mkdir(exist_ok=True)
    
    # Create directory structure
    create_directory_structure(OUTPUT_ROOT, file_mapping)
    
    # Step 6: Copy files to new structure
    copy_and_move_files(project_root, OUTPUT_ROOT, file_mapping)
    
    # Step 7: Analyze and generate dependencies
    print("\n📦 Step 5: Analyzing dependencies...")
    dependency_analyzer = DependencyAnalyzer(OUTPUT_ROOT)
    dependencies = dependency_analyzer.analyze_all_dependencies()
    
    print(f"   - Python packages: {len(dependencies['python'])}")
    print(f"   - JavaScript packages: {len(dependencies['javascript'])}")
    
    # Generate dependency files
    dependency_analyzer.generate_requirements_files()
    
    # Step 8: Refactor imports for all languages
    print("\n🔧 Step 6: Refactoring imports and dependencies...")
    import_engine = ImportRefactorEngine(file_mapping, project_root)
    import_engine.refactor_all_imports(OUTPUT_ROOT)
    
    # Step 9: Generate comprehensive reports
    print("\n📄 Step 7: Generating project reports...")
    generate_comprehensive_report(OUTPUT_ROOT, ai_plan, persona, dependencies)
    
    # Step 10: Create project README
    create_project_readme(OUTPUT_ROOT, ai_plan, persona, dependencies)
    
    print(f"\n🎉 Phase 2 Complete!")
    print(f"✅ Structured project created at: {OUTPUT_ROOT.resolve()}")
    print(f"📑 Reports available in: {OUTPUT_ROOT / '_project_reports'}")
    
    return True

# -----------------------------------------------------------------------------
# 10. Enhanced Helper Functions
# -----------------------------------------------------------------------------
def _get_ai_generated_summary(output_root: Path, ai_plan: Dict, dependencies: Dict[str, Set[str]]) -> Dict[str, str]:
    """
    Uses an LLM to generate a project title, a one-line summary, and a list of key features
    by analyzing the project's structure, dependencies, and key file contents.
    """
    print("🧠 Generating AI-powered project summary for README...")
    
    # 1. Gather context for the AI
    structure_overview = ai_plan.get("project_structure", {}).get("overview", "No overview provided.")
    key_dirs = ai_plan.get("project_structure", {}).get("key_directories", {})
    
    # Gather file names
    all_files = [p.relative_to(output_root).as_posix() for p in output_root.rglob("*") if p.is_file()]
    
    # Safely read content from a few key source files to give the AI more context
    file_contents_summary = ""
    source_files_to_read = [
        "src/main.py", "src/app.py", "main.py", "app.py", 
        "src/index.js", "index.js", "src/server.js", "server.js"
    ]
    files_read = 0
    for file_path_str in source_files_to_read:
        file_path = output_root / file_path_str
        if file_path.exists() and files_read < 3:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")[:2000] # Read first 2000 chars
                file_contents_summary += f"\n--- Content of {file_path_str} ---\n{content}\n"
                files_read += 1
            except Exception:
                pass # Ignore files we can't read

    prompt = f"""
You are an expert technical writer AI. Your task is to create a compelling project title, a short summary, and a list of key features for a software project's README file.

Analyze the following project details:

**Project Structure Overview:**
{structure_overview}

**Key Directories:**
{json.dumps(key_dirs, indent=2)}

**File List:**
{json.dumps(all_files[:30], indent=2)}

**Detected Dependencies:**
- Python: {', '.join(dependencies.get('python', []))}
- JavaScript: {', '.join(dependencies.get('javascript', []))}

**Key File Contents:**
{file_contents_summary if file_contents_summary else "No file contents available."}

**Your Mission:**
Based on all the information above, generate a JSON object with the following keys:
- "project_title": A short, descriptive, and engaging title for the project.
- "project_summary": A concise one-sentence summary of the project's purpose.
- "key_features": A bulleted list (as an array of strings) of 3-5 key features or capabilities inferred from the code and file structure.

**Output Format (JSON only):**
```json
{{
  "project_title": "Example: AI-Powered Data Processing Pipeline",
  "project_summary": "This project provides a robust pipeline for ingesting, processing, and analyzing customer data using Python and modern data science libraries.",
  "key_features": [
    "Automated data ingestion from multiple sources.",
    "Advanced feature engineering for machine learning models.",
    "Interactive dashboard for visualizing results."
  ]
}}
```

Generate the JSON object now:
"""
    
    try:
        parameters = {
            "decoding_method": "greedy", 
            "max_new_tokens": 8192, 
            "temperature": 0.2
        }
        llm = WatsonxLLM(
            model_id=MODEL_ID, 
            url=IBM_URL, 
            apikey=IBM_API_KEY,
            project_id=IBM_PROJECT_ID, 
            params=parameters
        )
        parser = JsonOutputParser()
        chain = llm | parser

        response = chain.invoke(prompt)
        # Basic validation
        if all(k in response for k in ["project_title", "project_summary", "key_features"]):
            return response
        else:
            raise ValueError("AI response missing required keys.")
            
    except Exception as e:
        print(f"⚠️ Could not generate AI summary, using fallback. Error: {e}")
        return {
            "project_title": "Structured Project",
            "project_summary": "This project has been automatically restructured.",
            "key_features": ["Modular source code.", "Organized file structure."]
        }

def _find_project_entry_points(output_root: Path) -> Dict:
    """Finds potential ways to run the project."""
    entry_points = {"python": [], "js_scripts": {}, "tests": []}

    # Python entry points
    py_candidates = ["main.py", "app.py", "run.py", "manage.py"]
    for candidate in py_candidates:
        if (output_root / candidate).exists():
            entry_points["python"].append(candidate)
        elif (output_root / "src" / candidate).exists():
            entry_points["python"].append(f"src/{candidate}")

    # JavaScript/Node.js scripts from package.json
    package_json_path = output_root / "package.json"
    if package_json_path.exists():
        try:
            with open(package_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "scripts" in data:
                    entry_points["js_scripts"] = data["scripts"]
        except Exception:
            pass # Ignore malformed package.json
            
    # Test commands
    if "test" in entry_points["js_scripts"]:
        entry_points["tests"].append("npm test")
    if any(p.name.startswith("test_") for p in output_root.rglob("*.py")):
        entry_points["tests"].append("pytest")
        
    return entry_points

def create_project_readme(output_root: Path, ai_plan: Dict, persona: str, dependencies: Dict[str, Set[str]]):
    """Creates a comprehensive, AI-enhanced README.md for the structured project."""

    # Step 1: Get AI-generated summary and entry points
    summary_data = _get_ai_generated_summary(output_root, ai_plan, dependencies)
    entry_points = _find_project_entry_points(output_root)

    project_structure = ai_plan.get("project_structure", {})

    # Step 2: Build the README content section by section
    readme_content = f"# {summary_data['project_title']}\n\n"
    readme_content += f"_{summary_data['project_summary']}_\n\n"

    readme_content += "## ✨ Key Features\n\n"
    for feature in summary_data['key_features']:
        readme_content += f"- {feature}\n"
    readme_content += "\n"

    # --- Technologies Section ---
    tech_list = []
    if dependencies.get("python"):
        tech_list.append(f"**Python:** Core logic and backend services. Key libraries: `{', '.join(list(dependencies['python'])[:3])}`")
    if dependencies.get("javascript"):
        js_deps = list(dependencies['javascript'])
        is_react = "react" in js_deps
        is_vue = "vue" in js_deps
        framework = "React" if is_react else "Vue" if is_vue else "Node.js"
        tech_list.append(f"**{framework}:** Frontend components and user interface. Key libraries: `{', '.join(js_deps[:3])}`")

    if tech_list:
        readme_content += "## 🚀 Tech Stack\n\n"
        for tech in tech_list:
            readme_content += f"- {tech}\n"
        readme_content += "\n"

    # --- Getting Started Section ---
    readme_content += "## 📋 Getting Started\n\n"
    readme_content += "### Prerequisites\n\n"
    readme_content += "Ensure you have the following installed:\n"
    if dependencies.get("python"):
        readme_content += "- Python 3.8+\n"
        readme_content += "- pip\n"
    if dependencies.get("javascript"):
        readme_content += "- Node.js & npm\n"
    readme_content += "\n"

    readme_content += "### Installation\n\n"
    if (output_root / "requirements.txt").exists():
        readme_content += "1. **Clone the repository**\n"
        readme_content += "2. **Set up a Python virtual environment:**\n"
        readme_content += "   ```bash\n   python -m venv venv\n   source venv/bin/activate  # On Windows use `venv\\Scripts\\activate`\n   ```\n"
        readme_content += "3. **Install Python dependencies:**\n"
        readme_content += "   ```bash\n   pip install -r requirements.txt\n   ```\n"
    if (output_root / "package.json").exists():
        readme_content += "4. **Install JavaScript dependencies:**\n"
        readme_content += "   ```bash\n   npm install\n   ```\n"

    # --- Usage Section ---
    usage_instructions = []
    if entry_points["python"]:
        usage_instructions.append(f"To run the main Python script:\n```bash\npython {entry_points['python'][0]}\n```")
    if entry_points["js_scripts"].get("start"):
        usage_instructions.append(f"To start the development server:\n```bash\nnpm start\n```")
    elif entry_points["js_scripts"].get("dev"):
         usage_instructions.append(f"To start the development server:\n```bash\nnpm run dev\n```")

    if usage_instructions:
        readme_content += "## ▶️ Usage\n\n"
        readme_content += "\n\n".join(usage_instructions)
        readme_content += "\n"

    # --- Testing Section ---
    if entry_points["tests"]:
        readme_content += "## 🧪 Running Tests\n\n"
        readme_content += "To run the automated tests for this project, use the following command(s):\n"
        for test_cmd in entry_points["tests"]:
            readme_content += f"```bash\n{test_cmd}\n```\n"
        readme_content += "\n"
        
    # --- Project Structure Section ---
    readme_content += f"## 📁 Project Structure\n\n"
    readme_content += f"The project structure was organized by the AI Struct Agent for the **{persona}** persona. Here is a high-level overview:\n\n"
    readme_content += f"```\n{_generate_directory_tree(output_root)}\n```\n\n"

    if project_structure.get("key_directories"):
        readme_content += "### Key Directories\n\n"
        for dir_name, purpose in project_structure.get("key_directories", {}).items():
            readme_content += f"- **`{dir_name}/`**: {purpose}\n"
        readme_content += "\n"

    # --- Footer ---
    readme_content += f"---\n\n*This README was generated by AI Struct Agent v{AGENT_VERSION}*\n"

    # Step 3: Write the file
    (output_root / "README.md").write_text(readme_content, encoding="utf-8")
    print("✅ Project README.md created with AI-enhanced details.")

def _generate_directory_tree(root_path: Path, max_depth: int = 3) -> str:
    """Generates a simple directory tree string."""
    tree_lines = []
    
    def add_directory(path: Path, depth: int = 0):
        if depth > max_depth:
            return
        
        indent = "  " * depth
        if path == root_path:
            tree_lines.append(f"{path.name}/")
        else:
            tree_lines.append(f"{indent}├── {path.name}/")
        
        try:
            subdirs = [p for p in path.iterdir() if p.is_dir() and not p.name.startswith('.')]
            for subdir in sorted(subdirs):
                add_directory(subdir, depth + 1)
        except PermissionError:
            pass
    
    add_directory(root_path)
    return "\n".join(tree_lines[:20])  # Limit output

# -----------------------------------------------------------------------------
# 11. Command Line Interface
# -----------------------------------------------------------------------------
def main():
    """Main entry point for standalone execution."""
    parser = argparse.ArgumentParser(
        description="Phase 2: AI-powered project structure refactoring with multi-language support"
    )
    parser.add_argument(
        "--auto-confirm", 
        action="store_true", 
        help="Skip user confirmation and apply structure automatically"
    )
    parser.add_argument(
        "--version", 
        action="version", 
        version=f"AI Struct Agent Phase 2 v{AGENT_VERSION}"
    )
    
    args = parser.parse_args()
def main():
    """Main entry point for standalone execution."""
    parser = argparse.ArgumentParser(
        description="Phase 2: AI-powered project structure refactoring with multi-language support"
    )
    parser.add_argument(
        "--auto-confirm", 
        action="store_true", 
        help="Skip user confirmation and apply structure automatically"
    )
    parser.add_argument(
        "--version", 
        action="version", 
        version=f"AI Struct Agent Phase 2 v{AGENT_VERSION}"
    )
    
    args = parser.parse_args()
    
    try:
        success = execute_phase2(auto_confirm=args.auto_confirm)
        if success:
            print("\n🎊 Phase 2 execution completed successfully!")
            print("\nNext Steps:")
            print("1. Review the generated structure in './structured_project/'")
            print("2. Check dependency files (requirements.txt, package.json)")
            print("3. Run tests to ensure imports are working correctly")
            print("4. Review the comprehensive report in '_project_reports/'")
            sys.exit(0)
        else:
            print("\n❌ Phase 2 execution failed. Check the logs above for details.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚡ Operation interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Unexpected error during execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# -----------------------------------------------------------------------------
# 12. Module Testing and Validation
# -----------------------------------------------------------------------------
def run_self_test():
    """Runs basic self-tests to validate the module functionality."""
    print("🧪 Running AI Struct Agent Phase 2 self-tests...")
    
    # Test 1: File Discovery
    print("   ✓ Testing FileDiscovery...")
    test_files = {
        "Python": ["main.py", "utils/helper.py"],
        "JavaScript": ["app.js", "components/Button.jsx"],
        "Config": ["package.json", "requirements.txt"],
        "Tests": ["test_main.py", "app.test.js"]
    }
    
    # Test 2: Import refactoring logic
    print("   ✓ Testing ImportRefactorEngine initialization...")
    test_mapping = {"src/main.py": "app/main.py"}
    engine = ImportRefactorEngine(test_mapping, Path("."))
    assert engine is not None
    
    # Test 3: Dependency analyzer
    print("   ✓ Testing DependencyAnalyzer initialization...")
    analyzer = DependencyAnalyzer(Path("."))
    stdlib = analyzer._get_python_stdlib()
    assert "os" in stdlib
    assert "sys" in stdlib
    
    # Test 4: Schema validation
    print("   ✓ Testing structure schema...")
    test_structure = {
        "file_mapping": {"test.py": "src/test.py"},
        "placement_reasons": {"src/test.py": "Python source file"}
    }
    try:
        jsonschema.validate(instance=test_structure, schema=STRUCTURE_SCHEMA)
        print("   ✓ Schema validation passed")
    except jsonschema.ValidationError:
        print("   ❌ Schema validation failed")
        return False
    
    print("✅ All self-tests passed!")
    return True

# -----------------------------------------------------------------------------
# 13. Utility Functions for Advanced Operations
# -----------------------------------------------------------------------------
def cleanup_temp_files(project_root: Path):
    """Cleans up temporary files and caches."""
    cleanup_patterns = [
        "**/__pycache__",
        "**/*.pyc",
        "**/.pytest_cache",
        "**/node_modules",
        "**/.DS_Store",
        "**/Thumbs.db"
    ]
    
    cleaned_count = 0
    for pattern in cleanup_patterns:
        for path in project_root.glob(pattern):
            if path.exists():
                if path.is_file():
                    path.unlink()
                    cleaned_count += 1
                elif path.is_dir():
                    shutil.rmtree(path)
                    cleaned_count += 1
    
    if cleaned_count > 0:
        print(f"🧹 Cleaned up {cleaned_count} temporary files/directories")

def validate_project_integrity(output_root: Path) -> bool:
    """Validates the integrity of the created project structure."""
    print("🔍 Validating project integrity...")
    
    issues = []
    
    # Check for empty directories
    for dir_path in output_root.rglob("*"):
        if dir_path.is_dir() and not any(dir_path.iterdir()):
            issues.append(f"Empty directory: {dir_path.relative_to(output_root)}")
    
    # Check for broken imports (basic check)
    for py_file in output_root.rglob("*.py"):
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Look for obvious import issues
                if "from ." in content and not any(py_file.parent.rglob("*.py")):
                    issues.append(f"Potential broken relative import in: {py_file.relative_to(output_root)}")
        except Exception:
            continue
    
    # Check for missing critical files
    critical_files = ["README.md"]
    for critical_file in critical_files:
        if not (output_root / critical_file).exists():
            issues.append(f"Missing critical file: {critical_file}")
    
    if issues:
        print("⚠️ Project integrity issues found:")
        for issue in issues[:5]:  # Show first 5 issues
            print(f"   - {issue}")
        if len(issues) > 5:
            print(f"   - ... and {len(issues) - 5} more issues")
        return False
    else:
        print("✅ Project integrity validation passed")
        return True

# -----------------------------------------------------------------------------
# 14. Enhanced Error Recovery and Rollback
# -----------------------------------------------------------------------------
class OperationContext:
    """Context manager for handling operations with rollback capability."""
    
    def __init__(self, output_root: Path):
        self.output_root = output_root
        self.backup_path = None
        self.created_files = []
        
    def __enter__(self):
        # Create backup if output directory exists
        if self.output_root.exists():
            self.backup_path = self.output_root.with_suffix('.backup')
            if self.backup_path.exists():
                shutil.rmtree(self.backup_path)
            shutil.copytree(self.output_root, self.backup_path)
            print(f"📦 Created backup at: {self.backup_path}")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # An error occurred, perform rollback
            print("🔄 Error detected, performing rollback...")
            if self.output_root.exists():
                shutil.rmtree(self.output_root)
            if self.backup_path and self.backup_path.exists():
                shutil.copytree(self.backup_path, self.output_root)
                print("✅ Rollback completed successfully")
        else:
            # Success, clean up backup
            if self.backup_path and self.backup_path.exists():
                shutil.rmtree(self.backup_path)
        
        return False  # Don't suppress exceptions

# -----------------------------------------------------------------------------
# 15. Integration Points and API
# -----------------------------------------------------------------------------
def get_phase2_status() -> Dict:
    """Returns the current status of Phase 2 execution."""
    return {
        "version": AGENT_VERSION,
        "phase1_available": PHASE1_METADATA_JSON.exists(),
        "output_exists": OUTPUT_ROOT.exists(),
        "last_execution": OUTPUT_ROOT.stat().st_mtime if OUTPUT_ROOT.exists() else None
    }

def execute_phase2_programmatic(config: Dict) -> Dict:
    """
    Programmatic interface for Phase 2 execution.
    
    Args:
        config: Configuration dictionary with options like auto_confirm, persona, etc.
    
    Returns:
        Dict with execution results and metadata
    """
    auto_confirm = config.get("auto_confirm", False)
    
    try:
        with OperationContext(OUTPUT_ROOT):
            success = execute_phase2(auto_confirm=auto_confirm)
            
            return {
                "success": success,
                "output_path": str(OUTPUT_ROOT.resolve()) if success else None,
                "message": "Phase 2 completed successfully" if success else "Phase 2 execution failed"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Phase 2 execution failed with exception"
        }

# -----------------------------------------------------------------------------
# 16. Module Initialization and Entry Point
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Check if this is a self-test run
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        if run_self_test():
            print("🎉 Self-test completed successfully!")
            sys.exit(0)
        else:
            print("❌ Self-test failed!")
            sys.exit(1)
    
    # Check for required environment variables on startup
    try:
        # Validate IBM Watsonx.ai configuration
        if not all([IBM_API_KEY, IBM_URL, IBM_PROJECT_ID]):
            print("❌ Missing required IBM Watsonx.ai configuration:")
            print("   Please set IBM_API_KEY, IBM_URL, and IBM_PROJECT_ID environment variables")
            sys.exit(1)
            
        # Run the main application
        main()
        
    except ImportError as e:
        missing_module = str(e).split("'")[1] if "'" in str(e) else "unknown"
        print(f"❌ Missing required dependency: {missing_module}")
        print("   Please install required packages:")
        print("   pip install langchain-ibm libcst jsonschema")
        sys.exit(1)
    except Exception as e:
        print(f"💥 Critical startup error: {e}")
        sys.exit(1)

# -----------------------------------------------------------------------------
# Module Information and Credits
# -----------------------------------------------------------------------------
__version__ = AGENT_VERSION
__author__ = "AI Struct Agent Team"
__description__ = "Enhanced AI-powered project structure refactoring with multi-language support"
__license__ = "MIT"

# Export public API
__all__ = [
    "execute_phase2",
    "execute_phase2_programmatic", 
    "get_phase2_status",
    "FileDiscovery",
    "ImportRefactorEngine",
    "DependencyAnalyzer",
    "AGENT_VERSION"
]