/** @type {import('ts-jest').JestConfigWithTsJest} */
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  testMatch: ['<rootDir>/tests/**/*.test.ts'],
  collectCoverageFrom: ['src/sdk/**/*.ts'],
  coverageThreshold: {
    global: { lines: 75, functions: 75, branches: 60, statements: 75 }
  }
};
