# Référentiel d'exigences Clawbot

Chaque modification du dépôt commence par une exigence écrite ici, puis par un
test qui échoue, puis par le code qui le fait passer (skill `clawbot-dev-cycle`).

## Format

Un fichier YAML par domaine, nommé `<DOMAINE>.yaml` :

```yaml
domain: TEST
requirements:
  - id: REQ-TEST-001
    title: ...
    statement: ...
    rationale: ...
    sources: [S42]
    safety: false
    method: test
    level: unit
    criterion: ...
    evidence: null
    status: implemented
    approved_by: null
    prompt: P00
```

Champs obligatoires : `id`, `title`, `statement`, `method`, `level`,
`criterion`, `status`.

## Domaines

`ARCH`, `SAFETY`, `DRV`, `EXEC`, `CAPA`, `HEALTH`, `MCP`, `PERC`, `ARM`, `OPS`,
`TEST`, `PERF`, `NET`.

## Numérotation

- `REQ-<DOMAINE>-<NNN>`, `NNN` sur trois chiffres, jamais réutilisé.
- Un identifiant publié ne change plus : on ajoute, on ne renumérote pas.
- Les trous sont normaux (une exigence retirée laisse son numéro vacant).
- Le domaine de l'identifiant doit être celui du fichier (`REQ-TEST-*` dans
  `TEST.yaml`).

## Méthodes

| `method` | Sens | Preuve attendue |
|---|---|---|
| `test` | vérifiable automatiquement | au moins un test marqué `@pytest.mark.req("<ID>")` |
| `inspection` | lecture d'un fichier ou d'une configuration | `evidence` : chemin versionné |
| `analysis` | calcul ou raisonnement documenté | `evidence` : document |
| `demonstration` | essai sur le robot | `evidence` : procédure `tests/hardware/HW-*.md` |

Une exigence `method: test` sans test marqué fait échouer `trace_check.py`.
Une exigence d'une autre méthode sans `evidence` existante fait aussi échouer
le contrôle.

## Statuts

`draft` → `approved` → `implemented` → `verified`.

Une exigence `safety: true` (mouvement, arrêt, bras, arbitre) reste en `draft`
tant que l'opérateur ne l'a pas validée ; `approved_by` porte alors
`"<nom> <date>"`. `trace_check.py` refuse une exigence `safety: true` déjà
couverte par des tests mais encore en `draft`.

## Traçabilité et cliquet

```bash
python3 scripts/trace_check.py --repo . --report
```

Le script vérifie le format, la couverture des exigences `method: test`, la
validité de chaque marqueur `req`, les preuves, et le plafond de tests non
tracés. Le plafond est inscrit dans `requirements/.untraced_baseline` et ne
doit que baisser : on trace les tests existants au fil des prompts, on
n'augmente jamais la valeur pour faire passer `scripts/check.sh`.
