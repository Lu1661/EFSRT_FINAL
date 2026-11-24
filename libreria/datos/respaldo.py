import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from ..config import INSTANCE, LIMA, mysql_config


def opcion_mysql(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def respaldo_diario(config=None, folder=None):
    config = config or mysql_config()
    folder = folder or INSTANCE / "respaldos"
    folder.mkdir(parents=True, exist_ok=True)
    final = folder / f"{config.database}-{datetime.now(LIMA):%Y-%m-%d}.sql"
    if final.is_file():
        return final
    exe = os.environ.get("LIBRERIA_MYSQLDUMP") or shutil.which("mysqldump")
    if not exe:
        raise RuntimeError("mysqldump no está en PATH. Configura LIBRERIA_MYSQLDUMP.")
    options = dict(user=config.username, password=config.password, host=config.host, port=config.port)
    with tempfile.TemporaryDirectory() as temp:
        cnf = Path(temp) / "cliente.cnf"
        cnf.write_text("[client]\n" + "\n".join(f"{k}={opcion_mysql(v)}" for k, v in options.items()),
                       encoding="utf-8")
        fd, path = tempfile.mkstemp(dir=folder, suffix=".tmp")
        os.close(fd)
        parcial = Path(path)
        try:
            args = [exe, f"--defaults-extra-file={cnf}", "--single-transaction", "--no-tablespaces",
                    "--set-gtid-purged=OFF", "--skip-lock-tables", "--default-character-set=utf8mb4",
                    f"--result-file={parcial}", config.database]
            try:
                result = subprocess.run(args, capture_output=True, timeout=180, check=False)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError('El respaldo superó el tiempo máximo.') from exc
            if result.returncode or not parcial.stat().st_size:
                raise RuntimeError(f"mysqldump no completó el respaldo (código {result.returncode}).")
            if not final.exists():
                parcial.replace(final)
        finally:
            parcial.unlink(missing_ok=True)
    return final
