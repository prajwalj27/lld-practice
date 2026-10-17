# Parking Lot: follow-ups

Juniors often get none of these, mid-level one or two, senior several in a row. Explaining where the change lives is usually enough. Follow-ups 1 to 4 build on each other, and I tested all four together.

## 1. Map vehicles to spot sizes (small, medium, large)

Real lots have sizes, not "car spots". A vehicle can use any spot big enough for it, and should get the **smallest** one that fits, so bigger spots stay free for bigger vehicles.

```python
class SpotType(Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"

# On ParkingLot. Each tuple lists sizes smallest-first.
_COMPATIBLE_SPOT_TYPES: ClassVar[dict[VehicleType, tuple[SpotType, ...]]] = {
    VehicleType.MOTORCYCLE: (SpotType.SMALL, SpotType.MEDIUM, SpotType.LARGE),
    VehicleType.CAR:        (SpotType.MEDIUM, SpotType.LARGE),
    VehicleType.LARGE:      (SpotType.LARGE,),
}
```

The one-to-one `_SPOT_TYPE_FOR_VEHICLE` becomes this one-to-many map. This is where having two separate enums pays off: `VehicleType.LARGE` and `SpotType.LARGE` mean different things, and the code stays clear.

## 2. Outer and inner loops when picking a spot

```python
def _find_available_spot(self, vehicle_type: VehicleType) -> ParkingSpot | None:
    for spot_type in self._COMPATIBLE_SPOT_TYPES[vehicle_type]:   # outer: sizes, smallest first
        for spot in self._spots:                                  # inner: every spot
            if spot.spot_type is spot_type and spot.id not in self._occupied_spot_ids:
                return spot                                       # first hit = smallest fit
    return None
```

**Why sizes must be the outer loop:** if you swap the loops, the first compatible free spot *in list order* wins. A motorcycle could take a large spot listed early while small spots are still empty. With sizes outside, every small spot is checked before any medium one.

**Complexity:** O(k × n), with k = 3 sizes, so it's still O(n). To scan each spot only once, group the spots by type in `__init__`, as a `dict[SpotType, list[ParkingSpot]]`, and make the inner loop go over just that type's list.

## 3. Different rates per vehicle type

Swap the single rate for a map, and use the vehicle type the ticket already stores.

```python
DEFAULT_RATES_CENTS: ClassVar[dict[VehicleType, int]] = {
    VehicleType.MOTORCYCLE: 100,   # $1/h
    VehicleType.CAR: 200,          # $2/h
    VehicleType.LARGE: 300,        # $3/h
}

def __init__(self, spots: list[ParkingSpot],
             hourly_rates_cents: dict[VehicleType, int] | None = None) -> None:
    rates = dict(self.DEFAULT_RATES_CENTS if hourly_rates_cents is None else hourly_rates_cents)
    missing = set(VehicleType) - rates.keys()
    if missing:
        raise ValueError(f"Missing rates for: {sorted(v.value for v in missing)}")
    if any(rate < 0 for rate in rates.values()):
        raise ValueError("Rates cannot be negative")
    self._hourly_rates_cents = rates
    ...

def _compute_fee(self, entry_ms: int, exit_ms: int, vehicle_type: VehicleType) -> int:
    hours, remainder = divmod(exit_ms - entry_ms, self.MS_PER_HOUR)
    if remainder > 0:
        hours += 1
    return max(1, hours) * self._hourly_rates_cents[vehicle_type]

# in exit():
fee = self._compute_fee(ticket.entry_time_ms, exit_ms, ticket.vehicle_type)
```

Details worth saying:

- **Every vehicle type must have a rate.** This is checked once, at construction, rather than failing with a `KeyError` at someone's exit.
- **The rates dict is copied** (`dict(...)`), so a caller changing their own dict later can't change the lot's prices.
- **`is None`, not `or`.** `hourly_rates_cents or DEFAULTS` would silently replace an empty dict with the defaults, instead of raising "missing rates".
- **Rates that change during a stay.** If the rate should be fixed at entry, store `rate_cents` on the Ticket when it's issued.
- **If the pricing rules get complex**, like surge, time-of-day, or discounts, that's when to bring in a `PricingStrategy` interface. A map is enough for three rates.

## 4. Pass the entry and exit times into `enter` and `exit`

The base code reads the real clock inside the methods, so testing "2 hours 10 minutes later" means waiting, or patching `time.time` as `main.py` does. Let callers pass the time, and fall back to the clock when they don't.

```python
def enter(self, vehicle_type: VehicleType, timestamp_ms: int | None = None) -> Ticket:
    entry_ms = self._now_ms() if timestamp_ms is None else timestamp_ms
    ...  # same as before, using entry_ms for the ticket

def exit(self, ticket_id: str, timestamp_ms: int | None = None) -> int:
    ...  # validate the ticket as before
    exit_ms = self._now_ms() if timestamp_ms is None else timestamp_ms
    if exit_ms < ticket.entry_time_ms:
        raise ValueError("Exit time is before entry time")
    fee = self._compute_fee(ticket.entry_time_ms, exit_ms, ticket.vehicle_type)
    ...  # free spot, delete ticket, return fee
```

A test then controls time directly:

```python
HOUR, MINUTE = 3_600_000, 60_000
ticket = lot.enter(VehicleType.CAR, timestamp_ms=0)
assert lot.exit(ticket.id, timestamp_ms=2 * HOUR + 10 * MINUTE) == 3 * 200   # 3 h at $2
```

Two Python traps:

- **Don't write `timestamp_ms=int(time.time() * 1000)` as the default.** Defaults are evaluated once, when the function is defined, so every call would get the same frozen time. Use `None` and fill in the time inside the method.
- **Don't write `if not timestamp_ms`.** `0` is a valid timestamp, but it's falsy, so it would be replaced with the current time. Use `is None`.

**The alternative** is to inject a clock: `ParkingLot(spots, clock=time.time)`, with tests passing a fake one, the same idea as Amazon Locker. Both are fine. Parameters are simpler to explain; an injected clock keeps the public method signatures clean.

## 5. Multiple floors

Add a `ParkingFloor` between the lot and its spots:

```
class ParkingLot:   - floors: list[ParkingFloor], active tickets, rates
class ParkingFloor: - floor_number, spots
                    + available_count(spot_type) -> int
                    + find_available_spot(spot_type) -> ParkingSpot | None
```

- The floor becomes part of the spot ID, for example `"3-A15"`, so **Ticket doesn't change**, and neither does exit.
- Allocation choices:
  - **Fill lower floors first.** This is the simple loop over floors.
  - **Balance across floors.** Pick the floor with the most free spots of that type.
  - **Closest to a destination.** For example, the floor that connects to the food court.

  Several interchangeable rules are a natural fit for the **Strategy** pattern.

## 6. A pricing strategy

```python
class PricingStrategy(ABC):
    @abstractmethod
    def fee(self, ticket: Ticket, exit_ms: int) -> int: ...

class HourlyPricing(PricingStrategy): ...    # today's logic
class SurgePricing(PricingStrategy): ...     # time-of-day multipliers, etc.
```

ParkingLot holds one strategy and calls `self._pricing.fee(ticket, exit_ms)`. Strategies can be swapped per lot, or at runtime, without touching ParkingLot. Only bring this out once the rules outgrow a rates map.

## 7. Multiple entrances at the same time

**The race:** two entrances both find spot B free, both add it, and two cars get tickets for one spot. The gap between "check that the spot is free" and "mark it taken" is the problem.

- **Coarse lock: the right default.** `self._lock = threading.Lock()`, with the body of `enter` and `exit` inside `with self._lock:`. It's simple and correct, and fast enough for a handful of entrances.
- **Finer-grained: only if needed.** Lock just the occupied set while claiming a spot, and if the claim fails because someone else got it first, search again. That gives more throughput, but it's more complex.
- **Python note.** The GIL doesn't make "check, then add" atomic, because a thread can be switched between the two steps. You still need the lock.
- **Across processes or a database.** You'd use a database transaction (`SELECT ... FOR UPDATE`) or a distributed lock. That's usually a system-design topic, not LLD.

## 8. Smaller follow-ups

- **Lost tickets.** Charge a flat maximum fee. Finding the ticket by spot ID or licence plate would mean storing the plate on the Ticket.
- **"Already used" vs "never existed".** Keep a `set` of used ticket IDs, which needs pruning over time.
- **Monitoring or dashboards.** Now is when to add `available_count(spot_type)` or a status view, not before.
- **Reservations.** Add a reserved state for spots, held in the lot like occupancy, with an expiry time.

## What interviewers look for, by level

- **Junior.** Spots, tickets, and an orchestrator. `enter` finds a spot, marks it, and returns a ticket. `exit` charges and frees the spot. Rejects a full lot and invalid tickets. Needing hints on where pricing goes is fine.
- **Mid-level.** Clean responsibilities without prompting. Vehicle is an enum, not a class. Handles a full lot, invalid tickets, and double exits. Can explain why tickets are in a dict and why pricing lives in ParkingLot. Discusses one follow-up.
- **Senior.** Raises trade-offs before being asked: occupancy stored twice on purpose, a dict for O(1) lookup, separate enums for flexibility. Catches their own edge cases. For follow-ups, gives the simple solution first and explains when Strategy becomes worth it. Can discuss multiple floors and concurrent entrances.
