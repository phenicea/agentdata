# ADR-001 — Architecture de l'endpoint #1 : « liquidité exécutable / fragilité & coût de sortie » (Base)

- **Statut :** Accepté (décision CTO)
- **Date :** 2026-06-16
- **Auteur :** cto-agent
- **Contexte amont :** `CLAUDE.md` §5 (7 composants), `decisions/DECISION_LOG.md` (cadrage HUMAIN +
  décisions CEO Pricing 3 tiers & Ordre de listing + Handoff CTO consolidé).
- **Portée :** architecture des 7 composants pour l'endpoint #1, structure projet, ordre d'implémentation
  Phase 1→3. **Testnet uniquement.** Tout point touchant au mainnet / vrai USDC / dépense réelle est marqué
  🚨 ESCALADE et n'est PAS décidé ici.

---

## 0. Doc live consultée (règle d'or §0 — aucune signature devinée)

| Sujet | Source live | Ce qu'elle confirme |
|---|---|---|
| Package x402 Python | `https://pypi.org/pypi/x402/json` | **Version 2.13.0**. Extras déclarés : `all, clients, evm, extensions, fastapi, flask, httpx, mcp, mechanisms, requests, servers, svm, tvm`. « x402 Payment Protocol SDK for Python — transport-agnostic client, server, and facilitator components ». Python ≥ 3.10. Deps clés : pydantic, web3, eth-account, httpx, starlette/fastapi. |
| Flux seller FastAPI | `https://docs.x402.org/getting-started/quickstart-for-sellers` | Install `x402[fastapi]`. Imports : `from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption`, `from x402.http.middleware.fastapi import PaymentMiddlewareASGI`, `from x402.mechanisms.evm.exact import ExactEvmServerScheme`, `from x402.server import x402ResourceServer`. Middleware : `app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)`. Route via `RouteConfig(accepts=[PaymentOption(scheme="exact", pay_to=..., price="$0.02", network=...)], mime_type=..., description=...)`. Facilitator testnet : `https://x402.org/facilitator`. CAIP-2 : **Base Sepolia = `eip155:84532`**, **Base mainnet = `eip155:8453`**. La vérification/settle est gérée par le middleware via le facilitator ; scheme `upto` dispo via `set_settlement_overrides(...)` (non requis ici). |
| Bazaar | `https://docs.x402.org/extensions/bazaar` | Opt-in **déclaratif** : ajouter l'extension `bazaar` à la `RouteConfig`. Facilitator peut exposer `/discovery/resources` listant les services. Métadonnées requises : input schema (avec description par paramètre), output example + schema, name + tags (≤5), icon URL (option). |
| MCP Python SDK | `https://pypi.org/pypi/mcp/json` | Package `mcp`, **version 1.27.2** (29 mai 2026). Transport `streamable-http` confirmé : `mcp.run(transport="streamable-http")`. Extras : `cli, rich, ws`. Python ≥ 3.10. |
| MCP Registry / publish | `https://modelcontextprotocol.io/registry/quickstart` + `registry/docs/.../publish-server.md` | `server.json` (schema `https://static.modelcontextprotocol.io/schemas/2025-10-17/server.schema.json`). CLI `mcp-publisher` (`init` génère un template). Pour serveur **distant** : champ `remotes[]` avec `url` + `type: "streamable-http"` (SSE déprécié). `remotes` et `packages` peuvent coexister. |
| Aerodrome Sugar | `https://github.com/velodrome-finance/sugar` + LpSugar v3 `0xa7638d351040e2adce3eca81b07132c5df4b99bd` (BaseScan) | Contrats : **LpSugar**, RewardsSugar, VeSugar, RelaySugar. LpSugar : `all(_limit,_offset)`, `byIndex(_index)`, `byAddress(_pool)`, `count()`, `tokens(...)`, `positions(...)`. Lp struct (~30 champs) : pool address, symbol, decimals, **liquidity, reserve0/reserve1**, staked, gauge, fees, **tick, sqrt_ratio**, type. Couvre v2 (stable/volatile) ET CL/Slipstream (tick/sqrt_ratio=0 pour v2). |
| Uniswap v3 lecture | `IUniswapV3PoolState.sol` (v3-core) + `QuoterV2.sol` (v3-periphery) | Pool : `slot0()` → (sqrtPriceX96, tick, ...), `liquidity()`, `token0()/token1()/fee()`. **La liquidité v3 est fragmentée par tick → pas de formule fermée** : `QuoterV2.quoteExactInputSingle` simule le swap (view) et retourne amountOut + sqrtPriceX96After + ticksCrossed. |

> ⚠️ Réserve : adresses de déploiement Base exactes (Sugar Slipstream, QuoterV2, factories) à **reconfirmer
> sur BaseScan / `deployments/base.env`** au moment d'implémenter — le code les lit depuis la config, jamais
> codées en dur dans la logique.

---

## 1. Composant 1 — Data Fetcher (sourcing on-chain Base)

### Décision
- **Sources retenues, on-chain uniquement** (droit de redistribution propre — §5/§7) :
  1. **Aerodrome** (pools v2 stable/volatile + CL/Slipstream) via le contrat **LpSugar** (lecture batch
     efficace : `byAddress`, `byIndex`, `all`).
  2. **Uniswap v3 sur Base** via lecture directe du pool (`slot0`, `liquidity`, `token0/1`, `fee`) +
     **QuoterV2** pour la simulation de swap exacte.
- **Accès chaîne (MVP dev) : RPC public Base** (`https://mainnet.base.org` ou équivalent public). Lecture
  seule, données publiques. 🚨 **ESCALADE** : passage à un RPC/indexeur **payant** à volume (dépense réelle,
  impacte le plancher de prix 0,008 $ — cf. handoff CEO point D). Le code abstrait le RPC derrière une
  interface + variable d'env `BASE_RPC_URL` pour que la bascule soit un changement de config revu.
- **Données exactes lues :**
  - v2 / stable-volatile (Aerodrome, Uni v2-like) : `reserve0`, `reserve1`, `decimals`, fee, type stable/vol.
  - CL / v3 (Uniswap v3, Aerodrome Slipstream) : `sqrtPriceX96`, `tick`, `liquidity` actif, `fee`, et —
    pour l'exit-cost size-aware — **simulation via QuoterV2** (`quoteExactInputSingle`) qui traverse les
    ticks réellement liquides.
- **Agrégateurs (DeFiLlama/CoinGecko) : cross-check INTERNE uniquement** (tier C), jamais dans le chemin de
  sortie servi (pas de licence de redistribution). Décision déjà actée, réaffirmée.

### Pourquoi / alternatives écartées
- Subgraph hébergé (The Graph) écarté du chemin critique : ToS de redistribution moins nets + dépendance
  d'indexeur tiers ; on garde le on-chain comme source de vérité. Subgraph possible en accélérateur de
  découverte de pools, jamais comme source des valeurs servies.
- Lecture brute des `reserves` v2 = formule fermée déterministe. Pour v3, **ne pas** tenter une formule
  fermée (liquidité fragmentée) → QuoterV2 = ground truth on-chain vérifiable.

### Risques & test
- Risque RPC public : rate limits / latence. Mesuré par monitoring latence p95 + taux d'erreur. Mitigation :
  cache court (TTL ~ quelques s) sur les lectures de pool, batch multicall.
- Test : comparer la sortie de notre math v3 vs `QuoterV2` on-chain pour la même size → écart < tolérance.

---

## 2. Composant 2 — Compute / Normalize Layer (la valeur ajoutée vérifiable)

### Décision — 3 sorties calculées, déterministes

**(a) Exit-cost size-aware** (coût de sortie pour une taille donnée) :
- **Pools v2 / stable-volatile** : math AMM fermée déterministe à partir de `reserve0/reserve1` et de la
  courbe (constant-product `x*y=k` pour volatile ; courbe stable pour stable). On calcule l'`amountOut`
  effectif pour la `size`, puis `exit_cost = (prix_mid * size - amountOut) / (prix_mid * size)` = pourcentage
  de valeur perdue à la sortie (price impact + fee), exprimé en bps et en USDC.
- **Pools CL / v3** : `exit_cost` dérivé de la simulation **QuoterV2** (traversée de ticks). C'est la valeur
  faisant autorité ; notre réplication tick-math sert de cross-check interne, pas de source servie.

**(b) Depeg-risk** (pour tokens à peg, ex. stablecoins / LST) :
- Score déterministe à partir de signaux **on-chain** : écart du prix implicite du pool vs le peg cible
  (ex. 1,00 pour un stable USD), profondeur de liquidité défendant le peg (combien de $ pour bouger le prix
  de X bps), asymétrie des réserves. **Pas** de feed de prix externe revendu : le « peg » est une référence,
  l'écart est calculé sur la donnée on-chain.

**(c) Fragilité agrégée multi-pools** :
- Score [0–100] combinant, sur l'ensemble des pools du token sur Base : concentration de la liquidité
  (HHI sur les pools), profondeur totale exécutable, sensibilité de l'exit-cost à la taille (pente de la
  courbe exit-cost), et part de liquidité « staked/lock » vs réellement disponible. Pondérations **figées
  et documentées** (versionnées) pour la stabilité du signal.

### Mapping calcul → 3 tiers (alignement coût marginal, handoff CEO point A)
| Tier | Param | Calcul | Coût RPC |
|---|---|---|---|
| **quote** (A, 0,008 $) | `tier=quote` | exit-cost size-aware, **1 pool / 1 size** | lecture 1 pool (+1 quoter v3) |
| **risk** (B, 0,02 $, défaut) | `tier=risk` ou absent | exit-cost + depeg-risk + **fragilité agrégée multi-pools** pour un token | lecture N pools du token |
| **deep** (C, 0,04 $) | `tier=deep` | **courbe** exit-cost sur plusieurs sizes (ladder de liquidation) + cross-check interne (agrégateur, usage interne) | lecture N pools × M sizes + cross-check |

### Pourquoi
La math déterministe sur réserves/ticks on-chain est **reproductible et auditable** : c'est le moat
d'exactitude (cadrage HUMAIN). Le tier B est la vitrine (handoff CEO) → c'est lui qu'on optimise pour
latence et clarté.

### Risques & test
- **Tests unitaires sur la math = priorité absolue** (mandat CTO). Vecteurs de test : (1) v2 exit-cost vs
  calcul manuel sur réserves connues ; (2) v3 exit-cost vs `QuoterV2` on-chain ; (3) fragilité : pools
  synthétiques à concentration connue → score attendu. Couverture cible : 100 % des branches de la math.
- Risque : pondérations de fragilité arbitraires. Mitigation : versionner le modèle (`fragility_model_version`
  dans la réponse), documenter les poids, ne pas les changer sans bump de version (stabilité de schéma/signal).

---

## 3. Composant 3 — API Layer (schéma JSON stable)

### Décision — routing & schéma
- **Une route** payable, paramétrée par tier (route par défaut = `risk`) :
  - `GET /v1/liquidity/exit-cost?token=<addr>&pool=<addr|optional>&size=<usd|token_amount>&tier=<quote|risk|deep>`
  - Tier absent ⇒ `risk` (handoff CEO point A.1). `pool` optionnel en `risk`/`deep` (sinon agrège tous les
    pools du token) ; requis (ou auto) en `quote`.
- **Versionnement dans l'URL (`/v1/`)** pour garantir la stabilité du schéma promise au listing MCP/Bazaar.
- **Schéma de sortie (stable, documenté, machine-readable)** — esquisse :

```json
{
  "schema_version": "1.0",
  "tier": "risk",
  "chain": "base",
  "network_mode": "testnet",
  "token": { "address": "0x...", "symbol": "USDC", "decimals": 6 },
  "request": { "size_usd": 10000, "pool": null },
  "exit_cost": {
    "size_usd": 10000,
    "amount_out_usd": 9962.0,
    "cost_bps": 38,
    "cost_usd": 38.0,
    "price_impact_bps": 31,
    "fee_bps": 7,
    "best_pool": "0x...",
    "source": "uniswap_v3_quoterv2 | aerodrome_lpsugar"
  },
  "depeg_risk": {
    "peg_target": 1.0,
    "implied_price": 0.9994,
    "deviation_bps": 6,
    "score": 12,
    "depth_to_1pct_usd": 2400000
  },
  "fragility": {
    "score": 27,
    "model_version": "frag-1.0",
    "n_pools": 5,
    "liquidity_hhi": 0.41,
    "executable_depth_usd": 5800000,
    "exit_cost_slope": 0.0009
  },
  "tiers_pricing": { "quote": "$0.008", "risk": "$0.02", "deep": "$0.04", "currency": "USDC" },
  "meta": { "computed_at": "2026-06-16T...Z", "latency_ms": 410, "block": 0 }
}
```
  - `deep` ajoute `exit_cost_curve: [{size_usd, cost_bps}, ...]` (ladder) + `cross_check`.
- **Stabilité** : champs additifs uniquement à l'intérieur d'une version ; tout changement cassant ⇒ `/v2/`.
  Les pricing metadata machine-readable sont **dans la réponse** ET avant l'appel (OpenAPI/MCP/llms.txt/402).

### Risques & test
- Test contractuel de schéma (snapshot/JSON Schema) en CI → empêche une régression silencieuse qui casserait
  le critère CEO « 3 jours uptime sans régression de schéma » avant listing MCP.

---

## 4. Composant 4 — x402 Payment Middleware

### Décision (confirmée doc live, §0)
- Lib : **`x402[fastapi]` v2.13.0**. Middleware `PaymentMiddlewareASGI` ajouté via
  `app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)`, `server=x402ResourceServer(...)`,
  scheme EVM `exact` (`ExactEvmServerScheme`), facilitator `HTTPFacilitatorClient`/`FacilitatorConfig`.
- **Facilitator testnet : `https://x402.org/facilitator`** (gratuit, Base Sepolia). Réseau **`eip155:84532`**.
- **Comportement (handoff CEO point B.6) :** requête entrante → middleware lit le `tier` → **fixe le montant
  selon le tier** (quote/risk/deep) → émet le `402` avec termes (montant, `pay_to`, `network`, asset USDC) →
  l'agent paie → rejoue avec preuve → middleware **verify/settle via facilitator** → débloque la réponse JSON.
- **Montant dépendant du tier (handoff A.3)** : on construit le `RouteConfig`/`PaymentOption.price` par tier
  à partir d'une **table de pricing centralisée** (`PRICING[tier][network_mode]`). Comme le tier est un query
  param sur une route unique, le middleware doit résoudre le prix dynamiquement : on enregistre soit une
  `RouteConfig` par tier (chemins distincts en interne) soit un résolveur de prix dépendant de la requête —
  **à confirmer sur la doc live au moment d'implémenter quelle des deux API le SDK 2.13 expose** (price
  dynamique par requête vs route statique par tier). Décision de design : table de pricing unique, source de
  vérité, jamais de montant codé en dur disséminé.
- **Testnet/mainnet séparés par config (handoff A.4) :** variable d'env `NETWORK_MODE=testnet|mainnet` →
  sélectionne `(facilitator_url, caip2_network, pricing_table)`. **Testnet ⇒ prix 0 $** (ou symbolique testnet
  si le facilitator l'exige pour valider la vérification). **Aucune valeur mainnet active sans bascule
  explicite.** Clé/adresse wallet en **secret manager / env** (`X402_PAY_TO`, clé jamais en repo — §14).
- 🚨 **ESCALADE HUMAIN** : toute bascule `NETWORK_MODE=mainnet` / vrai USDC / activation du pricing réel.
  Le code est préparé pour que ce soit **un changement de config revu**, pas une réécriture (handoff B.7).

### Risques & test
- Risque : exposer un montant mainnet par erreur. Mitigation : garde-fou code — refuser de démarrer en
  `mainnet` sans flag d'autorisation explicite + assert que `pricing_table is testnet` quand `NETWORK_MODE`
  != mainnet. Test : suite vérifiant que le 402 émis porte le bon montant **par tier** et `eip155:84532` en
  testnet ; test E2E du flux 402 → pay → serve sur Base Sepolia (Phase 2).

---

## 5. Composant 5 — MCP Server Wrapper

### Décision (confirmée doc live, §0)
- Lib : **`mcp` v1.27.2**, transport **`streamable-http`** (`mcp.run(transport="streamable-http")`) — serveur
  distant ; SSE déprécié (cohérent CLAUDE.md §9).
- **Un outil MCP** : `liquidity_exit_cost`, inputs = `token`, `pool` (optionnel), `size`, `tier`
  (enum quote/risk/deep, défaut risk) ; output = le schéma JSON du §3. **Descriptions par paramètre**
  (requis Bazaar + sélection agent) et **pricing par tier** décrit dans le schéma d'outil (handoff C.8).
- Le serveur MCP appelle la même couche compute que l'API HTTP (pas de duplication de logique). Le paiement
  x402 reste porté par la couche HTTP/middleware ; le wrapper MCP expose l'outil et les métadonnées de prix.

### Risques & test
- Test : un client MCP tiers découvre et appelle l'outil en testnet (critère CEO listing #1).

---

## 6. Composant 6 — Discovery Artifacts (liés aux déclencheurs de listing CEO)

### Décision — quoi produire et quand
| Artefact | Contenu | Déclencheur de listing (CEO) |
|---|---|---|
| **Schéma d'outil MCP** + **`server.json`** | inputs (token/pool/size/tier), outputs (exit-cost/depeg/fragilité), **pricing par tier**. `server.json` schema `2025-10-17`, `remotes[].type="streamable-http"`, publié via **`mcp-publisher`** (init→edit→publish). | **Listing #1 (MCP Registry + npm)** : endpoint testnet live + schéma stable + MCP fonctionnel + **3 j uptime testnet** sans régression de schéma. |
| **Extension `bazaar`** dans `RouteConfig` + **`/discovery/resources`** | name, tags (≤5), input/output schema + descriptions, icon (option). Auto-opt-in déclaratif. | **Listing #2 (Bazaar)** : flux 402 validé end-to-end testnet. |
| **`llms.txt`** (racine) + **docs markdown brut** (URL + `.md`) + **OpenAPI** complet | pricing par tier machine-readable, latence typique, schéma, capacités, réseau, token, destination. Prix lisible **avant** l'appel. | **Listing #3 (BlockRun)** : **7 j uptime testnet** + kit docs + un flux 402 démontrable → contact t.me/bc1max. |

- Le **pricing machine-readable** (0,008 / 0,02 / 0,04 $, USDC, réseau, destination, latence par tier) est
  répliqué **partout** depuis la table de pricing unique : OpenAPI, schéma MCP, llms.txt, termes 402
  (handoff A.2). Source de vérité unique → génération des artefacts, pas de recopie manuelle.

### 🚨 Escalade
- Listing **#3 actif sur trafic payant réel** = mainnet ⇒ ESCALADE. Le **contact** bc1max avec le kit testnet
  est OK ; ne rien promettre de mainnet sans accord humain (handoff CEO).

---

## 7. Composant 7 — Monitoring (dès testnet)

### Décision
- Métriques dès le testnet (handoff C.11 + §15) : **uptime**, **latence p50/p95** (globale + **par tier**),
  **taux d'erreur**, **nb d'appels PAR TIER** (quote/risk/deep). Le tier B doit être >60 % des appels et
  p95 < 800 ms (cibles CEO).
- Implémentation MVP : métriques exposées (`/metrics` Prometheus-style) + log structuré par requête
  (tier, latence, statut, network_mode). Uptime via un check synthétique externe.
- Ces métriques **sont les déclencheurs de listing** (3 j / 7 j uptime) et le socle de la future réputation
  (§13). À avoir tôt (Phase 1, pas Phase 5).

---

## 8. Structure de projet proposée

```
agentdata/
  pyproject.toml                  # deps: x402[fastapi]==2.13.* , mcp==1.27.* , web3, fastapi, uvicorn
  .env.example                    # BASE_RPC_URL, NETWORK_MODE, X402_PAY_TO, FACILITATOR_URL (jamais de secret réel)
  app/
    main.py                       # FastAPI app, montage middleware x402, routes
    config.py                     # NETWORK_MODE, PRICING table (par tier × mode), RPC url, facilitator url
    api/
      routes.py                   # GET /v1/liquidity/exit-cost (routing tier -> compute)
      schemas.py                  # Pydantic in/out (schéma stable §3, schema_version)
    payments/
      x402_setup.py               # PaymentMiddlewareASGI, x402ResourceServer, montant par tier
    chain/
      rpc.py                      # interface RPC Base (public MVP ; bascule payante = escalade)
      aerodrome.py                # LpSugar: byAddress/byIndex/all -> Lp struct (reserves, tick, sqrt_ratio)
      uniswap_v3.py               # slot0/liquidity + QuoterV2.quoteExactInputSingle
      addresses.py                # adresses contrats Base (depuis config, à reconfirmer BaseScan)
    compute/
      exit_cost.py                # math v2 (fermée) + v3 (via quoter) — DÉTERMINISTE
      depeg.py                    # score depeg on-chain
      fragility.py                # score agrégé multi-pools (poids versionnés, frag_model_version)
      tiers.py                    # mapping tier -> pipeline de calcul
    mcp/
      server.py                   # outil MCP liquidity_exit_cost, transport streamable-http
    monitoring/
      metrics.py                  # uptime, latence p50/p95 par tier, taux d'erreur, appels/tier
  discovery/
    llms.txt
    openapi.(généré)
    server.json                   # MCP Registry (remotes streamable-http), pricing par tier
    docs/                         # markdown brut (URL + .md)
  tests/
    test_exit_cost_v2.py          # vs calcul manuel sur réserves connues
    test_exit_cost_v3.py          # vs QuoterV2 on-chain
    test_fragility.py             # pools synthétiques -> score attendu
    test_schema_contract.py       # snapshot JSON Schema (anti-régression)
    test_x402_402_per_tier.py     # 402 porte le bon montant par tier + eip155:84532 en testnet
```

---

## 9. Ordre d'implémentation (Phase 1 → Phase 3)

**Phase 1 — Endpoint local (compute d'abord, c'est la valeur).** Aucun paiement, aucun mainnet.
1. `chain/` : lecture RPC public Base — Aerodrome LpSugar + Uniswap v3 (slot0/liquidity + QuoterV2).
2. `compute/` : exit-cost v2 (fermé) & v3 (quoter), depeg, fragilité. **Tests unitaires math = bloquants.**
3. `api/` : route `/v1/liquidity/exit-cost` + schéma stable §3 + routing des 3 tiers. Test contractuel schéma.
4. `monitoring/` : métriques par tier dès maintenant (uptime/latence/erreurs/appels par tier).
   → Sortie de phase : endpoint testnet live, schéma stable, math vérifiée vs QuoterV2.

**Phase 2 — Paiement testnet (x402).** Toujours testnet.
5. `payments/x402_setup.py` : middleware `PaymentMiddlewareASGI`, montant **par tier**, facilitator
   `x402.org` Base Sepolia (`eip155:84532`), `NETWORK_MODE=testnet` ⇒ prix 0 $/symbolique. Wallet en env.
6. Test E2E flux **402 → pay → serve** de bout en bout sur Base Sepolia + test 402-par-tier.
   → Débloque le déclencheur du **listing #2 (Bazaar)**.

**Phase 3 — Découvrabilité.**
7. `mcp/server.py` : outil MCP `liquidity_exit_cost`, transport streamable-http, pricing par tier décrit.
8. `discovery/` : `server.json` (+`mcp-publisher`), llms.txt, OpenAPI, docs markdown — générés depuis la
   table de pricing unique. Extension `bazaar` activée.
   → Après **3 j uptime** testnet : **listing #1 (MCP Registry + npm)**. Après **7 j uptime** + kit :
   préparer contact **BlockRun**.

**🚨 Hors périmètre de cet ADR (ESCALADE HUMAIN) :** Phase 5 mainnet / vrai USDC / pricing réel ;
RPC payant ; listing BlockRun sur trafic payant. Le code est conçu pour que la bascule mainnet soit un
changement de config revu, pas une réécriture.

---

## 10. Conséquences

- **Positif :** math déterministe vérifiable (moat d'exactitude) ; sourcing on-chain = redistribution propre ;
  séparation testnet/mainnet stricte par config ; artefacts de découverte alignés sur les déclencheurs CEO ;
  monitoring par tier dès J1 (alimente listings + réputation).
- **Coût/risque :** dépendance RPC public (latence/limits) jusqu'à l'escalade RPC payant ; complexité des 3
  tiers (mitigée par route unique + défaut `risk`) ; pondérations de fragilité à versionner.
- **À reconfirmer en doc live à l'implémentation :** adresses contrats Base exactes ; API précise du SDK
  x402 2.13 pour le **prix dynamique par requête vs route par tier** ; éventuel montant testnet non nul exigé
  par le facilitator.
