import fs from 'fs';
import path from 'path';

type DependencyMap = Record<string, string>;

const pkgPath = path.join(__dirname, '..', '..', 'package.json');
const pkgJson = JSON.parse(fs.readFileSync(pkgPath, 'utf8')) as {
  dependencies: DependencyMap;
  devDependencies: DependencyMap;
};

const expectedRuntimeDeps: DependencyMap = {
  next: '15.5.9',
  react: '19.2.3',
  'react-dom': '19.2.3',
  swr: '2.3.8',
};

const expectedDevDeps: DependencyMap = {
  '@types/react': '19.2.7',
  '@types/react-dom': '19.2.3',
  'eslint-config-next': '15.5.9',
  typescript: '5.9.3',
};

const expectNoRanges = (deps: DependencyMap) => {
  const ranged = Object.entries(deps).filter(([, version]) => /^[~^]/.test(version));
  expect(ranged).toEqual([]);
};

describe('frontend dependency pinning', () => {
  it('pins runtime dependencies to the required versions', () => {
    expect(pkgJson.dependencies).toMatchObject(expectedRuntimeDeps);
  });

  it('pins dev dependencies to the required versions and Next.js tooling alignment', () => {
    expect(pkgJson.devDependencies).toMatchObject(expectedDevDeps);
    expect(pkgJson.devDependencies['eslint-config-next']).toBe(pkgJson.dependencies.next);
    expect(pkgJson.devDependencies['@types/node']).toMatch(/^22\./);
  });

  it('does not allow range specifiers in dependency versions', () => {
    expectNoRanges(pkgJson.dependencies);
    expectNoRanges(pkgJson.devDependencies);
  });
});
