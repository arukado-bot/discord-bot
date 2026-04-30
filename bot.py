import discord
from discord.ext import commands
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

print("СТАРТ")

# ---------- GOOGLE ----------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

client = gspread.authorize(creds)
sheet = client.open("points").sheet1

print("ТАБЛИЦА ПОДКЛЮЧЕНА")

# ---------- DISCORD ----------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

message_points = {}
processed_messages = set()

# ---------- РОЛИ (без учета регистра) ----------
def has_role(member):
    allowed_roles = ["глава гильдии", "зам главы", "офицер", "консул"]
    user_roles = [role.name.lower() for role in member.roles]
    return any(role in user_roles for role in allowed_roles)

# ---------- ФУНКЦИИ ----------
def add_points(user, amount):
    data = sheet.get_all_values()

    for i, row in enumerate(data):
        if row and row[0] == str(user.id):
            try:
                current = int(row[2])
            except:
                current = 0

            sheet.update_cell(i + 1, 3, current + amount)
            return

    sheet.append_row([str(user.id), user.name, amount])


def remove_points(user_id, amount):
    data = sheet.get_all_values()

    for i, row in enumerate(data):
        if row and row[0] == str(user_id):
            try:
                current = int(row[2])
            except:
                current = 0

            sheet.update_cell(i + 1, 3, max(0, current - amount))
            return


def get_channel_settings(channel):
    if channel == "mass-up":
        return 15, 4
    elif channel == "pve":
        return 5, 2
    elif channel == "pvp":
        return 5, 3
    elif channel == "lfg":
        return 5, 2
    elif channel == "ава-данж":
        return 10, 2
    return None, None


# ---------- СОБЫТИЯ ----------
@bot.event
async def on_ready():
    print(f"БОТ ОНЛАЙН: {bot.user}")


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.id in processed_messages:
        return

    processed_messages.add(message.id)

    channel = message.channel.name.lower()
    mentions = message.mentions

    min_count, pts = get_channel_settings(channel)
    if not min_count:
        await bot.process_commands(message)
        return

    count = len(mentions)

    if count >= min_count:
        message_points.setdefault(message.id, {})

        for user in mentions:
            if user.id not in message_points[message.id]:
                add_points(user, pts)
                message_points[message.id][user.id] = pts

    await bot.process_commands(message)


@bot.event
async def on_message_edit(before, after):
    if after.author.bot:
        return

    if before.content == after.content:
        return

    channel = after.channel.name.lower()
    min_count, pts = get_channel_settings(channel)

    if not min_count:
        return

    before_ids = set(u.id for u in before.mentions)
    after_ids = set(u.id for u in after.mentions)

    before_count = len(before_ids)
    after_count = len(after_ids)

    message_points.setdefault(after.id, {})

    if before_count >= min_count and after_count < min_count:
        for user_id, amount in message_points[after.id].items():
            remove_points(user_id, amount)
        message_points[after.id].clear()
        return

    if before_count < min_count and after_count >= min_count:
        for user in after.mentions:
            add_points(user, pts)
            message_points[after.id][user.id] = pts
        return

    if after_count >= min_count:
        removed = before_ids - after_ids
        added = after_ids - before_ids

        for uid in removed:
            if uid in message_points[after.id]:
                remove_points(uid, pts)
                del message_points[after.id][uid]

        for user in after.mentions:
            if user.id in added:
                add_points(user, pts)
                message_points[after.id][user.id] = pts


# ---------- КОМАНДЫ ----------
@bot.command()
async def ping(ctx):
    if not has_role(ctx.author):
        return
    await ctx.send("pong")


@bot.command()
async def points(ctx):
    if not has_role(ctx.author):
        return

    data = sheet.get_all_values()

    text = ""
    for row in data[1:]:
        if len(row) >= 3:
            text += f"{row[1]}: {row[2]}\n"

    if not text:
        text = "Нет данных"

    await ctx.send(f"```{text}```")


@bot.command()
async def add(ctx, member: discord.Member, amount: int):
    if not has_role(ctx.author):
        return

    add_points(member, amount)
    await ctx.send(f"+{amount} {member.name}")


@bot.command()
async def reset(ctx):
    if not has_role(ctx.author):
        return

    sheet.clear()
    sheet.append_row(["user_id", "username", "points"])
    await ctx.send("Сброшено")


# ---------- ЗАПУСК ----------
bot.run(os.getenv("TOKEN"))
