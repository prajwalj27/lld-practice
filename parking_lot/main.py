"""Dry run for the parking lot. Run: python main.py

The base design reads the real clock inside enter() and exit(), so this runner
has to patch time.time to fake "2.5 hours later". Follow-up #4 in
03_extensibles.md (passing timestamps into enter/exit) removes the need for that.
"""

from datetime import timedelta
from unittest.mock import patch

from implementation import (
    ParkingLot,
    ParkingLotError,
    ParkingSpot,
    SpotType,
    VehicleType,
)


class FakeTime:
    """Stands in for time.time(): returns seconds we control."""

    def __init__(self, start_seconds: float) -> None:
        self.seconds = start_seconds

    def __call__(self) -> float:
        return self.seconds

    def advance(self, **kwargs: float) -> None:
        self.seconds += timedelta(**kwargs).total_seconds()


def dollars(cents: int) -> str:
    return f"${cents / 100:.2f}"


def attempt(label: str, action):
    print(f"\n> {label}")
    try:
        result = action()
        print(f"  -> {result}")
        return result
    except ParkingLotError as error:
        print(f"  -> {type(error).__name__}: {error}")
        return None


def main() -> None:
    clock = FakeTime(start_seconds=1_000_000)
    spots = [
        ParkingSpot("A", SpotType.MOTORCYCLE),
        ParkingSpot("B", SpotType.CAR),
        ParkingSpot("C", SpotType.LARGE),
    ]
    lot = ParkingLot(spots, hourly_rate_cents=500)  # $5 per hour

    with patch("implementation.time.time", clock):
        car = attempt("Car enters", lambda: lot.enter(VehicleType.CAR))
        attempt("Another car enters (the only CAR spot is taken)",
                lambda: lot.enter(VehicleType.CAR))

        clock.advance(hours=2.5)
        attempt("Car exits 2.5 hours later (rounds up to 3 h)",
                      lambda: dollars(lot.exit(car.id)))
        attempt("Same ticket again (already used)", lambda: lot.exit(car.id))
        attempt("Ticket that never existed", lambda: lot.exit("no-such-ticket"))
        attempt("Empty ticket ID", lambda: lot.exit(""))

        print("\n--- Rounding ---")
        for label, duration in [
            ("0 minutes", timedelta()),
            ("5 minutes", timedelta(minutes=5)),
            ("exactly 2 hours", timedelta(hours=2)),
            ("2 hours 1 minute", timedelta(hours=2, minutes=1)),
        ]:
            ticket = lot.enter(VehicleType.MOTORCYCLE)
            clock.seconds += duration.total_seconds()
            print(f"  motorcycle parked {label:<17} -> {dollars(lot.exit(ticket.id))}")

        print("\n--- Exact type matching ---")
        lot.enter(VehicleType.LARGE)
        attempt("Second LARGE vehicle (CAR and MOTORCYCLE spots are free, but don't fit the rule)",
                lambda: lot.enter(VehicleType.LARGE))


if __name__ == "__main__":
    main()
