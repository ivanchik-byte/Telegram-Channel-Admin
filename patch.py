import re

with open('src/bot/handlers.py', 'r', encoding='utf-8') as f:
    handlers = f.read()

# 1. Update FSM states
fsm_target = "class MediaReplacement(StatesGroup):\n    waiting_for_media = State()"
fsm_replacement = "class MediaReplacement(StatesGroup):\n    waiting_for_media = State()\n\nclass TextReplacement(StatesGroup):\n    waiting_for_text = State()"
handlers = handlers.replace(fsm_target, fsm_replacement)

# 2. Update process_edit
edit_target = r"(@router\.callback_query\(F\.data\.startswith\(\"edit_\"\), IsModeratorFilter\(\)\)\nasync def process_edit\(callback: CallbackQuery\):.*?)(?=@router\.callback_query)"
edit_replacement = """@router.callback_query(F.data.startswith("edit_"), IsModeratorFilter())
async def process_edit(callback: CallbackQuery, state: FSMContext):
    post_id = _parse_post_id(callback.data)
    if post_id is None:
        await callback.answer("Ошибка ID", show_alert=True)
        return

    async with async_session_maker() as session:
        post = await PostRepository.get_post_by_id(session, post_id)
        if not post or post.status != 'moderating':
            await callback.answer("Пост уже обработан", show_alert=True)
            return

    await state.set_state(TextReplacement.waiting_for_text)
    await state.update_data(post_id=post_id)
    await callback.message.delete()
    await callback.message.answer(f"Пришлите новый текст для поста {post_id}:")
    await callback.message.answer((post.rewritten_text or "")[:4000])

@router.message(TextReplacement.waiting_for_text, IsModeratorFilter())
async def receive_new_text(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    post_id = data.get('post_id')
    if not post_id or not message.text:
        await message.reply("Текст не получен или ID потерян. Отмена.")
        await state.clear()
        return

    async with async_session_maker() as session:
        post = await PostRepository.atomic_edit_text(session, post_id, 'moderating', message.text)
        if post:
            await send_mod_card_to_chat(bot, message.chat.id, post)
        else:
            await message.reply("Пост уже обработан или не найден.")
            
    await state.clear()

"""
handlers = re.sub(edit_target, lambda m: edit_replacement, handlers, flags=re.DOTALL)

# 3. Update process_change_media
media_target = r"(@router\.callback_query\(F\.data\.startswith\(\"change_media_\"\), IsModeratorFilter\(\)\)\nasync def process_change_media.*?await state\.set_state\(MediaReplacement\.waiting_for_media\))"
media_replacement = r"\1\n    await state.update_data(post_id=post_id)\n    await callback.message.delete()\n    await callback.message.answer(f'Пришлите новое медиа (фото/видео/файл) для поста {post_id}:')"
handlers = re.sub(media_target, media_replacement, handlers, flags=re.DOTALL)

# 4. Update receive_new_media
receive_media_target = r"(@router\.message\(MediaReplacement\.waiting_for_media, IsModeratorFilter\(\)\)\nasync def receive_new_media.*?)(?=@router\.callback_query|@router\.message|# ---)"
receive_media_replacement = """@router.message(MediaReplacement.waiting_for_media, IsModeratorFilter())
async def receive_new_media(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    post_id = data.get('post_id')
    
    media_type = None
    file_id = None
    if message.photo:
        media_type = 'photo'
        file_id = message.photo[-1].file_id
    elif message.video:
        media_type = 'video'
        file_id = message.video.file_id
    elif message.document:
        media_type = 'document'
        file_id = message.document.file_id
        
    if not media_type:
        await message.reply("Пожалуйста, отправьте медиа (фото/видео/документ).")
        return
        
    import os
    os.makedirs('data/media', exist_ok=True)
    temp_filename = f"media_{post_id}_{int(message.date.timestamp())}"
    
    try:
        file_info = await bot.get_file(file_id)
        file_ext = os.path.splitext(file_info.file_path)[1]
        new_filename = f"{temp_filename}{file_ext}"
        media_path = os.path.join('data/media', new_filename)
        await bot.download_file(file_info.file_path, media_path)
    except Exception as e:
        await message.reply(f"Не удалось сохранить медиа: {e}")
        await state.clear()
        return

    async with async_session_maker() as session:
        post = await PostRepository.atomic_update_media(session, post_id, 'moderating', media_path, media_type)
        if post:
            await send_mod_card_to_chat(bot, message.chat.id, post)
        else:
            await message.reply("Пост уже обработан или не найден.")
            
    await state.clear()

"""
handlers = re.sub(receive_media_target, lambda m: receive_media_replacement, handlers, flags=re.DOTALL)

with open('src/bot/handlers.py', 'w', encoding='utf-8') as f:
    f.write(handlers)

with open('src/worker/tasks.py', 'r', encoding='utf-8') as f:
    tasks = f.read()

# Update find_best_post_task
best_target = r"prompt = \"Ниже список постов\. Выбери ОДИН самый интересный.*?logger\.error\(f\"\[Worker\] Выбранный ID {best_id} не найден в списке!\"\)"
best_replacement = """prompt = "Ниже список постов. Выбери до 6 самых интересных, виральных и полезных постов. Верни ТОЛЬКО их числовые ID через запятую, без лишних слов, в порядке убывания интересности (самый крутой - первый).\\n\\n" + str(post_data)
    
    client: AsyncOpenAI = ctx['ai_client']
    try:
        response = await client.chat.completions.create(
            model=settings.AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            extra_body=settings.AI_EXTRA_BODY or {}
        )
        best_ids_str = response.choices[0].message.content.strip()
        import re
        matches = re.findall(r'\\d+', best_ids_str)
        if matches:
            best_ids = [int(m) for m in matches[:6]]
        else:
            raise ValueError(f"Нет чисел в ответе: {best_ids_str}")
    except Exception as e:
        logger.error(f"[Worker] Ошибка при выборе лучшего поста: {e}")
        return

    async with async_session_maker() as session:
        found_first = None
        for p in posts:
            if p.id in best_ids:
                if found_first is None and p.id == best_ids[0]:
                    found_first = p.id
                await PostRepository.update_status(session, p.id, 'queued')
                # Enqueue all selected posts
                await ctx['redis'].enqueue_job('process_post_task', p.id)
            else:
                await PostRepository.update_status(session, p.id, 'filtered_ad')
                
        if best_ids:
            bot = ctx['bot']
            await bot.send_message(settings.MODERATOR_CHAT_ID, f"Выбрано {len(best_ids)} постов из {len(posts)} кандидатов. Они отправлены в очередь на рерайт и публикацию.")
        else:
            logger.error(f"[Worker] Выбранные ID не найдены в списке!")"""
tasks = re.sub(best_target, lambda m: best_replacement, tasks, flags=re.DOTALL)

with open('src/worker/tasks.py', 'w', encoding='utf-8') as f:
    f.write(tasks)

print("Patch applied successfully")
