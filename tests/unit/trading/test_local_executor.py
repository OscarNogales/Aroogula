from backend.trading.execution.local_lexecutor import LocalExecutor

from pytest import approx

# --------------
# Helpers
# --------------

class FakeMarketData:
    def get_current_price(self, ticker):
        return 500

class FakeWallet:
    def __init__(self):
        self.last_update = None

    def update_balance(self, amount: float):
        self.last_update = amount

        return {
            "status": "success",
            "message": "Fake Wallet received the update amount successfully.",
        }

class FakeDefectiveMarketData:
    def get_current_price(self, ticker):
        return None

class FakeDefectiveWallet:
    def __init__(self):
        self.last_update = None

    def update_balance(self, amount: float):
        self.last_update = amount

        return {
            "status": "error",
            "message": "Fake Wallet was unable to process the deposit in the account.",
        }


def make_local_executor(defective_market_data: bool = False, defective_wallet: bool = False):
    market_data = FakeDefectiveMarketData() if defective_market_data else FakeMarketData()
    wallet = FakeDefectiveWallet() if defective_wallet else FakeWallet()

    local_executor = LocalExecutor(
        wallet=wallet,
        market_data=market_data
    )

    return local_executor, market_data, wallet


# -------------------------------------------
# Test test_buy_returns_appropriate_template
# -------------------------------------------

def test_buy_returns_appropriate_template():

    local_executor, _, wallet = make_local_executor()

    execution_result = local_executor.buy("AAPL", 1000)

    assert execution_result.status == "FILLED"
    assert execution_result.ticker == "AAPL"

    assert execution_result.filled_quantity == approx(2)
    assert execution_result.filled_price == approx(500)
    assert execution_result.requested_notional == approx(1000)

    assert execution_result.mode == "local_sim"
    assert execution_result.broker_order_id is None
    assert execution_result.message == "Fake Wallet received the update amount successfully."

    assert wallet.last_update == approx(-1000)


# --------------------------------------------------------------------
# Test test_buy_returns_appropriate_template_when_amount_is_incorrect
# --------------------------------------------------------------------

def test_buy_returns_appropriate_template_when_amount_is_incorrect():
    local_executor, _, wallet = make_local_executor()
    
    execution_result = local_executor.buy("AAPL", 0)

    assert execution_result.status == "FAILED"
    assert execution_result.ticker == "AAPL"

    assert execution_result.requested_notional == approx(0)

    assert execution_result.filled_quantity is None
    assert execution_result.filled_price is None
    

    assert execution_result.mode == "local_sim"
    assert execution_result.broker_order_id is None
    assert execution_result.message is not None

    assert wallet.last_update is None


# ---------------------------------------------------------------------------
# Test test_buy_returns_appropriate_template_when_market_data_is_unavailable
# ---------------------------------------------------------------------------

def test_buy_returns_appropriate_template_when_market_data_is_unavailable():
    local_executor, _, wallet = make_local_executor(defective_market_data=True)
    
    execution_result = local_executor.buy("AAPL", 1000)

    assert execution_result.status == "FAILED"
    assert execution_result.ticker == "AAPL"

    assert execution_result.requested_notional == approx(1000)

    assert execution_result.filled_quantity is None
    assert execution_result.filled_price is None
    

    assert execution_result.mode == "local_sim"
    assert execution_result.broker_order_id is None
    assert execution_result.message is not None

    assert wallet.last_update is None


# --------------------------------------------------------------------
# Test test_buy_returns_appropriate_template_when_wallet_is_defective
# --------------------------------------------------------------------

def test_buy_returns_appropriate_template_when_wallet_is_defective():

    local_executor, _, wallet = make_local_executor(defective_wallet=True)
        
    execution_result = local_executor.buy("AAPL", 1000)

    assert execution_result.status == "FAILED"
    assert execution_result.ticker == "AAPL"

    assert execution_result.requested_notional == approx(1000)

    assert execution_result.filled_quantity is None
    assert execution_result.filled_price is None
    
    assert execution_result.mode == "local_sim"
    assert execution_result.broker_order_id is None
    assert execution_result.message is not None

    assert wallet.last_update == approx(-1000)


# --------------------------------------------
# Test test_sell_returns_appropriate_template
# --------------------------------------------

def test_sell_returns_appropriate_template():

    local_executor, _, wallet = make_local_executor()

    execution_result = local_executor.sell("AAPL", 2)

    assert execution_result.status == "FILLED"
    assert execution_result.ticker == "AAPL"

    assert execution_result.filled_quantity == approx(2)
    assert execution_result.filled_price == approx(500)
    assert execution_result.requested_quantity == approx(2)
    assert execution_result.requested_notional is None

    assert execution_result.mode == "local_sim"
    assert execution_result.broker_order_id is None
    assert execution_result.message == "Fake Wallet received the update amount successfully."

    assert wallet.last_update == approx(1000)


# --------------------------------------------------------------------------
# Test test_sell_returns_appropriate_template_when_the_shares_are_not_valid
# --------------------------------------------------------------------------


def test_sell_returns_appropriate_template_when_the_shares_are_not_valid():

    local_executor, _, wallet = make_local_executor()

    execution_result = local_executor.sell("AAPL", -1)

    assert execution_result.status == "FAILED"
    assert execution_result.ticker == "AAPL"

    assert execution_result.filled_quantity == None
    assert execution_result.filled_price == None
    assert execution_result.requested_quantity == approx(-1)

    assert execution_result.mode == "local_sim"
    assert execution_result.broker_order_id is None
    assert execution_result.message is not None

    assert wallet.last_update is None


# ------------------------------------------------------------------------------
# Test test_sell_returns_appropriate_template_when_the_current_price_is_invalid
# ------------------------------------------------------------------------------


def test_sell_returns_appropriate_template_when_the_current_price_is_invalid():

    local_executor, _, wallet = make_local_executor(defective_market_data=True)

    execution_result = local_executor.sell("AAPL", 2)

    assert execution_result.status == "FAILED"
    assert execution_result.ticker == "AAPL"

    assert execution_result.filled_quantity == None
    assert execution_result.filled_price == None
    assert execution_result.requested_quantity == approx(2)

    assert execution_result.mode == "local_sim"
    assert execution_result.broker_order_id is None
    assert execution_result.message is not None

    assert wallet.last_update is None


# -------------------------------------------------------------------------
# Test test_sell_returns_appropriate_template_when_the_wallet_is_defective
# -------------------------------------------------------------------------


def test_sell_returns_appropriate_template_when_the_wallet_is_defective():

    local_executor, _, wallet = make_local_executor(defective_wallet=True)

    execution_result = local_executor.sell("AAPL", 2)

    assert execution_result.status == "FAILED"
    assert execution_result.ticker == "AAPL"

    assert execution_result.filled_quantity == None
    assert execution_result.filled_price == None
    assert execution_result.requested_quantity == approx(2)

    assert execution_result.mode == "local_sim"
    assert execution_result.broker_order_id is None
    assert execution_result.message is not None

    assert wallet.last_update == approx(1000)