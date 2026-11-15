#!/usr/bin/env python3
"""Calibration guidée de la manette — à lancer soi-même dans son terminal.

Chaque étape attend une ACTION, puis affiche un RETOUR immédiat (« ✅ index 3 »,
« ⚠ même code que A », « ✅ sens inversé ») avant de passer à la suivante. Aucun
délai ne court en arrière-plan : rien ne peut se décaler tant que l'opérateur n'a
pas agi, ou n'a pas validé avec Entrée.

Commandes pendant l'attente d'un bouton :
    Entrée  → passer cette entrée (elle sera notée ABSENTE, avec sa raison)
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
    ENTREES_DECLAREES,
    ENTREES_GACHETTES,
    SORTIE_DEFAUT,
    Calibration,
    echantillonner,
    surveiller_appui,
    vibrer,
    _teleop_active,
    reponse_booleenne,
    trouver_base_hid,
)
from js_lecteur import LecteurJs, lister_manettes, trouver_noeud_imu  # noqa: E402
from manette_materiel import chemin_sysfs, leds_du_pad, vibration_supportee  # noqa: E402

LARGEUR = 68


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


def attendre_appui(lecteur, rappel_s: float = 12.0):
    """Attend un appui (ou Entrée = passer, ou q = abandonner).

    Rend ('bouton', index), ('passe', None) ou ('quitter', None).
    """
    depart = dernier_rappel = time.monotonic()
    avant = list(lecteur.etat().boutons)
    while True:
        a_lire = [lecteur.fd, sys.stdin.fileno()]
        lus, _, _ = select.select(a_lire, [], [], 0.2)
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
            if ligne == "":            # entrée fermée : on ne bloque pas
                return "passe", None
            ligne = ligne.strip().lower()
            if ligne.startswith("q"):
                return "quitter", None
            return "passe", None
        if time.monotonic() - dernier_rappel >= rappel_s:
            print("   … en attente — Entrée pour passer cette entrée, q pour abandonner")
            dernier_rappel = time.monotonic()
        if time.monotonic() - depart > 600:
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
    """Résumé lisible : ce qui a été mesuré, ce qui manque, ce qui est suspect."""
    lignes = []
    collisions = cal.collisions()
    if collisions:
        for index, noms in collisions.items():
            lignes.append(f"⚠ index {index} revendiqué par {', '.join(noms)}")
    if cal.donnees["absents"]:
        lignes.append(f"◦ absents : {', '.join(cal.donnees['absents'])}")
    if not lignes:
        lignes.append("✓ aucune anomalie de code")
    return "\n".join(lignes)


def phase_boutons(cal: Calibration, lecteur) -> None:
    titre("1/5 — BOUTONS")
    print("À chaque ligne : appuie UNE fois sur le bouton demandé.")
    print("Entrée seule = je passe.  q + Entrée = j'abandonne.")

    total = len(ENTREES_DECLAREES)
    for rang, (nom, description) in enumerate(ENTREES_DECLAREES, 1):
        cal.declarer_entree(nom)
        invite(f"[{rang}/{total}] {description}")
        genre, index = attendre_appui(lecteur)

        if genre == "quitter":
            raise KeyboardInterrupt
        if genre == "passe":
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


def phase_axes(cal: Calibration, lecteur) -> None:
    titre("2/5 — AXES (six axes, trois gestes chacun)")
    for nom, index, direction, description in AXES_DECLARES:
        print(f"\n───── {nom} (index {index}) ─────")

        input(f"   Entrée, puis NE TOUCHE À RIEN pendant 1 seconde… ")
        repos = echantillonner(lecteur, 1.0, index)
        centre = statistics.fmean(repos)
        bruit = statistics.pstdev(repos) if len(repos) > 1 else 0.0
        ok(f"repos : centre {centre:+.3f}, bruit {bruit:.3f}")

        input(f"   Entrée, puis fais un CERCLE complet avec « {description} »… ")
        balayage = echantillonner(lecteur, 3.0, index)
        mini, maxi = min(balayage), max(balayage)
        ok(f"débattement : {mini:+.2f} … {maxi:+.2f}")

        input(f"   Entrée, puis POUSSE À FOND vers « {direction} » et maintiens… ")
        extreme = statistics.fmean(echantillonner(lecteur, 1.0, index))
        inverser = extreme < centre
        ok(f"valeur {extreme:+.3f} → sens {'INVERSÉ' if inverser else 'direct'}")

        plancher = 0.5 if nom.startswith("croix") else 0.08
        cal.enregistrer_axe(nom, index=index, centre=centre, minimum=mini,
                            maximum=maxi, zone_morte=max(plancher, 4 * bruit),
                            inverser=inverser)


def phase_gachettes(cal: Calibration, lecteur) -> None:
    titre("3/5 — GÂCHETTES (binaire ou analogique ?)")
    detectes = {}
    for nom, description in ENTREES_GACHETTES:
        if nom in cal.donnees["absents"]:
            print(f"\n── {nom} : déjà notée absente, on passe")
            continue
        invite(f"{description} : appuie PROGRESSIVEMENT à fond, puis relâche")
        try:
            index = cal.bouton(nom)
        except KeyError:
            attention("aucune mesure de bouton pour cette gâchette, on passe")
            continue
        ecarts = surveiller_appui(lecteur, index, 60.0)
        if ecarts:
            detectes[nom] = {str(i): round(v, 3) for i, v in sorted(ecarts.items())}
            attention(f"des axes bougent {detectes[nom]} → ANALOGIQUE")
        else:
            ok("aucun axe ne bouge → BINAIRE")

    if detectes:
        cal.donnees["capacites"]["gachettes_analogiques"] = {
            "disponible": True, "axes_detectes": detectes}
    else:
        cal.donnees["capacites"]["gachettes_analogiques"] = {
            "disponible": False,
            "raison": "aucun axe ne bouge pendant l'appui : gâchettes binaires"}


def phase_imu(cal: Calibration, chemin_imu: str | None) -> None:
    titre("4/5 — IMU (accéléromètre et gyroscope)")
    if not chemin_imu:
        attention("aucun nœud inertiel trouvé → phase ignorée")
        cal.donnees["imu"] = {"chemin": "", "verifie": False,
                              "raison": "aucun nœud /dev/input/jsN inertiel"}
        return

    lecteur = LecteurJs(chemin_imu)
    try:
        input("\n   Entrée, puis pose la manette À PLAT et immobile 3 secondes… ")
        temps_fin = time.monotonic() + 3.0
        releves = []
        while time.monotonic() < temps_fin:
            if not lecteur.lire(0.02):
                break
            releves.append(list(lecteur.etat().axes))
        biais = [round(statistics.fmean(c), 4) for c in zip(*releves)]
        bruit = [round(statistics.pstdev(c), 4) for c in zip(*releves)]
        ok(f"biais {biais}")

        input("   Entrée, puis RETOURNE la manette écran vers le bas, 3 secondes… ")
        temps_fin = time.monotonic() + 3.0
        retournes = []
        while time.monotonic() < temps_fin:
            if not lecteur.lire(0.02):
                break
            retournes.append(list(lecteur.etat().axes))
        biais_retourne = [statistics.fmean(c) for c in zip(*retournes)]
        verifie = (biais[2] * biais_retourne[2]) < 0
        ok(f"retournement {'confirmé' if verifie else 'NON confirmé'} "
           f"({biais[2]:+.2f} → {biais_retourne[2]:+.2f})")

        gravite = round((sum(v * v for v in biais[:3])) ** 0.5, 4)
        cal.donnees["imu"] = {"chemin": chemin_imu, "biais": biais, "bruit": bruit,
                              "gravite": gravite, "verifie": bool(verifie)}
    finally:
        lecteur.fermer()


def phase_actionneurs(cal: Calibration, chemin_pad: str) -> None:
    titre("5/5 — ACTIONNEURS (vibration, lumière)")
    noeud = chemin_pad.rsplit("/", 1)[-1]
    base_hid = trouver_base_hid()

    if vibration_supportee(chemin_sysfs(noeud, "ff")):
        print("\n   Le noyau annonce FF_RUMBLE : un effet va être joué.")
        try:
            vibrer(noeud)
        except Exception as err:               # noqa: BLE001
            attention(f"l'effet n'a pas pu être joué : {err}")
        reponse = input("   As-tu senti la vibration ? (o/n) ")
        cal.donnees["capacites"]["vibration"] = {
            "disponible": True, "methode": "evdev EV_FF (FF_RUMBLE)",
            "verifie": reponse_booleenne(reponse)}
        ok(f"vibration confirmée : {reponse_booleenne(reponse)}")
    else:
        cal.donnees["capacites"]["vibration"] = {
            "disponible": False, "methode": "evdev EV_FF",
            "raison": "le noyau n'annonce pas FF_RUMBLE"}
        attention("le noyau n'annonce pas FF_RUMBLE")

    leds = leds_du_pad(Path(base_hid)) if base_hid else []
    if leds:
        cal.donnees["capacites"]["lumieres"] = {
            "disponible": True, "entrees": [p.name for p in leds]}
        ok(f"{len(leds)} entrée(s) LED exposée(s) : {[p.name for p in leds]}")
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
    cal = Calibration(args.sortie, args.forcer)
    cal.donnees["appareil"] = {"nom": nom, "js_pad": chemin_pad,
                               "js_imu": trouver_noeud_imu() or ""}
    print(f"\nManette : {nom}  ({chemin_pad})")
    print(f"Sortie  : {args.sortie}")
    print("\nPendant l'attente d'un bouton : Entrée = passer, q + Entrée = abandonner.")

    lecteur = LecteurJs(chemin_pad)
    try:
        phase_boutons(cal, lecteur)
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

    phase_imu(cal, cal.donnees["appareil"].get("js_imu"))
    phase_actionneurs(cal, chemin_pad)

    titre("RÉSUMÉ")
    print(surligner_etat(cal))
    print(f"\n{len(cal.donnees['boutons'])} boutons mesurés, "
          f"{len(cal.donnees['aliases'])} alias, "
          f"{len(cal.donnees['absents'])} absent(s), "
          f"{len(cal.donnees['axes'])} axes.")

    try:
        chemin = cal.ecrire()
    except RuntimeError as err:
        print(f"\n⚠ ÉCRITURE REFUSÉE : {err}")
        print("  Rien n'a été enregistré. Relance la calibration.")
        return 6

    print(f"\n✅ Écrit : {chemin}")
    print("Vérifie-le, puis lance la téléopération :")
    print("  ros2 launch joy_teleop/joy_teleop_launch.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
