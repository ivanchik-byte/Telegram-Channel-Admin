import re

with open('src/bot/handlers.py', 'r', encoding='utf-8') as f:
    handlers = f.read()

best_target = r"(@router\.message\(Command\('best'\), IsModeratorFilter\(\)\)\nasync def cmd_best\(message: Message, command: CommandObject\):.*?)(?=@router\.message)"
best_replacement = """@router.message(Command('best'), IsModeratorFilter())
async def cmd_best(message: Message, command: CommandObject):
    hours = 24
    if command.args:
        try:
            from src.bot.handlers import parse_time_suffix
            delta = parse_time_suffix(command.args)
            if delta:
                hours = int(delta.total_seconds() / 3600)
            else:
                hours = int(command.args)
        except Exception:
            await message.reply("Неверный формат времени. Пример: /best 12h")
            return

    from arq import create_pool
    from arq.connections import RedisSettings
    from src.database.engine import async_session_maker
    from src.database.repository import SettingsRepository
    from datetime import timedelta
    
    redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    try:
        # Trigger parsing first
        await redis.set('force_parse', '20')
        
        # Reset interval
        async with async_session_maker() as session:
            await SettingsRepository.update_settings(session, next_post_time=None)
            
        # Defer best post task to allow parsing to complete
        await redis.enqueue_job('find_best_post_task', hours, _defer_by=timedelta(seconds=15))
        await message.reply(f"Запущено скачивание свежих постов и отбор лучшего за последние {hours} часов (интервал сброшен). Ожидайте...")
    finally:
        await redis.close()

"""
handlers = re.sub(best_target, lambda m: best_replacement, handlers, flags=re.DOTALL)

# And reply_find_best needs to call cmd_best correctly
reply_best_target = r"(@router\.message\(F\.text == \"Найти лучший пост\", IsModeratorFilter\(\)\)\nasync def reply_find_best.*?)(?=@router\.message)"
reply_best_replacement = """@router.message(F.text == "Найти лучший пост", IsModeratorFilter())
async def reply_find_best(message: Message):
    class DummyCommand:
        args = None
    await cmd_best(message, DummyCommand())

"""
handlers = re.sub(reply_best_target, lambda m: reply_best_replacement, handlers, flags=re.DOTALL)

with open('src/bot/handlers.py', 'w', encoding='utf-8') as f:
    f.write(handlers)

print("cmd_best patched")
