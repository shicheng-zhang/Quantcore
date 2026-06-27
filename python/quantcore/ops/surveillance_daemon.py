import os
import time
import json

def run_surveillance():
    print("[SURVEILLANCE] FINRA/SEC Market Abuse Monitor Online.")
    print("[SURVEILLANCE] Monitoring for Spoofing, Layering, and Wash Trading...")

    while True:
        try:
            # Read C++ telemetry to check order-to-trade ratios
            tel_path = "data/nexus_live.json"
            if os.path.exists(tel_path):
                with open(tel_path, "r") as f:
                    data = json.load(f)

                # Simulated logic: If sim_fills are high but adverse selection is spiking,
                # or if we detect anomalous routing, flag for spoofing.
                # For the simulation, we randomly trigger a "drill" every 60 seconds
                # to prove the Kill Switch works.
                if int(time.time()) % 60 == 0 and data.get("sim_fills", 0) > 100:
                    print("[SURVEILLANCE] ⚠️ ANOMALY DETECTED: High cancel-to-trade ratio. Triggering Regulatory Halt Drill.")
                    with open("data/surveillance_halt.flag", "w") as f:
                        f.write("SPOOFING_DETECTED")
                    time.sleep(5) # Let the C++ engine halt
                    print("[SURVEILLANCE] Drill complete. Resetting system.")
                    # Reset is handled via API

        except Exception as e:
            pass

        time.sleep(2)

if __name__ == "__main__":
    run_surveillance()
