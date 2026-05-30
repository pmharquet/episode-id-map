"""Point d'entrée minimal — smoke test de l'infrastructure ÉTAPE 2.

Le projet est encore vide : ce module ne contient aucune logique métier.
Il vérifie seulement que le socle fonctionne — connexion à PostgreSQL et
présence de la table `episode_id_map` — pour valider le Docker.
"""

from __future__ import annotations

import os
import sys

import psycopg


def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL non défini", file=sys.stderr)
        return 1

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.episode_id_map')")
        (table,) = cur.fetchone()
        if table is None:
            print("❌ table episode_id_map absente", file=sys.stderr)
            return 1
        cur.execute("SELECT count(*) FROM episode_id_map")
        (rows,) = cur.fetchone()

    print(f"✅ connexion OK — table {table} présente ({rows} lignes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
