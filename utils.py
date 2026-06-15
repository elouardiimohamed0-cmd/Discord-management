from typing import List, Optional, Dict, Any

def fuzzy_find_player(query: str, players: List[Any], squad_data: Dict[str, Any]) -> Optional[Any]:
    """Find a scraped player by name, PSN, or nickname."""
    if not query:
        return None
    query = query.lower().strip()
    squad_players = squad_data.get("players", [])
    
    squad_by_name = {p.get("name", "").lower(): p for p in squad_players}
    squad_by_psn = {p.get("psn", "").lower(): p for p in squad_players}
    squad_by_nick = {p.get("nickname", "").lower(): p for p in squad_players}
    
    def get_squad_info(pct_name: str):
        pct_name_lower = pct_name.lower()
        return (
            squad_by_name.get(pct_name_lower) or
            squad_by_psn.get(pct_name_lower) or
            squad_by_nick.get(pct_name_lower) or
            {}
        )
    
    # 1. Exact match on PCT name
    for p in players:
        if p.name.lower() == query:
            return p
    
    # 2. Exact match on PSN or nickname
    for p in players:
        info = get_squad_info(p.name)
        if info.get("psn", "").lower() == query:
            return p
        if info.get("nickname", "").lower() == query:
            return p
    
    # 3. Partial match on PCT name
    for p in players:
        if query in p.name.lower():
            return p
    
    # 4. Partial match on PSN/nickname
    for p in players:
        info = get_squad_info(p.name)
        if query in info.get("psn", "").lower():
            return p
        if query in info.get("nickname", "").lower():
            return p
    
    return None
