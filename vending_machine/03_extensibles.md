# Extensibles

Here are the extensions most likely to come up, roughly in order of how often they're asked. For each one: what changes, which class owns the change, and the key code.

## 1. Select first, then pay

**What changes:** the machine now has to remember the chosen item between calls. Store the selection, and dispense automatically once the balance covers the price.

- Add `self._selected_code: str | None = None` to `VendingMachine`.
- `select` validates the slot and stock, then stores the code. It no longer dispenses.
- `insert` rejects money if nothing is selected, adds to the balance, and completes the purchase once the balance covers the price.
- `cancel` refunds the balance and clears the selection.

```python
def select(self, code: str) -> None:
    slot = self._get_slot(code)
    if slot.is_empty():
        raise OutOfStockError(f"{slot.product.name} is out of stock")
    self._selected_code = code

def insert(self, denomination: Denomination) -> PurchaseResult | None:
    if self._selected_code is None:
        raise VendingMachineError("Select an item first")
    if not isinstance(denomination, Denomination):
        raise InvalidDenominationError(f"Unsupported money: {denomination!r}")
    self._balance_cents += denomination.value

    slot = self._slots[self._selected_code]
    if self._balance_cents >= slot.product.price_cents:
        return self._complete_purchase(slot)   # dispense, compute change, reset balance and selection
    return None
```

**What to say:** "Whether `_selected_code` is None already tells me the state, so I don't need a separate state field. If the states grew, say selecting, paying, dispensing, and maintenance, I'd use the **State pattern**: one class per state, each implementing `insert`, `select`, and `cancel`." Naming the pattern is enough at the new grad level.

### 2. The machine has a limited coin supply and returns real coins

**What changes:** change becomes a set of coins instead of a number, and the machine can fail to make change.

- Add `self._coin_inventory: dict[Denomination, int]` and a `load_coins(coin, count)` operator method.
- Track `self._inserted: list[Denomination]`, so `cancel` returns the customer's actual coins.
- Add `_make_change(amount)`, which returns a coin plan or None.
- In `select`, calculate the change plan **before** dispensing. If it's None, raise `CannotMakeChangeError` and keep the balance.
- `PurchaseResult.change` becomes `dict[Denomination, int]`.

```python
def _make_change(self, amount: int) -> dict[Denomination, int] | None:
    plan: dict[Denomination, int] = {}
    for coin in sorted(self._coin_inventory, key=lambda d: d.value, reverse=True):
        use = min(amount // coin.value, self._coin_inventory[coin])
        if use:
            plan[coin] = use
            amount -= use * coin.value
    return plan if amount == 0 else None
```

Once the purchase succeeds, subtract the plan from the inventory, and add the customer's inserted money to it. Only coins should go in the inventory, since machines don't usually give bills as change.

**What to say:** "Greedy works for normal coin sets with unlimited coins. With limited counts it can miss a valid answer. For 30 cents with one quarter, three dimes, and no nickels, greedy takes the quarter and gets stuck, but three dimes would work. To fix that properly, I'd use a DP search." Pointing out this limitation is a strong signal.

## 3. Card payments

**What changes:** add a second way to pay. This is the **Strategy pattern**: one interface with an implementation for each payment method.

```python
from abc import ABC, abstractmethod

class PaymentMethod(ABC):
    @abstractmethod
    def charge(self, amount_cents: int) -> bool: ...

class CardPayment(PaymentMethod):
    def charge(self, amount_cents: int) -> bool:
        return True   # would call a payment processor; mocked here

def buy_with(self, code: str, payment: PaymentMethod) -> Product:
    slot = self._get_slot(code)
    if slot.is_empty():
        raise OutOfStockError(f"{slot.product.name} is out of stock")
    if not payment.charge(slot.product.price_cents):
        raise PaymentDeclinedError("Payment declined")
    return slot.dispense_one()
```

The order still matters here: validate, then charge, then dispense. A declined card leaves the stock unchanged.

## 4. Buying more than one of an item

**What changes:** `select(code, quantity=1)`.

- Check that `quantity > 0`.
- Check `slot.quantity >= quantity`, otherwise raise `OutOfStockError`.
- Check `balance >= price * quantity`.
- Generalize `Slot.dispense_one()` to `Slot.dispense(count)`.
- Add a `quantity` field to `PurchaseResult`.

## 5. Keeping the balance for multiple purchases

**What changes:** `select` no longer resets the balance.

- Replace `self._balance_cents = 0` with `self._balance_cents -= price`.
- Change is returned only when the customer is finished, through `cancel()` (or a renamed `finish()`).
- `PurchaseResult` returns the remaining balance instead of change.

## 6. Operator features

These all go on `VendingMachine`, and each one is a few lines:

- **Change a price.** Product is frozen, so replace it instead of editing it: `slot.product = dataclasses.replace(slot.product, price_cents=new_price)`. That works because Slot isn't frozen.
- **Remove a slot.** Validate with `_get_slot(code)`, then `del self._slots[code]`.
- **Track revenue.** Add `self._total_sales_cents`, increase it in `select`, and add a `collect_cash()` method that returns the total and resets it.
- **Report low stock.** `[s.code for s in self._slots.values() if s.quantity <= threshold]`.

## 7. Sales history and reports

Add a frozen data class `Sale(code, product_name, price_cents, timestamp)` and a `self._sales: list[Sale]`. Append to it on each purchase. Reports are then simple loops over that list: total revenue, sales per product (`collections.Counter`), and best seller.

## 8. Discounts and promotions

Move pricing into one method so there's a single place to change it:

```python
def _price_for(self, product: Product) -> int:
    return product.price_cents * (100 - self._discount_percent) // 100
```

`select` calls `_price_for(product)` instead of reading `price_cents` directly. Keep the math in integers so you stay in cents. For several kinds of promotion, this becomes another Strategy, with one pricing rule class per promotion.

## 9. Several machines

Add a `VendingMachineFleet` that holds `dict[str, VendingMachine]`, with methods like `restock_all` and `total_revenue`. `VendingMachine` itself doesn't change, and that's worth saying out loud: it shows the original design was self-contained.

## 10. Concurrency

If the machine were reached through an API with several users at once, add `self._lock = threading.Lock()` and wrap the body of `insert`, `select`, and `cancel` in `with self._lock:`. That way two purchases can't both see a slot's last item as available.

**How to approach any extension in the interview:**

1. Say which class owns the new data or behavior.
2. Say what changes and what stays the same.
3. Keep validating before you change any state.

Name a pattern (State or Strategy) when it fits, but don't build it out unless you're asked to.