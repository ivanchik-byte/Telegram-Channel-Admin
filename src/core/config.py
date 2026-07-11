from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator, Json
from typing import List, Union

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    
    API_ID: int
    API_HASH: str
    
    # Can be a comma-separated string of IDs or usernames
    CHANNELS_TO_TRACK: str
    
    # Bot Settings
    TELEGRAM_BOT_TOKEN: str
    MODERATOR_CHAT_ID: str
    TARGET_CHANNEL_ID: str
    
    # AI Settings
    AI_API_KEY: str # Strict, no default
    AI_BASE_URL: str = "https://api.openai.com/v1"
    AI_MODEL: str = "gpt-4o-mini"
    AD_KEYWORDS: str = "реклама,erid,промокод,подписывайтесь"
    AI_EXTRA_BODY: Json[dict] = "{}"
    
    ADMIN_IDS: list[int] = Field(default_factory=list)

    @validator('ADMIN_IDS', pre=True)
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            if not v.strip():
                return []
            return [int(x.strip()) for x in v.split(',') if x.strip()]
        return v

    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def parsed_channels(self) -> List[Union[int, str]]:
        """
        Parses the comma-separated channels string into a list of ints (for IDs) and strings (for usernames).
        """
        if not self.CHANNELS_TO_TRACK:
            return []
        
        raw_channels = [c.strip() for c in self.CHANNELS_TO_TRACK.split(",") if c.strip()]
        parsed = []
        for c in raw_channels:
            try:
                # Try to parse as int (ID)
                parsed.append(int(c))
            except ValueError:
                # Keep as string (Username) and remove leading @
                parsed.append(c.lstrip('@'))
        return parsed

    @property
    def parsed_ad_keywords(self) -> List[str]:
        if not self.AD_KEYWORDS:
            return []
        return [k.strip().lower() for k in self.AD_KEYWORDS.split(",") if k.strip()]

settings = Settings()
