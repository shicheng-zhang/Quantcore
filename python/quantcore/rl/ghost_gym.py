import gymnasium as gym
from gymnasium import spaces
import numpy as np
import random

class GhostExchangeEnv(gym.Env):
    def __init__(self):
        super().__init__()
        self.observation_space = spaces.Box(low=0, high=1, shape=(5,), dtype=np.float32)
        self.action_space = spaces.Discrete(3)
        self.reset()

    def reset(self, seed=None):
        super().reset(seed=seed)
        self.target_shares = 10000
        self.filled_shares = 0
        self.steps = 0
        self.max_steps = 50
        self.base_price = 100.0
        self.current_price = 100.0
        return self._get_obs(), {}

    def _get_obs(self):
        spread = random.uniform(0.5, 5.0) / 10.0
        vol = random.uniform(0.01, 0.05) / 0.1
        toxicity = random.uniform(0, 1)
        rem_shares = (self.target_shares - self.filled_shares) / self.target_shares
        time_rem = 1.0 - (self.steps / self.max_steps)
        return np.array([spread, vol, toxicity, rem_shares, time_rem], dtype=np.float32)

    def step(self, action):
        self.steps += 1
        # Unified with GhostExchange: eta 0.15, ADV 50000
        vol = random.uniform(0.01, 0.05)
        remaining = self.target_shares - self.filled_shares
        slice_frac = random.uniform(0.1, 0.3)
        slice_size = int(remaining * slice_frac)
        slice_size = max(1, min(slice_size, remaining))
        fill_price = self.current_price
        reward = 0.0

        # Almgren-Chriss: slip_bps = eta * vol * sqrt(Q/ADV) * 10000
        eta = 0.15
        adv = 50000.0
        base_slip_bps = eta * vol * np.sqrt(float(slice_size) / adv) * 10000.0 if slice_size > 0 else 0.0
        base_slip_bps = float(np.clip(base_slip_bps, 0.5, 50.0))

        if action == 0:  # Aggressive Market
            slip_bps = base_slip_bps * 3.0  # pay full spread
            slip_bps = float(np.clip(slip_bps, 1.0, 50.0))
            fill_price = self.current_price * (1 + slip_bps / 10000)
            self.filled_shares += slice_size
            # Reward: negative slippage cost + urgency bonus for filling
            reward = -slip_bps * 0.1 + 0.5
        elif action == 1:  # Passive Limit
            slip_bps = base_slip_bps * 0.43  # reduced impact
            slip_bps = float(np.clip(slip_bps, 0.5, 20.0))
            if random.random() < 0.6:
                fill_price = self.current_price * (1 + slip_bps / 10000)
                self.filled_shares += slice_size
                reward = -slip_bps * 0.1 + 1.0  # bonus for passive fill + spread capture
            else:
                # No fill: pay opportunity cost
                reward = -0.5 - vol * 10
        else:  # Wait
            # Waiting costs time decay + exposure to adverse drift
            reward = -1.0 - vol * 5
            self.current_price += random.uniform(-0.5, 0.5)
            # Price reverts toward base (mean reversion)
            self.current_price += (self.base_price - self.current_price) * 0.02

        terminated = self.filled_shares >= self.target_shares
        truncated = self.steps >= self.max_steps
        if truncated and not terminated:
            reward -= 50.0
        # Clip reward for stable training
        reward = float(np.clip(reward, -60, 10))

        return self._get_obs(), reward, terminated, truncated, {"fill_price": fill_price, "slip_bps": base_slip_bps}
