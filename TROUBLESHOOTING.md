# Troubleshooting

Real issues encountered during the 1.0 hardening pass, and their fixes.

## `ImportError: libduckdb.so: cannot open shared object file`

The C++ extension links against DuckDB's shared library. As of 1.0 the build bakes an `$ORIGIN` RPATH into `quantcore_cpp.so` and `setup.sh` copies `libduckdb.so` next to it, so the loader finds it without environment hacks. If you still see this error, rebuild cleanly:

```bash
rm -rf build && bash setup.sh
```

Do not paper over it with `LD_LIBRARY_PATH`; fix the RPATH.

## Dashboard loads but charts are empty / "provider failed"

Market-data providers rate-limit. QuantCore serves the local parquet cache when live fetches fail, so charts should still render (possibly stale). To force a live refresh, set `QUANTCORE_PREFER_LIVE_DATA=true`. If a symbol has never been cached, add it first.

## The kill switch / stop buttons don't stop a process

Process termination targets exact PIDs found via `psutil`. If a process won't stop, confirm it actually matches the expected command line (`ps aux | grep nexus_core`). The supervisor (`python/scripts/supervisor.py status`) shows what it is tracking.

## DuckDB "database is locked" on reload

Database connections are created in the FastAPI lifespan (worker process only) so the Uvicorn reloader doesn't hold a lock across forks. If you see lock errors after a code change, restart the server cleanly rather than relying on auto-reload.

## Build fails

Ensure GCC 13+ and CMake 3.24+. DuckDB compiles from source and needs several GB of disk and RAM. On low-memory machines, build with fewer parallel jobs (`make -j2`).

## Tests fail after a data change

Some tests rely on the seeded universe. Re-seed with:

```bash
python3 python/scripts/seed_universe.py
```

Then re-run `pytest -q`.
