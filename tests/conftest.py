import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import app as app_module


@pytest.fixture
def cliente():
    """Fixture compartido que proporciona un cliente de prueba Flask sin servidor real."""
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as cliente:
        yield cliente
