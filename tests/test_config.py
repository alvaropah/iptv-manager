from app.core.config import settings


def test_settings_object_exists():
    assert settings.database_path
