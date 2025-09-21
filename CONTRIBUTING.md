# Contributing to IMAP Mail Cleanup

Thank you for your interest in contributing to IMAP Mail Cleanup! This document provides guidelines for contributing to the project.

## Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/your-username/imap-mail-cleanup.git
   cd imap-mail-cleanup
   ```

2. **Set up development environment**
   ```bash
   pip install -r requirements.txt
   pip install -e .  # Install in development mode
   ```

3. **Set up pre-commit hooks** (optional but recommended)
   ```bash
   pip install pre-commit
   pre-commit install
   ```

## Project Structure

```
├── imap_cleanup/          # Main package
│   ├── __init__.py       # Package exports
│   ├── config.py         # Configuration management
│   ├── imap_manager.py   # IMAP operations
│   ├── email_analyzer.py # Email analysis logic
│   ├── email_processor.py # Main orchestrator
│   ├── cli.py           # CLI interface
│   └── gui_interface.py  # GUI interface
├── examples/             # Usage examples
├── tests/               # Test suite
├── docs/                # Documentation
└── legacy/              # Old implementations
```

## Code Style

- **Type hints**: Use type hints for all function parameters and return values
- **Docstrings**: Include comprehensive docstrings for all classes and methods
- **PEP 8**: Follow Python PEP 8 style guidelines
- **Single responsibility**: Each class should have one clear purpose

## Testing

Run tests with:

```bash
# Run configuration tests
cd tests && python -c "import sys; sys.path.append('..'); import test_config; test_config.main()"

# Run basic functionality test
python examples/basic_usage.py
```

## Submitting Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow the code style guidelines
   - Add tests for new functionality
   - Update documentation as needed

3. **Test your changes**
   ```bash
   python tests/test_config.py
   python examples/basic_usage.py
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

5. **Push and create a pull request**
   ```bash
   git push origin feature/your-feature-name
   ```

## Commit Message Format

Use conventional commits:

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `style:` - Code style changes
- `refactor:` - Code refactoring
- `test:` - Adding tests
- `chore:` - Maintenance tasks

## Areas for Contribution

- **GUI Implementation**: Build desktop applications using the GUI interface
- **Additional Email Providers**: Extend support beyond iCloud
- **Performance Optimizations**: Improve threading and connection management
- **Enhanced Filtering**: Add more sophisticated email analysis
- **Documentation**: Improve guides and examples
- **Testing**: Expand test coverage

## Questions?

Feel free to open an issue for any questions about contributing!