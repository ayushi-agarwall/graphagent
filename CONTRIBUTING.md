# Contributing to TinyAgent

## Development Philosophy

TinyAgent prioritizes simplicity and minimal dependencies. Before contributing, understand these constraints:

1. **Core must remain zero-dependency**: Only Python standard library in `tinyagent.py`
2. **Core must remain under compact and clean**: Optimize for clarity and brevity
3. **Plugins can have dependencies**: Optional features go in separate modules

## Getting Started

### Prerequisites

- Python 3.10+
- Git

### Setup

```bash
git clone https://github.com/your-org/tinyagent.git
cd tinyagent
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

## Code Standards

### Style

- Follow PEP 8
- Use type hints for all function signatures
- Maximum line length: 120 characters
- Use descriptive variable names

### Documentation

- All public classes and methods require docstrings
- Use Google-style docstring format
- Update README.md for user-facing changes

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=tinyagent --cov-report=term-missing

# Run specific test
pytest tests/test_flow.py::test_sequential_execution
```

All contributions must include tests. Maintain 90%+ coverage on core module.

## Contribution Workflow

### 1. Create an Issue

Before significant work, open an issue to discuss the proposed change.

### 2. Fork and Branch

```bash
git checkout -b feature/your-feature-name
```

Branch naming conventions:
- `feature/` - New functionality
- `fix/` - Bug fixes
- `docs/` - Documentation only
- `refactor/` - Code restructuring

### 3. Commit Guidelines

Use conventional commits:

```
type(scope): description

body (optional)

footer (optional)
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
```
feat(flow): add timeout support for node execution
fix(state): resolve race condition in thread-safe mode
docs(readme): add MoE pattern example
```

### 4. Pull Request

1. Ensure all tests pass
2. Update documentation if needed
3. Fill out the PR template completely
4. Request review from maintainers

### PR Requirements

- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No new dependencies in core
- [ ] Type hints complete
- [ ] Changelog entry added

## Architecture Guidelines

### Core Module (`tinyagent.py`)

Reserved for:
- `State`
- `Node`
- `Flow`
- `Expr`
- `@node` decorator

Do not add:
- External imports
- Optional features
- I/O operations
- Network calls

### Plugin Modules

Optional features go in separate files:
- `tinyagent/tracing.py` - OpenTelemetry integration
- `tinyagent/validation.py` - Graph validation
- `tinyagent/visualization.py` - Mermaid export
- `tinyagent/server.py` - Agent discovery

Plugins may have dependencies, declared in `setup.py` extras.

## Reporting Issues

Use the issue templates provided. Include:

1. TinyAgent version
2. Python version
3. Operating system
4. Minimal reproduction code
5. Expected vs actual behavior

## Code of Conduct

- Be respectful and constructive
- Focus on the technical merits
- Welcome newcomers
- Assume good intent

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
