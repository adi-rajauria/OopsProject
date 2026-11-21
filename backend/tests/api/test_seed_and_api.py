"""Seed script + HTTP API on top of the seeded data (SQLite by default, PostgreSQL via ITSM_TEST_DATABASE_URL)."""

import csv
import io

import pytest

from app.domain.enums import IncidentStatus
from scripts.seed import DEMO_PASSWORD, Seeder, has_data, reset_database
from tests.conftest import START


@pytest.fixture
def seeded(session_factory):
    return Seeder(session_factory, now=START).run()


@pytest.fixture
def api(client, seeded):
    def login(local: str) -> dict:
        response = client.post("/api/auth/login", json={"email": f"{local}@itsm.demo", "password": DEMO_PASSWORD})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return client, login


def test_seed_meets_the_data_requirements(seeded, session_factory):
    assert seeded.users >= 15 and seeded.services >= 8 and seeded.incidents >= 40
    assert set(seeded.by_status) == {s.value for s in IncidentStatus} - {IncidentStatus.NEW.value}
    assert seeded.violations > 0 and seeded.links > 0 and seeded.escalated > 0
    assert has_data(session_factory)
    reset_database(session_factory.kw["bind"])
    assert not has_data(session_factory)


def test_employee_to_technician_flow_over_http(api):
    client, login = api
    riya = login("riya")
    services = {s["code"]: s["id"] for s in client.get("/api/lookups/services", headers=riya).json()}
    created = client.post(
        "/api/incidents",
        headers=riya,
        json={
            "title": "Laptop screen flickers",
            "description": "My laptop screen flickers and the battery drains fast.",
            "service_id": services["ENDPT"],
            "impact": 1,
            "urgency": 2,
        },
    )
    assert created.status_code == 201, created.text
    incident = created.json()
    assert incident["category"]["code"] == "HARDWARE" and incident["status"] == "ASSIGNED"
    technician = {"Meera Iyer": "meera", "Tom D'Souza": "tom"}[incident["technician"]["name"]]
    tech = login(technician)
    iid = incident["id"]
    assert client.post(f"/api/incidents/{iid}/acknowledge", headers=riya).status_code == 403
    assert client.post(f"/api/incidents/{iid}/acknowledge", headers=tech).json()["status"] == "ACKNOWLEDGED"
    assert client.post(f"/api/incidents/{iid}/start", headers=tech).status_code == 200
    resolved = client.post(
        f"/api/incidents/{iid}/resolve", headers=tech, json={"summary": "Replaced the display cable and the battery."}
    ).json()
    assert (
        resolved["status"] == "RESOLVED"
        and "verify" in client.get(f"/api/incidents/{iid}", headers=riya).json()["available_actions"]
    )
    verified = client.post(f"/api/incidents/{iid}/verify", headers=riya, json={"rating": 5}).json()
    assert verified["feedback"]["rating"] == 5
    trail = [a["action"] for a in client.get(f"/api/incidents/{iid}/audit", headers=riya).json()]
    assert trail[:3] == ["CREATED", "CLASSIFIED", "PRIORITY_CALCULATED"] and trail[-2:] == ["VERIFY", "FEEDBACK"]
    assert client.get("/api/notifications/unread-count", headers=riya).json()["count"] > 0


@pytest.mark.parametrize(
    ("user", "path", "expected"),
    [
        ("riya", "/api/admin/users", 403),
        ("riya", "/api/reports/overview", 403),
        ("riya", "/api/intelligence/sla-risk", 403),
        ("riya", "/api/intelligence/recurring", 403),
        ("riya", "/api/technicians/me/queue", 403),
        ("kabir", "/api/admin/services", 403),
        ("kabir", "/api/reports/overview", 403),
        ("kabir", "/api/technicians/workload", 200),
        ("kabir", "/api/intelligence/correlation", 200),
        ("admin", "/api/reports/overview", 200),
        ("admin", "/api/admin/audit-logs", 200),
    ],
)
def test_role_guards(api, user, path, expected):
    client, login = api
    assert client.get(path, headers=login(user)).status_code == expected


def test_search_parameters_and_validation(api):
    client, login = api
    admin, riya = login("admin"), login("riya")
    p1 = client.get(
        "/api/incidents", headers=admin, params={"priority": "P1", "status": ["ASSIGNED", "CLASSIFIED"]}
    ).json()
    assert p1["total"] > 0 and all(i["priority"] == "P1" for i in p1["items"])
    by_number = client.get("/api/incidents", headers=admin, params={"number": "INC1001"}).json()
    assert [i["number"] for i in by_number["items"]] == ["INC1001"]
    own = client.get("/api/incidents", headers=riya, params={"page_size": 100}).json()["items"]
    assert own and all(i["reporter"]["name"] == "Riya Kapoor" for i in own)
    assert client.get("/api/incidents", headers=admin, params={"number": "ABC"}).status_code == 422
    assert client.get("/api/incidents", headers=admin, params={"page_size": 101}).status_code == 422
    assert client.get("/api/incidents", headers=admin, params={"status": "DONE"}).status_code == 422


def test_report_errors_map_to_http_codes(api):
    client, login = api
    riya = login("riya")
    services = {s["code"]: s["id"] for s in client.get("/api/lookups/services", headers=riya).json()}
    categories = {c["code"]: c["id"] for c in client.get("/api/lookups/categories", headers=riya).json()}
    body = {
        "title": "Payroll export broken",
        "description": "The payroll export to the bank fails every time.",
        "service_id": services["HR"],
        "impact": 2,
        "urgency": 2,
        "category_id": categories["APPLICATION"],
    }
    no_category = client.post("/api/incidents", headers=riya, json={**body, "category_id": None})
    assert no_category.status_code == 422 and no_category.json()["error"]["code"] == "INVALID_INCIDENT"
    assert client.post("/api/incidents", headers=riya, json={**body, "impact": 5}).status_code == 422
    missing = client.post("/api/incidents", headers=riya, json={**body, "service_id": 999})
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "SERVICE_NOT_FOUND"
    assert client.post("/api/incidents", headers=riya, json=body).status_code == 201
    duplicate = client.post("/api/incidents", headers=riya, json=body)
    assert duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "DUPLICATE_INCIDENT"
    assert duplicate.json()["error"]["details"]["matches"][0]["similarity"] >= 0.85
    assert client.post("/api/incidents", headers=riya, json={**body, "force": True}).status_code == 201


def test_dashboards_intelligence_and_admin_over_http(api):
    client, login = api
    admin = login("admin")
    overview = client.get("/api/reports/overview", headers=admin).json()
    assert overview["total"] >= 40 and overview["sla_violations"] > 0
    assert {s["code"] for s in client.get("/api/reports/services", headers=admin).json()} >= {"PAY", "NET"}
    assert client.get("/api/reports/sla", headers=admin).json()["violations"]
    assert len(client.get("/api/reports/trends", headers=admin, params={"days": 7}).json()) == 7
    correlation = client.get("/api/intelligence/correlation", headers=admin).json()
    assert any(f["kind"] == "HOTSPOT" and f["root_service"] == "Payments Platform" for f in correlation["findings"])
    recurring = client.get("/api/intelligence/recurring", headers=admin).json()
    assert [(p["service"], p["occurrences"]) for p in recurring] == [("Corporate VPN", 3)]  # seeded VPN drop-outs
    assert client.get("/api/intelligence/sla-risk", headers=admin).json()
    strategies = client.put(
        "/api/admin/settings/assignment-strategy", headers=admin, json={"key": "ROUND_ROBIN"}
    ).json()
    assert [s["key"] for s in strategies if s["active"]] == ["ROUND_ROBIN"]
    policies = client.get("/api/admin/sla-policies", headers=admin).json()
    default = next(p for p in policies if p["service_id"] is None)
    assert client.delete(f"/api/admin/sla-policies/{default['id']}", headers=admin).status_code == 422
    assert client.post("/api/admin/sla/check-now", headers=admin).status_code == 200
    created = client.post(
        "/api/admin/users",
        headers=admin,
        json={
            "role": "TECHNICIAN",
            "email": "newtech@itsm.demo",
            "full_name": "New Tech",
            "password": "Secret123",
            "technician": {"skills": ["NETWORK"], "experience_years": 1},
        },
    )
    assert created.status_code == 201 and created.json()["technician_profile"]["skills"] == ["NETWORK"]


def test_self_help_and_resolution_estimate_over_http(api):
    client, login = api
    riya, admin = login("riya"), login("admin")
    text = {"title": "VPN keeps disconnecting", "description": "Remote staff lose the VPN connection"}
    tips = client.post("/api/intelligence/self-help", headers=riya, json=text).json()
    assert tips and tips[0]["resolution"] and "incident_id" not in tips[0]  # employees never see others' ids
    assert client.post("/api/intelligence/self-help", headers=riya, json={"title": ""}).status_code == 422
    hint = client.post("/api/intelligence/suggest-severity", headers=riya, json={"title": "All users cannot pay"}).json()
    assert (hint["impact"], hint["urgency"]) == (4, 4) and hint["urgency_reason"] == 'mentions "cannot pay"'

    own = client.get("/api/incidents", headers=riya, params={"page_size": 100}).json()["items"]
    mine = own[0]["id"]
    assert client.get(f"/api/incidents/{mine}/resolution-estimate", headers=riya).status_code == 200
    others = client.get("/api/incidents", headers=admin, params={"page_size": 100}).json()["items"]
    foreign = next(i["id"] for i in others if i["reporter"]["name"] != "Riya Kapoor")
    assert client.get(f"/api/incidents/{foreign}/resolution-estimate", headers=riya).status_code == 403
    estimates = [client.get(f"/api/incidents/{i['id']}/resolution-estimate", headers=admin).json() for i in others]
    assert any(e and e["sample_size"] >= 3 and "median of" in e["reason"] for e in estimates)


def test_csv_exports_respect_filters_visibility_and_block_formula_injection(api):
    client, login = api
    admin, riya = login("admin"), login("riya")
    services = {s["code"]: s["id"] for s in client.get("/api/lookups/services", headers=riya).json()}
    categories = {c["code"]: c["id"] for c in client.get("/api/lookups/categories", headers=riya).json()}
    created = client.post("/api/incidents", headers=riya, json={
        "title": "=HYPERLINK(\"http://evil.test\",\"click\")", "description": "Formula in the title of this report.",
        "service_id": services["WIKI"], "impact": 1, "urgency": 1, "category_id": categories["APPLICATION"],
    })
    assert created.status_code == 201

    def rows(headers: dict, **params) -> list[list[str]]:
        response = client.get("/api/incidents/export.csv", headers=headers, params=params)
        assert response.status_code == 200 and response.headers["content-type"].startswith("text/csv")
        assert "attachment" in response.headers["content-disposition"]
        return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))

    everything = rows(admin)
    total = client.get("/api/incidents", headers=admin).json()["total"]
    assert everything[0][:3] == ["Number", "Title", "Status"] and len(everything) == total + 1  # all pages, not 20
    assert all(r[3] == "P1" for r in rows(admin, priority="P1")[1:])
    own = rows(riya)[1:]
    assert own and all(r[7] == "Riya Kapoor" for r in own)  # employees only export their own incidents
    assert any(r[1] == "'=HYPERLINK(\"http://evil.test\",\"click\")" for r in own)  # neutralised for Excel

    violations = client.get("/api/reports/sla/violations.csv", headers=admin)
    assert violations.status_code == 200
    violation_rows = list(csv.reader(io.StringIO(violations.content.decode("utf-8-sig"))))
    assert len(violation_rows) > 1 and violation_rows[1][7].endswith(" UTC")  # same readable timestamps
    assert client.get("/api/reports/sla/violations.csv", headers=riya).status_code == 403


def test_event_stream_rejects_bad_tokens(api):
    client, _ = api
    assert client.get("/api/stream/events", params={"token": "not-a-real-token"}).status_code == 401


def test_background_monitor_pass_detects_new_breaches_and_escalations(seeded, session_factory, settings, clock):
    from app.main import build_infrastructure
    from app.workers.sla_monitor import SLAMonitor

    monitor = SLAMonitor(session_factory, build_infrastructure(settings, clock), interval_seconds=60)
    assert monitor.run_once().escalations == 0  # nothing new at the seeding instant
    clock.advance(minutes=30)
    summary = monitor.run_once()
    assert summary.violations > 0 and summary.escalations > 0
