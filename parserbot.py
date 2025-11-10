import discord
from discord.ext import commands, tasks
import asyncio
import re
import os
from datetime import datetime, timedelta
import traceback
import sys

# Настройки бота
SOURCE_SERVER_ID = 1003525677640851496  # Сервер-источник (отсюда проверяем роли)
TARGET_SERVER_ID = 1437338164292485122  # Целевой сервер (куда выдаём роль)
TARGET_ROLE_ID = 1437338476147380235    # ID роли для выдачи на целевом сервере
LOG_CHANNEL_ID = 1437338399206805625    # Канал для логов

# Список ID ролей для проверки на сервере-источнике
SOURCE_ROLE_IDS = [
    1352527374515699712,
    1383426539886084267,  
    1317882573342507069,
    1381685630555258931,
    1381683377090068550,
    1381682246678741022,
    1310673963000528949,
    1223589384452833290
]

# Настройка интентов
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.bans = True

bot = commands.Bot(command_prefix='!', intents=intents)

class UnbanButton(discord.ui.View):
    """Кнопка для разблокировки пользователя"""
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label='🔓 Разблокировать', style=discord.ButtonStyle.green, custom_id='unban_button')
    async def unban_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Разбаниваем пользователя
            target_server = bot.get_guild(TARGET_SERVER_ID)
            user = await bot.fetch_user(self.user_id)
            
            await target_server.unban(user, reason="Разблокировка через кнопку")
            
            # Обновляем сообщение
            embed = discord.Embed(
                description=(
                    f"✅ **Пользователь разблокирован**\n"
                    f"• Пользователь: `{user.display_name}`\n"
                    f"• ID: `{self.user_id}`\n"
                    f"• Разблокировал: {interaction.user.mention}\n"
                    f"• Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
                ),
                color=0x00ff00,
                timestamp=datetime.now()
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
            
            # Логируем действие
            await role_bot.log_to_channel(
                f"🔓 **Разблокировка через кнопку**\n"
                f"• Пользователь: `{user.display_name}`\n"
                f"• ID: `{self.user_id}`\n"
                f"• Администратор: {interaction.user.mention}",
                color=0x00ff00
            )
            
        except discord.NotFound:
            await interaction.response.send_message("❌ Пользователь не забанен или уже разбанен", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Нет прав для разблокировки", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка при разблокировке: {e}", ephemeral=True)

class RoleSyncBot:
    def __init__(self):
        self.is_monitoring = False
        self.start_time = datetime.now()
        self.banned_users = set()
        self.last_check = datetime.now()

    async def log_to_channel(self, message, color=0x00ff00, view=None):
        """Отправляет лог в указанный канал"""
        try:
            channel = bot.get_channel(LOG_CHANNEL_ID)
            if channel:
                embed = discord.Embed(
                    description=message,
                    color=color,
                    timestamp=datetime.now()
                )
                await channel.send(embed=embed, view=view)
            else:
                print(f"Не удалось найти канал логов: {LOG_CHANNEL_ID}")
        except Exception as e:
            print(f"Ошибка при отправке лога: {e}")

    async def ban_user(self, user_id, username, reason="Отсутствие требуемых ролей"):
        """Банит пользователя на 24 часа"""
        try:
            target_server = bot.get_guild(TARGET_SERVER_ID)
            user = await bot.fetch_user(user_id)
            
            # Баним на  часа
            ban_duration = timedelta(minutes=10)
            ban_reason = f"{reason} | Автобан до {(datetime.now() + ban_duration).strftime('%d.%m.%Y %H:%M')}"
            
            await target_server.ban(user, reason=ban_reason, delete_message_days=0)
            
            # Создаем сообщение с кнопкой разблокировки
            ban_embed = discord.Embed(
                description=(
                    f"🔨 **Пользователь заблокирован**\n"
                    f"• Имя: `{username}`\n"
                    f"• Упоминание: <@{user_id}>\n"
                    f"• Профиль: [Перейти](https://discord.com/users/{user_id})\n\n"
                    f"**Причина:**\n"
                    f"• Участник лишён необходимых ролей\n\n"
                    f"**Статус:**\n"
                    f"• Бан на 10 минут\n"
                    f"• Разблокировка: {(datetime.now() + ban_duration).strftime('%d.%m.%Y %H:%M')}"
                ),
                color=0xff0000,
                timestamp=datetime.now()
            )
            
            # Отправляем сообщение с кнопкой
            channel = bot.get_channel(LOG_CHANNEL_ID)
            if channel:
                await channel.send(embed=ban_embed, view=UnbanButton(user_id))
            
            self.banned_users.add(user_id)
            print(f"🔨 Забанен пользователь {username} ({user_id}) на 10 минут")
            
            return True
            
        except discord.Forbidden:
            error_msg = f"❌ Нет прав для бана пользователя `{username}`"
            await self.log_to_channel(error_msg, color=0xff0000)
        except discord.NotFound:
            error_msg = f"❌ Пользователь `{username}` не найден"
            await self.log_to_channel(error_msg, color=0xff0000)
        except Exception as e:
            error_msg = f"❌ Ошибка при бане пользователя `{username}`: {e}"
            await self.log_to_channel(error_msg, color=0xff0000)
        
        return False

    async def check_and_sync_user(self, user_id, username=None, check_ban=True):
        """Проверяет роли пользователя и синхронизирует"""
        try:
            source_server = bot.get_guild(SOURCE_SERVER_ID)
            target_server = bot.get_guild(TARGET_SERVER_ID)
            
            if not source_server or not target_server:
                return False
            
            target_role = target_server.get_role(TARGET_ROLE_ID)
            if not target_role:
                return False
            
            # Получаем пользователя на целевом сервере
            target_member = target_server.get_member(user_id)
            if not target_member:
                return False
            
            # Проверяем роли на сервере-источнике
            source_member = source_server.get_member(user_id)
            has_required_role = False
            found_roles = []
            
            if source_member:
                for role_id in SOURCE_ROLE_IDS:
                    role = source_server.get_role(role_id)
                    if role and role in source_member.roles:
                        has_required_role = True
                        found_roles.append(role.name)
            
            # Проверяем текущее состояние роли
            has_target_role = target_role in target_member.roles
            username = username or target_member.display_name
            
            # Логика выдачи/удаления роли и бана
            if has_required_role and not has_target_role:
                try:
                    await target_member.add_roles(target_role, reason="Автоматическая синхронизация ролей")
                    log_msg = (
                        f"✅ **Роль выдана**\n"
                        f"• Пользователь: `{username}`\n"
                        f"• ID: `{user_id}`\n"
                        f"• Найдены роли: {', '.join(found_roles) if found_roles else 'Не указано'}\n"
                        f"• Действие: Роль выдана"
                    )
                    await self.log_to_channel(log_msg, color=0x00ff00)
                    print(f"✅ Выдана роль пользователю {username} ({user_id})")
                    return True
                    
                except Exception as e:
                    error_msg = f"❌ Ошибка при выдаче роли пользователю `{username}`: {e}"
                    await self.log_to_channel(error_msg, color=0xff0000)
                    
            elif not has_required_role:
                # Если ролей нет - удаляем роль и баним
                if has_target_role:
                    try:
                        await target_member.remove_roles(target_role, reason="Автоматическая синхронизация - нет требуемых ролей")
                        print(f"🗑️ Удалена роль у пользователя {username} ({user_id})")
                    except Exception as e:
                        print(f"Ошибка при удалении роли: {e}")
                
                # Баним пользователя если проверка бана включена
                if check_ban and user_id not in self.banned_users:
                    ban_result = await self.ban_user(user_id, username)
                    if ban_result:
                        log_msg = (
                            f"🗑️ **Роль удалена и пользователь забанен**\n"
                            f"• Пользователь: `{username}`\n"
                            f"• ID: `{user_id}`\n"
                            f"• Статус: Требуемые роли отсутствуют\n"
                            f"• Действие: Роль удалена + бан 10м"
                        )
                        await self.log_to_channel(log_msg, color=0xff6600)
                        return True
                elif not check_ban and has_target_role:
                    # Только удаляем роль без бана
                    log_msg = (
                        f"🗑️ **Роль удалена**\n"
                        f"• Пользователь: `{username}`\n"
                        f"• ID: `{user_id}`\n"
                        f"• Статус: Требуемые роли отсутствуют\n"
                        f"• Действие: Роль удалена"
                    )
                    await self.log_to_channel(log_msg, color=0xff9900)
                    return True
                
                return True
                
        except Exception as e:
            error_msg = f"❌ Критическая ошибка при синхронизации пользователя {user_id}: {e}"
            print(error_msg)
        
        return False

    async def parse_snitch_message(self, message):
        """Парсит сообщение от SnitchParser и выполняет действия"""
        try:
            content = message.content
            
            # Проверяем, что это сообщение о потере ролей
            if "Потеря ролей:" in content and "Участник лишён необходимых ролей" in content:
                
                # Извлекаем имя пользователя
                name_match = re.search(r"Имя:\s*(.+)", content)
                # Ищем упоминание
                mention_match = re.search(r"Упоминание:\s*(<@!?(\d+)>)", content)
                
                if name_match:
                    username = name_match.group(1).strip()
                    user_id = mention_match.group(2) if mention_match else None
                    
                    if user_id:
                        await self.log_to_channel(
                            f"🔍 **Обнаружена потеря ролей**\n"
                            f"• Пользователь: `{username}`\n"
                            f"• ID: `{user_id}`\n"
                            f"• Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
                            color=0xff9900
                        )
                        
                        # Выполняем проверку и синхронизацию с баном
                        await self.check_and_sync_user(int(user_id), username, check_ban=True)
                    
        except Exception as e:
            error_msg = f"❌ Ошибка при парсинге сообщения: {e}"
            print(error_msg)

# Создаем экземпляр нашего бота
role_bot = RoleSyncBot()

@bot.event
async def on_ready():
    """Функция, которая выполняется при запуске бота"""
    print(f'✅ Бот {bot.user.name} успешно запущен!')
    print(f'📊 ID бота: {bot.user.id}')
    print(f'🕒 Время запуска: {datetime.now()}')
    print(f'🔍 Проверяемые роли: {len(SOURCE_ROLE_IDS)}')
    print(f'⏰ Интервал проверки: каждые 10 секунд')
    print('------')
    
    # Устанавливаем статус бота
    activity = discord.Activity(type=discord.ActivityType.watching, name="роли каждые 10 сек")
    await bot.change_presence(activity=activity)
    
    # Загружаем список забаненных пользователей
    await load_banned_users()
    
    # Отправляем сообщение о запуске в канал логов
    startup_msg = (
        f"🟢 **Role Sync Bot запущен**\n"
        f"• Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"• Статус: Мониторинг активен\n"
        f"• Проверяемые роли: `{len(SOURCE_ROLE_IDS)}`\n"
        f"• Интервал проверки: `10 секунд`\n"
        f"• Автобан: `10 минут` при отсутствии ролей"
    )
    await role_bot.log_to_channel(startup_msg, color=0x00ff00)
    
    # Запускаем фоновые задачи
    role_bot.is_monitoring = True
    rapid_sync_task.start()
    unban_checker.start()

async def load_banned_users():
    """Загружает список забаненных пользователей при запуске"""
    try:
        target_server = bot.get_guild(TARGET_SERVER_ID)
        if target_server:
            bans = [entry async for entry in target_server.bans()]
            for ban_entry in bans:
                role_bot.banned_users.add(ban_entry.user.id)
            print(f"📋 Загружено {len(bans)} забаненных пользователей")
    except Exception as e:
        print(f"❌ Ошибка при загрузке банов: {e}")

@tasks.loop(seconds=10)
async def rapid_sync_task():
    """Быстрая синхронизация всех пользователей каждые 10 секунд"""
    try:
        await sync_all_users()
    except Exception as e:
        print(f"❌ Ошибка в задаче синхронизации: {e}")

@tasks.loop(minutes=1)
async def unban_checker():
    """Проверяет истечение времени бана"""
    try:
        # Можно добавить авторазбан по времени, но пока оставляем ручной через кнопку
        pass
    except Exception as e:
        print(f"❌ Ошибка в проверке банов: {e}")

async def sync_all_users():
    """Синхронизирует всех пользователей на целевом сервере"""
    try:
        target_server = bot.get_guild(TARGET_SERVER_ID)
        if not target_server:
            return
        
        processed = 0
        actions = 0
        current_time = datetime.now()
        
        # Логируем начало проверки только раз в минуту чтобы не спамить
        if (current_time - role_bot.last_check).total_seconds() >= 60:
            print(f"🔄 Начинаю проверку {len(target_server.members)} пользователей...")
            role_bot.last_check = current_time
        
        for member in target_server.members:
            if member.bot:
                continue
                
            processed += 1
            result = await role_bot.check_and_sync_user(member.id, check_ban=True)  # Баним при проверке
            if result:
                actions += 1
            
            # Минимальная задержка чтобы не нагружать API
            await asyncio.sleep(0.05)
        
        if actions > 0:
            print(f"✅ Проверено {processed} пользователей, выполнено действий: {actions}")
        
    except Exception as e:
        print(f"❌ Ошибка при синхронизации всех пользователей: {e}")

@bot.event
async def on_message(message):
    """Обрабатывает все входящие сообщения"""
    try:
        if message.author == bot.user:
            return
        
        if message.channel.id == LOG_CHANNEL_ID:
            await role_bot.parse_snitch_message(message)
        
        await bot.process_commands(message)
    except Exception as e:
        print(f"Ошибка в on_message: {e}")

@bot.command(name='sync_user')
@commands.has_permissions(administrator=True)
async def sync_specific_user(ctx, user: discord.Member):
    """Синхронизировать конкретного пользователя"""
    await ctx.send(f"🔍 Проверяю пользователя {user.mention}...")
    result = await role_bot.check_and_sync_user(user.id, user.display_name, check_ban=True)
    if result:
        await ctx.send("✅ Синхронизация завершена")
    else:
        await ctx.send("❌ Ошибка при синхронизации")

@bot.command(name='force_check')
@commands.has_permissions(administrator=True)
async def force_check(ctx):
    """Принудительная проверка всех пользователей"""
    await ctx.send("🔄 Запускаю принудительную проверку всех пользователей...")
    await sync_all_users()
    await ctx.send("✅ Проверка завершена")

@bot.command(name='unban')
@commands.has_permissions(administrator=True)
async def manual_unban(ctx, user_id: int):
    """Ручная разблокировка пользователя"""
    try:
        target_server = bot.get_guild(TARGET_SERVER_ID)
        user = await bot.fetch_user(user_id)
        
        await target_server.unban(user, reason=f"Ручная разблокировка от {ctx.author}")
        role_bot.banned_users.discard(user_id)
        
        await ctx.send(f"✅ Пользователь {user.display_name} разблокирован")
        await role_bot.log_to_channel(
            f"🔓 **Ручная разблокировка**\n"
            f"• Пользователь: `{user.display_name}`\n"
            f"• ID: `{user_id}`\n"
            f"• Администратор: {ctx.author.mention}",
            color=0x00ff00
        )
        
    except Exception as e:
        await ctx.send(f"❌ Ошибка при разблокировке: {e}")

@bot.command(name='status')
async def bot_status(ctx):
    """Показать статус бота"""
    uptime = datetime.now() - role_bot.start_time
    status_msg = (
        f"🤖 **Статус бота**\n"
        f"• Работает: `{role_bot.is_monitoring}`\n"
        f"• Uptime: `{str(uptime).split('.')[0]}`\n"
        f"• Интервал проверки: `10 секунд`\n"
        f"• Забанено: `{len(role_bot.banned_users)}` пользователей\n"
        f"• Проверяемые роли: `{len(SOURCE_ROLE_IDS)}`"
    )
    await ctx.send(status_msg)

# Запуск бота
def main():
    print("🚀 Запуск Role Sync Bot...")
    print(f"🔍 Будет проверять {len(SOURCE_ROLE_IDS)} ролей")
    print(f"⏰ Интервал проверки: каждые 10 секунд")
    print(f"🔨 Автобан: 24 часа при отсутствии ролей")
    
    # Получаем токен из переменных окружения
    token = os.getenv('DISCORD_TOKEN')
    
    if not token:
        print("❌ Ошибка: DISCORD_TOKEN не найден в переменных окружения")
        return
    
    while True:
        try:
            bot.run(token)
        except KeyboardInterrupt:
            print("\n🛑 Бот остановлен пользователем")
            break
        except Exception as e:
            print(f"❌ Критическая ошибка: {e}")
            print("🔄 Перезапуск через 10 секунд...")
            asyncio.sleep(10)

if __name__ == "__main__":
    main()