# Runbook E2E testnet — flux x402 `402 → pay → serve` de bout en bout

> Statut : **TESTNET UNIQUEMENT** — Base Sepolia (`eip155:84532`). **JAMAIS de mainnet, jamais de vrai USDC.**
> Ce runbook est pour le **fondateur**, à exécuter **en local**. Le pipeline d'agents ne lance AUCUN
> paiement on-chain (pas de clé, pas de fonds ici) : il produit le harnais ; vous l'exécutez.

Ce document décrit comment valider, contre le vrai facilitator testnet, le flux complet
`402 → paiement on-chain → rejeu → réponse 200 JSON` :

1. (si nécessaire) récupérer de l'USDC de test sur Base Sepolia ;
2. exporter votre clé privée d'acheteur **dans l'environnement local** (jamais committée) ;
3. lancer le serveur vendeur local (x402 activé, testnet) ;
4. lancer le client acheteur `scripts/e2e_buyer.py` ;
5. observer la sortie attendue (`402 → 200`, JSON, tx hash si dispo).

---

## ⚠️ AVERTISSEMENT SÉCURITÉ — CLÉ PRIVÉE (à lire AVANT tout)

- La clé privée de l'acheteur vient **EXCLUSIVEMENT** d'une variable d'environnement locale
  (`PRIVATE_KEY`), lue à l'exécution. **JAMAIS** : en argument CLI, en fichier committé, en valeur
  par défaut, dans un log, dans la sortie console, dans un test.
- N'utilisez **JAMAIS** une clé qui détient ou détiendra du vrai USDC / des fonds mainnet. Créez un
  wallet **jetable, dédié au testnet**, et ne le financez **qu'en monnaie de test** Base Sepolia.
- Ne collez jamais votre clé dans un chat, un ticket, un commit, ou une capture d'écran.
- `scripts/e2e_buyer.py` **ne logge jamais** la clé. Il n'imprime pas non plus l'adresse dérivée
  en clair au-delà du strict nécessaire au diagnostic.
- Si `PRIVATE_KEY` est absente, le script s'arrête avec un message clair (pas de crash obscur).

> Rappel borne projet : ceci reste **du testnet**. Le passage mainnet / vrai USDC est un point
> d'escalade humain, hors de ce runbook (CLAUDE.md §0/§14, ADR-001 §4).

---

## 0. Prérequis

- Python ≥ 3.10 et le projet installé (depuis la racine du repo) :
  ```bash
  pip install -e .
  # SDK acheteur x402 + extra EVM (eth-account, web3) :
  pip install "x402[evm]"
  ```
- Un wallet EVM **jetable** dédié au testnet (adresse + clé privée). NE PAS réutiliser un wallet
  qui touche au mainnet.
- L'**adresse publique** de réception du vendeur (testnet) :
  `0x5E442c144687De1D311855d65E87584BdEe7541A`.
  C'est l'adresse du **vendeur** (`PAY_TO_ADDRESS`) ; elle est **sans rapport** avec la clé de
  l'acheteur.

---

## 1. (Conditionnel) Récupérer de l'USDC de test Base Sepolia

Vous n'avez besoin de fonds de test **que si** vous activez le **montant testnet symbolique**
(voir §3, `TESTNET_SYMBOLIC_PRICE_USDC`). Par **défaut**, le prix testnet est **$0** et aucun fonds
n'est requis — mais il n'est pas confirmé que le facilitator testnet accepte un paiement à $0 (un
`transferWithAuthorization` de valeur 0 est un no-op que certains facilitators refusent). Dans ce cas
seulement, repassez ici, financez le wallet, et activez le montant symbolique.

Pour financer le wallet acheteur jetable :

1. **Gas (ETH Base Sepolia)** : récupérez un peu d'ETH de test via un faucet Base Sepolia
   (ex. faucet Coinbase Developer Platform / Base, ou un faucet Sepolia + bridge testnet).
2. **USDC de test Base Sepolia** : faucet **Circle** — <https://faucet.circle.com> — choisir le
   réseau **Base Sepolia**, coller l'**adresse publique** de votre wallet acheteur jetable.
   Le contrat USDC Base Sepolia est `0x036CbD53842c5426634e7929541eC2318f3dCF7e` (auto-résolu par
   le SDK x402 selon le réseau — vous n'avez pas à le saisir).

> Montant à financer : très faible. Le montant symbolique recommandé est **$0.001** (1000 unités
> atomiques d'USDC 6 décimales), donc quelques cents de test suffisent largement, plus un peu de gas.

---

## 2. Exporter la clé privée acheteur en local (jamais committée)

La clé est lue depuis l'environnement, à l'exécution, **uniquement** chez vous.

bash / zsh (Linux/macOS) :
```bash
export PRIVATE_KEY="0x<votre_cle_privee_de_test_jetable>"
```

PowerShell (Windows) :
```powershell
$env:PRIVATE_KEY = "0x<votre_cle_privee_de_test_jetable>"
```

- Ne mettez **pas** cette ligne dans un fichier committé. Ne la collez nulle part de partagé.
- Vous pouvez la placer dans un `.env` **local non committé** (déjà couvert par `.gitignore`) que
  vous sourcez manuellement — mais ne committez jamais ce fichier.
- Pour effacer la variable après usage : `unset PRIVATE_KEY` (bash) / `Remove-Item Env:PRIVATE_KEY`
  (PowerShell).

---

## 3. Lancer le serveur vendeur local (testnet, x402 activé)

Dans un **premier terminal**, à la racine du repo. Le serveur doit tourner en **testnet** avec le
middleware x402 **opt-in activé** et l'adresse de réception du projet.

Cas par défaut — prix testnet = **$0** (pas de fonds requis) :

bash / zsh :
```bash
X402_ENABLED=true \
NETWORK_MODE=testnet \
PAY_TO_ADDRESS=0x5E442c144687De1D311855d65E87584BdEe7541A \
uvicorn agentdata.api.app:app --host 127.0.0.1 --port 8000
```

PowerShell :
```powershell
$env:X402_ENABLED = "true"
$env:NETWORK_MODE = "testnet"
$env:PAY_TO_ADDRESS = "0x5E442c144687De1D311855d65E87584BdEe7541A"
uvicorn agentdata.api.app:app --host 127.0.0.1 --port 8000
```

Cas de repli — le facilitator refuse $0 → activer le **montant testnet symbolique** (OPT-IN,
testnet uniquement, jamais de vrai USDC). Ajoutez `TESTNET_SYMBOLIC_PRICE_USDC` :

bash / zsh :
```bash
X402_ENABLED=true \
NETWORK_MODE=testnet \
PAY_TO_ADDRESS=0x5E442c144687De1D311855d65E87584BdEe7541A \
TESTNET_SYMBOLIC_PRICE_USDC=0.001 \
uvicorn agentdata.api.app:app --host 127.0.0.1 --port 8000
```

PowerShell :
```powershell
$env:TESTNET_SYMBOLIC_PRICE_USDC = "0.001"
# (+ les 3 variables ci-dessus, puis :)
uvicorn agentdata.api.app:app --host 127.0.0.1 --port 8000
```

Notes :
- `TESTNET_SYMBOLIC_PRICE_USDC` est un opt-in **dédié et explicite**. **Défaut = `0.0`** → prix
  testnet `$0`, comportement inchangé, **listing #1 préservé**. Il n'a **AUCUN effet en mainnet**
  (le garde-fou `safety.guard_network` impose « testnet ⇒ prix forcé à $0 » côté mainnet et refuse
  un démarrage mainnet non autorisé).
- Vérification rapide du serveur (autre terminal) :
  ```bash
  curl -s http://127.0.0.1:8000/health
  curl -s http://127.0.0.1:8000/pricing
  ```
  `/health` doit renvoyer `"network":"testnet"`. `/pricing` reflète le prix actif (0 ou symbolique).
- **NE PAS** mettre `NETWORK_MODE=mainnet` ni `ALLOW_MAINNET=true`. Ce runbook est testnet only.

---

## 4. Lancer le client acheteur

Dans un **second terminal** (avec `PRIVATE_KEY` exportée — §2). Le script lit la clé depuis l'env,
l'URL cible depuis argument/env (défaut `http://127.0.0.1:8000`), le tier en option.

```bash
python scripts/e2e_buyer.py
# ou en ciblant explicitement / en choisissant le tier :
python scripts/e2e_buyer.py --url http://127.0.0.1:8000 --tier risk
```

Ce que fait le script (via le SDK x402 acheteur, EVM `exact`, EIP-3009) :

1. `Account.from_key(os.environ["PRIVATE_KEY"])` — clé lue depuis l'env **uniquement**.
2. Construit le client x402 et enregistre le scheme EVM `exact` pour `eip155:84532`.
3. `GET /v1/liquidity/exit-cost?...` → reçoit un `402` avec les *payment requirements* du vendeur
   (montant, asset USDC, réseau, `pay_to`, nonce, validité).
4. Le **SDK** construit et **signe** le paiement EIP-3009 (`TransferWithAuthorization`) — l'acheteur
   ne choisit jamais le montant, il vient du `402` du serveur.
5. **Rejoue** la requête avec l'en-tête `X-PAYMENT` ; le facilitator `verify` puis `settle`.
6. Affiche le résultat : **status 200**, le **JSON** débloqué (exit-cost / depeg / fragilité), et le
   **tx hash** si le facilitator le renvoie.

> Le montant à payer est **dicté par le serveur** (le `402`). L'acheteur ne le fixe jamais.

---

## 5. Sortie attendue

Cas nominal (`402 → 200`) — exemple indicatif :

```
[e2e] cible : http://127.0.0.1:8000  tier=risk  réseau=eip155:84532 (Base Sepolia)
[e2e] 1er GET  -> 402 Payment Required (paiement requis, construction + signature par le SDK)
[e2e] rejeu    -> 200 OK
[e2e] tx hash  : 0x<hash_de_settlement>          # si renvoyé par le facilitator
[e2e] réponse JSON :
{
  "schema_version": "1.0",
  "tier": "risk",
  "network": "testnet",
  "token": "...",
  "exit_cost": { ... },
  "depeg_risk": { ... },
  "fragility": { ... }
}
[e2e] OK : flux 402 -> pay -> serve validé sur testnet.
```

La clé privée et l'adresse dérivée **n'apparaissent pas** dans la sortie.

---

## 6. Dépannage

| Symptôme | Cause probable | Action |
|---|---|---|
| `PRIVATE_KEY` absente → message d'erreur clair, sortie | clé non exportée dans CE terminal | refaire §2 dans le terminal de l'acheteur |
| Le `402` est rejeté / `settle` échoue sur montant 0 | le facilitator testnet refuse $0 | activer `TESTNET_SYMBOLIC_PRICE_USDC=0.001` côté serveur (§3, repli) et financer le wallet (§1) |
| Erreur fonds / USDC insuffisants | wallet acheteur non financé alors qu'un montant symbolique est actif | financer en USDC de test Base Sepolia (§1) ; vérifier aussi le gas ETH testnet |
| Connexion refusée vers `127.0.0.1:8000` | serveur vendeur non lancé / autre port | relancer §3 ; aligner `--url` du buyer (§4) |
| `402` jamais émis (réponse 200 directe) | `X402_ENABLED` non mis à `true` | relancer le serveur avec `X402_ENABLED=true` (§3) |
| Le serveur refuse de démarrer | `NETWORK_MODE=mainnet` sans `ALLOW_MAINNET` | **rester en testnet** ; ne pas activer le mainnet (hors runbook) |

---

## 7. Après l'E2E

- Effacez la clé de l'environnement (§2 — `unset` / `Remove-Item Env:`).
- Ce qui est **confirmé** par un E2E réussi : le flux `402 → pay → serve` fonctionne de bout en bout
  sur testnet, et si applicable, si le facilitator accepte ou non un montant `$0`.
- Reportez le résultat (et le choix $0 vs symbolique) dans `decisions/DECISION_LOG.md` — c'est le
  prérequis du **listing #2 (Bazaar)**.
- **Mainnet reste verrouillé** : aucune valeur mainnet n'est active, et y passer est une escalade
  humaine séparée (revue sécurité du code qui touche aux fonds).
