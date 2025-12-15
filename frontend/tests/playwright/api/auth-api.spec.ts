import { test, expect } from '@playwright/test';
import { API_BASE } from '../utils/test-helpers';

test.describe('Auth API', () => {
  const testUser = {
    email: `test-${Date.now()}@example.com`,
    password: 'TestPassword123!',
  };

  test.describe('POST /auth/login', () => {
    test('should return 401 for invalid credentials', async ({ request }) => {
      const response = await request.post(`${API_BASE}/auth/login`, {
        data: {
          email: 'invalid@example.com',
          password: 'wrongpassword',
        },
      });

      expect(response.status()).toBe(401);
      const body = await response.json();
      expect(body.detail).toBeTruthy();
    });

    test('should return token for valid admin credentials', async ({ request }) => {
      const response = await request.post(`${API_BASE}/auth/login`, {
        data: {
          email: 'admin@abvtrends.com',
          password: 'ABVTrendsAdmin2024!',
        },
      });

      expect(response.status()).toBe(200);
      const body = await response.json();

      expect(body.access_token).toBeTruthy();
      expect(body.token_type).toBe('bearer');
      expect(body.expires_in).toBeGreaterThan(0);
      expect(body.user).toBeTruthy();
      expect(body.user.email).toBe('admin@abvtrends.com');
      expect(body.user.role).toBe('admin');
    });

    test('should return user info with token', async ({ request }) => {
      const response = await request.post(`${API_BASE}/auth/login`, {
        data: {
          email: 'admin@abvtrends.com',
          password: 'ABVTrendsAdmin2024!',
        },
      });

      expect(response.status()).toBe(200);
      const body = await response.json();

      expect(body.user.id).toBeTruthy();
      expect(body.user.email).toBe('admin@abvtrends.com');
      expect(body.user.role).toBe('admin');
      expect(body.user.is_active).toBe(true);
    });
  });

  test.describe('POST /auth/register', () => {
    test('should register a new user', async ({ request }) => {
      const response = await request.post(`${API_BASE}/auth/register`, {
        data: testUser,
      });

      // Could be 201 (created) or 400 (if user already exists from previous test run)
      if (response.status() === 201) {
        const body = await response.json();
        expect(body.id).toBeTruthy();
        expect(body.email).toBe(testUser.email);
        expect(body.role).toBe('user');
      } else {
        expect(response.status()).toBe(400);
      }
    });

    test('should return 400 for duplicate email', async ({ request }) => {
      // Try to register with existing admin email
      const response = await request.post(`${API_BASE}/auth/register`, {
        data: {
          email: 'admin@abvtrends.com',
          password: 'SomePassword123!',
        },
      });

      expect(response.status()).toBe(400);
      const body = await response.json();
      expect(body.detail).toContain('already registered');
    });

    test('should return 422 for invalid email format', async ({ request }) => {
      const response = await request.post(`${API_BASE}/auth/register`, {
        data: {
          email: 'not-an-email',
          password: 'TestPassword123!',
        },
      });

      expect(response.status()).toBe(422);
    });
  });

  test.describe('GET /auth/me', () => {
    test('should return 401 without token', async ({ request }) => {
      const response = await request.get(`${API_BASE}/auth/me`);
      expect(response.status()).toBe(401);
    });

    test('should return 401 with invalid token', async ({ request }) => {
      const response = await request.get(`${API_BASE}/auth/me`, {
        headers: {
          Authorization: 'Bearer invalid-token',
        },
      });

      expect(response.status()).toBe(401);
    });

    test('should return user info with valid token', async ({ request }) => {
      // First login to get token
      const loginResponse = await request.post(`${API_BASE}/auth/login`, {
        data: {
          email: 'admin@abvtrends.com',
          password: 'ABVTrendsAdmin2024!',
        },
      });

      const { access_token } = await loginResponse.json();

      // Now get user info
      const response = await request.get(`${API_BASE}/auth/me`, {
        headers: {
          Authorization: `Bearer ${access_token}`,
        },
      });

      expect(response.status()).toBe(200);
      const body = await response.json();

      expect(body.id).toBeTruthy();
      expect(body.email).toBe('admin@abvtrends.com');
      expect(body.role).toBe('admin');
    });
  });

  test.describe('Protected Endpoints', () => {
    test('should return 401 for scheduler status without auth', async ({ request }) => {
      const response = await request.get(`${API_BASE}/scheduler/status`);
      expect(response.status()).toBe(401);
    });

    test('should return 401 for trigger scrape without auth', async ({ request }) => {
      const response = await request.post(`${API_BASE}/distributors/libdib/scrape`);
      expect(response.status()).toBe(401);
    });

    test('should allow admin to access scheduler status', async ({ request }) => {
      // Login as admin
      const loginResponse = await request.post(`${API_BASE}/auth/login`, {
        data: {
          email: 'admin@abvtrends.com',
          password: 'ABVTrendsAdmin2024!',
        },
      });

      const { access_token } = await loginResponse.json();

      // Access scheduler status
      const response = await request.get(`${API_BASE}/scheduler/status`, {
        headers: {
          Authorization: `Bearer ${access_token}`,
        },
      });

      expect(response.status()).toBe(200);
      const body = await response.json();
      expect(body.status).toBe('ok');
      expect(body.scheduler).toBeTruthy();
    });
  });

  test.describe('API Keys', () => {
    let authToken: string;

    test.beforeAll(async ({ request }) => {
      // Login to get token
      const loginResponse = await request.post(`${API_BASE}/auth/login`, {
        data: {
          email: 'admin@abvtrends.com',
          password: 'ABVTrendsAdmin2024!',
        },
      });

      const body = await loginResponse.json();
      authToken = body.access_token;
    });

    test('should return 401 for api-keys without auth', async ({ request }) => {
      const response = await request.get(`${API_BASE}/auth/api-keys`);
      expect(response.status()).toBe(401);
    });

    test('should list API keys (may be empty)', async ({ request }) => {
      const response = await request.get(`${API_BASE}/auth/api-keys`, {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });

      expect(response.status()).toBe(200);
      const body = await response.json();
      expect(body.api_keys).toBeDefined();
      expect(Array.isArray(body.api_keys)).toBe(true);
    });

    test('should create and list API key', async ({ request }) => {
      // Create API key
      const createResponse = await request.post(`${API_BASE}/auth/api-keys`, {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
        data: {
          name: `Test Key ${Date.now()}`,
        },
      });

      expect(createResponse.status()).toBe(201);
      const createBody = await createResponse.json();

      expect(createBody.api_key).toBeTruthy();
      expect(createBody.api_key.id).toBeTruthy();
      expect(createBody.api_key.name).toContain('Test Key');
      expect(createBody.key).toBeTruthy();
      expect(createBody.key).toMatch(/^abv_/);

      // List API keys to verify
      const listResponse = await request.get(`${API_BASE}/auth/api-keys`, {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });

      const listBody = await listResponse.json();
      const foundKey = listBody.api_keys.find(
        (k: { id: string }) => k.id === createBody.api_key.id
      );
      expect(foundKey).toBeTruthy();

      // Clean up - revoke the key
      const deleteResponse = await request.delete(
        `${API_BASE}/auth/api-keys/${createBody.api_key.id}`,
        {
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        }
      );

      expect(deleteResponse.status()).toBe(200);
    });
  });
});
