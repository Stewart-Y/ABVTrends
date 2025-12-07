/**
 * ABVTrends API Client
 *
 * Typed API client for communicating with the FastAPI backend.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

// Types

export interface Product {
  id: string;
  name: string;
  brand: string | null;
  category: string;
  subcategory: string | null;
  description: string | null;
  image_url: string | null;
  created_at: string;
  updated_at: string;
  latest_score: number | null;
}

export interface TrendingProduct {
  id: string;
  name: string;
  brand: string | null;
  category: string;
  subcategory: string | null;
  image_url: string | null;
  trend_score: number;
  trend_tier: 'viral' | 'trending' | 'emerging' | 'stable' | 'declining';
  score_change_24h: number | null;
  score_change_7d: number | null;
  component_breakdown: {
    media: number;
    social: number;
    retailer: number;
    price: number;
    search: number;
    seasonal: number;
  };
}

export interface TrendScore {
  id: string;
  product_id: string;
  score: number;
  media_score: number;
  social_score: number;
  retailer_score: number;
  price_score: number;
  search_score: number;
  seasonal_score: number;
  signal_count: number;
  calculated_at: string;
  trend_tier: string;
}

export interface Forecast {
  id: string;
  product_id: string;
  forecast_date: string;
  predicted_score: number;
  confidence_lower_80: number | null;
  confidence_upper_80: number | null;
  confidence_lower_95: number | null;
  confidence_upper_95: number | null;
  model_version: string;
}

export interface PaginationMeta {
  page: number;
  per_page: number;
  total: number;
  total_pages?: number;
}

export interface ApiResponse<T> {
  data: T;
  meta?: PaginationMeta;
  generated_at?: string;
}

export interface TopTrends {
  viral: TrendingProduct[];
  trending: TrendingProduct[];
  emerging: TrendingProduct[];
  generated_at: string;
}

// API Functions

async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `API Error: ${response.status}`);
  }

  return response.json();
}

// Trends API

export async function getTrendingProducts(params?: {
  page?: number;
  per_page?: number;
  category?: string;
  min_score?: number;
}): Promise<ApiResponse<TrendingProduct[]>> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set('page', params.page.toString());
  if (params?.per_page) searchParams.set('per_page', params.per_page.toString());
  if (params?.category) searchParams.set('category', params.category);
  if (params?.min_score) searchParams.set('min_score', params.min_score.toString());

  const query = searchParams.toString();
  return fetchApi(`/trends${query ? `?${query}` : ''}`);
}

export async function getTopTrends(): Promise<TopTrends> {
  return fetchApi('/trends/top');
}

export async function getProductTrend(productId: string): Promise<TrendScore> {
  return fetchApi(`/trends/${productId}`);
}

export async function getTrendHistory(
  productId: string,
  days: number = 30
): Promise<{ scores: TrendScore[]; product_name: string }> {
  return fetchApi(`/trends/${productId}/history?days=${days}`);
}

// Products API

export async function getProducts(params?: {
  page?: number;
  per_page?: number;
  category?: string;
  search?: string;
}): Promise<ApiResponse<Product[]>> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set('page', params.page.toString());
  if (params?.per_page) searchParams.set('per_page', params.per_page.toString());
  if (params?.category) searchParams.set('category', params.category);
  if (params?.search) searchParams.set('search', params.search);

  const query = searchParams.toString();
  return fetchApi(`/products${query ? `?${query}` : ''}`);
}

export async function getProduct(productId: string): Promise<Product> {
  return fetchApi(`/products/${productId}`);
}

export async function getProductSignals(
  productId: string,
  page: number = 1
): Promise<ApiResponse<any[]>> {
  return fetchApi(`/products/${productId}/signals?page=${page}`);
}

export interface TrendSummary {
  summary: string;
  key_points: string[];
  signal_count: number;
  celebrity_affiliation: string | null;
  launch_date: string | null;
  region_focus: string | null;
  trend_driver: string;
  days_active: number;
  sources_count: number;
}

export async function getProductTrendSummary(
  productId: string
): Promise<TrendSummary> {
  return fetchApi(`/products/${productId}/trend-summary`);
}

// Discover API

export interface DiscoverProduct {
  id: string;
  name: string;
  brand: string | null;
  category: string;
  image_url: string | null;
  score: number | null;
  trend_tier: string | null;
  created_at?: string;
  celebrity_affiliation?: string | null;
  signal_count?: number;
  recent_signal_count?: number;
}

export async function getNewArrivals(limit: number = 12): Promise<{ items: DiscoverProduct[] }> {
  return fetchApi(`/products/discover/new-arrivals?limit=${limit}`);
}

export async function getCelebrityBottles(limit: number = 12): Promise<{ items: DiscoverProduct[] }> {
  return fetchApi(`/products/discover/celebrity-bottles?limit=${limit}`);
}

export async function getEarlyMovers(limit: number = 12): Promise<{ items: DiscoverProduct[] }> {
  return fetchApi(`/products/discover/early-movers?limit=${limit}`);
}

// Forecasts API

export async function getProductForecast(productId: string): Promise<{
  product_id: string;
  product_name: string;
  current_score: number;
  forecasts: Forecast[];
  model_version: string;
  generated_at: string;
}> {
  return fetchApi(`/forecasts/${productId}`);
}

export async function generateForecast(
  productId: string,
  horizonDays: number = 7
): Promise<any> {
  return fetchApi(`/forecasts/${productId}/generate?horizon_days=${horizonDays}`, {
    method: 'POST',
  });
}

// Categories

export async function getCategories(): Promise<{
  categories: string[];
  subcategories: Record<string, string[]>;
}> {
  return fetchApi('/products/categories/list');
}

// Signals

export interface Signal {
  id: string;
  signal_type: string;
  title: string;
  url: string;
  captured_at: string;
  raw_data: any;
  source_id: string;
  product_id: string | null;
}

export async function getRecentSignals(limit: number = 10): Promise<ApiResponse<Signal[]>> {
  return fetchApi(`/signals?limit=${limit}`);
}
