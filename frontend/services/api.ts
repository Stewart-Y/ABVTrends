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
  score_change_24h?: number;
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
  items?: T;
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
  tier?: string;
  limit?: number;
  offset?: number;
}): Promise<ApiResponse<TrendingProduct[]>> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set('page', params.page.toString());
  if (params?.per_page) searchParams.set('per_page', params.per_page.toString());
  if (params?.category) searchParams.set('category', params.category);
  if (params?.min_score) searchParams.set('min_score', params.min_score.toString());
  if (params?.tier) searchParams.set('tier', params.tier);
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.offset) searchParams.set('offset', params.offset.toString());

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

// =============================================================================
// Phase 7: Distributor Data API Functions
// =============================================================================

// Distributor Types

export interface DistributorPrice {
  price: number;
  price_type: string;
  currency: string;
  recorded_at: string;
}

export interface DistributorPriceHistory {
  distributor: string;
  slug: string;
  prices: DistributorPrice[];
}

export interface ProductPricesResponse {
  product_id: string;
  product_name: string;
  days: number;
  distributors: DistributorPriceHistory[];
  stats: {
    current: number;
    min: number;
    max: number;
    avg: number;
    change_pct: number;
  } | null;
  total_records: number;
}

export interface DistributorAvailability {
  distributor: string;
  slug: string;
  website: string | null;
  external_id: string;
  external_url: string | null;
  in_stock: boolean | null;
  quantity: number | null;
  available_states: string[] | null;
  last_updated: string | null;
  price: number | null;
  price_type: string | null;
}

export interface ProductAvailabilityResponse {
  product_id: string;
  product_name: string;
  distributor_count: number;
  distributors: DistributorAvailability[];
}

export interface ProductHistoryResponse {
  product_id: string;
  product_name: string;
  days: number;
  current_score: {
    score: number | null;
    tier: string | null;
    momentum: string | null;
    retail_score: number | null;
    price_score: number | null;
    inventory_score: number | null;
  } | null;
  trends: Array<{ type: string; value: number; timestamp: string }>;
  prices: Array<{ type: string; value: number; timestamp: string }>;
  inventory: Array<{ type: string; value: number; in_stock: boolean; timestamp: string }>;
}

export interface DistributorArrival {
  product_id: string;
  product_name: string;
  brand: string | null;
  category: string | null;
  image_url: string | null;
  distributor: string;
  added_at: string;
  external_url: string | null;
  score: number | null;
  tier: string | null;
}

export interface ScraperHealth {
  distributor: string;
  slug: string;
  status: 'healthy' | 'stale' | 'failed' | 'unknown';
  last_run_at: string | null;
  hours_since_run: number | null;
  is_running: boolean;
}

export interface ScraperHealthResponse {
  overall_healthy: boolean;
  healthy_count: number;
  total_count: number;
  scrapers: ScraperHealth[];
  alerts: Array<{
    type: string;
    distributor: string;
    hours_since_run?: number;
    error?: string;
  }>;
  checked_at: string;
}

export interface ScrapeRun {
  id: string;
  distributor: string;
  distributor_slug: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  products_found: number | null;
  products_new: number | null;
  products_updated: number | null;
  error_count: number | null;
}

export interface Distributor {
  id: string;
  name: string;
  slug: string;
  website_url: string | null;
  is_active: boolean;
  scraper_class: string | null;
  last_scrape_at: string | null;
  last_scrape_status: string | null;
  products_count: number | null;
}

// Distributor API Functions

export async function getProductPrices(
  productId: string,
  days: number = 30
): Promise<ProductPricesResponse> {
  return fetchApi(`/products/${productId}/prices?days=${days}`);
}

export async function getProductAvailability(
  productId: string
): Promise<ProductAvailabilityResponse> {
  return fetchApi(`/products/${productId}/availability`);
}

export async function getProductHistory(
  productId: string,
  days: number = 30
): Promise<ProductHistoryResponse> {
  return fetchApi(`/products/${productId}/history?days=${days}`);
}

export async function getDistributorArrivals(
  days: number = 7,
  limit: number = 20
): Promise<{ days: number; items: DistributorArrival[] }> {
  return fetchApi(`/products/discover/distributor-arrivals?days=${days}&limit=${limit}`);
}

export async function getScraperHealth(): Promise<ScraperHealthResponse> {
  return fetchApi('/distributors/scraper/health');
}

export async function getRecentScrapeRuns(
  limit: number = 20,
  distributor?: string
): Promise<{ runs: ScrapeRun[] }> {
  const params = new URLSearchParams();
  params.set('limit', limit.toString());
  if (distributor) params.set('distributor', distributor);
  return fetchApi(`/distributors/scraper/runs?${params.toString()}`);
}

export async function getDistributors(
  activeOnly: boolean = true
): Promise<{ distributors: Distributor[]; total: number }> {
  return fetchApi(`/distributors?active_only=${activeOnly}`);
}

export async function triggerScrape(
  slug: string,
  categories?: string[]
): Promise<{ success: boolean; message: string }> {
  const params = new URLSearchParams();
  if (categories) {
    categories.forEach(cat => params.append('categories', cat));
  }
  const query = params.toString();
  return fetchApi(`/distributors/${slug}/scrape${query ? `?${query}` : ''}`, {
    method: 'POST',
  });
}
