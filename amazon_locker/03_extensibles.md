# Amazon Locker: follow-ups

Junior candidates often get none of these, mid-level one or two, senior more depth. Explaining where the change lives is usually enough.

## 1. Size fallback (a smaller package can use a bigger compartment)

Only `_find_available_compartment` changes. Try the exact size first, then each larger size, and never a smaller one, since the package wouldn't fit. Enum members iterate in the order they're defined, so `list(Size)` already runs from SMALL to LARGE.

```python
def _find_available_compartment(self, size: Size) -> Compartment | None:
    sizes = list(Size)
    for candidate in sizes[sizes.index(size):]:
        found = next(
            (c for c in self._compartments if c.size is candidate and not c.is_occupied),
            None,
        )
        if found is not None:
            return found
    return None
```

## 2. Staff marks expired packages as removed

Today, expired compartments stay occupied forever. Add the cleanup step that follows `open_expired_compartments`:

```python
def confirm_expired_removed(self) -> list[str]:
    now = self._clock()
    expired = [t for t in self._tokens.values() if t.is_expired(now)]
    for token in expired:
        self._clear_deposit(token)
    return [t.compartment.id for t in expired]
```

The expired tokens are collected into a list first, because deleting from a dict while looping over it raises an error.

## 3. Broken or out-of-service compartments

Replace the `occupied` bool with a status enum:

```python
class CompartmentStatus(Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    OUT_OF_SERVICE = "out_of_service"
```

- Compartment gets `is_available`, `mark_occupied`, `mark_available`, `mark_out_of_service`, and `mark_in_service`.
- The allocation check becomes `c.size is size and c.is_available`, so out-of-service compartments are skipped automatically.
- New edge case: a broken compartment that still has a package inside. Either block taking it out of service until it's emptied, or let staff handle it manually.

**What to say:** "This is physical state, so it lives on Compartment, the same reasoning as `occupied`."

## 4. Make sure the package is actually deposited (two-phase)

Today the door opens and we assume the driver uses it. To confirm the package is really there, split the deposit in two:

```
reserve_compartment(size) -> reservation_id    # status RESERVED, door opens
confirm_deposit(reservation_id) -> code         # status OCCUPIED, token created
cancel_reservation(reservation_id) -> None      # back to AVAILABLE
```

- Add a `RESERVED` status and a `_reservations: dict[str, (Compartment, reserved_at)]`.
- Add a timeout: a reservation that isn't confirmed within 2 to 3 minutes is cancelled. That can be checked lazily on the next call, using the same injected clock.
- The trade-off is more states and more cleanup paths. For the interview, single-step is fine; in production, a door sensor or confirmation step is essential.

## 5. Faster allocation for very large lockers

Keep `dict[Size, collections.deque[Compartment]]` of free compartments. A deposit uses `popleft()`, and a cleanup uses `append()`, both O(1). The FIFO order also spreads wear across doors.

The cost: availability now lives in two places, so every path that frees a compartment must put it back exactly once. Say when it's worth it: thousands of compartments, not 50.

## 6. Tell "already used" apart from "never existed"

Keep `self._used_codes: set[str]`, add the code on pickup, and raise a separate `UsedTokenError`.

The trade-off: the set grows forever, so it needs pruning, for example dropping codes older than 7 days. Mention that the UX gain is small.

## 7. Lockout after repeated wrong codes

Track failed attempts in Locker, either per keypad or per code prefix, with a time window. After N failures, reject all input until `locked_until`. The injected clock makes it testable. This is relational, system-managed state, so it belongs in the orchestrator.

## 8. Notifying the customer

Keep the Locker free of SMS and email code. Accept an optional `on_deposit: Callable[[str], None]` callback, or a list of observers (the **Observer** pattern), and call it with the code after a successful deposit. The notification system plugs in from outside.

## 9. When does Package become a real entity?

When the locker needs more than the size: for example, several packages in one compartment, per-package tracking, or weight limits. Then a `Package(id, size)` gets stored on the compartment or the token, and a token can map to a list of packages.

## 10. Multiple locker locations, and concurrency

- **Multiple locations.** A `LockerNetwork` holds `dict[location_id, Locker]` and routes each deposit to the chosen locker. Codes must be unique per locker; prefix them with the locker id if they need to be unique across the whole network.
- **Concurrency.** Two kiosks or drivers acting at once could both pick the same free compartment. A `threading.Lock` around `deposit_package` and `pickup` prevents that. Mention it in one line.

## What interviewers look for, by level

- **Junior.** Sensible classes (Locker, Compartment, AccessToken) and working happy paths: a package goes in, a code comes out, and the code gets it back out. You don't need every edge case on the first pass, but show you know they exist. Needing hints on the entities is fine.
- **Mid-level.** Reason your way to "Package isn't an entity" and the three-class model. Clear responsibilities. Handle invalid, expired, and full cases. Explain why occupancy sits on Compartment. Discuss one follow-up.
- **Senior.** Lead the conversation. Justify the model with Information Expert. Raise the trade-offs before you're asked: occupancy on the entity vs a set, lazy expiry, when Package becomes an entity. Bring up fallback, failures, and multi-package cases early.
