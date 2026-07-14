from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, BigInteger, String, Text, DateTime, UniqueConstraint, CheckConstraint, func
from datetime import datetime

class Base(DeclarativeBase):
    pass

class ProcessedPost(Base):
    __tablename__ = 'processed_posts'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_channel_id: Mapped[int] = mapped_column(BigInteger, index=True)
    source_message_id: Mapped[int] = mapped_column(BigInteger)
    post_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(50), default='seen')
    text: Mapped[str] = mapped_column(Text)
    rewritten_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_link: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # timezone=True → TIMESTAMPTZ in PostgreSQL; server_default evaluated per-row on DB side
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint('source_channel_id', 'source_message_id', name='uq_post_source'),
        CheckConstraint(
            "status IN ('seen', 'queued', 'ai_processing', 'processed', 'failed', 'moderating', 'published', 'rejected', 'filtered_ad', 'duplicate_content')",
            name='chk_status'
        ),
    )

class BotSettings(Base):
    __tablename__ = 'bot_settings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mode: Mapped[str] = mapped_column(String(50), default='auto')
    interval_min: Mapped[int] = mapped_column(Integer, default=0)
    interval_max: Mapped[int] = mapped_column(Integer, default=0)
    pause_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_post_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    queue_limit: Mapped[int] = mapped_column(Integer, default=5)
