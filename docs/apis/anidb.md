# AniDB — **référentiel de la grille d'épisodes + pivot `aid`**

> ✅ **Validé par appel réel** : `request=anime&aid=17617` (Frieren), client enregistré
> `episodeidmap` / clientver `1`. Exemples XML ci-dessous = extraits authentiques.

## 0. Rôle dans le projet — à lire en premier

AniDB joue **deux** rôles, tous deux utiles au mapping :

1. **Pivot d'identifiant** : l'`aid` (AniDB anime id) est la clé de jointure du graphe
   ```
   MAL (Jikan /external → URL AniDB → aid)  ──►  SIMKL /search/id?anidb={aid}  ──►  {tmdb,tvdb,mal,...}
   ```
2. **Référentiel de la grille d'épisodes** (← ce pour quoi on l'appelle vraiment) :
   AniDB fournit, par épisode, un **`id` AniDB stable (`epid`)**, un **`epno` canonique
   typé**, une **`airdate`** et des **titres multilingues (dont FR)**. **C'est la
   numérotation qu'utilisent MAL et SIMKL** → AniDB est l'**ancrage de référence** pour
   aligner les épisodes entre sources (par `epno` régulier et/ou par `airdate`).

> **Décision (2026-05-30) : AniDB est une `source` à part entière** (`source="ANIDB"`,
> cf. §6) — elle écrit ses propres lignes — **ET** son `epid`/`epno`/`airdate` sert
> d'**ossature** à l'attribution des `episode_absolute` et à la validation des
> correspondances MAL↔SIMKL↔TMDB↔TVDB. Le projet compte donc désormais **5 sources**.

## 1. Auth & quotas — ⚠ politique de ban agressive

- **Pas de clé API** mais un **client enregistré** sur `anidb.net` (page *Add Client*) :
  un **nom** (`client`) + une **version** (`clientver`). Les deux sont **obligatoires**.
  ⚠ **Le nom ne doit PAS contenir de tiret** : `episode-id-map` est rejeté
  (`<error code="302">client version missing or invalid</error>`), `episodeidmap`
  fonctionne. Tout appel porte `client`, `clientver`, `protover=1`.
- **HTTP en clair**, port non standard : `http://api.anidb.net:9001/httpapi`.
- **Erreurs dans le corps en HTTP 200** (vérifié) : une requête mal formée renvoie
  `<error code="...">...</error>` avec un **code HTTP 200** → **toujours parser le corps**,
  jamais se fier au seul status. Un ban se présente de même (`<error>banned</error>`).
- **Flood protection / ban** (critique) :
  - **≤ 1 requête / 2 s** ; le serveur applique la limite après les 5 premiers paquets.
  - **Cache OBLIGATOIRE** : re-demander le même `aid` le même jour = ban. ~**200 req/24h**
    est l'ordre de grandeur observé avant ban ; le ban **décroît sous ~24 h** d'inactivité.
  - Ne **jamais** « télécharger » AniDB en masse (anti-leech).
- Conséquence code : appels **rares, en série, avec cache disque persistant** des XML
  (les données anime bougent peu), backoff long sur erreur/ban.
- Réponse parfois **gzip** → `--compressed` / `Accept-Encoding: gzip`. Encodage **UTF-8**
  (titres ja/zh/uk… → forcer UTF-8 en sortie).

## 2. Endpoint au niveau ÉPISODE

Un seul endpoint utile, paramétré par `request` :

| Requête | URL |
|---|---|
| Anime + épisodes | `GET .../httpapi?request=anime&client={c}&clientver={v}&protover=1&aid={aid}` |

- `request=anime&aid={aid}` renvoie **en une fois** : titres, type, dates, `<resources>`
  (cross-ids), `<relatedanime>`, et **tous** les `<episode>`. Pas de pagination → cacher.

**Numérotation des épisodes (`epno` + attribut `type`)** — table **confirmée** sur
Frieren (`aid=17617`, 91 épisodes au total) :

| `type` | Signification | `epno` | Nb réel Frieren |
|---|---|---|---|
| 1 | **Épisode régulier** | `1, 2, 3…` | **28** |
| 2 | Special | `S1, S2…` | 25 |
| 3 | Crédit (opening/ending) | `C1…` | 5 |
| 4 | Trailer / PV | `T1…` | 33 |
| 5 | Parodie | `P1…` | (0 ici) |
| 6 | Autre | `O1…` | (0 ici) |

➡ **Pour le mapping, ne retenir que `type=1`** (28 = exactement le compte MAL `52991` et
SIMKL). Les types 2-6 sont des bonus/specials, à traiter à part (ou ignorer). `epno` y
porte un **préfixe lettre** (`S21`, `C1`…) → parser `type` + valeur, ne pas faire `int()`
aveuglément.

## 3. Mapping des épisodes (le cœur de l'usage AniDB)

Chaque `<episode>` réel (extrait **authentique**, `epid=271418`) :

```xml
<episode id="271418" update="2023-10-06">
  <epno type="1">1</epno>
  <length>30</length>
  <airdate>2023-09-29</airdate>
  <rating votes="36">8.00</rating>
  <title xml:lang="ja">冒険の終わり</title>
  <title xml:lang="en">The Journey`s End</title>
  <title xml:lang="de">Das Ende der Reise</title>
  <title xml:lang="fr">La fin de l`aventure</title>
  <title xml:lang="x-jat">Bouken no Owari</title>
  <title xml:lang="uk">Кінець мандрівки</title>
  <title xml:lang="zh-Hans">冒险的结束</title>
  <summary>The world celebrates the Demon King`s defeat ... Source: Crunchyroll</summary>
  <resources>
    <resource type="28"><externalentity><identifier>G0DUND0K2</identifier></externalentity></resource>
  </resources>
</episode>
```

Éléments exploitables pour relier un épisode entre sources :

| Champ | Usage mapping |
|---|---|
| `id` (epid) | **identifiant d'épisode AniDB stable** → clé d'ancrage de référence. |
| `epno` (type=1) | **n° canonique AniDB** = celui que MAL/SIMKL réexposent → jointure directe par numéro. |
| `airdate` | date de 1re diffusion → **réconciliation par date** quand les numéros divergent (films, fusions de saisons TMDB). |
| `title xml:lang="fr"` / `en` | titres lisibles **multilingues (FR dispo)** → utiles au LLM/n8n et à la validation humaine. |
| `length`, `rating`, `summary` | métadonnées d'appoint pour `extra`. |
| `<resources>` épisode | parfois un id de **streaming** (type 28 ici) ; **ni TMDB ni TVDB**. |

➡ **Stratégie de mapping recommandée** : pour un `aid`, prendre les épisodes `type=1`,
clé primaire = `epno` (s'aligne 1:1 avec MAL et avec la numérotation plate SIMKL) ;
**fallback `airdate`** quand l'alignement par numéro est douteux. AniDB devient ainsi
la **table d'ancrage** d'où dérivent les `episode_absolute`.

## 4. ID croisés disponibles (niveau œuvre)

Bloc `<resources>` racine — **réel** (Frieren) :

| `resource type` | Base | Valeur réelle (aid 17617) | Intérêt |
|---|---|---|---|
| 1 | AnimeNewsNetwork (ANN) | `26334` | aucun |
| 2 | **MyAnimeList** | **`52991` ET `56885`** | ✔ retrouver le(s) `mal_id` |
| 6 / 7 / 19 / 20 | Wikipedia en/ja/ko/zh | `Frieren` | aucun |
| 8 | Syoboi | — | aucun |
| 28 (épisode) | streaming (Crunchyroll-like) | `G0DUND0K2` | aucun |

- ⚠ **Découverte clé (cas de modélisation)** : `resource type 2` liste **deux** ids MAL :
  `52991` = la **série TV** (28 ép.) **et** `56885` = *« Frieren Mini Anime »* (**ONA**, 24
  ép. = les specials `type=2`). **Un seul `aid` peut donc regrouper plusieurs entrées
  MAL.** À gérer : ne pas supposer `aid` ↔ 1 seul `mal_id`.
- ⚠ **AniDB n'expose NI TMDB NI TVDB** (ni au niveau œuvre, ni au niveau épisode).
  Ce mapping reste le travail de **SIMKL** (cf. `simkl.md`). AniDB ↔ MAL seulement.
- `<relatedanime>` donne les `aid` liés (réel : `aid=18886 type="Sequel"` = Frieren 2026)
  → utile pour **regrouper une franchise** côté AniDB.

## 5. Dump de titres (`anime-titles`)

Dump **quotidien** statique : `http://anidb.net/api/anime-titles.xml.gz` (pas l'API → pas
de ban). Racine `<animetitles>` → `<anime aid="N">` → `<title type="main|official|short|
syn" xml:lang="...">`. Sert au **mapping titre ↔ `aid`** hors-ligne / index local des
`aid`. **Que les titres** (ni épisodes ni cross-ids). Télécharger **≤ 1×/jour**, avec
**User-Agent personnalisé**, et cacher.

## 6. Conventions de remplissage des colonnes (FIGÉES — AniDB = 5e source)

**Décision (2026-05-30) : AniDB est une `source` à part entière**, au même titre que
MAL/SIMKL/TMDB/TVDB. Elle écrit ses propres lignes dans `episode_id_map`, et son
`epid`/`epno`/`airdate` sert **en plus** d'ancrage de référence pour aligner les autres
sources (cf. §3).

| Colonne | Valeur |
|---|---|
| `source` | `"ANIDB"` |
| `id_series` | `aid` (ex. `17617`) |
| `id_season` | `NULL` (numérotation AniDB plate, pas de saison interne) |
| `id_episode` | `epno` des épisodes `type=1` (ex. `1..28`) ; specials = clé préfixée (`S1`, `C1`, `T1`…) |
| `id_franchise` | `NULL` (toujours) |
| `extra` | `{"epno_type":1}` |

- **`extra` = strict minimum utile au mapping** : seul `epno_type` (1=régulier,
  2=special…) y figure, car il qualifie `id_episode` (filtrage régulier vs special lors de
  l'alignement inter-sources). Tout le reste — `epid`, `airdate`, titres, `length`,
  `mal:[…]` — est l'**ancrage de référence consommé à l'ingestion** (cf. §3 : jointure par
  `epno`, fallback `airdate`, résolution des `mal_id`) pour calculer/valider
  l'`episode_absolute`, **pas persisté** dans `extra`.
- **`id_episode`** : pour `epno_type=1`, c'est l'entier `epno` (1:1 avec MAL). Pour les
  specials, **conserver le préfixe** (`S21`, `C1`…) → reste une chaîne, distincte des
  réguliers, jamais castée en `int`.
- **`id_season` NULL** → contrainte UNIQUE `(source,id_series,id_season,id_episode)` doit
  être `NULLS NOT DISTINCT` (comme MAL & SIMKL).
- **specials / mini-anime** : un `aid` peut mêler une série (`type=1`) et un contenu ONA
  rattaché (Frieren : les `type=2` correspondent au MAL `56885`). Décider à l'ingestion
  s'ils partagent l'`episode_absolute` d'un autre épisode réel ou restent ANIDB-only.
