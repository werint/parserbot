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
SOURCE_SERVER_3_ID = 1146542493584850955  # Третий сервер-источник
SOURCE_SERVER_4_ID = 819875298392408065   # Четвертый сервер-источник
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
    1384610338858860646
]

# Роли для проверки на третьем сервере
SOURCE_3_ROLE_IDS = [
    1148223265970593842,
    1148738387226927344,
    1155752556094566400,
    1146546952830455999,
    1146542546231763015,
    1169961441189707906  # ← ДОБАВЛЕНА НОВАЯ РОЛЬ
]

# Роли для проверки на четвертом сервере
SOURCE_4_ROLE_IDS = [
    931885444944232458
]

# Целевые роли для выдачи
TARGET_ROLE_ID = 1437338476147380235    # Первая целевая роль (первый сервер)
TARGET_ROLE_2_ID = 1437438016867274862  # Вторая целевая роль (второй сервер)
TARGET_ROLE_3_ID = 1437367354446315551  # Третья целевая роль (третий сервер)
TARGET_ROLE_4_ID = 1437527115267571983  # Четвертая целевая роль (четвертый сервер)

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
            target_server = bot.get_guild(TARGET_SERVER_ID)
            user = await bot.fetch_user(self.user_id)
            
            await target_server.unban(user, reason="Разблокировка через кнопку")
            
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
        self.banned_users = {}  # Теперь храним время бана {user_id: ban_time}
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

    async def ban_user(self, user_id, username, reason="Отсутствие требуемых ролей на всех серверах"):
        """Банит пользователя на 10 минут"""
        try:
            target_server = bot.get_guild(TARGET_SERVER_ID)
            user = await bot.fetch_user(user_id)
            
            # Баним на 10 минут
            ban_duration = timedelta(minutes=10)
            ban_reason = f"{reason} | Автобан до {(datetime.now() + ban_duration).strftime('%d.%m.%Y %H:%M')}"
            
            await target_server.ban(user, reason=ban_reason, delete_message_days=0)
            
            ban_embed = discord.Embed(
                description=(
                    f"🔨 **Пользователь заблокирован**\n"
                    f"• Имя: `{username}`\n"
                    f"• Упоминание: <@{user_id}>\n"
                    f"• Профиль: [Перейти](https://discord.com/users/{user_id})\n\n"
                    f"**Причина:**\n"
                    f"• Участник лишён необходимых ролей на всех серверах\n\n"
                    f"**Статус:**\n"
                    f"• Бан на 10 минут\n"
                    f"• Авторазбан: {(datetime.now() + ban_duration).strftime('%d.%m.%Y %H:%M')}"
                ),
                color=0xff0000,
                timestamp=datetime.now()
            )
            
            channel = bot.get_channel(LOG_CHANNEL_ID)
            if channel:
                await channel.send(embed=ban_embed, view=UnbanButton(user_id))
            
            # Сохраняем время бана
            self.banned_users[user_id] = datetime.now()
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

    async def auto_unban_users(self):
        """Автоматически разбанивает пользователей после 10 минут"""
        try:
            target_server = bot.get_guild(TARGET_SERVER_ID)
            if not target_server:
                return
            
            current_time = datetime.now()
            users_to_unban = []
            
            # Проверяем всех забаненных пользователей
            for user_id, ban_time in list(self.banned_users.items()):
                ban_duration = current_time - ban_time
                
                # Если прошло больше 10 минут - разбаниваем
                if ban_duration.total_seconds() >= 600:  # 600 секунд = 10 минут
                    users_to_unban.append(user_id)
            
            # Разбаниваем пользователей
            for user_id in users_to_unban:
                try:
                    user = await bot.fetch_user(user_id)
                    await target_server.unban(user, reason="Автоматический разбан после 10 минут")
                    
                    # Удаляем из списка забаненных
                    del self.banned_users[user_id]
                    
                    log_msg = (
                        f"🔓 **Автоматический разбан**\n"
                        f"• Пользователь: `{user.display_name}`\n"
                        f"• ID: `{user_id}`\n"
                        f"• Бан длился: 10 минут\n"
                        f"• Время разбана: {current_time.strftime('%d.%m.%Y %H:%M:%S')}"
                    )
                    await self.log_to_channel(log_msg, color=0x00ff00)
                    print(f"🔓 Автоматически разбанен пользователь {user.display_name} ({user_id})")
                    
                except discord.NotFound:
                    # Пользователь уже разбанен или не найден
                    del self.banned_users[user_id]
                except Exception as e:
                    print(f"❌ Ошибка при авторазбане пользователя {user_id}: {e}")
            
            if users_to_unban:
                print(f"✅ Автоматически разбанено {len(users_to_unban)} пользователей")
                
        except Exception as e:
            print(f"❌ Ошибка в авторазбане: {e}")

    async def check_user_roles(self, user_id):
        """Проверяет роли пользователя на всех серверах"""
        try:
            source_server = bot.get_guild(SOURCE_SERVER_ID)
            source_server_2 = bot.get_guild(SOURCE_SERVER_2_ID)
            source_server_3 = bot.get_guild(SOURCE_SERVER_3_ID)
            source_server_4 = bot.get_guild(SOURCE_SERVER_4_ID)
            
            has_first_server_roles = False
            has_second_server_roles = False
            has_third_server_roles = False
            has_fourth_server_roles = False
            found_roles_first = []
            found_roles_second = []
            found_roles_third = []
            found_roles_fourth = []
            
            # Проверяем первый сервер
            if source_server:
                source_member = source_server.get_member(user_id)
                if source_member:
                    for role_id in SOURCE_ROLE_IDS:
                        role = source_server.get_role(role_id)
                        if role and role in source_member.roles:
                            has_first_server_roles = True
                            found_roles_first.append(f"{role.name} ({role.id})")
            
            # Проверяем второй сервер
            if source_server_2:
                source_member_2 = source_server_2.get_member(user_id)
                if source_member_2:
                    for role_id in SOURCE_2_ROLE_IDS:
                        role = source_server_2.get_role(role_id)
                        if role and role in source_member_2.roles:
                            has_second_server_roles = True
                            found_roles_second.append(f"{role.name} ({role.id})")
            
            # Проверяем третий сервер
            if source_server_3:
                source_member_3 = source_server_3.get_member(user_id)
                if source_member_3:
                    for role_id in SOURCE_3_ROLE_IDS:
                        role = source_server_3.get_role(role_id)
                        if role and role in source_member_3.roles:
                            has_third_server_roles = True
                            found_roles_third.append(f"{role.name} ({role.id})")
            
            # Проверяем четвертый сервер
            if source_server_4:
                source_member_4 = source_server_4.get_member(user_id)
                if source_member_4:
                    for role_id in SOURCE_4_ROLE_IDS:
                        role = source_server_4.get_role(role_id)
                        if role and role in source_member_4.roles:
                            has_fourth_server_roles = True
                            found_roles_fourth.append(f"{role.name} ({role.id})")
            
            has_any_roles = has_first_server_roles or has_second_server_roles or has_third_server_roles or has_fourth_server_roles
            
            return {
                'has_first_server': has_first_server_roles,
                'has_second_server': has_second_server_roles,
                'has_third_server': has_third_server_roles,
                'has_fourth_server': has_fourth_server_roles,
                'found_roles_first': found_roles_first,
                'found_roles_second': found_roles_second,
                'found_roles_third': found_roles_third,
                'found_roles_fourth': found_roles_fourth,
                'has_any_roles': has_any_roles
            }
            
        except Exception as e:
            print(f"❌ Ошибка при проверке ролей пользователя {user_id}: {e}")
            return {
                'has_first_server': False,
                'has_second_server': False,
                'has_third_server': False,
                'has_fourth_server': False,
                'found_roles_first': [],
                'found_roles_second': [],
                'found_roles_third': [],
                'found_roles_fourth': [],
                'has_any_roles': False
            }

    async def check_and_sync_user(self, user_id, username=None, check_ban=True):
        """Проверяет роли пользователя и синхронизирует"""
        try:
            target_server = bot.get_guild(TARGET_SERVER_ID)
            if not target_server:
                print("❌ Целевой сервер не найден")
                return False
            
            target_role = target_server.get_role(TARGET_ROLE_ID)
            target_role_2 = target_server.get_role(TARGET_ROLE_2_ID)
            target_role_3 = target_server.get_role(TARGET_ROLE_3_ID)
            target_role_4 = target_server.get_role(TARGET_ROLE_4_ID)
            
            if not target_role or not target_role_2 or not target_role_3 or not target_role_4:
                return False
            
            target_member = target_server.get_member(user_id)
            if not target_member:
                print(f"❌ Пользователь {user_id} не найден на целевом сервере")
                return False
            
            # Проверяем роли на всех серверах
            role_check = await self.check_user_roles(user_id)
            username = username or target_member.display_name
            
            has_target_role = target_role in target_member.roles
            has_target_role_2 = target_role_2 in target_member.roles
            has_target_role_3 = target_role_3 in target_member.roles
            has_target_role_4 = target_role_4 in target_member.roles
            
            actions_performed = []
            
            # Первая роль (первый сервер)
            if role_check['has_first_server'] and not has_target_role:
                try:
                    await target_member.add_roles(target_role, reason="Автоматическая синхронизация - первый сервер")
                    actions_performed.append("✅ Выдана первая роль")
                    print(f"✅ Выдана первая роль пользователю {username} ({user_id})")
                except Exception as e:
                    print(f"❌ Ошибка при выдаче первой роли: {e}")
            elif not role_check['has_first_server'] and has_target_role:
                try:
                    await target_member.remove_roles(target_role, reason="Автоматическая синхронизация - нет ролей на первом сервере")
                    actions_performed.append("🗑️ Удалена первая роль")
                    print(f"🗑️ Удалена первая роль у пользователя {username} ({user_id})")
                except Exception as e:
                    print(f"❌ Ошибка при удалении первой роли: {e}")
            
            # Вторая роль (второй сервер)
            if role_check['has_second_server'] and not has_target_role_2:
                try:
                    await target_member.add_roles(target_role_2, reason="Автоматическая синхронизация - второй сервер")
                    actions_performed.append("✅ Выдана вторая роль")
                    print(f"✅ Выдана вторая роль пользователю {username} ({user_id})")
                except Exception as e:
                    print(f"❌ Ошибка при выдаче второй роли: {e}")
            elif not role_check['has_second_server'] and has_target_role_2:
                try:
                    await target_member.remove_roles(target_role_2, reason="Автоматическая синхронизация - нет ролей на втором сервере")
                    actions_performed.append("🗑️ Удалена вторая роль")
                    print(f"🗑️ Удалена вторая роль у пользователя {username} ({user_id})")
                except Exception as e:
                    print(f"❌ Ошибка при удалении второй роли: {e}")
            
            # Третья роль (третий сервер)
            if role_check['has_third_server'] and not has_target_role_3:
                try:
                    await target_member.add_roles(target_role_3, reason="Автоматическая синхронизация - третий сервер")
                    actions_performed.append("✅ Выдана третья роль")
                    print(f"✅ Выдана третья роль пользователю {username} ({user_id})")
                except Exception as e:
                    print(f"❌ Ошибка при выдаче третьей роли: {e}")
            elif not role_check['has_third_server'] and has_target_role_3:
                try:
                    await target_member.remove_roles(target_role_3, reason="Автоматическая синхронизация - нет ролей на третьем сервере")
                    actions_performed.append("🗑️ Удалена третья роль")
                    print(f"🗑️ Удалена третья роль у пользователя {username} ({user_id})")
                except Exception as e:
                    print(f"❌ Ошибка при удалении третьей роли: {e}")
            
            # Четвертая роль (четвертый сервер)
            if role_check['has_fourth_server'] and not has_target_role_4:
                try:
                    await target_member.add_roles(target_role_4, reason="Автоматическая синхронизация - четвертый сервер")
                    actions_performed.append("✅ Выдана четвертая роль")
                    print(f"✅ Выдана четвертая роль пользователю {username} ({user_id})")
                except Exception as e:
                    print(f"❌ Ошибка при выдаче четвертой роли: {e}")
            elif not role_check['has_fourth_server'] and has_target_role_4:
                try:
                    await target_member.remove_roles(target_role_4, reason="Автоматическая синхронизация - нет ролей на четвертом сервере")
                    actions_performed.append("🗑️ Удалена четвертая роль")
                    print(f"🗑️ Удалена четвертая роль у пользователя {username} ({user_id})")
                except Exception as e:
                    print(f"❌ Ошибка при удалении четвертой роли: {e}")
            
            # Логируем действия если они были
            if actions_performed:
                log_msg = (
                    f"🔧 **Синхронизация ролей**\n"
                    f"• Пользователь: `{username}`\n"
                    f"• ID: `{user_id}`\n"
                    f"• Первый сервер: {'✅' if role_check['has_first_server'] else '❌'} {', '.join(role_check['found_roles_first']) if role_check['found_roles_first'] else 'Нет ролей'}\n"
                    f"• Второй сервер: {'✅' if role_check['has_second_server'] else '❌'} {', '.join(role_check['found_roles_second']) if role_check['found_roles_second'] else 'Нет ролей'}\n"
                    f"• Третий сервер: {'✅' if role_check['has_third_server'] else '❌'} {', '.join(role_check['found_roles_third']) if role_check['found_roles_third'] else 'Нет ролей'}\n"
                    f"• Четвертый сервер: {'✅' if role_check['has_fourth_server'] else '❌'} {', '.join(role_check['found_roles_fourth']) if role_check['found_roles_fourth'] else 'Нет ролей'}\n"
                    f"• Действия: {', '.join(actions_performed)}"
                )
                await self.log_to_channel(log_msg, color=0x0099ff)
            
            # Бан только если нет ролей на ЛЮБОМ из серверов
            if check_ban and not role_check['has_any_roles'] and user_id not in self.banned_users:
                has_any_target_role = has_target_role or has_target_role_2 or has_target_role_3 or has_target_role_4
                if has_any_target_role:
                    print(f"🔨 Пользователь {username} ({user_id}) подлежит бану - нет ролей ни на одном сервере")
                    ban_result = await self.ban_user(user_id, username, "Отсутствие требуемых ролей на всех серверах")
                    if ban_result:
                        log_msg = (
                            f"🔨 **Пользователь забанен**\n"
                            f"• Пользователь: `{username}`\n"
                            f"• ID: `{user_id}`\n"
                            f"• Причина: Нет требуемых ролей ни на одном сервере\n"
                            f"• Длительность: 10 минут"
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
            
            if "Потеря ролей:" in content and "Участник лишён необходимых ролей" in content:
                name_match = re.search(r"Имя:\s*(.+)", content)
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
    
    # Проверяем доступность серверов
    source_server = bot.get_guild(SOURCE_SERVER_ID)
    source_server_2 = bot.get_guild(SOURCE_SERVER_2_ID)
    source_server_3 = bot.get_guild(SOURCE_SERVER_3_ID)
    source_server_4 = bot.get_guild(SOURCE_SERVER_4_ID)
    target_server = bot.get_guild(TARGET_SERVER_ID)
    
    print(f'🔍 Доступность серверов:')
    print(f'   Первый сервер: {"✅" if source_server else "❌"} {SOURCE_SERVER_ID}')
    print(f'   Второй сервер: {"✅" if source_server_2 else "❌"} {SOURCE_SERVER_2_ID}')
    print(f'   Третий сервер: {"✅" if source_server_3 else "❌"} {SOURCE_SERVER_3_ID}')
    print(f'   Четвертый сервер: {"✅" if source_server_4 else "❌"} {SOURCE_SERVER_4_ID}')
    print(f'   Целевой сервер: {"✅" if target_server else "❌"} {TARGET_SERVER_ID}')
    
    activity = discord.Activity(type=discord.ActivityType.watching, name="4 сервера | 10 сек")
    await bot.change_presence(activity=activity)
    
    await load_banned_users()
    
    startup_msg = (
        f"🟢 **Role Sync Bot запущен**\n"
        f"• Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"• Статус: Мониторинг активен\n"
        f"• Сервер 1: {'✅' if source_server else '❌'} `{SOURCE_SERVER_ID}`\n"
        f"• Сервер 2: {'✅' if source_server_2 else '❌'} `{SOURCE_SERVER_2_ID}`\n"
        f"• Сервер 3: {'✅' if source_server_3 else '❌'} `{SOURCE_SERVER_3_ID}`\n"
        f"• Сервер 4: {'✅' if source_server_4 else '❌'} `{SOURCE_SERVER_4_ID}`\n"
        f"• Целевой сервер: {'✅' if target_server else '❌'} `{TARGET_SERVER_ID}`\n"
        f"• Интервал проверки: `10 секунд`\n"
        f"• Авторазбан: `10 минут`"
    )
    await role_bot.log_to_channel(startup_msg, color=0x00ff00)
    
    role_bot.is_monitoring = True
    rapid_sync_task.start()
    unban_checker.start()
    auto_unban_task.start()

async def load_banned_users():
    """Загружает список забаненных пользователей при запуске"""
    try:
        target_server = bot.get_guild(TARGET_SERVER_ID)
        if target_server:
            bans = [entry async for entry in target_server.bans()]
            for ban_entry in bans:
                # При загрузке ставим текущее время минус 5 минут, чтобы не разбанивать сразу
                role_bot.banned_users[ban_entry.user.id] = datetime.now() - timedelta(minutes=5)
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
        await role_bot.auto_unban_users()
    except Exception as e:
        print(f"❌ Ошибка в проверке банов: {e}")

@tasks.loop(minutes=1)
async def auto_unban_task():
    """Автоматический разбан каждую минуту"""
    try:
        await role_bot.auto_unban_users()
    except Exception as e:
        print(f"❌ Ошибка в авторазбане: {e}")

async def sync_all_users():
    """Синхронизирует всех пользователей на целевом сервере"""
    try:
        target_server = bot.get_guild(TARGET_SERVER_ID)
        if not target_server:
            print("❌ Целевой сервер не доступен для синхронизации")
            return
        
        processed = 0
        actions = 0
        
        for member in target_server.members:
            if member.bot:
                continue
                
            processed += 1
            result = await role_bot.check_and_sync_user(member.id, check_ban=True)
            if result:
                actions += 1
            
            await asyncio.sleep(0.05)
        
        if actions > 0:
            print(f"✅ Проверено {processed} пользователей, выполнено действий: {actions}")
        
    except Exception as e:
        print(f"❌ Ошибка при синхронизации всех пользователей: {e}")

@bot.event
async def on_message(message):
    try:
        if message.author == bot.user:
            return
        
        if message.channel.id == LOG_CHANNEL_ID:
            await role_bot.parse_snitch_message(message)
        
        await bot.process_commands(message)
    except Exception as e:
        print(f"Ошибка в on_message: {e}")

@bot.command(name='debug_user')
@commands.has_permissions(administrator=True)
async def debug_user(ctx, user: discord.Member):
    """Диагностика конкретного пользователя"""
    await ctx.send(f"🔍 Запускаю диагностику для {user.mention}...")
    
    role_check = await role_bot.check_user_roles(user.id)
    
    debug_msg = (
        f"🔧 **Диагностика пользователя {user.mention}**\n"
        f"• ID: `{user.id}`\n"
        f"• Первый сервер: {'✅' if role_check['has_first_server'] else '❌'} {', '.join(role_check['found_roles_first']) if role_check['found_roles_first'] else 'Нет ролей'}\n"
        f"• Второй сервер: {'✅' if role_check['has_second_server'] else '❌'} {', '.join(role_check['found_roles_second']) if role_check['found_roles_second'] else 'Нет ролей'}\n"
        f"• Третий сервер: {'✅' if role_check['has_third_server'] else '❌'} {', '.join(role_check['found_roles_third']) if role_check['found_roles_third'] else 'Нет ролей'}\n"
        f"• Четвертый сервер: {'✅' if role_check['has_fourth_server'] else '❌'} {', '.join(role_check['found_roles_fourth']) if role_check['found_roles_fourth'] else 'Нет ролей'}\n"
        f"• Есть роли на любом сервере: {'✅' if role_check['has_any_roles'] else '❌'}\n"
        f"• Статус бана: {'🔨 Забанен' if user.id in role_bot.banned_users else '✅ Не забанен'}"
    )
    
    await ctx.send(debug_msg)

@bot.command(name='check_bans')
@commands.has_permissions(administrator=True)
async def check_bans(ctx):
    """Показать список забаненных пользователей и время до разбана"""
    try:
        target_server = bot.get_guild(TARGET_SERVER_ID)
        if not target_server:
            await ctx.send("❌ Целевой сервер не доступен")
            return
        
        current_time = datetime.now()
        ban_list = []
        
        for user_id, ban_time in role_bot.banned_users.items():
            try:
                user = await bot.fetch_user(user_id)
                time_passed = current_time - ban_time
                time_remaining = timedelta(minutes=10) - time_passed
                
                if time_remaining.total_seconds() > 0:
                    minutes_remaining = int(time_remaining.total_seconds() // 60)
                    seconds_remaining = int(time_remaining.total_seconds() % 60)
                    ban_list.append(f"• {user.display_name} - {minutes_remaining}м {seconds_remaining}с")
                else:
                    # Должны быть разбанены в следующей проверке
                    ban_list.append(f"• {user.display_name} - ожидает разбана")
                    
            except Exception:
                ban_list.append(f"• ID {user_id} - пользователь не найден")
        
        if ban_list:
            await ctx.send(f"🔨 **Забаненные пользователи ({len(ban_list)}):**\n" + "\n".join(ban_list[:10]))
        else:
            await ctx.send("✅ Нет забаненных пользователей")
            
    except Exception as e:
        await ctx.send(f"❌ Ошибка при получении списка банов: {e}")

# Запуск бота
def main():
    print("🚀 Запуск Role Sync Bot с авторазбаном...")
    print(f"🔍 Серверов для проверки: 4")
    print(f"⏰ Бан: 10 минут")
    print(f"🔄 Авторазбан: каждую минуту")
    
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