# TMDB (The Movie Database) — `source = "TMDB"`

> API officielle, REST, JSON. Base URL : `https://api.themoviedb.org/3`.
> Validé par appels réels (cas Frieren, `tv_id=209867`) sauf mention « ⚠ ».

## 1. Auth & quotas

- **Clé requise** : `TMDB_API_KEY` (clé v3). Deux modes au choix :
  - query param `?api_key=<clé v3>` (le plus simple, utilisé ici) ;
  - header `Authorization: Bearer <API Read Access Token v4>`.
- **Rate limit** : plus de limite stricte documentée (l'ancienne barre ~50 req/s/IP a été
  retirée). Rester raisonnable : prévoir tout de même retry/backoff sur `429`/`5xx`.
- **Langue** : `&language=fr-FR` (ou `en-US`). N'affecte pas les ids.
- **`append_to_response`** : agréger plusieurs sous-ressources en 1 appel (max 20),
  ex. `tv/{id}?append_to_response=external_ids`.
- Dates : `air_date` au format `YYYY-MM-DD`.

## 2. Endpoints au niveau ÉPISODE

| Endpoint | Usage |
|---|---|
| `GET /tv/{id}` | Fiche série : `name`, `seasons[]` (dont S0 specials), `number_of_episodes`. |
| `GET /tv/{id}/season/{n}` | **Liste des épisodes** de la saison `n` (champ `episodes[]`). |
| `GET /tv/{id}/season/{n}/episode/{e}` | Détail d'un épisode. |
| `GET /tv/{id}/season/{n}/episode/{e}/external_ids` | Cross-ids **niveau épisode** (voir §3). |
| `GET /tv/{id}/external_ids` | Cross-ids **niveau série**. |
| `GET /movie/{id}` | Fiche film. |
| `GET /movie/{id}/external_ids` | Cross-ids d'un film (`imdb_id`, `wikidata_id`…). |

**Numérotation** : **par saison** (`season_number` ≥ 1) ; `episode_number` repart à 1
à chaque saison. **Pas de numérotation absolue** native côté TMDB.
Chaque épisode a un **id TMDB stable** (`episodes[i].id`, ex. `3946240`).

## 3. ID croisés disponibles

TMDB expose des cross-ids **structurés**, au niveau série ET épisode — c'est l'un des
meilleurs ponts directs vers TVDB/IMDB.

**Niveau série** — `GET /tv/209867/external_ids` (réel) :
```json
{
  "id": 209867,
  "imdb_id": "tt22248376",
  "tvdb_id": 424536,
  "wikidata_id": "Q115792176",
  "freebase_mid": null, "tvrage_id": null,
  "facebook_id": null, "instagram_id": null, "twitter_id": "Anime_Frieren"
}
```

**Niveau épisode** — `GET /tv/209867/season/1/episode/1/external_ids` (réel) :
```json
{ "id": 3946240, "imdb_id": "tt23861604", "tvdb_id": 9350138, "wikidata_id": null }
```

- **`tvdb_id` (épisode) = l'id épisode TVDB** → **vérifié** : `9350138` est bien
  l'`episodes[0].id` renvoyé par TVDB pour la même série. **C'est le pont épisode↔épisode
  TMDB→TVDB le plus fiable.**
- Pas de `mal_id` ni `anidb_id` chez TMDB → pour rejoindre MAL, passer par
  **SIMKL** (pivot) ou par TVDB.

## 4. Pièges de modélisation

- **Saison 0 = Specials** : `seasons[]` contient une entrée `season_number=0`
  (Frieren : 26 specials). **L'exclure** du squelette d'épisodes « réguliers » ;
  la traiter à part si besoin (ne pas l'ancrer comme une saison normale).
- **Fusion de saisons** : TMDB regroupe parfois plusieurs saisons de diffusion en une
  seule. **Frieren** : « Season 1 » TMDB = **38 épisodes** (28 de la S1 MAL + 10 de la
  suite) → ne JAMAIS supposer « saison TMDB = saison MAL/AniDB ». L'ancrage se fait au
  niveau **épisode absolu**, par date de diffusion / cross-id, pas par n° de saison.
- **Films** : via `/movie/{id}`, univers d'ids distinct des séries. Un film partageant un
  `tmdb_id` numérique avec une série reste une **œuvre distincte** → trancher avec
  `extra.type` (`"movie"` vs `"tv"`, seul champ conservé dans `extra`, cf. §6).
- **TMDB Episode Groups** (`/tv/{id}/episode_groups`) : regroupements alternatifs
  (ordre de diffusion, etc.). **Non utilisés** ici (instables, source de confusion lors
  de la 1re tentative).
- `air_date` peut être `null` (épisode annoncé non daté) → ne pas s'en servir comme clé.

## 5. Exemple JSON réel — `GET /tv/209867/season/1` (Frieren, extrait)

```json
{
  "_id": "...",
  "name": "Season 1",
  "season_number": 1,
  "episodes": [
    { "episode_number": 1,  "name": "The Journey's End", "air_date": "2023-09-29", "id": 3946240 },
    { "episode_number": 38, "name": "A Beautiful Sight",  "air_date": "2026-03-27", "id": 6855843 }
  ]
}
```
→ 38 épisodes dans « Season 1 » (fusion). `seasons[]` au niveau série :
`[(0,"Specials",26), (1,"Season 1",38)]`.

## 6. Conventions de remplissage (rappel SYSTEM_PROMPT)

| Colonne | Valeur |
|---|---|
| `source` | `"TMDB"` |
| `id_series` | `tmdb_id` (ex. `209867`) |
| `id_season` | n° de saison **réel** TMDB (ex. `1`) ; `0` pour les specials |
| `id_episode` | `episode_number` réel (ex. `1..38`) |
| `id_franchise` | `NULL` (toujours) |
| `extra` | `{"type":"tv"\|"movie"}` |

> `extra` ne garde que `type` : il change la sémantique épisode (un `movie` n'a pas de
> saison/épisode) et n'est pas dans les colonnes figées. Le `tvdb_id` épisode et l'`imdb_id`
> restent **précieux comme pont TMDB→TVDB**, mais servent **à l'ingestion** (calcul de
> l'`episode_absolute`) — **pas persistés** ici.
