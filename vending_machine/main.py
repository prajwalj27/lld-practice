from vending_machine import VendingMachine, Product, Denomination, VendingMachineError

def main() -> None:
    machine = VendingMachine()
    machine.add_slot("A1", Product("Chips", 125), 2)
    machine.add_slot("A2", Product("Soda", 150), 1)
    machine.add_slot("B1", Product("Gum", 75), 0)

    def try_select(code: str) -> None:
        try:
            result = machine.select(code)
            print(f"Got {result.product.name}, change: {result.change_cents}")
        except VendingMachineError as error:
            print(f"Error: {error}")

    print("--- Buy chips with exact money ---")
    print("Balance:", machine.insert(Denomination.ONE_DOLLAR))
    print("Balance:", machine.insert(Denomination.QUARTER))
    try_select("A1")

    print("\n--- Buy soda with a $5 bill ---")
    print("Balance:", machine.insert(Denomination.FIVE_DOLLAR))
    try_select("A2")

    print("\n--- Not enough money ---")
    print("Balance:", machine.insert(Denomination.ONE_DOLLAR))
    try_select("A1")
    print("Balance kept:", machine.balance_cents)

    print("\n--- Sold out ---")
    try_select("A2")

    print("\n--- Invalid slot ---")
    try_select("Z9")

    print("\n--- Cancel ---")
    print("Refunded:", machine.cancel())
    print("Balance:", machine.balance_cents)

    print("\n--- Restock gum, then buy it ---")
    machine.restock("B1", 3)
    print("Balance:", machine.insert(Denomination.ONE_DOLLAR))
    try_select("B1")


if __name__ == "__main__":
    main()