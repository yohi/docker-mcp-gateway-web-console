import fs from 'fs';
import path from 'path';
import { TransformStream } from 'stream/web';
import type { PlaywrightTestConfig } from '@playwright/test';

if (!(global as { TransformStream?: unknown }).TransformStream) {
  (global as { TransformStream?: unknown }).TransformStream = TransformStream;
}

const playwrightConfig: PlaywrightTestConfig =
  require('../../playwright.config').default;

const repoRoot = path.resolve(__dirname, '..', '..', '..');
const composeFiles = [
  { path: path.join(repoRoot, 'docker-compose.yml'), label: 'docker-compose.yml' },
  {
    path: path.join(repoRoot, '.devcontainer', 'docker-compose.devcontainer.yml'),
    label: '.devcontainer/docker-compose.devcontainer.yml',
  },
];

describe('E2E configuration', () => {
  it('ensures Playwright runs headless chromium with explicit viewport and trace', () => {
    expect(playwrightConfig.use?.headless).toBe(true);
    expect(playwrightConfig.use?.viewport).toEqual({ width: 1280, height: 720 });
    expect(playwrightConfig.use?.trace).toBe('on-first-retry');
  });

  it('ensures frontend compose services allocate shared memory for chromium', () => {
    composeFiles.forEach(({ path: filePath, label }) => {
      const content = fs.readFileSync(filePath, 'utf-8').replace(/\r\n/g, '\n');
      const match = /frontend:\n((?:[ \t]+.*\n)+)/.exec(content);
      expect(match).not.toBeNull();
      const section = match ? match[1] : '';
      expect(section).toMatch(
        /shm_size:\s*1gb\s+#\s*Chromium requires at least 1GB shared memory for E2E tests/i,
      );
    });
  });
});
