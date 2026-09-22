from backend.trading.wallet import Wallet

import json
import pytest

# -----------------
# Helpers
# -----------------

def make_wallet_config(config_path, **overrides):
    config = {
        "trading_mode": "local_sim",
        "initial_sim_balance": 1000.0,
    }

    config.update(overrides)

    config_path.write_text(
        json.dumps(config, indent=4),
        encoding="utf-8",
    )

    return config_path

def make_wallet_state(wallet_state_path, cash=1000.0):
    wallet_state_path.write_text(
        json.dumps({"cash": cash}, indent=4),
        encoding="utf-8",
    )

    return wallet_state_path


# -----------------
# Test get_balance
# -----------------

def test_get_balance(tmp_path):
    wallet_state_path = tmp_path / "temp_wallet.json"
    wallet_config_path = tmp_path / "temp_config.json"

    make_wallet_config(wallet_config_path, initial_sim_balance=1000)

    wallet = Wallet(
        wallet_state=str(wallet_state_path),
        config_path=str(wallet_config_path)
    )

    balance = wallet.get_balance()

    assert balance["status"] == "success"
    assert balance["data"]["cash"] == pytest.approx(1000)
    assert balance["data"]["mode"] == "local_sim" 


# ----------------------------
# Test update_balance deposit
# ----------------------------

def test_update_balance_deposit(tmp_path):
    wallet_state_path = tmp_path / "temp_wallet.json"
    wallet_config_path = tmp_path / "temp_config.json"

    make_wallet_config(wallet_config_path, initial_sim_balance=1000)

    wallet = Wallet(
        wallet_state=str(wallet_state_path),
        config_path=str(wallet_config_path)
    )

    deposit = wallet.update_balance(+100)

    assert deposit["status"] == "success"
    assert deposit["data"]["new_cash"] == pytest.approx(1100)

    balance = wallet.get_balance()

    assert balance["status"] == "success"
    assert balance["data"]["cash"] == pytest.approx(1100)
    assert balance["data"]["mode"] == "local_sim" 

    saved_data = json.loads(wallet_state_path.read_text(encoding="utf-8"))

    assert saved_data["cash"] == pytest.approx(1100)


# -------------------------------
# Test update_balance withdrawal
# -------------------------------

def test_update_balance_withdrawal(tmp_path):
    wallet_state_path = tmp_path / "temp_wallet.json"
    wallet_config_path = tmp_path / "temp_config.json"

    make_wallet_config(wallet_config_path, initial_sim_balance=1000)

    wallet = Wallet(
        wallet_state=str(wallet_state_path),
        config_path=str(wallet_config_path)
    )

    deposit = wallet.update_balance(-100)

    assert deposit["status"] == "success"
    assert deposit["data"]["new_cash"] == pytest.approx(900)

    balance = wallet.get_balance()

    assert balance["status"] == "success"
    assert balance["data"]["cash"] == pytest.approx(900)
    assert balance["data"]["mode"] == "local_sim" 

    saved_data = json.loads(wallet_state_path.read_text(encoding="utf-8"))

    assert saved_data["cash"] == pytest.approx(900)


# -------------------------------
# Test save_local_balance
# -------------------------------

def test_save_local_balance(tmp_path):
    wallet_state_path = tmp_path / "temp_wallet.json"
    wallet_config_path = tmp_path / "temp_config.json"

    make_wallet_config(wallet_config_path, initial_sim_balance=1000)

    wallet = Wallet(
        wallet_state=str(wallet_state_path),
        config_path=str(wallet_config_path)
    )

    result = wallet.save_local_balance()

    assert result

    saved_data = json.loads(wallet_state_path.read_text(encoding="utf-8"))

    assert saved_data["cash"] == pytest.approx(1000)