"""Parking lot: assign spots, issue tickets, charge hourly on exit (requires Python 3.10+)."""

import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar


# ---------- Enums ----------

class VehicleType(Enum):
    MOTORCYCLE = "motorcycle"
    CAR = "car"
    LARGE = "large"


class SpotType(Enum):
    # Same labels as VehicleType on purpose, but a different concept:
    # what a spot IS vs what a vehicle IS. Keeping them apart makes
    # future rules like "motorcycles may use car spots" easy to express.
    MOTORCYCLE = "motorcycle"
    CAR = "car"
    LARGE = "large"


# ---------- Exceptions ----------

class ParkingLotError(Exception):
    """Base error for parking lot operations."""


class NoSpotAvailableError(ParkingLotError):
    """Raised when no free spot fits the vehicle."""


class InvalidTicketError(ParkingLotError):
    """Raised for an empty, unknown, or already-used ticket ID."""


# ---------- Data records ----------

@dataclass(frozen=True)
class ParkingSpot:
    # Intrinsic properties only. Whether it's occupied is the lot's business.
    id: str
    spot_type: SpotType

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Spot id cannot be empty")


@dataclass(frozen=True)
class Ticket:
    # A receipt for one parking session. Never changes after it's issued.
    id: str
    spot_id: str              # an ID, not a ParkingSpot: tickets don't reach into spots
    vehicle_type: VehicleType  # unused by flat pricing, kept for per-type pricing later
    entry_time_ms: int


# ---------- Orchestrator ----------

class ParkingLot:
    MS_PER_HOUR: ClassVar[int] = 60 * 60 * 1000
    _SPOT_TYPE_FOR_VEHICLE: ClassVar[dict[VehicleType, SpotType]] = {
        VehicleType.MOTORCYCLE: SpotType.MOTORCYCLE,
        VehicleType.CAR: SpotType.CAR,
        VehicleType.LARGE: SpotType.LARGE,
    }

    def __init__(self, spots: list[ParkingSpot], hourly_rate_cents: int) -> None:
        """
        Core logic:
        - Hold the spots, the hourly rate, the active tickets (by ID),
          and an index of occupied spot IDs

        Edge cases:
        - Two spots with the same ID -> ValueError
        - Negative rate -> ValueError
        """
        ids = [spot.id for spot in spots]
        if len(ids) != len(set(ids)):
            raise ValueError("Spot ids must be unique")
        if hourly_rate_cents < 0:
            raise ValueError("Hourly rate cannot be negative")
        self._spots = list(spots)
        self._hourly_rate_cents = hourly_rate_cents
        self._active_tickets: dict[str, Ticket] = {}
        self._occupied_spot_ids: set[str] = set()

    def enter(self, vehicle_type: VehicleType) -> Ticket:
        """
        Core logic:
        - Find a free spot of the matching type
        - Mark it occupied (add its ID to the occupied set)
        - Create a ticket with a unique ID, the spot, the vehicle type, and now
        - Store the ticket by ID and return it

        Edge cases:
        - No free matching spot -> NoSpotAvailableError, raised before
          anything changes
        - vehicle_type isn't a VehicleType -> ValueError
        """
        spot = self._find_available_spot(vehicle_type)
        if spot is None:
            raise NoSpotAvailableError(f"No available spot for {vehicle_type.value}")

        self._occupied_spot_ids.add(spot.id)
        ticket = Ticket(
            id=str(uuid.uuid4()),
            spot_id=spot.id,
            vehicle_type=vehicle_type,
            entry_time_ms=self._now_ms(),
        )
        self._active_tickets[ticket.id] = ticket
        return ticket

    def exit(self, ticket_id: str) -> int:
        """
        Core logic:
        - Look up the ticket by ID
        - Compute the fee from entry time to now
        - Free the spot and delete the ticket (so it can't be used twice)
        - Return the fee in cents

        Edge cases:
        - Empty ticket ID -> InvalidTicketError
        - Unknown ID -> InvalidTicketError; an already-used ticket looks the
          same, because it was deleted on its first exit
        - Fee is computed before freeing anything, so an error leaves the
          lot unchanged
        """
        if not ticket_id:
            raise InvalidTicketError("Ticket ID cannot be empty")

        ticket = self._active_tickets.get(ticket_id)
        if ticket is None:
            raise InvalidTicketError("Ticket not found or already used")

        fee = self._compute_fee(ticket.entry_time_ms, self._now_ms())

        self._occupied_spot_ids.discard(ticket.spot_id)
        del self._active_tickets[ticket_id]
        return fee

    def _find_available_spot(self, vehicle_type: VehicleType) -> ParkingSpot | None:
        """
        Core logic:
        - Map the vehicle type to its spot type
        - Return the first spot of that type that isn't occupied

        Edge cases:
        - Nothing free -> None
        - Unknown vehicle type -> ValueError
        """
        required = self._SPOT_TYPE_FOR_VEHICLE.get(vehicle_type)
        if required is None:
            raise ValueError(f"Unknown vehicle type: {vehicle_type!r}")
        return next(
            (
                spot
                for spot in self._spots
                if spot.spot_type is required and spot.id not in self._occupied_spot_ids
            ),
            None,
        )

    def _compute_fee(self, entry_ms: int, exit_ms: int) -> int:
        """
        Core logic:
        - Duration in hours, any partial hour rounds up (2.5 h -> 3 h)
        - Fee = hours x hourly rate, in cents

        Edge cases:
        - A zero-length stay still pays 1 hour (rounding alone would give 0)
        - Exit before entry (clock went backwards) -> ValueError
        """
        if exit_ms < entry_ms:
            raise ValueError("Exit time is before entry time")
        hours, remainder = divmod(exit_ms - entry_ms, self.MS_PER_HOUR)
        if remainder > 0:
            hours += 1
        return max(1, hours) * self._hourly_rate_cents

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)
