import discord
from discord.ext import commands, tasks
import asyncio
import re
from datetime import datetime, timedelta
import traceback
import sys
import os
import logging

# ОТКЛЮЧАЕМ ВСЕ ЛОГИ ДЛЯ RAILWAY
logging.getLogger('discord').setLevel(logging.ERROR)
logging.getLogger('discord.client').setLevel(logging.ERROR)
logging.getLogger('discord.gateway').setLevel(logging.ERROR)
logging.getLogger('asyncio').setLevel(logging.ERROR)

# Проверяем, запущен ли бот на Railway
IS_RAILWAY = os.environ.get('RAILWAY_ENVIRONMENT') is not None

if IS_RAILWAY:
    # На Railway отключаем весь вывод в консоль
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')

# Настройки бота
SOURCE_SERVER_ID = 1003525677640851496
SOURCE_SERVER_2_ID = 1135475290630529044
SOURCE_SERVER_3_ID = 1404969894562500718
SOURCE_SERVER_4_ID = 1393772967569260627
SOURCE_SERVER_5_ID = 1084418816571879464
SOURCE_SERVER_6_ID = 1346249563270414469
SOURCE_SERVER_7_ID = 1150420551324672030
TARGET_SERVER_ID = 1437338164292485122

# Роли для проверки
SOURCE_ROLE_IDS = [1481402373879365835]
SOURCE_2_ROLE_IDS = [1353826792443609110, 1135478212584022026]
SOURCE_3_ROLE_IDS = [1404969894574952557, 1404969894574952556]
SOURCE_4_ROLE_IDS = [1393776465639899197]
SOURCE_5_ROLE_IDS = [1084418816647368768, 1084418816647368769]
SOURCE_6_ROLE_IDS = [1462692338127077531]
SOURCE_7_ROLE_IDS = [1150422789778591764, 1424882436294049873, 1251618206905405573]

# Целевые роли
TARGET_ROLE_ID = 1437338476147380235
TARGET_ROLE_2_ID = 1485619582214475867
TARGET_ROLE_3_ID = 1485619744320127100
TARGET_ROLE_4_ID = 1485685800388530198
TARGET_ROLE_5_ID = 1485994860962910289
TARGET_ROLE_6_ID = 1491118136207085758
TARGET_ROLE_7_ID = 1491909211263864833

LOG_CHANNEL_ID = 1485618781807050914

# Настройка интентов
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.bans = True

bot = commands.Bot(command_prefix='!', intents=intents)

class UnbanButton(discord.ui.View):
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
        self.banned_users = {}
        self.last_check = datetime.now()

    async def log_to_channel(self, message, color=0x00ff00, view=None):
        try:
            channel = bot.get_channel(LOG_CHANNEL_ID)
            if channel:
                embed = discord.Embed(description=message, color=color, timestamp=datetime.now())
                await channel.send(embed=embed, view=view)
        except Exception:
            pass

    async def ban_user(self, user_id, username, reason="Отсутствие требуемых ролей на всех серверах"):
        try:
            target_server = bot.get_guild(TARGET_SERVER_ID)
            user = await bot.fetch_user(user_id)
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
            
            self.banned_users[user_id] = datetime.now()
            return True
        except Exception as e:
            await self.log_to_channel(f"❌ Ошибка при бане пользователя `{username}`: {e}", color=0xff0000)
            return False

    async def auto_unban_users(self):
        try:
            target_server = bot.get_guild(TARGET_SERVER_ID)
            if not target_server:
                return
            
            current_time = datetime.now()
            users_to_unban = []
            
            for user_id, ban_time in list(self.banned_users.items()):
                if (current_time - ban_time).total_seconds() >= 600:
                    users_to_unban.append(user_id)
            
            for user_id in users_to_unban:
                try:
                    user = await bot.fetch_user(user_id)
                    await target_server.unban(user, reason="Автоматический разбан после 10 минут")
                    del self.banned_users[user_id]
                    await self.log_to_channel(
                        f"🔓 **Автоматический разбан**\n• Пользователь: `{user.display_name}`\n• ID: `{user_id}`",
                        color=0x00ff00
                    )
                except:
                    del self.banned_users[user_id]
        except Exception:
            pass

    async def check_user_roles(self, user_id):
        try:
            source_server = bot.get_guild(SOURCE_SERVER_ID)
            source_server_2 = bot.get_guild(SOURCE_SERVER_2_ID)
            source_server_3 = bot.get_guild(SOURCE_SERVER_3_ID)
            source_server_4 = bot.get_guild(SOURCE_SERVER_4_ID)
            source_server_5 = bot.get_guild(SOURCE_SERVER_5_ID)
            source_server_6 = bot.get_guild(SOURCE_SERVER_6_ID)
            source_server_7 = bot.get_guild(SOURCE_SERVER_7_ID)
            
            has_first_server_roles = False
            has_second_server_roles = False
            has_third_server_roles = False
            has_fourth_server_roles = False
            has_fifth_server_roles = False
            has_sixth_server_roles = False
            has_seventh_server_roles = False
            found_roles_first = []
            found_roles_second = []
            found_roles_third = []
            found_roles_fourth = []
            found_roles_fifth = []
            found_roles_sixth = []
            found_roles_seventh = []
            
            if source_server:
                source_member = source_server.get_member(user_id)
                if source_member:
                    for role_id in SOURCE_ROLE_IDS:
                        role = source_server.get_role(role_id)
                        if role and role in source_member.roles:
                            has_first_server_roles = True
                            found_roles_first.append(f"{role.name}")
            
            if source_server_2:
                source_member_2 = source_server_2.get_member(user_id)
                if source_member_2:
                    for role_id in SOURCE_2_ROLE_IDS:
                        role = source_server_2.get_role(role_id)
                        if role and role in source_member_2.roles:
                            has_second_server_roles = True
                            found_roles_second.append(f"{role.name}")
            
            if source_server_3:
                source_member_3 = source_server_3.get_member(user_id)
                if source_member_3:
                    for role_id in SOURCE_3_ROLE_IDS:
                        role = source_server_3.get_role(role_id)
                        if role and role in source_member_3.roles:
                            has_third_server_roles = True
                            found_roles_third.append(f"{role.name}")
            
            if source_server_4:
                source_member_4 = source_server_4.get_member(user_id)
                if source_member_4:
                    for role_id in SOURCE_4_ROLE_IDS:
                        role = source_server_4.get_role(role_id)
                        if role and role in source_member_4.roles:
                            has_fourth_server_roles = True
                            found_roles_fourth.append(f"{role.name}")
            
            if source_server_5:
                source_member_5 = source_server_5.get_member(user_id)
                if source_member_5:
                    for role_id in SOURCE_5_ROLE_IDS:
                        role = source_server_5.get_role(role_id)
                        if role and role in source_member_5.roles:
                            has_fifth_server_roles = True
                            found_roles_fifth.append(f"{role.name}")
            
            if source_server_6:
                source_member_6 = source_server_6.get_member(user_id)
                if source_member_6:
                    for role_id in SOURCE_6_ROLE_IDS:
                        role = source_server_6.get_role(role_id)
                        if role and role in source_member_6.roles:
                            has_sixth_server_roles = True
                            found_roles_sixth.append(f"{role.name}")
            
            if source_server_7:
                source_member_7 = source_server_7.get_member(user_id)
                if source_member_7:
                    for role_id in SOURCE_7_ROLE_IDS:
                        role = source_server_7.get_role(role_id)
                        if role and role in source_member_7.roles:
                            has_seventh_server_roles = True
                            found_roles_seventh.append(f"{role.name}")
            
            has_any_roles = (has_first_server_roles or has_second_server_roles or has_third_server_roles or 
                           has_fourth_server_roles or has_fifth_server_roles or has_sixth_server_roles or 
                           has_seventh_server_roles)
            
            return {
                'has_first_server': has_first_server_roles,
                'has_second_server': has_second_server_roles,
                'has_third_server': has_third_server_roles,
                'has_fourth_server': has_fourth_server_roles,
                'has_fifth_server': has_fifth_server_roles,
                'has_sixth_server': has_sixth_server_roles,
                'has_seventh_server': has_seventh_server_roles,
                'found_roles_first': found_roles_first,
                'found_roles_second': found_roles_second,
                'found_roles_third': found_roles_third,
                'found_roles_fourth': found_roles_fourth,
                'found_roles_fifth': found_roles_fifth,
                'found_roles_sixth': found_roles_sixth,
                'found_roles_seventh': found_roles_seventh,
                'has_any_roles': has_any_roles
            }
        except Exception:
            return {
                'has_first_server': False, 'has_second_server': False, 'has_third_server': False,
                'has_fourth_server': False, 'has_fifth_server': False, 'has_sixth_server': False,
                'has_seventh_server': False, 'has_any_roles': False,
                'found_roles_first': [], 'found_roles_second': [], 'found_roles_third': [],
                'found_roles_fourth': [], 'found_roles_fifth': [], 'found_roles_sixth': [],
                'found_roles_seventh': []
            }

    async def check_and_sync_user(self, user_id, username=None, check_ban=True):
        try:
            target_server = bot.get_guild(TARGET_SERVER_ID)
            if not target_server:
                return False
            
            target_role = target_server.get_role(TARGET_ROLE_ID)
            target_role_2 = target_server.get_role(TARGET_ROLE_2_ID)
            target_role_3 = target_server.get_role(TARGET_ROLE_3_ID)
            target_role_4 = target_server.get_role(TARGET_ROLE_4_ID)
            target_role_5 = target_server.get_role(TARGET_ROLE_5_ID)
            target_role_6 = target_server.get_role(TARGET_ROLE_6_ID)
            target_role_7 = target_server.get_role(TARGET_ROLE_7_ID)
            
            if not all([target_role, target_role_2, target_role_3, target_role_4, target_role_5, target_role_6, target_role_7]):
                return False
            
            target_member = target_server.get_member(user_id)
            if not target_member:
                return False
            
            role_check = await self.check_user_roles(user_id)
            username = username or target_member.display_name
            
            has_target_role = target_role in target_member.roles
            has_target_role_2 = target_role_2 in target_member.roles
            has_target_role_3 = target_role_3 in target_member.roles
            has_target_role_4 = target_role_4 in target_member.roles
            has_target_role_5 = target_role_5 in target_member.roles
            has_target_role_6 = target_role_6 in target_member.roles
            has_target_role_7 = target_role_7 in target_member.roles
            
            actions_performed = []
            
            # Первая роль
            if role_check['has_first_server'] and not has_target_role:
                await target_member.add_roles(target_role, reason="Автосинхронизация")
                actions_performed.append("✅ Выдана первая роль")
            elif not role_check['has_first_server'] and has_target_role:
                await target_member.remove_roles(target_role, reason="Автосинхронизация")
                actions_performed.append("🗑️ Удалена первая роль")
            
            # Вторая роль
            if role_check['has_second_server'] and not has_target_role_2:
                await target_member.add_roles(target_role_2, reason="Автосинхронизация")
                actions_performed.append("✅ Выдана вторая роль")
            elif not role_check['has_second_server'] and has_target_role_2:
                await target_member.remove_roles(target_role_2, reason="Автосинхронизация")
                actions_performed.append("🗑️ Удалена вторая роль")
            
            # Третья роль
            if role_check['has_third_server'] and not has_target_role_3:
                await target_member.add_roles(target_role_3, reason="Автосинхронизация")
                actions_performed.append("✅ Выдана третья роль")
            elif not role_check['has_third_server'] and has_target_role_3:
                await target_member.remove_roles(target_role_3, reason="Автосинхронизация")
                actions_performed.append("🗑️ Удалена третья роль")
            
            # Четвертая роль
            if role_check['has_fourth_server'] and not has_target_role_4:
                await target_member.add_roles(target_role_4, reason="Автосинхронизация")
                actions_performed.append("✅ Выдана четвертая роль")
            elif not role_check['has_fourth_server'] and has_target_role_4:
                await target_member.remove_roles(target_role_4, reason="Автосинхронизация")
                actions_performed.append("🗑️ Удалена четвертая роль")
            
            # Пятая роль
            if role_check['has_fifth_server'] and not has_target_role_5:
                await target_member.add_roles(target_role_5, reason="Автосинхронизация")
                actions_performed.append("✅ Выдана пятая роль")
            elif not role_check['has_fifth_server'] and has_target_role_5:
                await target_member.remove_roles(target_role_5, reason="Автосинхронизация")
                actions_performed.append("🗑️ Удалена пятая роль")
            
            # Шестая роль
            if role_check['has_sixth_server'] and not has_target_role_6:
                await target_member.add_roles(target_role_6, reason="Автосинхронизация")
                actions_performed.append("✅ Выдана шестая роль")
            elif not role_check['has_sixth_server'] and has_target_role_6:
                await target_member.remove_roles(target_role_6, reason="Автосинхронизация")
                actions_performed.append("🗑️ Удалена шестая роль")
            
            # Седьмая роль
            if role_check['has_seventh_server'] and not has_target_role_7:
                await target_member.add_roles(target_role_7, reason="Автосинхронизация")
                actions_performed.append("✅ Выдана седьмая роль")
            elif not role_check['has_seventh_server'] and has_target_role_7:
                await target_member.remove_roles(target_role_7, reason="Автосинхронизация")
                actions_performed.append("🗑️ Удалена седьмая роль")
            
            if actions_performed:
                log_msg = (
                    f"🔧 **Синхронизация ролей**\n"
                    f"• Пользователь: `{username}`\n"
                    f"• ID: `{user_id}`\n"
                    f"• Действия: {', '.join(actions_performed)}"
                )
                await self.log_to_channel(log_msg, color=0x0099ff)
            
            if check_ban and not role_check['has_any_roles']:
                has_any_target_role = (has_target_role or has_target_role_2 or has_target_role_3 or 
                                      has_target_role_4 or has_target_role_5 or has_target_role_6 or 
                                      has_target_role_7)
                
                if user_id not in self.banned_users:
                    await self.ban_user(user_id, username)
                    return True
            
            return len(actions_performed) > 0
        except Exception:
            return False

    async def parse_snitch_message(self, message):
        try:
            content = message.content
            if "Потеря ролей:" in content and "Участник лишён необходимых ролей" in content:
                name_match = re.search(r"Имя:\s*(.+)", content)
                mention_match = re.search(r"Упоминание:\s*(<@!?(\d+)>)", content)
                
                if name_match and mention_match:
                    username = name_match.group(1).strip()
                    user_id = mention_match.group(2)
                    await self.check_and_sync_user(int(user_id), username, check_ban=True)
        except Exception:
            pass

role_bot = RoleSyncBot()

@bot.event
async def on_ready():
    print("Bot started")  # Только этот лог останется
    
    source_server = bot.get_guild(SOURCE_SERVER_ID)
    source_server_2 = bot.get_guild(SOURCE_SERVER_2_ID)
    source_server_3 = bot.get_guild(SOURCE_SERVER_3_ID)
    source_server_4 = bot.get_guild(SOURCE_SERVER_4_ID)
    source_server_5 = bot.get_guild(SOURCE_SERVER_5_ID)
    source_server_6 = bot.get_guild(SOURCE_SERVER_6_ID)
    source_server_7 = bot.get_guild(SOURCE_SERVER_7_ID)
    target_server = bot.get_guild(TARGET_SERVER_ID)
    
    activity = discord.Activity(type=discord.ActivityType.watching, name="7 серверов | 5 сек")
    await bot.change_presence(activity=activity)
    
    await load_banned_users()
    
    startup_msg = f"🟢 **Role Sync Bot запущен**\n• Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n• Серверов: 7\n• Интервал: 5 секунд"
    await role_bot.log_to_channel(startup_msg, color=0x00ff00)
    
    role_bot.is_monitoring = True
    rapid_sync_task.start()
    auto_unban_task.start()
    
    await bot.wait_until_ready()
    await asyncio.sleep(10)
    await sync_all_users_once()

async def load_banned_users():
    try:
        target_server = bot.get_guild(TARGET_SERVER_ID)
        if target_server:
            bans = [entry async for entry in target_server.bans()]
            for ban_entry in bans:
                role_bot.banned_users[ban_entry.user.id] = datetime.now() - timedelta(minutes=5)
    except Exception:
        pass

async def sync_all_users_once():
    try:
        target_server = bot.get_guild(TARGET_SERVER_ID)
        if not target_server:
            return
        
        members = [member for member in target_server.members if not member.bot]
        total_count = len(members)
        
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            progress_msg = await log_channel.send(f"🔄 **Начинаю проверку всех {total_count} пользователей...**")
        else:
            progress_msg = None
        
        processed = 0
        actions = 0
        
        for member in members:
            processed += 1
            result = await role_bot.check_and_sync_user(member.id, check_ban=True)
            if result:
                actions += 1
            
            if progress_msg and processed % 20 == 0:
                try:
                    await progress_msg.edit(content=f"🔄 **Проверка:** {processed}/{total_count} (действий: {actions})")
                except:
                    pass
            
            await asyncio.sleep(0.05)
        
        if progress_msg:
            await progress_msg.edit(content=f"✅ **Проверка завершена!**\n• Проверено: {processed}\n• Действий: {actions}")
    except Exception:
        pass

@tasks.loop(seconds=5)
async def rapid_sync_task():
    try:
        await sync_all_users()
    except Exception:
        pass

@tasks.loop(minutes=1)
async def auto_unban_task():
    try:
        await role_bot.auto_unban_users()
    except Exception:
        pass

async def sync_all_users():
    try:
        target_server = bot.get_guild(TARGET_SERVER_ID)
        if not target_server:
            return
        
        for member in target_server.members:
            if member.bot:
                continue
            await role_bot.check_and_sync_user(member.id, check_ban=True)
            await asyncio.sleep(0.02)
    except Exception:
        pass

@bot.event
async def on_message(message):
    try:
        if message.author == bot.user:
            return
        
        if message.channel.id == LOG_CHANNEL_ID:
            await role_bot.parse_snitch_message(message)
        
        await bot.process_commands(message)
    except Exception:
        pass

@bot.command(name='check_user')
@commands.has_permissions(administrator=True)
async def check_user_command(ctx, user: discord.Member = None):
    if not user:
        user = ctx.author
    
    await ctx.send(f"🔍 Проверяю пользователя {user.mention}...")
    
    try:
        role_check = await role_bot.check_user_roles(user.id)
        result = await role_bot.check_and_sync_user(user.id, check_ban=True)
        
        target_server = bot.get_guild(TARGET_SERVER_ID)
        target_role = target_server.get_role(TARGET_ROLE_ID)
        target_role_2 = target_server.get_role(TARGET_ROLE_2_ID)
        target_role_3 = target_server.get_role(TARGET_ROLE_3_ID)
        target_role_4 = target_server.get_role(TARGET_ROLE_4_ID)
        target_role_5 = target_server.get_role(TARGET_ROLE_5_ID)
        target_role_6 = target_server.get_role(TARGET_ROLE_6_ID)
        target_role_7 = target_server.get_role(TARGET_ROLE_7_ID)
        
        has_target_role = target_role in user.roles if target_role else False
        has_target_role_2 = target_role_2 in user.roles if target_role_2 else False
        has_target_role_3 = target_role_3 in user.roles if target_role_3 else False
        has_target_role_4 = target_role_4 in user.roles if target_role_4 else False
        has_target_role_5 = target_role_5 in user.roles if target_role_5 else False
        has_target_role_6 = target_role_6 in user.roles if target_role_6 else False
        has_target_role_7 = target_role_7 in user.roles if target_role_7 else False
        
        report = (
            f"📋 **Отчет по пользователю {user.mention}**\n"
            f"• ID: `{user.id}`\n\n"
            f"**Исходные сервера:**\n"
            f"• Сервер 1: {'✅' if role_check['has_first_server'] else '❌'}\n"
            f"• Сервер 2: {'✅' if role_check['has_second_server'] else '❌'}\n"
            f"• Сервер 3: {'✅' if role_check['has_third_server'] else '❌'}\n"
            f"• Сервер 4: {'✅' if role_check['has_fourth_server'] else '❌'}\n"
            f"• Сервер 5: {'✅' if role_check['has_fifth_server'] else '❌'}\n"
            f"• Сервер 6: {'✅' if role_check['has_sixth_server'] else '❌'}\n"
            f"• Сервер 7: {'✅' if role_check['has_seventh_server'] else '❌'}\n\n"
            f"**Целевые роли:**\n"
            f"• Роль 1: {'✅' if has_target_role else '❌'}\n"
            f"• Роль 2: {'✅' if has_target_role_2 else '❌'}\n"
            f"• Роль 3: {'✅' if has_target_role_3 else '❌'}\n"
            f"• Роль 4: {'✅' if has_target_role_4 else '❌'}\n"
            f"• Роль 5: {'✅' if has_target_role_5 else '❌'}\n"
            f"• Роль 6: {'✅' if has_target_role_6 else '❌'}\n"
            f"• Роль 7: {'✅' if has_target_role_7 else '❌'}\n\n"
            f"**Статус бана:** {'🔨 Забанен' if user.id in role_bot.banned_users else '✅ Не забанен'}"
        )
        await ctx.send(report)
    except Exception as e:
        await ctx.send(f"❌ Ошибка: {e}")

@bot.command(name='stats')
@commands.has_permissions(administrator=True)
async def stats_command(ctx):
    target_server = bot.get_guild(TARGET_SERVER_ID)
    if not target_server:
        await ctx.send("❌ Целевой сервер не доступен")
        return
    
    total_members = len([m for m in target_server.members if not m.bot])
    banned_count = len(role_bot.banned_users)
    
    stats_msg = (
        f"📊 **Статистика**\n"
        f"• Пользователей: {total_members}\n"
        f"• Забанено: {banned_count}\n"
        f"• Серверов: 7\n"
        f"• Интервал: 5 секунд"
    )
    await ctx.send(stats_msg)

# Запуск бота
def main():
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("ERROR: DISCORD_TOKEN not found")
        return
    
    try:
        bot.run(token)
    except Exception as e:
        print(f"Critical error: {e}")

if __name__ == "__main__":
    main()