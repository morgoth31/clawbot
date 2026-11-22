import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_audit import HEADINGS, check  # noqa: E402

REGISTRY = ("| S01 | Nœuds | `ros2 node list` | `raw/X/runtime/01_nodes.txt` | 2026-11-22T11:00:00+01:00 |\n"
            "| S05 | Actions | `ros2 action list` | `raw/X/runtime/05_actions.txt` | 2026-11-22T11:00:00+01:00 |\n")
MERMAID = "\n\n```mermaid\nflowchart LR\n A-->B\n```\n"


def build(tmp_path, raw_ok=True):
    (tmp_path / "raw/X/runtime").mkdir(parents=True)
    (tmp_path / "raw/X/runtime/01_nodes.txt").write_text("/a\n" if raw_ok else "")
    # artefact légitimement vide : aucun serveur d'action dans le graphe
    (tmp_path / "raw/X/runtime/05_actions.txt").write_text("")
    (tmp_path / "00_index.md").write_text(
        "# Index\n\n| ID | Donnée | Commande | Artefact | Horodatage |\n|---|---|---|---|---|\n" + REGISTRY
    )
    for name, heads in HEADINGS.items():
        body = "# Titre\n\n" + "\n\n".join(
            h + "\n\nTexte [S01]." + (MERMAID if h == heads[0] else "") for h in heads
        )
        (tmp_path / name).write_text(body)
    return tmp_path


def test_contrat_des_livrables_est_fige():
    assert {k: len(v) for k, v in HEADINGS.items()} == {
        "01_architecture_factuelle.md": 12,
        "02_analyse_performances_et_concurrence.md": 7,
        "03_audit_robustesse_et_maintenabilite.md": 6,
        "04_cahier_entree_refonte_pour_claude.md": 6,
    }


def test_dossier_conforme_ne_remonte_rien(tmp_path):
    assert check(build(tmp_path)) == []


def test_artefact_vide_declare_ne_signale_rien(tmp_path):
    problems = check(build(tmp_path))
    assert not any("05_actions.txt" in p for p in problems)


def test_livrable_absent_signale(tmp_path):
    root = build(tmp_path)
    (root / "03_audit_robustesse_et_maintenabilite.md").unlink()
    problems = check(root)
    assert any("03_audit_robustesse" in p and "absent" in p for p in problems)


def test_section_manquante_signalee(tmp_path):
    root = build(tmp_path)
    p = root / "02_analyse_performances_et_concurrence.md"
    p.write_text(p.read_text().replace("## 6. Diagnostic priorisé", "## Diagnostic"))
    assert any("Diagnostic priorisé" in x for x in check(root))


def test_source_inconnue_signalee(tmp_path):
    root = build(tmp_path)
    p = root / "01_architecture_factuelle.md"
    p.write_text(p.read_text() + "\nFait sans source [S42].\n")
    assert any("S42" in x for x in check(root))


def test_artefact_vide_signale(tmp_path):
    problems = check(build(tmp_path, raw_ok=False))
    assert any("01_nodes.txt" in p for p in problems)


def test_non_observe_sans_recette_signale(tmp_path):
    root = build(tmp_path)
    p = root / "02_analyse_performances_et_concurrence.md"
    p.write_text(p.read_text() + "\nRéseau : [NON OBSERVÉ / À VÉRIFIER]\n")
    assert any("recette" in x for x in check(root))


def test_non_observe_avec_recette_accepte(tmp_path):
    root = build(tmp_path)
    p = root / "02_analyse_performances_et_concurrence.md"
    p.write_text(p.read_text()
                 + "\nRéseau : [NON OBSERVÉ / À VÉRIFIER] → obtenir : ss -uan\n")
    assert not any("recette" in x for x in check(root))


def test_formulation_speculative_signalee(tmp_path):
    root = build(tmp_path)
    p = root / "03_audit_robustesse_et_maintenabilite.md"
    p.write_text(p.read_text() + "\nLe pilote est probablement en cause [S01].\n")
    assert any("probablement" in x for x in check(root))


def test_diagramme_mermaid_absent_signale(tmp_path):
    root = build(tmp_path)
    p = root / "01_architecture_factuelle.md"
    p.write_text(p.read_text().replace("```mermaid", "```text").replace("flowchart LR", ""))
    assert any("mermaid" in x for x in check(root))


def test_marqueur_cite_entre_accents_graves_ignore(tmp_path):
    root = build(tmp_path)
    p = root / "04_cahier_entree_refonte_pour_claude.md"
    p.write_text(p.read_text()
                 + "\nLes mentions `[NON OBSERVÉ / À VÉRIFIER]` ne sont pas des zéros.\n")
    assert not any("recette" in x for x in check(root))


def test_registre_avec_pipe_echappe_dans_la_commande(tmp_path):
    root = build(tmp_path)
    idx = root / "00_index.md"
    idx.write_text(idx.read_text().replace(
        "`ros2 node list`", "`ros2 node list \\| grep -c .`"))
    assert check(root) == []
