from typing import List, Optional, Dict, Any

def _squad_players_list(squad_data: Dict[str, Any]) -> List[Dict[str, Any]]:
 """
 squad.json can be:
 - {"players": [ ... ]}
 - {"dictator": {...}, "shark": {...}, ...}
 This helper normalizes to a list.
 """
 if not isinstance(squad_data, dict):
  return []
 if "players" in squad_data and isinstance(squad_data.get("players"), list):
  return [p for p in squad_data.get("players", []) if isinstance(p, dict)]
 # dict-of-players
 return [p for p in squad_data.values() if isinstance(p, dict)]

def fuzzy_find_player(query: str, players: List[Any], squad_data: Dict[str, Any]) -> Optional[Any]:
 """Find a scraped player by name, PSN, or nickname."""
 if not query:
  return None
 query = query.lower().strip()

 squad_players = _squad_players_list(squad_data)

 squad_by_name = {str(p.get("name", "")).lower(): p for p in squad_players}
 squad_by_psn = {str(p.get("psn", "")).lower(): p for p in squad_players}
 squad_by_nick = {str(p.get("nickname", "")).lower(): p for p in squad_players}

 def get_squad_info(pct_name: str):
  pct_name_lower = (pct_name or "").lower()
  return (
   squad_by_name.get(pct_name_lower) or
   squad_by_psn.get(pct_name_lower) or
   squad_by_nick.get(pct_name_lower) or
   {}
  )

 # 1. Exact match on PCT name
 for p in players:
  if getattr(p, "name", "").lower() == query:
   return p

 # 2. Exact match on PSN or nickname
 for p in players:
  info = get_squad_info(getattr(p, "name", ""))
  if str(info.get("psn", "")).lower() == query:
   return p
  if str(info.get("nickname", "")).lower() == query:
   return p

 # 3. Partial match on PCT name
 for p in players:
  if query in getattr(p, "name", "").lower():
   return p

 # 4. Partial match on PSN/nickname
 for p in players:
  info = get_squad_info(getattr(p, "name", ""))
  if query in str(info.get("psn", "")).lower():
   return p
  if query in str(info.get("nickname", "")).lower():
   return p

 return None
