import fs from 'fs';
import path from 'path';

const BASE_IMAGE = 'node:22.12.0-alpine';
const PRODUCTION_STAGE_REGEX = /FROM node:22\.12\.0-alpine AS (deps|builder|runner)/g;

describe('Frontend Dockerfile base image pinning', () => {
  const dockerfilePath = path.join(process.cwd(), 'Dockerfile');
  const dockerfileDevPath = path.join(process.cwd(), 'Dockerfile.dev');

  it('uses Node 22.12.0-alpine for all stages in the production Dockerfile', () => {
    const content = fs.readFileSync(dockerfilePath, 'utf8');
    const matches = content.match(PRODUCTION_STAGE_REGEX) ?? [];

    expect(matches).toHaveLength(3);
    expect(content).not.toMatch(/FROM node:18/);
  });

  it('uses Node 22.12.0-alpine as the base for the development Dockerfile', () => {
    const content = fs.readFileSync(dockerfileDevPath, 'utf8').trim();

    expect(content.startsWith(`FROM ${BASE_IMAGE}`)).toBe(true);
    expect(content).not.toMatch(/FROM node:18/);
  });
});
