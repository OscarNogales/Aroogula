from .order_template import ExecutionResult


class LocalExecutor:
    """Immediate-fill executor used by local simulation mode."""

    def __init__(self, wallet, market_data, debug_mode: bool = False):
        self.mode = "local_sim"
        self.wallet = wallet
        self.market_data = market_data
        self.debug_mode = debug_mode

    def buy(self, ticker: str, amount: float) -> ExecutionResult:
        try:
            if amount <= 0:
                raise RuntimeError(
                    f"Please enter a valid amount to buy. Requested amount: {amount}"
                )

            current_price = self.market_data.get_current_price(ticker)
            if current_price is None or current_price <= 0:
                raise RuntimeError(
                    f"Market data did not return a valid price for {ticker}."
                )

            shares = amount / current_price
            wallet_result = self.wallet.update_balance(-amount)

            if wallet_result["status"] != "success":
                raise RuntimeError(
                    "Wallet did not update the local value. "
                    f"Error message: {wallet_result['message']}"
                )

            result = ExecutionResult(
                status="FILLED",
                ticker=ticker,
                mode=self.mode,
                requested_notional=amount,
                requested_quantity=None,
                filled_quantity=shares,
                filled_price=current_price,
                client_order_id=None,
                broker_order_id=None,
                message=wallet_result["message"],
            )

        except Exception as exc:
            result = ExecutionResult(
                status="FAILED",
                ticker=ticker,
                mode=self.mode,
                requested_notional=amount,
                requested_quantity=None,
                filled_quantity=None,
                filled_price=None,
                client_order_id=None,
                broker_order_id=None,
                message=f"Unable to complete the transaction: {exc}",
            )

        if self.debug_mode:
            print(result)

        return result

    def sell(self, ticker: str, shares: float) -> ExecutionResult:
        try:
            if shares <= 0:
                raise RuntimeError(
                    f"Please enter a valid quantity of shares to sell. Requested shares: {shares}"
                )

            current_price = self.market_data.get_current_price(ticker)
            if current_price is None or current_price <= 0:
                raise RuntimeError(
                    f"Market data did not return a valid price for {ticker}."
                )

            proceeds = shares * current_price
            wallet_result = self.wallet.update_balance(proceeds)

            if wallet_result["status"] != "success":
                raise RuntimeError(
                    "Wallet did not update the local value. "
                    f"Error message: {wallet_result['message']}"
                )

            result = ExecutionResult(
                status="FILLED",
                ticker=ticker,
                mode=self.mode,
                requested_notional=None,
                requested_quantity=shares,
                filled_quantity=shares,
                filled_price=current_price,
                client_order_id=None,
                broker_order_id=None,
                message=wallet_result["message"],
            )

        except Exception as exc:
            result = ExecutionResult(
                status="FAILED",
                ticker=ticker,
                mode=self.mode,
                requested_notional=None,
                requested_quantity=shares,
                filled_quantity=None,
                filled_price=None,
                client_order_id=None,
                broker_order_id=None,
                message=f"Unable to complete the transaction: {exc}",
            )

        if self.debug_mode:
            print(result)

        return result
