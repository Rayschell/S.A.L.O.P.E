Affiche les dernières lignes de logs du service demandé. Service par défaut : `backend`.

Si `$ARGUMENTS` est vide, affiche les 50 dernières lignes du backend :

```
docker compose logs --tail=50 backend
```

Si `$ARGUMENTS` contient un nom de service (`frontend`, `postgres`, `migrations`), affiche les logs de ce service :

```
docker compose logs --tail=50 $ARGUMENTS
```
