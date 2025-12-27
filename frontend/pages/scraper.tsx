'use client';

import { useEffect, useState, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Layout } from '@/components/Layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import {
  getScraperHealth,
  getRecentScrapeRuns,
  getDistributors,
  triggerScrape,
  ScraperHealthResponse,
  ScrapeRun,
  Distributor,
} from '@/services/api';

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  logger: string;
}

interface ScraperStatus {
  is_running: boolean;
  current_source: string | null;
  progress: number;
  total: number;
  logs_count: number;
}

// Use relative URL in production (works with ALB routing), absolute URL for local dev
const API_BASE = process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== 'undefined' && window.location.hostname !== 'localhost'
    ? ''
    : 'http://localhost:8000');

export default function ScraperPage() {
  const [mounted, setMounted] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [status, setStatus] = useState<ScraperStatus>({
    is_running: false,
    current_source: null,
    progress: 0,
    total: 0,
    logs_count: 0,
  });
  const [isStreaming, setIsStreaming] = useState(false);
  const [tier1Enabled, setTier1Enabled] = useState(true);
  const [tier2Enabled, setTier2Enabled] = useState(false);
  const [parallelMode, setParallelMode] = useState(false);
  const [activeTab, setActiveTab] = useState<'media' | 'distributors'>('distributors');
  const [error, setError] = useState<string | null>(null);

  const logsEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const queryClient = useQueryClient();

  // Distributor scraper queries
  const { data: scraperHealth, isLoading: healthLoading } = useQuery({
    queryKey: ['scraperHealth'],
    queryFn: getScraperHealth,
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const { data: recentRuns, isLoading: runsLoading } = useQuery({
    queryKey: ['recentScrapeRuns'],
    queryFn: () => getRecentScrapeRuns(20),
    refetchInterval: 30000,
  });

  const { data: distributors } = useQuery({
    queryKey: ['distributors'],
    queryFn: () => getDistributors(true),
  });

  // Trigger scrape mutation
  const triggerScrapeMutation = useMutation({
    mutationFn: (slug: string) => triggerScrape(slug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scraperHealth'] });
      queryClient.invalidateQueries({ queryKey: ['recentScrapeRuns'] });
    },
  });

  useEffect(() => {
    document.documentElement.classList.add('dark');
    setMounted(true);
  }, []);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // Fetch status periodically
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await fetch(`${API_BASE}/scraper/status`);
        const data = await response.json();
        setStatus(data);
      } catch (error) {
        console.error('Failed to fetch status:', error);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  // Connect to log stream
  const connectToStream = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const eventSource = new EventSource(`${API_BASE}/scraper/logs/stream`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'log') {
          setLogs((prev) => [...prev, data.data]);
        } else if (data.type === 'connected') {
          console.log('Connected to log stream');
        }
      } catch (error) {
        console.error('Failed to parse log:', error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('EventSource error:', error);
      eventSource.close();
      setIsStreaming(false);
    };

    eventSourceRef.current = eventSource;
    setIsStreaming(true);
  };

  // Disconnect from stream
  const disconnectFromStream = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsStreaming(false);
  };

  // Auto-connect to stream on mount
  useEffect(() => {
    connectToStream();
    return () => disconnectFromStream();
  }, []);

  // Start scraper
  const handleStart = async () => {
    setError(null); // Clear previous errors
    try {
      const response = await fetch(`${API_BASE}/scraper/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tier1: tier1Enabled,
          tier2: tier2Enabled,
          parallel: parallelMode,
          max_articles: 5,
        }),
      });

      const data = await response.json();
      if (data.success) {
        setLogs([]);  // Clear old logs
      } else {
        setError(data.message || 'Failed to start scraper');
      }
    } catch (err) {
      console.error('Failed to start scraper:', err);
      setError('Failed to start scraper. Please check if the backend is running.');
    }
  };

  // Clear logs
  const handleClear = () => {
    setLogs([]);
  };

  if (!mounted) return null;

  const getLogColor = (level: string) => {
    switch (level.toUpperCase()) {
      case 'ERROR':
        return 'text-red-400';
      case 'WARNING':
        return 'text-yellow-400';
      case 'INFO':
        return 'text-blue-400';
      case 'DEBUG':
        return 'text-gray-400';
      default:
        return 'text-foreground';
    }
  };

  const progressPercent = status.total > 0 ? (status.progress / status.total) * 100 : 0;

  const headerActions = (
    <div className="flex items-center gap-1.5 sm:gap-2">
      <Badge variant={isStreaming ? 'default' : 'secondary'} className="gap-1 sm:gap-1.5 text-xs" data-testid="connection-status">
        <div
          className={cn(
            'w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full',
            isStreaming ? 'bg-green-400 animate-pulse' : 'bg-gray-400'
          )}
        />
        <span className="hidden sm:inline">{isStreaming ? 'Connected' : 'Disconnected'}</span>
      </Badge>
      <Badge variant={status.is_running ? 'default' : 'outline'} className="text-xs" data-testid="running-status">
        {status.is_running ? '🟢' : '⚫'}
        <span className="hidden sm:inline ml-1">{status.is_running ? 'Running' : 'Idle'}</span>
      </Badge>
    </div>
  );

  return (
    <ProtectedRoute requireAdmin>
      <Layout
        title="AI Scraper Monitor"
        subtitle="Real-time monitoring of AI-powered data collection"
        headerActions={headerActions}
        testId="scraper-page"
      >
        <div className="space-y-4 sm:space-y-6" data-testid="scraper-header">
          {/* Tab Navigation */}
          <div className="flex gap-2 border-b border-border pb-4">
            <Button
              variant={activeTab === 'distributors' ? 'default' : 'outline'}
              onClick={() => setActiveTab('distributors')}
              className="gap-2"
            >
              <span>📦</span>
              Distributors
            </Button>
            <Button
              variant={activeTab === 'media' ? 'default' : 'outline'}
              onClick={() => setActiveTab('media')}
              className="gap-2"
            >
              <span>📰</span>
              Media Scrapers
            </Button>
          </div>

          {/* Distributors Tab */}
          {activeTab === 'distributors' && (
            <>
              {/* Distributor Health Overview */}
              <Card data-testid="distributor-health-card">
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-xl">🏥</span>
                      Scraper Health
                    </div>
                    {scraperHealth && (
                      <Badge
                        variant={scraperHealth.overall_healthy ? 'default' : 'outline'}
                        className={cn(
                          "gap-1.5",
                          !scraperHealth.overall_healthy && "border-red-500/50 text-red-400"
                        )}
                      >
                        <div
                          className={cn(
                            'w-2 h-2 rounded-full',
                            scraperHealth.overall_healthy ? 'bg-green-400' : 'bg-red-400'
                          )}
                        />
                        {scraperHealth.overall_healthy ? 'All Healthy' : `${scraperHealth.alerts.length} Alerts`}
                      </Badge>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {healthLoading ? (
                    <div className="flex items-center justify-center h-32">
                      <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent" />
                    </div>
                  ) : scraperHealth ? (
                    <div className="space-y-6">
                      {/* Stats Row */}
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="p-4 rounded-lg bg-card/50 border border-border/30">
                          <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Healthy</p>
                          <p className="text-2xl font-bold text-green-400">{scraperHealth.healthy_count}</p>
                        </div>
                        <div className="p-4 rounded-lg bg-card/50 border border-border/30">
                          <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Total</p>
                          <p className="text-2xl font-bold text-foreground">{scraperHealth.total_count}</p>
                        </div>
                        <div className="p-4 rounded-lg bg-card/50 border border-border/30">
                          <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Alerts</p>
                          <p className="text-2xl font-bold text-red-400">{scraperHealth.alerts.length}</p>
                        </div>
                        <div className="p-4 rounded-lg bg-card/50 border border-border/30">
                          <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Last Check</p>
                          <p className="text-sm font-medium text-foreground">
                            {new Date(scraperHealth.checked_at).toLocaleTimeString()}
                          </p>
                        </div>
                      </div>

                      {/* Alerts */}
                      {scraperHealth.alerts.length > 0 && (
                        <div className="space-y-2">
                          <h4 className="text-sm font-semibold text-red-400 uppercase tracking-wider">Alerts</h4>
                          {scraperHealth.alerts.map((alert, idx) => (
                            <div
                              key={idx}
                              className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center gap-3"
                            >
                              <span className="text-lg">⚠️</span>
                              <div>
                                <p className="text-sm font-medium text-foreground">
                                  {alert.type === 'stale_data' && `Stale data: ${alert.distributor}`}
                                  {alert.type === 'last_run_failed' && `Failed: ${alert.distributor}`}
                                  {alert.type === 'never_run' && `Never run: ${alert.distributor}`}
                                </p>
                                {alert.hours_since_run && (
                                  <p className="text-xs text-muted-foreground">
                                    Last run {alert.hours_since_run.toFixed(1)} hours ago
                                  </p>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Scraper List */}
                      <div className="space-y-2">
                        <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">All Scrapers</h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          {scraperHealth.scrapers.map((scraper) => (
                            <div
                              key={scraper.slug}
                              className="p-4 rounded-lg bg-card/50 border border-border/30 hover:border-primary/30 transition-colors"
                            >
                              <div className="flex items-center justify-between mb-2">
                                <h5 className="font-medium text-foreground">{scraper.distributor}</h5>
                                <div className="flex items-center gap-2">
                                  {scraper.is_running && (
                                    <Badge variant="outline" className="text-xs gap-1">
                                      <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
                                      Running
                                    </Badge>
                                  )}
                                  <ScraperStatusBadge status={scraper.status} />
                                </div>
                              </div>
                              <div className="flex items-center justify-between text-xs text-muted-foreground">
                                <span>
                                  {scraper.last_run_at
                                    ? `Last run: ${new Date(scraper.last_run_at).toLocaleString()}`
                                    : 'Never run'}
                                </span>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => triggerScrapeMutation.mutate(scraper.slug)}
                                  disabled={scraper.is_running || triggerScrapeMutation.isPending}
                                  className="h-7 text-xs"
                                >
                                  {triggerScrapeMutation.isPending ? 'Starting...' : 'Run Now'}
                                </Button>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <span className="text-3xl mb-2 block">📦</span>
                      <p>No scraper health data available</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Recent Runs */}
              <Card data-testid="recent-runs-card">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <span className="text-xl">📋</span>
                    Recent Scrape Runs
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {runsLoading ? (
                    <div className="flex items-center justify-center h-32">
                      <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent" />
                    </div>
                  ) : recentRuns?.runs?.length ? (
                    <div className="space-y-2">
                      {recentRuns.runs.map((run) => (
                        <div
                          key={run.id}
                          className="p-4 rounded-lg bg-card/50 border border-border/30 hover:border-primary/30 transition-colors"
                        >
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-3">
                              <span className="text-lg">📦</span>
                              <div>
                                <h5 className="font-medium text-foreground">{run.distributor}</h5>
                                <p className="text-xs text-muted-foreground">
                                  {run.started_at && new Date(run.started_at).toLocaleString()}
                                </p>
                              </div>
                            </div>
                            <RunStatusBadge status={run.status} />
                          </div>
                          <div className="grid grid-cols-4 gap-4 text-xs">
                            <div>
                              <p className="text-muted-foreground">Found</p>
                              <p className="font-medium text-foreground">{run.products_found ?? '-'}</p>
                            </div>
                            <div>
                              <p className="text-muted-foreground">New</p>
                              <p className="font-medium text-green-400">{run.products_new ?? '-'}</p>
                            </div>
                            <div>
                              <p className="text-muted-foreground">Updated</p>
                              <p className="font-medium text-blue-400">{run.products_updated ?? '-'}</p>
                            </div>
                            <div>
                              <p className="text-muted-foreground">Errors</p>
                              <p className="font-medium text-red-400">{run.error_count ?? '-'}</p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <span className="text-3xl mb-2 block">📋</span>
                      <p>No recent scrape runs</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          )}

          {/* Media Scrapers Tab */}
          {activeTab === 'media' && (
            <>
          {/* Error Display */}
          {error && (
            <Card className="border-red-500/30 bg-red-500/5" data-testid="error-card">
              <CardContent className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-xl">⚠️</span>
                  <p className="text-sm text-red-400">{error}</p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setError(null)}
                  className="text-red-400 hover:text-red-300"
                >
                  Dismiss
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Controls Card */}
          <Card data-testid="scraper-controls">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <span className="text-xl">⚙️</span>
                Scraper Controls
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Configuration */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="flex items-center gap-3 p-4 rounded-lg border border-border hover:border-primary/30 transition-colors">
                  <input
                    type="checkbox"
                    id="tier1"
                    checked={tier1Enabled}
                    onChange={(e) => setTier1Enabled(e.target.checked)}
                    disabled={status.is_running}
                    data-testid="tier1-checkbox"
                    className="w-5 h-5 rounded border-gray-300 text-primary focus:ring-primary"
                  />
                  <label htmlFor="tier1" className="flex-1 cursor-pointer">
                    <div className="font-medium">Tier 1 Media</div>
                    <div className="text-xs text-muted-foreground">News & trade publications</div>
                  </label>
                </div>

                <div className="flex items-center gap-3 p-4 rounded-lg border border-border hover:border-primary/30 transition-colors">
                  <input
                    type="checkbox"
                    id="tier2"
                    checked={tier2Enabled}
                    onChange={(e) => setTier2Enabled(e.target.checked)}
                    disabled={status.is_running}
                    data-testid="tier2-checkbox"
                    className="w-5 h-5 rounded border-gray-300 text-primary focus:ring-primary"
                  />
                  <label htmlFor="tier2" className="flex-1 cursor-pointer">
                    <div className="font-medium">Tier 2 Retail</div>
                    <div className="text-xs text-muted-foreground">Retailer websites & blogs</div>
                  </label>
                </div>

                <div className="flex items-center gap-3 p-4 rounded-lg border border-border hover:border-primary/30 transition-colors">
                  <input
                    type="checkbox"
                    id="parallel"
                    checked={parallelMode}
                    onChange={(e) => setParallelMode(e.target.checked)}
                    disabled={status.is_running}
                    data-testid="parallel-checkbox"
                    className="w-5 h-5 rounded border-gray-300 text-primary focus:ring-primary"
                  />
                  <label htmlFor="parallel" className="flex-1 cursor-pointer">
                    <div className="font-medium">Parallel Mode</div>
                    <div className="text-xs text-muted-foreground">Faster scraping</div>
                  </label>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-3">
                <Button
                  onClick={handleStart}
                  disabled={status.is_running || (!tier1Enabled && !tier2Enabled)}
                  className="gap-2"
                  data-testid="start-scraper-button"
                >
                  <span>▶️</span>
                  Start Scraping
                </Button>
                <Button onClick={handleClear} variant="outline" className="gap-2" data-testid="clear-logs-button">
                  <span>🗑️</span>
                  Clear Logs
                </Button>
                <Button
                  onClick={isStreaming ? disconnectFromStream : connectToStream}
                  variant="outline"
                  className="gap-2"
                  data-testid="stream-toggle-button"
                >
                  <span>{isStreaming ? '🔌' : '🔗'}</span>
                  {isStreaming ? 'Disconnect' : 'Connect'}
                </Button>
              </div>

              {/* Progress */}
              {status.is_running && status.total > 0 && (
                <div className="space-y-2" data-testid="scraper-progress">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">
                      Progress: {status.progress} / {status.total} sources
                    </span>
                    <span className="font-medium" data-testid="progress-percent">{progressPercent.toFixed(0)}%</span>
                  </div>
                  <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary rounded-full transition-all duration-500"
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                  {status.current_source && (
                    <div className="text-sm text-muted-foreground">
                      Current: <span className="text-foreground font-medium" data-testid="current-source">{status.current_source}</span>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Logs Card */}
          <Card className="flex-1" data-testid="logs-card">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xl">📋</span>
                  Live Logs
                  <Badge variant="outline" className="text-xs font-normal" data-testid="logs-count">
                    {logs.length} entries
                  </Badge>
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="bg-black/40 rounded-lg p-4 h-[600px] overflow-y-auto font-mono text-sm" data-testid="logs-container">
                {logs.length === 0 ? (
                  <div className="h-full flex items-center justify-center text-muted-foreground" data-testid="logs-empty">
                    <div className="text-center">
                      <div className="text-4xl mb-3">💤</div>
                      <div>No logs yet. Start scraping to see activity.</div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-1">
                    {logs.map((log, index) => (
                      <div key={index} className="flex gap-3 hover:bg-white/5 px-2 py-1 rounded" data-testid={`log-entry-${index}`}>
                        <span className="text-gray-500 text-xs shrink-0">
                          {new Date(log.timestamp).toLocaleTimeString()}
                        </span>
                        <span className={cn('text-xs font-semibold shrink-0 w-16', getLogColor(log.level))}>
                          {log.level}
                        </span>
                        <span className="text-gray-200 flex-1">{log.message}</span>
                      </div>
                    ))}
                    <div ref={logsEndRef} />
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
            </>
          )}
        </div>
      </Layout>
    </ProtectedRoute>
  );
}

// Helper Components

function ScraperStatusBadge({ status }: { status: string }) {
  switch (status) {
    case 'healthy':
      return (
        <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
          Healthy
        </Badge>
      );
    case 'stale':
      return (
        <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
          Stale
        </Badge>
      );
    case 'failed':
      return (
        <Badge className="bg-red-500/20 text-red-400 border-red-500/30">
          Failed
        </Badge>
      );
    default:
      return (
        <Badge variant="outline" className="text-muted-foreground">
          Unknown
        </Badge>
      );
  }
}

function RunStatusBadge({ status }: { status: string }) {
  switch (status) {
    case 'completed':
      return (
        <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
          Completed
        </Badge>
      );
    case 'running':
      return (
        <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30 gap-1">
          <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
          Running
        </Badge>
      );
    case 'failed':
      return (
        <Badge className="bg-red-500/20 text-red-400 border-red-500/30">
          Failed
        </Badge>
      );
    default:
      return (
        <Badge variant="outline" className="text-muted-foreground">
          {status}
        </Badge>
      );
  }
}
