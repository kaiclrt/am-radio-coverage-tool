import { useRef, useState } from 'react';
import { AlertTriangle } from 'lucide-react';

import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useDebouncedCallback } from '@/hooks/useDebouncedCallback';
import { estimateRms, ApiError } from '@/lib/api';
import type { PowerMode, PowerState } from '@/lib/coverage';

interface Props {
  value: PowerState;
  onChange: (next: PowerState) => void;
  disabled?: boolean;
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

export function PowerRmsField({ value, onChange, disabled }: Props) {
  const [estimating, setEstimating] = useState(false);
  const [estimateError, setEstimateError] = useState<string | null>(null);
  // Pops up centered, every time the mode is (re-)entered - not just the
  // first time - per docs/web_ui_design.md's "not just a one-time
  // disclaimer." Also reopenable any time via the inline reminder below.
  const [warningOpen, setWarningOpen] = useState(false);
  // True once the user hand-edits the estimated RMS, so a later (debounced)
  // estimate response doesn't overwrite their adjustment.
  const userEditedRmsRef = useRef(false);

  const runEstimate = useDebouncedCallback((powerKw: string) => {
    const kw = Number(powerKw);
    if (powerKw.trim() === '' || Number.isNaN(kw) || kw <= 0) {
      setEstimating(false);
      setEstimateError(null);
      return;
    }
    setEstimating(true);
    setEstimateError(null);
    estimateRms(kw)
      .then((res) => {
        if (!userEditedRmsRef.current) {
          onChange({ ...value, powerKw, rmsMvm: String(round2(res.rms_at_1km_mvm)) });
        }
      })
      .catch((err) => {
        setEstimateError(err instanceof ApiError ? err.message : 'Could not estimate RMS.');
      })
      .finally(() => setEstimating(false));
  }, 500);

  function handleModeChange(mode: PowerMode) {
    if (mode === 'power') {
      setWarningOpen(true);
      if (value.rmsMvm.trim() === '') {
        userEditedRmsRef.current = false;
        onChange({ ...value, mode });
        runEstimate(value.powerKw);
        return;
      }
    }
    onChange({ ...value, mode });
  }

  function handlePowerKwChange(powerKw: string) {
    userEditedRmsRef.current = false;
    onChange({ ...value, powerKw });
    runEstimate(powerKw);
  }

  return (
    <fieldset className="space-y-3" disabled={disabled}>
      <RadioGroup value={value.mode} onValueChange={(m) => handleModeChange(m as PowerMode)}>
        {/* Licensed / measured RMS */}
        <div className="rounded-lg border p-3">
          <div className="flex items-start gap-3">
            <RadioGroupItem value="rms" id="power-rms" className="mt-0.5" />
            <div className="space-y-1">
              <Label htmlFor="power-rms" className="font-medium">
                Licensed/Measured RMS
              </Label>
              <p className="text-muted-foreground text-xs leading-relaxed">
                Enter your station’s actual field intensity at 1 km, from your license or
                proof-of-performance measurement. Most accurate.
              </p>
            </div>
          </div>
          {value.mode === 'rms' && (
            <div className="mt-3 max-w-[12rem] space-y-1 pl-7">
              <Label htmlFor="rms-value" className="text-xs">
                Field intensity at 1 km (mV/m)
              </Label>
              <Input
                id="rms-value"
                inputMode="decimal"
                value={value.rmsMvm}
                onChange={(e) => onChange({ ...value, rmsMvm: e.target.value })}
              />
            </div>
          )}
        </div>

        {/* Estimate from transmitter power */}
        <div className="rounded-lg border p-3">
          <div className="flex items-start gap-3">
            <RadioGroupItem value="power" id="power-est" className="mt-0.5" />
            <div className="space-y-1">
              <Label htmlFor="power-est" className="font-medium">
                Estimate from Transmitter Power
              </Label>
              <p className="text-muted-foreground text-xs leading-relaxed">
                Enter your transmitter power in kW for a rough estimate. Real-world coverage is
                typically smaller than shown due to antenna and ground system losses.
              </p>
            </div>
          </div>

          {value.mode === 'power' && (
            <div className="mt-3 space-y-3 pl-7">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label htmlFor="power-kw" className="text-xs">
                    Transmitter power (kW)
                  </Label>
                  <Input
                    id="power-kw"
                    inputMode="decimal"
                    value={value.powerKw}
                    onChange={(e) => handlePowerKwChange(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="power-rms-out" className="text-xs">
                    Estimated RMS at 1 km (mV/m) – editable
                  </Label>
                  <Input
                    id="power-rms-out"
                    inputMode="decimal"
                    value={value.rmsMvm}
                    onChange={(e) => {
                      userEditedRmsRef.current = true;
                      onChange({ ...value, rmsMvm: e.target.value });
                    }}
                  />
                </div>
              </div>
              <p className="text-muted-foreground text-xs">
                {estimating
                  ? 'Estimating…'
                  : 'Computed as 100·√P mV/m (via /api/estimate-rms). Adjust downward to account for real-world losses.'}
              </p>
              {estimateError && <p className="text-destructive text-xs">{estimateError}</p>}

              {/* Compact, always-visible reminder - the full warning is a
                  centered dialog (shown automatically on entering this mode,
                  and reopenable here), but this line stays on screen the
                  entire time the mode is active per the design doc's "not
                  just a one-time disclaimer." */}
              <button
                type="button"
                onClick={() => setWarningOpen(true)}
                className="text-muted-foreground hover:text-foreground flex items-center gap-1.5 text-xs underline decoration-dotted underline-offset-2"
              >
                <AlertTriangle className="size-3.5 text-amber-500" />
                Estimated. Learn more
              </button>
            </div>
          )}
        </div>
      </RadioGroup>

      <Dialog open={warningOpen} onOpenChange={setWarningOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="size-5 text-amber-500" />
              Estimated coverage
            </DialogTitle>
            <DialogDescription>
              This RMS is a theoretical figure derived from power alone. Antenna efficiency and
              ground-system losses mean actual coverage is usually smaller. Use a licensed or
              proof-of-performance RMS for an authoritative result.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button onClick={() => setWarningOpen(false)}>Got it</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </fieldset>
  );
}
