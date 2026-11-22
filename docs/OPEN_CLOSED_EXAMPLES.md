# Open/Closed in Decerno

*Open for extension, closed for modification.* Each extension below means **adding** code or data; no existing
class has to change. Each one is backed by a test.

## 1. A new incident category: zero code

Categories are data (`categories` table: code, name, keywords). An administrator adds one in the admin screen
(`POST /api/admin/categories`):

```json
{ "code": "PRINTING", "name": "Printing", "keywords": ["toner", "print queue"] }
```

Immediately afterwards:

- the report form lists it (`GET /api/lookups/categories`);
- category suggestion proposes it for "Toner empty and the print queue is stuck" (keywords are read at run time);
- technicians can be given the `PRINTING` skill, and skill-based assignment then routes these incidents to them;
- search, dashboards and SLA handling work unchanged.

Tests: `test_new_category_is_suggested_immediately_without_code_changes`,
`test_admin_manages_services_categories_and_policies`.

## 2. A new assignment strategy: one new class

Strategies register themselves with a decorator (`AssignmentStrategyRegistry`, `domain/strategies/assignment.py`).
The template method `choose()` already filters out unavailable or full technicians; a new strategy only implements
`_pick()`:

```python
@AssignmentStrategyRegistry.register
class PriorityAwareStrategy(AssignmentStrategy):
    key = "PRIORITY"
    name = "Priority-based"
    description = "P1/P2 go to the most experienced skilled technician, others to the least loaded."

    def _pick(self, eligible, context):
        if context.priority in (Priority.P1, Priority.P2):
            best = max(eligible, key=lambda c: (c.technician.has_skill(context.category_code), c.experience))
            return best, f"critical incident -> most experienced ({best.experience} yrs)"
        best = min(eligible, key=lambda c: c.active_incidents)
        return best, f"routine incident -> lowest load ({best.active_incidents} active)"
```

It then appears automatically in `GET /api/admin/settings/assignment-strategy` and can be activated at run time
(`PUT … {"key": "PRIORITY"}`). `AssignmentService`, `IncidentService`, the API and the UI are untouched.
Test: `test_registry_rejects_unknown_strategy_and_accepts_new_ones_without_code_changes` registers a strategy inside
the test itself.

## 3. A new notification channel: one adapter + one registration

```python
class PushChannel(NotificationChannel):                       # Adapter over a push SDK
    def __init__(self, sdk: FakePushSdk) -> None:
        self._sdk = sdk

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.PUSH

    def can_reach(self, recipient: User) -> bool:
        return self._sdk.has_device(recipient.id)

    def deliver(self, notification: Notification, recipient: User) -> None:
        try:
            self._sdk.notify(user=recipient.id, title=notification.title, text=notification.body)
        except ConnectionError as exc:
            raise NotificationDeliveryError(f"Push failed: {exc}") from exc
```

Register it in `build_infrastructure()` (`ChannelRegistry([..., PushChannel(sdk)])`) and add `PUSH` to `ChannelType`.
To decide *when* it is used, either add it to `DefaultChannelSelectionPolicy` or supply a new `ChannelSelectionPolicy`
(Strategy) to `Infrastructure`. The `NotificationDispatcher` observer, the services and the domain do not change: the
dispatcher only knows the `NotificationChannel` interface.

## 4. A new observer: one class + one `attach`

Anything that should react to incident events (e.g. a Slack webhook) implements `EventObserver`
(`interests()` + `handle()`), and is attached in `build_event_bus()` or passed through `Infrastructure.extra_observers`.
That is how the SSE `RealtimeForwarder` was added in Phase 2 without touching `Incident` or `IncidentService`.

## 5. A new lifecycle state: one State subclass

For example, an `ON_HOLD` state: add the enum value, write `class OnHoldState(IncidentState)` overriding only its legal
transitions, and add it to the state map. All other states keep raising `InvalidStateTransitionError` for anything they
don't override.

## 6. A different priority algorithm: one `PriorityCalculator`

Implement `calculate(PriorityInput) -> PriorityResult` (e.g. history-based) and pass it as
`Infrastructure.priority_calculator`. `IncidentService` depends only on the abstraction.
