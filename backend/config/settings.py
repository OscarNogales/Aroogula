import json
import os
from typing import Any

class Settings():
    def __init__(self, settings_path: str):
        self.settings_path = settings_path

        self.settings_default_dict = {
        "trading_mode": "local_sim", 
        "Bloomberg bot": False,
        "Yahoo bot": True,
        "Forbes bot": False,
        "EDGAR bot": False,
        "trade_execution_mode": "normal",
        "trade_risk_per_trade_pct": 0.005,
        "trade_target_gain_pct": 0.05,
        "trade_stop_loss_pct": 0.03,
        "ai_dynamic_risk_mode": "normal",
        "ai_dynamic_gain_mode": "normal",
        "ai_dynamic_loss_mode": "normal",
        "cb_spy_hard_stop": -1.75,
        "cb_vix_high": 28.0,
        "cb_vix_spike": 10.0,
        "cb_tnx_spike": 2.5,
        "cb_breadth_drop": -1.0,
        "cb_min_warning_score": 3,
        "gold_spike": 1.5,
        "oil_spike": 2.5,
        "cb_macro_buffer_minutes": 45,
    }
        self.settings = self._load_settings()

        

    def _load_settings(self):
        if not os.path.exists(self.settings_path):
            with open(self.settings_path, "w") as f:
                json.dump(self.settings_default_dict, f, indent=4)
            return self.settings_default_dict.copy()
        else:
            with open(self.settings_path, "r") as f:
                current_settings = json.load(f)
                
                # Revisamos TODAS las llaves por defecto siempre
                needs_saving = False
                for k, v in self.settings_default_dict.items():
                    if k not in current_settings:
                        current_settings[k] = v  # Si falta, la agregamos
                        needs_saving = True      # Marcamos que hubo un cambio
                
                return current_settings
            

    def _save_settings(self):
        with open(self.settings_path, "w") as f:
            json.dump(self.settings, f, indent=4)


    def update_settings(self, new_settings: dict):
        self.settings.update(new_settings)
        
        with open(self.settings_path, "w") as f:
            json.dump(self.settings, f, indent=4)
            
        return self.settings