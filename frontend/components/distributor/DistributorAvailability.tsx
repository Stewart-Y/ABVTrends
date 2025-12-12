'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { getProductAvailability, DistributorAvailability } from '@/services/api';

interface DistributorAvailabilityProps {
  productId: string;
}

export function DistributorAvailabilityCard({ productId }: DistributorAvailabilityProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['productAvailability', productId],
    queryFn: () => getProductAvailability(productId),
    enabled: !!productId,
  });

  if (isLoading) {
    return (
      <Card data-testid="availability-loading">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <span className="text-xl">🏪</span>
            Available From
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-32">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card data-testid="availability-error">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <span className="text-xl">🏪</span>
            Available From
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            <span className="text-3xl mb-2 block">📦</span>
            <p>Distributor data not available</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (data.distributor_count === 0) {
    return (
      <Card data-testid="availability-empty">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <span className="text-xl">🏪</span>
            Available From
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            <span className="text-3xl mb-2 block">🔍</span>
            <p>No distributor listings found</p>
            <p className="text-sm mt-1">This product may not be available through tracked distributors</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card data-testid="availability-card">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl">🏪</span>
            Available From
          </div>
          <Badge variant="outline" className="text-xs">
            {data.distributor_count} distributor{data.distributor_count !== 1 ? 's' : ''}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {data.distributors.map((dist) => (
          <DistributorRow key={dist.slug} distributor={dist} />
        ))}
      </CardContent>
    </Card>
  );
}

function DistributorRow({ distributor }: { distributor: DistributorAvailability }) {
  const stockStatus = distributor.in_stock === null
    ? 'unknown'
    : distributor.in_stock
      ? 'in_stock'
      : 'out_of_stock';

  return (
    <div
      className="p-4 rounded-xl bg-card/50 border border-border/50 hover:border-primary/30 transition-all duration-300"
      data-testid={`distributor-${distributor.slug}`}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
            <span className="text-lg">📦</span>
          </div>
          <div>
            <h4 className="font-medium text-foreground">{distributor.distributor}</h4>
            {distributor.external_url && (
              <a
                href={distributor.external_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-primary hover:underline"
              >
                View on site
              </a>
            )}
          </div>
        </div>
        <StockBadge status={stockStatus} />
      </div>

      <div className="grid grid-cols-2 gap-4 mt-3">
        {distributor.price !== null && (
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Price</p>
            <p className="text-lg font-bold text-foreground">
              ${distributor.price.toFixed(2)}
              {distributor.price_type && (
                <span className="text-xs text-muted-foreground ml-1">/ {distributor.price_type}</span>
              )}
            </p>
          </div>
        )}
        {distributor.quantity !== null && (
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Stock</p>
            <p className="text-lg font-bold text-foreground">
              {distributor.quantity} units
            </p>
          </div>
        )}
      </div>

      {distributor.available_states && distributor.available_states.length > 0 && (
        <div className="mt-3">
          <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Available In</p>
          <div className="flex flex-wrap gap-1">
            {distributor.available_states.slice(0, 10).map((state) => (
              <Badge key={state} variant="outline" className="text-xs">
                {state}
              </Badge>
            ))}
            {distributor.available_states.length > 10 && (
              <Badge variant="outline" className="text-xs">
                +{distributor.available_states.length - 10} more
              </Badge>
            )}
          </div>
        </div>
      )}

      {distributor.last_updated && (
        <p className="text-xs text-muted-foreground mt-3">
          Updated {new Date(distributor.last_updated).toLocaleDateString()}
        </p>
      )}
    </div>
  );
}

function StockBadge({ status }: { status: 'in_stock' | 'out_of_stock' | 'unknown' }) {
  if (status === 'in_stock') {
    return (
      <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
        In Stock
      </Badge>
    );
  }
  if (status === 'out_of_stock') {
    return (
      <Badge className="bg-red-500/20 text-red-400 border-red-500/30">
        Out of Stock
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="text-muted-foreground">
      Status Unknown
    </Badge>
  );
}
