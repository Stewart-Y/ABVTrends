import { test, expect } from '@playwright/test';
import { API_BASE } from '../utils/test-helpers';

test.describe('Trends API', () => {
  test('GET /api/v1/trends - should return paginated trends', async ({ request }) => {
    const response = await request.get(`${API_BASE}/trends`);

    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body).toHaveProperty('data');
    expect(body).toHaveProperty('meta');
    expect(body.meta).toHaveProperty('page');
    expect(body.meta).toHaveProperty('per_page');
    expect(body.meta).toHaveProperty('total');
    expect(Array.isArray(body.data)).toBe(true);
  });

  test('GET /api/v1/trends/top - should return top trends by tier', async ({ request }) => {
    const response = await request.get(`${API_BASE}/trends/top`);

    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body).toHaveProperty('viral');
    expect(body).toHaveProperty('trending');
    expect(body).toHaveProperty('emerging');
    expect(body).toHaveProperty('generated_at');
    expect(Array.isArray(body.viral)).toBe(true);
    expect(Array.isArray(body.trending)).toBe(true);
    expect(Array.isArray(body.emerging)).toBe(true);
  });

  test('GET /api/v1/trends with filters - should apply category filter', async ({ request }) => {
    const response = await request.get(`${API_BASE}/trends?category=spirits`);

    expect(response.status()).toBe(200);

    const body = await response.json();
    // All returned items should be spirits category
    for (const item of body.data) {
      if (item.category) {
        expect(item.category).toBe('spirits');
      }
    }
  });
});
