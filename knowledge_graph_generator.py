import ast
import os
from pathlib import Path
import json
from typing import Dict, List, Set, Any
import logging
from collections import defaultdict

class CodeAnalyzer:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.imports = defaultdict(set)
        self.classes = {}
        self.functions = {}
        self.dependencies = defaultdict(set)
        self.component_relationships = defaultdict(set)
        self.logger = logging.getLogger(__name__)
        
    def analyze_file(self, file_path: Path) -> Dict:
        """Analyze a single Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            tree = ast.parse(content)
            
            file_info = {
                'classes': {},
                'functions': {},
                'imports': set(),
                'dependencies': set(),
                'file_type': self._get_file_type(file_path),
                'file_size': os.path.getsize(file_path),
                'last_modified': os.path.getmtime(file_path)
            }
            
            # Analyze imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        file_info['imports'].add(name.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module
                    for name in node.names:
                        file_info['imports'].add(f"{module}.{name.name}")
            
            # Analyze classes and methods
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_info = {
                        'methods': [],
                        'bases': [base.id for base in node.bases if isinstance(base, ast.Name)],
                        'docstring': ast.get_docstring(node),
                        'line_count': len(node.body),
                        'decorators': [d.id for d in node.decorator_list if isinstance(d, ast.Name)]
                    }
                    
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            method_info = {
                                'name': item.name,
                                'args': [arg.arg for arg in item.args.args],
                                'docstring': ast.get_docstring(item),
                                'line_count': len(item.body),
                                'decorators': [d.id for d in item.decorator_list if isinstance(d, ast.Name)]
                            }
                            class_info['methods'].append(method_info)
                    
                    file_info['classes'][node.name] = class_info
                
                elif isinstance(node, ast.FunctionDef):
                    function_info = {
                        'args': [arg.arg for arg in node.args.args],
                        'docstring': ast.get_docstring(node),
                        'line_count': len(node.body),
                        'decorators': [d.id for d in node.decorator_list if isinstance(d, ast.Name)]
                    }
                    file_info['functions'][node.name] = function_info
            
            return file_info
            
        except Exception as e:
            self.logger.error(f"Error analyzing {file_path}: {str(e)}")
            return {}
    
    def _get_file_type(self, file_path: Path) -> str:
        """Determine the type of file based on its location and content."""
        if 'web' in str(file_path):
            if file_path.suffix == '.py':
                return 'web_backend'
            elif file_path.suffix in ['.html', '.css', '.js']:
                return 'web_frontend'
        elif 'core' in str(file_path):
            if 'validators' in str(file_path):
                return 'validator'
            elif 'services' in str(file_path):
                return 'service'
            elif 'models' in str(file_path):
                return 'model'
        elif 'utils' in str(file_path):
            return 'utility'
        elif 'config' in str(file_path):
            return 'configuration'
        return 'other'
    
    def analyze_directory(self) -> Dict:
        """Analyze all files in the directory."""
        results = {}
        folder_structure = {}
        
        # First pass: Build folder structure
        for root, dirs, files in os.walk(self.root_dir):
            relative_path = Path(root).relative_to(self.root_dir)
            if '__pycache__' in str(relative_path):
                continue
                
            current_level = folder_structure
            for part in relative_path.parts:
                if part not in current_level:
                    current_level[part] = {}
                current_level = current_level[part]
            
            current_level['_files'] = [f for f in files if not f.startswith('.')]
        
        # Second pass: Analyze Python files
        for file_path in self.root_dir.rglob('*.py'):
            if '__pycache__' in str(file_path):
                continue
                
            relative_path = file_path.relative_to(self.root_dir)
            file_info = self.analyze_file(file_path)
            results[str(relative_path)] = file_info
            
            # Update global imports and dependencies
            for imp in file_info['imports']:
                self.imports[str(relative_path)].add(imp)
                if imp.startswith('core.') or imp.startswith('utils.'):
                    self.dependencies[str(relative_path)].add(imp)
        
        return {
            'file_analysis': results,
            'folder_structure': folder_structure
        }
    
    def build_knowledge_graph(self) -> Dict:
        """Build a comprehensive knowledge graph of the codebase."""
        analysis_results = self.analyze_directory()
        
        knowledge_graph = {
            'system_name': 'Healthcare Bill Review System',
            'version': '2.0',
            'folder_structure': analysis_results['folder_structure'],
            'architecture': {
                'components': {},
                'relationships': {},
                'dependencies': {},
                'web_app': {
                    'frontend': {},
                    'backend': {},
                    'routes': [],
                    'templates': []
                }
            },
            'data_models': {},
            'services': {},
            'utilities': {},
            'configuration': {}
        }
        
        # Organize components by type
        for file_path, file_info in analysis_results['file_analysis'].items():
            if 'web' in file_path:
                self._process_web_component(file_path, file_info, knowledge_graph)
            elif 'core' in file_path:
                if 'models' in file_path:
                    self._process_models(file_path, file_info, knowledge_graph)
                elif 'services' in file_path:
                    self._process_services(file_path, file_info, knowledge_graph)
                elif 'validators' in file_path:
                    self._process_validators(file_path, file_info, knowledge_graph)
            elif 'utils' in file_path:
                self._process_utilities(file_path, file_info, knowledge_graph)
            elif 'config' in file_path:
                self._process_configuration(file_path, file_info, knowledge_graph)
        
        # Add relationships
        knowledge_graph['architecture']['relationships'] = self._build_relationships(analysis_results['file_analysis'])
        
        # Add dependencies
        knowledge_graph['architecture']['dependencies'] = {
            'internal': self._get_internal_dependencies(),
            'external': self._get_external_dependencies()
        }
        
        return knowledge_graph
    
    def _process_web_component(self, file_path: str, file_info: Dict, graph: Dict) -> None:
        """Process web application components."""
        if file_info['file_type'] == 'web_backend':
            for class_name, class_info in file_info['classes'].items():
                # Check for route decorators
                routes = []
                for method in class_info['methods']:
                    if 'route' in method['decorators']:
                        routes.append({
                            'method': method['name'],
                            'path': next((d for d in method['decorators'] if d.startswith('/')), '/'),
                            'handler': method['name']
                        })
                
                if routes:
                    graph['architecture']['web_app']['backend'][class_name] = {
                        'file': file_path,
                        'routes': routes,
                        'methods': class_info['methods'],
                        'docstring': class_info['docstring']
                    }
        elif file_info['file_type'] == 'web_frontend':
            graph['architecture']['web_app']['frontend'][file_path] = {
                'type': 'template' if file_path.endswith('.html') else 'static',
                'size': file_info['file_size'],
                'last_modified': file_info['last_modified']
            }
    
    def _process_models(self, file_path: str, file_info: Dict, graph: Dict) -> None:
        """Process data model files."""
        for class_name, class_info in file_info['classes'].items():
            graph['data_models'][class_name] = {
                'file': file_path,
                'methods': class_info['methods'],
                'docstring': class_info['docstring'],
                'inheritance': class_info['bases']
            }
    
    def _process_services(self, file_path: str, file_info: Dict, graph: Dict) -> None:
        """Process service files."""
        for class_name, class_info in file_info['classes'].items():
            graph['services'][class_name] = {
                'file': file_path,
                'methods': class_info['methods'],
                'docstring': class_info['docstring'],
                'inheritance': class_info['bases']
            }
    
    def _process_validators(self, file_path: str, file_info: Dict, graph: Dict) -> None:
        """Process validator files."""
        for class_name, class_info in file_info['classes'].items():
            graph['architecture']['components'][class_name] = {
                'type': 'validator',
                'file': file_path,
                'methods': class_info['methods'],
                'docstring': class_info['docstring'],
                'inheritance': class_info['bases']
            }
    
    def _process_utilities(self, file_path: str, file_info: Dict, graph: Dict) -> None:
        """Process utility files."""
        for class_name, class_info in file_info['classes'].items():
            graph['utilities'][class_name] = {
                'file': file_path,
                'methods': class_info['methods'],
                'docstring': class_info['docstring'],
                'inheritance': class_info['bases']
            }
    
    def _process_configuration(self, file_path: str, file_info: Dict, graph: Dict) -> None:
        """Process configuration files."""
        for class_name, class_info in file_info['classes'].items():
            graph['configuration'][class_name] = {
                'file': file_path,
                'methods': class_info['methods'],
                'docstring': class_info['docstring'],
                'inheritance': class_info['bases']
            }
    
    def _build_relationships(self, analysis_results: Dict) -> Dict:
        """Build component relationships."""
        relationships = defaultdict(set)
        
        for file_path, file_info in analysis_results.items():
            for class_name, class_info in file_info['classes'].items():
                # Add inheritance relationships
                for base in class_info['bases']:
                    relationships[class_name].add(f"inherits_from:{base}")
                
                # Add method call relationships
                for method in class_info['methods']:
                    for imp in self.imports[file_path]:
                        if imp.startswith('core.') or imp.startswith('utils.'):
                            relationships[class_name].add(f"uses:{imp}")
                
                # Add web-specific relationships
                if 'web' in file_path:
                    for route in method.get('decorators', []):
                        if route.startswith('/'):
                            relationships[class_name].add(f"exposes_route:{route}")
        
        return {k: list(v) for k, v in relationships.items()}
    
    def _get_internal_dependencies(self) -> List[str]:
        """Get internal dependencies."""
        internal_deps = set()
        for deps in self.dependencies.values():
            internal_deps.update(deps)
        return sorted(list(internal_deps))
    
    def _get_external_dependencies(self) -> List[str]:
        """Get external dependencies."""
        external_deps = set()
        for deps in self.imports.values():
            for dep in deps:
                if not (dep.startswith('core.') or dep.startswith('utils.')):
                    external_deps.add(dep)
        return sorted(list(external_deps))

def main():
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Get the root directory of the project
    root_dir = Path(__file__).parent
    
    # Create analyzer and generate knowledge graph
    analyzer = CodeAnalyzer(root_dir)
    knowledge_graph = analyzer.build_knowledge_graph()
    
    # Save the knowledge graph to a file
    output_file = root_dir / 'knowledge_graph.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(knowledge_graph, f, indent=2)
    
    print(f"Knowledge graph generated and saved to {output_file}")

if __name__ == '__main__':
    main() 