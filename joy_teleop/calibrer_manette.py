#!/usr/bin/env python3
"""Calibration guidée de la manette — à lancer soi-même dans son terminal.

Chaque étape attend une ACTION puis affiche un RETOUR immédiat (« ✅ index 3 »,
« ⚠ même code que A », « ✅ sens inversé ») avant de passer à la suivante. Aucun
délai ne court en arrière-plan : rien ne peut se décaler tant que l'opérateur n'a
pas agi, ou validé avec Entrée.

Ce que la première calibration réelle (2026-11-15) a appris et qui est intégré ici :
  * `T` n'émet rien : il est traité comme un commutateur, pas comme un bouton.
  * `light` n'émet rien : il est noté absent avec sa raison.
  * `L` et `R` sont des boutons ; `ZL` et `ZR` ont une course progressive. La
    procédure le DEMANDE au lieu de le déduire d'un axe qui bouge par accident.
  * un axe jamais balayé (min = max) rend une fonction morte : la procédure
    propose de refaire la mesure.
  * l'IMU n'est plus calibré : il n'apporte rien au pilotage.

Commandes pendant l'attente d'un bouton :
    Entrée  → passer cette entrée (notée ABSENTE avec sa raison)
    q       → abandonner sans écrire de fichier

Usage :
    python3 joy_teleop/calibrer_manette.py
    python3 joy_teleop/calibrer_manette.py --sortie /tmp/essai.yaml
"""

from __future__ import annotations

import argparse
import select
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from calibration import (  # noqa: E402
    AXES_DECLARES,
    compter_appuis,
    ENTREES_DECLAREES,
    ENTREES_GACHETTES,
    SORTIE_DEFAUT,
    Calibration,
    echantillonner,
    surveiller_appui,
    _teleop_active,
    reponse_booleenne,
    trouver_base_hid,
)
from js_lecteur import LecteurJs, lister_manettes  # noqa: E402
from manette_materiel import chemin_sysfs, leds_du_pad, vibration_supportee  # noqa: E402
from retour_force import jouer_rumble  # noqa: E402

LARGEUR = 70
DEBATTEMENT_MINIMUM = 0.5


def titre(texte: str) -> None:
    print("\n" + "═" * LARGEUR)
    print(f"  {texte}")
    print("═" * LARGEUR)


def invite(texte: str) -> None:
    print(f"\n▶ {texte}")


def ok(texte: str) -> None:
    print(f"   ✅ {texte}")


def attention(texte: str) -> None:
    print(f"   ⚠️  {texte}")


def demander_oui_non(question: str) -> bool:
    try:
        return reponse_booleenne(input(f"   {question} (o/n) "))
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def attendre_appui(lecteur, rappel_s: float = 12.0):
    """Attend un appui (ou Entrée = passer, ou q = abandonner).

    Rend ('bouton', index), ('passe', None) ou ('quitter', None).
    """
    depart = dernier_rappel = time.monotonic()
    avant = list(lecteur.etat().boutons)
    while True:
        lus, _, _ = select.select([lecteur.fd, sys.stdin.fileno()], [], [], 0.2)
        if lecteur.fd in lus:
            if not lecteur.lire(0.0):
                raise RuntimeError("manette déconnectée")
            apres = list(lecteur.etat().boutons)
            nouveaux = [i for i, v in enumerate(apres)
                        if v and (i >= len(avant) or not avant[i])]
            if nouveaux:
                return "bouton", nouveaux[0]
            avant = apres
        if sys.stdin.fileno() in lus:
            ligne = sys.stdin.readline()
            if ligne == "":
                return "passe", None
            ligne = ligne.strip().lower()
            if ligne.startswith("q"):
                return "quitter", None
            return "passe", None
        if time.monotonic() - dernier_rappel >= rappel_s:
            print("   … en attente — Entrée pour passer, q pour abandonner")
            dernier_rappel = time.monotonic()
        if time.monotonic() - depart > 900:
            return "passe", None


def attendre_relachement(lecteur, index: int, delai_s: float = 3.0) -> None:
    depart = time.monotonic()
    while time.monotonic() - depart < delai_s:
        if not lecteur.lire(0.02):
            raise RuntimeError("manette déconnectée")
        boutons = lecteur.etat().boutons
        if index >= len(boutons) or not boutons[index]:
            return


def surligner_etat(cal: Calibration) -> str:
    lignes = []
    for index, noms in cal.collisions().items():
        lignes.append(f"⚠ index {index} revendiqué par {', '.join(noms)}")
    if cal.donnees["absents"]:
        lignes.append(f"◦ absents : {', '.join(cal.donnees['absents'])}")
    if cal.donnees.get("reserve"):
        lignes.append(f"◦ réservés : {', '.join(cal.donnees['reserve'])}")
    if not lignes:
        lignes.append("✓ aucune anomalie de code")
    return "\n".join(lignes)


# ── 1. Boutons ──────────────────────────────────────────────────────────────

def phase_boutons(cal: Calibration, lecteur) -> None:
    titre("1/4 — BOUTONS")
    print("Appuie UNE fois sur le bouton demandé, puis relâche.")
    print("Entrée seule = passer cette entrée.  q + Entrée = abandonner.")

    total = len(ENTREES_DECLAREES)
    for rang, (nom, description) in enumerate(ENTREES_DECLAREES, 1):
        cal.declarer_entree(nom)
        invite(f"[{rang}/{total}] {description}")
        genre, index = attendre_appui(lecteur)

        if genre == "quitter":
            raise KeyboardInterrupt
        if genre == "passe":
            if nom == "T":
                if demander_oui_non("T est-il la touche TURBO (elle n'agit qu'avec un autre bouton) ?"):
                    cal.declarer_reserve(
                        "T", "touche TURBO : aucun code propre, arme une répétition "
                             "sur un autre bouton (mesuré en phase 1 bis)")
                    attention("noté TOUCHE TURBO (réservé), pas bouton")
                else:
                    cal.marquer_absent("T", "aucun événement, ne sert pas de turbo")
                    attention("noté ABSENT")
            elif nom == "light":
                cal.marquer_absent("light", "aucun événement : bouton non fonctionnel")
                attention("noté ABSENT (non fonctionnel)")
            else:
                cal.marquer_absent(nom, "passée par l'opérateur (Entrée)")
                attention("passée → notée ABSENTE")
            continue

        resultat = cal.enregistrer_bouton(nom, index)
        if resultat == "alias":
            cible = cal.donnees["aliases"][nom]
            attention(f"index {index} — MÊME CODE que {cible} → enregistré comme alias")
        else:
            ok(f"index {index}")
        attendre_relachement(lecteur, index)


# ── 1 bis. Turbo ────────────────────────────────────────────────────────────

def phase_turbo(cal: Calibration, lecteur) -> None:
    """Caractérise le TURBO : T n'émet rien seul, il arme peut-être un autre bouton.

    Mesure : un bouton maintenu produit UN front 0→1 ; le même bouton en turbo en
    produit plusieurs par seconde. C'est ce qui distingue « T ne fait rien » de
    « T arme un turbo », sans supposition.
    """
    titre("1 bis/4 — MODE TURBO (bouton T)")
    print("T seul n'émet aucun code : on vérifie s'il arme une répétition sur un autre bouton.")
    reference = "A"
    try:
        index = cal.bouton(reference)
    except KeyError:
        attention("bouton A non mesuré : test turbo ignoré")
        return

    input(f"\n   Entrée, puis MAINTIENS {reference} appuyé 2 secondes (sans toucher à T)… ")
    base = compter_appuis(lecteur, index, 2.0)
    ok(f"référence : {base} appui(s) en 2 s")

    invite("Appuie UNE fois sur T, relâche-le, puis maintiens A 2 secondes")
    input("   Entrée quand tu es prêt à maintenir A… ")
    turbo = compter_appuis(lecteur, index, 2.0)

    actif = turbo > base + 1
    if actif:
        attention(f"{turbo} appuis en 2 s → TURBO ARMÉ sur {reference}")
        print("      Pour le couper : refais T puis A, ou maintiens T 5 s (selon le pad).")
        print("      Un turbo actif ferait répéter les ordres du bras : à désactiver.")
    else:
        ok(f"{turbo} appui(s) en 2 s → pas de répétition détectée")
    cal.enregistrer_turbo(bouton="T", actif=actif, repetitions=turbo,
                          reference=reference, duree_s=2.0)


# ── 2. Axes ─────────────────────────────────────────────────────────────────

def mesurer_un_axe(cal: Calibration, lecteur, nom, index, direction, description) -> None:
    while True:
        print(f"\n───── {nom} (index {index}) ─────")
        input("   Entrée, puis NE TOUCHE À RIEN pendant 1 seconde… ")
        repos = echantillonner(lecteur, 1.0, index)
        centre = statistics.fmean(repos)
        bruit = statistics.pstdev(repos) if len(repos) > 1 else 0.0
        ok(f"repos : centre {centre:+.3f}, bruit {bruit:.3f}")

        input(f"   Entrée, puis fais un CERCLE COMPLET avec « {description} »… ")
        balayage = echantillonner(lecteur, 3.0, index)
        mini, maxi = min(balayage), max(balayage)
        debattement = abs(maxi - mini)
        ok(f"débattement : {mini:+.2f} … {maxi:+.2f}")

        input(f"   Entrée, puis POUSSE À FOND vers « {direction} » et maintiens… ")
        extreme = statistics.fmean(echantillonner(lecteur, 1.0, index))
        inverser = extreme < centre
        ok(f"valeur {extreme:+.3f} → sens {'INVERSÉ' if inverser else 'direct'}")

        if debattement < DEBATTEMENT_MINIMUM:
            attention(f"débattement insuffisant ({debattement:.2f}) : cet axe serait MORT")
            if demander_oui_non("Refaire la mesure de cet axe ?"):
                continue
        plancher = 0.5 if nom.startswith("croix") else 0.08
        cal.enregistrer_axe(nom, index=index, centre=centre, minimum=mini,
                            maximum=maxi, zone_morte=max(plancher, 4 * bruit),
                            inverser=inverser)
        return


def phase_axes(cal: Calibration, lecteur) -> None:
    titre("2/4 — AXES (six axes, trois gestes chacun)")
    for nom, index, direction, description in AXES_DECLARES:
        mesurer_un_axe(cal, lecteur, nom, index, direction, description)


# ── 3. Gâchettes ────────────────────────────────────────────────────────────

def phase_gachettes(cal: Calibration, lecteur) -> None:
    titre("3/4 — GÂCHETTES")
    print("Pour chacune : appuie PROGRESSIVEMENT à fond, puis relâche.")
    for nom, description in ENTREES_GACHETTES:
        invite(f"{description} : appuie progressivement à fond, puis relâche")
        axes_bouges = {}
        try:
            index = cal.bouton(nom)
            ecarts = surveiller_appui(lecteur, index, 60.0)
            if ecarts:
                axes_bouges = {str(i): round(v, 3) for i, v in sorted(ecarts.items())}
                ok(f"axes qui bougent : {axes_bouges}")
            else:
                ok("aucun axe ne bouge")
        except KeyError:
            attention("aucune mesure de bouton pour cette gâchette")
        analogique = demander_oui_non(
            "Cette gâchette a-t-elle une course progressive (analogique) ?")
        if analogique:
            attention("notée ANALOGIQUE")
        else:
            ok("notée BINAIRE")
        cal.enregistrer_gachette(nom, analogique=analogique, axes=axes_bouges or None)


# ── 4. Actionneurs ──────────────────────────────────────────────────────────

def phase_actionneurs(cal: Calibration, chemin_pad: str) -> None:
    titre("4/4 — CE QUI PEUT ÊTRE COMMANDÉ")
    noeud = chemin_pad.rsplit("/", 1)[-1]
    base_hid = trouver_base_hid()

    # Vibration : effet joué par ioctl, pas par fftest (qui n'envoie rien quand son
    # entrée est redirigée, et fait conclure à tort que le matériel ne vibre pas).
    if vibration_supportee(chemin_sysfs(noeud, "ff")):
        event = f"/dev/input/{noeud.replace('js', 'event')}"
        print(f"\n   Le noyau annonce FF_RUMBLE ; envoi d'un effet de 600 ms sur {event}.")
        joue = False
        try:
            jouer_rumble(event, 600)
            joue = True
            ok("effet chargé, joué et retiré")
        except OSError as err:
            attention(f"l'effet n'a pas pu être joué : {err}")
        senti = demander_oui_non("As-tu senti la vibration ?")
        cal.donnees["capacites"]["vibration"] = {
            "disponible": True,
            "methode": "evdev EV_FF (ioctl EVIOCSFF)",
            "effet_accepte": joue,
            "verifie": senti,
        }
        if not senti:
            attention("le noyau accepte l'effet mais rien n'est perçu : noté NON vérifié")
    else:
        cal.donnees["capacites"]["vibration"] = {
            "disponible": False, "methode": "evdev EV_FF",
            "raison": "le noyau n'annonce pas FF_RUMBLE"}
        attention("le noyau n'annonce pas FF_RUMBLE")

    # Lumière : les LED du pad sont exposées sous /sys/class/leds, en écriture root.
    leds = leds_du_pad(Path(base_hid)) if base_hid else []
    if leds:
        noms = [p.name for p in leds]
        ok(f"{len(noms)} entrée(s) LED : {noms}")
        cal.donnees["capacites"]["lumieres"] = {
            "disponible": True,
            "entrees": noms,
            "ecriture": "root requis (/sys/class/leds/<nom>/brightness)",
        }
        joueurs = [n for n in noms if "player" in n]
        if joueurs and demander_oui_non("Tester les LED maintenant (nécessite sudo) ?"):
            print("   Relance ce script avec sudo si l'écriture échoue.")
        if joueurs:
            ok("les LED de joueur existent : pilotables, non testées ici")
    else:
        cal.donnees["capacites"]["lumieres"] = {
            "disponible": False,
            "raison": "aucune entrée /sys/class/leds rattachée au pad"}
        attention("aucune LED exposée sous /sys/class/leds")


def main(argv=None) -> int:
    parseur = argparse.ArgumentParser(description="Calibration guidée de la manette")
    parseur.add_argument("--sortie", default=SORTIE_DEFAUT)
    parseur.add_argument("--forcer", action="store_true")
    args = parseur.parse_args(argv)

    titre("CALIBRATION DE LA MANETTE")
    if not args.forcer and _teleop_active():
        print("La téléopération tourne : elle commanderait les servos à chaque appui.")
        print("  sudo systemctl stop clawbot-joy-teleop   (ou --forcer)")
        return 3

    manettes = lister_manettes()
    if not manettes:
        print("Aucune manette sur un nœud /dev/input/jsN.")
        print("  sudo bash joy_teleop/pair_procontroller.sh, puis appuyer sur un bouton")
        return 4

    chemin_pad, nom = manettes[0]
    lecteur = LecteurJs(chemin_pad)
    etat_initial = lecteur.etat()
    cal = Calibration(args.sortie, args.forcer)
    cal.donnees["appareil"] = {
        "nom": nom,
        "js_pad": chemin_pad,
        "nb_axes": len(etat_initial.axes),
        "nb_boutons": len(etat_initial.boutons),
    }
    print(f"\nManette : {nom}  ({chemin_pad})")
    print(f"Forme   : {len(etat_initial.axes)} axes, {len(etat_initial.boutons)} boutons "
          f"— un changement de mode invalidera ce fichier")
    print(f"Sortie  : {args.sortie}")
    print("\nPendant l'attente d'un bouton : Entrée = passer, q + Entrée = abandonner.")

    try:
        phase_boutons(cal, lecteur)
        phase_turbo(cal, lecteur)
        phase_axes(cal, lecteur)
        phase_gachettes(cal, lecteur)
    except KeyboardInterrupt:
        print("\n\nAbandon : aucun fichier écrit.")
        return 130
    except RuntimeError as err:
        print(f"\n\nINTERROMPU : {err}")
        print("Aucun fichier écrit. Réveille la manette (un appui) et relance.")
        return 5
    finally:
        lecteur.fermer()

    phase_actionneurs(cal, chemin_pad)

    titre("RÉSUMÉ")
    print(surligner_etat(cal))
    print(f"\n{len(cal.donnees['boutons'])} boutons, "
          f"{len(cal.donnees['aliases'])} alias, "
          f"{len(cal.donnees['absents'])} absent(s), "
          f"{len(cal.donnees.get('gachettes', {}))} gâchettes typées, "
          f"{len(cal.donnees['axes'])} axes.")

    try:
        chemin = cal.ecrire()
    except RuntimeError as err:
        print(f"\n⚠ ÉCRITURE REFUSÉE : {err}")
        print("  Rien n'a été enregistré. Relance la calibration.")
        return 6

    print(f"\n✅ Écrit : {chemin}")
    print("Essai à blanc, sans le robot (domaine 98) :")
    print("  ROS_DOMAIN_ID=98 ros2 launch joy_teleop/joy_teleop_launch.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
