#!/usr/bin/env python3
import struct
import os
import sys

def main():
    # On force la lecture du premier joystick
    device_path = '/dev/input/js0'
    
    if not os.path.exists(device_path):
        print(f"❌ {device_path} introuvable. La manette n'est pas connectée en USB ou reconnue.")
        sys.exit(1)

    print(f"✅ Écoute des événements sur {device_path}...")
    print("Appuyez sur des boutons ou bougez les joysticks (Ctrl+C pour quitter)...")

    try:
        with open(device_path, 'rb') as f:
            while True:
                ev_data = f.read(8)
                if not ev_data:
                    break
                
                # Le format du kernel pour joystick (struct js_event) correspond à 8 octets
                # - time (4 octets, unsigned int)
                # - value (2 octets, signed short)
                # - type (1 octet, unsigned char)
                # - number (1 octet, unsigned char)
                time, value, ev_type, number = struct.unpack('IhBB', ev_data)
                
                # Ignorer les événements d'initialisation (flag 0x80)
                if ev_type & 0x80:
                    continue
                    
                # Type 1 = Bouton
                if ev_type == 1:
                    action = "Enfoncé" if value == 1 else "Relâché"
                    print(f"🎮 [BOUTON] Index {number} : {action}")
                
                # Type 2 = Axe (Joystick, Trigger analogique, ou Croix multidirectionnelle)
                elif ev_type == 2:
                    # On évite d'afficher le "bruit" des joysticks s'ils bougent à peine autour du centre
                    if abs(value) > 2000:
                        print(f"🕹️ [AXE]    Index {number} : {value:>6}")
                    
    except KeyboardInterrupt:
        print("\nArrêt du test.")
    except PermissionError:
        print(f"\n❌ Erreur de permission pour lire {device_path}. Essayez avec 'sudo chmod 666 /dev/input/js0'.")
    except Exception as e:
        print(f"\n❌ Erreur inattendue : {e}")

if __name__ == '__main__':
    main()
