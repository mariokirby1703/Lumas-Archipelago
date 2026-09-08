from unittest.mock import patch

from . import TestBase


class TestInitialization(TestBase):
    def test_subclasses_reuse_initialized_app(self) -> None:
        class FirstClass(TestBase):
            pass

        class SecondClass(TestBase):
            pass

        with patch("WebHost.get_app", side_effect=AssertionError("App initialized twice")):
            FirstClass.setUpClass()
            SecondClass.setUpClass()

        self.assertIs(FirstClass.app, self.app)
        self.assertIs(SecondClass.app, self.app)
        self.assertIn("api", self.app.blueprints)
