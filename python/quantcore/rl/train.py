from stable_baselines3 import PPO
from ghost_gym import GhostExchangeEnv
import os

def train():
    print("[RL] Initializing Ghost Exchange Environment...")
    env = GhostExchangeEnv()
    print("[RL] Training PPO Agent...")
    model = PPO("MlpPolicy", env, verbose=0, n_steps=2048, batch_size=64, learning_rate=3e-4)
    model.learn(total_timesteps=50000)
    os.makedirs("data/models", exist_ok=True)
    model.save("data/models/rl_execution_ppo")
    print("[RL] PPO Agent saved.")

if __name__ == "__main__":
    train()
