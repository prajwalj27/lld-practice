"""Dry run for the Amazon Locker. Run: python main.py"""

from datetime import datetime, timedelta, timezone

from implementation import Compartment, Locker, LockerError, Size


class FakeClock:
    """A clock the dry run controls, so 'eight days later' takes no time."""

    def __init__(self, start: datetime) -> None:
        self._now = start

    def __call__(self) -> datetime:
        return self._now

    def advance(self, **kwargs: float) -> None:
        self._now += timedelta(**kwargs)


class LoggingCompartment(Compartment):
    """Stands in for the door hardware: prints when a door opens."""

    def open(self) -> None:
        print(f"  [door {self.id} opens]")


def show(locker_compartments: list[Compartment]) -> None:
    states = ", ".join(
        f"{c.id}={'full' if c.is_occupied else 'free'}" for c in locker_compartments
    )
    print(f"  compartments: {states}")


def attempt(label: str, action) -> object:
    print(f"\n> {label}")
    try:
        result = action()
        if result is not None:
            print(f"  -> {result}")
        return result
    except LockerError as error:
        print(f"  -> {type(error).__name__}: {error}")
        return None


def main() -> None:
    clock = FakeClock(datetime(2026, 10, 17, 9, 0, tzinfo=timezone.utc))
    compartments = [
        LoggingCompartment("S1", Size.SMALL),
        LoggingCompartment("M1", Size.MEDIUM),
        LoggingCompartment("M2", Size.MEDIUM),
        LoggingCompartment("L1", Size.LARGE),
    ]
    locker = Locker(compartments, clock=clock)
    show(compartments)

    code_a = attempt("Driver deposits a MEDIUM package",
                     lambda: locker.deposit_package(Size.MEDIUM))
    code_b = attempt("Driver deposits another MEDIUM package",
                     lambda: locker.deposit_package(Size.MEDIUM))
    attempt("Third MEDIUM package (L1 is free, but sizes must match exactly)",
            lambda: locker.deposit_package(Size.MEDIUM))
    show(compartments)

    attempt("Customer picks up with the first code",
            lambda: locker.pickup(code_a))
    show(compartments)
    attempt("Same code again (already used)", lambda: locker.pickup(code_a))
    attempt("A code that never existed", lambda: locker.pickup("not-a-code"))
    attempt("Empty code", lambda: locker.pickup(""))

    print("\n... 8 days pass ...")
    clock.advance(days=8)

    attempt("Customer tries the second code (expired)",
            lambda: locker.pickup(code_b))
    show(compartments)
    attempt("New MEDIUM package: M2 still holds the expired one, so M1 is used",
            lambda: locker.deposit_package(Size.MEDIUM))
    attempt("Staff opens all expired compartments",
            lambda: locker.open_expired_compartments())
    show(compartments)


if __name__ == "__main__":
    main()
