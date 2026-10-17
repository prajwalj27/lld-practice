"""Amazon Locker: deposit packages, pick them up with an access code (requires Python 3.10+)."""

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import ClassVar


# ---------- Enum ----------

class Size(Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


# ---------- Exceptions ----------

class LockerError(Exception):
    """Base error for locker operations."""


class NoCompartmentAvailableError(LockerError):
    """Raised when no free compartment of the requested size exists."""


class InvalidTokenError(LockerError):
    """Raised for an empty code, a code that never existed, or one already used."""


class ExpiredTokenError(LockerError):
    """Raised when a real code is used after it expired."""


# ---------- Compartment ----------

class Compartment:
    """A physical slot. Knows its id, its size, and whether a package is inside."""

    def __init__(self, compartment_id: str, size: Size) -> None:
        """
        Edge cases:
        - Empty id -> ValueError
        - size isn't a Size -> ValueError
        """
        if not compartment_id:
            raise ValueError("Compartment id cannot be empty")
        if not isinstance(size, Size):
            raise ValueError(f"Invalid size: {size!r}")
        self._id = compartment_id
        self._size = size
        self._occupied = False

    @property
    def id(self) -> str:
        return self._id

    @property
    def size(self) -> Size:
        return self._size

    @property
    def is_occupied(self) -> bool:
        return self._occupied

    def mark_occupied(self) -> None:
        """
        Edge cases:
        - Already occupied -> RuntimeError (two packages in one slot is a bug)
        """
        if self._occupied:
            raise RuntimeError(f"Compartment {self._id} is already occupied")
        self._occupied = True

    def mark_free(self) -> None:
        """
        Edge cases:
        - Already free -> RuntimeError (a double cleanup is a bug)
        """
        if not self._occupied:
            raise RuntimeError(f"Compartment {self._id} is already free")
        self._occupied = False

    def open(self) -> None:
        """Hardware hook: unlock the door. The hardware closes and locks it again
        on its own after ~30 seconds. A real system overrides this to talk to the lock."""


# ---------- Access token ----------

@dataclass(frozen=True)
class AccessToken:
    code: str
    expires_at: datetime
    compartment: Compartment

    def is_expired(self, now: datetime) -> bool:
        """
        Core logic:
        - Expired once the current time reaches the expiry time

        Edge cases:
        - Exactly at expires_at -> expired (>=, not >)
        - "now" is passed in, so tests control time instead of waiting 7 days
        """
        return now >= self.expires_at


# ---------- Locker (orchestrator) ----------

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Locker:
    TOKEN_TTL: ClassVar[timedelta] = timedelta(days=7)
    CODE_DIGITS: ClassVar[int] = 6

    def __init__(
        self,
        compartments: list[Compartment],
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        """
        Core logic:
        - Hold every compartment and a code -> AccessToken map
        - clock returns the current time; tests pass a fake clock

        Edge cases:
        - No compartments -> ValueError
        - Two compartments with the same id -> ValueError
        """
        if not compartments:
            raise ValueError("A locker needs at least one compartment")
        ids = [c.id for c in compartments]
        if len(ids) != len(set(ids)):
            raise ValueError("Compartment ids must be unique")
        self._compartments = list(compartments)
        self._tokens: dict[str, AccessToken] = {}
        self._clock = clock

    def deposit_package(self, size: Size) -> str:
        """
        Core logic:
        - Find a free compartment of exactly this size
        - Open its door, mark it occupied
        - Create an access token that expires in 7 days and store it by code
        - Return only the code (the driver sees which door opened; the code
          goes to the customer through some other system)

        Edge cases:
        - size isn't a Size -> ValueError
        - No free compartment of that size -> NoCompartmentAvailableError,
          even if bigger ones are free (exact match only)
        """
        if not isinstance(size, Size):
            raise ValueError(f"Invalid size: {size!r}")

        compartment = self._find_available_compartment(size)
        if compartment is None:
            raise NoCompartmentAvailableError(f"No available {size.value} compartment")

        compartment.open()
        compartment.mark_occupied()
        token = self._generate_token(compartment)
        self._tokens[token.code] = token
        return token.code

    def pickup(self, code: str) -> None:
        """
        Core logic:
        - Look up the token by code
        - Not expired -> open the door, free the compartment, delete the token

        Edge cases:
        - Empty code -> InvalidTokenError
        - Unknown code -> InvalidTokenError (an already-used code looks the
          same, since its token was deleted on pickup)
        - Expired code -> ExpiredTokenError; the token stays so staff can find
          the package, and the compartment stays occupied
        """
        if not code:
            raise InvalidTokenError("Invalid access token code")

        token = self._tokens.get(code)
        if token is None:
            raise InvalidTokenError("Invalid access token code")
        if token.is_expired(self._clock()):
            raise ExpiredTokenError("Access token has expired")

        token.compartment.open()
        self._clear_deposit(token)

    def open_expired_compartments(self) -> list[str]:
        """
        Core logic:
        - Open every compartment whose token has expired, so staff can
          remove the packages and return them to the sender
        - Return the ids of the doors that opened

        Edge cases:
        - Nothing expired -> nothing opens, returns []
        - Doesn't free anything: the packages are still physically inside
          until staff removes them
        """
        now = self._clock()
        opened = []
        for token in self._tokens.values():
            if token.is_expired(now):
                token.compartment.open()
                opened.append(token.compartment.id)
        return opened

    def _find_available_compartment(self, size: Size) -> Compartment | None:
        return next(
            (c for c in self._compartments if c.size is size and not c.is_occupied),
            None,
        )

    def _generate_token(self, compartment: Compartment) -> AccessToken:
        """
        Core logic:
        - Random 6-digit code from `secrets` (cryptographically secure)
        - Expires TOKEN_TTL from now

        Edge cases:
        - Code collides with a live token -> draw again
        """
        while True:
            code = f"{secrets.randbelow(10 ** self.CODE_DIGITS):0{self.CODE_DIGITS}d}"
            if code not in self._tokens:
                break
        return AccessToken(code, self._clock() + self.TOKEN_TTL, compartment)

    def _clear_deposit(self, token: AccessToken) -> None:
        # Both steps, always together: forgetting either leaves the
        # compartment and the token map out of sync.
        token.compartment.mark_free()
        del self._tokens[token.code]
