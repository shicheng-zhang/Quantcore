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
        vol = random.uniform(0.01, 0.05)
        slice_size = int((self.target_shares - self.filled_shares) * random.uniform(0.1, 0.3))
        fill_price = self.current_price
        reward = 0

        if action == 0: # Aggressive Market
            slip_bps = 15.0 * vol * 100
            fill_price = self.current_price * (1 + slip_bps/10000)
            self.filled_shares += slice_size
            reward = -slip_bps * 0.1
        elif action == 1: # Passive Limit
            slip_bps = 2.0 * vol * 100
            if random.random() < 0.6:
                fill_price = self.current_price * (1 + slip_bps/10000)
                self.filled_shares += slice_size
                reward = -slip_bps * 0.1 + 1.0
            else:
                reward = -0.5
        else: # Wait
            reward = -1.0
            self.current_price += random.uniform(-0.5, 0.5)

        terminated = self.filled_shares >= self.target_shares
        truncated = self.steps >= self.max_steps
        if truncated and not terminated: reward -= 50.0

        return self._get_obs(), reward, terminated, truncated, {}
