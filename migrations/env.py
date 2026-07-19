from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from src.config import settings
from src.db import Base

# Это Alembic-конфиг
config = context.config

# Интерпретируем файл для логов
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Подставляем наш URL из .env
config.set_main_option("sqlalchemy.url", f"{settings.DB_URL}?async_fallback=True")

# Метаданные моделей
target_metadata = Base.metadata

# Импортируем модели (чтобы Alembic их увидел)
from src.telegram_bot.models import User  # 👈 Добавь сюда

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()