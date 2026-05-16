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

# Настройки бота (3 СЕРВЕРА)
SOURCE_SERVER_1_ID = 1003525677640851496  # Первый сервер-источник
SOURCE_SERVER_2_ID = 1404969894562500718  # Второй сервер-источник
SOURCE_SERVER_3_ID = 1084418816571879464  # Третий сервер-источник
TARGET_SERVER_ID = 1437338164292485122     # Целевой сервер (куда выдаём роли)

# Роли для проверки на первом сервере
SOURCE_1_ROLE_IDS = [1481402373879365835]

# Роли для проверки на втором сервере
SOURCE_2_ROLE_IDS = [1404969894574952557, 1404969894574952556]

# Роли для проверки на третьем сервере
SOURCE_3_ROLE_IDS = [1501701988965023805, 1084418816647368768, 1084418816647368769, 1261971136124682271, 1084418816689324067]

# Целевые роли для выдачи
TARGET_ROLE_1_ID = 1437338476147380235  # Первая целевая роль (для первого сервера)
TARGET_ROLE_2_ID = 1485619744320127100  # Вторая целевая роль (для второго сервера)
TARGET_ROLE_3_ID = 1485994860962910289  # Третья целевая роль (для третьего сервера)

LOG_CHANNEL_ID = 1485618781807050914     # Канал для логов

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
            source_server_1 = bot.get_guild(SOURCE_SERVER_1_ID)
            source_server_2 = bot.get_guild(SOURCE_SERVER_2_ID)
            source_server_3 = bot.get_guild(SOURCE_SERVER_3_ID)
            
            has_first_server_roles = False
            has_second_server_roles = False
            has_third_server_roles = False
            found_roles_first = []
            found_roles_second = []
            found_roles_third = []
            
            # Проверяем первый сервер
            if source_server_1:
                source_member = source_server_1.get_member(user_id)
                if source_member:
                    for role_id in SOURCE_1_ROLE_IDS:
                        role = source_server_1.get_role(role_id)
                        if role and role in source_member.roles:
                            has_first_server_roles = True
                            found_roles_first.append(f"{role.name}")
            
            # Проверяем второй сервер
            if source_server_2:
                source_member_2 = source_server_2.get_member(user_id)
                if source_member_2:
                    for role_id in SOURCE_2_ROLE_IDS:
                        role = source_server_2.get_role(role_id)
                        if role and role in source_member_2.roles:
                            has_second_server_roles = True
                            found_roles_second.append(f"{role.name}")
            
            # Проверяем третий сервер
            if source_server_3:
                source_member_3 = source_server_3.get_member(user_id)
                if source_member_3:
                    for role_id in SOURCE_3_ROLE_IDS:
                        role = source_server_3.get_role(role_id)
                        if role and role in source_member_3.roles:
                            has_third_server_roles = True
                            found_roles_third.append(f"{role.name}")
            
            has_any_roles = has_first_server_roles or has_second_server_roles or has_third_server_roles
            
            return {
                'has_first_server': has_first_server_roles,
                'has_second_server': has_second_server_roles,
                'has_third_server': has_third_server_roles,
                'found_roles_first': found_roles_first,
                'found_roles_second': found_roles_second,
                'found_roles_third': found_roles_third,
                'has_any_roles': has_any_roles
            }
        except Exception:
            return {
                'has_first_server': False,
                'has_second_server': False,
                'has_third_server': False,
                'found_roles_first': [],
                'found_roles_second': [],
                'found_roles_third': [],
                'has_any_roles': False
            }

    async def check_and_sync_user(self, user_id, username=None, check_ban=True):
        try:
            target_server = bot.get_guild(TARGET_SERVER_ID)
            if not target_server:
                return False
            
            target_role_1 = target_server.get_role(TARGET_ROLE_1_ID)
            target_role_2 = target_server.get_role(TARGET_ROLE_2_ID)
            target_role_3 = target_server.get_role(TARGET_ROLE_3_ID)
            
            if not target_role_1 or not target_role_2 or not target_role_3:
                return False
            
            target_member = target_server.get_member(user_id)
            if not target_member:
                return False
            
            role_check = await self.check_user_roles(user_id)
            username = username or target_member.display_name
            
            has_target_role_1 = target_role_1 in target_member.roles
            has_target_role_2 = target_role_2 in target_member.roles
            has_target_role_3 = target_role_3 in target_member.roles
            
            actions_performed = []
            
            # Первая роль (для первого сервера)
            if role_check['has_first_server'] and not has_target_role_1:
                await target_member.add_roles(target_role_1, reason="Автосинхронизация - первый сервер")
                actions_performed.append("✅ Выдана первая роль")
            elif not role_check['has_first_server'] and has_target_role_1:
                await target_member.remove_roles(target_role_1, reason="Автосинхронизация - нет ролей на первом сервере")
                actions_performed.append("🗑️ Удалена первая роль")
            
            # Вторая роль (для второго сервера)
            if role_check['has_second_server'] and not has_target_role_2:
                await target_member.add_roles(target_role_2, reason="Автосинхронизация - второй сервер")
                actions_performed.append("✅ Выдана вторая роль")
            elif not role_check['has_second_server'] and has_target_role_2:
                await target_member.remove_roles(target_role_2, reason="Автосинхронизация - нет ролей на втором сервере")
                actions_performed.append("🗑️ Удалена вторая роль")
            
            # Третья роль (для третьего сервера)
            if role_check['has_third_server'] and not has_target_role_3:
                await target_member.add_roles(target_role_3, reason="Автосинхронизация - третий сервер")
                actions_performed.append("✅ Выдана третья роль")
            elif not role_check['has_third_server'] and has_target_role_3:
                await target_member.remove_roles(target_role_3, reason="Автосинхронизация - нет ролей на третьем сервере")
                actions_performed.append("🗑️ Удалена третья роль")
            
            if actions_performed:
                log_msg = (
                    f"🔧 **Синхронизация ролей**\n"
                    f"• Пользователь: `{username}`\n"
                    f"• ID: `{user_id}`\n"
                    f"• Первый сервер: {'✅' if role_check['has_first_server'] else '❌'} {', '.join(role_check['found_roles_first']) if role_check['found_roles_first'] else 'Нет ролей'}\n"
                    f"• Второй сервер: {'✅' if role_check['has_second_server'] else '❌'} {', '.join(role_check['found_roles_second']) if role_check['found_roles_second'] else 'Нет ролей'}\n"
                    f"• Третий сервер: {'✅' if role_check['has_third_server'] else '❌'} {', '.join(role_check['found_roles_third']) if role_check['found_roles_third'] else 'Нет ролей'}\n"
                    f"• Действия: {', '.join(actions_performed)}"
                )
                await self.log_to_channel(log_msg, color=0x0099ff)
            
            if check_ban and not role_check['has_any_roles']:
                has_any_target_role = has_target_role_1 or has_target_role_2 or has_target_role_3
                
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
    print("Bot started")
    
    source_server_1 = bot.get_guild(SOURCE_SERVER_1_ID)
    source_server_2 = bot.get_guild(SOURCE_SERVER_2_ID)
    source_server_3 = bot.get_guild(SOURCE_SERVER_3_ID)
    target_server = bot.get_guild(TARGET_SERVER_ID)
    
    activity = discord.Activity(type=discord.ActivityType.watching, name="3 сервера | 5 сек")
    await bot.change_presence(activity=activity)
    
    await load_banned_users()
    
    startup_msg = f"🟢 **Role Sync Bot запущен**\n• Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n• Серверов: 3\n• Интервал: 5 секунд"
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
        target_role_1 = target_server.get_role(TARGET_ROLE_1_ID)
        target_role_2 = target_server.get_role(TARGET_ROLE_2_ID)
        target_role_3 = target_server.get_role(TARGET_ROLE_3_ID)
        
        has_target_role_1 = target_role_1 in user.roles if target_role_1 else False
        has_target_role_2 = target_role_2 in user.roles if target_role_2 else False
        has_target_role_3 = target_role_3 in user.roles if target_role_3 else False
        
        report = (
            f"📋 **Отчет по пользователю {user.mention}**\n"
            f"• ID: `{user.id}`\n"
            f"• Имя: `{user.display_name}`\n\n"
            f"**Исходные сервера:**\n"
            f"• Сервер 1 ({SOURCE_SERVER_1_ID}): {'✅ Есть роли' if role_check['has_first_server'] else '❌ Нет ролей'}\n"
            f"  Найденные роли: {', '.join(role_check['found_roles_first']) if role_check['found_roles_first'] else 'Нет'}\n"
            f"• Сервер 2 ({SOURCE_SERVER_2_ID}): {'✅ Есть роли' if role_check['has_second_server'] else '❌ Нет ролей'}\n"
            f"  Найденные роли: {', '.join(role_check['found_roles_second']) if role_check['found_roles_second'] else 'Нет'}\n"
            f"• Сервер 3 ({SOURCE_SERVER_3_ID}): {'✅ Есть роли' if role_check['has_third_server'] else '❌ Нет ролей'}\n"
            f"  Найденные роли: {', '.join(role_check['found_roles_third']) if role_check['found_roles_third'] else 'Нет'}\n\n"
            f"**Целевой сервер:**\n"
            f"• Роль 1 ({TARGET_ROLE_1_ID}): {'✅ Есть' if has_target_role_1 else '❌ Нет'}\n"
            f"• Роль 2 ({TARGET_ROLE_2_ID}): {'✅ Есть' if has_target_role_2 else '❌ Нет'}\n"
            f"• Роль 3 ({TARGET_ROLE_3_ID}): {'✅ Есть' if has_target_role_3 else '❌ Нет'}\n\n"
            f"**Статус:**\n"
            f"• Есть роли на любом сервере: {'✅ Да' if role_check['has_any_roles'] else '❌ Нет'}\n"
            f"• Статус бана: {'🔨 Забанен' if user.id in role_bot.banned_users else '✅ Не забанен'}"
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
    
    target_role_1 = target_server.get_role(TARGET_ROLE_1_ID)
    target_role_2 = target_server.get_role(TARGET_ROLE_2_ID)
    target_role_3 = target_server.get_role(TARGET_ROLE_3_ID)
    
    with_role_1 = len([m for m in target_server.members if target_role_1 in m.roles]) if target_role_1 else 0
    with_role_2 = len([m for m in target_server.members if target_role_2 in m.roles]) if target_role_2 else 0
    with_role_3 = len([m for m in target_server.members if target_role_3 in m.roles]) if target_role_3 else 0
    
    stats_msg = (
        f"📊 **Статистика Role Sync Bot**\n"
        f"• Время работы: {datetime.now() - role_bot.start_time}\n"
        f"• Всего пользователей: {total_members}\n"
        f"• С ролью 1: {with_role_1}\n"
        f"• С ролью 2: {with_role_2}\n"
        f"• С ролью 3: {with_role_3}\n"
        f"• Забанено: {banned_count} пользователей\n"
        f"• Интервал проверки: 5 секунд"
    )
    await ctx.send(stats_msg)

@bot.command(name='check_bans')
@commands.has_permissions(administrator=True)
async def check_bans(ctx):
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
                    ban_list.append(f"• {user.display_name} - ожидает разбана")
            except Exception:
                ban_list.append(f"• ID {user_id} - пользователь не найден")
        
        if ban_list:
            await ctx.send(f"🔨 **Забаненные пользователи ({len(ban_list)}):**\n" + "\n".join(ban_list[:15]))
        else:
            await ctx.send("✅ Нет забаненных пользователей")
    except Exception as e:
        await ctx.send(f"❌ Ошибка: {e}")

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