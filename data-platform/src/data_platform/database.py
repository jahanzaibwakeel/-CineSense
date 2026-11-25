from __future__ import annotations

import os
import re

import psycopg
from psycopg.conninfo import make_conninfo


def database_connection(env: dict[str, str] | None = None) -> psycopg.Connection:
    values = os.environ if env is None else env
    url = values.get("CINESENSE_DATABASE_URL") or values.get("DATABASE_URL")
    if url:
        url = re.sub(r"^jdbc:postgresql:", "postgresql:", url)
        return psycopg.connect(url)
    jdbc_url = values.get("SPRING_DATASOURCE_URL", "")
    match = re.fullmatch(r"jdbc:postgresql://([^/:]+)(?::(\d+))?/([^?]+)(?:\?.*)?", jdbc_url)
    if match:
        host, port, database = match.groups()
        conninfo = make_conninfo(host=host, port=port or 5432, dbname=database,
                                 user=values.get("SPRING_DATASOURCE_USERNAME"),
                                 password=values.get("SPRING_DATASOURCE_PASSWORD"))
        return psycopg.connect(conninfo)
    raise RuntimeError("Configure CINESENSE_DATABASE_URL or SPRING_DATASOURCE_URL and Spring datasource credentials.")
