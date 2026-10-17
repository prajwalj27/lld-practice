# DISCUSSION

## CLARIFYING QUESTIONS -

1. What does the machine sell, and how are the items organized?
    - snacks and drinks in slots, each with a code (eg. A1)
    - each slot holds one product - name, price, remaining count
2. How does a customer pay?
    - cash only - nickels, dimes, quarters, $1 bills and $5 bills
    - no card payments
3. Does the customer pay first or select first?
    - insert money first, then select
    - can insert several coins or bills before selecting
4. Does the machine give change?
    - yes. just return the change amount
    - assume machine has enough coins, dont need to work out which coins to give back
5. What if they haven't inserted enough money?
    - reject selection, but keep their balance, so they can add more or cancel order
6. What if item is sold out?
    - reject it, keep balance
7. What if slot code doesn't exist?
    - reject
8. Can the customer cancel?
    - yes. machine refunds full balance
9. After a purchase, does the leftover money stay in the machine for another item?
    - no
    - one item per transaction, and leftover is returned as change
10. What about unsupported money, like a penny or a foreign coin?
    - reject
    - balance stays the same
11. Who stocks the machine?
    - an operator can setup slots and restock them
    - no login or authentication needed
12. What's out of scope?
    - card/mobile payments
    - tracking machine's own coin supply
    - database
    - concurrency
    - ui
    - managing multiple machines

## REQUIREMENTS

**Requirements** -

1. machine has slots identified by a code (eg. A1); each slot holds one product and a quantity
2. product has a name and price
3. accepted money: nickel, dime, quarter, $1, $5 - reject anything else
4. customer inserts money first; multiple inserts add to the balance
5. customer selects a slot code
    - reject if the code is invalid
    - reject if the slot is out of stock (balance kept)
    - reject if balance < price (balance kept)
    - otherwise dispense one item, return change = balance - price; reset balance to 0
6. one item per transaction; leftover money is returned as change
7. canel refunds the full balance
8. operator can add slots and restock them

**Out of Scope** -

- card / mobile payments
- tracking the machine's coin supply (assume change is always available)
- concurrency
- db / persistence
- ui
- multiple machines

## ENTITIES

**Entitites** -

- **Vending machine**: This is the orchestrator. It holds the slots and the balance and runs the insert, select, and cancel flow.
- **Slot**: It has state that changes (the quantity goes down on a sale and up on a restock) and its own behavior: checking if it’s empty, dispensing, and restocking. It’s a mutable data class.
- **Product**: It’s pure data, a name and a price, and neither changes after creation, so it’s a frozen data class.
- **Denomination**: It’s a fixed set of accepted values, so it’s an enum. Each member’s value is its worth in cents.
- **PurchaseResult**: This is a small frozen return value that bundles the dispensed product with the change, so select can return both.

**Not Entitites** -

- **Customer and operator**: They’re just the callers of the machine’s methods, and they have no state the system tracks.
- **Balance and change**: These are just integers on the machine.
- **Coin Supply**: Tracking it is out of scope.
