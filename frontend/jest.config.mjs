import jpa from 'jest-preset-angular/presets/index.js';

const { createEsmPreset } = jpa;

/** @type {import("jest").Config} **/
export default {
  ...createEsmPreset(),
  testEnvironment: 'jsdom',
  testMatch: ['**/*.spec.ts'],
  moduleNameMapper: {
    '^tslib$': 'tslib/tslib.js',
    '^rxjs': '<rootDir>/node_modules/rxjs/dist/bundles/rxjs.umd.js',
    '^@app/(.*)$': '<rootDir>/src/app/$1',
    '^@shared/(.*)$': '<rootDir>/src/app/shared/$1',
    '^@styles/(.*)$': '<rootDir>/src/styles/$1',
    '^@environments/(.*)$': '<rootDir>/src/environments/$1',
  },
  setupFilesAfterEnv: ['<rootDir>/src/test-setup.ts'],
  collectCoverageFrom: [
    'src/app/**/*.ts',
    '!src/app/**/*.spec.ts',
    '!src/main.ts',
  ],
  coverageDirectory: 'coverage',
  coverageReporters: ['lcov', 'text', 'html'],
};