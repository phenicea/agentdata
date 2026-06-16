# Runbook — Publication au MCP Registry (`mcp-publisher`)

> **Statut : PRÉPARÉ — NON EXÉCUTÉ.** Ce document fournit les commandes exactes.
> **L'authentification GitHub et la publication finale sont des actions du FONDATEUR.**
> Aucun agent ne lance `mcp-publisher login` ni `mcp-publisher publish`.
>
> Source : doc live `modelcontextprotocol.io/registry/{quickstart,authentication,remote-servers,github-actions}`,
> fetchée le 2026-06-16. Toute signature provient de la doc live, jamais devinée (CLAUDE.md §0).

---

## 0. TL;DR — ce qu'on publie

- **Listing #1 = serveur MCP DISTANT (remote).** On liste avec une **URL seule** (`remotes[].type=streamable-http`).
  **Aucun package npm n'est requis** (confirmé doc live `remote-servers`). Le runbook npm
  (`docs/publish-npm.md`) reste **hors du chemin critique** — réservation de marque uniquement.
- Le manifeste est déjà dans le repo : [`../server.json`](../server.json).
  Il utilise le bon schéma live **`2025-12-11`** (et non `2025-10-17` comme noté à tort dans ADR-001 §0 ;
  l'entrée Phase 3 du DECISION_LOG l'avait déjà corrigé).
- Namespace figé : **`io.github.phenicea/agentdata-liquidity-exit-cost`** (GitHub org auth).

---

## 1. Prérequis (gates — à vérifier AVANT de publier)

| Prérequis | Responsable | État |
|---|---|---|
| Org GitHub `phenicea` créée et contrôlée par le fondateur | **HUMAIN** | à confirmer (fallback : `phenicea-ai` / `phenicea-labs`) |
| Service testnet déployé, HTTPS public, `/mcp` joignable (streamable-http) | HUMAIN (déploiement Render) | `remotes[].url` déjà renseigné dans `server.json` |
| **3 jours d'uptime testnet applicatif sans régression de schéma** (keep-alive + monitoring) | déclencheur CEO | gate de publication |
| `mcp-publisher` installé et sur le `PATH` | exécutant (fondateur) | §2 |
| `server.json` valide, `name` == `package.json.mcpName` | fait | vérifié §3 |

> Tant que le gate « 3 j uptime » n'est pas atteint, **ne pas publier** (risque réputation, cf. décision CEO listing).

---

## 2. Installer `mcp-publisher`

### Windows / PowerShell (notre poste)

```powershell
$arch = if ([System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture -eq "Arm64") {"arm64"} else {"amd64"}
Invoke-WebRequest -Uri "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_windows_$arch.tar.gz" -OutFile "mcp-publisher.tar.gz"
tar xf mcp-publisher.tar.gz mcp-publisher.exe
Remove-Item mcp-publisher.tar.gz
# puis placer mcp-publisher.exe sur le PATH (ex. un dossier déjà dans $env:Path)
```

### macOS / Linux

```bash
curl -L "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_$(uname -s | tr A-Z a-z)_$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/').tar.gz" | tar xz mcp-publisher
sudo mv mcp-publisher /usr/local/bin/
# alternative macOS : brew install mcp-publisher
```

### Vérifier l'install

```bash
mcp-publisher --help
# commandes attendues : init, login, logout, publish
```

---

## 3. `server.json` — déjà présent, à vérifier (ne pas régénérer)

Le repo a déjà un [`server.json`](../server.json) correct. **`mcp-publisher init` n'est PAS nécessaire**
(il ne sert qu'à générer un template depuis zéro). Si jamais on régénère :
`mcp-publisher init` produit un template avec
`$schema=https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`.

Pour notre serveur **distant**, on utilise `remotes[]` (PAS `packages[]`). Forme attendue (= état actuel du repo) :

```json
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
  "name": "io.github.phenicea/agentdata-liquidity-exit-cost",
  "description": "...",
  "version": "0.1.0",
  "remotes": [
    { "type": "streamable-http", "url": "https://<render-host>/mcp" }
  ]
}
```

**Avant de publier, confirmer :**
- `name` == `io.github.phenicea/agentdata-liquidity-exit-cost` (préfixe `io.github.<org>` → autorise l'auth GitHub).
- `remotes[].url` pointe sur le **vrai host Render** déployé (pas le placeholder), en HTTPS, et répond sur `/mcp`.
- Invariant registre : `server.json.name` doit être identique à `package.json.mcpName` (vérifié — les deux valent
  `io.github.phenicea/agentdata-liquidity-exit-cost`).

```bash
# Sanity check rapide (lecture seule)
curl -sf "https://<render-host>/mcp" -o /dev/null && echo "remote /mcp reachable"
```

---

## 4. Login GitHub — **ACTION FONDATEUR** (device flow)

⚠️ **NE PAS exécuter par un agent.** Le login ouvre un flux OAuth **device** (et non un redirect) :

```bash
mcp-publisher login github
```

Déroulé attendu (confirmé doc live) :
1. La commande **affiche un code** (user code).
2. Le fondateur ouvre **https://github.com/login/device** dans un navigateur.
3. Il saisit le code, puis **autorise** l'application.
4. L'auth réussit si le compte GitHub possède/contrôle l'org **`phenicea`** et y est membre.
   - GitHub auth autorise le préfixe `io.github.<username>/*` **OU** `io.github.<orgname>/*`.
   - Donc `io.github.phenicea/*` est légitime dès que le fondateur contrôle l'org `phenicea`.
   - **Si mauvais compte / pas membre** → erreur : `You do not have permission to publish this server`.

> Alternative PAT (si device flow indisponible) : `mcp-publisher login github --token $MCP_GITHUB_TOKEN`
> (scopes PAT : `read:org` + `read:user`). Toujours action fondateur.

---

## 5. Publier — **ACTION FONDATEUR**

⚠️ **NE PAS exécuter par un agent.** Une fois loggé et le gate « 3 j uptime » atteint :

```bash
mcp-publisher publish
```

Sortie attendue : `Successfully published` → enregistré sur `https://registry.modelcontextprotocol.io`.

---

## 6. Vérifier la publication (lecture seule — OK pour un agent)

```bash
curl "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.phenicea/agentdata-liquidity-exit-cost"
```

Attendu : l'entrée apparaît avec le `name`, la `version`, et le `remotes[].url` Render.

---

## 7. (Optionnel, PRÉPARÉ seulement) — Publication via GitHub Actions OIDC

Permet de publier depuis un workflow CI **sans secret** (OIDC). À placer dans le repo `phenicea/agentdata`.
OIDC fonctionne aussi pour `io.github.<orgname>` quand le workflow tourne dans un repo de cette org.

```yaml
# .github/workflows/publish-mcp.yml  (PRÉPARÉ — déclenchement manuel)
name: Publish to MCP Registry
on:
  workflow_dispatch:        # jamais auto : déclenchement humain explicite
permissions:
  id-token: write           # requis pour l'OIDC mcp-publisher
  contents: read
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install mcp-publisher
        run: |
          curl -L "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_linux_amd64.tar.gz" | tar xz mcp-publisher
          sudo mv mcp-publisher /usr/local/bin/
      - name: Login (OIDC, no secret)
        run: mcp-publisher login github-oidc
      - name: Publish
        run: mcp-publisher publish
```

> Même en CI : ne l'activer qu'après le gate « 3 j uptime ». Le `workflow_dispatch` garantit un déclenchement humain.

---

## 8. TODO restants (hors de ce runbook — actions humaines / autres blocs)

- [ ] **HUMAIN** : créer/confirmer l'org GitHub `phenicea` (fallback `phenicea-ai`/`phenicea-labs` → ajuster le
  namespace dans `server.json` + `package.json` si fallback retenu, et re-vérifier l'invariant `name == mcpName`).
- [ ] **HUMAIN** : déployer le service testnet sur Render et confirmer que `remotes[].url` (déjà dans `server.json`)
  est bien le host réel et que `/mcp` répond.
- [ ] **Monitoring** : atteindre **3 jours d'uptime applicatif** sans régression de schéma (keep-alive `/health`).
- [ ] **HUMAIN** : exécuter §4 (`login github`, device flow) puis §5 (`publish`).
- [ ] Après publication : vérifier via §6 et consigner le résultat dans `DECISION_LOG.md`.

**Hors périmètre (rappels) :** aucune touche mainnet ; aucun vrai USDC ; npm non requis pour ce listing.
