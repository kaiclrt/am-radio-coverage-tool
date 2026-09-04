import { useCallback, useRef, useState } from 'react';

import { CoverageForm } from '@/components/CoverageForm';
import { CoverageMap } from '@/components/CoverageMap';
import { ResultsPanel } from '@/components/ResultsPanel';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { coverageContour, ApiError } from '@/lib/api';
import type { ContourRequest, ContourResponse } from '@/types/api';

export default function App() {
  const [result, setResult] = useState<ContourResponse | null>(null);
  const [center, setCenter] = useState<{ lat: number; lon: number }>({ lat: 14.6, lon: 121.0 });
  const [rmsUsed, setRmsUsed] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const handleCalculate = useCallback((request: ContourRequest, rms: number) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    coverageContour(request, controller.signal)
      .then((res) => {
        setResult(res);
        setRmsUsed(rms);
        setCenter({ lat: request.tx_lat, lon: request.tx_lon });
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError(err instanceof ApiError ? err.message : 'Unexpected error calculating coverage.');
      })
      .finally(() => {
        if (abortRef.current === controller) {
          setLoading(false);
          abortRef.current = null;
        }
      });
  }, []);

  return (
    <div className="bg-background min-h-screen">
      <header className="border-b">
        <div className="mx-auto max-w-[1400px] px-6 py-4">
          <h1 className="text-lg font-semibold">AM Radio Coverage Calculator</h1>
          <p className="text-muted-foreground text-sm">
            Ground wave coverage prediction from FCC propagation curves (47 CFR §73.184) and
            terrain-based ground conductivity.
          </p>
        </div>
      </header>

      <main className="mx-auto grid max-w-[1400px] gap-6 px-6 py-6 lg:grid-cols-[380px_1fr]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Inputs</CardTitle>
            </CardHeader>
            <CardContent>
              <CoverageForm loading={loading} onCalculate={handleCalculate} />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          {error && (
            <Alert variant="destructive">
              <AlertTitle>Could not calculate coverage</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <Card className="overflow-hidden py-0">
            <div className="h-[520px] w-full">
              <CoverageMap txLat={center.lat} txLon={center.lon} result={result} />
            </div>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Results</CardTitle>
            </CardHeader>
            <CardContent>
              <ResultsPanel result={result} rmsUsed={rmsUsed} />
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
