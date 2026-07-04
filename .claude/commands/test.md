Lance la suite de tests backend dans Docker (la stack docker compose doit être démarrée).

Exécute la commande suivante et affiche le résultat :

```
docker compose run --rm --no-deps \
  -v ./backend/tests:/app/tests \
  -v ./backend/app:/app/app \
  -v ./backend/requirements-dev.txt:/app/requirements-dev.txt \
  -e TEST_DATABASE_URL=postgresql://baruser:barpassword@postgres:5432/salope_test \
  backend bash -c "pip install -q -r requirements-dev.txt && pytest tests -v $ARGUMENTS"
```

Si `$ARGUMENTS` contient un nom de test ou un fichier (ex: `-k test_scheduler` ou `tests/test_slots.py`), passe-le tel quel à pytest.
