Applique les migrations Alembic en attente sur la base de développement.

Exécute :

```
docker compose run --rm migrations
```

Affiche le résultat. Si la commande échoue, lis les logs et identifie la cause (conflit de migration, base inaccessible, etc.).
