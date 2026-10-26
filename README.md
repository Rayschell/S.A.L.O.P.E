# S.A.L.O.P.E

Application de gestion de plannings de shifts pour bar associatif (LATEB).

Elle couvre le cycle complet d'un événement : import des disponibilités depuis Strawpoll, génération optimisée du planning (solveur CP-SAT), ajustements manuels, publication avec comptabilisation des heures, export PNG — plus le suivi des statistiques de staff par membre et par saison (mandat de bureau).

---

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Développement local](#développement-local)
- [Tests & CI](#tests--ci)
- [Workflow utilisateur](#workflow-utilisateur)
- [Formulaire public de disponibilités](#formulaire-public-de-disponibilités)
- [Génération de planning](#génération-de-planning)
- [Saisons (mandats de bureau)](#saisons-mandats-de-bureau)
- [Page Membres](#page-membres)
- [Import de planning historique](#import-de-planning-historique)
- [Modèle de données (résumé)](#modèle-de-données-résumé)
- [Déploiement en production (K3s)](#déploiement-en-production-k3s)
- [Variables d'environnement backend](#variables-denvironnement-backend)
- [Structure du projet](#structure-du-projet)

---

## Fonctionnalités

- **Événements** : création, édition, duplication (créneaux + exclusions copiés), suppression. Deux types : `afterwork` et `soiree`.
- **Import CSV Strawpoll** : parsing de l'export, résolution des noms par alias + fuzzy matching, validation manuelle des cas ambigus.
- **Formulaire public de disponibilités** : lien `/dispo/{token}` partageable, sans compte — chaque membre saisit son nom et coche dispo / peut-être / pas dispo par créneau ; toggle d'ouverture + date limite optionnelle ; noms non reconnus mis en attente de validation bureau.
- **Créneaux manuels** : générateur façon Strawpoll intégré à la création d'événement (plage horaire découpée en pas fixes, passage minuit géré, prévisualisation du nombre de créneaux) + suppression par créneau — plus besoin de CSV pour lancer un événement.
- **Génération de planning** : solveur CP-SAT (OR-Tools) avec contraintes dures et pénalités pondérées ; mode « propositions » pour comparer plusieurs variantes avant d'appliquer ; exclusion de membres de la génération.
- **Ajustements manuels** : modification/suppression d'affectations cellule par cellule dans la grille.
- **Publication / dépublication** : la publication incrémente les compteurs de stats (`fois_staffe`, respo bar) ; la dépublication les décrémente proprement.
- **Warnings (W1–W7)** : anomalies détectées sur le planning généré (créneau sans respo bar, sous-staffing, absence de membre bureau, dépassement de quota, « peut-être » utilisé, affinité insatisfaite, longue pause).
- **Export PNG** : image du planning prête à partager.
- **Saisons** : découpage des stats par mandat de bureau, avec saison en cours sans date de fin.
- **Membres** : CRUD, rôles (`staff` / `bureau`), alias de noms, fusion de doublons, remise à zéro des compteurs, stats détaillées et timeline par membre, badge « Bien membré·e·s ».
- **Import historique** : OCR d'anciennes grilles de planning (captures Excel/Sheets) pour comptabiliser rétroactivement les heures.

---

## Architecture

```
frontend/   React 18 + Vite — dev :3000, servi par nginx en prod
backend/    Python 3.12 + FastAPI + SQLAlchemy + Alembic — API sous /api/*
k8s/        Manifests Kubernetes pour K3s (OVH VPS)
.github/    CI GitHub Actions (build frontend + pytest backend)
```

Auth par JWT (access + refresh token) ; les mutations sensibles exigent le rôle `bureau`. Le vocabulaire métier est en français dans le code (`creneau`, `heure_relative`, `fois_staffe`, `membre_id`…).

---

## Développement local

Prérequis : Docker avec le plugin `docker compose` (v2+).

```bash
# Premier lancement — build les images et applique les migrations
docker compose up --build

# Lancements suivants
docker compose up
```

| Service | URL | Hot-reload |
|---|---|---|
| Frontend (Vite) | http://localhost:3000 | Oui — `frontend/src/` monté en live |
| Backend (uvicorn) | http://localhost:8000 | Oui — `backend/app/` monté en live |
| API docs (Swagger) | http://localhost:8000/docs | — |
| PostgreSQL | localhost:**5433** | — |

> Le port PostgreSQL est exposé sur **5433** côté hôte (5432 est généralement occupé par un Postgres local). Les conteneurs communiquent entre eux via le réseau Docker interne sur le port 5432.
>
> Les migrations Alembic sont appliquées automatiquement au démarrage via le service one-shot `migrations`.

### Commandes utiles

```bash
# Logs d'un service
docker compose logs -f backend
docker compose logs -f frontend

# Relancer les migrations manuellement (ex. après une nouvelle migration)
docker compose run --rm migrations

# Shell dans un conteneur
docker compose exec backend bash
docker compose exec postgres psql -U baruser -d salope

# Connexion Postgres depuis l'hôte
psql -h localhost -p 5433 -U baruser salope

# Arrêter (les données postgres sont conservées) / tout supprimer
docker compose down
docker compose down -v
```

### Premier utilisateur bureau

Après le premier `docker compose up` :

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

## Tests & CI

La suite de tests backend vit dans `backend/tests/` (pytest + TestClient FastAPI). Elle utilise une base dédiée `salope_test` créée automatiquement sur le Postgres de dev.

```bash
# Avec la stack docker compose démarrée (Postgres accessible sur :5433) :
docker compose run --rm --no-deps \
  -v ./backend/tests:/app/tests \
  -v ./backend/app:/app/app \
  -v ./backend/requirements-dev.txt:/app/requirements-dev.txt \
  -e TEST_DATABASE_URL=postgresql://baruser:barpassword@postgres:5432/salope_test \
  backend bash -c "pip install -q -r requirements-dev.txt && pytest tests -v"
```

La CI GitHub Actions (`.github/workflows/ci.yml`) tourne sur chaque push/PR :

- **Frontend build** : `npm ci` + `vite build`
- **Backend tests** : pytest contre un Postgres 16 de service

---

## Workflow utilisateur

1. **Login** — email + mot de passe (domaine restreint, `lateb.eu` par défaut)
2. **Créer un événement** — nom, date, type (Soirée / Afterwork) **et ses créneaux** (générateur façon Strawpoll : plage horaire + pas + max personnes) — ou **dupliquer** un événement existant
3. **Ajuster les créneaux** — onglet Créneaux : `max_personnes` par créneau, suppression d'un créneau
4. **Collecter les disponibilités** — en partageant le **lien d'inscription public**, ou en important le CSV Strawpoll (les deux passent par la même résolution de noms alias + fuzzy matching ; le CSV crée les créneaux manquants)
5. _(Soirée)_ **Désigner les respos bar** — optionnel, dans l'ordre souhaité
6. **Saisir les affinités** — paires de membres qui souhaitent être ensemble
7. **Générer le planning** — génération directe, ou plusieurs **propositions** comparées côte à côte avant d'en appliquer une ; possibilité d'**exclure des membres** de la génération
8. **Ajustements manuels** — cliquer sur une cellule pour modifier ou retirer une affectation
9. **Publier** — incrémente `fois_staffe` par créneau et `shifts_respo_bar_cumules` (la **dépublication** annule ces compteurs)
10. **Exporter en PNG** — image prête à partager

---

## Formulaire public de disponibilités

Alternative à l'import CSV : un lien `https://…/dispo/{token}` partageable aux membres (Discord, WhatsApp…), **sans compte ni connexion** — l'équivalent interne d'un Strawpoll.

- **Côté membre** : saisir prénom + nom, cocher dispo ✅ / peut-être 🤷 / pas dispo ❌ pour chaque créneau, envoyer. Re-soumettre avec le même nom **écrase** les réponses précédentes.
- **Côté bureau** (onglet Disponibilités de l'événement) : le lien est **permanent** (token généré à la création de l'événement) ; le toggle « inscriptions ouvertes » contrôle uniquement si le formulaire peut être rempli, avec date limite optionnelle. Les créneaux se définissent **dès la création de l'événement** (générateur façon Strawpoll : plage horaire découpée en pas de 30 min à 2 h) — le CSV n'est plus un prérequis.
- **Résolution des noms** : un nom reconnu (alias ou fuzzy ≥ seuil) alimente directement les `availabilities` ; un nom inconnu est mis **en attente** et le bureau le résout depuis le même onglet (membre existant / créer / ignorer), via la même modale que l'import CSV.
- Endpoints publics sous `/api/public/polls/{token}` (GET infos + POST soumission), sans authentification ; le token non devinable fait office d'accès, comme un lien Strawpoll.

---

## Génération de planning

Le planning est résolu par un solveur **CP-SAT (OR-Tools)** :

- **Contrainte dure** : `max_personnes` par créneau.
- **Pénalités pondérées** : créneau sans respo bar, sans membre bureau, sous-staffé ; dépassement du quota de base (2 h) ; utilisation d'un « peut-être » ; affinité insatisfaite ; pauses longues entre deux blocs.
- **Limite de résolution** : 10 s.

Deux modes :

- `POST /api/events/{id}/generate` — résout et écrit les affectations en base.
- `POST /api/events/{id}/generate-proposals` puis `POST /api/events/{id}/apply-proposal` — calcule plusieurs variantes **sans rien écrire**, l'utilisateur choisit celle à appliquer.

Les membres exclus (`PUT /api/events/{id}/exclusions`) sont ignorés par le solveur. Après résolution, les **warnings W1–W7** listent les anomalies restantes et sont conservés sur l'événement (`last_warnings`).

| Code | Anomalie |
|---|---|
| W1 | Créneau sans respo bar (soirée uniquement) |
| W2 | Créneau sous-staffé |
| W3 | Créneau sans membre bureau |
| W4 | Membre au-delà du quota de base (2 h) |
| W5 | Membre placé sur un « peut-être » |
| W6 | Affinité insatisfaite |
| W7 | Longue pause (≥ 3 h) entre deux blocs d'un même membre |

---

## Saisons (mandats de bureau)

Une **saison** correspond à un mandat de bureau (souvent avril → avril). Elle sert de fenêtre de filtrage pour les statistiques : le filtre de la page Membres, le badge ✦ et les histogrammes se calculent sur la saison sélectionnée. Sans saison sélectionnée, les stats couvrent tout l'historique.

- CRUD réservé au bureau, via la modale « Saisons » de la page Membres (`/api/saisons`).
- **Saison en cours** : laisser la date de fin **vide** — la saison couvre alors tout événement à partir de sa date de début, sans borne haute. On pourra la clôturer plus tard en lui donnant une date de fin.
- Par défaut, la page Membres sélectionne la saison contenant la date du jour.

---

## Page Membres

- Tableau de tous les membres avec rôles modifiables (bureau uniquement) et filtre par saison.
- **Alias** : noms alternatifs par membre, utilisés par le fuzzy matching des imports.
- **Fusion de doublons** : `POST /api/members/{id}/merge` réattribue dispos, affectations, stats, respos, affinités et alias du doublon vers le membre cible.
- **Remise à zéro des compteurs** : par membre ou pour tous (bureau).
- **« Voir stats »** ouvre un panneau par membre :
  - Heures staffées : total afterworks, total soirées, total cumulé
  - **Badge « Bien membré·e·s » (✦)** : atteint à **≥ 10 h** cumulées sur les événements publiés, avec barre de progression
  - Histogrammes de staffing par heure relative (afterwork / soirée)
  - Histogramme respo bar (membres bureau uniquement)
  - Timeline chronologique des événements publiés

---

## Import de planning historique

Fonctionnalité réservée aux membres **bureau**, accessible via « Import historique » dans la barre latérale.

Permet de comptabiliser rétroactivement les heures d'anciens plannings qui n'existent que sous forme d'image (capture d'écran d'une grille Excel ou Google Sheets). Ces heures alimentent les statistiques et le badge « Bien membré·e·s » exactement comme un événement créé normalement.

### Format d'image attendu

| Zone | Description |
|---|---|
| Ligne d'en-tête | Fond bleu, cellules avec les créneaux `HH:MM - HH:MM` |
| Colonne gauche | Noms des membres |
| Cellules vertes | Affectation **staff** |
| Cellules rouges | Affectation **respo bar** |
| Dernière ligne | « Total ✓ voix » — ignorée automatiquement |

### Déroulement

**Étape 1 — Métadonnées + image** : remplir nom, date et type de l'événement, déposer l'image (PNG, JPEG ou WEBP), cliquer sur **Analyser l'image**. Le backend détecte la grille (en-tête bleue, séparateurs), OCR-ise horaires et noms, détecte les couleurs des cellules, et fuzzy-matche les noms contre les membres en base.

**Étape 2 — Validation de la prévisualisation** :
- **Bandeau orange** : noms non reconnus — choisir un membre existant, en créer un, ou ignorer la ligne.
- **Pills de créneaux** : heures éditables en cas d'erreur OCR.
- **Grille** : cliquer sur une cellule pour cycler son état (vide → Staff → Respo bar → vide).

**Étape 3 — Import** : crée l'`Event` publié, les `Slot`s (`max_personnes = 99`), les `Assignment`s, et incrémente les compteurs de stats.

### Limites connues

- L'OCR peut mal lire les noms avec accents ou tirets — la prévisualisation permet de corriger avant de valider.
- L'image doit être propre (pas de rotation ni de flou). Les exports directs Excel/Google Sheets fonctionnent bien.
- Tesseract est inclus dans l'image backend (`tesseract-ocr tesseract-ocr-fra`).

---

## Modèle de données (résumé)

### Member

| Colonne | Type | Description |
|---|---|---|
| `nom`, `prenom`, `email` | String | Identité |
| `roles` | String[] | `staff` et/ou `bureau` |
| `shifts_respo_bar_cumules` | Integer | Nombre de fois respo bar sur événements publiés |

### Event → Slot → Availability / Assignment

- `Event` : nom, date, type, statut (`brouillon` / `publie`), membres exclus, derniers warnings.
- `Slot` (créneau) : bornes horaires, `heure_relative` (index 0, 1, 2…), `max_personnes`.
- `Availability` : disponibilité d'un membre sur un créneau (`yes` / `no` / `maybe`), unique par (événement, membre, créneau).
- `Assignment` : affectation `staff` ou `respo_bar`, de source `auto` (solveur) ou `manuel`.

### Saison

| Colonne | Type | Description |
|---|---|---|
| `nom` | String | ex. « Mandat 2026-2027 » |
| `date_debut` | Date | Début du mandat |
| `date_fin` | Date, nullable | Fin du mandat — **NULL = saison en cours** (pas de borne haute) |

### StatsMemberHeureRelative

Statistiques par membre × type d'événement × heure relative (index du créneau) : `fois_disponible`, `fois_staffe`.

### Badge « Bien membré·e·s »

Un membre atteint le statut **Bien membré·e·s** dès qu'il cumule **≥ 10 heures** de staff sur l'ensemble des événements publiés (afterworks + soirées confondus). Le total est calculé à la volée à partir des assignments publiés.

---

## Déploiement en production (K3s)

Prérequis : kubectl configuré sur le cluster, cert-manager installé (avec un `ClusterIssuer` nommé `letsencrypt-prod`).

### 1. Build & push des images

Remplacez `your-registry` par votre registry (Docker Hub, GHCR…) :

```bash
docker build -t your-registry/salope-backend:latest ./backend
docker build -t your-registry/salope-frontend:latest ./frontend
docker push your-registry/salope-backend:latest
docker push your-registry/salope-frontend:latest
```

### 2. Préparer les secrets

Éditez `k8s/secret.yaml` pour remplacer les valeurs base64 :

```bash
echo -n 'votre-mot-de-passe-postgres' | base64
openssl rand -base64 32 | tr -d '\n' | base64   # pour SECRET_KEY
```

Ajoutez aussi le client OAuth Google (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`) : dans la console Google Cloud, déclarez l'URI de redirection `https://planning.lateb.eu/api/auth/google/callback`. Ne commitez pas ces valeurs ; le plus simple est de les poser après coup :

```bash
kubectl patch secret salope-secret -n salope -p '{"stringData":{"GOOGLE_CLIENT_ID":"...","GOOGLE_CLIENT_SECRET":"..."}}'
```

### 3. Adapter la configuration

- `k8s/configmap.yaml` et `k8s/ingress.yaml` : domaine (`lateb.eu`, frontend sur `planning.lateb.eu`), `GOOGLE_REDIRECT_URI` et `BUREAU_EMAILS`.
- `k8s/backend-deployment.yaml` et `k8s/frontend-deployment.yaml` : `your-registry/salope-*:latest` → vos images.

### 4. Appliquer les manifests

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

# Backend + frontend
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/backend-service.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/frontend-service.yaml

# Ingress (Traefik + TLS via cert-manager)
kubectl apply -f k8s/ingress.yaml
```

### 5. Vérification

```bash
kubectl get pods -n salope
kubectl get ingress -n salope
kubectl describe certificate salope-tls -n salope
```

### 6. Premier utilisateur bureau

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
│   │   └── deps.py          Dépendances FastAPI (auth, rôle bureau)
│   ├── routers/
│   │   ├── auth.py               /api/auth/*
│   │   ├── members.py            /api/members/*  (CRUD, alias, merge, stats, timeline)
│   │   ├── events.py             /api/events/*   (CRUD, CSV, generate, proposals, publish)
│   │   ├── saisons.py            /api/saisons/*  (mandats de bureau)
│   │   ├── public.py             /api/public/polls/* (formulaire public, sans auth)
│   │   ├── export.py             /api/events/{id}/export-png
│   │   └── import_historique.py  /api/import-historique/* (preview + commit)
│   └── services/
│       ├── csv_import.py         Import Strawpoll + fuzzy matching
│       ├── public_poll.py        Formulaire public (soumission, pending, résolution)
│       ├── scheduler.py          Génération de planning (solveur CP-SAT OR-Tools)
│       ├── export_img.py         Export PNG (Pillow)
│       └── historical_img_import.py  Parsing image + OCR (pytesseract)
├── tests/                   Suite pytest (CRUD, scheduler, publication, saisons, poll public…)
└── alembic/versions/        Migrations 001 → 008

frontend/
├── src/
│   ├── api/                 Clients axios (auth, events, members, saisons, historique)
│   ├── contexts/            AuthContext
│   ├── pages/               LoginPage, EventsPage, EventDetailPage, MembersPage,
│   │                        HistoricalImportPage, PublicPollPage (/dispo/:token)
│   └── components/
│       ├── events/          CsvImport, PublicPollAdmin, SlotConfig, RespoBarConfig, AffinityConfig
│       ├── members/         MemberTable, MemberForm, MemberStats, SaisonManager
│       ├── planning/        PlanningGrid, PlanningLegend, WarningsList
│       └── layout/          Navbar, Sidebar

k8s/                         Manifests K3s (namespace: salope)
.github/workflows/ci.yml     CI — build frontend + pytest backend
```
