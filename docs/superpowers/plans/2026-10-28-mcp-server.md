# Serveur MCP du planning — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exposer un serveur MCP sur `/api/mcp` dans le backend FastAPI, protégé par un serveur d'autorisation OAuth 2.1 maison adossé au login Google, avec 4 tools (`create_event`, `list_events`, `get_event`, `list_saisons`) réservés au bureau.

**Architecture:** Un service `oauth_store` (clients DCR, codes, tokens opaques hashés) est piloté par un router `oauth.py` (metadata, register, authorize + consentement, token, revoke). Le serveur MCP (SDK officiel `mcp`, streamable HTTP, stateless, réponses JSON) est enveloppé dans un middleware ASGI qui valide le bearer, revérifie le rôle bureau et pose le membre dans un contextvar. La création event + créneaux est extraite de `routers/events.py` dans un service partagé avec le tool MCP.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16, SDK Python `mcp`, itsdangerous, authlib (existant), pytest + TestClient.

**Spec:** `docs/superpowers/specs/2026-10-28-mcp-server-design.md`. Lire la spec avant chaque tâche : ce plan fixe les noms et les tests, la spec garde les raisons.

## Global Constraints

- Vocabulaire métier français dans le code (`creneau`, `membre_id`, `heure_relative`…), datetimes **naïfs**.
- Horloge OAuth : `datetime.utcnow()` naïf, passé par un helper `_now()` dans `oauth_store` (pour les tests).
- PKCE `S256` **obligatoire**, `plain` refusé.
- Clients publics uniquement : `token_endpoint_auth_method = "none"`.
- Access token MCP **60 min**, refresh **30 jours**, code **5 min, usage unique**.
- Tokens et codes opaques (`secrets.token_urlsafe(32)`), stockés en **SHA-256 hex**, jamais en clair.
- Ressource MCP : `{PUBLIC_BASE_URL}/api/mcp`. Issuer : `{PUBLIC_BASE_URL}`.
- Allowlist redirect URIs par défaut : loopback `http://localhost:*`, `http://127.0.0.1:*`, `http://[::1]:*` (port et chemin libres) ; `https://claude.ai/api/mcp/auth_callback` ; `https://claude.com/api/mcp/auth_callback` ; `https://vscode.dev/redirect`. Surchargeable par `MCP_ALLOWED_REDIRECT_URIS`.
- Le rôle `bureau` est revérifié **à chaque** requête MCP.
- Un JWT web n'est jamais accepté sur `/api/mcp`, un token MCP jamais par `get_current_member`.
- Migration : `backend/alembic/versions/011_oauth_mcp.py` (010 est la dernière existante).
- Heures saisies via MCP = Europe/Paris.

**Commande de test** (stack docker démarrée), notée `TEST` ci-dessous :

```bash
docker compose run --rm --no-deps \
  -v ./backend/tests:/app/tests -v ./backend/app:/app/app \
  -v ./backend/requirements-dev.txt:/app/requirements-dev.txt \
  -e TEST_DATABASE_URL=postgresql://baruser:barpassword@postgres:5432/salope_test \
  backend bash -c "pip install -q -r requirements-dev.txt && pytest tests -v <ARGS>"
```

Après une modification de `requirements.txt` : `docker compose build backend` avant `TEST`.

Travailler sur une branche `feat/mcp-server` (créée en Task 1).

## Review Focus

1. **`redirect_uri` loopback avec un port différent de celui enregistré** (Claude Code ouvre un port aléatoire à chaque login) → doit être accepté si host et chemin matchent ; un host différent (`http://evil.com:1234`) jamais. Test en Task 2.
2. **Event « 22h-02h »** (soirée qui passe minuit) → 4 créneaux, les deux derniers datés du lendemain, `heure_relative` 0..3. Test en Task 5.
3. **Requête `/api/mcp` sans slash final** → doit répondre directement (pas de 307 vers `/api/mcp/`, les clients MCP ne suivent pas toujours). Test en Task 6.
4. **Plusieurs `TestClient(app)` successifs dans la suite** → le session manager MCP ne doit pas planter avec « run() can only be called once » (lifespan rejoué à chaque test). Couvert par le simple fait que la suite entière passe en Task 6.
5. **Refresh token rejoué** (client qui crashe et réutilise l'ancien) → `invalid_grant` + révocation de toute la famille, y compris le nouvel access token. Test en Task 2.

---

### Task 1: Dépendances, configuration, modèles et migration

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/config.py`
- Modify: `backend/app/models/models.py` (ajout en fin de fichier)
- Create: `backend/alembic/versions/011_oauth_mcp.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_oauth_models.py`

**Interfaces:**
- Produces:
  - `settings.PUBLIC_BASE_URL: str = "http://localhost:3000"`, `settings.MCP_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60`, `settings.MCP_REFRESH_TOKEN_EXPIRE_DAYS: int = 30`, `settings.MCP_ALLOWED_REDIRECT_URIS: str` (défaut = allowlist des Global Constraints, séparée par des virgules, `*` comme port loopback, ex. `http://localhost:*`).
  - Modèles `OAuthClient` (`oauth_clients` : `client_id` String PK, `client_name` String nullable, `redirect_uris` ARRAY(String) non null, `created_at` DateTime), `OAuthAuthorizationCode` (`oauth_authorization_codes` : `id` PK, `code_hash` String unique indexé, `client_id` FK→oauth_clients CASCADE, `membre_id` FK→members CASCADE, `redirect_uri`, `code_challenge`, `resource` nullable, `expires_at`, `used_at` nullable), `OAuthToken` (`oauth_tokens` : `id` PK, `token_hash` unique indexé, `type` String (`access`/`refresh`), `client_id` FK CASCADE, `membre_id` FK CASCADE, `family_id` String indexé, `expires_at`, `revoked_at` nullable, `created_at`).

- [ ] **Step 1: Créer la branche**

```bash
git checkout -b feat/mcp-server
```

- [ ] **Step 2: Ajouter `mcp` à `requirements.txt`**, pinner une version publiée depuis au moins 2 semaines. Monter `pydantic`, `pydantic-settings`, `fastapi`, `uvicorn` si le résolveur l'exige. Run : `docker compose build backend`. Expected : build OK, sans conflit de résolution.

- [ ] **Step 3: Vérifier la non-régression des versions**

Run : `TEST` (suite complète)
Expected : tous les tests existants PASS.

- [ ] **Step 4: Écrire le test qui échoue** `tests/test_oauth_models.py::test_oauth_tables_roundtrip` : crée un `OAuthClient(client_id="c1", redirect_uris=["http://localhost:1/cb"])`, un `OAuthToken` lié à `bureau_member`, flush, relit ; puis supprime le client et vérifie que le token disparaît (cascade).

- [ ] **Step 5: Run** `TEST` avec `-k test_oauth_tables_roundtrip` → FAIL (ImportError).

- [ ] **Step 6: Ajouter les 3 modèles et les settings**, plus la migration `011_oauth_mcp.py` (`down_revision` = révision de `010_logo_couleurs.py`, `downgrade` qui drop les 3 tables). Ajouter les nouvelles variables commentées dans `.env.example`.

- [ ] **Step 7: Run** le test → PASS. Run : `docker compose run --rm migrations` → la migration s'applique sans erreur.

- [ ] **Step 8: Commit**

```bash
git add backend/requirements.txt backend/app/config.py backend/app/models/models.py backend/alembic/versions/011_oauth_mcp.py backend/.env.example backend/tests/test_oauth_models.py
git commit -m "feat(mcp): modèles OAuth, migration 011 et dépendance mcp"
```

---

### Task 2: Service `oauth_store`

**Files:**
- Create: `backend/app/services/oauth_store.py`
- Test: `backend/tests/test_oauth_store.py`

**Interfaces:**
- Consumes : modèles et settings de la Task 1.
- Produces (tous dans `app.services.oauth_store`) :
  - `class OAuthError(Exception)` avec `.error: str` (code OAuth : `invalid_redirect_uri`, `invalid_client`, `invalid_grant`, `invalid_request`) et `.description: str | None`.
  - `@dataclass TokenPair(access_token: str, refresh_token: str, expires_in: int)`
  - `hash_secret(raw: str) -> str`
  - `redirect_uri_allowed(uri: str) -> bool` (contre l'allowlist settings)
  - `redirect_uri_matches(registered: list[str], requested: str) -> bool` (exact ; pour le loopback, le port est ignoré mais scheme, host et path doivent être égaux)
  - `register_client(db, client_name: str | None, redirect_uris: list[str]) -> OAuthClient`, lève `OAuthError("invalid_redirect_uri")` si la liste est vide ou si une URI est hors allowlist
  - `get_client(db, client_id: str) -> OAuthClient | None`
  - `issue_code(db, client: OAuthClient, membre_id: int, redirect_uri: str, code_challenge: str, resource: str | None) -> str` (code brut)
  - `exchange_code(db, client_id: str, code: str, redirect_uri: str, code_verifier: str) -> TokenPair`
  - `issue_tokens(db, client_id: str, membre_id: int, family_id: str | None = None) -> TokenPair`
  - `refresh_tokens(db, client_id: str, refresh_token: str) -> TokenPair`
  - `revoke_token(db, raw: str) -> None` (révoque toute la famille, sans erreur si le token est inconnu)
  - `member_for_access_token(db, raw: str) -> Member | None` (access valide, non expiré, non révoqué ; **ne vérifie pas** le rôle)
  - Toutes les fonctions font `flush()`, pas `commit()` ; c'est l'appelant qui commit.

- [ ] **Step 1: Écrire les tests qui échouent** dans `tests/test_oauth_store.py` (fixture locale `oauth_client` = `register_client(db, "Claude Code", ["http://localhost:33418/callback"])`) :
  - `test_register_rejects_unknown_redirect` : `["https://evil.com/cb"]` → `OAuthError`, `.error == "invalid_redirect_uri"`.
  - `test_register_accepts_claude_ai` : `["https://claude.ai/api/mcp/auth_callback"]` est accepté.
  - `test_loopback_port_free` : `redirect_uri_matches(["http://localhost:33418/callback"], "http://localhost:51000/callback") is True` ; même chose avec `http://evil.com:51000/callback` et `http://localhost:51000/other` → `False`.
  - `test_code_exchange_ok` : `verifier = "a"*50`, `challenge = base64url(sha256(verifier))` sans padding ; `issue_code` puis `exchange_code` → `TokenPair`, `expires_in == 3600`, `member_for_access_token(access).id == bureau_member.id`.
  - `test_code_bad_verifier` → `OAuthError("invalid_grant")`.
  - `test_code_single_use` : deuxième `exchange_code` → `invalid_grant`.
  - `test_code_expired` : monkeypatch `oauth_store._now` à +6 min → `invalid_grant`.
  - `test_code_wrong_redirect_uri` → `invalid_grant`.
  - `test_refresh_rotates` : `refresh_tokens` renvoie un nouveau couple ; l'ancien refresh rejoué → `invalid_grant`, et le **nouvel** access donne alors `member_for_access_token(...) is None` (famille révoquée).
  - `test_access_expired` : `_now` à +61 min → `None`.
  - `test_revoke` : `revoke_token(access)` → `member_for_access_token(access) is None`.
  - `test_web_jwt_not_accepted` : `member_for_access_token(db, create_access_token(bureau_member.id)) is None`.

- [ ] **Step 2: Run** `TEST` avec `-k oauth_store` → FAIL (ImportError).

- [ ] **Step 3: Implémenter `oauth_store.py`.** Comparaison du challenge PKCE avec `hmac.compare_digest`. `family_id = secrets.token_hex(16)` à la première émission, réutilisé lors de la rotation. Rotation : marquer le refresh utilisé comme `revoked_at = _now()`. Un refresh déjà révoqué présenté → révoquer tous les tokens de la famille, puis `invalid_grant`.

- [ ] **Step 4: Run** `TEST` avec `-k oauth_store` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/oauth_store.py backend/tests/test_oauth_store.py
git commit -m "feat(mcp): service oauth_store (DCR, PKCE, tokens opaques)"
```

---

### Task 3: Router OAuth — metadata, register, token, revoke

**Files:**
- Create: `backend/app/routers/oauth.py`
- Modify: `backend/app/main.py` (include des deux routers)
- Test: `backend/tests/test_oauth_router.py`

**Interfaces:**
- Consumes : `oauth_store` (Task 2).
- Produces :
  - `oauth.well_known_router` (sans préfixe) et `oauth.router` (préfixe `/api/oauth`).
  - `GET /.well-known/oauth-protected-resource/api/mcp` → `{"resource": f"{base}/api/mcp", "authorization_servers": [base], "bearer_methods_supported": ["header"]}`.
  - `GET /.well-known/oauth-authorization-server` et `GET /.well-known/openid-configuration` (contenu identique) → `issuer`, `authorization_endpoint` (`{base}/api/oauth/authorize`), `token_endpoint`, `registration_endpoint`, `revocation_endpoint`, `response_types_supported: ["code"]`, `grant_types_supported: ["authorization_code","refresh_token"]`, `code_challenge_methods_supported: ["S256"]`, `token_endpoint_auth_methods_supported: ["none"]`.
  - `POST /api/oauth/register` (JSON RFC 7591) → 201 `{client_id, client_name, redirect_uris, token_endpoint_auth_method: "none", grant_types, response_types: ["code"], client_id_issued_at}` ; erreur → 400 `{"error": ..., "error_description": ...}`.
  - `POST /api/oauth/token` (form-urlencoded, `grant_type`, `client_id`, `code`, `redirect_uri`, `code_verifier` | `refresh_token`) → 200 `{access_token, token_type: "Bearer", expires_in, refresh_token}`, header `Cache-Control: no-store` ; erreur → 400 `{"error": ...}`.
  - `POST /api/oauth/revoke` (form `token`) → 200 dans tous les cas.
  - `base = settings.PUBLIC_BASE_URL.rstrip("/")`.

- [ ] **Step 1: Écrire les tests qui échouent** (fixture `client` existante) :
  - `test_protected_resource_metadata` : `resource == "http://localhost:3000/api/mcp"`.
  - `test_as_metadata` : `code_challenge_methods_supported == ["S256"]` ; `/.well-known/openid-configuration` renvoie le même JSON.
  - `test_register_ok` / `test_register_bad_uri` (400, `error == "invalid_redirect_uri"`).
  - `test_token_authorization_code` : client enregistré via l'API, code émis via `oauth_store.issue_code` sur `db_session`, `POST /api/oauth/token` en `data=` → 200, `token_type == "Bearer"`, `Cache-Control` = `no-store`.
  - `test_token_refresh` et `test_token_bad_grant_type` (400, `unsupported_grant_type`).
  - `test_revoke_unknown_token` → 200.

- [ ] **Step 2: Run** `TEST` avec `-k oauth_router` → FAIL (404).

- [ ] **Step 3: Implémenter** les endpoints du bloc Produces, en traduisant `OAuthError` en 400 JSON. `db.commit()` après chaque mutation réussie. Inclure les deux routers dans `main.py`.

- [ ] **Step 4: Run** `TEST` avec `-k oauth_router` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/oauth.py backend/app/main.py backend/tests/test_oauth_router.py
git commit -m "feat(mcp): endpoints OAuth metadata/register/token/revoke"
```

---

### Task 4: Authorize, consentement et retour du login Google

**Files:**
- Modify: `backend/app/routers/oauth.py`
- Modify: `backend/app/routers/auth.py` (`google_login`, `google_callback`)
- Test: `backend/tests/test_oauth_authorize.py`, ajout dans `backend/tests/test_google_auth.py`

**Interfaces:**
- Consumes : `oauth_store.get_client`, `redirect_uri_matches`, `issue_code` ; `core.security.decode_token` ; le cookie `access_token`.
- Produces :
  - `GET /api/oauth/authorize?response_type&client_id&redirect_uri&code_challenge&code_challenge_method&state&resource&scope` :
    - client inconnu, `redirect_uri` non enregistrée, `response_type != "code"` ou méthode PKCE ≠ `S256` → **400 HTML** (pas de redirection vers le client) ;
    - `resource` fourni et ≠ `{base}/api/mcp` → 400 HTML ;
    - cookie `access_token` absent ou invalide → **303** vers `/api/auth/google/login?next=<chemin+query authorize url-encodé>` ;
    - membre sans `bureau` → **403 HTML** « Accès MCP réservé au bureau » ;
    - sinon **200 HTML** : page de consentement affichant `client_name` et l'email du membre, formulaire POST vers `/api/oauth/authorize/consent` avec un champ caché `request` (`URLSafeTimedSerializer(settings.SECRET_KEY, salt="mcp-consent")` sur `{client_id, redirect_uri, code_challenge, state, resource, membre_id}`) et deux boutons `name="decision"` (`allow` / `deny`).
  - `POST /api/oauth/authorize/consent` (form `request`, `decision`) : signature invalide ou plus vieille que 600 s, ou `membre_id` différent du membre du cookie → 400 HTML. `deny` → 303 vers `redirect_uri?error=access_denied&state=…`. `allow` → `issue_code`, commit, 303 vers `redirect_uri?code=…&state=…` (paramètres ajoutés proprement si l'URI a déjà une query).
  - Dans `routers/auth.py` : `safe_next(value: str | None) -> str | None` renvoie `value` seulement s'il commence par `/api/oauth/authorize` (ni `//`, ni schéma). `google_login(request, next: str | None = None)` stocke `request.session["next"]` ; `google_callback` fait un `pop` et redirige vers ce `next` au lieu de `/` (en conservant la pose des cookies).

- [ ] **Step 1: Écrire les tests qui échouent** dans `test_oauth_authorize.py`. Utiliser un `TestClient(app)` **sans** override d'auth, avec seulement `get_db` overridé, et poser le cookie avec `create_access_token(member.id)` ; `follow_redirects=False`.
  - `test_authorize_unknown_client` → 400.
  - `test_authorize_plain_pkce` → 400.
  - `test_authorize_no_session_redirects_to_google` : 303, `location` commence par `/api/auth/google/login?next=%2Fapi%2Foauth%2Fauthorize`.
  - `test_authorize_staff_forbidden` : membre `roles=["staff"]` → 403.
  - `test_authorize_shows_consent` : 200, le `client_name` apparaît dans le HTML.
  - `test_consent_allow_redirects_with_code` : extraire `request` du HTML, POST `decision=allow` → 303, `location` commence par la `redirect_uri` et contient `code=` et `state=xyz` ; ce code s'échange via `/api/oauth/token`.
  - `test_consent_deny` → `error=access_denied`.
  - `test_consent_tampered` : `request` modifié → 400.
  - `test_consent_other_member` : cookie d'un autre membre bureau → 400.
- [ ] Dans `test_google_auth.py` : `test_safe_next` → `safe_next("/api/oauth/authorize?x=1")` accepté ; `"https://evil.com"`, `"//evil.com"`, `"/events"` et `None` → `None`.

- [ ] **Step 2: Run** `TEST` avec `-k "oauth_authorize or safe_next"` → FAIL.

- [ ] **Step 3: Implémenter.** HTML en f-string dans `oauth.py`, avec les valeurs **échappées** (`html.escape`) car `client_name` vient du client. Style minimal inline.

- [ ] **Step 4: Run** les tests ciblés → PASS, puis `-k google` → les tests Google existants PASS toujours.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/oauth.py backend/app/routers/auth.py backend/tests/test_oauth_authorize.py backend/tests/test_google_auth.py
git commit -m "feat(mcp): authorize + consentement, retour login Google via next"
```

---

### Task 5: Service partagé de création événement + créneaux

**Files:**
- Create: `backend/app/services/event_creation.py`
- Modify: `backend/app/routers/events.py` (`create_event`, `create_slots`, `_recompute_heures_relatives` délèguent au service)
- Test: `backend/tests/test_event_creation.py` (et `tests/test_slots.py` existant comme non-régression)

**Interfaces:**
- Produces (`app.services.event_creation`) :
  - `class EventPublieError(Exception)`
  - `build_slot_ranges(jour: date, debut: time, fin: time, pas_minutes: int = 60) -> list[tuple[datetime, datetime]]` : même algo que `buildSlots` dans `frontend/src/components/events/EventForm.jsx` (fin ≤ début = lendemain, dernier créneau tronqué à la fin).
  - `recompute_heures_relatives(db, event_id: int) -> None` (déplacé depuis le router, qui l'importe)
  - `add_slots(db, event: Event, ranges: list[tuple[datetime, datetime]], max_personnes: int) -> list[Slot]` : lève `EventPublieError` si l'event est publié ; dédoublonne ; recalcule ; `flush` ; renvoie tous les créneaux triés.
  - `new_event(db, nom: str, date: datetime, type: EventTypeEnum) -> Event` (avec `public_token = secrets.token_urlsafe(16)`, `flush`).
  - Le router traduit `EventPublieError` en 400 avec le même message qu'aujourd'hui (« Événement publié : créneaux verrouillés »).

- [ ] **Step 1: Écrire les tests qui échouent** :
  - `test_ranges_afterwork` : `build_slot_ranges(date(2026,11,5), time(18), time(20))` → `[(18:00,19:00),(19:00,20:00)]` le 5/11.
  - `test_ranges_midnight` : 22h → 02h donne 4 créneaux, le 3ᵉ commence le 6/11 à 00:00.
  - `test_ranges_truncated` : 18h → 19h30 au pas de 60 → le dernier créneau est `(19:00, 19:30)`.
  - `test_add_slots_heures_relatives` : `new_event` + `add_slots` sur les plages 22h-02h → `heure_relative == [0,1,2,3]`, `max_personnes` respecté.
  - `test_add_slots_publie` : statut `publie` → `EventPublieError`.

- [ ] **Step 2: Run** `-k event_creation` → FAIL.

- [ ] **Step 3: Implémenter le service et faire déléguer `routers/events.py`.**

- [ ] **Step 4: Run** `-k "event_creation or slots or duplicate"` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/event_creation.py backend/app/routers/events.py backend/tests/test_event_creation.py
git commit -m "refactor(events): extrait la création event/créneaux dans un service"
```

---

### Task 6: Serveur MCP, middleware bearer et les 4 tools

**Files:**
- Create: `backend/app/mcp/__init__.py`, `backend/app/mcp/context.py`, `backend/app/mcp/auth.py`, `backend/app/mcp/tools.py`, `backend/app/mcp/server.py`
- Modify: `backend/app/main.py` (lifespan + montage)
- Test: `backend/tests/test_mcp.py`

**Interfaces:**
- Consumes : `oauth_store.member_for_access_token`, `oauth_store.issue_tokens` (tests), `event_creation.*`, modèles `Event`, `Saison`.
- Produces :
  - `app.mcp.context` : `current_member: ContextVar[Member]` ; `open_session()`, un contextmanager qui yield une `Session` (`SessionLocal` + close). Le middleware et les tools l'appellent **via le module** (`context.open_session()`) pour que les tests puissent le monkeypatcher.
  - `app.mcp.auth.BearerAuthMiddleware(app)` (ASGI) : `Authorization: Bearer <t>` → `member_for_access_token` → absent ou invalide : 401 JSON `{"error":"invalid_token"}` avec `WWW-Authenticate: Bearer resource_metadata="{base}/.well-known/oauth-protected-resource/api/mcp"` ; membre sans `bureau` → 403 `{"error":"insufficient_scope"}` ; sinon pose `current_member` et délègue.
  - `app.mcp.tools` : des fonctions pures qui prennent `db`, appelées par les wrappers MCP :
    - `create_event(db, nom: str, type: str, date: str, heure_debut: str, heure_fin: str, max_personnes: int = 3, duree_creneau_minutes: int = 60) -> dict` : `date` au format `YYYY-MM-DD`, heures en `HH:MM` ; renvoie `{"event": {...}, "creneaux": [...], "url": f"{base}/events/{id}"}` ; commit.
    - `list_events(db, statut: str | None = None, type: str | None = None, depuis: str | None = None, jusqu_a: str | None = None, limite: int = 20) -> list[dict]` (tri date décroissante, avec `nb_creneaux`).
    - `get_event(db, event_id: int) -> dict` (event + créneaux + `inscriptions_ouvertes`, `inscriptions_deadline`) ; event introuvable → `ValueError("Événement introuvable")`.
    - `list_saisons(db) -> list[dict]`.
  - `app.mcp.server` : instance FastMCP `"planning"` qui enregistre les 4 tools (descriptions en français avec un exemple, `readOnlyHint` sur les 3 lectures), stateless, réponses JSON ; expose `mcp_asgi_app` (déjà enveloppé dans `BearerAuthMiddleware`) et `mcp_lifespan(app)`.
  - Endpoint servi exactement à **`/api/mcp`** (POST, sans redirection de slash).
  - Contrainte lifespan : `main.py` appelle `mcp_lifespan` dans le `lifespan` de FastAPI. Le session manager streamable HTTP doit être **recréé à chaque entrée du lifespan** (un `StreamableHTTPSessionManager` ne peut tourner qu'une fois, et les tests rejouent le lifespan à chaque `TestClient`).

**Convention de date de `create_event` :** `Event.date` est stocké comme le fait le front (`new Date(...).toISOString()`). Les créneaux sont stockés en heure locale naïve (`toLocalIso`). Avant d'implémenter, vérifier en base dev sur un event créé depuis l'UI :

```bash
docker compose exec postgres psql -U baruser salope -c \
 "select e.date, min(s.heure_debut) from events e join slots s on s.evenement_id=e.id group by e.id order by e.id desc limit 5;"
```

Si `e.date` est décalé de -1 h / -2 h par rapport au premier créneau, convertir l'heure de début Europe/Paris en UTC naïf (`zoneinfo.ZoneInfo("Europe/Paris")`). Sinon, la stocker telle quelle. Noter le constat dans le message de commit.

- [ ] **Step 1: Écrire les tests qui échouent** dans `test_mcp.py`. Fixtures :
  - `mcp_client` : `TestClient(app)` avec override `get_db` et `monkeypatch.setattr(app.mcp.context, "open_session", <contextmanager qui yield db_session sans le fermer>)` ;
  - `bureau_token` : `oauth_store.register_client(...)` puis `issue_tokens(...)`.
  Helper `rpc(client, token, method, params)` : POST `/api/mcp` avec `{"jsonrpc":"2.0","id":1,"method":...,"params":...}` et les headers `Accept: application/json, text/event-stream`, `Authorization: Bearer …`.
  - `test_mcp_no_token` → 401 avec un header `WWW-Authenticate` qui contient `resource_metadata=`.
  - `test_mcp_web_jwt_rejected` : bearer `create_access_token(id)` → 401.
  - `test_mcp_demoted_member` : token valide, puis `bureau_member.roles = ["staff"]` et flush → 403.
  - `test_mcp_no_trailing_slash` : `tools/list` sur `/api/mcp` → 200 (pas de 307), avec exactement les 4 noms de tools.
  - `test_tool_create_event_afterwork` : `tools/call create_event {nom:"Afterwork test", type:"afterwork", date:"2026-11-05", heure_debut:"18:00", heure_fin:"20:00"}` → en base, 1 event `brouillon` et 2 créneaux 18-19 / 19-20 avec `max_personnes == 3` et `heure_relative` 0/1 ; `inscriptions_ouvertes` reste `False`.
  - `test_tool_list_and_get_event` : après création, `list_events` contient l'event avec `nb_creneaux == 2` ; `get_event` renvoie les 2 créneaux ; un id inconnu donne une réponse `isError: true`.
  - `test_tool_list_saisons` : une saison avec `date_fin=None` apparaît.

- [ ] **Step 2: Run** `-k mcp` → FAIL.

- [ ] **Step 3: Implémenter `context.py`, `auth.py`, `tools.py`, `server.py`, puis brancher dans `main.py`.**

- [ ] **Step 4: Run** `-k mcp` → PASS, puis la suite complète `TEST` → tout PASS (couvre le point 4 du Review Focus).

- [ ] **Step 5: Commit**

```bash
git add backend/app/mcp backend/app/main.py backend/tests/test_mcp.py
git commit -m "feat(mcp): serveur MCP /api/mcp + tools create_event, list_events, get_event, list_saisons"
```

---

### Task 7: Routage `/.well-known`, documentation et essai réel

**Files:**
- Modify: `k8s/ingress.yaml` (path `/.well-known` Prefix → `salope-backend:8000`, **avant** `/`)
- Modify: `frontend/vite.config.js` (proxy `/.well-known` → `http://backend:8000`)
- Modify: `CLAUDE.md` (section « Serveur MCP » : URL, commande `claude mcp add --transport http planning http://localhost:3000/api/mcp`, ajout d'un connecteur sur claude.ai, variables `PUBLIC_BASE_URL` / `MCP_*`, emplacement de la spec avec le catalogue complet)
- Modify: `k8s/` (manifeste configmap/secret du backend : `PUBLIC_BASE_URL=https://planning.lateb.eu`)

- [ ] **Step 1: Appliquer les modifications de routage et de config**, puis `docker compose up --build`.

- [ ] **Step 2: Vérifier la découverte via le proxy front**

Run : `curl -s http://localhost:3000/.well-known/oauth-protected-resource/api/mcp`
Expected : JSON avec `"resource":"http://localhost:3000/api/mcp"`.

Run : `curl -si -X POST http://localhost:3000/api/mcp | head -5`
Expected : `401` et un header `WWW-Authenticate` qui contient `resource_metadata`.

- [ ] **Step 3: Essai réel avec Claude Code** (à faire par l'utilisateur, connecté avec un compte bureau) : `claude mcp add --transport http planning http://localhost:3000/api/mcp`, puis `/mcp` → login Google → consentement → demander « crée un afterwork jeudi prochain de 18h à 20h ». Expected : l'event apparaît dans l'UI à 18h avec 2 créneaux.

- [ ] **Step 4: Vérifier les redirect URIs de claude.ai / Claude Desktop / Cursor** dans la doc officielle des clients, puis ajuster le défaut de `MCP_ALLOWED_REDIRECT_URIS` et la spec si besoin.

- [ ] **Step 5: Commit**

```bash
git add k8s frontend/vite.config.js CLAUDE.md docs/superpowers/specs/2026-10-28-mcp-server-design.md
git commit -m "chore(mcp): routage .well-known, config prod et doc de branchement"
```
