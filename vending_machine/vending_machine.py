from dataclasses import dataclass
from enum import Enum

# ---------- Enums ---------

class Denomination(Enum):
    NICKEL = 5
    DIME = 10
    QUARTER = 25
    ONE_DOLLAR = 100
    FIVE_DOLLAR = 500


# ---------- Exceptions ----------

class VendingMachineError(Exception):
    """Base error for vending machine operations."""


class InvalidDenominationError(VendingMachineError):
    """Raised when inserted money is not an accepted denomination."""


class InvalidSlotError(VendingMachineError):
    """Raised when a slot code does not exist."""


class OutOfStockError(VendingMachineError):
    """Raised when the selected slot is empty."""


class InsufficientFundsError(VendingMachineError):
    """Raised when the balance is less than the product price."""


# ---------- Data classes ----------

@dataclass(frozen=True)
class Product:
    name: str
    price_cents: int

    def __post_init__(self) -> None:
        # A product's price never changes, so it is validated once at creation.
        if self.price_cents <= 0:
            raise ValueError("Price must be +ve")


@dataclass
class Slot:
    # Not frozen: quantity changes on every sale and restock
    code: str
    product: Product
    quantity: int

    def is_empty(self) -> bool:
        return self.quantity == 0

    def dispense_one(self) -> Product:
        """
        Logic:
        - decrease quantity by 1
        - return the product

        edge cases
        - slot is empty -> OutOfStockError
        (defensive guard: the machine checks first, but the slot
        protects its own rule that quantity never goes negative)
        """
        if self.is_empty():
            raise OutOfStockError(f"Slot {self.code} is empty")
        self.quantity -= 1
        return self.product

    def restock(self, amount: int) -> None:
        """
        Core Logic:
        - Increase quantity by amount

        Edge Cases:
        - amount is 0 or -ve -> ValueError
        """
        if amount <= 0:
            raise ValueError("Restock amount must be +ve")
        self.quantity += amount


@dataclass(frozen=True)
class PurchaseResult:
    product: Product
    change_cents: int


# ---------- Orchestrator ----------

class VendingMachine:
    def __init__(self) -> None:
        self._slots: dict[str, Slot] = {}
        self._balance_cents = 0

    @property
    def balance_cents(self) -> int:
        # Read-only from outside: callers can see the balance but not set it
        return self._balance_cents

    def add_slot(self, code: str, product: Product, quantity: int) -> None:
        """
        Core Logic
        - create a slot holding one product and its starting quantity
        - store it by code for O(1) lookup
        
        Edge Cases
        - empty slot code -> ValueError
        - Slot code already exists -> ValueError
        - -ve quantity -> ValueError (0 is allowed = empty slot)
        - Invalid price is already rejected when the Product is created
        """
        if not code:
            raise ValueError("Slot code cannot be empty")
        if code in self._slots:
            raise ValueError(f"Slot {code} already exists")
        if quantity < 0:
            raise ValueError("Quantity cannot be negative")
        self._slots[code] = Slot(code, product, quantity)

    def insert(self, denomination: Denomination) -> int:
        """
        Core logic
        - accept only supported coins and bills
        - add the value to the balance
        - return new balance

        Edge cases
        - Unsupported money (Not a Denomination) -> InvalidDenominationError; balance unchanged
        - Mulitple inserts accumulate 
        """
        if not isinstance(denomination, Denomination):
            raise InvalidDenominationError(f"Unsupported money: {denomination!r}")
        self._balance_cents += denomination.value
        return self._balance_cents

    def _get_slot(self, code: str) -> Slot:
        slot = self._slots.get(code)        # returns None if slot doesn't exist, instead of a KeyError
        if slot is None:
            raise InvalidSlotError(f"Slot {code!r} doesn't exist") 
        return slot

    def select(self, code: str) -> PurchaseResult:
        """
        Core Logic
        - Look up the slot by code
        - Check the slot has stock
        - check the balance covers the price
        - Dispense one item
        - Change = balance - price, then reset the balance to 0
        - Return the product and the change

        Edge cases
        - Slot code doesn't exist -> InvalidSlotError
        - Slot is Empty -> OutOfStockError, balance kept
        - Balance < price (including no money) -> InsufficientFundsError, balance kept so the customer can add more or cancel
        - Exact payment -> change is 0
        - Every check runs before any state changes, so a failed selection leaves the money untouched
        """
        slot = self._get_slot(code)

        if slot.is_empty():
            raise OutOfStockError(f"{slot.product.name} is out of stock")

        price = slot.product.price_cents
        if self._balance_cents < price:
            shortfall = price - self._balance_cents
            raise InsufficientFundsError(
            f"Insert {shortfall} more cents for {slot.product.name}"
        )

        product = slot.dispense_one()
        change = self.balance_cents - price
        self._balance_cents = 0
        return PurchaseResult(product, change)

    def cancel(self) -> int:
        """
        Core Logic
        - Refund the full balance
        - Reset the balance to 0

        Edge Cases
        - No money inserted -> refund 0 (not an error)
        - Cancel called twice -> second call refunds 0
        """
        refund = self._balance_cents
        self._balance_cents = 0
        return refund

    def restock(self, code: str, amount: int) -> None:
        """
        Core logic:
        - Find the slot and add stock to it

        Edge cases:
        - Slot code doesn't exist -> InvalidSlotError
        - amount is zero or negative -> ValueError (raised by Slot)
        """
        self._get_slot(code).restock(amount)
    