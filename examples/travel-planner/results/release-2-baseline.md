# Travel planner — baseline

## Text

# Saturday in Seabrook — Final Itinerary (2 adults + 7-year-old)

**Constraints met:** step-free throughout · child lunch at noon · $115 budget excl. hotel.

## Schedule

| Time | Activity | Cost | Notes |
|---|---|---|---|
| 08:30–09:10 | Breakfast (hotel, prepaid) | $0 | 40 min |
| 09:15–11:15 | **Aquarium** (step-free) | $56 | 2 adults × $22 + child $12; closes 18:00, no conflict |
| 11:15–11:35 | Bus to beach (20 min, step-free) | $12 | Family day pass covers the day's rides |
| 11:35–12:00 | Settle at beach | $0 | 25 min buffer |
| **12:00–12:45** | **Lunch** (child eats at noon) | $28 | Family estimate |
| 13:00–15:15 | Beach & boardwalk (step-free) | $0 | 2 hr 15 min |
| 15:30 | ~~Lighthouse~~ **SKIPPED** | — | 90 stairs, not step-free |
| 15:30–17:15 | Free time / boardwalk | $0 | Rest, snack |
| 17:30–18:30 | Dinner — picnic/simple meal | $15 | Option A swap (replaces $35 dinner out) |
| 19:00 | Evening boardwalk stroll | $0 | Optional, flexible |

## Budget Check (verified in Python)

| Item | Cost |
|---|---|
| Breakfast (prepaid) | $0 |
| Aquarium | $56 |
| Bus family pass | $12 |
| Lunch | $28 |
| Dinner (picnic, est.) | $15 |
| Beach / boardwalk / stroll | $0 |
| **Total** | **$111** |

**Total: $111 · Remaining: $4 of $115.**

## Schedule conflicts resolved
- **Bus leg matches the notes exactly** — 11:15→11:35 is 20 min, as stated. No conflict.
- **Noon lunch protected** — arrival at 11:35 leaves 25 min to settle before the child's 12:00 lunch.
- **Aquarium timing safe** — visit ends 11:15, well before the 18:00 close.
- **Lighthouse correctly excluded** — 90 stairs violates the step-free requirement.
- **⚠️ One unverified gap:** the notes give **no hotel→aquarium travel time**. The plan only allows a **5-minute buffer** (09:10–09:15). If the hotel isn't within a 5-minute step-free walk of the aquarium, either start breakfast at 08:15 or trim the aquarium visit slightly. This is the only soft spot in the schedule.

## Alternatives (if preferences change)
- **Option B — skip aquarium:** $75 total, **$40 remaining** (largest buffer).
- **Option C — keep aquarium, drop bus pass:** $119 → **$4 over**. Only works with a $12 lunch instead of $28 → **$115, exactly on budget** — and only if prepaid transport or a step-free walk is actually available (not confirmed in notes).

## Still to book / confirm
1. **Aquarium tickets** — not booked; $56 is an estimate from the notes.
2. **Bus family day pass** — not booked; confirm it covers all of the day's rides.
3. **Lunch venue** — not booked; **step-free seating is not specified in the notes** — confirm on arrival or reserve ahead.
4. **Picnic/simple dinner** — the $15 figure is an **estimate, not a confirmed booking**; confirm a step-free picnic spot or venue.
5. **Hotel→aquarium travel time** — missing from the notes; verify the route is step-free and fits the 5-minute buffer (or adjust breakfast earlier).

All figures are estimates from the supplied notes; nothing is prepaid except hotel breakfast.
