# Parking Lot: class design and relationships

Design top-down: ParkingLot first, then ParkingSpot and Ticket. For each class, ask what it must **remember** to meet the requirements (its state), and what it must **do** (its methods).

## Deriving the state

| Requirement | Who tracks what |
|---|---|
| Assign a free compatible spot | ParkingLot: all spots, and which are occupied. ParkingSpot: its type |
| Issue a ticket at entry | ParkingLot: active tickets, to validate on exit |
| Fee based on time, hourly | ParkingLot: the hourly rate. Ticket: the entry time |
| Free the spot on exit | Ticket: which spot it was |
| Driver gives the ticket ID | Ticket: its ID. ParkingSpot: its ID |

## Class design

```
enum VehicleType: MOTORCYCLE, CAR, LARGE
enum SpotType:    MOTORCYCLE, CAR, LARGE

class ParkingSpot:                  (frozen dataclass)
    - id: str
    - spot_type: SpotType

class Ticket:                       (frozen dataclass)
    - id: str
    - spot_id: str
    - vehicle_type: VehicleType
    - entry_time_ms: int

class ParkingLot:
    - MS_PER_HOUR                                        (class constant)
    - _SPOT_TYPE_FOR_VEHICLE: dict[VehicleType, SpotType] (class constant)
    - _spots: list[ParkingSpot]
    - _hourly_rate_cents: int
    - _active_tickets: dict[str, Ticket]
    - _occupied_spot_ids: set[str]
    + ParkingLot(spots, hourly_rate_cents)
    + enter(vehicle_type) -> Ticket
    + exit(ticket_id) -> int                (fee in cents)
    - _find_available_spot(vehicle_type) -> ParkingSpot | None
    - _compute_fee(entry_ms, exit_ms) -> int
    - _now_ms() -> int

exceptions: ParkingLotError
    ├─ NoSpotAvailableError
    └─ InvalidTicketError
```

That's the whole public API: two methods. Don't add `get_available_spots()` or `get_status()` unless the requirements ask for them. They expose internal state for no reason; add them if the interviewer later brings up dashboards or monitoring.

## Relationships

- **ParkingLot owns many ParkingSpots** and creates every Ticket.
- **ParkingLot stores active tickets by ID**, and keeps an index of occupied spot IDs.
- **A Ticket refers to its spot by ID only.** ParkingSpot knows nothing about tickets.

## Flows

```
enter(vehicle_type)
  ├─ find first free spot of the matching type
  │     └─ none -> NoSpotAvailableError (nothing has changed)
  ├─ add spot ID to the occupied set
  ├─ ticket = new ID + spot ID + vehicle type + now
  ├─ store ticket by ID
  └─ return ticket

exit(ticket_id)
  ├─ empty, or not in active tickets -> InvalidTicketError
  ├─ fee = compute_fee(entry time, now)
  ├─ remove spot ID from the occupied set
  ├─ delete the ticket (prevents a second exit)
  └─ return fee
```

## Design decisions worth saying out loud

### Who tracks occupancy?

There are three options, and all of them are defensible.

1. **An occupied flag on ParkingSpot.** It reads nicely ("find a spot that's free and matches"), but occupancy now lives in two places: the flag, and the tickets that point at the spot. If you forget to update one, the same spot gets assigned twice. It's still a fine choice if you see occupancy as part of the spot itself; Amazon Locker does exactly this.
2. **Work it out from the tickets.** A spot is occupied if and only if an active ticket points to it. This is the cleanest option, since nothing is stored twice. But every entry rebuilds the occupied set by scanning all the tickets. And with multiple entrances, you'd have to lock the whole ticket map for every read and write.
3. **An occupancy index: a set of occupied spot IDs in ParkingLot.** This is the chosen approach. It *is* redundant with the tickets, in the same way a database index is. In return, membership checks are O(1), and it gives concurrency a small, clear thing to lock: you can lock just the set to claim a spot.

The rule of thumb: is this a **property of the thing itself**, like its ID, size, or being broken, or a **relationship the system manages**, like being assigned to ticket X? Properties go on the entity; relationships go in the orchestrator. Here, a spot becomes occupied the moment a ticket is issued at the gate, before the car even reaches it. That makes occupancy a relationship, so it goes in ParkingLot.

In Amazon Locker, occupancy means a package is physically inside, so it went on the entity. It's a mental model, not a hard rule. What matters is that you can defend your choice.

### Where does the fee calculation go?

1. **`calculate_fee()` on Ticket: avoid.** The ticket would become both a record and a pricing calculator, with two reasons to change. It would also need to store the rate, which raises the question of what happens when rates change mid-stay. Pricing is business policy, not a property of a receipt.
2. **`_compute_fee()` in ParkingLot: the chosen approach.** All business rules live in the orchestrator, and Ticket stays an immutable record. Every future pricing change happens in one place, and the method can be tested with plain numbers.
3. **A `PricingStrategy` interface: not yet.** It's the right tool when many lots need completely different pricing models. For "one hourly rate", it's adding abstraction for requirements that don't exist (YAGNI). Bring it up only if asked how you'd support other pricing.

### Other decisions

- **Two enums with the same labels.** A spot type and a vehicle type are different ideas that happen to share names. Keeping them separate makes rules like "motorcycles can also use car spots" easy to write. The follow-ups do exactly that.
- **Active tickets in a dict, not a list.** Exit looks a ticket up by ID, and a dict makes that intent obvious. Speed isn't the real argument: with about 200 tickets, scanning a list takes microseconds.
- **The rate lives on ParkingLot.** Pricing is the lot's policy. A global constant would make testing harder. Passing the rate into `exit()` would force callers to know about pricing.
- **Money in integer cents.** Floats can't store values like 0.1 exactly, and the small errors add up. $5.47 is stored as 547.
- **Ticket stores `spot_id`, not a ParkingSpot.** A ticket is a record, not a way to reach into other objects, so it can't call methods on spots. This is the Law of Demeter.
- **Ticket stores `vehicle_type` even though flat pricing ignores it.** That costs nothing now, and makes per-vehicle pricing a small change later.
- **The same error for unknown and used tickets.** A used ticket is deleted on exit, so it looks identical to one that never existed. Telling them apart would need a separate set of used IDs; "invalid ticket" is enough here.
- **Validate before changing anything.** `enter` raises before touching the set. `exit` computes the fee before freeing the spot or deleting the ticket.
- **A minimum charge of 1 hour.** Rounding up turns 5 minutes into 1 hour, but a zero-length stay would round to 0 hours. `max(1, hours)` charges at least one hour.
- **No clever allocation.** "Prefer spots near the entrance" isn't in the requirements. If the interviewer wants smarter allocation, they'll ask.

## Python choices and why

### Classes

- **VehicleType and SpotType are `Enum`s.** Each is a fixed set of values, so an invalid type can't exist. Members are compared with `is`.
- **ParkingSpot is `@dataclass(frozen=True)`.** It holds only permanent properties, an ID and a type, so freezing it makes sure nothing changes them. The data class writes the constructor, and callers read `spot.id` directly, with no getters. Freezing it only works because occupancy lives in the lot, not on the spot.
- **Ticket is `@dataclass(frozen=True)`.** It's a receipt that must never change after it's issued. `__eq__` and `__repr__` come for free, and a readable `repr` helps when debugging.
- **ParkingLot is a regular class.** It's an orchestrator with private, internally built state (the ticket dict and the occupied set). Those shouldn't be constructor arguments or public fields, so a data class would be the wrong fit.

### Decorators and attributes

- **`ClassVar` for `MS_PER_HOUR` and `_SPOT_TYPE_FOR_VEHICLE`.** They're the same for every lot, so they live on the class. The vehicle-to-spot mapping is a dict lookup rather than an if-chain: adding a type is one line, and there's no "forgot a branch" bug.
- **`@staticmethod` for `_now_ms`.** It needs neither the lot nor the class. Keeping time-reading in one helper means there's a single place to replace for tests; the dry run patches `time.time` for that reason.
- **Leading underscores** on every field and helper. The public API is `enter` and `exit`, and nothing else.

### Exceptions

- **A small hierarchy under `ParkingLotError`.** `NoSpotAvailableError` and `InvalidTicketError` map to the two failures in the requirements. A gate can catch each one separately, or catch `ParkingLotError` to handle both.
- **`ValueError` for bad setup or input:** duplicate spot IDs, a negative rate, an unknown vehicle type, or an exit time before the entry time.

### Small details

- **`uuid.uuid4()` for ticket IDs.** They're unique without needing a counter.
- **`divmod`** for hours and remainder in one step.
- **`next(generator, None)`** to get the first free matching spot, or `None`.
- **`set.discard` on exit.** It never raises, even if the spot is somehow already free.

## Complexity

- `enter` is O(n) for the scan over spots, with O(1) set checks.
- `exit` is O(1): a dict lookup plus set and dict removals.
