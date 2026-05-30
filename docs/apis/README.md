# Documentation des API — `episode_id_map`

Livrable de l'**ÉTAPE 1** du `SYSTEM_PROMPT.md` : documenter les sources **avant tout
code**. Une fiche par source, validée par **appels réels** (cas de référence Frieren).
**5 sources** (AniDB ajoutée le 2026-05-30, cf. `anidb.md`) :

- [`jikan.md`](./jikan.md) — MAL via Jikan (`source="MAL"`)
- [`tmdb.md`](./tmdb.md) — The Movie Database (`source="TMDB"`)
- [`simkl.md`](./simkl.md) — SIMKL (`source="SIMKL"`) · **pivot cross-ID principal**
- [`tvdb.md`](./tvdb.md) — TheTVDB v4 (`source="TVDB"`) · pivot secondaire
- [`anidb.md`](./anidb.md) — AniDB · **référentiel de la grille d'épisodes + pivot `aid`** (validé par appel réel)

Clés API : voir [`../../.env.example`](../../.env.example). Jikan ne nécessite pas de clé.
AniDB exige un **client enregistré** (nom **sans tiret** : `episodeidmap`) et a une
**politique de ban agressive** (≤1 req/2s, cache obligatoire) → voir `anidb.md` §1.

---

## Finalité (rappel)

La table alimente un **bot Discord** (orchestration **n8n + LLM**, base **Supabase**) qui
annonce les sorties d'anime traduites. Le bot reçoit un épisode **depuis une source** et
doit savoir s'il a **déjà annoncé CET épisode réel**, quelle que soit la source.
➡ **`episode_absolute` est la clé anti-doublon** : la table sert à résoudre
`(source + ids) → episode_absolute`.

**Coûts d'erreur asymétriques** : ne pas relier deux vues d'un même épisode = **doublon
d'annonce** ; relier à tort deux épisodes distincts = **annonce manquée**. D'où la règle
du `SYSTEM_PROMPT` : **valider toute correspondance avant de l'écrire**.

---

## Tableau des ID croisés (qui expose quoi)

| Source | id natif | MAL | AniDB | TMDB | TVDB | IMDB | AniList | Niveau |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|---|
| **Jikan (MAL)** | mal_id | ✔ (lui) | ✔ (URL `/external`) | – | – | – | – | œuvre |
| **SIMKL** | simkl | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | **œuvre** |
| **SIMKL** (épisode) | simkl_id | – | ~ | – | ✔ `{s,e}` | – | – | **épisode** |
| **TMDB** | tmdb_id | – | – | ✔ (lui) | ✔ | ✔ | – | œuvre **+ épisode** |
| **TVDB** | series id | – | – | ✔ (série) | ✔ (lui) | ✔ (série) | – | œuvre (épisode : ~vide) |
| **AniDB** | aid / epid | ✔ (resource 2) | ✔ (lui) | – | – | – | – | œuvre **+ épisode** (epid/epno/airdate) |

Légende : ✔ exposé · ~ partiel/non garanti · – absent.

**Lectures clés :**
- **SIMKL au niveau œuvre = le hub** : un seul appel donne mal+anidb+tmdb+tvdb+imdb+anilist.
- **MAL n'expose que AniDB** (extrait de l'URL du lien externe) → AniDB est la porte
  d'entrée de MAL dans le graphe.
- **AniDB = grille d'épisodes de référence** : `epid` stable + `epno` typé + `airdate` +
  titres multilingues (FR). C'est la numérotation que **MAL et SIMKL suivent** → ancrage
  épisode-à-épisode. ⚠ AniDB n'expose **ni TMDB ni TVDB**, et un `aid` peut regrouper
  **plusieurs entrées MAL** (Frieren `aid=17617` → MAL `52991` TV **+** `56885` ONA).
- **Le seul cross-id fiable au niveau ÉPISODE vers TMDB/TVDB** :
  - `TMDB …/episode/{e}/external_ids` → `tvdb_id` (id épisode TVDB) — **vérifié** ;
  - `SIMKL /anime/episodes` → `tvdb:{season,episode}` par épisode AniDB.
- **TVDB remoteIds épisode = souvent vide** → toujours croiser **vers** TVDB (TMDB→TVDB,
  SIMKL→TVDB), jamais en partant de l'épisode TVDB.

---

## Stratégie de cross-ID (sans agrégateur tiers)

`episode_absolute` (UUIDv4 **persisté**) = un par épisode réel ; chaque ligne source y
pointe. Trois chemins complémentaires, **chacun validé avant écriture** :

1. **Pivot SIMKL — niveau œuvre**
   `MAL → AniDB (Jikan /external) → SIMKL /search/id?anidb= → {mal, tmdb, tvdb, imdb}`.
   Établit que ces œuvres parlent de la même série.

2. **Pivot SIMKL — niveau épisode**
   `SIMKL /anime/episodes/{id}` → pour chaque épisode AniDB, `tvdb:{season,episode}`.
   Relie l'épisode MAL/AniDB à la grille saison TVDB.

3. **Direct TMDB ↔ TVDB ↔ IMDB**
   `TMDB external_ids` au niveau **série** et **épisode** ; `TVDB remoteIds` au niveau
   **série** ; `TVDB /search/remoteid` pour l'inverse.

4. **Ancrage des épisodes via AniDB** (référentiel)
   `AniDB request=anime&aid=` → épisodes `type=1` : `epid`/`epno`/`airdate`. C'est la
   grille que MAL & SIMKL réexposent → jointure par `epno` (1:1 MAL) avec **fallback
   `airdate`** quand les numéros divergent (films, fusions de saisons TMDB).

```
            ┌──────────────┐
   MAL ──── AniDB ───────► SIMKL ──────► TMDB ──(episode external_ids)──► TVDB
 (Jikan   (lien      │  (hub: tous     (tvdb_id série+épisode)        (id épisode
  /external) externe)│   les ids)                                       stable)
                     │     │
   grille épisodes ──┘     └─ par épisode: tvdb:{season,episode}
   (epid/epno/airdate
    = ancrage de référence)
```

---

## Cas de référence (à valider en phase code)

| Cas | mal_id | tmdb_id | tvdb_id | aid | Particularité |
|---|---|---|---|---|---|
| **Frieren** | 52991 | 209867 | 424536 | 17617 | MAL S1=28 ép. ; TMDB « Season 1 »=**38** (fusion 28+10) ; TVDB `official` par saison + specials ; AniDB 28 ép. `type=1`. Tests : **fusion de saisons** + **1 `aid` → 2 mal_id** (52991 TV + 56885 ONA). |
| **One Piece** | 21 | (TV) | — | — | 1 entrée MAL **continue** (1100+) ↔ N saisons TMDB. Test **numérotation absolue** (TVDB `absolute`). |
| **Un film** | — | (movie) | — | — | Doit rester **œuvre distincte** d'une série même `tmdb_id` ; `extra.type="movie"`. |

---

## Conventions de remplissage des colonnes (figées)

`uuid` et `episode_absolute` = UUIDv4 **persistés** (jamais dérivés). `id_franchise` =
**toujours NULL**. `id_season` NULL pour MAL/SIMKL/AniDB → contrainte UNIQUE
`(source, id_series, id_season, id_episode)` à déclarer **`NULLS NOT DISTINCT`** (PG15+)
pour garantir l'idempotence.

**Le projet compte 5 sources** : MAL, SIMKL, TMDB, TVDB **et AniDB** (décision
2026-05-30). AniDB écrit ses lignes **et** sert d'ancrage d'épisodes (epid/epno/airdate).

> **`extra` = strict minimum utile au mapping.** Il ne contient **que** le qualificatif de
> numérotation/type que les colonnes figées ne portent pas (`type` tv/movie pour TMDB,
> `season_type` pour TVDB, `epno_type` pour AniDB) — `NULL` quand il n'y en a pas. Les
> **cross-ids** (tmdb/tvdb/anidb/mal/imdb, ids d'épisode, titres, dates) sont utilisés
> **transitoirement à l'ingestion** pour calculer/valider l'`episode_absolute`, **pas
> persistés** ici : une fois le lien fait, chaque source pointe le même `episode_absolute`.

| Source | `id_series` | `id_season` | `id_episode` | `extra` |
|---|---|---|---|---|
| **MAL** | mal_id | `NULL` | n° d'épisode (mal_id de l'épisode) | `NULL`                                                               |
| **TMDB** | tmdb_id | saison réelle (`0`=specials) | episode_number réel | `{type:"tv"\|"movie"}`                                               |
| **SIMKL** | simkl id | `NULL` | n° SIMKL/AniDB | `NULL`                                                               |
| **TVDB** | series id | seasonNumber (`official`) | number (`official`) | `{season_type:"official"\|"absolute"}` |
| **AniDB** | aid | `NULL` | `epno` (type=1 ; specials préfixés `S1`/`C1`/`T1`) | `{epno_type}` |
