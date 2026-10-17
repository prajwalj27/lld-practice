# Amazon Locker: class design and relationships

Design top-down: Locker first, since it's the entry point, then AccessToken, then Compartment. For each class, ask two questions of the requirements: what must it remember (its state), and what must it do (its public methods)?

## Deriving the state

| Requirement | Who tracks what |
|---|---|
| Assign a free compartment of matching size | Locker: all compartments. Compartment: its own size and whether it's occupied |
| Pick up by entering a code | Locker: a map from code to AccessToken, for fast lookup |
| A code is generated and returned | AccessToken: the code |
| Codes expire after 7 days | AccessToken: the expiry time |
| Validate the code and open the compartment | AccessToken: the compartment it opens |

## Class design

```
enum Size: SMALL, MEDIUM, LARGE

class Compartment:
    - _id: str
    - _size: Size
    - _occupied: bool
    + id, size, is_occupied              (read-only properties)
    + mark_occupied() -> None
    + mark_free() -> None
    + open() -> None                     (hardware hook)

class AccessToken:                       (frozen dataclass)
    - code: str
    - expires_at: datetime
    - compartment: Compartment
    + is_expired(now) -> bool

class Locker:
    - TOKEN_TTL = 7 days, CODE_DIGITS = 6        (class constants)
    - _compartments: list[Compartment]
    - _tokens: dict[str, AccessToken]
    - _clock: Callable[[], datetime]
    + Locker(compartments, clock=now)
    + deposit_package(size) -> str               (the code)
    + pickup(code) -> None                       (raises on a bad code)
    + open_expired_compartments() -> list[str]   (ids of doors opened)
    - _find_available_compartment(size) -> Compartment | None
    - _generate_token(compartment) -> AccessToken
    - _clear_deposit(token) -> None

exceptions: LockerError
    ├─ NoCompartmentAvailableError
    ├─ InvalidTokenError
    └─ ExpiredTokenError
```

## Relationships

- **Locker owns many Compartments, and maps each code to one AccessToken.**
- **Each AccessToken points to exactly one Compartment.** Each occupied compartment has exactly one live token, since there's one code per package.
- **Compartment knows nothing about tokens.** It only knows its own physical state.

This follows **Information Expert**: the class that owns the data is the one that uses it. AccessToken owns the expiry time, so it decides whether it's expired. Compartment owns its physical state, so it marks itself occupied or free. Locker runs the workflow.

## Flows

```
deposit_package(size)
  ├─ not a Size?                     -> ValueError
  ├─ no free compartment that size?  -> NoCompartmentAvailableError
  ├─ open door, mark occupied
  ├─ token = code + (now + 7 days) + compartment, stored by code
  └─ return code

pickup(code)
  ├─ empty, or not in the map?       -> InvalidTokenError
  ├─ expired?                        -> ExpiredTokenError (token and package stay)
  ├─ open door
  └─ clear deposit: free the compartment AND delete the token

open_expired_compartments()
  └─ open every compartment whose token has expired (nothing is freed)
```

## Design decisions worth saying out loud

### Where occupancy lives

When deciding where state belongs, ask whether it's **physical** or **relational**. Physical state, like "has a package" or "is broken", describes the thing itself, so it goes on the entity. Relational state, like "assigned to this token", describes a link the system manages, so it goes in the orchestrator.

Here, occupancy goes on Compartment, because a package being inside is physical. In the parking lot problem, we kept occupancy as a set in the orchestrator instead. Both are fine. What matters is that you can defend your reason.

There are three ways to find a free compartment:

1. **Work out occupancy from the tokens** (a compartment is taken if some token points to it). This is wrong here. An expired token has to stay in the map, so pickup can say "expired" rather than "invalid", yet the package is still physically there. If you skip expired tokens, you'd hand out a compartment that still has a package in it. Whether a code is valid and whether a package is present are different facts, and you can't derive one from the other.
2. **Index free compartments by size**, with a dict from Size to a queue of free compartments. This makes lookup O(1), and the queue spreads wear across doors. But availability now lives in two places, and forgetting to put a compartment back, or putting it back twice, silently corrupts it. That's worth it with thousands of compartments.
3. **An `occupied` flag on each Compartment, and scan the list.** This is the chosen approach. There's one source of truth, and for a locker of 20 to 50 compartments the O(n) scan is negligible.

### API shape

- **`deposit_package` returns only the code.** The door opens in front of the driver, so they don't need a compartment number. The code goes to the customer, through some other system.
- **`pickup` returns nothing.** Success is the door opening. Failure is a specific exception.
- **`open_expired_compartments` returns the ids it opened.** It's not strictly required, but it's free to provide, and a staff screen could use it.

### Errors and expiry

- **Unknown codes and used codes get the same error.** A used code's token is deleted on pickup, so it looks exactly like a code that never existed. Telling them apart would mean tracking used codes, which adds state for little benefit; "this code doesn't work" is enough.
- **Expired codes get their own error.** That's actionable: the customer knows to contact support about a package that's still inside.
- **Expired tokens stay in the map.** They're needed for the "expired" message and for `open_expired_compartments`. Expiry is checked when a code is used (lazy), not by a background job.
- **`open_expired_compartments` doesn't free anything.** The packages are still inside until staff physically removes them. A separate "removed" step would free them; that's out of scope here, and covered in the follow-ups.

### Other choices

- **`open()` is a hardware hook.** We assume the door closes and locks itself after about 30 seconds, and that the driver really does put the package in. Checking that the package is actually there needs a two-step reserve-then-confirm flow, covered in the follow-ups.
- **`_clear_deposit` does both cleanup steps together.** It frees the compartment and deletes the token. Forget either, and the compartment and token map disagree.
- **The clock is injected.** Locker takes a `clock` function that defaults to the real time. Tests pass a fake clock, so "8 days later" takes no time to test. It's the same idea as the parking lot's timestamp parameter.

## Python choices and why

### Classes

- **Size is an `Enum`.** It's a fixed set of values, so an invalid size like `"XL"` can't exist. Members are compared with `is`.
- **AccessToken is `@dataclass(frozen=True)`.** A token is a record whose code, expiry, and compartment never change. Freezing it means nothing can quietly extend an expiry date or point a token at a different door. It's a data class *with* one method, which is fine because `is_expired` only uses the token's own fields.
- **Compartment is a regular class.** Its id and size must be fixed while `occupied` changes. A data class would make every field publicly changeable. A regular class with read-only properties for `id` and `size`, plus methods that change `occupied`, enforces exactly those rules.
- **Locker is a regular class.** It's an orchestrator with private, internally built state.

### Decorators and attributes

- **`@property` for `id`, `size`, `is_occupied`.** They read like fields but can't be assigned. The only way to change occupancy is `mark_occupied()` and `mark_free()`, which check that the change is valid.
- **`ClassVar` for `TOKEN_TTL` and `CODE_DIGITS`.** They're the same for every locker, so they belong to the class, and there's one place to change the 7 days.
- **Leading underscores on `_compartments`, `_tokens`, `_clock`, and the helper methods.** These are internal. Callers only use deposit, pickup, and open-expired.
- **A subclass for the hardware.** The runner's `LoggingCompartment` overrides `open()` to print. A real system would override it to drive the lock, and Locker doesn't change at all.

### Exceptions

- **A small hierarchy under `LockerError`.** `NoCompartmentAvailableError`, `InvalidTokenError`, and `ExpiredTokenError` each map to a specific message from the requirements. A kiosk can catch each one and show the right screen, or catch `LockerError` to handle them all.
- **`ValueError` for bad input,** like an unknown size, an empty or duplicate compartment id, or a locker with no compartments.
- **`RuntimeError` in `mark_occupied` and `mark_free`** when the compartment is already in that state. That can only happen through a bug, so the compartment fails loudly instead of quietly breaking its own rule. It's the same defensive check as `Slot.dispense_one` in the vending machine.

### Small details

- **`secrets.randbelow` for codes, not `random`.** Codes open real doors, so they must be unpredictable. The code is drawn again if it clashes with a live token.
- **Timezone-aware times (`datetime.now(timezone.utc)`).** These avoid daylight-saving surprises, and Python refuses to compare them with naive times, which catches mixing bugs.
- **`>=` in `is_expired`.** A code is expired at exactly 7 days, not one moment later.
- **`next(generator, None)` in `_find_available_compartment`.** It returns the first match or `None` in one expression.
- **`timedelta(days=7)`.** Date math stays readable and correct across month boundaries.

## Complexity

- `deposit_package` is O(n) for the scan, with n = number of compartments.
- `pickup` is O(1), a dict lookup.
- `open_expired_compartments` is O(number of tokens).
