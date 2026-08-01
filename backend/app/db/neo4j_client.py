from contextlib import contextmanager

from neo4j import GraphDatabase

from app.config import settings

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


@contextmanager
def session():
    with get_driver().session() as s:
        yield s


def close_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
