'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { Layout } from '@/components/Layout';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn, getTierColor } from '@/lib/utils';

// API function to get all products
async function getProducts(params?: {
  search?: string;
  category?: string;
  limit?: number;
  offset?: number;
}): Promise<{ items: ProductItem[]; meta: { total: number } }> {
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const searchParams = new URLSearchParams();

  if (params?.search) searchParams.set('search', params.search);
  if (params?.category) searchParams.set('category', params.category);
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.offset) searchParams.set('offset', params.offset.toString());

  const query = searchParams.toString();
  const response = await fetch(`${API_BASE}/products${query ? `?${query}` : ''}`);

  if (!response.ok) {
    throw new Error('Failed to fetch products');
  }

  return response.json();
}

interface ProductItem {
  id: string;
  name: string;
  brand: string | null;
  category: string;
  subcategory: string | null;
  image_url: string | null;
  created_at: string;
  updated_at: string;
  latest_score: number | null;
}

type CategoryFilter = 'all' | 'spirits' | 'wine' | 'rtd' | 'beer';

export default function ProductsPage() {
  const [mounted, setMounted] = useState(false);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [category, setCategory] = useState<CategoryFilter>('all');
  const [page, setPage] = useState(1);
  const pageSize = 24;

  useEffect(() => {
    document.documentElement.classList.add('dark');
    setMounted(true);
  }, []);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1); // Reset to first page on search
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const { data, isLoading, error } = useQuery({
    queryKey: ['products', debouncedSearch, category, page],
    queryFn: () =>
      getProducts({
        search: debouncedSearch || undefined,
        category: category === 'all' ? undefined : category,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      }),
  });

  if (!mounted) return null;

  const headerActions = (
    <Badge variant="outline" className="text-xs">
      <span className="mr-1.5">📦</span>
      Product Catalog
    </Badge>
  );

  return (
    <Layout
      title="Products"
      subtitle="Browse all tracked products in the catalog"
      headerActions={headerActions}
      testId="products-page"
    >
      <div className="space-y-6" data-testid="products-header">
        {/* Filters */}
        <Card data-testid="products-filters">
          <CardContent className="p-4 sm:p-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Search */}
              <div className="sm:col-span-2">
                <label className="block text-xs sm:text-sm font-medium text-muted-foreground mb-2">
                  Search
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">
                    🔍
                  </span>
                  <input
                    type="text"
                    placeholder="Search products by name or brand..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    data-testid="search-input"
                    className="w-full pl-10 pr-4 py-2.5 text-sm bg-background border border-border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary transition-colors"
                  />
                </div>
              </div>

              {/* Category Filter */}
              <div>
                <label className="block text-xs sm:text-sm font-medium text-muted-foreground mb-2">
                  Category
                </label>
                <select
                  value={category}
                  onChange={(e) => {
                    setCategory(e.target.value as CategoryFilter);
                    setPage(1);
                  }}
                  data-testid="category-filter"
                  className="w-full px-4 py-2.5 text-sm bg-background border border-border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary transition-colors cursor-pointer"
                >
                  <option value="all">All Categories</option>
                  <option value="spirits">🥃 Spirits</option>
                  <option value="wine">🍷 Wine</option>
                  <option value="rtd">🥤 RTD</option>
                  <option value="beer">🍺 Beer</option>
                </select>
              </div>

              {/* Results count */}
              <div className="flex items-end">
                <div className="w-full p-3 rounded-lg bg-primary/10 border border-primary/20" data-testid="results-count">
                  <p className="text-sm text-muted-foreground">
                    <span className="text-2xl font-bold text-primary mr-2">
                      {data?.meta?.total || 0}
                    </span>
                    products
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Loading State */}
        {isLoading && (
          <div className="flex items-center justify-center h-64" data-testid="products-loading">
            <div className="text-center">
              <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent mb-4" />
              <p className="text-muted-foreground">Loading products...</p>
            </div>
          </div>
        )}

        {/* Error State */}
        {error && (
          <Card className="border-red-500/30 bg-red-500/5" data-testid="products-error">
            <CardContent className="p-8 text-center">
              <span className="text-4xl mb-4 block">⚠️</span>
              <h3 className="text-lg font-semibold mb-2 text-red-400">Failed to load products</h3>
              <p className="text-muted-foreground">Please try again later</p>
            </CardContent>
          </Card>
        )}

        {/* Products Grid */}
        {!isLoading && !error && data?.items && (
          <>
            {data.items.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 sm:gap-6" data-testid="products-grid">
                {data.items.map((product, index) => (
                  <ProductCard key={product.id} product={product} index={index} />
                ))}
              </div>
            ) : (
              <Card data-testid="products-empty">
                <CardContent className="p-8 text-center">
                  <span className="text-5xl mb-4 block">🔍</span>
                  <h3 className="text-lg font-semibold mb-2">No products found</h3>
                  <p className="text-muted-foreground">
                    Try adjusting your search or filter
                  </p>
                </CardContent>
              </Card>
            )}

            {/* Pagination */}
            {(data.meta?.total || 0) > pageSize && (
              <div className="flex items-center justify-between" data-testid="products-pagination">
                <p className="text-sm text-muted-foreground">
                  Showing{' '}
                  <span className="font-medium text-foreground">
                    {(page - 1) * pageSize + 1}
                  </span>{' '}
                  to{' '}
                  <span className="font-medium text-foreground">
                    {Math.min(page * pageSize, data.meta?.total || 0)}
                  </span>{' '}
                  of{' '}
                  <span className="font-medium text-foreground">{data.meta?.total || 0}</span>{' '}
                  products
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    data-testid="pagination-prev"
                  >
                    ← Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => p + 1)}
                    disabled={page * pageSize >= (data.meta?.total || 0)}
                    data-testid="pagination-next"
                  >
                    Next →
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </Layout>
  );
}

function ProductCard({ product, index }: { product: ProductItem; index: number }) {
  const getCategoryEmoji = (cat: string) => {
    switch (cat) {
      case 'spirits': return '🥃';
      case 'wine': return '🍷';
      case 'beer': return '🍺';
      case 'rtd': return '🥤';
      default: return '🍸';
    }
  };

  return (
    <Link href={`/product/${product.id}`}>
      <Card
        data-testid={`product-card-${product.id}`}
        className="group cursor-pointer overflow-hidden hover:border-primary/50 transition-all duration-300 hover:shadow-lg hover:shadow-primary/10 animate-fade-in"
        style={{ animationDelay: `${index * 30}ms` }}
      >
        {/* Image */}
        <div className="relative aspect-square bg-muted/30 overflow-hidden">
          {product.image_url ? (
            <img
              src={product.image_url}
              alt={product.name}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <span className="text-6xl opacity-20">{getCategoryEmoji(product.category)}</span>
            </div>
          )}

          {/* Score Badge */}
          {product.latest_score !== null && (
            <div className="absolute top-3 right-3">
              <Badge
                className="backdrop-blur-sm"
                style={{
                  backgroundColor: `${getTierColor(
                    product.latest_score >= 90 ? 'viral' :
                    product.latest_score >= 70 ? 'trending' :
                    product.latest_score >= 50 ? 'emerging' :
                    product.latest_score >= 30 ? 'stable' : 'declining'
                  )}20`,
                  color: getTierColor(
                    product.latest_score >= 90 ? 'viral' :
                    product.latest_score >= 70 ? 'trending' :
                    product.latest_score >= 50 ? 'emerging' :
                    product.latest_score >= 30 ? 'stable' : 'declining'
                  ),
                }}
              >
                {product.latest_score.toFixed(0)}
              </Badge>
            </div>
          )}
        </div>

        <CardContent className="p-4">
          <h3 className="font-semibold text-sm group-hover:text-primary transition-colors line-clamp-2 mb-1">
            {product.name}
          </h3>
          {product.brand && (
            <p className="text-xs text-muted-foreground mb-2">{product.brand}</p>
          )}
          <div className="flex items-center gap-2 text-xs text-muted-foreground capitalize">
            <span>{getCategoryEmoji(product.category)}</span>
            <span>{product.category}</span>
            {product.subcategory && (
              <>
                <span className="text-border">•</span>
                <span>{product.subcategory}</span>
              </>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
