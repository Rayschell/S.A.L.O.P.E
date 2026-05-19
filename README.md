# S.A.L.O.P.E

Application de gestion de planning de shifts pour bar associatif.

---

## Architecture

```
frontend/   React 18 + Vite + Tailwind CSS — servi par nginx
backend/    Python 3.12 + FastAPI + SQLAlchemy + Alembic
k8s/        Manifests Kubernetes pour K3s (OVH VPS)
```

---

## Prérequis locaux

- Docker avec `docker-compose` installé
- kubectl configuré sur votre cluster K3s (pour le déploiement prod uniquement)
- cert-manager installé dans le cluster (avec un `ClusterIssuer` nommé `letsencrypt-prod`)

---

## Développement local avec Docker

Le `docker-compose.yml` fournit un environnement complet avec **hot-reload** sur le backend et le frontend.

### Démarrage

```bash
# Premier lancement — build les images et applique les migrations
docker compose up --build

# Lancement suivants (images déjà buildées)
docker compose up
```

| Service | URL | Hot-reload |
|---|---|---|
| Frontend (Vite) | http://localhost:3000 | Oui — tout changement dans `frontend/src/` est reflété instantanément |
| Backend (uvicorn) | http://localhost:8000 | Oui — tout changement dans `backend/app/` redémarre le serveur |
| API docs | http://localhost:8000/docs | — |
| PostgreSQL | localhost:5432 | — |

> Les migrations Alembic sont appliquées automatiquement au démarrage via le service `migrations`.

### Commandes utiles

```bash
# Voir les logs d'un service
docker compose logs -f backend
docker compose logs -f frontend

# Relancer les migrations manuellement (ex. après une nouvelle migration)
docker compose run --rm migrations

# Accéder au shell d'un conteneur
docker compose exec backend bash
docker compose exec postgres psql -U baruser -d salope

# Arrêter et supprimer les conteneurs (les données postgres sont conservées)
docker compose down

# Tout supprimer y compris le volume postgres
docker compose down -v
```

### Premier utilisateur bureau

Après le premier `docker compose up`, créer le compte admin :

```bash
docker compose exec backend python -c "
from app.database import SessionLocal
from app.models.models import Member
from app.core.security import hash_password
db = SessionLocal()
m = Member(
    nom='Nom',
    prenom='Prénom',
    email='admin@lateb.eu',
    roles=['staff', 'bureau'],
    hashed_password=hash_password('motdepasse')
)
db.add(m)
db.commit()
print('Membre créé, id =', m.id)
"
```

---

## Build des images Docker (production)

Remplacez `your-registry` par votre registry Docker Hub / GitHub Container Registry / etc.

```bash
# Backend
docker build -t your-registry/salope-backend:latest ./backend

# Frontend
docker build -t your-registry/salope-frontend:latest ./frontend

# Push
docker push your-registry/salope-backend:latest
docker push your-registry/salope-frontend:latest
```

---

## Déploiement sur K3s (OVH VPS)

### 1. Préparer les secrets

Éditez `k8s/secret.yaml` pour remplacer les valeurs base64 par les vôtres :

```bash
# Exemple de génération
echo -n 'votre-mot-de-passe-postgres' | base64
openssl rand -base64 32 | tr -d '\n' | base64   # pour SECRET_KEY
```

### 2. Adapter la configuration

Dans `k8s/configmap.yaml` et `k8s/ingress.yaml`, remplacez :
- Domaine configuré : `lateb.eu` (frontend sur `planning.lateb.eu`)

Dans `k8s/backend-deployment.yaml` et `k8s/frontend-deployment.yaml`, remplacez :
- `your-registry/salope-backend:latest` → votre image

### 3. Appliquer les manifests

```bash
# Namespace + secrets + config (dans cet ordre)
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/configmap.yaml

# Stockage PostgreSQL
kubectl apply -f k8s/postgres-pvc.yaml
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/postgres-service.yaml

# Migrations (attendre que postgres soit prêt)
kubectl apply -f k8s/migrations-job.yaml
kubectl wait --for=condition=complete job/salope-migrations -n salope --timeout=120s

# Backend
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/backend-service.yaml

# Frontend
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/frontend-service.yaml

# Ingress (Traefik + TLS via cert-manager)
kubectl apply -f k8s/ingress.yaml
```

### 4. Vérification

```bash
kubectl get pods -n salope
kubectl get ingress -n salope
kubectl describe certificate salope-tls -n salope
```

### 5. Créer le premier utilisateur bureau

Depuis un pod backend :

```bash
kubectl exec -it deploy/salope-backend -n salope -- python -c "
from app.database import SessionLocal
from app.models.models import Member
from app.core.security import hash_password
db = SessionLocal()
m = Member(
    nom='Nom',
    prenom='Prénom',
    email='admin@lateb.eu',
    roles=['staff', 'bureau'],
    hashed_password=hash_password('motdepasse')
)
db.add(m)
db.commit()
print('Membre créé, id =', m.id)
"
```

---

## Variables d'environnement backend

| Variable | Description | Défaut |
|---|---|---|
| `DATABASE_URL` | URL PostgreSQL | `postgresql://...` |
| `SECRET_KEY` | Clé JWT (≥ 32 chars) | _à changer_ |
| `ALLOWED_EMAIL_DOMAIN` | Domaine email autorisé | `lateb.eu` |
| `CORS_ORIGINS` | Origins CORS autorisées | `http://localhost:3000` |
| `FUZZY_MATCH_THRESHOLD` | Seuil fuzzy matching (0-100) | `90` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Durée access token | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Durée refresh token | `7` |

---

## Workflow utilisateur

1. **Login** — email + mot de passe (domaine restreint)
2. **Créer un événement** — nom, date, type (Soirée / Afterwork)
3. **Importer le CSV Strawpoll** — résolution automatique des noms via alias + fuzzy matching ; validation manuelle des cas ambigus
4. **Configurer les créneaux** — définir le `max_personnes` par créneau
5. _(Soirée)_ **Désigner les respos bar** — optionnel, dans l'ordre souhaité
6. **Saisir les affinités** — paires de membres qui souhaitent se retrouver ensemble
7. **Générer le planning** — algorithme à escalade automatique
8. **Ajustements manuels** — cliquer sur une cellule pour modifier une affectation
9. **Valider & publier** — incrémente les compteurs `heures_cumulees` et `shifts_respo_bar_cumules`
10. **Exporter en PNG** — image prête à partager

---

## Structure du projet

```
backend/
├── app/
│   ├── main.py              FastAPI app + CORS
│   ├── config.py            Paramètres (pydantic-settings)
│   ├── database.py          SQLAlchemy engine + session
│   ├── models/models.py     Tous les modèles ORM
│   ├── schemas/schemas.py   Schémas Pydantic
│   ├── core/
│   │   ├── security.py      JWT + bcrypt
│   │   └── deps.py          Dépendances FastAPI
│   ├── routers/
│   │   ├── auth.py          /api/auth/*
│   │   ├── members.py       /api/members/*
│   │   ├── events.py        /api/events/* (CRUD, CSV, schedule)
│   │   └── export.py        /api/events/{id}/export-png
│   └── services/
│       ├── csv_import.py    Import Strawpoll + fuzzy matching
│       ├── scheduler.py     Algorithme de génération
│       └── export_img.py    Export PNG Pillow
└── alembic/                 Migrations DB

frontend/
├── src/
│   ├── api/                 Clients axios
│   ├── contexts/            AuthContext
│   ├── pages/               LoginPage, EventsPage, EventDetailPage, MembersPage
│   └── components/
│       ├── events/          CsvImport, SlotConfig, RespoBarConfig, AffinityConfig
│       ├── members/         MemberTable, MemberForm
│       └── planning/        PlanningGrid, WarningsList

k8s/                         Manifests K3s
```