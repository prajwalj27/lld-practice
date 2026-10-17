# Amazon Locker (new grad LLD): discussion

Prompt: design a locker system like Amazon Locker, where delivery drivers deposit packages and customers pick them up with a code.

## Clarifying questions

Spend 3 to 5 minutes here. Cover four areas: the core operations, what can go wrong, where the scope ends, and what might be extended later. If you've never used an Amazon Locker, say so and ask for a quick explanation. That's a perfectly good opening.

1. **How does it work, at a high level?**
   Interviewer: It's a self-serve pickup point. The customer picks a locker location when ordering. Once the package is deposited, they get a code that opens the compartment.

2. **Are there different compartment sizes? Can a small package go in a large compartment if the small ones are full?**
   Interviewer: Small, medium, and large. Match the size exactly for now, and reject the deposit if there's no free compartment of that size.

3. **What's in scope: the whole delivery, or just the locker?**
   Interviewer: Just the locker. Assume the package is already there. Routing and driver assignment are out.

4. **How does the customer receive the code?**
   Interviewer: Just return it. Sending it by SMS or email is another system's job.

5. **What if someone enters a wrong code many times? Should we lock them out?**
   Interviewer: Keep it simple. Validate the code and return an error if it's wrong. No lockout.

6. **Can one customer have several packages? Is there one code per package?**
   Interviewer: One code per package. A customer with several packages gets several codes and compartments.

7. **How long do codes last, and what if a package is never picked up?**
   Interviewer: Codes expire after 7 days, and expired codes are rejected. The package stays in the compartment until staff removes it and sends it back.

8. **What if every compartment of the needed size is full?**
   Interviewer: Return an error. The driver tries another location or comes back later. No queueing or reservations.

## Requirements

```
requirements
1. driver deposits a package by giving its size (small, medium, large)
    - system picks a free compartment of exactly that size and opens it
    - returns an access code, or an error if there's no space
2. one access code per package, generated on a successful deposit
3. customer picks up by entering the code
    - system validates it and opens the compartment
    - specific error if the code is invalid or expired
4. codes expire after 7 days
    - expired codes are rejected at pickup
    - the package stays in the compartment until staff removes it
5. staff can open every compartment with an expired code, to remove the packages
6. clear errors for: wrong code, already-used code, expired code

out of scope
- delivery logistics (how the package reaches the locker)
- sending the code to the customer (SMS / email)
- lockout after failed attempts
- ui
- multiple locker locations
- payment
```

It's worth calling out features you considered and chose not to build, like lockout and notifications. It shows you're thinking ahead without over-building.

## Entities

Look for the nouns, then ask whether each one actually earns a class. Some nouns are just a field or a parameter.

- **Package: not an entity.** Another system already tracks packages (IDs, shipping, the customer). The locker only cares about the package's size, so `size` is just a parameter to `deposit_package`.
- **Compartment: an entity.** A physical slot with an id, a size, and whether a package is inside.
- **Locker: an entity, the orchestrator.** It finds a free compartment, creates the code, and ties everything together. It's the system's entry point.
- **AccessToken: an entity.** It looks like it could be a string field, but it's really a permission with an expiry date: the right to open one specific compartment until a certain time. As its own class, it owns the expiry logic and the link to its compartment.
- **Size: an enum** of SMALL, MEDIUM, LARGE.

| Entity | Job |
|---|---|
| **Locker** | The orchestrator. Owns all compartments and the code → token map. Handles deposit, pickup, and opening expired compartments. |
| **AccessToken** | A code, its expiry time, and the compartment it opens. Decides whether it has expired. |
| **Compartment** | A physical slot: id, size, and whether a package is inside. |

Don't worry if your first entity list isn't right. If a class ends up with no real behavior, or something feels awkwardly indirect, go back and adjust. Revising the design is expected.
