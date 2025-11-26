# bot.py
import discord
from discord.ext import commands, tasks
from discord.ui import Select, View, Button
from datetime import datetime, timezone, timedelta
import asyncio

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="$", intents=intents)

# ---------------- KONFIG ----------------
# Panel + ticket category (gdzie tworzymy tickety)
TICKET_PANEL_CHANNEL_ID = 1441137554073194704
TICKET_CATEGORY_ID = 1441137554073194705  # tutaj tworzymy wszystkie tickety (zgodnie z Twoim wcześniejszym ustawieniem)

# Statystyki - nowa kategoria, podałeś: 1441137552785674295
STAT_CATEGORY_ID = 1441137552785674295

OPINIA_CHANNEL_ID = 1441137553733320801
REKRUTACJA_RESULT_CHANNEL = 1442150562211696740

VERIFY_CHANNEL_ID = 1441137553288855615   # kanał gdzie ma wysłać panel
VERIFY_ROLES = [
    1441137551128920097,   # pierwsza rola
    1441137551116206276    # druga rola
]





# Emoji dla pozycji w select
CATEGORY_EMOJIS = {
    "Grafiki": "<:111:1442099835502333983>",
    "Budowle": "<:111:1442099835502333983>",
    "Pluginy": "<:111:1442099835502333983>",
    "Boty": "<:111:1442099835502333983>",
    "Montaż": "<:111:1442099835502333983>",
    "Animacje": "<:111:1442099835502333983>",
    "Strony": "<:111:1442099835502333983>",
    "Pomoc": "<:111:1442099835502333983>",
    "Zgłoś scam": "<:111:1442099835502333983>",
    "Rekrutacja": "<:111:1442099835502333983>",
}

# Role przypisane do kategorii (podane przez Ciebie)
CATEGORY_ROLES = {
    "Grafiki": [1441137551183446035, 1441137551183446033, 1441137551128920103],
    "Budowle": [1441137551183446035, 1441137551183446033, 1441137551137181797],
    "Pluginy": [1441137551183446035, 1441137551183446033, 1441137551137181806],
    "Boty": [1441137551183446035, 1441137551183446033, 1441137551137181805],
    "Montaż": [1441137551183446035, 1441137551183446033, 1441137551128920102],
    "Animacje": [1441137551183446035, 1441137551183446033, 1441137551128920101],
    "Strony": [1441137551183446035, 1441137551183446033, 1441137551137181802],
    "Pomoc": [1441137551183446030, 1441137551183446029],
    "Zgłoś scam": [1442093776746319892, 1441137551183446034],
    "Rekrutacja": [1441137551183446035, 1441137551183446033],
}

GLOBAL_ROLES = [1441137551183446035]
TEAM_ROLES = [1441137551183446030, 1441137551183446029]
REKRUTACJA_MOD_ROLES = [1441137551183446034, 1442093776746319892]  # mogą używać $tak/$nie

# Clean config
CLEAN_COOLDOWN = timedelta(seconds=30)
CLEAN_ROLES_COOLDOWN = [
    1441137551149633615,
    1441137551183446026,
    1441137551183446029,
    1441137551183446030,
    1441137551183446032,
]
CLEAN_ROLES_NO_COOLDOWN = [1442093776746319892, 1441137551183446034, 1441137551183446050]

# ---------------- pamięci bota ----------------
active_tickets = {}      # user_id -> channel_id
ticket_owners = {}       # channel_id -> user_id
ticket_claims = {}       # channel_id -> staff_id (kto przejął)
ticket_messages = {}     # channel_id -> (message, roles)
rekrutacja_data = {}     # channel_id -> {"formularz": {...}, "user_id":..., "created":...}
last_clean = {}          # user_id -> datetime
last_opinia = {}         # user_id -> datetime

# ---------------- helper: safe user fetch ----------------
async def fetch_user_safe(user_id: int):
    user = bot.get_user(user_id)
    if user:
        return user
    try:
        user = await bot.fetch_user(user_id)
        return user
    except Exception:
        return None

# ---------------- send ticket panel ----------------
async def send_ticket_panel():
    await bot.wait_until_ready()
    channel = bot.get_channel(TICKET_PANEL_CHANNEL_ID)
    if not channel:
        print("Nie znaleziono panelu ticketowego:", TICKET_PANEL_CHANNEL_ID)
        return

    embed = discord.Embed(
        title="```🎫・CHERRYCODE - System Ticketów```",
        description=(
            "> Potrzebujesz pomocy lub masz pytania? Skorzystaj z sekcji **Pomoc Ogólna**.\n\n"
            "> Jeśli chcesz złożyć zamówienie lub poznać przewidywane koszty, wybierz odpowiednią kategorię z menu poniżej.\n\n"
            "> Prosimy nie zakładać zgłoszeń w celach rozrywkowych i nie oznaczać członków zespołu w zgłoszeniach. Odpowiemy na wszystkie wiadomości tak szybko, jak to możliwe."
        ),
        color=discord.Color.red(),
    )
    embed.set_image(url="https://cdn.discordapp.com/attachments/1441137551799877771/1442103115372564500/static.png")
    embed.set_footer(text="Wybierz kategorię poniżej, aby utworzyć ticket.")

    options = [discord.SelectOption(label=cat, emoji=emoji) for cat, emoji in CATEGORY_EMOJIS.items()]
    select = Select(placeholder="Wybierz kategorię ticketu", options=options, min_values=1, max_values=1)

    async def select_callback(interaction: discord.Interaction):
        user = interaction.user
        # cleanup stale active ticket entry
        existing = active_tickets.get(user.id)
        if existing:
            ch = interaction.guild.get_channel(existing)
            if ch is None:
                active_tickets.pop(user.id, None)
            else:
                await interaction.response.send_message("Masz już aktywny ticket!", ephemeral=True)
                return

        category_name = select.values[0]
        try:
            ticket_channel = await create_ticket(interaction.guild, user, category_name)
            await interaction.response.send_message(f"Ticket utworzony {ticket_channel.mention} ✅", ephemeral=True)
            # dm confirmation
            try:
                dm = await user.create_dm()
                await dm.send(f"Twój ticket został utworzony: {ticket_channel.mention}")
            except:
                pass
        except Exception as e:
            print("Błąd tworzenia ticketa:", e)
            await interaction.response.send_message("Wystąpił błąd podczas tworzenia ticketa.", ephemeral=True)

    select.callback = select_callback
    view = View()
    view.add_item(select)
    await channel.send(embed=embed, view=view)
    print("Panel ticketowy wysłany.")

# ---------------- create ticket (force category by ID) ----------------
async def create_ticket(guild: discord.Guild, user: discord.Member, category_name: str):
    # pobierz kategorię po ID (wymuszone)
    category = discord.utils.get(guild.categories, id=TICKET_CATEGORY_ID)
    if not category:
        # fallback: spróbuj znaleźć kategorię o nazwie category_name
        category = discord.utils.get(guild.categories, name=category_name)
    # jeśli dalej None, utwórz bez kategorii (ale wcześniej użytkownik podał że ma kategorię)
    # permissions
    category_roles = CATEGORY_ROLES.get(category_name, [])
    overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    for role_id in category_roles + GLOBAL_ROLES:
        role = guild.get_role(role_id)
        if role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
    overwrites[user] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

    # unikalna nazwa aby uniknac kolizji
    safe_name = f"ticket-{user.name}".lower()
    channel_name = f"{safe_name}-{user.id}"

    ticket_channel = await guild.create_text_channel(
        name=channel_name,
        overwrites=overwrites,
        category=category
    )

    active_tickets[user.id] = ticket_channel.id
    ticket_owners[ticket_channel.id] = user.id

    creation_time = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")

    # Embed różny dla rekrutacji
    if category_name == "Rekrutacja":
        # ping roles above embed
        ping_roles = f"<@&{1441137551183446034}> <@&{1442093776746319892}>"
        try:
            await ticket_channel.send(ping_roles)
        except:
            pass

        desc = (
            "```🎫・CHERRYCODE - Rekrutacja``` \n"
            f"<:czlonek:1441159458016465147> ︲ **Użytkownik:** {user.mention}\n"
            f"<:id1:1441159366488228012> ︲ **ID:** `{user.id}`\n"
            f"<:dzwon:1441159667828134010> ︲ **Stworzony:** {creation_time}\n\n"
            "```FORMULARZ (odpowiedz poniżej, bez limitu czasu)```\n"
            "`1` Wiek\n"
            "`2` Dlaczego ty\n"
            "`3` Co wniesiesz w nasze szeregi\n"
            "`4` Opisz siebie w min 3 zdaniach\n"
            "`5` Twoje motto (opcjonalnie)\n"
            "`6` Na jaki stopień chcesz się zrekrutować? (np. montazysta)\n"
            "`7` Wyślij link do swojego portfolio`\n\n"
            "_Odpowiedz kolejno w tym kanale. Jeśli chcesz anulować - wpisz `anuluj`._"
        )
    else:
        desc = (
            "```🎫・CHERRYCODE - Ticket``` \n"
            f"<:czlonek:1441159458016465147> ︲ **Użytkownik:** {user.mention}\n"
            f"<:id1:1441159366488228012> ︲ **ID:** `{user.id}`\n"
            f"<:szukac:1441159580108460165> ︲ **Kategoria:** `{category_name}`\n"
            f"<:dzwon:1441159667828134010> ︲ **Stworzony:** {creation_time}\n\n"
            f"```🟢 ・ Dostępność - Rang``` \n"
            f"<:adm:1441159426084966611> ︲ **Zarząd online:** {get_online_count(guild, category_roles, True)}\n"
            f"<:star:1441159514874187951> ︲ **Team online:** {get_online_count(guild, TEAM_ROLES, False)}"
        )

    embed = discord.Embed(title="", description=desc, color=discord.Color.red())
    claim_button = Button(label="Przejmij ticket", style=discord.ButtonStyle.green)

    async def claim_callback(interaction: discord.Interaction):
        allowed = any(r.id in category_roles + GLOBAL_ROLES for r in interaction.user.roles)
        if not allowed:
            await interaction.response.send_message("Nie masz uprawnień do przejęcia tego ticketu.", ephemeral=True)
            return
        ticket_claims[ticket_channel.id] = interaction.user.id
        await interaction.response.send_message(f"Ticket został przejęty przez {interaction.user.mention} ✅", ephemeral=True)

    claim_button.callback = claim_callback
    view = View()
    view.add_item(claim_button)

    message = await ticket_channel.send(embed=embed, view=view)
    ticket_messages[ticket_channel.id] = (message, category_roles)

    if category_name == "Rekrutacja":
        bot.loop.create_task(run_rekrutacja_flow(ticket_channel, user))

    return ticket_channel

# ---------------- run rekrutacja flow (bez limitu) ----------------
async def run_rekrutacja_flow(channel: discord.TextChannel, user: discord.Member):
    questions = [
        ("1) Podaj swój wiek:", True),
        ("2) Dlaczego to właśnie Ty?", True),
        ("3) Co wniesiesz w nasze szeregi?", True),
        ("4) Opisz siebie - min. 3 zdania:", True),
        ("5) Twoje motto (opcjonalnie):", False),
        ("6) Na jaki stopień chcesz się zrekrutować? (np. montazysta)", True),
        ("7) Wyślij link do swojego portfolio:", True),
    ]
    answers = {}
    def check(m: discord.Message):
        return m.author.id == user.id and m.channel.id == channel.id

    try:
        for idx, (prompt, required) in enumerate(questions, start=1):
            await channel.send(f"**{prompt}**\n_Pisz tutaj (wpisz `anuluj` aby przerwać)._")
            msg = await bot.wait_for("message", check=check)
            if msg.content.lower() == "anuluj":
                await channel.send(f"{user.mention} Proces rekrutacji anulowany.")
                rekrutacja_data.pop(channel.id, None)
                return
            answers[str(idx)] = msg.content

        rekrutacja_data[channel.id] = {"formularz": answers, "user_id": user.id, "created": datetime.now(timezone.utc)}
        form_text = "\n".join([f"{k}. {v}" for k, v in answers.items()])
        embed = discord.Embed(
            title="Formularz rekrutacyjny - wypełniony",
            description=f"**Użytkownik:** {user.mention}\n**ID:** `{user.id}`\n\n```FORMULARZ```\n{form_text}",
            color=discord.Color.blue()
        )
        await channel.send(embed=embed)
        try:
            dm = await user.create_dm()
            dm_embed = discord.Embed(
                title="Potwierdzenie wypełnienia formularza rekrutacyjnego",
                description=f"Dziękujemy! Oto Twoje odpowiedzi:\n\n{form_text}",
                color=discord.Color.blue()
            )
            await dm.send(embed=dm_embed)
        except:
            pass

    except Exception as e:
        print("Błąd w run_rekrutacja_flow:", e)
        try:
            await channel.send("Wystąpił błąd podczas procesu rekrutacji. Skontaktuj się z administracją.")
        except:
            pass

# ---------------- komendy tak / nie ----------------
@bot.command()
async def tak(ctx: commands.Context):
    channel_id = ctx.channel.id
    if channel_id not in rekrutacja_data:
        await ctx.send("To nie jest ticket rekrutacji lub brak danych formularza.", delete_after=7)
        return
    if not any(role.id in REKRUTACJA_MOD_ROLES for role in ctx.author.roles):
        await ctx.send("Nie masz uprawnień do tej komendy.", delete_after=7)
        return

    data = rekrutacja_data[channel_id]
    user_id = data.get("user_id")
    if not user_id:
        await ctx.send("Brak danych użytkownika.", delete_after=7)
        return

    embed = discord.Embed(title="Wynik Pozytywny", color=discord.Color.green())
    embed.add_field(name="Użytkownik", value=f"<@{user_id}>", inline=False)
    embed.add_field(name="ID", value=str(user_id), inline=False)

    ch = bot.get_channel(REKRUTACJA_RESULT_CHANNEL)
    if ch:
        await ch.send(embed=embed)
    await ctx.send("Wynik pozytywny wysłany.", delete_after=6)

@bot.command()
async def nie(ctx: commands.Context):
    channel_id = ctx.channel.id
    if channel_id not in rekrutacja_data:
        await ctx.send("To nie jest ticket rekrutacji lub brak danych formularza.", delete_after=7)
        return
    if not any(role.id in REKRUTACJA_MOD_ROLES for role in ctx.author.roles):
        await ctx.send("Nie masz uprawnień do tej komendy.", delete_after=7)
        return

    data = rekrutacja_data[channel_id]
    user_id = data.get("user_id")
    if not user_id:
        await ctx.send("Brak danych użytkownika.", delete_after=7)
        return

    embed = discord.Embed(title="Wynik Negatywny", color=discord.Color.red())
    embed.add_field(name="Użytkownik", value=f"<@{user_id}>", inline=False)
    embed.add_field(name="ID", value=str(user_id), inline=False)

    ch = bot.get_channel(REKRUTACJA_RESULT_CHANNEL)
    if ch:
        await ch.send(embed=embed)
    await ctx.send("Wynik negatywny wysłany.", delete_after=6)

# ---------------- online count helper ----------------
def get_online_count(guild: discord.Guild, roles: list, zarzad: bool = False) -> int:
    count = 0
    for member in guild.members:
        try:
            if member.status != discord.Status.offline:
                if zarzad:
                    if any(r.id in GLOBAL_ROLES for r in member.roles):
                        count += 1
                else:
                    if any(r.id in roles for r in member.roles):
                        count += 1
        except:
            continue
    return count

# ---------------- update ticket embeds co 20s ----------------
@tasks.loop(seconds=20)
async def update_ticket_counts():
    for channel_id, (message, roles) in list(ticket_messages.items()):
        guild = message.guild
        if not guild:
            continue
        # jeśli kanał usunięty, cleanup
        ch = guild.get_channel(channel_id)
        if ch is None:
            ticket_messages.pop(channel_id, None)
            ticket_owners.pop(channel_id, None)
            ticket_claims.pop(channel_id, None)
            rekrutacja_data.pop(channel_id, None)
            continue
        try:
            embed = message.embeds[0]
            user_id = ticket_owners.get(channel_id)
            member = guild.get_member(user_id) if user_id else None
            created = message.created_at if getattr(message, "created_at", None) else datetime.now(timezone.utc)
            cat_name = message.channel.category.name if getattr(message.channel, "category", None) else "Ticket"
            if cat_name == "Rekrutacja":
                new_value = (
                    f"<:czlonek:1441159458016465147> ︲ **Użytkownik:** {member.mention if member else 'Nieznany'}\n"
                    f"<:id1:1441159366488228012> ︲ **ID:** `{user_id}`\n"
                    f"<:dzwon:1441159667828134010> ︲ **Stworzony:** {created.strftime('%d.%m.%Y %H:%M UTC')}\n"
                )
            else:
                new_value = (
                    f"<:czlonek:1441159458016465147> ︲ **Użytkownik:** {member.mention if member else 'Nieznany'}\n"
                    f"<:id1:1441159366488228012> ︲ **ID:** `{user_id}`\n"
                    f"<:szukac:1441159580108460165> ︲ **Kategoria:** `{cat_name}`\n"
                    f"<:dzwon:1441159667828134010> ︲ **Stworzony:** {created.strftime('%d.%m.%Y %H:%M UTC')}\n\n"
                    f"<:adm:1441159426084966611> ︲ **Zarząd online:** {get_online_count(guild, roles, True)}\n"
                    f"<:star:1441159514874187951> ︲ **Team online:** {get_online_count(guild, TEAM_ROLES, False)}"
                )
            embed.set_field_at(0, name="\u200b", value=new_value, inline=False)
            try:
                await message.edit(embed=embed)
            except:
                pass
        except Exception as e:
            print("Błąd update_ticket_counts:", e)

# ---------------- Zamknij z odliczaniem i archiwum ----------------
@bot.command()
async def Zamknij(ctx: commands.Context, *, reason: str = None):
    channel_id = ctx.channel.id
    if channel_id not in ticket_claims:
        await ctx.send("Nie możesz zamknąć tego ticketu, nie jest przejęty.", delete_after=7)
        return
    if ticket_claims.get(channel_id) != ctx.author.id:
        await ctx.send("Nie możesz zamknąć ticketu, nie jesteś właścicielem.", delete_after=7)
        return
    if not reason:
        reason = "Brak powodu"

    countdown_embed = discord.Embed(title="Zamykanie ticketa...", color=discord.Color.red())
    msg = await ctx.send(embed=countdown_embed)
    for i in range(5, 0, -1):
        countdown_embed.description = f"Ticket zostanie zamknięty za {i} sekund ⏳"
        try:
            await msg.edit(embed=countdown_embed)
        except:
            pass
        await asyncio.sleep(1)

    # archiwum
    archive_lines = []
    try:
        async for m in ctx.channel.history(limit=500):
            if m.author and (m.content or m.attachments):
                ts = m.created_at.astimezone(timezone.utc).strftime("%d.%m.%Y %H:%M")
                content = m.content if m.content else "[attachment]"
                archive_lines.append(f"[{ts}] {m.author}: {content}")
    except Exception as e:
        print("Arch error:", e)

    archive_text = "\n".join(reversed(archive_lines)) if archive_lines else "Brak wiadomości."

    owner_id = ticket_owners.get(channel_id)
    if owner_id:
        try:
            user = await fetch_user_safe(owner_id)
            if user:
                max_len = 1900
                fragments = [archive_text[i:i+max_len] for i in range(0, len(archive_text), max_len)] if archive_text else []
                pv_embed = discord.Embed(
                    title="Twój ticket został zamknięty ✅",
                    description=f"Cześć, Twoje zgłoszenie zostało zamknięte przez {ctx.author.mention}\nPowód:\n```\n{reason}\n```",
                    color=discord.Color.green()
                )
                if fragments:
                    pv_embed.add_field(name="Archiwum (fragment 1)", value=fragments[0], inline=False)
                else:
                    pv_embed.add_field(name="Archiwum", value="Brak wiadomości", inline=False)
                try:
                    await user.send(embed=pv_embed)
                except:
                    pass
                for idx, frag in enumerate(fragments[1:], start=2):
                    try:
                        await user.send(f"Archiwum (fragment {idx}):\n```\n{frag}\n```")
                    except:
                        pass
        except Exception as e:
            print("Błąd wysyłania PV:", e)

    try:
        await ctx.channel.delete()
    except Exception as e:
        print("Błąd usuwania kanału:", e)

    if owner_id:
        active_tickets.pop(owner_id, None)
    ticket_owners.pop(channel_id, None)
    ticket_claims.pop(channel_id, None)
    ticket_messages.pop(channel_id, None)
    rekrutacja_data.pop(channel_id, None)

# ---------------- Clean ----------------
@bot.command()
async def Clean(ctx: commands.Context, amount: int):
    author_roles = [r.id for r in ctx.author.roles]
    now = datetime.now(timezone.utc)

    allowed = any(r in CLEAN_ROLES_COOLDOWN + CLEAN_ROLES_NO_COOLDOWN for r in author_roles)
    if not allowed:
        await ctx.send("Nie masz uprawnień do użycia tej komendy.", delete_after=5)
        return

    cooldown_applicable = any(r in CLEAN_ROLES_COOLDOWN for r in author_roles) and not any(r in CLEAN_ROLES_NO_COOLDOWN for r in author_roles)
    if cooldown_applicable:
        last = last_clean.get(ctx.author.id)
        if last and (now - last) < CLEAN_COOLDOWN:
            remain = int((CLEAN_COOLDOWN - (now - last)).total_seconds())
            await ctx.send(f"Musisz odczekać {remain} sekund.", delete_after=5)
            return
        last_clean[ctx.author.id] = now

    if amount > 500:
        amount = 500

    try:
        deleted = await ctx.channel.purge(limit=amount)
        await ctx.send(f"Usunięto {len(deleted)} wiadomości ✅", delete_after=5)
    except Exception as e:
        await ctx.send("Nie udało się usunąć wiadomości.", delete_after=5)
        print("Clean error:", e)

# ---------------- Opinia ----------------
@bot.command()
async def opinia(ctx: commands.Context, member: discord.Member, *, args: str):
    if ctx.channel.id != OPINIA_CHANNEL_ID:
        await ctx.send("Komenda można używać tylko na dedykowanym kanale.", delete_after=5)
        return
    now = datetime.now(timezone.utc)
    last = last_opinia.get(ctx.author.id)
    if last and (now - last) < timedelta(hours=24):
        await ctx.send("Możesz wysłać opinię tylko raz na 24h.", delete_after=5)
        return

    parts = args.split()
    if len(parts) < 2:
        await ctx.send("Niepoprawne użycie. `$opinia @user Powód 5`", delete_after=5)
        return

    try:
        stars = int(parts[-1])
        if not (1 <= stars <= 5):
            await ctx.send("Liczba gwiazdek musi być 1-5.", delete_after=5)
            return
        reason = " ".join(parts[:-1])
    except:
        await ctx.send("Niepoprawne użycie. `$opinia @user Powód 5`", delete_after=5)
        return

    last_opinia[ctx.author.id] = now
    embed = discord.Embed(title="OPINIA - CHERRYCODE", color=discord.Color.dark_red())
    embed.add_field(name="Kto", value=ctx.author.mention, inline=False)
    embed.add_field(name="Komu", value=member.mention, inline=False)
    embed.add_field(name="Dlaczego", value=reason, inline=False)
    embed.add_field(name="Ile gwiazdek", value=f"{stars}/5", inline=False)
    await ctx.send(embed=embed)

# ---------------- Stats: create/get in category (voice channels) ----------------
MEMBERS_CHANNEL_NAME = "👥│Members: {}"
ONLINE_CHANNEL_NAME = "🟢│Online: {}"

def get_stat_category(guild):
    for cat in guild.categories:
        if cat.id == STAT_CATEGORY_ID:
            return cat
    return None

async def create_or_get_stat_channel(guild, name):
    category = get_stat_category(guild)
    if not category:
        return None
    prefix = name.split(":")[0]
    for ch in category.channels:
        if ch.name.startswith(prefix):
            return ch
    # tworzymy voice channel, bo to popularny sposób (można też utworzyć tekstowy)
    try:
        return await category.create_voice_channel(name)
    except Exception as e:
        print("Błąd tworzenia kanału statystyk:", e)
        return None

@tasks.loop(seconds=30)
async def update_stats():
    for guild in bot.guilds:
        category = get_stat_category(guild)
        if category is None:
            # nie mamy kategorii statystyk na tym serwerze
            continue
        total_members = guild.member_count
        online_count = sum(1 for m in guild.members if m.status != discord.Status.offline)
        members_channel = await create_or_get_stat_channel(guild, MEMBERS_CHANNEL_NAME.format(total_members))
        online_channel = await create_or_get_stat_channel(guild, ONLINE_CHANNEL_NAME.format(online_count))
        try:
            if members_channel:
                await members_channel.edit(name=MEMBERS_CHANNEL_NAME.format(total_members))
            if online_channel:
                await online_channel.edit(name=ONLINE_CHANNEL_NAME.format(online_count))
        except Exception as e:
            print("Błąd update_stats edit:", e)

# ---------------- on_ready start tasks ----------------
@bot.event
async def on_ready():
    print(f"Zalogowano jako {bot.user} (ID: {bot.user.id})")
    # wyślij panel jeśli możliwe
    try:
        await send_ticket_panel()
    except Exception as e:
        print("send_ticket_panel error:", e)
    # uruchom taski (bez duplikatów)
    try:
        update_ticket_counts.start()
    except RuntimeError:
        pass
    try:
        update_stats.start()
    except RuntimeError:
        pass

# ---------- run ----------------
if __name__ == "__main__":
    bot.run("MTQ0MTEzNjI1OTY1NjQ1NDMyMA.GjHFZl.WlMc7G3gCcRINEF_jE9egcnrLJPqokGN8iTz9M")
