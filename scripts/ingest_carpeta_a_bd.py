import os
import argparse
from sa_core.config import load_config
from sa_core.db import get_conn
from sa_core.ingest import ingest_dir

def _iter_txt(input_dir, max_files):
    files = [f for f in os.listdir(input_dir) if f.lower().endswith(".txt")]
    files.sort()
    if max_files and max_files > 0:
        files = files[:max_files]
    return files

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.ini")
    ap.add_argument("--input_dir", required=True)
    ap.add_argument("--max_files", type=int, default=0)
    ap.add_argument("--notas", default="")
    args = ap.parse_args()

    cfg = load_config(args.config)
    conn = get_conn(cfg)

    # ingest_dir original recorre os.listdir(input_dir). Para limitar sin tocar sa_core,
    # hacemos un "input_dir temporal" con symlinks/copias? No: más simple: ejecutamos
    # ingest_dir si max_files==0, y si no, iteramos nosotros replicando el bucle.
    # Como ingest_dir ya hace INSERT de ejecución + lectura + insert, lo más robusto
    # acá es: si max_files==0 -> ingest_dir; si no -> llamarlo igual pero filtrando
    # con un monkeypatch de os.listdir dentro del módulo.
    if args.max_files and args.max_files > 0:
        import sa_core.ingest as ingest_mod
        real_listdir = os.listdir
        allowed = _iter_txt(args.input_dir, args.max_files)
        def _patched_listdir(_):
            return allowed
        ingest_mod.os.listdir = _patched_listdir
        try:
            ingest_dir(conn, args.input_dir, args.notas)
        finally:
            ingest_mod.os.listdir = real_listdir
    else:
        ingest_dir(conn, args.input_dir, args.notas)

    conn.close()

if __name__ == "__main__":
    main()
