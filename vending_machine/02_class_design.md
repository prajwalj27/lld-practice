# Class Design and Relationships

## CLASS DESIGN

```python
enum Denomination:
    NICKEL = 5, DIME = 10, QUARTER = 25, ONE_DOLLAR = 100, FIVE_DOLLAR = 500

class Product:      (frozen dataclass)
    - name: str
    - price_cents: int

class Slot:         (mutable dataclass)
    - code: str
    - product: Product
    - quantity: int
    + is_empty() -> bool
    + dispense_one() -> Product
    + restock(amount) -> None

class VendingMachine:
    - _slots: dict[str, Slot]
    - _balance_cents: int
    + balance_cents -> int      (read-only property)
    + add_slot(code, product, quantity) -> None
    + insert(denomination) -> int 
    + select(code) -> PurchaseResult
    + cancel() -> int
    + restock(code, amount) -> None
    + _get_slot(code) -> Slot
```

## RELATIONSHIPS

- The VendingMachine owns many Slots, stored in a dict keyed by code so lookup is O(1).
- Each Slot holds one Product and the count of that product left.
 insert takes a Denomination, and select returns a PurchaseResult that refers to the dispensed Product.

## DESIGN DECISIONS

- Money is stored in integer cents, for the same reason as in the parking lot: it avoids floating-point errors.
- The balance is the only state; there’s no state enum. Many vending machine solutions use states like IDLE and HAS_MONEY. Here, those can be worked out directly from balance > 0, so a separate state field would just be a second copy that could drift out of sync. That’s the same lesson as the occupied set in the parking lot.
- Product is frozen, but Slot isn’t. A price is fixed, but the quantity changes with every sale. This is the same reasoning that kept ParkingSpot frozen only once the occupied state moved into the lot.
- Every check runs before any change. select checks that the slot exists, then that it’s in stock, then that there’s enough money, and only then changes anything. A failed purchase leaves the machine exactly as it was.
- The stock check comes before the funds check. That way you never tell someone to insert more money for an item you can’t sell them.
- @property makes balance_cents read-only. Callers can check the balance, but they can’t set it. A property is a method that’s read like a field: machine.balance_cents, with no parentheses.
