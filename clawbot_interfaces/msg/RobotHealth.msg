# Santé du robot, publiée sur /clawbot/health à 1 Hz (référentiel §3.4).
builtin_interfaces/Time stamp
uint8 LEVEL_OK=0
uint8 LEVEL_WARN=1
uint8 LEVEL_ERROR=2
uint8 level
string[] active_capabilities
string[] stale_flows        # topics attendus dont l'âge dépasse leur max_age_s
string safety_state         # copie de /safety/state
bool estop_latched
float32 voltage
string detail_json
