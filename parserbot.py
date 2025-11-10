import discord
from discord.ext import commands, tasks
import asyncio
import re
from datetime import datetime, timedelta
import traceback
import sys
import os

# Настройки бота
SOURCE_SERVER_ID = 1003525677640851496  # Первый сервер-источник
SOURCE_SERVER_2_ID = 1384222670635405425  # Второй сервер-источник
TARGET_SERVER_ID = 1437338164292485122  # Целевой сервер (куда выдаём роли)

# Роли для проверки на первом сервере
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

# Роли для проверки на втором сервере
SOURCE_2_ROLE_IDS = [
    1384610338858860646  # Роль на втором сервере
]

# Целевые роли для выдачи
TARGET_ROLE_ID = 1437338476147380235    # Первая целевая роль
TARGET_ROLE_2_ID = 1437438016867274862  # Вторая целевая роль

LOG_CHANNEL_ID = 1437338399206805625    # Канал для логов

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

    async def ban_user(self, user_id, username, reason="Отсутствие требуемых ролей на обоих серверах"):
        """Банит пользователя на 24 часа"""
        try:
            target_server = bot.get_guild(TARGET_SERVER_ID)
            user = await bot.fetch_user(user_id)
            
            # Баним на 24 часа
            ban_duration = timedelta(hours=24)
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
                    f"• Участник лишён необходимых ролей на всех серверах\n\n"
                    f"**Статус:**\n"
                    f"• Бан на 24 часа\n"
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
            print(f"🔨 Забанен пользователь {username} ({user_id}) на 24 часа")
            
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

    async def check_user_roles(self, user_id):
        """Проверяет роли пользователя на обоих серверах"""
        try:
            source_server = bot.get_guild(SOURCE_SERVER_ID)
            source_server_2 = bot.get_guild(SOURCE_SERVER_2_ID)
            
            has_first_server_roles = False
            has_second_server_roles = False
            found_roles_first = []
            found_roles_second = []
            
            # Проверяем первый сервер
            if source_server:
                source_member = source_server.get_member(user_id)
                if source_member:
                    for role_id in SOURCE_ROLE_IDS:
                        role = source_server.get_role(role_id)
                        if role and role in source_member.roles:
                            has_first_server_roles = True
                            found_roles_first.append(role.name)
            
            # Проверяем второй сервер
            if source_server_2:
                source_member_2 = source_server_2.get_member(user_id)
                if source_member_2:
                    for role_id in SOURCE_2_ROLE_IDS:
                        role = source_server_2.get_role(role_id)
                        if role and role in source_member_2.roles:
                            has_second_server_roles = True
                            found_roles_second.append(role.name)
            
            return {
                'has_first_server': has_first_server_roles,
                'has_second_server': has_second_server_roles,
                'found_roles_first': found_roles_first,
                'found_roles_second': found_roles_second,
                'has_any_roles': has_first_server_roles or has_second_server_roles
            }
            
        except Exception as e:
            print(f"❌ Ошибка при проверке ролей пользователя {user_id}: {e}")
            return {
                'has_first_server': False,
                'has_second_server': False,
                'found_roles_first': [],
                'found_roles_second': [],
                'has_any_roles': False
            }

    async def check_and_sync_user(self, user_id, username=None, check_ban=True):
        """Проверяет роли пользователя и синхронизирует"""
        try:
            target_server = bot.get_guild(TARGET_SERVER_ID)
            if not target_server:
                return False
            
            target_role = target_server.get_role(TARGET_ROLE_ID)
            target_role_2 = target_server.get_role(TARGET_ROLE_2_ID)
            
            if not target_role or not target_role_2:
                return False
            
            # Получаем пользователя на целевом сервере
            target_member = target_server.get_member(user_id)
            if not target_member:
                return False
            
            # Проверяем роли на обоих серверах
            role_check = await self.check_user_roles(user_id)
            username = username or target_member.display_name
            
            # Проверяем текущее состояние ролей
            has_target_role = target_role in target_member.roles
            has_target_role_2 = target_role_2 in target_member.roles
            
            # Логика выдачи/удаления ролей
            actions_performed = []
            
            # Первая роль (первый сервер)
            if role_check['has_first_server'] and not has_target_role:
                try:
                    await target_member.add_roles(target_role, reason="Автоматическая синхронизация - первый сервер")
                    actions_performed.append(f"✅ Выдана первая роль")
                    print(f"✅ Выдана первая роль пользователю {username} ({user_id})")
                except Exception as e:
                    print(f"❌ Ошибка при выдаче первой роли: {e}")
            elif not role_check['has_first_server'] and has_target_role:
                try:
                    await target_member.remove_roles(target_role, reason="Автоматическая синхронизация - нет ролей на первом сервере")
                    actions_performed.append(f"🗑️ Удалена первая роль")
                    print(f"🗑️ Удалена первая роль у пользователя {username} ({user_id})")
                except Exception as e:
                    print(f"❌ Ошибка при удалении первой роли: {e}")
            
            # Вторая роль (второй сервер)
            if role_check['has_second_server'] and not has_target_role_2:
                try:
                    await target_member.add_roles(target_role_2, reason="Автоматическая синхронизация - второй сервер")
                    actions_performed.append(f"✅ Выдана вторая роль")
                    print(f"✅ Выдана вторая роль пользователю {username} ({user_id})")
                except Exception as e:
                    print(f"❌ Ошибка при выдаче второй роли: {e}")
            elif not role_check['has_second_server'] and has_target_role_2:
                try:
                    await target_member.remove_roles(target_role_2, reason="Автоматическая синхронизация - нет ролей на втором сервере")
                    actions_performed.append(f"🗑️ Удалена вторая роль")
                    print(f"🗑️ Удалена вторая роль у пользователя {username} ({user_id})")
                except Exception as e:
                    print(f"❌ Ошибка при удалении второй роли: {e}")
            
            # Логируем действия если они были
            if actions_performed:
                log_msg = (
                    f"🔧 **Синхронизация ролей**\n"
                    f"• Пользователь: `{username}`\n"
                    f"• ID: `{user_id}`\n"
                    f"• Первый сервер: {'✅' if role_check['has_first_server'] else '❌'} {', '.join(role_check['found_roles_first']) if role_check['found_roles_first'] else 'Нет ролей'}\n"
                    f"• Второй сервер: {'✅' if role_check['has_second_server'] else '❌'} {', '.join(role_check['found_roles_second']) if role_check['found_roles_second'] else 'Нет ролей'}\n"
                    f"• Действия: {', '.join(actions_performed)}"
                )
                await self.log_to_channel(log_msg, color=0x0099ff)
            
            # Бан только если нет ролей на ЛЮБОМ из серверов
            if check_ban and not role_check['has_any_roles'] and user_id not in self.banned_users:
                # Проверяем есть ли у пользователя хотя бы одна из целевых ролей
                has_any_target_role = has_target_role or has_target_role_2
                if has_any_target_role:
                    ban_result = await self.ban_user(user_id, username, "Отсутствие требуемых ролей на всех серверах")
                    if ban_result:
                        log_msg = (
                            f"🔨 **Пользователь забанен**\n"
                            f"• Пользователь: `{username}`\n"
                            f"• ID: `{user_id}`\n"
                            f"• Причина: Нет требуемых ролей на обоих серверах\n"
                            f"• Длительность: 24 часа"
                        )
                        await self.log_to_channel(log_msg, color=0xff6600)
                        return True
            
            return len(actions_performed) > 0
                
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
                        
                        # Выполняем проверку и синхронизацию
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
    print(f'🔍 Проверяемые серверы: 2')
    print(f'⏰ Интервал проверки: каждые 10 секунд')
    print('------')
    
    # Устанавливаем статус бота
    activity = discord.Activity(type=discord.ActivityType.watching, name="2 сервера | 10 сек")
    await bot.change_presence(activity=activity)
    
    # Загружаем список забаненных пользователей
    await load_banned_users()
    
    # Отправляем сообщение о запуске в канал логов
    startup_msg = (
        f"🟢 **Role Sync Bot запущен**\n"
        f"• Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"• Статус: Мониторинг активен\n"
        f"• Серверы для проверки: `2`\n"
        f"• Интервал проверки: `10 секунд`\n"
        f"• Автобан: только если нет ролей на ВСЕХ серверах"
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
            print(f"🔄 Начинаю проверку {len(target_server.members)} пользователей на 2 серверах...")
            role_bot.last_check = current_time
        
        for member in target_server.members:
            if member.bot:
                continue
                
            processed += 1
            result = await role_bot.check_and_sync_user(member.id, check_ban=True)
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

@bot.command(name='check_user')
async def check_specific_user(ctx, user: discord.Member = None):
    """Проверить статус пользователя на обоих серверах"""
    if user is None:
        user = ctx.author
    
    role_check = await role_bot.check_user_roles(user.id)
    
    status_msg = (
        f"🔍 **Статус пользователя {user.mention}**\n"
        f"• Первый сервер: {'✅' if role_check['has_first_server'] else '❌'} {', '.join(role_check['found_roles_first']) if role_check['found_roles_first'] else 'Нет ролей'}\n"
        f"• Второй сервер: {'✅' if role_check['has_second_server'] else '❌'} {', '.join(role_check['found_roles_second']) if role_check['found_roles_second'] else 'Нет ролей'}\n"
        f"• Общий статус: {'🟢 Есть роли' if role_check['has_any_roles'] else '🔴 Нет ролей'}"
    )
    
    await ctx.send(status_msg)

@bot.command(name='force_check')
@commands.has_permissions(administrator=True)
async def force_check(ctx):
    """Принудительная проверка всех пользователей"""
    await ctx.send("🔄 Запускаю принудительную проверку всех пользователей на 2 серверах...")
    await sync_all_users()
    await ctx.send("✅ Проверка завершена")

@bot.command(name='status')
async def bot_status(ctx):
    """Показать статус бота"""
    uptime = datetime.now() - role_bot.start_time
    status_msg = (
        f"🤖 **Статус бота**\n"
        f"• Работает: `{role_bot.is_monitoring}`\n"
        f"• Uptime: `{str(uptime).split('.')[0]}`\n"
        f"• Интервал проверки: `10 секунд`\n"
        f"• Серверы для проверки: `2`\n"
        f"• Забанено: `{len(role_bot.banned_users)}` пользователей"
    )
    await ctx.send(status_msg)

# Запуск бота
def main():
    print("🚀 Запуск Role Sync Bot с 2 серверами...")
    print(f"🔍 Сервер 1: {SOURCE_SERVER_ID}")
    print(f"🔍 Сервер 2: {SOURCE_SERVER_2_ID}")
    print(f"⏰ Интервал проверки: каждые 10 секунд")
    print(f"🔨 Автобан: только если нет ролей на ВСЕХ серверах")
    
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