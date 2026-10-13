import os
PORT = open(os.path.join(os.path.dirname(__file__), "port.txt")).read().strip()
DSN = f"postgresql+asyncpg://postgres:pw@127.0.0.1:{PORT}/s0"
RAW_DSN = f"postgresql://postgres:pw@127.0.0.1:{PORT}/s0"
