# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Dev local (Docker requis)

```bash
docker compose up --build   # Premier lancement (build + migrations)
docker compose up           # Lancements suivants
docker compose down         # Arrêt (données conservées)
docker compose down -v      # Purge complète
```

Services exposés : frontend `:3000` (hot-reload), backend `:8000` (hot-reload + Swagger `/docs`), PostgreSQL `:5433`.

### Tests backend

Avec la stack docker compose démarrée :

```bash
docker compose run --rm --no-deps \
  -v ./backend/tests:/app/tests \
  -v ./backend/app:/app/app \
  -v ./backend/requirements-dev.txt:/app/requirements-dev.txt \
  -e TEST_DATABASE_URL=postgresql://baruser:barpassword@postgres:5432/salope_test \
  backend bash -c "pip install -q -r requirements-dev.txt && pytest tests -v"
```

Pour un test unique : ajouter `-k test_nom_du_test` à la commande pytest.

### Migrations

```bash
docker compose run --rm migrations   # Applique toutes les migrations en attente
```

### Frontend (hors docker)

```bash
cd frontend && npm ci && npm run dev    # Dev server :3000
cd frontend && npm run build            # Build prod
```

## Architecture

Stack monorepo : `frontend/` (React 18 + Vite + Tailwind) et `backend/` (FastAPI + SQLAlchemy + PostgreSQL 16). En dev les deux tournent dans Docker Compose ; en prod K3s sur OVH (`k8s/`).

### Backend

- **`app/main.py`** : app FastAPI + CORS, monte les 7 routers sous `/api/*`
- **`app/models/models.py`** : toutes les entités ORM (source de vérité schéma)
- **`app/schemas/schemas.py`** : schémas Pydantic requêtes/réponses
- **`app/core/deps.py`** : dépendances FastAPI (`get_current_user`, `require_bureau`)
- **`app/routers/events.py`** : le plus gros router (1000+ lignes), orchestre CSV import, génération, publication
- **`app/services/scheduler.py`** : solveur CP-SAT OR-Tools (~830 lignes) — cœur du système de génération de planning
- **`app/services/csv_import.py`** : parsing CSV Strawpoll + fuzzy matching (RapidFuzz) + gestion pending
- **`app/services/public_poll.py`** : logique formulaire public (soumission, résolution pending)
- **`app/services/historical_img_import.py`** : OCR Tesseract + détection grille + fuzzy matching noms
- **`alembic/versions/`** : 8 migrations (001 → 008)

### Frontend

- **`src/App.jsx`** : routeur React (6 routes dont `/dispo/:token` sans auth)
- **`src/api/client.js`** : instance axios avec intercepteurs (cookies JWT, toasts d'erreur automatiques)
- **`src/pages/EventDetailPage.jsx`** : page principale du workflow (6 onglets : Disponibilités → Créneaux → Respos → Affinités → Participants → Planning)
- **`src/components/planning/PlanningGrid.jsx`** : grille cliquable (modifier/supprimer affectation, stack undo côté client)
- **`src/utils/computeWarnings.js`** : calcul des warnings W1-W7 côté client

### Flux de données principal

```
Event (brouillon)
  → Créneaux (générateur ou CSV)
  → Disponibilités (formulaire public /dispo/{token} ou CSV Strawpoll)
  → generate / generate-proposals → apply-proposal
  → Ajustements manuels
  → publish()  →  incrémente fois_staffe + shifts_respo_bar_cumules
  → export PNG
```

La publication est la seule action qui met à jour les compteurs de stats. La dépublication les décrémente symétriquement.

### Auth

Login Google OIDC (`/api/auth/google/login` → callback, `services/google_auth.py`) : tout compte `@lateb.eu` est créé en `staff` au premier login, et les emails de `BUREAU_EMAILS` reçoivent `bureau`. Le login email/mot de passe reste dispo. Ensuite JWT en httpOnly cookies (access + refresh). `require_bureau` dans `deps.py` gate les mutations sensibles. Le formulaire public (`/api/public/polls/{token}`) est le seul endpoint sans auth — le token opaque fait office d'accès.

### Modèle de données — points non-évidents

- `heure_relative` sur `Slot` est un index (0, 1, 2…) qui sert de clé pour les stats — **1 créneau = 1 heure** par convention.
- `StatsMemberHeureRelative` agrège par `(membre_id, type_evenement, heure_relative)` — les histogrammes de la page Membres en dépendent.
- `Saison.date_fin = NULL` signifie saison en cours (pas de borne haute).
- `Assignment.maybe_force` indique qu'un membre a été affecté malgré une dispo `maybe`.
- `PendingSubmission` est la table tampon pour les noms non reconnus du formulaire public ou du CSV — `nom_normalise` est la clé d'unicité (pas `nom_saisi`).
- `Event.excluded_member_ids` (ARRAY int) — les membres exclus sont ignorés par le solveur CP-SAT.

### Solveur CP-SAT (`scheduler.py`)

Deux modes : `generate` (résout et persiste directement) et `generate-proposals` (calcule 2-3 variantes sans écrire, `apply-proposal` choisit). Timeout 10 s. Contrainte dure : `max_personnes` par slot. Pénalités pondérées : créneau sans respo bar, sans bureau, sous-staffé, quota dépassé (> 2 h), dispo `maybe` utilisée, affinité insatisfaite, pause longue (≥ 3 h).

### Conventions

- Vocabulaire métier **français partout** dans le code : `creneau`, `heure_relative`, `fois_staffe`, `membre_id`, `statut`, `brouillon`/`publie`.
- Datetimes **naïfs** (sans timezone).
- La stack undo du planning utilise `(creneau_id, membre_id)` comme clé naturelle, jamais l'id d'assignment.
- Tests backend : pytest + `TestClient` FastAPI contre une vraie base `salope_test` (pas de mocks DB). Fixtures dans `tests/conftest.py`.

## Serveur MCP (`/api/mcp`)

Le backend expose un serveur MCP (SDK `mcp` 2.x, `MCPServer`, streamable HTTP stateless, protocole jusqu'à 2026-07-28) réservé au **bureau**, protégé par un serveur d'autorisation OAuth 2.1 maison adossé au login Google.

- **`app/mcp/`** : `server.py` (tools + lifespan), `tools.py` (logique, fonctions pures sur `db`), `auth.py` (bearer + rôle bureau revérifié à chaque requête), `context.py` (session DB, monkeypatchée en test).
- **`app/routers/oauth.py`** : découverte `/.well-known/oauth-protected-resource/api/mcp` + `/.well-known/oauth-authorization-server`, `/api/oauth/register` (DCR), `/authorize` (+ écran de consentement), `/token`, `/revoke`.
- **`app/services/oauth_store.py`** : clients, codes PKCE S256, tokens opaques hashés (access 1 h, refresh 30 j avec rotation). Un token MCP n'est jamais un JWT web, et inversement.
- Tools V1 : `create_event`, `list_events`, `get_event`, `list_saisons`. Catalogue complet prévu : `docs/superpowers/specs/2026-10-28-mcp-server-design.md`.

Brancher un client :

```bash
claude mcp add --transport http planning http://localhost:3000/api/mcp     # dev
claude mcp add --transport http planning https://planning.lateb.eu/api/mcp # prod
# puis /mcp dans Claude Code → login Google → consentement
```

Sur claude.ai / Claude Desktop : Paramètres → Connecteurs → ajouter un connecteur personnalisé avec l'URL prod.

Variables : `PUBLIC_BASE_URL` (issuer OAuth, doit être l'URL publique du front), `MCP_ACCESS_TOKEN_EXPIRE_MINUTES`, `MCP_REFRESH_TOKEN_EXPIRE_DAYS`, `MCP_ALLOWED_REDIRECT_URIS`. `/.well-known` doit être routé vers le backend (ingress + proxy Vite).

## Créer une migration Alembic

```bash
# 1. Générer le fichier de migration (depuis le conteneur backend)
docker compose exec backend alembic revision --autogenerate -m "description_courte"

# 2. Vérifier/éditer le fichier généré dans alembic/versions/
# 3. Appliquer
docker compose run --rm migrations
```

Nommer les migrations : `NNN_description_courte.py` (NNN = numéro séquentiel suivant).

## Premier utilisateur bureau

Après le premier `docker compose up` :

```bash
docker compose exec backend python -c "
from app.database import SessionLocal
from app.models.models import Member
from app.core.security import hash_password
db = SessionLocal()
m = Member(nom='Nom', prenom='Prénom', email='admin@lateb.eu', roles=['staff', 'bureau'], hashed_password=hash_password('motdepasse'))
db.add(m)
db.commit()
print('Membre créé, id =', m.id)
"
```

## Variables d'environnement backend

Minimales pour faire tourner le backend hors docker (copier `.env.example` → `.env`) :

| Variable | Valeur dev | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://baruser:barpassword@localhost:5433/salope` | PostgreSQL (port 5433 depuis l'hôte) |
| `SECRET_KEY` | n'importe quelle chaîne ≥ 32 chars | Signature JWT |
| `ALLOWED_EMAIL_DOMAIN` | `lateb.eu` | Domaine email autorisé au login |
| `CORS_ORIGINS` | `http://localhost:3000` | Origin frontend |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | depuis Google Cloud Console | Client OAuth « Web » ; redirect URI `http://localhost:3000/api/auth/google/callback` |
| `BUREAU_EMAILS` | `zachee.descamps@lateb.eu` | Emails (virgules) promus `bureau` à la connexion |
| `COOKIE_SECURE` | `false` | `true` uniquement en prod HTTPS |
