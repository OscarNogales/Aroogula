
import os
import json

class Wallet:
    def __init__(self, wallet_state: str, config_path="config.json",  alpaca_client=None):
        self.config_path = config_path
        self.client = alpaca_client
        self.mode = "local_sim" 
        self.cash = 10000.0   
        self.wallet_file = wallet_state
        
        self.load_config()

    def load_config(self) -> dict:
        """Lee el archivo de ajustes y define el modo. Retorna dict para la API."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                
                if "trading_mode" in config:
                    self.mode = config["trading_mode"]
                elif "paper_trading" in config:
                    self.mode = "alpaca_paper" if config["paper_trading"] else "alpaca_live"
                
                self.cash = config.get("initial_sim_balance", 10000.0)
                
            return {"status": "success", "message": "Configuración cargada", "mode": self.mode}
        else:
            self.mode = "local_sim"
            return {"status": "warning", "message": "No se encontró config. Usando local_sim.", "mode": self.mode}

    def get_balance(self) -> dict:
        """
        Esta es la función que Rust llamará cuando quiera saber el saldo actual.
        """
        if self.mode == "local_sim":
            if os.path.exists(self.wallet_file):
                with open(self.wallet_file, 'r') as f:
                    data = json.load(f)
                    self.cash = data.get("cash", self.cash)
            else:
                self.save_local_balance()
                
            return {
                "status": "success", 
                "message": "Virtual cash loaded", 
                "data": {"cash": self.cash, "mode": self.mode}
            }

        elif self.mode in ["alpaca_paper", "alpaca_live"]:
            if self.client is None:
                # Escudo: Falla en Alpaca, caemos a simulación local
                self.mode = "local_sim"
                return {
                    "status": "error",
                    "message": "Falta cliente Alpaca. Cambiando a simulación local.",
                    "data": {"cash": self.cash, "mode": self.mode}
                }
            
            try:
                account = self.client.get_account()
                self.cash = float(account.cash)
                return {
                    "status": "success", 
                    "message": "Saldo real obtenido de Alpaca", 
                    "data": {"cash": self.cash, "mode": self.mode}
                }
            except Exception as e:
                self.mode = "local_sim"
                return {
                    "status": "error", 
                    "message": f"Error API Alpaca: {str(e)}. Cambiando a simulación.", 
                    "data": {"cash": self.cash, "mode": self.mode}
                }

    def update_balance(self, amount: float) -> dict:
        """
        Adds or withdraws money. It return a dict so that the front can see the assets.
        """
        if self.mode == "local_sim":
            new_balance = self.cash + amount
            if new_balance < 0:
                return {
                    "status": "error", 
                    "message": f"Not enough money in the wallet to make the transaction. Current cash: ${self.cash}; Requested withdrawal: ${abs(amount)}", 
                    "data": {"current_cash": self.cash}
                }
            self.cash = new_balance
            self.save_local_balance()
            return {
                "status": "success", 
                "message": f"Virtual money updated ({amount})", 
                "data": {"new_cash": self.cash}
            }
        else:
            return {
                "status": "ignored", 
                "message": "Alpaca mode: cash is automatically updated through Broker.", 
                "data": {"current_cash": self.cash}
            }

    def save_local_balance(self) -> bool:
        with open(self.wallet_file, 'w') as f:
            json.dump({"cash": self.cash}, f, indent=4)
        return True
    