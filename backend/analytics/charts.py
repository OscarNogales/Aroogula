import yfinance as yf   
import pandas as pd

class ChartEngine():
    def __init__(self, ledger):
        self.ledger = ledger

    def tickerGraph(self, ticker: str, period: str, mean: bool = False):
        allowed_periods = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]

        if period not in allowed_periods:
            print(f"Error, period not in the allowed values {', '.join(allowed_periods)}")
        
        interval_mapping = {
            "1d": "5m",
            "5d": "15m",
            "1mo": "1h",
            "3mo": "1h",
            "6mo": "90m",
            "1y": "1d",
            "2y": "1d",
            "5y": "1d",
            "10y": "1d",
            "ytd": "1d",
            "max": "1d"
        }

        ticker_obj = yf.Ticker(ticker)
        historical_data = ticker_obj.history(period=period, interval=interval_mapping.get(period))

        data = historical_data.copy().reset_index()
        if "Datetime" in data.keys():
            data = data.rename(columns={"Datetime": "Date"})

        if mean:
            data["EMA_20"] = data["Close"].ewm(
                span=20,
                adjust=False
                ).mean()
            data = data.dropna(subset=["EMA_20"])

        if not data.empty:
            return {
                "status": "success",
                **data.to_dict(orient="list")
            }
        else:
            return {
        "status": "error",
        "message": f"El historial está vacío para el ticker '{ticker}'."
    }
        
