from langchain_core.callbacks import BaseCallbackHandler

from .config import langfuse_settings


def make_langfuse_handler() -> BaseCallbackHandler | None:
    if not (langfuse_settings.public_key and langfuse_settings.secret_key):
        return None

    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler

    Langfuse(
        public_key=langfuse_settings.public_key,
        secret_key=langfuse_settings.secret_key,
        host=langfuse_settings.host,
    )
    return CallbackHandler()


def flush() -> None:
    if not (langfuse_settings.public_key and langfuse_settings.secret_key):
        return
    from langfuse import get_client

    get_client().flush()
