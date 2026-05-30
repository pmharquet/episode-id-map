# SIMKL — `source = "SIMKL"` · **pivot cross-ID principal**

> API officielle, REST, JSON. Base URL : `https://api.simkl.com`.
> Validé par appels réels (cas Frieren, `simkl_id=1990194`) sauf mention « ⚠ ».
> SIMKL indexe l'anime via **AniDB** ; c'est le hub qui relie toutes les autres sources.

## 1. Auth & quotas

- **Clé requise** : en-tête **`simkl-api-key: <client_id>`** (le `client_id` de l'app
  créée sur `simkl.com/settings/developer`). Le `client_id` peut aussi passer en query
  `?client_id=`. Pas d'OAuth nécessaire pour la lecture publique (lookup, summary,
  episodes) ; OAuth seulement pour les données utilisateur (sync/scrobble).
- **Rate limit** : non strictement publié. Rester raisonnable + retry/backoff `429`/`5xx`.
- **Condition d'usage** : un lien retour vers `simkl.com` est requis dans l'app finale ;
  ne pas utiliser SIMKL comme simple proxy de métadonnées TMDB/TVDB (les récupérer à la
  source). Pour nous, SIMKL sert au **cross-ID**, usage conforme.
- Images : chemins relatifs `posters/`, `episodes/` → préfixer par `https://simkl.in/`.

## 2. Endpoints au niveau ÉPISODE / lookup

| Endpoint | Usage |
|---|---|
| `GET /search/id?{service}={id}` | **Lookup par id externe** → Standard Media Object. |
| `GET /anime/{id}?extended=full` | Fiche anime + **bloc `ids` complet** (tous cross-ids). |
| `GET /anime/episodes/{id}` | **Liste des épisodes** d'un anime (numérotation AniDB). |
| `GET /tv/{id}?extended=full` | Idem pour une série non-anime. |
| `GET /tv/episodes/{id}` | Épisodes d'une série TV. |

**`/search/id` — services acceptés** : `simkl, imdb, tvdb, tmdb, mal, anidb, anilist,
hulu, netflix, crunchyroll`. Pour `tmdb`, ajouter `&type=show|anime|movie`. Tous les
autres paramètres peuvent être vides si un id est fourni. **Validé** : `?anidb=17617` et
`?mal=52991` renvoient tous deux la même œuvre `simkl=1990194`.

**Numérotation** : SIMKL suit **AniDB** → numérotation **plate par entrée** (`episode`
= 1, 2, 3…), proche de MAL, **différente** de la grille saison TMDB/TVDB.

## 3. ID croisés disponibles — **le cœur du pivot**

`GET /anime/1990194?extended=full` → bloc `ids` (réel, Frieren) :
```json
{
  "title": "Sousou no Frieren",
  "type": "anime",
  "anime_type": "tv",
  "total_episodes": 28,
  "ids": {
    "simkl": 1990194,
    "slug": "sousou-no-frieren",
    "anidb": "17617",
    "mal": "52991",
    "anilist": "154587",
    "kitsu": "46474",
    "imdb": "tt22248376",
    "tvdb": "424536",
    "tmdb": "209867",
    "tvdbslug": "sousou-no-frieren",
    "trakttvslug": "frieren-beyond-journey-s-end"
  }
}
```
➡ **Niveau œuvre** : SIMKL donne d'un coup `mal, anidb, anilist, tmdb, tvdb, imdb`.
C'est la jointure la plus économique pour relier les 4 sources du projet.

**Niveau épisode** — `GET /anime/episodes/1990194` (réel, extrait) :
```json
[
  {
    "title": "The Journey's End",
    "description": "The world celebrates the Demon King's defeat ...",
    "episode": 1,
    "type": "episode",
    "aired": true,
    "date": "2023-09-29T23:00:00+09:00",
    "img": "14/146256642a3afd9c8e",
    "ids": { "simkl_id": 10972280 },
    "tvdb": { "season": 1, "episode": 2 }
  }
]
```
➡ **Niveau épisode**, le seul cross-id est `ids.simkl_id`, **MAIS** chaque épisode porte
un mapping **`tvdb: {season, episode}`** → relie directement l'épisode AniDB/SIMKL (donc,
par numérotation, l'épisode MAL) à la **grille saison/épisode TVDB**. Pont épisode-à-
épisode exploitable. ⚠ Pas de `tmdb` au niveau épisode → pour atteindre TMDB, chaîner
`SIMKL.tvdb(s,e) → TVDB → TMDB.external_ids`, ou via la date de diffusion.

## 4. Pièges de modélisation

- **Numérotation AniDB** : peut diverger de TMDB/TVDB (specials, ordres). Le champ
  `tvdb:{season,episode}` par épisode est l'outil de réconciliation fourni par SIMKL.
  ⚠ Il peut être **absent ou décalé** sur certains épisodes (specials, films) → si absent,
  ne rien inventer (laisser le lien à NULL).
- **anime vs tv vs movie** : un anime-film a `anime_type` ≈ `movie` ; utiliser les
  endpoints `/anime/...`. Les séries non-anime passent par `/tv/...`.
- **Specials** : présents avec leur propre numérotation ; les traiter à part.
- **Champs ids en string** : `"mal":"52991"` est une **chaîne** côté SIMKL → caster.

## 5. Exemple JSON réel — `GET /search/id?anidb=17617` (Frieren)

```json
[
  {
    "type": "anime",
    "title": "Sousou no Frieren",
    "year": 2023,
    "status": "ended",
    "total_episodes": 28,
    "anime_type": "tv",
    "ids": { "simkl": 1990194, "slug": "sousou-no-frieren" }
  }
]
```
(Avec `?mal=52991`, réponse identique + un bloc `"mal": {"id":52991,"type":"tv"}`.)

## 6. Conventions de remplissage (à figer — proposition)

| Colonne | Valeur |
|---|---|
| `source` | `"SIMKL"` |
| `id_series` | `simkl` id (ex. `1990194`) |
| `id_season` | `NULL` (numérotation AniDB plate, pas de saison interne) |
| `id_episode` | `episode` (n° SIMKL/AniDB, ex. `1..28`) |
| `id_franchise` | `NULL` (toujours) |
| `extra` | `NULL` |

> SIMKL n'a qu'une numérotation plate (AniDB) → aucun qualificatif à porter. C'est pourtant
> le **pivot** : son bloc `ids` complet et le `tvdb:{season,episode}` par épisode sont la
> matière première du mapping, mais consommés **à l'ingestion** pour relier les sources et
> assigner l'`episode_absolute` — **pas persistés** dans `extra`.
