"""Serveur MCP /api/mcp : auth bearer + tools du noyau V1."""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.models.models import Event, Saison, Slot
from app.services import oauth_store


@pytest.fixture()
def mcp_client(db_session, monkeypatch):
    import app.mcp.context as mcp_context
    from app.core.deps import get_db
    from app.main import app

    @contextmanager
    def shared_session():
        yield db_session

    monkeypatch.setattr(mcp_context, "open_session", shared_session)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, follow_redirects=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def bureau_token(db_session, bureau_member):
    client = oauth_store.register_client(db_session, "Test", ["http://localhost:1/cb"])
    return oauth_store.issue_tokens(db_session, client.client_id, bureau_member.id).access_token


def rpc(client, token, method, params=None, path="/api/mcp"):
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(
        path,
        headers=headers,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
    )


def call_tool(client, token, name, arguments):
    r = rpc(client, token, "tools/call", {"name": name, "arguments": arguments})
    assert r.status_code == 200, r.text
    return r.json()["result"]


def tool_data(result):
    assert not result.get("isError"), result
    if "structuredContent" in result:
        data = result["structuredContent"]
        return data.get("result", data) if set(data) == {"result"} else data
    return json.loads(result["content"][0]["text"])


def test_mcp_no_token(mcp_client):
    r = rpc(mcp_client, None, "tools/list")
    assert r.status_code == 401
    assert (
        'resource_metadata="http://localhost:3000/.well-known/oauth-protected-resource/api/mcp"'
        in r.headers["www-authenticate"]
    )


def test_mcp_web_jwt_rejected(mcp_client, bureau_member):
    r = rpc(mcp_client, create_access_token(bureau_member.id), "tools/list")
    assert r.status_code == 401


def test_mcp_demoted_member(mcp_client, bureau_token, bureau_member, db_session):
    bureau_member.roles = ["staff"]
    db_session.flush()
    r = rpc(mcp_client, bureau_token, "tools/list")
    assert r.status_code == 403


def test_mcp_no_trailing_slash(mcp_client, bureau_token):
    r = rpc(mcp_client, bureau_token, "tools/list")
    assert r.status_code == 200, r.text
    names = {t["name"] for t in r.json()["result"]["tools"]}
    assert names == {"create_event", "list_events", "get_event", "list_saisons"}


def test_tool_create_event_afterwork(mcp_client, bureau_token, db_session):
    data = tool_data(
        call_tool(
            mcp_client,
            bureau_token,
            "create_event",
            {
                "nom": "Afterwork test",
                "type": "afterwork",
                "date": "2026-11-05",
                "heure_debut": "18:00",
                "heure_fin": "20:00",
            },
        )
    )
    event = db_session.get(Event, data["event"]["id"])
    assert event.nom == "Afterwork test"
    assert event.statut.value == "brouillon"
    assert event.date == datetime(2026, 11, 5, 18)
    assert event.inscriptions_ouvertes is False
    slots = (
        db_session.query(Slot)
        .filter(Slot.evenement_id == event.id)
        .order_by(Slot.heure_debut)
        .all()
    )
    assert [(s.heure_debut.hour, s.heure_fin.hour) for s in slots] == [(18, 19), (19, 20)]
    assert [s.heure_relative for s in slots] == [0, 1]
    assert {s.max_personnes for s in slots} == {3}
    assert data["url"] == f"http://localhost:3000/events/{event.id}"


def test_tool_create_event_invalid_input(mcp_client, bureau_token):
    result = call_tool(
        mcp_client,
        bureau_token,
        "create_event",
        {
            "nom": "X",
            "type": "brunch",
            "date": "2026-11-05",
            "heure_debut": "18:00",
            "heure_fin": "20:00",
        },
    )
    assert result["isError"] is True


def test_tool_list_and_get_event(mcp_client, bureau_token):
    created = tool_data(
        call_tool(
            mcp_client,
            bureau_token,
            "create_event",
            {
                "nom": "AW liste",
                "type": "afterwork",
                "date": "2026-11-05",
                "heure_debut": "18:00",
                "heure_fin": "20:00",
            },
        )
    )
    event_id = created["event"]["id"]

    events = tool_data(call_tool(mcp_client, bureau_token, "list_events", {}))
    listed = next(e for e in events if e["id"] == event_id)
    assert listed["nb_creneaux"] == 2

    detail = tool_data(call_tool(mcp_client, bureau_token, "get_event", {"event_id": event_id}))
    assert len(detail["creneaux"]) == 2
    assert detail["inscriptions_ouvertes"] is False

    missing = call_tool(mcp_client, bureau_token, "get_event", {"event_id": 999999})
    assert missing["isError"] is True


def test_tool_list_saisons(mcp_client, bureau_token, db_session):
    db_session.add(Saison(nom="2026-2027", date_debut=date(2026, 9, 1), date_fin=None))
    db_session.flush()
    saisons = tool_data(call_tool(mcp_client, bureau_token, "list_saisons", {}))
    assert {"nom": "2026-2027", "date_debut": "2026-09-01", "date_fin": None} in [
        {k: s[k] for k in ("nom", "date_debut", "date_fin")} for s in saisons
    ]


def test_mcp_db_access_off_event_loop(db_session, bureau_token, monkeypatch):
    """Les accès base (middleware + tools) ne doivent pas bloquer la boucle async."""
    import asyncio

    import app.mcp.context as mcp_context
    from app.core.deps import get_db
    from app.main import app

    on_loop = []

    @contextmanager
    def recording_session():
        try:
            asyncio.get_running_loop()
            on_loop.append(True)
        except RuntimeError:
            on_loop.append(False)
        yield db_session

    monkeypatch.setattr(mcp_context, "open_session", recording_session)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as c:
            call_tool(c, bureau_token, "list_saisons", {})
    finally:
        app.dependency_overrides.clear()
    assert on_loop and not any(on_loop), on_loop


def test_mcp_modern_protocol_2026_07_28(mcp_client, bureau_token):
    """Révision 2026-07-28 (requête autonome, sans initialize) : tools/call doit marcher."""
    from mcp.types import LATEST_PROTOCOL_VERSION, PROTOCOL_VERSION_META_KEY

    assert LATEST_PROTOCOL_VERSION == "2026-07-28"
    r = mcp_client.post(
        "/api/mcp",
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bureau_token}",
            "MCP-Protocol-Version": LATEST_PROTOCOL_VERSION,
            "Mcp-Method": "tools/call",
            "Mcp-Name": "list_saisons",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "list_saisons",
                "arguments": {},
                "_meta": {
                    PROTOCOL_VERSION_META_KEY: LATEST_PROTOCOL_VERSION,
                    "io.modelcontextprotocol/clientCapabilities": {},
                },
            },
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["result"]["isError"] is False


def test_tool_call_logged_with_member(mcp_client, bureau_token, bureau_member, caplog):
    caplog.set_level(logging.INFO, logger="app.mcp")
    data = tool_data(
        call_tool(
            mcp_client,
            bureau_token,
            "create_event",
            {
                "nom": "Log",
                "type": "soiree",
                "date": "2026-11-06",
                "heure_debut": "22:00",
                "heure_fin": "23:00",
            },
        )
    )
    call_tool(mcp_client, bureau_token, "get_event", {"event_id": 999999})

    records = [r for r in caplog.records if r.name == "app.mcp"]
    ok, erreur = records[-2], records[-1]
    assert ok.tool == "create_event"
    assert ok.membre_id == bureau_member.id
    assert ok.statut == "ok"
    assert ok.event_id == data["event"]["id"]
    assert erreur.tool == "get_event"
    assert erreur.statut == "erreur_usage"
    assert erreur.membre_id == bureau_member.id
