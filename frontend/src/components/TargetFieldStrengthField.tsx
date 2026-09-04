import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import type { TargetMode, TargetState } from '@/lib/coverage';

interface Props {
  value: TargetState;
  onChange: (next: TargetState) => void;
  disabled?: boolean;
}

interface ModeMeta {
  id: TargetMode;
  title: string;
  subtext: string;
}

// Subtext copy is taken verbatim from docs/web_ui_design.md - it is part of
// the finalized design, not placeholder text.
const MODES: ModeMeta[] = [
  {
    id: 'primary',
    title: 'Primary Service Contour',
    subtext: 'The standard 1 mV/m contour defined by KBP as an AM station’s primary service area.',
  },
  {
    id: 'dayNight',
    title: 'Day/Night Protection Contours',
    subtext:
      'Enter your station’s permit-specific daytime and nighttime field intensity requirements. Nighttime values are typically higher due to increased skywave interference.',
  },
  {
    id: 'custom',
    title: 'Custom Contour',
    subtext:
      'Enter any target field strength – useful for checking interference thresholds to a specific neighboring station.',
  },
];

export function TargetFieldStrengthField({ value, onChange, disabled }: Props) {
  return (
    <fieldset className="space-y-3" disabled={disabled}>
      <RadioGroup
        value={value.mode}
        onValueChange={(mode) => onChange({ ...value, mode: mode as TargetMode })}
      >
        {MODES.map((m) => (
          <div key={m.id} className="rounded-lg border p-3">
            <div className="flex items-start gap-3">
              <RadioGroupItem value={m.id} id={`target-${m.id}`} className="mt-0.5" />
              <div className="space-y-1">
                <Label htmlFor={`target-${m.id}`} className="font-medium">
                  {m.title}
                </Label>
                <p className="text-muted-foreground text-xs leading-relaxed">{m.subtext}</p>
              </div>
            </div>

            {m.id === 'dayNight' && value.mode === 'dayNight' && (
              <div className="mt-3 grid grid-cols-2 gap-3 pl-7">
                <div className="space-y-1">
                  <Label htmlFor="target-day" className="text-xs">
                    Daytime (mV/m)
                  </Label>
                  <Input
                    id="target-day"
                    inputMode="decimal"
                    value={value.dayMvm}
                    onChange={(e) => onChange({ ...value, dayMvm: e.target.value })}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="target-night" className="text-xs">
                    Nighttime (mV/m)
                  </Label>
                  <Input
                    id="target-night"
                    inputMode="decimal"
                    value={value.nightMvm}
                    onChange={(e) => onChange({ ...value, nightMvm: e.target.value })}
                  />
                </div>
                <p className="text-muted-foreground col-span-2 text-xs">
                  Permit values are often given in µV/m – divide by 1000 (e.g. 500 µV/m = 0.5 mV/m).
                  No conversion is applied automatically.
                </p>
              </div>
            )}

            {m.id === 'custom' && value.mode === 'custom' && (
              <div className="mt-3 max-w-[12rem] space-y-1 pl-7">
                <Label htmlFor="target-custom" className="text-xs">
                  Target (mV/m)
                </Label>
                <Input
                  id="target-custom"
                  inputMode="decimal"
                  value={value.customMvm}
                  onChange={(e) => onChange({ ...value, customMvm: e.target.value })}
                />
              </div>
            )}
          </div>
        ))}
      </RadioGroup>
    </fieldset>
  );
}
