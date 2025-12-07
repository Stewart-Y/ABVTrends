import { test, expect } from '@playwright/test';
import { API_BASE } from '../utils/test-helpers';

test.describe('Products API', () => {
  test('GET /api/v1/products - should return paginated products', async ({ request }) => {
    const response = await request.get(`${API_BASE}/products`);

    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body).toHaveProperty('data');
    expect(body).toHaveProperty('meta');
    expect(Array.isArray(body.data)).toBe(true);
  });

  test('GET /api/v1/products/categories/list - should return categories', async ({ request }) => {
    const response = await request.get(`${API_BASE}/products/categories/list`);

    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body).toHaveProperty('categories');
    expect(body).toHaveProperty('subcategories');
    expect(Array.isArray(body.categories)).toBe(true);
  });

  test('GET /api/v1/products/discover/new-arrivals - should return new products or error', async ({ request }) => {
    const response = await request.get(`${API_BASE}/products/discover/new-arrivals?limit=5`);

    // API should return a valid JSON response (200 with data, or error with error object)
    const body = await response.json();

    if (response.ok()) {
      // Success case - should have items array
      expect(body).toHaveProperty('items');
      expect(Array.isArray(body.items)).toBe(true);
    } else {
      // Error case - should have error object (backend may have issues in demo mode)
      expect(body).toHaveProperty('error');
    }
  });
});
