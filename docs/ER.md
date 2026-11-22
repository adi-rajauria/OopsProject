# Database design (PostgreSQL 18)

Schema source: `backend/app/repositories/orm.py`; migrations: `backend/alembic/versions/`.
Only portable column types are used (JSON, timestamptz, …), so the same schema runs on SQLite for tests.

```mermaid
erDiagram
    users ||--o| technician_profiles : "has (technicians only)"
    users ||--o{ incidents : reports
    users ||--o{ incidents : "is assigned"
    services ||--o{ incidents : affects
    categories ||--o{ incidents : classifies
    services ||--o{ service_dependencies : "depends on"
    services ||--o{ sla_policies : "may override"
    sla_policies ||--o{ incidents : "applied (snapshot)"
    incidents ||--o{ incident_comments : contains
    incidents ||--o{ incident_links : "similar to"
    incidents ||--o{ audit_records : "history of"
    incidents ||--o{ sla_violations : records
    incidents ||--o| feedback : "rated by reporter"
    incidents ||--o{ notifications : about
    users ||--o{ notifications : receives
    users ||--o{ audit_records : performed

    users {
        int id PK
        string email UK
        string full_name
        string password_hash "argon2id"
        string role "EMPLOYEE|TECHNICIAN|ADMINISTRATOR"
        string admin_level "SYSTEM_ADMIN|IT_MANAGER"
        string phone
        string department
        bool is_active
        timestamptz created_at
    }
    technician_profiles {
        int user_id PK,FK
        json skills "category codes"
        int experience_years
        int max_workload
        bool is_available
        bool is_team_lead
        string team
    }
    services {
        int id PK
        string code UK
        string name
        int business_criticality "1-4"
        string owner_team
        bool is_active
    }
    service_dependencies {
        int service_id PK,FK
        int depends_on_service_id PK,FK
    }
    categories {
        int id PK
        string code UK
        string name
        json keywords
        bool is_active
    }
    sla_policies {
        int id PK
        string priority "P1-P4"
        int service_id FK "null = default"
        int response_minutes
        int resolution_minutes
        int warning_threshold_pct
    }
    incidents {
        int id PK "number = DCN- + 1000 + id"
        string title
        text description
        int reporter_id FK
        int service_id FK
        int category_id FK
        int suggested_category_id FK
        int impact
        int urgency
        int affected_users
        string priority
        float priority_score
        string status
        int assigned_technician_id FK
        int sla_policy_id FK
        int sla_response_minutes "snapshot"
        int sla_resolution_minutes "snapshot"
        timestamptz response_due_at
        timestamptz resolution_due_at
        bool response_breached
        bool resolution_breached
        int sla_paused_seconds
        timestamptz sla_paused_at
        string sla_status "denormalised for filtering"
        int escalation_level
        int parent_incident_id FK
        timestamptz created_at
    }
    incident_comments {
        int id PK
        int incident_id FK
        int author_id FK
        string kind "NOTE|COMMENT|INFO_REQUEST|INFO_REPLY|RESOLUTION"
        text body
        bool is_internal
    }
    incident_links {
        int incident_id PK,FK
        int related_incident_id PK,FK
        float similarity
        string link_type "DUPLICATE|RELATED"
    }
    audit_records {
        int id PK
        int incident_id FK "null = system/admin event"
        int actor_id FK "null = SYSTEM"
        string actor_name
        string action
        string previous_state
        string new_state
        text description
        timestamptz created_at
    }
    sla_violations {
        int id PK
        int incident_id FK
        string target "RESPONSE|RESOLUTION"
        timestamptz due_at
        timestamptz detected_at
        int overdue_minutes
    }
    notifications {
        int id PK
        int recipient_id FK
        int incident_id FK
        string channel "IN_APP|EMAIL|SMS"
        string event_type
        string title
        bool is_read
        bool delivered
        string delivery_error
    }
    feedback {
        int id PK
        int incident_id FK,UK
        int employee_id FK
        int rating "1-5"
        text comment
    }
    system_settings {
        string key PK
        text value
    }
```

## Important constraints and indexes

| Rule | Enforced by |
|---|---|
| One account per email | `users.email` unique |
| One SLA policy per (priority, service) | `uq_sla_priority_service` |
| Each SLA target violated at most once per incident | `uq_violation_incident_target` + `SLATracker` check |
| One feedback per incident | `feedback.incident_id` unique |
| Service dependency graph is acyclic | `AdminService._reject_cycles` (depth-first search) |
| Fast queue/search/dashboards | indexes on `(status, priority)`, `(service_id, created_at)`, `sla_status`, `assigned_technician_id`, `reporter_id`, `created_at`; notifications `(recipient_id, is_read)` |

## Design notes

- **Domain model ≠ table model.** Mappers in `repositories/mappers.py` translate between them, so the domain stays
  framework-free.
- **SLA clock stored inline** in `incidents` (composition: it has no identity of its own). Policy targets are
  snapshotted, so editing a policy never silently moves existing deadlines.
- **Users: single table + optional profile** for the Employee / Technician / Administrator inheritance. Technician-only
  data lives in `technician_profiles` (1:0..1).
- **Audit is append-only**: rows are only inserted (by the `AuditLogger` observer), never updated.

## Sample data

`python -m scripts.seed --reset` creates 18 users, 11 services with dependencies, 9 categories, 7 SLA policies
(4 defaults + 3 service overrides) and 43 incidents in every lifecycle state (except the transient NEW). The data
includes SLA violations, near-duplicate links, escalations, feedback and a deliberately unassigned incident, all generated
by replaying history through the real services. See `docs/SETUP.md` for the credentials.
