import unittest
import typing
from uuid import uuid4

from flask import Flask
from flask.testing import FlaskClient


class TestBase(unittest.TestCase):
    app: typing.ClassVar[Flask]
    client: FlaskClient
    _shared_app: typing.ClassVar[Flask | None] = None

    @classmethod
    def setUpClass(cls) -> None:
        if TestBase._shared_app is not None:
            cls.app = TestBase._shared_app
            return

        from WebHostLib import app as raw_app
        from WebHost import get_app

        raw_app.config["PONY"] = {
            "provider": "sqlite",
            "filename": ":memory:",
            "create_db": True,
        }
        raw_app.config.update({
            "TESTING": True,
            "DEBUG": True,
        })
        TestBase._shared_app = get_app()
        cls.app = TestBase._shared_app

    def setUp(self) -> None:
        from WebHostLib.models import db
        from pony.orm import db_session
        with db_session:
            for entity in db.entities.values():
                entity.select().delete(bulk=True)
        self.client = self.app.test_client()
