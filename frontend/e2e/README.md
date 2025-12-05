# E2E Tests

End-to-end tests for Docker MCP Gateway Console using Playwright.

## Overview

These tests verify the complete user workflows including:
- Authentication flow (login/logout)
- Catalog browsing and server selection
- Container lifecycle management
- MCP Inspector functionality

## Running Tests

### Prerequisites

1. Install dependencies:
```bash
npm install
```

2. Install Playwright browsers:
```bash
npx playwright install
```

### Run All Tests

```bash
# Run all tests in headless mode
npm run test:e2e

# Run tests with UI mode (interactive)
npm run test:e2e:ui

# Run tests in headed mode (see browser)
npm run test:e2e:headed
```

### Run Specific Tests

```bash
# Run only authentication tests
npx playwright test auth.spec.ts

# Run only catalog tests
npx playwright test catalog.spec.ts

# Run only container tests
npx playwright test containers.spec.ts

# Run only inspector tests
npx playwright test inspector.spec.ts
```

### Debug Tests

```bash
# Run tests in debug mode
npx playwright test --debug

# Run specific test in debug mode
npx playwright test auth.spec.ts --debug
```

## Test Structure

```
e2e/
├── auth.spec.ts          # Authentication flow tests
├── catalog.spec.ts       # Catalog browsing tests
├── containers.spec.ts    # Container management tests
├── inspector.spec.ts     # MCP Inspector tests
├── helpers.ts            # Shared helper functions
└── README.md            # This file
```

## Test Configuration

Configuration is in `playwright.config.ts`:
- Base URL: `http://localhost:3000` (configurable via `PLAYWRIGHT_BASE_URL`)
- Browsers: Chromium, Firefox, WebKit
- Retries: 2 on CI, 0 locally
- Screenshots: On failure only
- Traces: On first retry

## Writing Tests

### Best Practices

1. **Use semantic selectors**: Prefer `getByRole`, `getByLabel`, `getByText` over CSS selectors
2. **Wait for state**: Use `waitForLoadState('networkidle')` when needed
3. **Handle async operations**: Always await async operations
4. **Mock external dependencies**: Use route mocking for API calls when needed
5. **Test user flows**: Focus on complete user workflows, not individual components

### Example Test

```typescript
import { test, expect } from '@playwright/test';

test('should complete user flow', async ({ page }) => {
  // Navigate to page
  await page.goto('/');
  
  // Interact with UI
  await page.getByLabel('Email').fill('user@example.com');
  await page.getByRole('button', { name: 'Login' }).click();
  
  // Assert outcome
  await expect(page).toHaveURL('/dashboard');
});
```

### Using Helpers

```typescript
import { mockAuthentication, mockCatalogData } from './helpers';

test('should work with mocked data', async ({ page }) => {
  // Mock authentication
  await mockAuthentication(page);
  
  // Mock catalog data
  await mockCatalogData(page);
  
  // Test with mocked data
  await page.goto('/catalog');
  await expect(page.getByText('Test MCP Server')).toBeVisible();
});
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: 18
      
      - name: Install dependencies
        run: npm ci
      
      - name: Install Playwright browsers
        run: npx playwright install --with-deps
      
      - name: Run E2E tests
        run: npm run test:e2e
        env:
          CI: true
      
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: playwright-report/
```

## Troubleshooting

### Tests Failing Locally

1. **Check if dev server is running**: Tests expect the app at `http://localhost:3000`
2. **Clear browser cache**: `npx playwright clean`
3. **Update browsers**: `npx playwright install`
4. **Check for port conflicts**: Ensure port 3000 is available

### Flaky Tests

1. **Add explicit waits**: Use `waitForLoadState` or `waitForSelector`
2. **Increase timeouts**: Add `{ timeout: 10000 }` to assertions
3. **Check for race conditions**: Ensure proper sequencing of operations
4. **Use retry logic**: Configure retries in `playwright.config.ts`

### Debugging Tips

1. **Use UI mode**: `npm run test:e2e:ui` for interactive debugging
2. **Add screenshots**: Tests automatically capture screenshots on failure
3. **Enable trace**: Traces are captured on first retry
4. **Use console logs**: Add `console.log` statements in tests
5. **Slow down execution**: Use `page.waitForTimeout(1000)` to observe behavior

## Test Coverage

Current test coverage includes:

- ✅ Authentication flow (login, logout, session validation)
- ✅ Protected route access control
- ✅ Catalog browsing and searching
- ✅ Catalog filtering by category
- ✅ Container list display
- ✅ Container creation and configuration
- ✅ Container operations (start, stop, restart, delete)
- ✅ Container log viewing
- ✅ MCP Inspector (tools, resources, prompts)
- ✅ Error handling and user feedback

## Future Improvements

- [ ] Add visual regression testing
- [ ] Add performance testing
- [ ] Add accessibility testing
- [ ] Add mobile viewport testing
- [ ] Add cross-browser compatibility tests
- [ ] Add API contract testing
- [ ] Add load testing scenarios

## Resources

- [Playwright Documentation](https://playwright.dev)
- [Best Practices](https://playwright.dev/docs/best-practices)
- [Debugging Guide](https://playwright.dev/docs/debug)
- [CI/CD Guide](https://playwright.dev/docs/ci)
