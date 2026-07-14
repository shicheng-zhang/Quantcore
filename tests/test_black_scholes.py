import sys
import os
import numpy as np
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from python.quantcore.vol.black_scholes import BlackScholes

def test_call_put_parity():
    S, K, T, r, sigma = 100, 100, 1.0, 0.05, 0.2
    call = BlackScholes.price(S, K, T, r, sigma, 'call')
    put = BlackScholes.price(S, K, T, r, sigma, 'put')
    # Put-Call Parity: C - P = S - K * e^(-rT)
    parity_diff = call - put
    expected_diff = S - K * np.exp(-r * T)
    assert abs(parity_diff - expected_diff) < 1e-5

def test_greeks_delta_bounds():
    S, K, T, r, sigma = 100, 100, 1.0, 0.05, 0.2
    call_g = BlackScholes.greeks(S, K, T, r, sigma, 'call')
    put_g = BlackScholes.greeks(S, K, T, r, sigma, 'put')
    assert 0 <= call_g["delta"] <= 1
    assert -1 <= put_g["delta"] <= 0
