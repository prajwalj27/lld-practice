# Parking Lot (new grad LLD): discussion

Prompt: design a parking lot system where different vehicle types can park. The system assigns spots and charges a fee on exit.

## Clarifying questions

Cover what the system does, how it handles mistakes, what's in scope, and what might change later.

1. **Does the system pick the spot when a vehicle enters?**
   Interviewer: Yes. It assigns a free spot that matches the vehicle type and issues a ticket. Real lots usually let you choose, but the assigned version is the standard interview form because it makes you design the allocation logic.

2. **Which vehicle types?**
   Interviewer: Three: motorcycles, cars, and large vehicles like SUVs or vans.

3. **What does the driver get on entry?**
   Interviewer: A ticket with a unique ID. They need it to leave.

4. **How does pricing work?**
   Interviewer: Keep it simple. One hourly rate for every vehicle, rounded up to the next hour, paid on exit. "Keep it simple" is your signal not to build surge pricing or discounts.

5. **What if the lot is full, or the ticket is bad?**
   Interviewer: Reject entry if no matching spot is free. Reject exit if the ticket is invalid or already used.

6. **What if someone loses their ticket?**
   Interviewer: Assume nobody does, for now. Asking "what can go wrong?" questions like this is a good signal, but don't list twenty of them.

7. **What's out of scope?**
   Interviewer: Payment processing, gates, cameras, and UI. Focus on spot assignment, tickets, and fees.

## Requirements

```
requirements
1. three vehicle types: motorcycle, car, large
2. on entry, the system assigns a free compatible spot
3. the system issues a ticket at entry
4. on exit, the driver gives the ticket ID
    - system validates the ticket
    - fee = time parked, hourly, rounded up
    - the spot is freed
5. one hourly rate for all vehicles
6. reject entry if no compatible spot is free
7. reject exit if the ticket is invalid or already used

out of scope
- payment processing
- gate hardware, cameras, monitoring
- ui / displays
- reservations
- lost tickets
```

## Entities

Look for nouns, but don't make every noun a class. Some are just data.

- **Vehicle: not a class, just an enum.** The vehicle is outside our system: we don't track it or its state. All we need is its type, to match it with a spot. That's one piece of classification data, so `VehicleType` is an enum.
- **ParkingSpot: an entity.** It has an ID and a type. It holds only what's permanently true of the spot.
- **Ticket: an entity, even though it only holds data.** Unlike a vehicle, a ticket is something our system creates and manages: a record of one parking session (ID, spot, vehicle type, entry time).
- **ParkingLot: the orchestrator.** It finds a spot, issues the ticket, and marks the spot taken on entry. On exit, it validates the ticket, computes the fee, and frees the spot. It's the system's only public API.

| Entity | Job |
|---|---|
| **ParkingLot** | Owns the spots, tracks active tickets and which spots are taken, assigns spots on entry, validates tickets and charges on exit. |
| **ParkingSpot** | One space: an ID and a spot type. Knows nothing about tickets, pricing, or whether it's occupied. |
| **Ticket** | A read-only record of a session: ticket ID, spot ID, vehicle type, entry time. No business logic. |
| **VehicleType, SpotType** | Enums for MOTORCYCLE / CAR / LARGE. |

**Relationships:** ParkingLot owns many ParkingSpots, creates a Ticket on each entry, and keeps active tickets so it can validate them on exit.
