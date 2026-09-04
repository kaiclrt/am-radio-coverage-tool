import { useState, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';

interface Props {
  title: string;
  /** Open on first render. Each section manages its own open/closed state
   *  independently - collapsing one doesn't affect the others. */
  defaultOpen?: boolean;
  children: ReactNode;
}

/** A titled, collapsible wrapper used around each of the form's three
 *  sections (Transmitter / Target field strength / Power-RMS) so a long
 *  form can be tucked away once you've set it up the way you want. */
export function CollapsibleSection({ title, defaultOpen = true, children }: Props) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className="border-b pb-4 last:border-b-0 last:pb-0"
    >
      <CollapsibleTrigger className="flex w-full items-center justify-between py-1 text-left text-sm font-semibold">
        {title}
        <ChevronDown
          className={cn(
            'text-muted-foreground size-4 shrink-0 transition-transform',
            open && 'rotate-180',
          )}
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="pt-3 data-[state=closed]:pt-0">{children}</CollapsibleContent>
    </Collapsible>
  );
}
