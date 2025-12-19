process.env.NEXT_IGNORE_INCORRECT_LOCKFILE = process.env.NEXT_IGNORE_INCORRECT_LOCKFILE || '1';
process.env.NEXT_SKIP_LOCKFILE_PATCH = process.env.NEXT_SKIP_LOCKFILE_PATCH || '1';
process.env.NEXT_TELEMETRY_DISABLED = process.env.NEXT_TELEMETRY_DISABLED || '1';

const nextJest = require('next/jest');

const createJestConfig = nextJest({
  dir: './',
});

const customJestConfig = {
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  testEnvironment: 'jest-environment-jsdom',
  watchman: false,
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1',
  },
  testMatch: ['**/__tests__/**/*.test.[jt]s?(x)'],
};

module.exports = createJestConfig(customJestConfig);
