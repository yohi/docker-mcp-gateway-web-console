# Integration and E2E Testing Guide

This document provides comprehensive information about integration and end-to-end testing for the Docker MCP Gateway Console.

## Overview

The project uses a multi-layered testing approach:

1. **Unit Tests**: Test individual components and functions in isolation
2. **Integration Tests**: Test interactions between components and services
3. **E2E Tests**: Test complete user workflows from browser to backend

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    E2E Tests (Playwright)                │
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │         Browser Automation                       │   │
│  │  - User interactions                             │   │
│  │  - Visual verification                           │   │
│  │  - Network mocking                               │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Frontend (Next.js + React)                  │
│                                                           │
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │  Unit Tests      │  │  Component Tests │            │
│  │  (Jest)          │  │  (React Testing) │            │
│  └──────────────────┘  └──────────────────┘            │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Backend (FastAPI + Python)                  │
│                                                           │
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │  Unit Tests      │  │  Integration     │            │
│  │  (pytest)        │  │  Tests (pytest)  │            │
│  └──────────────────┘  └──────────────────┘            │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│         External Services (Docker, Bitwarden)            │
└─────────────────────────────────────────────────────────┘
```

## E2E Testing with Playwright

### Setup

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Install Playwright browsers:
```bash
npx playwright install --with-deps
```

### Running Tests

#### Local Development

```bash
# Start the application
docker-compose up -d

# Run E2E tests
cd frontend
npm run test:e2e
```

#### With Test Environment

```bash
# Use the test script (recommended)
./scripts/run-e2e-tests.sh

# Or manually
docker-compose -f docker-compose.test.yml up -d frontend backend
cd frontend
npm run test:e2e
```

#### Interactive Mode

```bash
# UI mode (best for development)
npm run test:e2e:ui

# Headed mode (see browser)
npm run test:e2e:headed

# Debug mode
npx playwright test --debug
```

### Test Structure

```
frontend/e2e/
├── auth.spec.ts          # Authentication flows
├── catalog.spec.ts       # Catalog browsing
├── containers.spec.ts    # Container management
├── inspector.spec.ts     # MCP Inspector
├── helpers.ts            # Shared utilities
└── README.md            # Detailed documentation
```

### Writing E2E Tests

#### Basic Test Structure

```typescript
import { test, expect } from '@playwright/test';

test.describe('Feature Name', () => {
  test.beforeEach(async ({ page }) => {
    // Setup before each test
    await page.goto('/');
  });

  test('should do something', async ({ page }) => {
    // Arrange
    await page.getByLabel('Input').fill('value');
    
    // Act
    await page.getByRole('button', { name: 'Submit' }).click();
    
    // Assert
    await expect(page).toHaveURL('/success');
  });
});
```

#### Using Mocks

```typescript
import { mockAuthentication, mockCatalogData } from './helpers';

test('should work with mocked data', async ({ page }) => {
  // Mock authentication
  await mockAuthentication(page);
  
  // Mock API responses
  await page.route('**/api/catalog', route => {
    route.fulfill({
      status: 200,
      body: JSON.stringify({ servers: [] })
    });
  });
  
  // Test with mocked data
  await page.goto('/catalog');
});
```

### Best Practices

1. **Use Semantic Selectors**
   - ✅ `page.getByRole('button', { name: 'Login' })`
   - ✅ `page.getByLabel('Email')`
   - ❌ `page.locator('.btn-primary')`

2. **Wait for State**
   ```typescript
   await page.waitForLoadState('networkidle');
   await page.waitForURL('/dashboard');
   ```

3. **Handle Async Operations**
   ```typescript
   await expect(page.getByText('Success')).toBeVisible({ timeout: 5000 });
   ```

4. **Test User Flows, Not Implementation**
   - Focus on what users do, not how it's implemented
   - Test complete workflows from start to finish

5. **Keep Tests Independent**
   - Each test should be able to run in isolation
   - Don't rely on test execution order

## Integration Testing

### Backend Integration Tests

Located in `backend/tests/`, these tests verify:
- API endpoint functionality
- Service layer interactions
- Database operations
- External service integrations

#### Running Backend Tests

```bash
cd backend
pytest

# With coverage
pytest --cov=app --cov-report=html

# Specific test file
pytest tests/test_auth.py

# Specific test
pytest tests/test_auth.py::test_login_success
```

### Frontend Integration Tests

Located in `frontend/__tests__/`, these tests verify:
- Component interactions
- Context providers
- API client functions
- Form submissions

#### Running Frontend Tests

```bash
cd frontend
npm test

# Watch mode
npm run test:watch

# With coverage
npm test -- --coverage
```

## Docker Compose Configurations

### Development (`docker-compose.yml`)

- Standard development environment
- Hot reloading enabled
- Ports: 3000 (frontend), 8000 (backend)

### Testing (`docker-compose.test.yml`)

- Isolated test environment
- Different ports to avoid conflicts
- Health checks for service readiness
- Ports: 3001 (frontend), 8001 (backend)

### Usage

```bash
# Development
docker-compose up

# Testing
docker-compose -f docker-compose.test.yml up

# Cleanup
docker-compose down -v
docker-compose -f docker-compose.test.yml down -v
```

## CI/CD Integration

### GitHub Actions

The project includes a GitHub Actions workflow (`.github/workflows/e2e-tests.yml`) that:

1. Sets up Node.js and Python environments
2. Installs dependencies
3. Starts Docker Compose services
4. Runs E2E tests
5. Uploads test reports and artifacts
6. Shows logs on failure

### Running in CI

```yaml
# .github/workflows/e2e-tests.yml
- name: Run E2E tests
  run: npm run test:e2e
  env:
    CI: true
    PLAYWRIGHT_BASE_URL: http://localhost:3001
```

## Test Data Management

### Mock Data

For E2E tests, use the helper functions in `frontend/e2e/helpers.ts`:

```typescript
// Mock authentication
await mockAuthentication(page);

// Mock catalog data
await mockCatalogData(page);

// Mock container list
await mockContainerList(page, [
  { id: 'test-1', name: 'test-container', status: 'running' }
]);

// Mock inspector data
await mockInspectorData(page, 'container-id');
```

### Test Credentials

For integration tests that require real Bitwarden access:

1. Create a test Bitwarden account
2. Store credentials in environment variables
3. Use separate vault for test data
4. Never commit credentials to repository

```bash
# .env.test
BITWARDEN_TEST_EMAIL=test@example.com
BITWARDEN_TEST_API_KEY=test-api-key
```

## Debugging

### Playwright Debugging

```bash
# UI mode (interactive)
npm run test:e2e:ui

# Debug mode (step through)
npx playwright test --debug

# Specific test in debug mode
npx playwright test auth.spec.ts --debug

# Show browser
npm run test:e2e:headed
```

### Viewing Test Reports

```bash
# After test run
npx playwright show-report

# Open specific report
npx playwright show-report playwright-report/
```

### Analyzing Failures

1. **Screenshots**: Automatically captured on failure
2. **Traces**: Captured on first retry
3. **Videos**: Optional, configure in `playwright.config.ts`
4. **Logs**: Check Docker Compose logs

```bash
# View logs
docker-compose -f docker-compose.test.yml logs backend
docker-compose -f docker-compose.test.yml logs frontend

# Follow logs
docker-compose -f docker-compose.test.yml logs -f
```

## Performance Testing

### Load Testing

For load testing, consider using:
- [k6](https://k6.io/) for API load testing
- [Lighthouse](https://developers.google.com/web/tools/lighthouse) for frontend performance

### Example k6 Script

```javascript
import http from 'k6/http';
import { check } from 'k6';

export let options = {
  vus: 10,
  duration: '30s',
};

export default function() {
  let res = http.get('http://localhost:8000/api/catalog?source=test');
  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });
}
```

## Troubleshooting

### Common Issues

#### Tests Failing Locally

1. **Port conflicts**: Check if ports 3000/8000 are in use
2. **Stale containers**: Run `docker-compose down -v`
3. **Browser issues**: Run `npx playwright install`
4. **Cache issues**: Clear `.next` and `node_modules`

#### Flaky Tests

1. Add explicit waits: `waitForLoadState('networkidle')`
2. Increase timeouts: `{ timeout: 10000 }`
3. Check for race conditions
4. Use retry logic in config

#### CI Failures

1. Check GitHub Actions logs
2. Download test artifacts
3. Review screenshots and traces
4. Verify environment variables

### Getting Help

1. Check [Playwright documentation](https://playwright.dev)
2. Review test logs and reports
3. Check Docker Compose logs
4. Open an issue with:
   - Test output
   - Screenshots/traces
   - Environment details

## Maintenance

### Updating Dependencies

```bash
# Frontend
cd frontend
npm update
npx playwright install

# Backend
cd backend
pip install --upgrade -r requirements.txt
```

### Updating Tests

When adding new features:

1. Write E2E tests for user workflows
2. Write integration tests for API endpoints
3. Write unit tests for business logic
4. Update test documentation

### Test Coverage Goals

- Unit tests: 80%+ coverage
- Integration tests: Key workflows covered
- E2E tests: Critical user paths covered

## Resources

- [Playwright Documentation](https://playwright.dev)
- [Jest Documentation](https://jestjs.io)
- [pytest Documentation](https://docs.pytest.org)
- [Docker Compose Documentation](https://docs.docker.com/compose)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
