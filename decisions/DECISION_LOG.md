# Journal des décisions — AgentData

> Mémoire partagée des deux agents décisionnels (`ceo-agent`, `cto-agent`) et du fondateur.
> Chaque décision est ajoutée en bas, datée, avec son auteur (CEO / CTO / HUMAIN). Ne pas réécrire une
> décision passée : si elle change, en ajouter une nouvelle qui supersède l'ancienne (référence-la).
> Source de vérité du projet : `../CLAUDE.md`.

---

## 2026-06-16 — HUMAIN + Phase 0 — Cadrage validé

**Décision :** Endpoint #1 = sous-niche **« liquidité exécutable / fragilité & coût de sortie »**
(exit-cost, depeg-risk), positionné sur la fragilité/coût de sortie, **pas** le slippage brut.
**Pourquoi :** primitive pré-trade à haute fréquence d'appel (idéal modèle % sur volume) ; vrai trou de
marché (TVL statique partout, exit-cost dynamique size-aware nulle part) ; math AMM déterministe et
vérifiable = défendable sur l'exactitude ; 100 % sourçable on-chain = droit de redistribution propre ;
conforme aux valeurs (info de marché, pas de maysir/riba).
**Succès mesuré par :** endpoint testnet live, schéma JSON stable, latence basse, exactitude vérifiable
contre un swap simulé.
**Handoff :** Phase 1 (endpoint local) à lancer après cadrage — non démarrée.

## 2026-06-16 — HUMAIN — Chaîne MVP

**Décision :** **Base d'abord** pour le MVP ; **Solana = endpoint #2**. Projet = track données, multi-chaîne
(Base + Solana) à terme.
**Pourquoi :** Base = volume x402 le plus gros + sources on-chain les plus propres (Aerodrome Sugar +
Uniswap v3) ; MVP le plus rapide et le plus propre.

## 2026-06-16 — HUMAIN — Stack

**Décision :** **Python / FastAPI** pour l'endpoint #1.
**Pourquoi :** SDK x402 Python confirmé en live (PyPI `x402` v2.x, extras `fastapi`/`svm`/`mcp`) vs incertitude
sur les versions npm `@x402/*` ; math AMM propre en Python ; pas de raison de forcer TS pour un backend de données.

## 2026-06-16 — HUMAIN — Création des agents décisionnels

**Décision :** Mise en place de `ceo-agent` (décisions business) et `cto-agent` (décisions techniques) comme
subagents persistants, bornés par les valeurs du `CLAUDE.md`, escaladant au humain tout ce qui touche au
mainnet / vrai USDC / irréversible.
**Pourquoi :** déléguer les décisions courantes vers l'objectif 10K/mois tout en gardant l'humain sur les
décisions argent réel.

## 2026-06-16 — CEO — Pricing endpoint #1 (exit-cost / fragilité de liquidité)

**Décision :**
- **Prix mainnet cible = tarification par tiers, pas prix unique.** Trois tiers basés sur la complexité de
  calcul de la requête (le coût marginal réel = lectures RPC + simulation AMM, pas la taille du payload) :
  - **Tier A — « quote » (lookup simple)** : exit-cost size-aware pour 1 pool/1 size sur Base. **0,008 $/appel.**
  - **Tier B — « risk » (par défaut, sweet spot)** : exit-cost + depeg-risk + fragilité agrégée multi-pools
    pour un token/une position. **0,02 $/appel.** C'est le tier vitrine, celui qu'on optimise pour la sélection.
  - **Tier C — « deep » (multi-size / scénarios de sortie)** : courbe de coût de sortie sur plusieurs tailles
    (ladder de liquidation) + cross-check interne. **0,04 $/appel.**
- **Prix testnet = gratuit (0 $)**, flux 402 complet quand même exécuté en monnaie de test (montant symbolique
  non nul possible en testnet USDC si le facilitator l'exige pour valider la vérification de paiement, mais
  jamais de vrai USDC). Le testnet sert à valider le flux, pas à monétiser.
- **Plancher défendu : on ne descend pas sous 0,008 $.** On ne participe pas à la course vers le bas (cf.
  CLAUDE.md §16 « écartés : x402 moins cher »).

**Pourquoi :**
- Cible CLAUDE.md §8 respectée : 0,008–0,04 $ est entièrement dans la fenêtre 0,001–0,05 $ et sous le seuil
  0,10 $ où vivent 76 % des services. On reste sélectionnable.
- Positionnement vs marché Phase 0 : on se place **délibérément au-dessus de la pure commodité** (x402-api
  0,001–0,008 $) parce qu'on ne vend PAS une lecture brute revendable — on vend un **calcul AMM déterministe
  size-aware** que personne ne sert (le trou identifié). Le tier B à 0,02 $ chevauche Sentinel (0,005–0,025 $)
  et le bas de DeFi Signal Agent (0,01–0,10 $) : crédible, dans la norme « donnée à valeur ajoutée », sans
  être Intel API (0,50 $) qui est hors-fenêtre pour un agent qui appelle en boucle pré-trade.
- Tiers plutôt que prix unique : un agent qui veut juste « est-ce que je peux sortir 10k $ de ce pool » ne doit
  pas payer le prix d'une courbe complète ; et la requête « deep » coûte réellement plus cher à calculer. Le
  pricing par tier aligne prix et coût marginal, et donne un point d'entrée bas (0,008 $) qui sert d'aimant.
- Conforme aux valeurs : modèle % sur volume d'appels (§3), pas d'abonnement, primitive pré-trade à haute
  fréquence — donc même un prix bas accumule du volume.

**Hypothèses & risques :**
- Hypothèse : le coût amont reste quasi nul (RPC public Base + Sugar/Uniswap v3 on-chain). **Si on doit passer
  à un RPC/indexeur payant à volume (§14), le plancher 0,008 $ doit être revalidé** → ESCALADE humain (dépense
  réelle) avant tout engagement RPC payant.
- Risque : 3 tiers ajoutent de la complexité de découvrabilité — un agent doit comprendre quel tier appeler.
  Mitigé en exposant le tier B comme route par défaut et les tiers A/C comme paramètres explicites documentés.
- Risque : prix mainnet réels = exposition USDC. **Le passage mainnet et l'activation du pricing réel sont
  ESCALADÉS au humain** (CLAUDE.md §0, §14). Ces chiffres sont la cible, pas une autorisation de mainnet.
- Risque marché : le marché est petit (§4). Le pricing n'est pas le levier de revenu des premiers mois — la
  découvrabilité l'est. On ne sur-optimise pas le prix maintenant ; on le fige pour pouvoir shipper.

**Succès mesuré par :**
- Court terme (testnet/positionnement) : tier B est le tier appelé dans **> 60 %** des requêtes (signe que le
  produit-vitrine est bien le point de valeur), latence p95 du tier B **< 800 ms**.
- Mainnet (après escalade) : **taux de rachat** (mêmes wallets qui rappellent) > taux de sélection one-shot —
  c'est le vrai signal qu'on est « choisi », pas juste « listé ». Revenu = métrique secondaire les 3 premiers mois.

**Handoff :** voir bloc Handoff CTO consolidé en fin de ces deux décisions.

## 2026-06-16 — CEO — Ordre & stratégie de listing / distribution

**Décision :** Ordre de listing, avec critère déclencheur explicite par canal :

1. **MCP Registry + npm — EN PREMIER (dès Phase 3, sur testnet).**
   - Déclencheur : **endpoint testnet live + schéma JSON stable + serveur MCP fonctionnel + 3 jours d'uptime
     testnet sans régression de schéma.** Pas besoin du flux 402 réglé pour publier ici.
   - npm est groupé avec MCP : le serveur MCP est publié comme package npm (`server.json` + CLI `mcp-publisher`),
     donc une seule étape technique couvre les deux. On publie en marquant clairement « testnet / preview ».

2. **x402 Bazaar — EN DEUXIÈME (Phase 4, dès que le flux 402 est validé end-to-end sur testnet).**
   - Déclencheur : **flux 402 → pay → serve validé de bout en bout sur testnet** (Phase 2 done), endpoint
     `/discovery/resources` du facilitator répond, extension de route « bazaar » activée et auto-opt-in vérifié.
   - C'est la couche de découverte machine native du protocole : on doit y être dès qu'on a un 402 qui marche,
     car c'est le chemin par lequel un agent x402 nous trouve sans intermédiaire.

3. **BlockRun (t.me/bc1max) — EN TROISIÈME, mais c'est le canal à plus fort trafic → on le prépare en parallèle.**
   - Déclencheur de **contact** : **7 jours d'uptime testnet stable + page de docs markdown + OpenAPI + au moins
     un flux 402 démontrable.** On ne contacte bc1max qu'avec un produit montrable (ils onboardent chaque semaine,
     on ne brûle pas le premier contact avec un truc cassé).
   - Déclencheur de **listing actif sur trafic réel** : BlockRun route du volume mainnet → **le listing BlockRun
     pleinement actif (trafic payant réel) est conditionné au passage mainnet → ESCALADE humain.** On peut être
     référencé/préparé avant, mais l'exposition au vrai USDC via leur gateway = décision humain.

**Pourquoi :**
- Principe CLAUDE.md §9 « sois partout », mais l'ordre suit le **coût/risque croissant** : MCP/npm ne demandent
  ni paiement ni mainnet → on se positionne tôt et gratuitement, on apprend le pipeline de publication. Bazaar
  exige un 402 qui marche mais reste testnet → étape suivante logique. BlockRun apporte le plus de trafic mais
  son intérêt réel (volume payant) est couplé au mainnet → on le garde pour la fin de la séquence, contact
  préparé mais activation pleine = porte humain.
- On séquence par **ce qu'on peut faire seul sans toucher à l'argent réel** d'abord (mandat CEO : décider tant
  que ce n'est pas mainnet/USDC réel), et on isole proprement les deux points d'escalade (RPC payant, mainnet).
- Être listé tôt sur MCP Registry = historique de fiabilité qui commence à courir avant même le revenu (§4, §13).

**Hypothèses & risques :**
- Hypothèse : l'auto-opt-in Bazaar via facilitator CDP fonctionne sans config lourde. Si le facilitator CDP
  impose une étape custody/compte qui touche aux fonds → revérifier, possible escalade.
- Risque : publier sur MCP Registry en « testnet/preview » et ne pas tenir l'uptime nuirait à la réputation
  naissante. Mitigé par le déclencheur « 3 jours uptime » avant publication et par un libellé honnête du statut.
- Risque : BlockRun pourrait demander un endpoint mainnet pour onboarder. Si c'est le cas, le **contact** reste
  possible (préparer le terrain) mais l'**activation** attend l'escalade mainnet. Ne pas promettre de mainnet à
  bc1max sans accord humain.

**Succès mesuré par :**
- Phase 3 : présence vérifiable sur MCP Registry + package npm résolvable, schéma d'outil MCP lisible (pricing,
  inputs/outputs décrits). Seuil : découvrable et appelable par un client MCP tiers en testnet.
- Phase 4 : apparition dans le catalogue Bazaar via `/discovery/resources`, premier appel testnet venu d'un
  chemin de découverte (pas d'un appel direct codé en dur).
- Contact BlockRun : réponse de bc1max + critères d'onboarding obtenus et documentés dans ce journal.

**Handoff :** voir bloc Handoff CTO consolidé ci-dessous.

## 2026-06-16 — CEO — Handoff consolidé → cto-agent (contraintes des 2 décisions ci-dessus)

Contraintes techniques imposées par les décisions Pricing + Listing. À traiter par `cto-agent` (le « comment ») :

**A. Pricing — exposition et structure**
1. **3 routes/tiers** à implémenter, alignées sur le coût de calcul : `tier=quote` (A), `tier=risk` (B, défaut),
   `tier=deep` (C). Le tier B doit être la route par défaut si le paramètre est absent.
2. **Métadonnées de pricing machine-readable** à exposer partout (OpenAPI, schéma MCP, llms.txt, et dans les
   termes du `402`) : prix par tier (0,008 / 0,02 / 0,04 $), réseau, token (USDC), adresse de destination,
   latence typique par tier. Le prix doit être lisible AVANT l'appel pour que l'agent puisse décider.
3. **Le montant du 402 doit dépendre du tier demandé** : le middleware x402 calcule le montant en fonction du
   paramètre `tier` de la requête entrante, puis génère le 402 correspondant. Pas de prix codé en dur unique.
4. **Mode testnet = prix 0 $ (ou symbolique testnet)** piloté par variable d'environnement / flag de config,
   strictement séparé du prix mainnet. Aucune valeur mainnet ne doit être active sans bascule explicite (qui
   sera déclenchée par le humain). Clé wallet en secret manager, jamais en repo (§14).
5. Le calcul doit rester **déterministe et vérifiable** (math AMM) pour défendre l'exactitude — tier C inclut
   le cross-check interne (jamais redistribution de données d'agrégateur, sourcing on-chain — décision actée).

**B. x402 middleware — comportement attendu**
6. Flux 402 → pay → serve complet sur **testnet d'abord** ; vérification de paiement via facilitator (vérifier
   signatures/options sur doc live, ne pas déduire de CLAUDE.md — §0). Le middleware doit lire le tier, fixer le
   montant, émettre le 402, vérifier la preuve, puis débloquer la réponse JSON.
7. **Ne pas activer mainnet.** Toute bascule mainnet / vrai USDC est un point d'escalade humain. Préparer le code
   pour que la bascule soit un changement de config revu, pas une réécriture.

**C. Discovery artifacts requis (conditionnent l'ordre de listing)**
8. **Pour le listing #1 (MCP Registry + npm)** : `server.json` valide, publication via CLI `mcp-publisher`,
   package npm résolvable, **schéma d'outil MCP** décrivant inputs (token/pool/size/tier), outputs (exit-cost,
   depeg-risk, fragilité), et **pricing par tier**. Prérequis CEO : 3 jours uptime testnet + schéma stable.
9. **Pour le listing #2 (Bazaar)** : activer l'**extension de route bazaar** + exposer l'endpoint
   `/discovery/resources` du facilitator ; vérifier l'auto-opt-in via facilitator CDP. Prérequis CEO : flux 402
   validé end-to-end testnet.
10. **Pour le listing #3 (BlockRun)** : avoir prêts docs en **markdown brut** (URL + `.md`), **OpenAPI** complet,
    **llms.txt** à la racine, et un flux 402 démontrable. Le contact bc1max se fait avec ce kit, pas avant.
11. **Monitoring dès le testnet** : uptime, latence p50/p95, taux d'erreur, nb d'appels par tier — ces métriques
    sont les déclencheurs des listings (3j / 7j d'uptime) ET le socle de la future réputation (§13). À avoir tôt.

**D. Points d'escalade (ne PAS décider côté agents)**
- Passage RPC/indexeur **payant** → dépense réelle → humain (impacte le plancher de prix 0,008 $).
- Passage **mainnet** / vrai USDC / activation pricing réel / listing BlockRun sur trafic payant → humain.

## 2026-06-16 — CTO — Architecture endpoint #1 (ADR-001)

**Décision :** Architecture des 7 composants de l'endpoint #1 figée dans
`decisions/adr/ADR-001-architecture-endpoint-1.md`. Synthèse :
- **Sourcing on-chain Base** : Aerodrome via **LpSugar** (`byAddress/byIndex/all`, struct = reserves, tick,
  sqrt_ratio, type) + **Uniswap v3** (`slot0`/`liquidity` + **QuoterV2.quoteExactInputSingle** comme ground
  truth, car liquidité v3 fragmentée par tick = pas de formule fermée). RPC **public** Base en MVP dev.
- **Compute** : exit-cost size-aware (v2 = math fermée sur réserves ; v3 = via Quoter), depeg-risk on-chain,
  fragilité agrégée multi-pools (poids versionnés `frag_model_version`). Mapping aux 3 tiers : quote = 1 pool/
  1 size ; risk (défaut) = + depeg + fragilité ; deep = courbe multi-size + cross-check interne.
- **API** : route unique versionnée `GET /v1/liquidity/exit-cost?token&pool&size&tier` (défaut `risk`),
  schéma JSON stable additif-only, `schema_version`.
- **x402** : `x402[fastapi]` v2.13.0, `PaymentMiddlewareASGI`, scheme EVM `exact`, facilitator testnet
  `x402.org` (Base Sepolia `eip155:84532`). Montant **par tier** depuis une table de pricing unique ;
  `NETWORK_MODE=testnet|mainnet` sépare facilitator/réseau/prix ; testnet = 0 $. Wallet en env/secret manager.
- **MCP** : SDK `mcp` v1.27.2, transport **streamable-http**, outil `liquidity_exit_cost` (inputs token/pool/
  size/tier ; output schéma §3 ; pricing par tier décrit).
- **Discovery** : `server.json` (schema 2025-10-17, remotes streamable-http) + `mcp-publisher` → listing #1
  (3 j uptime) ; extension `bazaar` + `/discovery/resources` → listing #2 (402 validé) ; llms.txt + OpenAPI +
  docs markdown → listing #3 (7 j uptime, contact bc1max). Pricing machine-readable répliqué partout depuis
  la table unique.
- **Monitoring** dès testnet : uptime, latence p50/p95 (globale + par tier), taux d'erreur, appels par tier.

**Doc live consultée :**
- `https://pypi.org/pypi/x402/json` → **x402 2.13.0**, extras `fastapi/svm/mcp/evm/extensions` confirmés.
- `https://docs.x402.org/getting-started/quickstart-for-sellers` → imports/middleware FastAPI, facilitator
  testnet `https://x402.org/facilitator`, CAIP-2 Base Sepolia `eip155:84532` / Base `eip155:8453`.
- `https://docs.x402.org/extensions/bazaar` → opt-in déclaratif extension bazaar, `/discovery/resources`.
- `https://pypi.org/pypi/mcp/json` → **mcp 1.27.2**, transport `streamable-http` confirmé.
- `https://modelcontextprotocol.io/registry/quickstart` → `server.json` (schema 2025-10-17), CLI
  `mcp-publisher`, `remotes[].type="streamable-http"`.
- `https://github.com/velodrome-finance/sugar` (LpSugar v3 `0xa7638d351040e2adce3eca81b07132c5df4b99bd`) →
  fonctions et champs Lp struct.
- Uniswap `v3-core IUniswapV3PoolState` + `v3-periphery QuoterV2` → `slot0/liquidity` + simulation de swap.

**Pourquoi / alternatives écartées :** on-chain comme source de vérité (redistribution propre) vs subgraph
hébergé (ToS/dépendance) écarté du chemin servi ; QuoterV2 vs formule fermée v3 (impossible, liquidité par
tick) ; route unique + défaut `risk` vs 3 routes séparées (simplicité de découverte) ; agrégateurs en
cross-check interne seulement (pas de licence de redistribution).

**Risques & comment c'est testé :** tests unitaires math bloquants (v2 vs manuel, v3 vs QuoterV2, fragilité
vs pools synthétiques, couverture 100 % branches) ; test contractuel de schéma (anti-régression, condition du
critère « 3 j uptime sans régression ») ; test E2E 402→pay→serve sur Base Sepolia + 402 bon montant par tier ;
latence p95 tier B < 800 ms, part appels tier B > 60 % mesurées via monitoring.

**🚨 Escalades (NON décidées) :** RPC/indexeur **payant** (dépense réelle, impacte plancher 0,008 $) ;
**mainnet / vrai USDC / pricing réel / listing BlockRun sur trafic payant**. Code conçu pour que la bascule
mainnet soit un changement de config revu, pas une réécriture.

**À reconfirmer en doc live à l'implémentation :** adresses de contrats Base exactes (Sugar Slipstream,
QuoterV2, factories) sur BaseScan / `deployments/base.env` ; API exacte du SDK x402 2.13 pour fixer le prix
**dynamiquement par requête** (tier en query param) vs une `RouteConfig` par tier ; éventuel montant testnet
non nul exigé par le facilitator pour valider la vérification.

**Handoff :** ADR-001 prêt. Phase 1 (compute local + tests math + monitoring par tier) peut démarrer
immédiatement sans toucher à l'argent. CEO : les déclencheurs de listing (3 j / 7 j uptime, flux 402 validé)
sont câblés sur le monitoring dès le testnet. Humain : deux portes d'escalade isolées et inactives par défaut
(RPC payant, mainnet) ; aucune valeur mainnet n'est active dans le code.

## 2026-06-16 — BUILD — Phase 1 livrée (endpoint local, zéro fonds)

**Statut :** Phase 1 (endpoint local) **terminée et vérifiée**. Aucune exposition argent réel, mode testnet
par défaut, prix forcés à 0 $.

**Livré :**
- `compute/` (valeur ajoutée, stdlib pur, déterministe) : `amm.py` (constant-product + courbe stable Solidly
  `x³y+xy³`, exit-cost size-aware, `max_size_for_cost` par bisection), `routing.py` (meilleur venue),
  `depeg.py` (déviation/dispersion/score pondéré liquidité, poids versionnés v1), `fragility.py` (depth +
  concentration HHI + convexité, poids versionnés v1), `tiers.py` (quote/risk/deep).
- `chain/` : `FixturePoolProvider` (pools déterministes WETH/THIN/USDX, offline) + factory ; `OnChainPoolProvider`
  (web3 lazy, **refuse de tourner sur des adresses devinées** — registre vide tant que non vérifié live, conforme
  mandat CTO §0).
- `api/` : FastAPI `GET /v1/liquidity/exit-cost` (défaut `risk`), `/health`, `/metrics`, `/pricing` ; schéma
  pydantic stable additif-only ; `pricing.py` = **table de prix source unique** (quote 0,008 / risk 0,02 /
  deep 0,04 $ mainnet, 0 $ testnet).
- `monitoring/` : uptime, latence p50/p95 (global + par tier), taux d'erreur, appels par tier.
- `config.py` : `NETWORK_MODE` (testnet défaut) + `POOL_SOURCE` (fixture défaut) ; CAIP-2 et facilitator testnet
  confirmés en doc live. `.env.example`, `.gitignore` (secrets exclus), `README.md`, `pyproject.toml`.

**Vérifié :** **42 tests verts** (33 math stdlib sans dépendance + 9 API end-to-end via TestClient). Démo :
token THIN (pool fin unique) → coût de sortie ~1134 bps sur 5000 (signal de fragilité) ; USDX stable près du
peg → 4,7 bps + depeg ≈ 0. C'est l'intelligence différenciée visée (pas un prix brut).

**Non fait (volontairement) :** x402 middleware (Phase 2), wrapper MCP + discovery artifacts (Phase 3),
intégration on-chain réelle (registre de pools à peupler depuis source vérifiée, ADR-001). Aucune touche mainnet.

**Handoff :** prêt pour Phase 2 (x402 sur testnet Base Sepolia) — décision CTO requise sur l'API exacte du SDK
x402 2.13 (prix dynamique par tier) à reconfirmer en doc live. Portes d'escalade humain inchangées (RPC payant,
mainnet) — toujours inactives.

## 2026-06-16 — BUILD — Phase 2 x402 (testnet) livrée via pipeline multi-agents

**Process :** 1 agent CTO spec (install + introspection x402 2.13.0 + doc live) → 5 codeurs sur fichiers disjoints
→ intégration CTO (câblage opt-in + run tests) → 5 testeurs/sécurité → corrections → 3 agents de consolidation.
SDK x402 confirmé : `x402` 2.13.0, middleware officiel `PaymentMiddlewareASGI`, scheme EVM `exact`, prix dynamique
par tier via `DynamicPrice` callback (`ctx.adapter.get_query_param("tier")` confirmé sûr en introspection).

**Livré :** package `src/agentdata/payment/` (middleware.py, facilitator.py, pricing_402.py) + câblage **opt-in**
dans app.py (`X402_ENABLED`, défaut false → middleware non monté, Phase 1 intacte). Montant du 402 par tier depuis
la table de prix unique (`api/pricing.py`), testnet = 0 $, facilitator testnet x402.org / Base Sepolia
`eip155:84532`, scheme `exact`. Flux verify→settle fail-closed (géré par le SDK : body bufferisé, 502 sur erreur
facilitator, 402 sur échec settle). `docs/x402-integration.md`, `.env.example` mis à jour.

**Findings sécurité traités (consolidation) :**
- 🔴 HIGH (bloquant) — **Garde-fou mainnet ADR-001 §4 absent** → CORRIGÉ : `src/agentdata/safety.py` `guard_network()`
  + champ `allow_mainnet` (env `ALLOW_MAINNET`, défaut false). L'app **refuse de démarrer en mainnet** sans
  autorisation explicite ; invariant "testnet = 0 $" asserté. Vérifié en exécution.
- 🟠 MEDIUM — **TOCTOU** (guard one-shot à l'import, endpoints relisent l'env par requête) → CORRIGÉ : `guard_network`
  est désormais appelé dans `load_settings()` à CHAQUE lecture → un flip mainnet au runtime échoue (fail-closed,
  vérifié : 500). Garde aussi ajoutée en interne dans `build_x402_middleware` (défense en profondeur, tout futur
  chemin de montage est gardé).
- 🟡 LOW — **`facilitator_url` vide** avec x402 activé → CORRIGÉ : `build_x402_middleware` refuse de monter sans
  facilitator. **`tier_price` sans try/except** (DoS route payante) → CORRIGÉ : repli sur DEFAULT_TIER. **Doc
  `ALLOW_MAINNET`** → ajoutée à `.env.example`.

**Tests :** **71 verts** (42 Phase 1 + 21 paiement + 4 garde-fou réseau + 4 hardening). Aucune régression, schéma
API inchangé.

**🚧 À traiter AVANT bascule mainnet (hardening tracké, non bloquant pour testnet) :**
- F-2 : faire passer le flux "manuel" `payment_requirements()` (pricing_402.py) par le même invariant testnet/mainnet
  que `guard_network` ; vérifier la présence de l'extra `x402[evm]` au chargement.
- F-3 : centraliser `MAX_TIMEOUT_SECONDS` (dupliqué middleware.py / pricing_402.py) en source unique.
- F-4 : ajouter un test anti-rejeu (facilitator mocké `is_valid=False, nonce_already_used` → 402, body non servi).
- F-5 : `FacilitatorClient._to_dict` ne doit pas masquer une forme inconnue en dict ambigu → fail-closed explicite.
- Post-escalade : valider format/allowlist de `FACILITATOR_URL` et `PAY_TO_ADDRESS` lors de la revue mainnet humaine.
- E2E testnet réel (402→pay→serve contre le vrai facilitator) : nécessite un **wallet Base Sepolia financé** =
  action humaine ; vérifier alors si le facilitator accepte un montant 0 $ ou exige un montant testnet symbolique.

**Handoff :** Phase 2 prête côté code sur testnet (opt-in, gardée). Reste : E2E testnet réel (wallet financé = humain),
puis Phase 3 (MCP + discovery artifacts). Mainnet toujours verrouillé (double garde : refus démarrage + refus par requête).

## 2026-06-16 — CEO — Prochaine étape : Phase 3 (Découvrabilité) en priorité, E2E testnet en parallèle, hardening différé

**Décision :** La prochaine étape de travail est **(A) Phase 3 — Découvrabilité** : wrapper MCP (transport
streamable-http, outil `liquidity_exit_cost`) + discovery artifacts (`server.json`, OpenAPI, `llms.txt`, docs
markdown brut), avec pricing par tier machine-readable répliqué partout depuis la table unique. **Séquence retenue :**
1. **MAINTENANT → cto-agent : Phase 3** (ne dépend d'aucun fonds, avance directement le listing #1 MCP Registry + npm).
2. **EN PARALLÈLE → humain : préparer le wallet Base Sepolia financé** (débloque l'option C / E2E testnet réel, qui
   est le prérequis du listing #2 Bazaar — sans bloquer A).
3. **PLUS TARD → (B) hardening F-2..F-5 : différé**, à traiter juste avant la bascule mainnet (lointaine, escalade humain),
   PAS maintenant. Exception : si Phase 3 touche `pricing_402.py` / la table de prix, intégrer F-2 et F-3 à ce moment-là
   (coût marginal nul, pas de détour).

**Pourquoi :**
- North Star honnête (CLAUDE.md §4, §3 de ma définition) : les premiers mois = **fiabilité + découvrabilité +
  positionnement**, pas le revenu. La Phase 3 est exactement cette fonction-objectif. Elle fait **démarrer
  l'historique d'uptime/fiabilité** (déclencheur listing #1 : 3 j uptime testnet + schéma stable) — du temps qui
  court à notre avantage, gratuitement, dès maintenant.
- A ne dépend d'**aucun fonds** et n'a **aucun point d'escalade** : c'est pleinement dans mon mandat et exécutable
  immédiatement par cto-agent. C'est le seul des trois qui crée de la **valeur de découvrabilité nette** tout de suite.
- C (E2E testnet réel) est **bloqué sur une action humaine** (wallet financé) → on ne le met pas sur le chemin
  critique, mais on le **déclenche en parallèle** car c'est le prérequis du listing #2 (Bazaar) et la dernière
  validation testnet manquante. Le faire avancer en fond évite qu'il devienne le goulot une fois A livrée.
- B (hardening) **n'apporte pas de découvrabilité** et n'est utile que juste avant le mainnet, qui est lointain et
  sous escalade humain. Le journal le qualifie déjà explicitement « non bloquant pour testnet ». Le faire maintenant
  = optimiser un risque qui ne se matérialise pas avant le mainnet, au détriment du temps d'uptime qui, lui, court
  maintenant. Mauvais arbitrage de séquencement → différé (sauf F-2/F-3 si on est déjà dans ces fichiers).

**Hypothèses & risques :**
- Hypothèse : publier MCP Registry/npm en **testnet/preview** ne nuit pas à la réputation naissante TANT QUE le
  libellé de statut est honnête et que le déclencheur « 3 j uptime sans régression de schéma » est respecté AVANT
  publication (cf. décision listing du 16/06). Risque réputationnel si on publie trop tôt → mitigé par ce gate.
- Risque : Phase 3 livrée mais E2E testnet réel toujours bloqué (wallet non fourni) → on peut publier listing #1
  (qui n'exige pas le 402 réglé) mais **pas** listing #2 (Bazaar, qui exige le flux 402 validé end-to-end). Acceptable :
  A débloque le listing à plus fort effet-historique en premier ; Bazaar suit dès le wallet dispo.
- Risque technique : le wrapper MCP doit exposer le **même** pricing/schéma que l'API REST depuis la table de prix
  unique (pas de divergence) — sinon incohérence machine-readable qui casse la sélection par l'agent. À tester.
- Hypothèse : le code Phase 1/2 (schéma JSON, table de prix unique) est stable → le wrapper MCP s'y branche sans
  refonte. Vérifié par le journal (schéma additif-only, table source unique).

**Succès mesuré par :**
- **Court terme (Phase 3 done) :** `server.json` valide + publié via `mcp-publisher`, package npm résolvable,
  serveur MCP **appelable par un client MCP tiers en testnet** (outil `liquidity_exit_cost` avec inputs token/pool/
  size/tier, outputs exit-cost/depeg-risk/fragilité, pricing par tier lisible). `llms.txt` à la racine + OpenAPI
  complet + docs markdown brut servis. Pas de régression : tests toujours verts, schéma API inchangé.
- **Déclencheur listing #1 armé :** monitoring testnet tourne en continu → **3 jours d'uptime sans régression de
  schéma** atteints = feu vert publication MCP Registry. C'est la métrique qui compte (l'historique de fiabilité
  commence à courir).
- **Parallèle (humain) :** wallet Base Sepolia financé fourni → débloque E2E testnet réel → prérequis listing #2.

**Handoff :**
- **cto-agent (à faire ensuite, maintenant) :** lancer **Phase 3** par ordre d'effet sur le listing #1 :
  (1) **wrapper MCP** SDK `mcp` 1.27.2, transport **streamable-http**, outil `liquidity_exit_cost` (schéma ADR-001),
  pricing par tier décrit depuis la table unique ;
  (2) **`server.json`** (schema 2025-10-17, remotes streamable-http) + chaîne de publication `mcp-publisher` + package
  npm résolvable (libellé **testnet/preview** honnête) ;
  (3) **discovery artifacts** : `llms.txt` à la racine, **OpenAPI** complet, **docs markdown brut** (URL + `.md`),
  métadonnées pricing/latence/schéma machine-readable répliquées depuis la table de prix unique ;
  (4) garder le **monitoring testnet** allumé en continu pour faire courir le compteur d'uptime (déclencheur 3 j) ;
  (5) **ne pas** traiter F-2..F-5 maintenant **sauf** si l'implémentation touche `pricing_402.py` / la table de prix
  → alors intégrer **F-2** (invariant testnet/mainnet sur `payment_requirements()` + check extra `x402[evm]`) et
  **F-3** (centraliser `MAX_TIMEOUT_SECONDS`) au passage, coût marginal nul ;
  (6) reconfirmer en **doc live** (MCP Registry quickstart, SDK mcp 1.27.2) avant publication — ne pas déduire les
  signatures du journal (CLAUDE.md §0). **Ne PAS toucher au mainnet** : portes d'escalade inchangées.
- **Humain (en parallèle, non bloquant pour A) :** préparer et **financer un wallet Base Sepolia** (USDC + gas de
  test) dédié à l'E2E testnet, et le fournir à cto-agent quand prêt → débloque l'E2E réel (option C) et le listing #2
  (Bazaar). Vérifier à ce moment si le facilitator x402.org accepte un montant **0 $** ou exige un **montant testnet
  symbolique**. Rappel : ceci reste du **testnet** (pas de vrai USDC, pas de mainnet — toujours sous verrou).
- **Différé (ni A ni parallèle) :** hardening pré-mainnet **F-2..F-5** (sauf F-2/F-3 opportunistes ci-dessus) → à
  planifier dans la revue sécurité **juste avant l'escalade mainnet** (Phase 5), pas avant.

## 2026-06-16 — BUILD — Phase 3 (MCP + découvrabilité) livrée via pipeline multi-agents

**Process :** spec CTO (introspection `mcp` 1.27.2 + doc live registre) → 5 codeurs (fichiers disjoints) →
intégration CTO → 5 testeurs/sécurité → correctif ciblé. **Aucun finding bloquant.**

**Livré :**
- Package `src/agentdata/mcp/` : `tool_schema.py` (source unique du schéma de l'outil), `server.py`
  (outil `liquidity_exit_cost`, transport **streamable-http**, réutilise le MÊME chemin que l'API REST :
  get_provider → compute_tier ; point d'entrée `python -m agentdata.mcp.server`, jamais lancé à l'import).
- Discovery artifacts : `llms.txt` (racine, complet : endpoint, tiers+prix, liens), `docs/api.md` (doc markdown
  brute), OpenAPI enrichi (tags/description/contact/licence), `server.json` (manifest MCP Registry) + `package.json`.
- Routes FastAPI ajoutées : `GET /llms.txt` et `GET /docs/api.md` (servies en brut, distinctes du Swagger `/docs`).

**Findings traités :**
- 🟠 MEDIUM (discovery) — **`llms.txt` annonçait `/docs/api.md` → 404** (fichier présent mais non servi) → CORRIGÉ :
  route `GET /docs/api.md` ajoutée ; tous les liens du llms.txt résolvent (200), pas de collision Swagger. Test
  `tests/test_discovery.py` ajouté (verrouille la surface servie).
- ℹ️ Correction doc : le schéma du registre MCP est **`2025-12-11`** en live (pas `2025-10-17` comme noté dans
  ADR-001/anciennes entrées — id obsolète). Le `server.json` utilise déjà le bon `$schema`.

**Tests :** **91 verts** (71 Phases 1+2 + 15 MCP + 5 discovery). Schéma API inchangé, garde-fous mainnet intacts.

**🚧 Dépendances HUMAINES pour le listing #1 (MCP Registry + npm) :**
- Choisir le **namespace** (GitHub `io.github.<user>/...` ou domaine custom via DNS auth) — placeholder dans server.json.
- Fournir le **host de déploiement public** (`remotes[].url`) — nécessite de déployer le service (Railway/Render/Fly).
- Puis **3 j d'uptime testnet** sans régression de schéma → feu vert publication (`mcp-publisher`, étape humaine).

**Handoff :** code Phase 3 prêt (testnet). Listing #1 gated sur déploiement + namespace (humain) + 3 j uptime.
E2E testnet (option C) attend le wallet Base Sepolia financé (humain, en cours). Mainnet toujours verrouillé.

## 2026-06-16 — CEO — Namespace marque Phenicea + cible de déploiement testnet + déblocage listing #1

**Décision :**

**1. Namespace MCP exact = GitHub org auth (PAS domaine custom pour l'instant).**
- Nom MCP (`server.json` `name` ET `package.json` `mcpName`) : **`io.github.phenicea/agentdata-liquidity-exit-cost`**.
  Auth = GitHub OAuth via `mcp-publisher login github`. Confirmé doc live : GitHub auth accepte `io.github.orgname/*`
  (pas seulement un user perso), donc l'org GitHub `phenicea` est le préfixe légitime.
- Nom npm : **`@phenicea/agentdata-liquidity-exit-cost`** (scope npm = la marque).
  ⚠️ **Mais npm n'est PAS requis pour le listing #1** : confirmé doc live, un serveur **remote** (`remotes[].type=streamable-http`)
  se liste au registre **avec une simple URL, sans package npm publié**. Le `packages[]`/npm ne sert qu'à une install stdio
  locale, qu'on n'offre pas. → On garde le nom npm **réservé** sous `@phenicea` (cohérence de marque + option future),
  mais on ne le met PAS sur le chemin critique de publication. Le listing #1 = `server.json` remote + `mcp-publisher publish`.
- **Pourquoi GitHub org plutôt que domaine custom (`ai.phenicea` / `com.phenicea`)** : le domaine custom (DNS auth) exige de
  **posséder + prouver un domaine** (clé Ed25519 + TXT record `v=MCPv1; k=ed25519; p=...`), ce qui ajoute un achat de domaine
  (= **dépense réelle → escalade humain**) et une étape DNS, pour **zéro gain de découvrabilité** au stade actuel (le registre
  ne classe pas par "beauté" du namespace, l'agent sélectionne sur prix/latence/fiabilité/schéma — cf. CLAUDE.md §10). On ne
  paie pas un domaine pour de l'esthétique de marque tant qu'on n'a pas de revenu. Le namespace reste **migrable plus tard**
  vers `com.phenicea/...` ou `ai.phenicea/...` quand le fondateur voudra investir dans le domaine (on publiera une nouvelle
  entrée qui supersède — coût: re-listing, pas une réécriture de code).

**2. Cible de déploiement testnet = Render (Web Service), tier gratuit, pour démarrer le compteur d'uptime.**
- **Recommandation : Render**, en acceptant explicitement sa limite, AVEC un keep-alive. Raison : c'est la seule des 4 options
  qui offre un **vrai tier gratuit sans carte bancaire requise** (donc **PAS de dépense réelle → reste dans mon mandat, pas
  d'escalade**), supporte nativement un serveur **Python ASGI long-running** (uvicorn/FastAPI + transport MCP streamable-http),
  et est simple/vibecodable (`render.yaml` ou détection auto).
- **⚠️ Caveat décisif (fait live)** : en 2026, **aucun** tier gratuit (Render/Railway/Fly/Cloudflare) n'est "always-on". Render
  free **dort après 15 min d'inactivité** (cold start 30–60 s). Or notre déclencheur de listing #1 = **"3 jours d'uptime testnet
  sans régression de schéma"**. Donc : **uptime mesuré = uptime applicatif (réponses 200 cohérentes + schéma stable), pas
  "process jamais évincé"**. On **neutralise le sommeil** avec un **health-check ping externe gratuit** (ex. cron-job.org ou
  UptimeRobot, gratuits, sans CB) qui frappe `/health` toutes les ~10 min → le service reste chaud et le moniteur d'uptime
  tourne. C'est suffisant pour du **testnet/preview** (on n'a pas encore de trafic d'agents réel à servir).
- **Cloudflare Workers écarté** : modèle d'exécution éphémère/edge, mauvais fit pour un serveur ASGI Python long-running avec
  état de connexion streamable-http. **Railway / Fly écartés au stade testnet** : exigent une **CB / post-paid** dès le départ
  (Railway: $5 trial one-shot puis payant ; Fly: CB obligatoire, plus de free tier) → **dépense réelle = escalade humain**, qu'on
  évite tant que le gratuit suffit. **Bascule prévue** : quand on aura besoin d'un vrai always-on (proximité mainnet / trafic réel
  via BlockRun), **passer sur Railway ou Fly en plan payant = décision à escalader au humain** (petite dépense récurrente).

**3. À exécuter MAINTENANT (zéro argent, zéro mainnet) :** voir Handoff CTO ci-dessous. En résumé : figer le namespace Phenicea
dans `server.json`/`package.json`, préparer la config de déploiement Render (Dockerfile/render.yaml + entrypoint MCP
streamable-http), brancher un keep-alive gratuit sur `/health`, déployer en testnet/preview, et **une fois l'URL connue**, y
brancher `remotes[].url`, `websiteUrl`, OpenAPI `servers[]` et les liens du `llms.txt`. Puis laisser courir le compteur 3 j.

**Pourquoi :**
- Conforme au mandat CEO : tout ceci est **gratuit + testnet + réversible** → pleinement dans mon périmètre, **aucune escalade
  argent** sauf les deux micro-escaladess "compte/possession" notées ci-dessous (créer l'org GitHub, et — seulement si plus tard —
  acheter un domaine ou un plan payant).
- North Star (CLAUDE.md §4) : l'objectif des premiers mois = **fiabilité + découvrabilité + historique d'uptime qui court**.
  Déployer maintenant, même sur un free tier qui dort, fait **démarrer le compteur 3 j** (avec keep-alive) → on débloque le
  listing #1 (le plus fort effet-historique, qui n'exige NI 402 réglé NI mainnet) au plus vite et au coût zéro.
- On **n'achète pas de marque** (domaine) ni de compute payant tant que le revenu n'existe pas : le namespace GitHub org donne la
  marque "Phenicea" gratuitement et reste migrable.

**Hypothèses & risques :**
- Hypothèse : l'org GitHub `phenicea` est **disponible** et le fondateur la crée. Si `phenicea` est pris sur GitHub, fallback :
  variante proche (`phenicea-ai`, `phenicea-labs`) → le namespace devient `io.github.phenicea-ai/...` (à acter alors). Le scope
  npm `@phenicea` doit aussi être libre ; sinon `@phenicea-ai`.
- Risque réputation : publier en testnet/preview puis ne pas tenir l'uptime nuit à la réputation naissante → mitigé par (a) le
  gate "3 j uptime sans régression de schéma" AVANT `mcp-publisher publish`, (b) le keep-alive, (c) le libellé honnête
  "Testnet / preview" déjà dans la description.
- Risque keep-alive/free tier : si Render free s'avère trop instable même avec ping (évictions, quotas), le compteur 3 j ne tiendra
  pas → fallback = **escalade humain pour un petit plan payant** (Railway/Render Starter, quelques $/mois). On tente le gratuit
  d'abord ; on n'escalade la dépense que si le gratuit échoue à tenir 3 j.
- Risque migration namespace : si le fondateur veut plus tard `com.phenicea/...`, il faudra re-lister (nouvelle entrée registre) —
  acceptable, c'est de la config/re-publication, pas du code.

**Succès mesuré par :**
- Namespace figé : plus aucun `PLACEHOLDER-GITHUB-USER` dans `server.json`/`package.json` ; `name` == `mcpName` ==
  `io.github.phenicea/agentdata-liquidity-exit-cost` (invariant du registre respecté).
- Déploiement : service testnet répond `200` sur `/health`, `/mcp` (streamable-http) joignable publiquement en HTTPS,
  `remotes[].url` pointant dessus.
- Déclencheur listing #1 armé : **3 jours d'uptime applicatif continu sans régression de schéma** (monitoring + keep-alive) →
  feu vert `mcp-publisher publish`. Métrique qui compte : l'historique de fiabilité commence à courir.

**Handoff :** voir bloc Handoff CTO ci-dessous.

## 2026-06-16 — CEO — Handoff consolidé → cto-agent (déploiement Render + namespace Phenicea)

À traiter par `cto-agent` (le "comment"). **Aucune touche mainnet, aucune dépense** (free tier only ; toute bascule payante = escalade humain).

**A. Figer le namespace Phenicea (dès maintenant, ne dépend de rien) :**
1. Dans `server.json` : `name` → `io.github.phenicea/agentdata-liquidity-exit-cost`. Remplacer aussi les
   `PLACEHOLDER-GITHUB-USER` dans `websiteUrl` et `repository.url` par l'org `phenicea` (ex.
   `https://github.com/phenicea/agentdata`). NE PAS encore toucher `remotes[].url` (attend l'URL Render — étape C).
2. Dans `package.json` : `name` → `@phenicea/agentdata-liquidity-exit-cost` ; `mcpName` →
   `io.github.phenicea/agentdata-liquidity-exit-cost` (doit être identique à `server.json.name`) ;
   `repository.url`, `homepage`, `bugs.url` → org `phenicea`.
3. Vérifier l'invariant registre : `server.json.name` === `package.json.mcpName`. (Confirmé doc live : doivent matcher.)
4. **Ne pas publier npm** : le listing #1 est un serveur **remote** (URL only), npm non requis. Garder le package comme
   réservation de marque (`@phenicea`), `private:false` ok mais publication npm = étape optionnelle ultérieure, pas sur le
   chemin critique.

**B. Préparer la config de déploiement Render (testnet/preview, free tier) :**
5. Ajouter un artefact de déploiement reproductible : **Dockerfile** (Python 3.x slim + install `pyproject` + extras MCP) OU
   `render.yaml` (type: web, env: python, `buildCommand`/`startCommand`). Entrypoint = serveur MCP **streamable-http** exposé
   publiquement (le serveur actuel `python -m agentdata.mcp.server` + l'app FastAPI qui sert `/health`, `/metrics`, `/pricing`,
   `/llms.txt`, `/docs/api.md`, et le mount MCP `/mcp`). Bind sur `0.0.0.0:$PORT` (Render injecte `$PORT`).
6. **Variables d'env Render** : `NETWORK_MODE=testnet` (défaut), `X402_ENABLED` selon besoin de démo (peut rester false pour
   le listing #1 qui n'exige pas le 402), **`ALLOW_MAINNET` absent/false** (garde-fou intact), `POOL_SOURCE=fixture` tant que
   l'on-chain réel n'est pas câblé sur adresses vérifiées. **Aucun secret/clé wallet en repo** (§14) — si une clé testnet est
   nécessaire plus tard pour l'E2E, en var d'env Render, jamais commitée.
7. Vérifier en **doc live** au moment de l'implémentation : commande de start exacte pour servir le transport streamable-http
   du SDK `mcp` 1.27.2 derrière uvicorn/ASGI sur un PaaS (host/port/path) — ne pas déduire du journal (CLAUDE.md §0).

**C. Brancher l'URL publique une fois le déploiement live :**
8. Récupérer l'URL Render (forme `https://<service>.onrender.com`). Mettre à jour :
   - `server.json` → `remotes[0].url` = `https://<service>.onrender.com/mcp` (ou le path réel du mount MCP).
   - OpenAPI → `servers[].url` = base publique ; liens du `llms.txt` (endpoint, docs `.md`, OpenAPI) → URLs publiques absolues.
   - Vérifier que tous les liens `llms.txt` résolvent en 200 sur l'host public (test discovery déjà en place — le rejouer
     contre l'URL publique).
9. **Keep-alive gratuit** : configurer un ping externe (cron-job.org / UptimeRobot, gratuit, sans CB) sur `/health` toutes les
   ~10 min pour neutraliser le sommeil free-tier et alimenter le compteur d'uptime. Documenter l'URL pingée.

**D. Laisser courir + déclencher la publication :**
10. Monitoring testnet allumé en continu ; viser **3 jours d'uptime applicatif sans régression de schéma**. À l'atteinte du
    seuil → `mcp-publisher login github` (org `phenicea`) puis `mcp-publisher publish` (libellé testnet/preview honnête).
    **Cette étape de publication finale nécessite l'auth GitHub de l'org → action humaine/fondateur** (login OAuth).
11. **Ne pas** traiter F-2..F-5 (hardening pré-mainnet) — sauf coût marginal nul si on touche `pricing_402.py`. **Ne PAS**
    activer mainnet ni x402 mainnet. Portes d'escalade inchangées.

**E. Points d'escalade humain (ne PAS décider côté agents) :**
- **Micro-escalade légère (compte/possession, pas d'argent)** : créer l'**org GitHub `phenicea`** (et idéalement réserver le
  scope npm `@phenicea`). Sans ça, le namespace et la publication sont bloqués. Si `phenicea` indisponible → choisir une
  variante et la communiquer (on réajuste le namespace).
- **Escalade dépense (seulement si nécessaire plus tard)** : si le free tier Render ne tient pas 3 j même avec keep-alive, ou
  quand on aura besoin d'un vrai always-on (proximité mainnet / trafic BlockRun réel) → **plan payant Railway/Fly/Render**
  (quelques $/mois) = décision humain.
- **Escalade marque (optionnelle, plus tard)** : acheter un domaine pour passer à `com.phenicea/...` ou `ai.phenicea/...`
  (DNS auth) = dépense réelle → humain. Non nécessaire au stade actuel.
- **Inchangé** : wallet Base Sepolia financé (humain, en cours) débloque E2E testnet → listing #2 Bazaar. Mainnet verrouillé.

## 2026-06-16 — BUILD — Phase 3b : namespace Phenicea figé + deploy-readiness (Render) via pipeline

**Process :** spec CTO (montage MCP streamable-http + FastAPI sur un seul port, mcp 1.27.2) → 4 codeurs → intégration
CTO → 3 testeurs/sécurité. **Aucun finding bloquant** (tous pass, sévérité max low).

**Décisions CEO appliquées :**
- Namespace figé : `server.json.name` = `package.json.mcpName` = **`io.github.phenicea/agentdata-liquidity-exit-cost`** ;
  npm `@phenicea/agentdata-liquidity-exit-cost` ; `$schema` 2025-12-11 ; `remotes[0].url` = placeholder
  `https://PLACEHOLDER-RENDER-HOST/mcp` (à remplacer post-déploiement).
- Cible : Render free tier, un seul process uvicorn servant REST + MCP.

**Livré :**
- `src/agentdata/asgi.py` : app ASGI combinée (FastAPI REST + MCP streamable-http monté sous `/mcp`, lifespan/session
  manager du MCP câblé depuis le lifespan parent). Réutilise l'app et le serveur existants, zéro logique dupliquée.
- `Dockerfile` + `render.yaml` + `.dockerignore` : Python, start `uvicorn agentdata.asgi:app --host 0.0.0.0 --port $PORT`,
  build `pip install ".[mcp]"`. Env testnet (NETWORK_MODE=testnet, POOL_SOURCE=fixture, X402_ENABLED=false, PAS de
  ALLOW_MAINNET). PAY_TO_ADDRESS/FACILITATOR_URL en env Render (`sync:false`, jamais committés). `healthCheckPath:/health`.
- `tests/test_deploy.py` (12 tests).

**Bloqueur de déploiement trouvé + corrigé (CTO) :** l'extra `mcp` n'était pas déclaré dans `pyproject.toml` →
`pip install ".[mcp]"` n'installait rien (WARNING silencieux) → `ModuleNotFoundError` au build Render propre. Corrigé :
ajout `[project.optional-dependencies] mcp = ["mcp>=1.27,<2"]`.

**Vérifié :** **103 tests verts** (91 + 12 deploy). Smoke E2E local (lifespan démarré) : `/health` 200, `/v1/liquidity/
exit-cost` 200, **`POST /mcp initialize` → 200** (handshake MCP JSON-RPC valide, protocole 2025-06-18), `/mcp/mcp` 404
(pas de double préfixe). Garde-fous mainnet intacts. Aucun secret en repo.

**🚧 Portes humaines pour publier le listing #1 (aucune n'expose d'argent réel) :**
1. Créer l'org GitHub **`phenicea`** (+ réserver scope npm `@phenicea`). Si pris → fallback `phenicea-ai`/`phenicea-labs`.
2. Déployer sur **Render** (compte humain) → récupérer l'URL → remplacer `PLACEHOLDER-RENDER-HOST` dans server.json
   (+ OpenAPI servers[], liens absolus llms.txt) → keep-alive `/health` (~10 min).
3. **3 j d'uptime testnet** sans régression de schéma → `mcp-publisher login github` (org phenicea) + `publish`.

**Handoff :** code 100 % deploy-ready (testnet). Reste humain : org GitHub + déploiement Render + 3 j uptime + publish.
E2E testnet (option C) attend le wallet Base Sepolia financé. Mainnet toujours verrouillé (double garde).

## 2026-06-16 — CEO — Repo/namespace : pousser MAINTENANT sous 0xcssh (intérimaire), garder Phenicea comme cible (supersède partiellement le namespace figé de l'entrée « Phase 3b »)

**Décision :**

**1. Repo & namespace — Option A retenue (pousser maintenant sous `0xcssh`), avec garde-fou de migration explicite.**
- **POUSSER MAINTENANT** le code sous `github.com/0xcssh/agentdata` (l'agent peut le faire seul : `gh` authentifié sur `0xcssh`, scopes repo/workflow suffisent). On ne reste PAS bloqués à attendre la création d'org.
- **Namespace MCP intérimaire = `io.github.0xcssh/agentdata-liquidity-exit-cost`** dans `server.json.name` ET `package.json.mcpName` (l'invariant registre « name === mcpName » doit rester respecté). Idem `repository.url`, `websiteUrl`, `homepage`, `bugs.url` → `0xcssh` (sinon ces URLs sont des 404, ce qui DÉGRADE la crédibilité lue par un agent — un repo réel et public > une jolie URL morte).
- **Phenicea reste la cible de marque durable**, mais on ne fige plus `io.github.phenicea/...` dans le code TANT QUE l'org n'existe pas (l'entrée « Phase 3b » figeait Phenicea ; elle est **superseded sur ce point précis** : le namespace effectif au push est `0xcssh`, Phenicea redevient une cible de migration, pas une valeur committée). Raison du retournement : fait technique nouveau = l'org n'est pas créable par l'agent → figer un namespace non-authentifiable bloque la publication ; un namespace authentifiable maintenant fait courir l'uptime maintenant.
- **Coût de migration vers Phenicea = faible et planifié** : le registre permet de republier (nouvelle entrée qui supersède), et le repo se transfère/forke (`gh repo transfer` ou recréation sous l'org). C'est de la config + re-listing, **pas une réécriture de code**. On l'assume.

**2. Repo PUBLIC au push (pas privé — Option C écartée).**
- Le listing MCP référence `repository.url` ; un agent (et un humain qui évalue) peut lire le repo. **Public = crédibilité + lisibilité par agent** (CLAUDE.md §10 : la doc/le code lisibles directement comptent pour être *choisi*). Un repo privé derrière auth = invisible au lecteur machine = anti-découvrabilité.
- Rien dans le repo n'expose d'argent réel : `.gitignore` exclut les secrets, aucune clé wallet committée, mode testnet par défaut, garde-fous mainnet doubles (vérifié entrée Phase 2). Donc aucun risque à le rendre public. (Si un doute subsiste sur un secret résiduel → cto-agent fait un scan avant `git push` ; voir Handoff.)
- Privé « pour préparer » (Option C) n'apporte rien ici : ça retarde le bénéfice de crédibilité sans réduire un risque réel, et il faudra le rendre public de toute façon pour le listing.

**3. Ce qu'on demande au fondateur, dans l'ordre (du plus débloquant au moins urgent) :**
- **(P1 — débloque l'uptime, le plus urgent) Déployer sur Render** sous son compte (Render exige le compte fondateur). C'est ce qui fait *démarrer le compteur 3 j* — le vrai goulot. Sans déploiement, ni 0xcssh ni phenicea ne changent quoi que ce soit.
- **(P2 — débloque la marque, non bloquant pour l'uptime) Créer l'org GitHub `phenicea`** (+ réserver le scope npm `@phenicea`). Dès qu'elle existe, on migre le namespace `0xcssh → phenicea` (re-listing). Si `phenicea` est pris → `phenicea-ai`/`phenicea-labs`.
- **(P3 — inchangé, parallèle) Wallet Base Sepolia financé** pour l'E2E testnet → prérequis listing #2 (Bazaar). N'affecte pas le listing #1.
- Ordre justifié : le North Star des premiers mois = fiabilité + découvrabilité + historique d'uptime qui court. Le déploiement (P1) est le seul qui fait courir le temps ; la marque (P2) est durable mais non bloquante et migrable ; le wallet (P3) sert un listing ultérieur.

**Pourquoi :**
- **Vitesse > esthétique de marque au stade actuel.** Le namespace n'est PAS un critère mécanique de sélection des agents (prix/latence/fiabilité/schéma le sont — CLAUDE.md §10, et North Star §3 de ma définition). Or l'historique d'uptime, lui, EST un actif qui se construit dans le temps réel et qu'on ne peut pas rattraper. Chaque jour d'attente sous Option B = un jour d'historique perdu pour zéro gain de sélection. Mauvais arbitrage.
- **Un repo réel sous 0xcssh > un namespace phenicea fantôme.** Ce qu'un agent « voit » de mieux, ce n'est pas le mot « phenicea » dans une chaîne — c'est un repo public lisible, une doc markdown brute, un schéma propre, un endpoint qui répond 200. Option A délivre tout ça maintenant ; Option B délivre une belle chaîne pointant vers du vide.
- **La migration est bon marché et le registre est conçu pour ça** (supersede). On ne se peint pas dans un coin : on garde Phenicea comme destination, on y va dès que l'org existe, sans bloquer le chemin critique entre-temps.
- **Pleinement dans mon mandat** : tout est gratuit, testnet, réversible. Aucune dépense, aucun mainnet, aucun vrai USDC. Pousser un repo public et figer un namespace authentifiable = décisions business/distribution = mon domaine.

**Hypothèses & risques :**
- Hypothèse : `0xcssh/agentdata` n'existe pas déjà / le nom est libre sous ce compte. Sinon → suffixe (`agentdata-mcp`) et ajuster les URLs en conséquence.
- Risque : on publie le listing #1 sous `io.github.0xcssh/...` puis on migre vers phenicea → **double entrée registre / churn de namespace** visible. Mitigé : (a) on n'aura probablement pas encore `mcp-publisher publish` (le gate 3 j + l'auth GitHub ne tombent qu'après) — donc l'idéal est de **migrer AVANT le publish si l'org phenicea arrive à temps** ; (b) si phenicea n'est pas prête au moment du feu vert 3 j, on publie sous 0xcssh (mieux vaut listé que pas listé) et on supersède plus tard. **Règle de décision** : publier sous le namespace de la marque si elle est prête à l'instant du publish ; sinon publier sous 0xcssh sans attendre.
- Risque : exposition publique de code immature (testnet/preview) → réputation. Mitigé par le libellé honnête « Testnet / preview » déjà présent dans la description, et par le fait que le code est testé (103 tests verts).
- Risque secret résiduel dans l'historique git au moment du push public → cto-agent scanne avant push (gitleaks/`git log` des fichiers sensibles). `.gitignore` déjà en place mais on vérifie l'historique, pas juste le working tree.
- Risque identité : pousser sous le compte perso du fondateur (`0xcssh`) lie le projet à son identité GitHub perso plutôt qu'à une marque neutre. Acceptable au stade testnet/preview ; résolu par la migration vers l'org `phenicea`.

**Succès mesuré par :**
- Repo public live sous `github.com/0xcssh/agentdata`, lisible (README, docs markdown, llms.txt visibles), zéro secret committé (scan propre).
- `server.json.name` === `package.json.mcpName` === `io.github.0xcssh/agentdata-liquidity-exit-cost` ; plus aucune URL pointant vers `phenicea` (404) tant que l'org n'existe pas ; `repository.url`/`websiteUrl` résolvent en 200.
- Déclencheur listing #1 armé une fois Render déployé : **3 j d'uptime applicatif sans régression de schéma** → publish (sous phenicea si prête, sinon 0xcssh).
- Migration : quand l'org phenicea existe, repo transféré + namespace re-figé en `io.github.phenicea/...` + (si déjà listé) nouvelle entrée registre qui supersède. Coût = config/re-listing, pas de réécriture.

**Handoff :** voir bloc Handoff CTO + demandes humaines ci-dessous.

## 2026-06-16 — CEO — Handoff consolidé → cto-agent (push 0xcssh, repo public, namespace intérimaire)

À traiter par `cto-agent` (le « comment »). **Aucune touche mainnet, aucune dépense, tout réversible.**

**A. Re-figer le namespace en intérimaire `0xcssh` (avant le push) :**
1. `server.json` : `name` → `io.github.0xcssh/agentdata-liquidity-exit-cost` ; `websiteUrl` et `repository.url` → `https://github.com/0xcssh/agentdata` (et `.url` du repo). NE PAS toucher `remotes[0].url` (reste `PLACEHOLDER-RENDER-HOST` jusqu'au déploiement Render — étape humaine P1).
2. `package.json` : `name` → `@0xcssh/agentdata-liquidity-exit-cost` (ou garder un nom local non-scopé si `@0xcssh` pose souci — npm non requis pour le listing #1, c'est de la réservation) ; `mcpName` → `io.github.0xcssh/agentdata-liquidity-exit-cost` (DOIT être identique à `server.json.name`) ; `repository.url`, `homepage`, `bugs.url` → `0xcssh`.
3. Vérifier l'invariant : `server.json.name` === `package.json.mcpName`.
4. Laisser le code clairement migrable : pas de hardcode du namespace ailleurs que dans ces deux manifests (de sorte que la future migration phenicea = éditer 2 fichiers + transfert repo).

**B. Pré-push (sécurité, bloquant avant `git push` public) :**
5. **Scanner l'historique git ET le working tree** pour tout secret avant de rendre public : clés wallet, `.env` réel, `FACILITATOR_URL`/`PAY_TO_ADDRESS` non-placeholder, tokens. Confirmer que `.gitignore` exclut bien `.env` et secrets (déjà noté en place — re-vérifier l'historique, pas que le HEAD). Si un secret a déjà été committé → ne PAS pousser, nettoyer l'historique d'abord (ou repartir d'un repo neuf sans historique sale).
6. Vérifier que `NETWORK_MODE=testnet` par défaut, `ALLOW_MAINNET` absent, `X402_ENABLED=false` par défaut, garde-fous mainnet doubles intacts (entrée Phase 2) — rien ne doit exposer d'argent réel dans un repo public.

**C. Créer + pousser le repo PUBLIC sous 0xcssh :**
7. `gh repo create 0xcssh/agentdata --public` (vérifier d'abord que le nom est libre ; sinon `agentdata-mcp` et ajuster les URLs de A). Pousser le code (branche par défaut). Vérifier que README, `llms.txt`, `docs/api.md`, OpenAPI sont visibles dans le repo public et que `repository.url`/`websiteUrl` résolvent en 200.
8. **Ne pas** publier sur npm ni `mcp-publisher publish` maintenant (le publish attend le déploiement Render + 3 j uptime, et idéalement le namespace de marque). Le push repo n'est PAS la publication registre.

**D. Après déploiement Render (étape humaine P1) — inchangé vs entrée précédente :**
9. Quand l'URL Render est connue : `remotes[0].url` = `https://<render-host>/mcp` ; OpenAPI `servers[]` + liens absolus `llms.txt` → host public ; rejouer le test discovery contre l'URL publique (tous liens 200). Keep-alive gratuit (cron-job.org / UptimeRobot) sur `/health` ~10 min.
10. Laisser courir le monitoring → **3 j uptime sans régression de schéma** → feu vert publish.

**E. Migration phenicea (quand l'org existe — étape humaine P2) :**
11. `gh repo transfer` (ou recréation) `0xcssh/agentdata → phenicea/agentdata` ; re-figer `server.json.name`/`package.json.mcpName` en `io.github.phenicea/agentdata-liquidity-exit-cost` ; mettre à jour les URLs repo. Si déjà listé au registre sous 0xcssh → nouvelle entrée phenicea qui supersède (re-listing, pas réécriture).
12. **Règle de timing du publish** : si l'org phenicea est prête à l'instant où le gate 3 j tombe → publier directement sous phenicea (éviter le double-listing). Sinon → publier sous 0xcssh sans attendre, migrer ensuite.

**F. Escalades humaines (ne PAS décider côté agents) :**
- **P1 (déploiement Render)** : compte fondateur requis → action humaine. C'est le déblocage prioritaire (fait courir l'uptime).
- **P2 (org GitHub `phenicea` + scope npm `@phenicea`)** : création web only → action humaine. Non bloquant pour le push 0xcssh ni pour l'uptime.
- **P3 (wallet Base Sepolia financé)** : inchangé → débloque E2E testnet → listing #2 Bazaar.
- **Inchangé** : plan payant (si free tier ne tient pas 3 j), domaine custom (marque), mainnet/vrai USDC → tous escalade humain. Mainnet verrouillé (double garde).

## 2026-06-16 — BUILD — Repo poussé sur GitHub (interim namespace 0xcssh)

**Fait par l'agent (dans son mandat, zéro argent) :** application de la décision CEO (Option A). Namespace re-figé
`io.github.0xcssh/agentdata-liquidity-exit-cost` (server.json + package.json mcpName + test_deploy + contact OpenAPI),
103 tests verts, scan secrets négatif, repo git init + 2 commits, **repo PUBLIC créé et poussé** :
https://github.com/0xcssh/agentdata (branche master). `remotes[0].url` reste placeholder Render.

**Ne PEUT PAS être fait par l'agent (compte/identité/temps réel) — escalades humaines :**
- P1 **Render** : déployer (compte fondateur) → Blueprint lit render.yaml → fournir l'URL. Pour le listing #1,
  X402_ENABLED=false → aucun secret requis (PAY_TO_ADDRESS vide ok, facilitator testnet par défaut).
- P2 **org GitHub `phenicea`** + scope npm `@phenicea` (migration de marque, non bloquante).
- P3 **wallet Base Sepolia financé** (E2E testnet → listing #2 Bazaar).
- Création d'org GitHub = web only (token a read:org, pas admin:org) ; pas de CLI Render ; 3 j uptime = temps réel.

**Reste agent après P1 :** remplacer le placeholder par l'URL Render dans server.json/OpenAPI/llms.txt, keep-alive
/health, puis (après 3 j uptime) préparer `mcp-publisher`. Mainnet toujours verrouillé.

## 2026-06-16 — CEO — Migration vers Phenicea MAINTENANT (org créée avant tout déploiement) — supersède le point « namespace intérimaire 0xcssh » de l'Option A

> **Supersession explicite.** Cette décision **supersède le point namespace** de l'entrée « Option A » du
> 16/06 (« 2026-06-16 — CEO — Repo/namespace : pousser MAINTENANT sous 0xcssh »). Le namespace intérimaire
> `io.github.0xcssh/...` était conditionné à « TANT QUE l'org phenicea n'existe pas ». **Fait nouveau :
> l'org `phenicea` existe, l'agent (compte 0xcssh) y est admin.** La condition de l'intérim tombe → on
> exécute la migration prévue par l'Option A elle-même (qui désignait Phenicea comme cible et la migration
> comme « config + re-listing, pas une réécriture »). Tout le reste de l'Option A (repo public, escalades,
> ordre P1/P3) **reste en vigueur**.

**Décision :**

**1. A1 — MIGRER MAINTENANT vers `io.github.phenicea/...`. (Recommandé. A2 = rester sous 0xcssh : REJETÉE.)**
- On re-fige le namespace de marque **maintenant**, parce que la fenêtre est idéale : l'org est prête
  **AVANT** tout déploiement Render, tout uptime, et toute publication registre. C'est le moment où la
  migration coûte **le strict minimum absolu** :
  - **aucune entrée registre à superséder** (rien n'est encore publié via `mcp-publisher`) → zéro double-listing, zéro churn de namespace visible ;
  - **aucun uptime à redémarrer** (le compteur 3 j n'a pas commencé : Render n'est pas déployé) → on ne perd pas un seul jour d'historique ;
  - **aucune URL Render live à repointer** (`remotes[0].url` est encore un placeholder).
- Migrer plus tard (après déploiement/uptime/publish) coûterait au contraire : re-listing registre + churn visible + risque de repointer une URL en prod. **Donc migrer maintenant élimine toute migration future** et donne la marque dès le jour 1. C'est l'arbitrage que l'Option A appelait elle-même de ses vœux (« migrer AVANT le publish si l'org arrive à temps ») — l'org est arrivée à temps, et même bien plus tôt qu'espéré.
- **A2 rejetée** : rester sous 0xcssh n'a de sens QUE comme intérim pour ne pas bloquer l'uptime. Or rien n'est bloqué par la migration ici (elle est plus rapide que d'attendre le déploiement). Garder 0xcssh maintenant ne ferait que **garantir** une migration future plus coûteuse, sans aucun bénéfice. C'est le mauvais côté de l'arbitrage.

**2. Méthode = T (TRANSFÉRER le repo `0xcssh/agentdata` → `phenicea/agentdata`). (Recommandé. F = repo neuf : REJETÉE.)**
- **`gh repo transfer 0xcssh/agentdata --new-owner phenicea`** (l'agent est admin sur l'org → faisable sans escalade). Le transfert GitHub : (a) **préserve l'historique** des 2 commits ; (b) crée une **redirection automatique** `0xcssh/agentdata → phenicea/agentdata` (les anciens liens ne meurent pas — important car `repository.url` a pu être vu/indexé) ; (c) ne laisse **pas de doublon** sous 0xcssh.
- Ensuite : re-figer le namespace en `io.github.phenicea/...` dans `server.json` + `package.json` (+ tout autre fichier référençant 0xcssh : `test_deploy`, contact OpenAPI, liens llms.txt/docs), mettre à jour le **remote git local** (`git remote set-url origin https://github.com/phenicea/agentdata.git`), commit + push.
- **F (repo neuf + re-push) rejetée** : plus « simple » en apparence mais (i) **pas de redirection** → les liens 0xcssh deviennent morts ou trompeurs ; (ii) **laisse `0xcssh/agentdata` en doublon public** (deux repos du même projet = bruit, ambiguïté pour un agent/humain qui évalue, anti-lisibilité — contraire à CLAUDE.md §10) ; (iii) perd la continuité d'historique. Le transfert est strictement supérieur ici et tout aussi gratuit/réversible.
- Garde-fou : avant transfert, re-confirmer qu'aucun secret n'est dans l'historique (déjà scanné négatif à l'entrée « Repo poussé », mais le push de migration touche au public → re-vérifier le HEAD au moins). Vérifier aussi que le nom `phenicea/agentdata` est libre (l'org est neuve, donc oui sauf collision improbable).

**3. npm `@phenicea` — RÉSERVER MAINTENANT (publication = plus tard, non bloquante).**
- **Réserver le scope/nom maintenant** : c'est gratuit, ça verrouille la marque sur npm avant un éventuel squat, et ça s'aligne sur le re-fige du `package.json` qu'on fait de toute façon dans cette migration (coût marginal nul). Concrètement : renommer `package.json` en `@phenicea/agentdata-liquidity-exit-cost` (cohérence de marque), garder `private:false`.
- **Mais ne PAS mettre la publication npm sur le chemin critique** : rappel confirmé en doc live (entrée « Namespace Phenicea » du 16/06) — un serveur **remote** (`remotes[].type=streamable-http`) se liste au MCP Registry **avec une simple URL, sans package npm publié**. Le listing #1 = `server.json` remote + `mcp-publisher publish`. npm ne sert qu'à une install stdio locale qu'on n'offre pas.
- **Sur la réservation effective du nom sur npm** : `npm publish` réel sous `@phenicea` exige un compte npm + une org/scope npm créée par le fondateur. Si ce n'est pas déjà fait → **micro-escalade (compte, pas argent)** : créer le scope npm `@phenicea`. Tant que ce n'est pas fait, on fige juste le **nom** dans `package.json` (réservation « intention de marque » dans le code) sans publier. Publier le placeholder npm peut se faire plus tard, hors chemin critique. **Recommandation : réserver le nom dans le manifest maintenant, créer le scope npm quand le fondateur passe (non urgent), publier seulement si/quand utile.**

**Pourquoi :**
- **La fenêtre actuelle rend la migration gratuite et définitive.** L'Option A avait raison de ne pas attendre l'org pour faire courir l'uptime — mais l'org est arrivée **avant** que l'uptime ne démarre. Donc l'unique justification de l'intérim (ne pas perdre de temps d'historique) ne s'applique plus : migrer maintenant ne coûte aucun jour d'uptime. On capture le bénéfice de marque dès le jour 1 **sans payer le coût** que l'intérim était censé éviter.
- **Cohérence avec le North Star (CLAUDE.md §4, §3 def CEO)** : le namespace n'est pas un critère mécanique de sélection (prix/latence/fiabilité/schéma le sont). Donc on ne se précipite PAS pour la marque au détriment de l'uptime — ici il n'y a pas d'arbitrage, les deux vont dans le même sens : migrer maintenant ne retarde rien et supprime un futur churn de namespace (qui, lui, *pourrait* être lu comme un signal d'instabilité).
- **Pleinement dans le mandat CEO** : transfert de repo + re-fige de namespace + réservation de nom = gratuit, testnet, réversible, distribution/marque = mon domaine. Aucune dépense, aucun mainnet, aucun vrai USDC. L'admin sur l'org rend le transfert exécutable par l'agent sans escalade (≠ création d'org, qui exigeait le fondateur).

**Hypothèses & risques :**
- Hypothèse : `gh repo transfer` vers une org où l'agent est admin réussit sans intervention humaine (admin org = droit de recevoir un transfert + créer des repos). Si GitHub exige une acceptation côté org / un scope `admin:org` que le token n'a pas → **fallback escalade légère** : le fondateur clique « accept transfer » (ou fait le transfert depuis l'UI), puis l'agent reprend le re-fige namespace. Ne PAS basculer vers F (repo neuf) pour contourner — ça perd la redirection ; préférer l'acceptation humaine du transfert.
- Risque : le scope npm `@phenicea` n'est pas encore créé → on ne peut que figer le nom dans le manifest, pas publier. Acceptable (npm hors chemin critique). Documenté comme micro-escalade compte.
- Risque : références résiduelles à `0xcssh` ailleurs que les 2 manifests (tests, OpenAPI contact, liens llms.txt/docs) → un grep exhaustif `0xcssh` doit revenir vide après migration, sinon URLs incohérentes. À vérifier (cf. Handoff).
- Risque : la redirection GitHub se casse si quelqu'un recrée plus tard un repo `0xcssh/agentdata`. Faible (compte perso du fondateur, pas de raison de recréer). Acceptable.
- Inchangé : tout le reste de l'Option A tient (repo public = crédibilité, garde-fous mainnet doubles, P1 Render = vrai goulot de l'uptime, P3 wallet = listing #2).

**Succès mesuré par :**
- `phenicea/agentdata` existe, public, historique préservé, **redirection `0xcssh/agentdata` → `phenicea/agentdata` active** (l'ancien lien résout en 200/redirige), **pas de doublon** `0xcssh/agentdata` laissé tel quel.
- `server.json.name` === `package.json.mcpName` === **`io.github.phenicea/agentdata-liquidity-exit-cost`** ; `grep -ri 0xcssh` sur le repo = **vide** (plus aucune URL/namespace 0xcssh) ; `repository.url`/`websiteUrl` → `github.com/phenicea/agentdata` résolvent en 200 ; `remote origin` local pointe sur phenicea ; 103 tests toujours verts.
- npm : nom figé `@phenicea/agentdata-liquidity-exit-cost` dans `package.json` (réservation de marque). Publication npm = optionnelle, hors chemin critique.
- **Conséquence durable : plus AUCUNE migration de namespace à prévoir.** Quand le gate 3 j uptime tombera (après déploiement Render), on publie directement sous phenicea — un seul listing, aucun supersede.

**Handoff :** voir bloc Handoff CTO ci-dessous.

## 2026-06-16 — CEO — Handoff consolidé → cto-agent (migration 0xcssh → phenicea, exécutable maintenant)

À traiter par `cto-agent` (le « comment »). **Aucune touche mainnet, aucune dépense, tout réversible. L'agent est admin sur l'org `phenicea` → le transfert est dans le mandat (pas d'escalade), sauf si GitHub exige une acceptation côté org (fallback humain ci-dessous).**

**A. Pré-migration (avant le transfert) :**
1. Re-confirmer **aucun secret** au HEAD (et idéalement historique) : pas de `.env` réel, pas de `PAY_TO_ADDRESS`/`FACILITATOR_URL` non-placeholder, pas de clé wallet. (Scan déjà négatif à l'entrée « Repo poussé » — re-vérifier le HEAD au minimum avant un push public de migration.)
2. Confirmer que le nom `phenicea/agentdata` est **libre** dans l'org (org neuve → normalement oui).

**B. Transférer le repo (méthode T) :**
3. `gh repo transfer 0xcssh/agentdata --new-owner phenicea` (ou équivalent API). Vérifier que la **redirection automatique** `0xcssh/agentdata → phenicea/agentdata` est active (cliquer l'ancien lien doit rediriger).
4. **Si GitHub bloque** (acceptation requise côté org / scope `admin:org` manquant) → **escalade légère** : demander au fondateur d'**accepter le transfert** dans l'UI GitHub (ou de le lancer depuis l'UI). **NE PAS** créer un repo neuf à la place (F) — on tient à la redirection + zéro doublon.
5. Mettre à jour le **remote git local** : `git remote set-url origin https://github.com/phenicea/agentdata.git`.

**C. Re-figer le namespace en `phenicea` (dans le code) :**
6. `server.json` : `name` → `io.github.phenicea/agentdata-liquidity-exit-cost` ; `websiteUrl` et `repository.url` → `https://github.com/phenicea/agentdata`. **NE PAS toucher** `remotes[0].url` (reste `PLACEHOLDER-RENDER-HOST` jusqu'au déploiement Render — étape humaine P1).
7. `package.json` : `name` → `@phenicea/agentdata-liquidity-exit-cost` ; `mcpName` → `io.github.phenicea/agentdata-liquidity-exit-cost` (DOIT être identique à `server.json.name`) ; `repository.url`, `homepage`, `bugs.url` → `phenicea`.
8. Vérifier l'invariant registre : `server.json.name` === `package.json.mcpName`.
9. **Grep exhaustif `0xcssh`** sur tout le repo (code, tests, OpenAPI contact, llms.txt, docs/api.md, README) → remplacer **toutes** les occurrences résiduelles par `phenicea`. Le grep final doit revenir **vide**. (L'entrée « Repo poussé » mentionne test_deploy + contact OpenAPI parmi les fichiers touchés au moment du fige 0xcssh — les re-cibler.)
10. Re-lancer la suite : **103 tests doivent rester verts** ; schéma API inchangé ; garde-fous mainnet intacts (NETWORK_MODE=testnet défaut, ALLOW_MAINNET absent, X402_ENABLED=false défaut).
11. Commit (« migrate namespace 0xcssh → phenicea ») + push sur `phenicea/agentdata`.

**D. npm (réservation de marque, hors chemin critique) :**
12. Garder le nom `@phenicea/agentdata-liquidity-exit-cost` figé dans `package.json` (fait en C7). **Ne PAS** `npm publish` maintenant (listing #1 = remote URL, npm non requis). Publication npm = optionnelle ultérieure, sous le scope `@phenicea` (création du scope npm = micro-escalade compte fondateur, non urgente).

**E. Après déploiement Render (étape humaine P1) — inchangé :**
13. URL Render connue → `remotes[0].url` = `https://<render-host>/mcp` ; OpenAPI `servers[]` + liens absolus `llms.txt` → host public ; rejouer le test discovery (tous liens 200) ; keep-alive `/health` (~10 min). Puis 3 j uptime → `mcp-publisher login github` (org `phenicea`) + `publish` (libellé testnet/preview). **Plus aucun arbitrage de timing de namespace** : on publie directement sous phenicea, un seul listing.

**F. Escalades humaines (ne PAS décider côté agents) :**
- **P1 (déploiement Render)** : compte fondateur requis → action humaine. Reste le **vrai goulot** qui fait courir l'uptime. Inchangé, prioritaire.
- **Acceptation transfert GitHub** (seulement si le transfert auto échoue, B4) : clic fondateur dans l'UI. Léger.
- **Scope npm `@phenicea`** (seulement si/quand on veut publier npm) : création compte/scope = fondateur. Non urgent, hors chemin critique.
- **P3 (wallet Base Sepolia financé)** : inchangé → E2E testnet → listing #2 Bazaar.
- **Inchangé** : plan payant (si free tier ne tient pas 3 j), domaine custom (marque `com.phenicea`/`ai.phenicea`), mainnet/vrai USDC → tous escalade humain. Mainnet verrouillé (double garde).

## 2026-06-16 — BUILD — Migration namespace → io.github.phenicea (org créée)

Le fondateur a créé l'org GitHub `phenicea` ; l'agent y est admin. Décision CEO (A1+T) exécutée :
- Repo **transféré** `0xcssh/agentdata` → **`phenicea/agentdata`** (public, historique préservé, redirection auto active).
- Namespace re-figé partout en **`io.github.phenicea/agentdata-liquidity-exit-cost`** (server.json, package.json
  name `@phenicea/...` + mcpName, test_deploy, contact OpenAPI ; grep `0xcssh` vide hors journal). remote git mis à jour.
- 103 tests verts, commit + push sur phenicea. `remotes[0].url` toujours placeholder Render.
- Plus aucune migration de namespace à prévoir : publication future directement sous phenicea (un seul listing).

## 2026-06-16 — BUILD — Service LIVE sur Render (testnet) + URL branchée

Déployé et **vérifié en prod** : https://agentdata-liquidity-exit-cost.onrender.com
- `/health` 200 (testnet), `/pricing` 200 ($0), `/v1/liquidity/exit-cost` 200, `/llms.txt` 200 (text/plain),
  `/docs/api.md` 200, `/openapi.json` 200 (champ `servers` présent), handshake MCP `/mcp/ initialize` 200.
- Correctif prod appliqué : résolution robuste des artifacts (llms.txt/docs via fallback CWD) car install
  non-editable ne copie pas les fichiers repo-root dans site-packages. URL réelle branchée dans server.json
  (remote `…/mcp`), OpenAPI `servers[]`, llms.txt (liens absolus).
- `autoDeploy: true` activé (push → déploiement auto ; à appliquer via un resync Blueprint).

**Reste pour listing #1 :** keep-alive `/health` (~5-10 min, free tier dort à 15 min) → 3 j d'uptime → `mcp-publisher
login github` (org phenicea) + publish. npm `@phenicea` optionnel. E2E testnet (option C) attend le wallet Sepolia.

## 2026-06-16 — CEO — E2E 402 en LOCAL (Option A), Render reste payments-OFF pour le listing #1

> **Fait nouveau :** le fondateur a fourni l'**adresse PUBLIQUE** de wallet Base Sepolia
> **`0x5E442c144687De1D311855d65E87584BdEe7541A`**, financée ~0,1 testnet ETH (gas). Pas de clé privée
> partagée (correct, CLAUDE.md §14 — la clé reste locale, jamais en chat/repo). Cette adresse devient le
> **`PAY_TO_ADDRESS` du projet** (côté VENDEUR). Toujours **testnet** (Base Sepolia `eip155:84532`),
> mainnet verrouillé.

**Décision :**

**1. Où valider l'E2E 402 = Option A — EN LOCAL. (Recommandée. B = activer x402 sur Render : REJETÉE. C = 2e instance Render : REJETÉE pour l'instant.)**
- L'E2E 402 → pay → serve se valide **en local** : `X402_ENABLED=true` + `NETWORK_MODE=testnet` +
  `PAY_TO_ADDRESS=0x5E44…` côté serveur (lancé localement par l'agent/le fondateur), facilitator testnet
  `x402.org`. Le fondateur joue l'**acheteur** avec sa clé privée en **env local uniquement** (jamais en
  chat/repo) et signe le paiement testnet.
- **Le service Render LIVE reste `X402_ENABLED=false`** (payments OFF) — inchangé. Le listing #1 (MCP
  Registry) n'exige PAS le 402 ; activer x402 sur Render renverrait un 402 à toute requête
  `/v1/liquidity/exit-cost`, ce qui **casse l'attente « endpoint data sans paiement »** du listing #1 ET
  **perturbe le compteur d'uptime/découvrabilité en cours** (le keep-alive ping `/health`, mais un agent qui
  teste `/v1/liquidity/exit-cost` tomberait sur un 402 inattendu → signal de fiabilité dégradé).
- **B rejetée** : sacrifier le « no-402 » du listing #1 pour valider un flux qui se valide aussi bien en
  local = mauvais arbitrage (on casse l'actif qui court — l'uptime/découvrabilité — pour zéro gain qu'on ne
  puisse obtenir en local).
- **C rejetée pour l'instant** : une 2e instance Render dédiée paiements ajoute coût/complexité (et un 2e
  service free-tier qui dort + un 2e keep-alive) pour une validation qui n'a pas besoin d'être publique. On
  ne déploie une instance « démo paiements » publique QUE si, plus tard, un canal (BlockRun, ou une démo
  Bazaar) exige une URL 402 live montrable — à ce moment-là, ce sera une décision séparée (et toute version
  always-on payante = escalade humain).

**2. Ordre vs listing #1 = on NE casse PAS le chemin critique. Le compteur 3 j (payments OFF) reste prioritaire ; l'E2E 402 se fait EN PARALLÈLE en local.**
- Le **compteur d'uptime 3 j** (listing #1, Render payments-OFF) continue **sans interruption** — c'est
  l'actif qui court dans le temps réel et qu'on ne peut pas rattraper (North Star CLAUDE.md §4 : fiabilité +
  découvrabilité d'abord). On ne touche à rien sur Render.
- L'**E2E 402 local** avance **en fond**, sans bloquer ni perturber le listing #1. Il débloque le **listing
  #2 (Bazaar)**, qui exige le flux 402 validé end-to-end testnet (décision listing du 16/06). Les deux
  pistes sont indépendantes : listing #1 ne dépend pas du 402, listing #2 en dépend.

**3. Périmètre d'E2E « suffisant » pour débloquer le listing #2 Bazaar :**
- **Minimum requis (gate listing #2) :** au moins **une transaction testnet complète** où :
  (a) le serveur émet un **402 bien formé** (termes corrects : montant par tier, réseau Base Sepolia
  `eip155:84532`, token USDC testnet, `pay_to` = `0x5E44…`, scheme EVM `exact`) ;
  (b) l'acheteur **signe et paie** sur Base Sepolia ;
  (c) le serveur **vérifie ET settle** la preuve via le facilitator testnet (verify→settle OK) ;
  (d) puis **sert le JSON** exit-cost (200) — le tout au moins **une fois de bout en bout**, prouvé par un
  hash de tx testnet + la réponse servie.
- **Idéalement (non bloquant pour Bazaar mais à faire si peu de coût) :** rejouer pour ≥ 2 tiers (au moins
  `risk` défaut + un autre) pour prouver que **le montant du 402 dépend bien du tier** ; et un cas négatif
  (preuve invalide/rejouée → 402, body non servi) pour prouver le fail-closed. Ces deux derniers points
  recoupent les findings hardening F-4 (anti-rejeu) — bonus, pas un prérequis Bazaar.
- **Point ouvert à trancher pendant l'E2E (doc live, déjà noté Phase 2) :** le facilitator testnet
  accepte-t-il un montant **$0** pour verify/settle ? **Si NON**, fixer un **montant testnet symbolique non
  nul** (USDC de test, jamais de vrai USDC) via config pour valider la vérification → cela peut exiger que le
  fondateur détienne du **test-USDC Base Sepolia** (pas seulement du gas ETH). À déterminer empiriquement au
  premier run ; documenter le résultat dans ce journal.

**Pourquoi :**
- **On protège l'actif qui court (uptime/découvrabilité) sans rien sacrifier.** L'Option A valide exactement
  le même flux que B/C mais en local, donc casser le listing #1 (B) ou payer une 2e instance (C) serait du
  coût/risque pur pour zéro information supplémentaire. Le flux 402 est identique local vs déployé (même code,
  même facilitator testnet, même adresse `pay_to`).
- **Conforme au mandat CEO et aux valeurs** : tout est gratuit, testnet, réversible ; aucune dépense, aucun
  mainnet, aucun vrai USDC. La clé privée reste locale chez le fondateur (CLAUDE.md §14) — l'agent n'exécute
  QUE le côté vendeur (qui n'a besoin que de l'adresse publique) et la préparation/instructions du côté
  acheteur, **jamais** la clé.
- **Séquencement honnête** : listing #1 (le plus fort effet-historique, n'exige pas le 402) reste sur le
  chemin critique ; listing #2 (Bazaar) suit dès l'E2E validé, sans que l'un ralentisse l'autre.

**Hypothèses & risques :**
- Hypothèse : le facilitator testnet `x402.org` accepte `$0` → si NON, fallback = montant testnet symbolique
  + test-USDC requis côté fondateur (ask P-USDC ci-dessous). Risque faible, juste un détour de config.
- Risque : divergence local vs prod. Le code est le même (un seul `app`/`asgi`), seul `X402_ENABLED` diffère →
  ce qui marche en local avec x402=true marchera sur Render si un jour on l'active. Mitigé : on teste le
  **vrai** facilitator testnet, pas un mock, donc l'E2E est représentatif.
- Risque : pour le listing #2 Bazaar, il faudra que l'endpoint de discovery / l'extension bazaar soit
  joignable — à vérifier si Bazaar exige une **URL publique** 402-active pour s'auto-référencer, ou si la
  validation E2E locale + l'opt-in déclaratif suffisent. **Si Bazaar exige une URL publique qui renvoie un
  402**, alors et seulement alors C (instance dédiée paiements) ou une bascule contrôlée redeviennent sur la
  table → décision séparée à ce moment (et toujours sans casser le listing #1 : instance distincte, pas le
  service du listing #1). À lever par cto-agent en doc live avant de conclure Bazaar.
- Risque clé privée : aucune clé ne doit transiter par l'agent/chat/repo. Garde-fou : l'agent fournit des
  **instructions** au fondateur pour l'étape acheteur ; la clé reste en env local chez lui.

**Succès mesuré par :**
- **Listing #1 (inchangé, prioritaire) :** Render reste payments-OFF, `/v1/liquidity/exit-cost` renvoie 200
  (pas 402), compteur 3 j d'uptime sans régression de schéma continue de courir. Aucune perturbation.
- **E2E 402 (gate listing #2) :** au moins **1 transaction testnet** prouvée 402→pay→verify→settle→serve
  (hash tx Base Sepolia + réponse JSON servie), `pay_to` = `0x5E44…`. Idéalement 2 tiers + 1 cas de rejet.
- **Point ouvert tranché :** statut « facilitator accepte $0 ? » documenté (oui → rien à faire ; non →
  montant symbolique + test-USDC), consigné au journal.
- **Listing #2 débloqué :** une fois l'E2E validé, prérequis Bazaar atteint (sous réserve du point « URL
  publique requise ? » à lever).

**Handoff :** voir blocs ci-dessous (cto-agent : partie agent sans clé privée ; fondateur : clé en local + test-USDC éventuel).

## 2026-06-16 — CEO — Handoff → cto-agent (E2E 402 LOCAL, partie agent, SANS clé privée)

À traiter par `cto-agent` (le « comment »). **Aucune touche mainnet, aucune dépense, testnet only. L'agent n'exécute QUE le côté vendeur + la préparation du côté acheteur — la clé privée du fondateur ne transite JAMAIS par l'agent/chat/repo (CLAUDE.md §14).**

**A. NE PAS toucher le service Render (listing #1 protégé) :**
1. Render reste `X402_ENABLED=false`, `NETWORK_MODE=testnet`. Ne PAS activer x402 en prod, ne pas redeployer
   pour les paiements. Le compteur 3 j d'uptime continue de courir sans interruption.

**B. Lancer le serveur VENDEUR en LOCAL avec x402 activé (testnet) :**
2. En local (`.env` local non committé) : `NETWORK_MODE=testnet`, `X402_ENABLED=true`,
   `PAY_TO_ADDRESS=0x5E442c144687De1D311855d65E87584BdEe7541A`, `FACILITATOR_URL` vide (→ défaut testnet
   `https://x402.org/facilitator`), `POOL_SOURCE=fixture`. `ALLOW_MAINNET` absent. Lancer `agentdata.asgi:app`
   localement (uvicorn) et vérifier qu'une requête `/v1/liquidity/exit-cost?...&tier=risk` renvoie bien un
   **402 bien formé** (montant du tier, réseau `eip155:84532`, token USDC testnet, `pay_to`=`0x5E44…`, scheme
   `exact`). C'est la moitié vendeur — **aucune clé privée requise** (l'adresse publique suffit).
3. **Reconfirmer en doc live** (CLAUDE.md §0, ne pas déduire du journal) : la forme exacte des termes 402 du
   SDK x402 2.13 ; et surtout **si le facilitator testnet accepte un montant `$0`** pour verify/settle.
   - Si **$0 accepté** : l'E2E se fait à montant nul, le fondateur n'a besoin que de gas ETH (déjà fourni).
   - Si **$0 refusé** : fixer un **montant testnet symbolique non nul** via config (USDC de test, jamais de
     vrai USDC), strictement séparé du prix mainnet (invariant testnet/mainnet intact). Cela déclenche l'ask
     **test-USDC** au fondateur (côté acheteur). Documenter le choix.
   - Profiter de ce passage (si on touche `pricing_402.py`) pour intégrer **F-2** (invariant testnet/mainnet
     sur `payment_requirements()` + check extra `x402[evm]`) et **F-3** (centraliser `MAX_TIMEOUT_SECONDS`) —
     coût marginal nul (décision séquencement du 16/06).

**C. Préparer (sans exécuter) le côté ACHETEUR pour le fondateur :**
4. Fournir au fondateur des **instructions/un script local** pour jouer l'acheteur : un client x402 testnet
   (CLI/script) qui lit le 402, signe le paiement avec **sa** clé (en **env local chez lui**, ex.
   `PRIVATE_KEY=…` jamais committé/jamais en chat), paie sur Base Sepolia, rejoue la requête avec la preuve.
   L'agent **écrit le script et le doc**, mais **n'exécute pas** l'étape qui consomme la clé. Le script doit
   lire la clé depuis l'env local, jamais d'un argument en clair ni d'un fichier committé.

**D. Exécuter l'E2E + capturer la preuve :**
5. Avec le fondateur jouant l'acheteur en local : dérouler 402 → pay → verify → settle → serve **au moins une
   fois** (tier `risk` par défaut). Capturer : le **hash de tx testnet** Base Sepolia, le 402 émis, et la
   **réponse JSON 200** servie après paiement. Idéalement rejouer pour un 2e tier (prouver montant ∝ tier) et
   un **cas de rejet** (preuve invalide/rejouée → 402, body non servi — recoupe F-4).
6. **Consigner le résultat** dans ce journal (entrée BUILD) : statut « facilitator $0 oui/non », hash(es) de
   tx, tiers couverts, et tout écart. NE PAS committer de clé, de `.env` réel, ni de log contenant une clé.

**E. Lever le point bloquant Bazaar (avant de conclure listing #2) :**
7. En **doc live** (`docs.x402.org/extensions/bazaar`, `/discovery/resources` du facilitator) : déterminer si
   Bazaar exige une **URL publique renvoyant un 402** pour l'auto-référencement, ou si l'E2E validé + l'opt-in
   déclaratif suffisent. **Remonter le résultat au CEO** : si une URL publique 402-active est requise, NE PAS
   l'activer sur le service du listing #1 — ce sera une décision CEO séparée (probablement une instance/route
   dédiée paiements, ou une bascule contrôlée), pour ne jamais casser le listing #1.

**F. Escalades / limites (ne PAS décider ni exécuter côté agent) :**
- **Clé privée acheteur** : exécution LOCALE par le fondateur uniquement. L'agent ne la voit pas, ne la
  stocke pas, ne l'exécute pas.
- **Test-USDC Base Sepolia** : seulement si le facilitator refuse `$0` → ask fondateur (faucet test-USDC).
- **Mainnet / vrai USDC / activation x402 en prod sur le service du listing #1** : escalade / décision CEO
  séparée. Mainnet verrouillé (double garde inchangée).
- **Instance Render dédiée paiements (Option C)** : seulement si Bazaar (ou un autre canal) exige une URL
  publique 402 — décision CEO séparée, jamais sur le service du listing #1.

**Demandes au FONDATEUR (côté acheteur, local) :**
- **Garder la clé privée du wallet `0x5E44…` en LOCAL** (env local, ex. `PRIVATE_KEY`), **jamais** en chat ni
  committée. Lancer l'étape acheteur de l'E2E avec le script fourni par cto-agent quand prêt.
- **Test-USDC Base Sepolia** : à récupérer via un faucet **seulement si** le premier run montre que le
  facilitator testnet refuse un montant `$0` (cto-agent confirmera après B3). Le gas ETH (~0,1) déjà fourni
  couvre la signature/tx ; l'USDC de test ne sert que si un montant symbolique non nul est imposé.
- Rappel : tout ceci reste **testnet** — pas de vrai USDC, pas de mainnet.

## 2026-06-16 — BUILD — E2E côté VENDEUR validé en local (402 bien formé)

PAY_TO_ADDRESS du projet (testnet) = `0x5E442c144687De1D311855d65E87584BdEe7541A` (Base Sepolia, adresse publique ;
clé privée jamais en chat/repo). Décision CEO : E2E en LOCAL (Option A), Render reste payments-OFF (listing #1 protégé).

Vérifié en local (X402_ENABLED=true, NETWORK_MODE=testnet, PAY_TO_ADDRESS=0x5E44…) : `GET /v1/liquidity/exit-cost`
renvoie **HTTP 402 bien formé**, défi dans l'en-tête `payment-required` (base64) :
scheme=exact, network=eip155:84532, asset=0x036CbD…CF7e (**USDC testnet Base Sepolia, auto-résolu**),
amount="0" (prix testnet $0), payTo=0x5E44…541A. Côté vendeur OK, sans clé.

**Ouvert :** le facilitator x402.org accepte-t-il amount="0" ? Sinon → montant testnet symbolique + test-USDC (acheteur).
Prochaine étape : harnais ACHETEUR (script local, clé en env du fondateur) pour dérouler 402→pay→verify+settle→200.

## 2026-06-16 — MILESTONE — E2E x402 testnet VALIDÉ (402 → pay → serve)

Le fondateur a déroulé l'E2E en local (serveur vendeur X402_ENABLED=true + acheteur scripts/e2e_buyer.py, clé en
env local jamais partagée). Résultat : **402 → pay → 200 vérifié sur testnet**, JSON débloqué (token USDX, tier risk).

**Question ouverte tranchée par le run réel :** le facilitator x402.org **testnet accepte un montant `$0`** (run lancé
SANS TESTNET_SYMBOLIC_PRICE_USDC, paiement à 0, settle OK). → Pas besoin de test-USDC ; le repli symbolique reste
disponible mais non requis. Le tx hash n'est pas renvoyé par le facilitator (flux OK quand même).

**Conséquence :** la couche paiement x402 est prouvée de bout en bout (testnet). Le **prérequis du listing #2 (Bazaar)
est levé**. Mainnet toujours verrouillé (double garde). Listing #1 (Render, payments-OFF) inchangé.

## 2026-06-16 — CEO — Topologie Bazaar (listing #2) + séquencement vs listing #1

**Décision :**

**1. Topologie pour le Bazaar = Option A (2e instance Render gratuite dédiée 402/Bazaar), MAIS conditionnée
à une vérif doc live, et seulement APRÈS avoir armé le listing #1. Ordre de préférence tranché : A > C > B.**
- **(B) Activer x402 sur l'instance existante = REJETÉ.** Cela sacrifierait le « endpoint data sans 402 » du
  listing #1 alors que son compteur 3 j d'uptime court en ce moment. On ne casse jamais un actif qui tourne
  pour en démarrer un autre, surtout quand l'isolation est gratuite. (Cf. décision E2E du 16/06 : « jamais sur
  le service du listing #1 ».)
- **(C) Attendre / tout séquentiel = REJETÉ comme posture par défaut.** Le listing #1 et le Bazaar n'ont
  **aucune dépendance technique mutuelle** une fois l'E2E validé (il l'est). Attendre la fin complète du
  listing #1 pour seulement *commencer* à préparer le Bazaar laisse du temps de découvrabilité sur la table
  pour rien. On prépare le Bazaar **en parallèle** ; on l'**active** au bon moment (voir §2).
- **(A) 2e instance Render gratuite `agentdata-pay` (ou nom équivalent) avec `X402_ENABLED=true` +
  `PAY_TO_ADDRESS=0x5E44…`, `NETWORK_MODE=testnet`, payments-actifs, dédiée au 402 public + opt-in Bazaar =
  RETENU** — **MAIS uniquement si la doc live confirme que le Bazaar exige une URL publique renvoyant un 402**
  (point à lever par cto-agent, cf. §3). Même code, même repo, même adresse publique ; seul un flag de config
  diffère entre les deux services. L'instance #1 reste strictement payments-OFF.
- **Si la doc live montre que le Bazaar ne requiert PAS d'URL 402 publique** (opt-in déclaratif côté facilitator
  + ressources déclarées suffisent), alors **on n'a même pas besoin de la 2e instance** : on déclare l'opt-in
  par la voie supportée et on évite d'opérer un 2e service. Dans ce cas A se réduit à « rien à déployer », ce
  qui est encore mieux (moins de surface à maintenir). **C'est pourquoi A est conditionné à la vérif §3 :
  on ne déploie une 2e instance que si elle est réellement nécessaire.**

**2. Séquencement / chemin critique vers « être listé ET choisi » :**
- **Chemin critique = listing #1 (MCP Registry).** Inchangé, prioritaire : laisser courir les **3 j d'uptime
  testnet sans régression de schéma** sur l'instance Render existante (payments-OFF), puis `mcp-publisher
  publish`. C'est le listing à plus fort effet-historique et il n'exige ni 402 réglé ni mainnet. Rien ne doit
  le perturber.
- **Le Bazaar (listing #2) se prépare EN PARALLÈLE, s'active APRÈS le feu vert du listing #1.** Préparation
  (vérif doc live §3 + code d'opt-in/extension bazaar + éventuelle config de la 2e instance) = **maintenant,
  en fond**, sans toucher l'instance #1. Activation (déploiement de la 2e instance si requise + opt-in effectif)
  = **une fois le listing #1 publié** (ou au minimum une fois les 3 j d'uptime atteints), pour ne pas diviser
  l'attention ni risquer une manip sur l'instance #1 pendant que son compteur court.
- **Pourquoi cet ordre et pas l'inverse :** au marché actuel (CLAUDE.md §4), la découvrabilité native MCP
  (Claude et clients MCP) a un public concret aujourd'hui ; le Bazaar est la découverte native x402, à plus
  faible volume actuel mais stratégiquement « être partout ». Le premier débloque de l'historique de fiabilité
  immédiatement et gratuitement ; le second est un ajout de surface. On fait le plus fort effet d'abord, le
  second en recouvrement.

**3. Vérifs doc live AVANT de coder le Bazaar (cto-agent, ne pas deviner — CLAUDE.md §0) :**
- Forme exacte de l'extension « bazaar » sur la `RouteConfig` x402 (SDK 2.13) : nom du champ/flag, structure
  des métadonnées de ressource déclarées (l'agent doit voir prix/réseau/schéma).
- Endpoint `/discovery/resources` du facilitator : qui l'expose (notre service ? le facilitator ?), forme de
  la réponse, et **si l'auto-référencement Bazaar exige que notre endpoint serve publiquement un 402** ou si
  l'opt-in déclaratif suffit. **C'est CE point qui détermine si la 2e instance Render est nécessaire** (§1).
- Source : `docs.x402.org/extensions/bazaar`. Confirmer, ne pas extrapoler du journal.

**Pourquoi :**
- Mandat CEO : tout est **gratuit, testnet, réversible** (free tier, même code, adresse publique uniquement) →
  dans mon périmètre, aucune escalade argent — **sauf** la création de la 2e instance Render par le fondateur
  (action de compte, pas une dépense), et seulement si la vérif §3 la rend nécessaire.
- North Star (CLAUDE.md §4, §9 « sois partout ») : être listé partout sans se disperser. On isole les deux
  listings pour qu'aucun ne mette l'autre en risque, et on séquence par effet décroissant + dépendance.
- Cohérence avec l'acté : la décision E2E du 16/06 disait déjà « si Bazaar exige une URL publique 402, NE PAS
  l'activer sur le service du listing #1 → instance dédiée, décision CEO séparée ». La voici tranchée : oui à
  l'instance dédiée si (et seulement si) requise, jamais sur l'instance #1.

**Hypothèses & risques :**
- Hypothèse : Render permet une **2e Web Service gratuite** sous le même compte sans CB. Si le free tier est
  limité à un seul service actif / impose une CB pour le second → fallback : (a) déclarer l'opt-in Bazaar sans
  2e service si la doc le permet, sinon (b) **escalade humain** pour un petit plan payant (cohérent avec la
  bascule déjà prévue). On tente le gratuit d'abord.
- Risque : opérer 2 services double la surface d'uptime à surveiller. Mitigé : keep-alive gratuit sur les deux
  `/health`, monitoring déjà en place ; l'instance #2 n'est pas sur le chemin critique du listing #1.
- Risque : divergence de config entre les deux instances (l'une OFF, l'autre ON). Mitigé : un seul repo, un
  seul code, la seule différence est `X402_ENABLED` (+ pas d'`ALLOW_MAINNET` nulle part). Mainnet verrouillé
  des deux côtés (double garde inchangée).
- Risque : si on déploie la 2e instance avant la vérif §3 et qu'elle s'avère inutile → surface gaspillée.
  Mitigé : §1 ordonne explicitement de **ne déployer la 2e instance qu'après confirmation qu'elle est requise**.

**Succès mesuré par :**
- **Listing #1 (prioritaire, inchangé) :** instance Render existante payments-OFF, `/v1/liquidity/exit-cost`
  → 200 (pas 402), compteur 3 j d'uptime sans régression atteint → `mcp-publisher publish` exécuté.
- **Vérif §3 levée :** statut « Bazaar exige-t-il une URL publique 402 ? oui/non » documenté au journal, avec
  la forme exacte de l'extension bazaar et de `/discovery/resources`.
- **Listing #2 (Bazaar) :** apparition de notre ressource dans le catalogue Bazaar via `/discovery/resources`
  (testnet), opt-in effectif, **sans** que l'instance #1 ait jamais quitté l'état payments-OFF.

**Handoff :** voir bloc Handoff CTO ci-dessous + demande au fondateur.

## 2026-06-16 — CEO — Handoff → cto-agent (préparer le Bazaar, instance #1 protégée)

À traiter par `cto-agent` (le « comment »). **Aucune touche mainnet, aucune dépense, testnet only. NE JAMAIS
activer x402 sur l'instance Render du listing #1 (elle reste `X402_ENABLED=false`, compteur 3 j en cours).**

**A. Lever le point bloquant en DOC LIVE (à faire EN PREMIER, avant tout code Bazaar) :**
1. Sur `docs.x402.org/extensions/bazaar` (+ introspection SDK x402 2.13) : confirmer **(a)** la forme exacte de
   l'extension « bazaar » sur la `RouteConfig` (champ/flag, métadonnées de ressource : prix par tier, réseau
   `eip155:84532`, token USDC testnet, schéma) ; **(b)** le rôle/forme de `/discovery/resources` du facilitator ;
   **(c) LE point décisif : le Bazaar exige-t-il que notre endpoint serve publiquement un 402, ou l'opt-in
   déclaratif suffit-il ?** Remonter la réponse au CEO — c'est elle qui décide si on déploie une 2e instance.

**B. Préparer le code d'opt-in Bazaar (sans déployer la 2e instance pour l'instant) :**
2. Implémenter l'extension bazaar sur la `RouteConfig` selon la forme confirmée en A, avec les métadonnées de
   ressource répliquées depuis la **table de prix unique** (`api/pricing.py`) — pas de divergence. Garder ça
   derrière le flag `X402_ENABLED` (donc inactif sur l'instance #1, actif seulement là où x402 est ON).
3. Si l'implémentation touche `pricing_402.py`/la table de prix : intégrer au passage **F-2** (invariant
   testnet/mainnet sur `payment_requirements()` + check extra `x402[evm]`) et **F-3** (centraliser
   `MAX_TIMEOUT_SECONDS`) — coût marginal nul (décision séquencement 16/06).

**C. Si (et seulement si) A.(c) montre qu'une URL publique 402 est requise → préparer la 2e instance :**
4. Préparer la config de déploiement d'une **2e Web Service Render gratuite** (`agentdata-pay` ou équivalent),
   **même repo/même code**, variables : `X402_ENABLED=true`, `NETWORK_MODE=testnet`,
   `PAY_TO_ADDRESS=0x5E442c144687De1D311855d65E87584BdEe7541A`, `FACILITATOR_URL` vide (→ défaut testnet),
   `POOL_SOURCE=fixture`, **pas d'`ALLOW_MAINNET`**. Brancher un keep-alive gratuit sur son `/health`.
   **Ne PAS la créer/déployer toi-même** : fournir le `render.yaml`/instructions au fondateur (création de
   service = action de compte côté fondateur).
5. Une fois la 2e instance live (par le fondateur) : y brancher l'URL publique dans la config Bazaar / l'opt-in,
   vérifier que `GET /v1/liquidity/exit-cost` y renvoie un **402 bien formé** publiquement, et que la ressource
   apparaît via `/discovery/resources`. **Capturer la preuve** (402 public + entrée discovery) au journal.

**D. Séquencement d'activation (respecter l'ordre CEO) :**
6. La **préparation** (A, B, et C-config) se fait **maintenant, en parallèle**, sans toucher l'instance #1.
   L'**activation** du Bazaar (déploiement effectif de la 2e instance + opt-in live) se fait **après** le feu
   vert du listing #1 (3 j uptime atteints / `mcp-publisher publish`), pour ne pas diviser l'attention pendant
   que le compteur du listing #1 court.

**E. Escalades / limites (ne PAS décider ni exécuter côté agent) :**
- **Mainnet / vrai USDC / activation x402 sur l'instance #1** : interdit. Mainnet verrouillé (double garde).
- **Plan Render payant** : seulement si le free tier refuse une 2e instance → escalade humain.
- **Clé privée** : jamais côté agent (l'instance vendeur n'a besoin que de l'adresse publique `0x5E44…`).

**Demande au FONDATEUR (le cas échéant) :**
- **Conditionnelle** — seulement si cto-agent confirme (point A.c) qu'une **URL publique 402 est requise** pour
  le Bazaar : **créer une 2e Web Service Render gratuite** (`agentdata-pay`) depuis le même repo, avec les
  variables fournies par cto-agent (`X402_ENABLED=true`, testnet, `PAY_TO_ADDRESS=0x5E44…`). C'est une **action
  de compte gratuite** (free tier, pas de CB attendue) — **pas une dépense**. Si Render impose une CB pour un
  2e service, **ne rien payer sans validation** : remonter au CEO (escalade plan payant).
- **Inconditionnel :** continuer à laisser courir les **3 j d'uptime** sur l'instance #1 (payments-OFF) — c'est
  le chemin critique. Ne pas y toucher.
- Rappel : tout reste **testnet** — pas de vrai USDC, pas de mainnet.

## 2026-06-16 — CTO (doc live) — Mécanique du Bazaar (listing #2)

Vérifié sur docs.x402.org/extensions/bazaar :
- Extension déclarative : `extensions.bazaar.info` (input/output schemas) sur la RouteConfig + serviceName/tags/iconUrl optionnels.
- `/discovery/resources` servi par le **facilitator** (liste les services « enregistrés via ce facilitator »).
- **Non confirmé par la doc** : si un endpoint public renvoyant un 402 en live est requis, et le mécanisme exact
  d'enregistrement auprès du facilitator. Trou de spec — ne pas deviner.
- Inférence (à confirmer empiriquement) : découverte = via facilitator ; notre E2E était en localhost (inatteignable
  par le facilitator) → il faut probablement un endpoint **public, payments-ON**, interagissant avec x402.org →
  **2e instance Render (option A CEO)**. Décision finale d'instance après confirmation.

**Statut listing #2 :** prêt à préparer (extension bazaar codable derrière X402_ENABLED, inactive sur listing #1) ;
activation après le feu vert du listing #1 (chemin critique = 3 j uptime + publish MCP Registry).

## 2026-06-16 — CEO — Listing #2 (Bazaar) : ATTENDRE x402.org (Option A), ZÉRO engagement CDP

> **Fait vérifié en live (ce jour) :** `GET https://x402.org/facilitator/discovery/resources`
> renvoie toujours `308 → 404` (page HTML « This page could not be found »), idem
> `https://x402.org/discovery/resources`. Le catalogue de découverte Bazaar n'est PAS servi par le
> facilitator x402.org testnet aujourd'hui (« Bazaar in early development », cf. CTO doc live du 16/06).
> Notre côté est prêt : extension déclarative `extensions.bazaar.info` codée derrière `X402_ENABLED`,
> E2E 402→pay→serve validé testnet, `scripts/check_bazaar_discovery.py` en place (exit code 3 = endpoint
> non servi = attendu). Le SEUL maillon manquant est externe : le facilitator ne publie pas encore le catalogue.

**Décision : (A) ATTENDRE que x402.org expose `/discovery/resources`. (B) évaluer/utiliser le facilitator
CDP = REJETÉE maintenant. Hybride limité au seul monitoring, voir ci-dessous.**

- **On NE déploie PAS la 2e instance maintenant.** L'instance dédiée 402/Bazaar (`agentdata-pay`, option A de
  l'entrée « Topologie Bazaar ») ne sert à rien tant qu'aucun facilitator n'indexe le catalogue : un endpoint
  public renvoyant un 402 sans catalogue qui le référence = surface opérée pour zéro découvrabilité. Le code
  (extension déclarative + `render-bazaar.yaml`) reste **prêt à déployer le moment venu** ; le déclencheur de
  déploiement = « x402.org sert `/discovery/resources` en JSON » (ou un autre facilitator non-custodial le sert).
- **On N'ENGAGE RIEN côté CDP (Coinbase) pour l'instant — confirmé.** Pas de compte CDP créé, pas de clé/API CDP,
  pas de bascule de facilitator vers CDP, aucune dépense, aucun KYC. Raison : (1) la valeur non négociable du
  projet est **non-custodial + pas de dépense + testnet d'abord** (def CEO, CLAUDE.md §8/§14) ; un facilitator
  CDP peut impliquer un compte Coinbase Developer Platform / une custody / des conditions à vérifier — on ne
  s'engage pas dans cette dépendance pour un listing #2 dont le North Star dit qu'il est secondaire au stade
  actuel. (2) Le bénéfice est faible et incertain : même si CDP servait déjà le catalogue Bazaar, le volume de
  découverte Bazaar aujourd'hui est marginal vs le listing #1 (MCP Registry), qui est le chemin critique.
  (3) Changer de facilitator nous ferait diverger du facilitator testnet déjà validé E2E (x402.org) sans gain
  proportionné. → **CDP = porte fermée pour l'instant ; sa réévaluation est elle-même une décision CEO séparée,
  et toute étape qui impliquerait un compte/custody/coût = escalade humain.**
- **Hybride retenu (le seul) : surveillance passive.** On garde `scripts/check_bazaar_discovery.py` et on
  surveille périodiquement l'endpoint. La seule « ouverture » vers CDP autorisée sans engagement est une
  **vérification en lecture seule** : pointer le script sur un éventuel facilitator CDP public
  (`--facilitator <url>`) pour CONSTATER s'il sert le catalogue — un simple HTTP GET, sans compte, sans clé,
  sans paiement. Cela INFORME une future décision, ça n'engage rien. Si un jour un facilitator non-custodial
  (x402.org OU autre) sert le catalogue sans compte/KYC/coût, on rouvre le dossier topologie.

**Pourquoi (lié au North Star) :**
- North Star des premiers mois (CLAUDE.md §4) = **fiabilité + découvrabilité + positionnement**, marché petit,
  **ne pas se disperser**. Le chemin critique aujourd'hui est le **listing #1 (MCP Registry, publish ~19 juin)**
  dont le compteur 3 j d'uptime court en temps réel — c'est l'actif qu'on ne peut pas rattraper. Le Bazaar est
  bloqué par une dépendance **externe** qu'aucune action de notre part ne débloque (le facilitator ne sert pas
  le catalogue). Dépenser de l'attention (et a fortiori s'engager sur CDP) pour contourner un blocage externe à
  faible enjeu = exactement la dispersion que le North Star proscrit.
- « Sois partout » (CLAUDE.md §9) reste vrai, mais « partout » se construit **quand chaque canal est joignable**,
  pas en forçant un canal mort. Notre coût marginal pour être sur le Bazaar le jour J est **quasi nul** (déployer
  une 2e instance gratuite à partir de code déjà écrit) — donc attendre ne coûte rien et ne nous fait rien perdre.
- Valeurs : rester sur le facilitator non-custodial déjà validé (x402.org testnet) > prendre une dépendance
  custody/compte (CDP) pour un gain marginal. Cohérent avec « non-custodial, pas de dépense, testnet d'abord ».

**Hypothèses & risques :**
- Hypothèse : x402.org finira par exposer `/discovery/resources` (Bazaar « in early development » → publié à terme).
  Risque : délai inconnu, possiblement long. Mitigation : la surveillance périodique nous fait basculer en mode
  « déployer » dès que c'est dispo, sans avoir mobilisé d'effort entre-temps ; et le listing #1 (le canal à effet
  concret aujourd'hui) avance indépendamment.
- Risque : un concurrent se référence sur le Bazaar avant nous via CDP. Faible enjeu au volume actuel ; et notre
  positionnement (schéma propre, prix/latence/fiabilité) prime sur l'ordre d'arrivée dans un catalogue naissant.
  Si la surveillance révèle que CDP sert le catalogue ET que des services data s'y listent réellement, on rouvre
  la décision (réévaluation CDP = entrée CEO séparée + vérif compte/KYC/coût avant tout engagement).
- Risque : oublier de surveiller → on rate la fenêtre d'ouverture. Mitigé par la cadence ci-dessous (légère,
  soutenable) et par le fait que le script est déjà prêt et scriptable.

**Cadence de surveillance de `/discovery/resources` :**
- **Hebdomadaire** tant que l'endpoint renvoie 404 (exit code 3). Une fois/semaine = suffisant pour un endpoint
  « in early development » sans changement annoncé ; ne consomme aucune attention. Run :
  `python scripts/check_bazaar_discovery.py --json` (et, opportunément, contre un facilitator CDP public en
  lecture seule si une URL est connue : `--facilitator <cdp_url>`).
- **Resserrement à immédiat** dès tout signal externe (annonce x402.org/Bazaar GA, changelog, mention que
  `/discovery/resources` est servi) → re-check sur-le-champ et, si le catalogue répond en JSON (exit code 0 ou 2),
  bascule en mode déploiement (voir « listing #2 done » ci-dessous).
- Réévaluation de la cadence si toujours 404 après ~6-8 semaines : reconfirmer en doc live que le mécanisme
  d'enregistrement n'a pas changé (CLAUDE.md §0, ne pas deviner) — le script teste la dispo, pas le protocole.

**Critère « listing #2 (Bazaar) done » :**
1. Un facilitator **non-custodial** (x402.org en priorité ; sinon un autre **sans compte/KYC/coût** — sinon
   escalade) sert `/discovery/resources` en JSON ;
2. notre 2e instance (`agentdata-pay`, testnet, `X402_ENABLED=true`, `PAY_TO_ADDRESS=0x5E44…`) est déployée et
   renvoie publiquement un **402 bien formé** sur `/v1/liquidity/exit-cost`, avec l'extension `bazaar` déclarée ;
3. `scripts/check_bazaar_discovery.py` retourne **exit code 0 (FOUND)** : notre ressource apparaît dans le
   catalogue via `/discovery/resources` (matchée par nom OU URL) ;
4. le tout **sans jamais** avoir fait quitter à l'instance #1 son état `payments-OFF` (listing #1 protégé).
Tant que (1) est faux, listing #2 = « bloqué externe, prêt côté nous » — état acceptable et explicitement non
sur le chemin critique.

**Confirmation explicite (Option A) : ZÉRO engagement côté CDP à ce stade.** Aucun compte CDP, aucune clé, aucun
KYC, aucune dépense, aucune bascule de facilitator. La seule interaction tolérée avec CDP est un GET de lecture
seule à fin de constat via le script de surveillance. Toute utilisation réelle de CDP = décision CEO séparée +
escalade humain si elle implique compte/custody/coût.

**Succès mesuré par :**
- Listing #1 reste sur le chemin critique, non perturbé (publish MCP Registry ~19 juin atteint).
- Surveillance Bazaar effective : check hebdo loggé ; bascule immédiate prévue si l'endpoint s'ouvre.
- Aucun artefact CDP créé (vérifiable : pas de compte/clé/config CDP dans le repo ni côté fondateur).
- Le jour où `/discovery/resources` est servi : critère « listing #2 done » (1→4) atteint au coût marginal
  d'un déploiement free-tier déjà préparé.

**Handoff :**
- **cto-agent :** RIEN à activer maintenant. Garder l'extension bazaar derrière `X402_ENABLED` (inactive sur
  l'instance #1) et `render-bazaar.yaml` prêts. Exécuter la **surveillance hebdomadaire**
  `python scripts/check_bazaar_discovery.py --json` (consigner brièvement le résultat ; pas besoin d'une entrée
  par run tant que c'est « 404/exit 3 »). Si un facilitator CDP public est connu, un GET lecture seule
  `--facilitator <url>` est autorisé pour CONSTAT uniquement (aucun compte/clé). Dès qu'un facilitator
  non-custodial sert le catalogue en JSON → remonter au CEO pour déclencher le déploiement de la 2e instance.
  Ne PAS s'engager côté CDP, ne PAS toucher l'instance #1, mainnet verrouillé.
- **Fondateur :** aucune action requise pour le Bazaar maintenant. Continuer à protéger le listing #1
  (instance #1 payments-OFF, 3 j uptime → publish ~19 juin). La 2e instance Render ne sera demandée que le jour
  où l'endpoint de découverte s'ouvre (action de compte gratuite, free tier ; toute CB/plan payant = escalade).
  Ne créer AUCUN compte CDP/Coinbase Developer Platform pour ce projet sans décision CEO préalable.

## 2026-06-16 — MILESTONE — Math AMM PROUVÉE contre l'oracle on-chain réel (+ finding bloquant résolu)

Audit sécurité du pipeline « parallel-hardening » a trouvé 1 bloquant (high) : la vérif AMM-vs-onchain était
**tautologique** (le « ground truth » recopiait la formule de amm.py) et **ne couvrait pas v3**.

**Corrigé :** `scripts/verify_amm_onchain.py` + `tests/test_amm_onchain.py` réécrits pour comparer amm.py au
**`getAmountOut` réel des pools Aerodrome déployés** (oracle indépendant = code du contrat on-chain), en lecture seule
(RPC public Base, aucun fonds). Adresses vérifiées en eth_call (pas devinées) :
- Volatile WETH/USDC `0xcDAC…C43` (fee 30 bps) → **0,0000 bps** d'écart sur 0.1/1/10/100 WETH.
- Stable USDC/USDbC `0x27a8…B2bD` (fee 5 bps, courbe Solidly x³y+xy³ = notre code non trivial) → **0,0000 bps**.
worst deviation = 0,0000 bps → PASS. L'exactitude (argument de vente) est donc **prouvée empiriquement**.

**Scope honnête (finding v3) :** amm.py n'implémente que VOLATILE + STABLE. v3/CL n'a pas de formule fermée → serait
sourcé via QuoterV2 (extension planifiée, NON implémentée). Description OpenAPI corrigée pour ne plus survendre v3.

**Autres livrables du pipeline (commités) :** PaymentRail (`payment/rail.py` interface + X402Rail délégation) +
`NOTES_RAILS.md` ; tests edge/erreurs + `chain/onchain.py` durci (ChainError clair sur RPC down/pool vide) ;
dashboard `/dashboard` + `monitoring/logging_setup.py` ; landing `/` ; runbooks `docs/publish-mcp-registry.md` +
`docs/publish-npm.md`. **175 tests verts** (vérif on-chain incluse), listing #1 intact (X402 off, $0, schéma inchangé).

## 2026-06-18 — CEO — Gate uptime listing #1 : on PUBLIE MAINTENANT (~46h), gate 72h levé

> **Supersède** le déclencheur « 3 jours (72h) d'uptime testnet sans régression de schéma » fixé dans
> l'entrée du 2026-06-16 (« Ordre & stratégie de listing », critère #1 du listing MCP Registry) et repris
> dans les Handoff CTO suivants. Le reste de cette entrée (libellé testnet/preview honnête, namespace
> phenicea, instance #1 payments-OFF) reste inchangé.

**Décision : publier le listing #1 (MCP Registry) MAINTENANT, à ~46h de stabilité démontrée, sans attendre
les 72h.** Dès que les 3 vérifs pré-publication ci-dessous sont OK (toutes vérifiées en live ce jour, voir
plus bas), le fondateur exécute `mcp-publisher login github` (org `phenicea`) + `mcp-publisher publish`.
Tout reste **testnet** ; mainnet verrouillé (double garde inchangée).

**Pourquoi :**
- Le gate 72h n'était pas un seuil du registre — le MCP Registry **n'impose aucun minimum d'uptime**
  (publication = `server.json` valide + OAuth GitHub, confirmé). C'était une **règle interne** que je m'étais
  donnée pour une seule raison : la sélection des agents est mécanique sur la fiabilité (CLAUDE.md §10, §13) —
  protéger la réputation naissante contre le scénario « listé puis down ».
- Ce risque est **déjà couvert autrement** à 46h : (a) ~46h de stabilité continue effectivement démontrée
  (UptimeRobot keep-alive actif), (b) incident 405 sur HEAD `/health` réglé, (c) E2E x402 testnet validé,
  (d) exactitude AMM prouvée empiriquement (0,0000 bps vs `getAmountOut` on-chain réel). La barre 72h était
  un **proxy** de « c'est stable » ; on a maintenant la **preuve directe** de stabilité. Tenir un proxy
  arbitraire alors que la chose qu'il mesure est démontrée = optimiser un rituel, pas le risque réel.
- North Star honnête (CLAUDE.md §4) : les premiers mois, la fonction-objectif est **être listé + fiable +
  découvrable**, pas le revenu. L'**historique de fiabilité de l'entrée registre commence à courir au moment
  du publish**, pas avant. Chaque jour d'attente = un jour d'historique de réputation perdu, sur un actif
  (l'ancienneté/track-record de l'entrée) qu'on **ne peut pas rattraper plus tard**. `total_calls=0`
  aujourd'hui est normal et ne change rien : on ne peut pas être *choisi* tant qu'on n'est pas *découvrable*.
- Asymétrie du risque : si après publish le service flanchait, le listing reste **dépublia­ble/corrigeable**
  (c'est du testnet/preview, libellé honnête, zéro USDC, zéro utilisateur lésé) — coût réputationnel réel
  ~nul à ce stade sans trafic. À l'inverse, 26h d'attente supplémentaires ne nous apprennent **rien de
  nouveau** (46h sans régression dit déjà l'essentiel) et coûtent du temps d'historique. Décision claire :
  la vitesse de positionnement l'emporte, le garde-fou réputation est satisfait autrement.

**Vérifs pré-publication — à confirmer juste avant `publish` (toutes OK en live ce 2026-06-18) :**
1. `GET` ET `HEAD /health` → **200** (network=testnet, pool_source=fixture). ✅
2. `GET /v1/liquidity/exit-cost?token=USDX&size=5000` → **200, PAS 402** (instance #1 reste payments-OFF) et
   payload = schéma complet attendu (exit_cost / route / fragility / depeg), donnée **calculée** (USDX
   ~4 bps + depeg≈0), pas un prix brut. ✅
3. Handshake MCP **streamable-http → 200** et tous les liens de découverte 200 (`/llms.txt`, `/docs/api.md`,
   `/openapi.json`, `/pricing` = $0). ✅ ; `server.json` : `name` === `package.json.mcpName` ===
   `io.github.phenicea/...`, et `repository.url`/`websiteUrl` (`github.com/phenicea/agentdata`) résolvent
   **200** (pas de 404 qui dégraderait la lecture par un agent). ✅

**Deux frictions mineures relevées en live (NON bloquantes — à régler au passage, pas un report) :**
- ⚠️ **`remotes[0].url` = `.../mcp` (sans slash final) renvoie 307** ; `.../mcp/` renvoie 200. Un client
  streamable-http conforme suit le 307, mais un 307 dès le handshake est une aspérité inutile pour un
  sélecteur mécanique. **Reco : faire pointer `remotes[0].url` sur `.../mcp/`** (ou rendre `/mcp` 200 sans
  redirect) avant publish. Coût ~nul, supprime toute ambiguïté. → Handoff cto-agent.
- ℹ️ **`/metrics.uptime_seconds` se réinitialise à chaque cold start** (éviction du process sur Render free
  tier — observé 62 s). Donc le « 167536 s ≈46h » **ne vient pas du compteur in-process** mais bien du
  moniteur externe (UptimeRobot) + cohérence des 200/schéma. C'est exactement la définition d'« uptime
  applicatif » actée le 16/06 (décision Render). **Ne pas se fier au compteur in-process** comme preuve
  d'uptime ; la preuve = moniteur externe + 200 cohérents + schéma stable. Sans incidence sur la décision.

**Hypothèses & risques :**
- Hypothèse : publier en **testnet/preview** avec libellé honnête ne nuit pas à la réputation tant que le
  service répond et que le schéma est stable — conditions remplies. Risque résiduel (service down post-publish)
  = couvert par keep-alive + dépublication possible + zéro trafic réel à léser.
- Risque : friction 307 sur `/mcp` casse un client MCP strict. Faible (le protocole suit les redirects), mais
  on l'élimine par la reco ci-dessus avant publish → risque ramené à ~0.
- Risque : régression de schéma silencieuse entre maintenant et le publish. Mitigé : le publish suit
  immédiatement les 3 vérifs ci-dessus ; les exécuter à T-0 du `publish`.

**Succès mesuré par :**
- **Publish atteint :** entrée `io.github.phenicea/agentdata-liquidity-exit-cost` présente et résolvable dans
  le MCP Registry (remote streamable-http), `mcp-publisher publish` retourné OK.
- **Pré-publish vert à T-0 :** les 3 vérifs ci-dessus = 200/schéma OK au moment exact du publish, `remotes`
  pointant sur un endpoint MCP qui répond **200 directement** (pas via 307).
- **Historique qui court :** à partir du publish, le track-record de fiabilité de l'entrée commence — c'est la
  métrique qui compte au stade actuel (pas `total_calls`, encore à 0 et attendu tel quel).

**Handoff :**
- **cto-agent :** (1) faire pointer `remotes[0].url` de `server.json` sur `.../mcp/` (slash final) — ou rendre
  `/mcp` 200 sans redirect — pour supprimer le 307 au handshake ; re-vérifier handshake 200 sur l'URL exacte
  publiée. (2) Rejouer les 3 vérifs pré-publication ci-dessus juste avant le publish (200 + schéma stable +
  liens 200 + `name===mcpName` + URLs repo 200). (3) Ne rien changer d'autre : instance #1 reste
  `X402_ENABLED=false`, $0, mainnet verrouillé. Bazaar (listing #2) inchangé (toujours bloqué externe, en
  veille hebdo).
- **Fondateur :** une fois le slash corrigé et les vérifs vertes → exécuter `mcp-publisher login github`
  (compte/org `phenicea`) puis `mcp-publisher publish` (runbook `docs/publish-mcp-registry.md`), libellé
  testnet/preview. C'est l'unique action humaine restante du listing #1. Reste testnet — **aucun** USDC réel,
  **aucune** bascule mainnet.

## 2026-06-18 — MILESTONE 🚀 — Listing #1 LIVE sur le MCP Registry

`mcp-publisher publish` réussi par le fondateur. **`io.github.phenicea/agentdata-liquidity-exit-cost` v0.1.0**
est résolvable dans le registre (`count:1`), remote `https://agentdata-liquidity-exit-cost.onrender.com/mcp/`,
description 88 car. Découvrable par tout client MCP. Premier canal de découverte ACTIF.

Frictions résolues au publish : (1) description >100 car → raccourcie à 88 ; (2) JWT expiré → re-login ;
(3) 403 namespace org → le fondateur a rendu son appartenance à l'org `phenicea` **publique** (le device-flow ne
voyait que `io.github.0xcssh/*`), puis re-login → token couvrant `io.github.phenicea/*` → publish OK.

Gate 72h levé par le CEO (preuve de stabilité ~46h + tout vert > proxy temporel). Tout reste testnet, mainnet
verrouillé, instance #1 payments-OFF ($0). Prochains canaux : Bazaar (#2, attend /discovery/resources côté x402.org),
BlockRun (#3, contact t.me/bc1max avec le kit docs). npm non requis (serveur remote).
