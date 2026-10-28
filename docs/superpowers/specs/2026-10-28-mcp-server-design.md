# Serveur MCP du planning — design

Date : 2026-10-28 · Statut : à valider

## Intention

Permettre aux membres du **bureau** de piloter le planning depuis un agent IA
(Claude Code, claude.ai, Claude Desktop, autres clients MCP courants) en langage
naturel : « je veux organiser un afterwork de 18h à 20h jeudi » → l'événement et
ses créneaux sont créés.

Le serveur MCP est **exposé directement par le backend FastAPI existant** et
sécurisé par **OAuth 2.1 adossé à nos comptes** (login Google `@lateb.eu`
existant). Seuls les membres `bureau` y ont accès.

## Objectifs

- V1 = un **noyau de test** : le socle OAuth complet + 4 tools (voir § Noyau V1).
- Documenter l'**ensemble du catalogue** de tools envisagés (§ Catalogue complet)
  pour les itérations suivantes.
- Brancher le serveur en une commande :
  `claude mcp add --transport http planning https://planning.lateb.eu/api/mcp`,
  puis `/mcp` → login Google → c'est prêt. Idem via « Ajouter un connecteur » sur
  claude.ai / Claude Desktop.

## Non-objectifs (V1)

- Pas d'enchaînement automatique : `create_event` crée l'événement et ses
  créneaux **puis s'arrête** (pas d'ouverture du formulaire, pas de génération).
- Pas d'UI de gestion des clients/tokens OAuth (révocation = SQL / plus tard).
- Pas d'accès MCP pour les membres `staff` non-bureau.

## Anti-objectifs (échec même si « ça marche »)

- Un token MCP qui fonctionne aussi comme cookie/JWT de l'app web, ou l'inverse.
- Un membre retiré du bureau qui garde l'accès MCP jusqu'à expiration du token.
- Un client enregistré dynamiquement qui obtient un token **sans écran de
  consentement** explicite (risque de phishing via DCR).
- Des tools MCP qui dupliquent la logique métier des routers au lieu de la
  partager (deux comportements divergents pour « créer des créneaux »).
- Des actions destructrices (merge, reset compteurs, suppression membre)
  exposées au MCP.

## Contraintes

- Stack existante : FastAPI 0.111, SQLAlchemy 2, PostgreSQL 16, authlib (Google
  OIDC déjà en place dans `routers/auth.py` / `services/google_auth.py`).
- Prod : K3s, ingress Traefik `planning.lateb.eu` — `/api` → backend, `/` →
  frontend. Dev : Vite proxifie `/api` vers `backend:8000`.
- Conventions projet : vocabulaire métier français, datetimes naïfs, tests
  pytest contre la vraie base `salope_test`, migrations `NNN_description.py`.
- Spécification MCP Authorization (révision 2025-06-18 ou plus récente) :
  serveur MCP = *resource server* OAuth 2.1, PKCE S256 obligatoire, Protected
  Resource Metadata (RFC 9728), Authorization Server Metadata (RFC 8414),
  Dynamic Client Registration (RFC 7591), paramètre `resource` (RFC 8707).

## Architecture

```
Client MCP (Claude Code / claude.ai / Desktop)
   │ 1. POST /api/mcp  → 401 + WWW-Authenticate: resource_metadata=…
   │ 2. GET  /.well-known/oauth-protected-resource/api/mcp
   │ 3. GET  /.well-known/oauth-authorization-server
   │ 4. POST /api/oauth/register            (DCR, client public)
   │ 5. navigateur → GET /api/oauth/authorize (PKCE)
   │        └─ pas de session web ? → login Google existant → retour authorize
   │        └─ membre non bureau ?  → page d'erreur
   │        └─ écran de consentement → code
   │ 6. POST /api/oauth/token              (code + code_verifier)
   │ 7. POST /api/mcp  Authorization: Bearer <token MCP>
```

Tout vit dans le backend :

- **`app/routers/oauth.py`** (nouveau) : metadata, register, authorize
  (+ consentement), token, revoke.
- **`app/mcp/`** (nouveau) : serveur MCP (SDK Python officiel `mcp`, transport
  *streamable HTTP*, mode stateless), monté sur `/api/mcp`, + vérification du
  bearer token.
- **`app/services/`** : la logique de création événement + créneaux est extraite
  des routers vers un service partagé par le router REST et le tool MCP.

### Choix de lib — *décision Claude*

SDK officiel `mcp` 2.x (`MCPServer`, protocole 2026-07-28) pour le protocole et la vérification du
token côté resource server. Le serveur d'autorisation est écrit **à la main**
dans un router FastAPI (quelques endpoints, explicite, testable avec
`TestClient`) plutôt que via le provider AS du SDK. Le builder peut revoir ce
choix s'il constate que le provider du SDK couvre proprement le flux « login
Google + consentement ».

Points d'attention : le SDK `mcp` peut exiger des versions plus récentes de
pydantic/starlette que celles pinnées (`fastapi==0.111.0`, `pydantic==2.7.1`)
— monter les versions si nécessaire et vérifier que la suite de tests passe. Le
session manager streamable HTTP doit être démarré dans le `lifespan` de l'app.

## OAuth — détail

### URLs (prod)

| Élément | Valeur |
|---|---|
| Ressource MCP | `https://planning.lateb.eu/api/mcp` |
| Issuer AS | `https://planning.lateb.eu` |
| Protected Resource Metadata | `/.well-known/oauth-protected-resource/api/mcp` |
| AS Metadata | `/.well-known/oauth-authorization-server` (servir aussi `/.well-known/openid-configuration` avec le même contenu, certains clients la cherchent) |
| Endpoints | `/api/oauth/register`, `/api/oauth/authorize`, `/api/oauth/token`, `/api/oauth/revoke` |

Base publique configurable via `PUBLIC_BASE_URL` (dev : `http://localhost:3000`).

**Routage `/.well-known`** : ajouter un path `/.well-known` → backend dans
`k8s/ingress.yaml` et un proxy `/.well-known` dans `frontend/vite.config.*`.

### Enregistrement dynamique (DCR)

- Clients **publics uniquement** (`token_endpoint_auth_method: none`),
  `grant_types: authorization_code, refresh_token`.
- Chaque `redirect_uri` déclaré doit matcher l'**allowlist** :
  - loopback, n'importe quel port et chemin : `http://localhost:*`,
    `http://127.0.0.1:*`, `http://[::1]:*` (Claude Code, Codex CLI, VS Code,
    Cursor, MCP Inspector…) ;
  - `https://claude.ai/api/mcp/auth_callback` et
    `https://claude.com/api/mcp/auth_callback` (claude.ai **et** Claude Desktop) ;
  - `https://vscode.dev/redirect` (VS Code web) ;
  - schémas custom des IDE courants (ex. Cursor) — **à vérifier** au moment de
    l'implémentation dans la doc de chaque client.
  - Les URIs exactes de claude.ai/Desktop sont à **revérifier** dans la doc
    Anthropic au moment de l'implémentation.
- Allowlist surchargeable par env `MCP_ALLOWED_REDIRECT_URIS` (liste séparée par
  des virgules, `*` autorisé uniquement pour le port loopback).
- Le `client_name` déclaré est stocké et **affiché sur l'écran de
  consentement**.

### Authorize

1. Valider `client_id`, `redirect_uri` (match exact avec une URI enregistrée ;
   pour le loopback, port libre — RFC 8252), `response_type=code`,
   `code_challenge_method=S256` (obligatoire), `resource` = ressource MCP si
   fourni.
2. Session web : réutiliser le cookie `access_token` existant (`decode_token`).
   Absent/expiré → rediriger vers `/api/auth/google/login?next=<url authorize
   complète>`. `google_login` / `google_callback` doivent accepter un `next`
   **relatif commençant par `/api/oauth/authorize`** (rien d'autre, anti open
   redirect), stocké en session authlib, et y rediriger après avoir posé les
   cookies.
3. Membre sans rôle `bureau` → page HTML d'erreur « réservé au bureau » (pas de
   redirection vers le client).
4. **Écran de consentement** HTML minimal rendu par le backend : « *<client_name>*
   veut accéder au planning en ton nom (<email>) » + Autoriser / Refuser.
   Formulaire POST protégé CSRF (paramètres signés via `itsdangerous`, déjà en
   dépendance). Refuser → redirect `error=access_denied`.
5. Autoriser → code aléatoire, **usage unique, 5 min**, lié à client,
   redirect_uri, code_challenge, membre, resource → redirect avec `code` +
   `state`.

### Token

- `authorization_code` : vérifie code (non consommé, non expiré), client,
  redirect_uri, `code_verifier` (S256). Consomme le code.
- `refresh_token` : **rotation** à chaque usage ; réutilisation d'un refresh déjà
  consommé → révoque toute la famille.
- Tokens **opaques** (aléatoires), stockés **hashés** (SHA-256) en base — donc
  jamais acceptés par `get_current_member` et révocables.
- Durées : access **1 h**, refresh **30 jours** (*décision Claude*, via env
  `MCP_ACCESS_TOKEN_EXPIRE_MINUTES`, `MCP_REFRESH_TOKEN_EXPIRE_DAYS`).

### Vérification à chaque appel MCP

Bearer → hash → token valide non expiré non révoqué → charge le `Member` →
**revérifie `bureau` dans `roles`** → sinon 401 (token) / 403 (rôle). Les 401
portent `WWW-Authenticate: Bearer resource_metadata="…"`.

### Modèle de données (migration `011_oauth_mcp.py`)

- `oauth_clients` : `client_id` (PK, aléatoire), `client_name`,
  `redirect_uris` (ARRAY text), `created_at`.
- `oauth_authorization_codes` : `code_hash`, `client_id`, `membre_id`,
  `redirect_uri`, `code_challenge`, `resource`, `expires_at`, `used_at`.
- `oauth_tokens` : `token_hash`, `type` (`access`/`refresh`), `client_id`,
  `membre_id`, `family_id`, `expires_at`, `revoked_at`, `created_at`.

## Noyau V1 — tools

Tous exigent un token valide d'un membre bureau.

### `create_event` (écriture)

Entrées :
- `nom` (str), `type` (`afterwork` | `soiree`)
- `date` (`YYYY-MM-DD`), `heure_debut` (`HH:MM`), `heure_fin` (`HH:MM`)
- `max_personnes` (int, défaut 3), `duree_creneau_minutes` (int, défaut 60)

Comportement — **identique au formulaire web** (`EventForm.jsx` →
`buildSlots`) :
- `Event.date` = date + heure_debut ; `public_token` généré comme dans
  `routers/events.py::create_event`.
- Découpe `[heure_debut, heure_fin]` en créneaux de `duree_creneau_minutes` ;
  `heure_fin ≤ heure_debut` = passage minuit (fin le lendemain).
- Créneaux créés via la **même logique** que `create_slots` (dédoublonnage,
  `_recompute_heures_relatives`) — extraite dans un service partagé.
- Ne fait rien d'autre. Retourne l'event (id, nom, type, date, statut) + la liste
  des créneaux + l'URL de l'event dans l'app (`/events/{id}`).

⚠ Convention de datetime : le front envoie `new Date(...).toISOString()` (UTC).
Le builder doit vérifier ce qui est **réellement stocké** en base pour un event
créé depuis l'UI et faire en sorte qu'un event créé via MCP pour « 18h »
s'affiche à 18h dans l'UI, comme s'il avait été créé depuis le formulaire.

### `list_events` (lecture)

Filtres optionnels : `statut`, `type`, `depuis` / `jusqu_a` (dates). Tri par
date décroissante, limite 20 par défaut. Résumé par event : id, nom, type, date,
statut, nb créneaux.

### `get_event` (lecture)

`event_id` → event + créneaux (heure_debut, heure_fin, heure_relative,
max_personnes) + statut du formulaire public (ouvert/fermé, deadline).

### `list_saisons` (lecture)

Liste des saisons (nom, date_debut, date_fin — `NULL` = en cours).

Annotations MCP : `readOnlyHint` sur les tools de lecture ; `create_event` non
destructif. Descriptions des tools en français, avec un exemple d'usage.

## Catalogue complet (itérations futures)

Légende : L = lecture, É = écriture, ⚠ = demander confirmation explicite à
l'utilisateur dans la description du tool.

**Événements**
- `duplicate_event` (É) — repartir d'un event passé.
- `update_event` (É) — renommer, changer date/type/logo.
- `delete_event` (É ⚠) — brouillon uniquement.

**Créneaux**
- `list_slots` (L), `set_slots` (É — remplace la grille), `update_slot` (É —
  `max_personnes`).

**Disponibilités / formulaire public**
- `open_availability_poll` (É) — ouvre + deadline, renvoie le lien
  `/dispo/{token}`.
- `close_availability_poll` (É).
- `get_availability_summary` (L) — qui est dispo où, trous (pas de respo, pas de
  bureau…).
- `list_pending_submissions` (L) / `resolve_pending` (É) — rattacher un nom saisi
  à un membre.

**Contraintes**
- `set_respos_bar` (É), `add_affinity` / `remove_affinity` (É),
  `set_exclusions` (É).

**Génération & planning**
- `generate_proposals` (L — calcule sans écrire, renvoie 2-3 variantes
  comparées).
- `apply_proposal` (É).
- `get_planning` (L) — planning + warnings W1-W7.
- `assign_member` / `unassign_member` (É) — clé `(creneau_id, membre_id)`.
- `publish_event` / `unpublish_event` (É ⚠ — impacte les compteurs).
- `export_planning_png` (L) — renvoie l'image.

**Membres & stats** (lecture seule)
- `search_members` (fuzzy nom + alias), `get_member_stats`,
  `get_stats_overview` (« qui a le moins staffé cette saison ? »).

**Prompt MCP** : `organiser_evenement` — guide création → lien dispo →
génération → publication.

**Exclus du MCP** (restent dans l'UI) : merge membres, reset compteurs
(unitaire et global), suppression membre, import CSV / OCR historique, gestion
des logos.

## Tests attendus

- OAuth bout en bout avec `TestClient` : DCR (URI autorisée / refusée), authorize
  sans session → redirection login, non-bureau → refus, consentement →
  code, token avec bon/mauvais `code_verifier`, code rejoué, refresh rotation +
  détection de réutilisation, révocation.
- Bearer : token web JWT refusé sur `/api/mcp`, token MCP refusé sur les routes
  REST, membre rétrogradé → 403 immédiat.
- Tools : `create_event` 18h-20h → 2 créneaux `heure_relative` 0/1 ; 22h-02h →
  4 créneaux sur deux jours ; lectures.
- Le login Google lui-même n'est pas testé de bout en bout (simuler une session
  web via le cookie `access_token`, comme les tests existants).

## Décisions Claude (à relire)

- Consentement affiché **à chaque** authorize (pas de mémorisation par client).
- **Pas de scopes** en V1 : un token MCP = tous les tools, accès bureau.
- Heures saisies via MCP interprétées en **Europe/Paris**, converties pour
  correspondre à ce que stocke l'UI (`Event.date` envoyé en UTC par le front,
  créneaux en heure locale naïve via `toLocalIso`).
- Une seule réplique backend : pas de coordination multi-instance nécessaire.

## Laissé au builder

- Organisation interne de `app/mcp/` et du service partagé événement/créneaux.
- Style de l'écran de consentement (HTML simple, sans dépendance front).
- Format exact des réponses texte des tools (lisibles par un LLM, avec ids).
- Nettoyage des codes/tokens expirés (tâche au démarrage ou à la volée).
- Section README / CLAUDE.md « Brancher le MCP » (commande `claude mcp add`,
  ajout connecteur claude.ai).
