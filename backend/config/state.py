import json
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo

class BotState():
    def __init__(self, state_path: str):
        self.state_path = state_path
        self.data = self._load()

    def _load(self):
        """Loads the state, or creates a new if it doesn't exist."""

        default_state = {
            "bot_status": "PAUSED",
            "consecutive_api_fails": 0,
            "last_crash_check": None
        }
        
        if not os.path.exists(self.state_path):
            with open(self.state_path, 'w') as f:
                json.dump({
                "consecutive_api_fails": 0,
                "last_crash_check": None  
                }, f, indent=4)
            return default_state
        
        with open(self.state_path, 'r') as f:
            api_fails = json.load(f)

        default_state.update(api_fails)

        return default_state

    def is_market_window(self) -> bool:
        ny_now = datetime.now(ZoneInfo("America/New_York"))

        # Monday = 0, Sunday = 6
        if ny_now.weekday() >= 5:
            return False

        market_open = time(9, 30)
        market_close = time(16, 0)

        return market_open <= ny_now.time() <= market_close

    def can_activate_bot(self) -> tuple[bool, str]:
        if self.is_blind():
            return False, "Bot is blind because API has failed 3 or more times."

        if not self.is_market_window():
            return False, "Market is closed."

        return True, "Bot can be activated."

    def _save(self):
        """Saves the data from RAM to the HD."""

        persistent_state = {
            "consecutive_api_fails": self.data.get("consecutive_api_fails", 0),
            "last_crash_check": self.data.get("last_crash_check", None)
        }

        with open(self.state_path, 'w') as f:
            json.dump(persistent_state, f, indent=4)


    def add_api_strike(self) -> int:
        """Suma un fallo de API y lo guarda. Retorna el número de fallos actuales."""
        self.data["consecutive_api_fails"] += 1
        self.data["last_crash_check"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self._save()
        return self.data["consecutive_api_fails"]

    def reset_api_strikes(self):
        """Si la API funciona, ponemos el contador a 0."""
        if self.data["consecutive_api_fails"] > 0:
            self.data["consecutive_api_fails"] = 0
            self._save()

    def is_blind(self) -> bool:
        """Devuelve True si llevamos 3 o más fallos consecutivos (el bot está ciego)."""
        return self.data["consecutive_api_fails"] >= 3
     