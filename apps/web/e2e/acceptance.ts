// The existing acceptance fixture observes every browser context.
import { test as base, expect } from '@playwright/test';
import * as fixture from '../../../scripts/acceptance.fixture.cjs';
export const test: typeof base = fixture.test;
export { expect };
export type { Page } from '@playwright/test';
