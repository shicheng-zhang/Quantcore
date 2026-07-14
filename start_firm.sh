#!/bin/bash
SESSION="quantcore_firm"
tmux kill-session -t $SESSION 2>/dev/null
tmux new-session -d -s $SESSION -n "trading_desk"

# Pane 0: C++ Nexus Engine (Top Left)
tmux send-keys -t $SESSION "cd $(pwd) && ./nexus/build/nexus_core" C-m

# Pane 1: Python Hive-Mind Daemon (Top Right)
tmux split-window -h -t $SESSION
tmux send-keys -t $SESSION "cd $(pwd) && python3 -u python/quantcore/hivemind/quant_daemon.py" C-m

# Pane 2: FastAPI Web UI (Bottom)
tmux split-window -v -t $SESSION:0.1
tmux send-keys -t $SESSION "cd $(pwd) && python3 -m uvicorn web.backend.main:app --host 127.0.0.1 --port 8765 --reload" C-m

tmux select-pane -t 0
echo "=========================================="
echo " ⚡ QuantCore Firm Launched in tmux"
echo "=========================================="
echo " To view: tmux attach -t $SESSION"
echo " To detach: Ctrl+B, then D"
echo "=========================================="
tmux attach -t $SESSION
