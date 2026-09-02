# Web UI Input Design

Finalized design for the coverage calculator's two primary inputs: target
field strength (what contour to draw) and station power/RMS (what signal
strength to project). Locked in before implementation - see also the
stack decisions in [`web_ui_stack.md`](web_ui_stack.md) covering
Flask/React/Leaflet/Tailwind/shadcn choices.

## Target Field Strength

Three modes, mutually exclusive (radio-button style selector):

### Primary Service Contour
> The standard 1 mV/m contour defined by KBP as an AM station's primary
> service area.

No further input needed - runs `coverage_contour(..., target_mvm=1.0)`
once.

### Day/Night Protection Contours
> Enter your station's permit-specific daytime and nighttime field
> intensity requirements. Nighttime values are typically higher due to
> increased skywave interference.

Two number inputs (day target, night target, both mV/m) - these are
**per-station values from the station's actual NTC permit**, not a fixed
default, since they vary by station (e.g. a real permit reviewed during
this design phase specified 500 µV/m daytime / 2,500 µV/m nighttime =
0.5 / 2.5 mV/m - note the unit conversion from the permit's µV/m to the
tool's mV/m, ÷1000).

Runs `coverage_contour()` **twice** (once per target), displays both
contours on the map simultaneously, visually distinguished (e.g. two
colors/line styles), labeled "Daytime" and "Nighttime."

Rationale: groundwave propagation itself doesn't change day vs. night
(it's governed by frequency and ground conductivity, not sunlight) - what
changes is the *interference floor* from skywave propagation, which
activates at night and raises the field strength needed to be reliably
received. This is why the same station's nighttime protected contour is
smaller than its daytime one, despite no change in transmitted signal.

### Custom Contour
> Enter any target field strength - useful for checking interference
> thresholds to a specific neighboring station.

One number input (mV/m), no unit conversion assumptions - whatever the
user needs to check.

## Power / RMS

Two modes, mutually exclusive:

### Licensed/Measured RMS
> Enter your station's actual field intensity at 1 km, from your license
> or proof-of-performance measurement. Most accurate.

Direct number input, mV/m. Used as-is in `radial_field_strength()` /
`radial_distance_for_field_strength()`.

### Estimate from Transmitter Power
> Enter your transmitter power in kW for a rough estimate. Real-world
> coverage is typically smaller than shown due to antenna and ground
> system losses.

Number input in kW → computes `estimate_theoretical_rms(power_kw)`
(broadcast-engineering convention, 100·√P mV/m - see
`docs/radial_calculator.md` and `CHANGELOG.md` for how this formula was
validated against a real textbook worked example) → the computed RMS
value is displayed and **remains editable**, so the user can adjust it
down to account for real-world losses the formula doesn't capture →
persistent warning banner shown whenever this mode is active, not just
on first entry (state must survive re-renders/toggling back to this mode).

## How the two selectors compose

Independent of each other - any target mode pairs with either power mode.
Example: Day/Night targets (0.5 / 2.5 mV/m) + Estimate from Power (5 kW →
RMS ≈ 223.6 mV/m, editable) → two `coverage_contour()` calls, each using
the same (editable) RMS value, different targets, both contours rendered
on the map at once.

## Not yet decided

- Exact visual treatment for dual (day/night) contours on the map (color
  choice, fill vs. outline, legend design) - defer to actual frontend
  implementation/`frontend-design` conventions.
- Whether "Custom Contour" needs a saved-presets feature (e.g. for
  repeatedly checking against the same neighboring station) - noted as
  possible v2 scope, not v1.
