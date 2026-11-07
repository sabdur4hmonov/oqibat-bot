import logging

from bot.utils.logging import SecretFormatter


def test_redacts_credentials_even_in_exception_text():
    token = "123:private-token"
    db_url = "postgresql+asyncpg://name:password@localhost/db"
    try:
        raise RuntimeError(f"failed for {token} and {db_url}")
    except RuntimeError as error:
        record = logging.LogRecord(
            "test",
            logging.ERROR,
            __file__,
            1,
            "URL %s",
            (token,),
            (type(error), error, error.__traceback__),
        )
    rendered = SecretFormatter([token, db_url]).format(record)
    assert token not in rendered
    assert db_url not in rendered
    assert "[REDACTED]" in rendered
