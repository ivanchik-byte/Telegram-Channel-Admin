from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import BigInteger, String, Text, DateTime, UniqueConstraint, CheckConstraint, func
from datetime import datetime

class Base(DeclarativeBase):
    pass

class ProcessedPost(Base):
    __tablename__ = 'processed_posts'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_channel_id: Mapped[int] = mapped_column(BigInteger, index=True)
    source_message_id: Mapped[int] = mapped_column(BigInteger, index=True)
    post_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(50), default='seen')
    text: Mapped[str] = mapped_column(Text)
    rewritten_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # timezone=True → TIMESTAMPTZ in PostgreSQL; server_default evaluated per-row on DB side
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp()
    )

    __table_args__ = (
        UniqueConstraint('source_channel_id', 'source_message_id', name='uq_source_msg'),
        CheckConstraint(
            "status IN ('seen', 'queued', 'ai_processing', 'processed', 'failed', 'moderating', 'published', 'rejected', 'filtered_ad', 'duplicate_content')",
            name='chk_status'
        ),
    )
