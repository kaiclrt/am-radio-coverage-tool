import { useState, type FormEvent } from 'react';
import { Loader2 } from 'lucide-react';

import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { CollapsibleSection } from '@/components/CollapsibleSection';
import { TargetFieldStrengthField } from '@/components/TargetFieldStrengthField';
import { PowerRmsField } from '@/components/PowerRmsField';
import {
  buildContourRequest,
  DEFAULT_FORM,
  FormValidationError,
  MAX_SAMPLES_PER_REQUEST,
  type CoverageFormState,
} from '@/lib/coverage';
import type { ContourRequest } from '@/types/api';

interface Props {
  loading: boolean;
  onCalculate: (request: ContourRequest, rmsUsed: number) => void;
}

export function CoverageForm({ loading, onCalculate }: Props) {
  const [form, setForm] = useState<CoverageFormState>(DEFAULT_FORM);
  const [error, setError] = useState<string | null>(null);

  // Explicit submit only - no request-per-keystroke. The coverage endpoint
  // is rate-limited to 10/minute (docs/api.md); recalculation is a
  // deliberate action, not a side effect of typing (CLAUDE.md).
  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      const { request, rmsUsed } = buildContourRequest(form);
      setError(null);
      onCalculate(request, rmsUsed);
    } catch (err) {
      setError(err instanceof FormValidationError ? err.message : 'Invalid input.');
    }
  }

  const patch = (p: Partial<CoverageFormState>) => setForm((f) => ({ ...f, ...p }));

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <CollapsibleSection title="Transmitter">
        <fieldset className="space-y-3" disabled={loading}>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="tx-lat" className="text-xs">
                Latitude
              </Label>
              <Input
                id="tx-lat"
                inputMode="decimal"
                value={form.txLat}
                onChange={(e) => patch({ txLat: e.target.value })}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="tx-lon" className="text-xs">
                Longitude
              </Label>
              <Input
                id="tx-lon"
                inputMode="decimal"
                value={form.txLon}
                onChange={(e) => patch({ txLon: e.target.value })}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="freq" className="text-xs">
                Frequency (kHz)
              </Label>
              <Input
                id="freq"
                inputMode="numeric"
                value={form.freqKhz}
                onChange={(e) => patch({ freqKhz: e.target.value })}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="radials" className="text-xs">
                Radials
              </Label>
              <Input
                id="radials"
                inputMode="numeric"
                value={form.nRadials}
                onChange={(e) => patch({ nRadials: e.target.value })}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="max-search" className="text-xs">
                Max search (km)
              </Label>
              <Input
                id="max-search"
                inputMode="numeric"
                value={form.maxSearchKm}
                onChange={(e) => patch({ maxSearchKm: e.target.value })}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="sample-interval" className="text-xs">
                Sample interval (km)
              </Label>
              <Input
                id="sample-interval"
                inputMode="decimal"
                value={form.sampleIntervalKm}
                onChange={(e) => patch({ sampleIntervalKm: e.target.value })}
              />
            </div>
          </div>
          <p className="text-muted-foreground text-xs">
            The API allows about {MAX_SAMPLES_PER_REQUEST} terrain samples per request: radials ×
            (max search ÷ sample interval). If you exceed it, cut the radial count, widen the sample
            interval, or shorten the search distance.
          </p>
        </fieldset>
      </CollapsibleSection>

      <CollapsibleSection title="Target field strength">
        <TargetFieldStrengthField
          value={form.target}
          onChange={(target) => patch({ target })}
          disabled={loading}
        />
      </CollapsibleSection>

      <CollapsibleSection title="Power / RMS">
        <PowerRmsField
          value={form.power}
          onChange={(power) => patch({ power })}
          disabled={loading}
        />
      </CollapsibleSection>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Check your input</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Button type="submit" className="w-full" disabled={loading}>
        {loading && <Loader2 className="animate-spin" />}
        {loading ? 'Calculating…' : 'Calculate coverage'}
      </Button>
    </form>
  );
}
