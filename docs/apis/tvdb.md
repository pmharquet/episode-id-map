# TheTVDB v4 — `source = "TVDB"` · pivot cross-ID secondaire

> API officielle v4, REST, JSON. Base URL : `https://api4.thetvdb.com/v4`.
> Validé par appels réels (cas Frieren, `series_id=424536`) sauf mention « ⚠ ».

## 1. Auth & quotas

- **Clé requise** : `TVDB_API_KEY`. Auth en 2 temps :
  1. `POST /login` avec body `{"apikey":"<clé>"}` (+ `"pin":"<pin>"` **uniquement** pour
     les clés « user-supported » ; notre clé est `community_supported:false` → **pas de
     pin**) → renvoie `{"data":{"token":"<JWT>"}}`.
  2. Joindre `Authorization: Bearer <JWT>` à chaque appel.
- **Durée du token** : ~1 mois (re-login si expiré).
- **Quota** : large (token observé : `hits_per_day` = 100 000 000). Prévoir tout de même
  retry/backoff `429`/`5xx`.
- ⚠ **Encodage** : beaucoup de titres en japonais ; bien décoder en UTF-8 (les `name`
  série/épisode peuvent être en `jpn`). Utiliser `?lang=eng` ou les traductions.

## 2. Endpoints au niveau ÉPISODE

| Endpoint | Usage |
|---|---|
| `POST /login` | Auth → Bearer token. |
| `GET /series/{id}/extended` | Fiche série + `seasons[]`, `remoteIds[]` (voir §3). |
| `GET /series/{id}/episodes/{season-type}?page=N` | **Liste paginée des épisodes** selon l'ordre. |
| `GET /series/{id}/episodes/{season-type}/{lang}` | Idem + traductions (`eng`, `fra`…). |
| `GET /seasons/{id}/extended` | Détail d'une saison. |
| `GET /episodes/{id}/extended` | Détail d'un épisode + `remoteIds[]`. |
| `GET /search/remoteid/{id}` | **Lookup par id externe** (imdb, tmdb…) → série/épisode. |
| `GET /sources/types` | Référentiel des `type` de `remoteIds`. |

**`{season-type}`** (validé sur Frieren, `seasons[].type.type`) :
- `official` = **Aired Order** (ordre de diffusion, **par saison** ; le plus utilisé) ;
- `absolute` = **Absolute Order** (numérotation continue, utile type One Piece) ;
- aussi `default`, `dvd`, `alternate` selon les séries.

**Numérotation** : `seasonNumber` + `number` (par saison) en `official` ; **numéro
continu** en `absolute`. ⚠ La liste `official` **inclut la saison 0 (specials)** →
**filtrer par `seasonNumber`** (Frieren : ~66 entrées renvoyées toutes saisons + specials
confondues). Chaque épisode a un **id TVDB stable** (`episodes[i].id`).

## 3. ID croisés disponibles

`remoteIds[] = { id, type, sourceName }` où `type` est un entier décrit par
`GET /sources/types`. **Niveau série** — `GET /series/424536/extended` (réel, extrait) :
```json
"remoteIds": [
  { "id": "tt22248376", "type": 2,  "sourceName": "IMDB" },
  { "id": "209867",      "type": 12, "sourceName": "TheMovieDB.com" },
  { "id": "Q115792176",  "type": 18, "sourceName": "Wikidata" },
  { "id": "69956",       "type": 19, "sourceName": "TV Maze" }
]
```
➡ **Niveau série, TVDB→TMDB et TVDB→IMDB sont disponibles** (`type 12` = TMDB série,
`type 2` = IMDB). Mapping `type` utile (extrait de `/sources/types`) :

| type | sourceName | slug |
|---|---|---|
| 2 | IMDB | `imdb` |
| 10 | TheMovieDB.com (movie) | `tmdb` |
| 12 | TheMovieDB.com (tv) | `tmdbtv` |
| 13 | EIDR | `eidr` |
| 18 | Wikidata | `wikidata` |
| 19 | TV Maze | `tvmaze` |

- ⚠ **Pas de MAL ni AniDB** dans les `remoteIds` TVDB → pour relier à MAL, passer par
  **SIMKL** (qui, lui, connaît tvdb↔anidb↔mal) ou via TMDB→SIMKL.
- ⚠ **Niveau épisode** : `remoteIds` est **souvent vide** → ne pas compter dessus.
  Le pont fiable au niveau épisode est **TMDB→TVDB** (`tmdb …/episode/{e}/external_ids`
  renvoie le `tvdb_id` de l'épisode) ou **SIMKL→TVDB** (`tvdb:{season,episode}`).

`GET /search/remoteid/{id}` permet l'inverse (ex. `search/remoteid/209867` → série
TVDB `424536`).

## 4. Pièges de modélisation

- **Saison 0 / specials** dans la réponse `official` → filtrer `seasonNumber > 0` pour le
  squelette régulier ; traiter les specials à part.
- **`official` vs `absolute`** : choisir l'ordre selon le besoin d'ancrage. Pour les
  longues séries continues (One Piece), `absolute` peut simplifier l'alignement avec la
  numérotation MAL continue.
- **Pagination** : `?page=N` (commence à 0). Itérer jusqu'à liste vide / `links.next`.
- **Langue** : `name`/`overview` parfois uniquement en `jpn` → demander `/eng` ou lire
  `nameTranslations`.
- **remoteIds épisode vides** : croiser dans le sens TMDB→TVDB (cf. §3).

## 5. Exemple JSON réel — `GET /series/424536/episodes/official` (Frieren, extrait)

```json
{
  "status": "success",
  "data": {
    "series": { "id": 424536, "name": "葬送のフリーレン" },
    "episodes": [
      { "id": 9350138, "seasonNumber": 1, "number": 1,
        "name": "The Journey's End", "aired": "2023-09-29" }
    ]
  },
  "links": { "next": "..." }
}
```
→ L'`id` épisode `9350138` correspond **exactement** au `tvdb_id` renvoyé par TMDB pour
`tv/209867/season/1/episode/1/external_ids` : pont épisode TMDB↔TVDB confirmé.

## 6. Conventions de remplissage (à figer — proposition)

| Colonne | Valeur |
|---|---|
| `source` | `"TVDB"` |
| `id_series` | `series.id` TVDB (ex. `424536`) |
| `id_season` | `seasonNumber` (ordre `official`) ; `0` = specials |
| `id_episode` | `number` (n° dans la saison, ordre `official`) |
| `id_franchise` | `NULL` (toujours) |
| `extra` | `{"season_type":"official"\|"absolute"}` |

> `extra` ne garde que `season_type` : il indique quel ordre `id_season`/`id_episode`
> suivent (`official` par saison vs `absolute` continu, cf. One Piece) — info de mapping
> absente des colonnes. L'`id` d'épisode TVDB et les `remoteIds` série (`tmdb_id`,
> `imdb_id`) servent **à l'ingestion** (pont vers TMDB/IMDB) — **pas persistés** ici.
