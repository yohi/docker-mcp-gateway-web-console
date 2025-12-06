# Contributing to Docker MCP Gateway Console

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Coding Standards](#coding-standards)
- [Documentation](#documentation)

## Code of Conduct

This project adheres to a code of conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

### Our Standards

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on what is best for the community
- Show empathy towards other community members

## Getting Started

### Prerequisites

Before contributing, ensure you have:

- Git installed
- Node.js 18+ installed
- Python 3.11+ installed
- Docker and Docker Compose installed
- Bitwarden CLI installed
- A Bitwarden account for testing

### Finding Issues to Work On

1. Check the [Issues](repository-url/issues) page
2. Look for issues labeled `good first issue` or `help wanted`
3. Comment on the issue to let others know you're working on it
4. Wait for maintainer approval before starting work

### Reporting Bugs

Before creating a bug report:

1. Check if the bug has already been reported
2. Collect relevant information (logs, screenshots, steps to reproduce)
3. Create a detailed issue with:
   - Clear title
   - Description of the bug
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Environment details (OS, versions, etc.)

### Suggesting Features

Feature requests are welcome! Please:

1. Check if the feature has already been requested
2. Clearly describe the feature and its benefits
3. Provide examples of how it would be used
4. Be open to discussion and feedback

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR-USERNAME/docker-mcp-gateway-console.git
cd docker-mcp-gateway-console

# Add upstream remote
git remote add upstream https://github.com/ORIGINAL-OWNER/docker-mcp-gateway-console.git
```

### 2. Install Dependencies

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..

# Frontend
cd frontend
npm install
cd ..
```

### 3. Set Up Environment

```bash
# Copy environment files
cp frontend/.env.local.example frontend/.env.local
cp backend/.env.example backend/.env

# Edit with your local configuration
```

### 4. Start Development Environment

```bash
# Option 1: Using Docker Compose
docker-compose up

# Option 2: Run services separately
# Terminal 1 - Backend
cd backend
source venv/bin/activate
uvicorn app.main:app --reload

# Terminal 2 - Frontend
cd frontend
npm run dev
```

## Making Changes

### Branch Naming

Use descriptive branch names:

- `feature/add-new-catalog-filter`
- `fix/session-timeout-bug`
- `docs/update-deployment-guide`
- `refactor/improve-secret-caching`

### Commit Messages

Follow conventional commit format:

```
type(scope): subject

body (optional)

footer (optional)
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(catalog): add category filtering

Add ability to filter catalog items by multiple categories
simultaneously. Updates the search bar component and catalog
service.

Closes #123
```

```
fix(auth): resolve session timeout issue

Sessions were not properly expiring after the configured timeout.
Fixed by updating the session validation logic.

Fixes #456
```

### Making Changes

1. **Create a branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes:**
   - Write clean, readable code
   - Follow existing code style
   - Add comments for complex logic
   - Update documentation as needed

3. **Test your changes:**
   - Run all tests
   - Test manually in the UI
   - Ensure no regressions

4. **Commit your changes:**
   ```bash
   git add .
   git commit -m "feat(scope): your message"
   ```

## Testing

### Running Tests

```bash
# Backend tests
cd backend
pytest

# Frontend unit tests
cd frontend
npm test

# Frontend E2E tests
cd frontend
npm run test:e2e

# Run all tests
npm run test:all  # If available
```

### Writing Tests

#### Backend Tests (pytest)

```python
# backend/tests/test_feature.py
import pytest
from app.services.feature import FeatureService

def test_feature_functionality():
    """Test that feature works correctly"""
    service = FeatureService()
    result = service.do_something()
    assert result == expected_value
```

#### Frontend Unit Tests (Jest)

```typescript
// frontend/__tests__/components/Feature.test.tsx
import { render, screen } from '@testing-library/react';
import Feature from '@/components/Feature';

describe('Feature', () => {
  it('renders correctly', () => {
    render(<Feature />);
    expect(screen.getByText('Expected Text')).toBeInTheDocument();
  });
});
```

#### E2E Tests (Playwright)

```typescript
// frontend/e2e/feature.spec.ts
import { test, expect } from '@playwright/test';

test('feature workflow', async ({ page }) => {
  await page.goto('/');
  await page.click('button[data-testid="feature-button"]');
  await expect(page.locator('.result')).toBeVisible();
});
```

### Test Coverage

- Aim for at least 80% code coverage
- All new features should include tests
- Bug fixes should include regression tests

## Submitting Changes

### Pull Request Process

1. **Update your branch:**
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Push to your fork:**
   ```bash
   git push origin feature/your-feature-name
   ```

3. **Create Pull Request:**
   - Go to GitHub and create a PR
   - Fill out the PR template
   - Link related issues
   - Request review from maintainers

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] E2E tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests added/updated
```

### Review Process

1. Maintainers will review your PR
2. Address any feedback or requested changes
3. Once approved, your PR will be merged
4. Your contribution will be credited

## Coding Standards

### Python (Backend)

- Follow PEP 8 style guide
- Use type hints
- Maximum line length: 100 characters
- Use meaningful variable names
- Add docstrings to functions and classes

```python
from typing import Optional

def process_secret(secret_ref: str, session_id: str) -> Optional[str]:
    """
    Process a Bitwarden secret reference.
    
    Args:
        secret_ref: Bitwarden reference notation
        session_id: User session identifier
        
    Returns:
        Resolved secret value or None if not found
    """
    # Implementation
    pass
```

### TypeScript (Frontend)

- Use TypeScript strict mode
- Follow Airbnb style guide
- Use functional components with hooks
- Prefer const over let
- Use meaningful variable names

```typescript
interface ContainerConfig {
  name: string;
  image: string;
  env: Record<string, string>;
}

const createContainer = async (config: ContainerConfig): Promise<string> => {
  // Implementation
  return containerId;
};
```

### Code Formatting

```bash
# Backend (Black)
cd backend
black app/ tests/

# Frontend (Prettier)
cd frontend
npm run format
```

### Linting

```bash
# Backend (Flake8)
cd backend
flake8 app/ tests/

# Frontend (ESLint)
cd frontend
npm run lint
```

## Documentation

### Code Documentation

- Add comments for complex logic
- Use docstrings for Python functions
- Use JSDoc for TypeScript functions
- Keep comments up to date

### User Documentation

When adding features, update:

- README.md
- Relevant docs in `docs/` directory
- API documentation (if applicable)
- Inline help text in the UI

### Documentation Style

- Use clear, concise language
- Include code examples
- Add screenshots for UI features
- Keep formatting consistent

## Project Structure

```
docker-mcp-gateway-console/
├── backend/              # Python FastAPI backend
│   ├── app/
│   │   ├── api/         # API endpoints
│   │   ├── models/      # Data models
│   │   ├── services/    # Business logic
│   │   └── main.py      # Application entry
│   └── tests/           # Backend tests
├── frontend/            # Next.js frontend
│   ├── app/            # Next.js pages
│   ├── components/     # React components
│   ├── lib/            # Utilities
│   └── __tests__/      # Frontend tests
├── docs/               # Documentation
└── docker-compose.yml  # Development environment
```

## Getting Help

- **Questions**: Open a discussion on GitHub
- **Issues**: Create an issue with details
- **Chat**: Join our community chat (if available)
- **Email**: Contact maintainers (if provided)

## Recognition

Contributors will be:

- Listed in CONTRIBUTORS.md
- Credited in release notes
- Mentioned in project documentation

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

## Thank You!

Your contributions make this project better for everyone. We appreciate your time and effort!
