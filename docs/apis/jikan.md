# Jikan (MyAnimeList) — `source = "MAL"`

> Jikan est une API REST **non officielle** qui scrape MyAnimeList (MAL) en temps réel.
> Base URL : `https://api.jikan.moe/v4`. Tout ce qui suit a été **validé par appels réels**
> (cas Frieren, `mal_id=52991`) sauf mention « ⚠ à confirmer ».

## 1. Auth & quotas

- **Aucune clé API.** API publique, pas d'en-tête d'auth.
- **Rate limit** : ~**3 req/s** et **60 req/min** par IP. Dépassement → `429`.
- Réponses cachées côté Jikan (jusqu'à 24 h) → fraîcheur non garantie pour un titre
  modifié récemment sur MAL.
- **Robustesse** : prévoir retry/backoff sur `429` et `5xx`, + un limiteur par hôte
  (`api.jikan.moe`) calé sur 3 req/s.
- Toutes les dates sont en **ISO8601 / UTC**.

## 2. Endpoints au niveau ÉPISODE

| Endpoint | Usage |
|---|---|
| `GET /anime/{id}/episodes?page=N` | Liste **paginée** des épisodes d'un anime. |
| `GET /anime/{id}/episodes/{episode}` | Un épisode précis (détail enrichi : synopsis…). |
| `GET /anime/{id}` | Fiche série (dont `episodes` = nb total, `type`, `aired`). |
| `GET /anime/{id}/full` | Fiche série complète (+ `relations`, `external`, `theme`). |
| `GET /anime/{id}/relations` | Relations **internes MAL** (sequel/prequel/side story…). |
| `GET /anime/{id}/external` | Liens externes (URLs uniquement, voir §3). |

**Pagination** : objet `pagination` racine `{ last_visible_page, has_next_page }`.
Itérer `page=1..last_visible_page` (≈ 100 épisodes/page).

**Schéma de numérotation — POINT CRUCIAL :**
- Dans `/episodes`, le champ **`mal_id` d'un épisode = son numéro d'épisode** (1, 2, 3…),
  **PAS** l'id MAL de la série. La numérotation est **relative à l'entrée MAL**, et
  **recommence à 1** pour chaque entrée (chaque saison MAL est une entrée distincte).
- Conséquence pour notre table : `id_series = mal_id de la SÉRIE` (celui de l'URL,
  ex. `52991`), `id_episode = mal_id de l'ÉPISODE` (le n° relatif, ex. `1..28`).

## 3. ID croisés disponibles

MAL **n'expose AUCUN id structuré** d'autres bases (pas de champ tmdb/tvdb/imdb).
La seule passerelle est `/anime/{id}/external`, qui renvoie des **URLs** (extrait réel
Frieren) :

```json
{"data":[
  {"name":"Official Site","url":"https://frieren-anime.jp/"},
  {"name":"AniDB","url":"https://anidb.net/perl-bin/animedb.pl?show=anime&aid=17617"},
  {"name":"ANN","url":"https://www.animenewsnetwork.com/encyclopedia/anime.php?id=26334"},
  {"name":"Wikipedia","url":"https://en.wikipedia.org/wiki/Frieren#Anime"},
  {"name":"Syoboi","url":"https://cal.syoboi.jp/tid/6776"}
]}
```

- **`AniDB` → l'id AniDB est extractible de l'URL** (`...&aid=17617` → `17617`).
  C'est le **seul cross-id exploitable**, et il est central : **SIMKL indexe l'anime par
  AniDB**. La chaîne de pivot envisagée est donc :
  **MAL → AniDB (via lien externe) → SIMKL → TMDB / TVDB.**
  ⚠ Le format d'URL AniDB varie (`/perl-bin/animedb.pl?...&aid=N` **ou** `/anime/N`) →
  parser les deux formes.
- ANN / Syoboi : ids extractibles aussi mais sans intérêt pour nos 4 sources.
- ⚠ Présence du lien AniDB **non garantie** pour tout titre (films/OAV anciens) → si
  absent, laisser le rattachement à NULL (ne rien inventer).

`relations` ne contient que des **`mal_id`** (autres anime/manga MAL), utile uniquement
pour **regrouper les entrées MAL d'une même franchise** (ex. relier S1↔S2↔film), pas
pour croiser vers TMDB/TVDB.

## 4. Pièges de modélisation

- **1 saison réelle = N entrées MAL** : MAL découpe souvent une saison en plusieurs
  entrées (cours), chacune avec sa propre numérotation repartant de 1. L'ancrage doit se
  faire au niveau **épisode absolu**, jamais « saison MAL = saison TMDB ».
- **One Piece** (`mal_id=21`) : **une seule** entrée MAL à numérotation **continue**
  (1100+ épisodes) ↔ **N saisons** TMDB. Pagination lourde.
- **Films / OAV / Specials** : entrées MAL distinctes (`type` = `Movie`, `OVA`,
  `Special`, `ONA`). Un film peut n'avoir **aucun** épisode listé dans `/episodes`
  (le considérer alors comme **1 épisode unique**). Un film partageant un `tmdb_id`
  avec une série doit rester une **œuvre distincte** (cf. `extra.type`).
- **`filler` / `recap`** : booléens présents (info source, ne pas s'en servir pour
  l'ancrage). Non persistés dans `extra` (cf. §6).
- **Titres** : `title`, `title_japanese`, `title_romanji` (souvent un espace insécable
  en fin de romanji — à `strip()`).

## 5. Exemple JSON réel — `GET /anime/52991/episodes` (Frieren S1, extrait)

```json
{
  "pagination": { "last_visible_page": 1, "has_next_page": false },
  "data": [
    {
      "mal_id": 1,
      "url": "https://myanimelist.net/anime/52991/Sousou_no_Frieren/episode/1",
      "title": "The Journey's End",
      "title_japanese": "冒険の終わり",
      "title_romanji": "Bouken no Owari ",
      "aired": "2023-09-29T00:00:00+00:00",
      "score": 4.3,
      "filler": false,
      "recap": false,
      "forum_url": "https://myanimelist.net/forum/?topicid=2120196"
    }
  ]
}
```

→ 28 épisodes, 1 page. `data[i].mal_id` = numéro d'épisode (1..28).

## 6. Conventions de remplissage (rappel SYSTEM_PROMPT)

| Colonne | Valeur |
|---|---|
| `source` | `"MAL"` |
| `id_series` | `mal_id` de la série (ex. `52991`) |
| `id_season` | `NULL` (MAL ne modélise pas de saison interne) |
| `id_episode` | n° d'épisode = `mal_id` de l'épisode (ex. `1..28`) |
| `id_franchise` | `NULL` (toujours) |
| `extra` | `NULL` |

> `id_season` reste NULL → contrainte UNIQUE `(source,id_series,id_season,id_episode)`
> doit être `NULLS NOT DISTINCT` pour l'idempotence.
>
> `extra = NULL` : MAL n'a qu'une numérotation (tous épisodes réguliers) → aucun
> qualificatif à porter. L'`aid` (lien `/external`) et `filler`/`recap` servent **à
> l'ingestion** (pivot vers SIMKL, validation) mais ne sont **pas persistés** ici.
