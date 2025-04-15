# Knowledge Graph Generator for Healthcare Bill Review System

This tool generates a detailed knowledge graph of the Healthcare Bill Review System codebase, which can be used for LLM evaluation and system understanding.

## Features

- Static analysis of Python code
- Extraction of:
  - Class hierarchies and relationships
  - Method signatures and docstrings
  - Dependencies (both internal and external)
  - Component relationships
  - Configuration details
  - Service and utility components

## Output Format

The generated knowledge graph is saved in JSON format with the following structure:

```json
{
  "system_name": "Healthcare Bill Review System",
  "version": "2.0",
  "architecture": {
    "components": {
      // Validator components with methods and relationships
    },
    "relationships": {
      // Component relationships and dependencies
    },
    "dependencies": {
      "internal": [
        // Internal module dependencies
      ],
      "external": [
        // External package dependencies
      ]
    }
  },
  "data_models": {
    // Data model classes with methods and docstrings
  },
  "services": {
    // Service classes with methods and docstrings
  },
  "utilities": {
    // Utility classes with methods and docstrings
  },
  "configuration": {
    // Configuration classes and settings
  }
}
```

## Usage

1. Place the `knowledge_graph_generator.py` script in your project root directory
2. Run the script:
   ```bash
   python knowledge_graph_generator.py
   ```
3. The script will generate a `knowledge_graph.json` file in the same directory

## Using with LLMs

The generated knowledge graph can be used with LLMs in several ways:

1. **System Understanding**: Provide the knowledge graph to help LLMs understand the system architecture
2. **Code Generation**: Use the graph to generate code that follows the existing patterns
3. **Documentation**: Generate comprehensive documentation based on the extracted information
4. **Refactoring**: Identify potential improvements and refactoring opportunities
5. **Testing**: Generate test cases based on the component relationships

## Example LLM Prompts

1. **System Understanding**:
   ```
   Based on the following knowledge graph of our Healthcare Bill Review System, explain the main components and their relationships:
   [Insert knowledge_graph.json contents]
   ```

2. **Code Generation**:
   ```
   Using the knowledge graph below, generate a new validator that follows the same patterns as the existing validators:
   [Insert knowledge_graph.json contents]
   ```

3. **Documentation**:
   ```
   Create comprehensive documentation for the system based on this knowledge graph:
   [Insert knowledge_graph.json contents]
   ```

## Notes

- The script uses Python's `ast` module for static analysis
- It ignores `__pycache__` directories
- All Python files in the project are analyzed
- The output is formatted for easy reading and LLM consumption

## Requirements

- Python 3.6+
- No external dependencies required 