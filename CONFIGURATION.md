# Configuration

Primary configuration lives in `config/system.yaml`. It is validated at load time by Pydantic; invalid values (e.g., a risk limit above 1.0) are rejected.

## system.yaml

```yaml
config_version: 1            # bump when the schema changes
system:
  database_path: "data/analytics.db"
  runtime_dir: "data/runtime"
data:
  prefer_live_data: false     # true = refresh from provider before cache
  parquet_views:
    market_data: "data/raw/equities/"
risk:
  max_position_pct: 0.05
  max_daily_loss_pct: 0.03
  max_drawdown_pct: 0.10
```

## Environment variables

Environment overrides are explicit and never mutate the YAML file.

| Variable | Purpose |
|---|---|
| `QUANTCORE_PREFER_LIVE_DATA` | `true` to prefer the live provider over the local cache |
| `QUANTCORE_AUTO_RESEED` | `true` to enable automatic reseeding at startup |
| `QUANTCORE_CONTROL_TOKEN` | Token for remote access to control endpoints |
| `QUANTCORE_RUNTIME_DIR` | Override the runtime artifact directory |
| `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY` | Alpaca paper API credentials (optional) |

## Runtime artifacts

Runtime state (logs, telemetry, supervisor state) belongs under `data/runtime/` and is never a source input. The persistent market cache lives in `data/raw/equities/`.

## Control-plane security

The dashboard is intended to run on loopback. Endpoints that mutate trading or process state require either a loopback client or a valid `QUANTCORE_CONTROL_TOKEN`. Do not bind Uvicorn to a public interface without setting the token.
