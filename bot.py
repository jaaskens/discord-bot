import discord
from discord.ext import commands, tasks
import json
import os
from datetime import datetime, time

# --- KONFIGURACJA ---
SUMMARY_CHANNEL_ID = 1488957365733818428  # ID kanału, na który ma lecieć podsumowanie o 23:00
FOOTER_TEXT = "Niedzielne Typy"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "typy.json"

# Kolory i emotki statusów
STATUS_CONFIG = {
    "PENDING": {"color": 0xf1c40f, "label": "🟡 OCZEKUJĄCY"},
    "LIVE": {"color": 0xe74c3c, "label": "🔴 MECZ TRWA (LIVE)"},
    "WIN": {"color": 0x2ecc71, "label": "🟢 WYGRANA"},
    "LOSE": {"color": 0x34495e, "label": "⚫ PRZEGRANA"}
}

# --- ZARZĄDZANIE DANYMI ---
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return {}
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

typy = load_data()

# --- PRZYCISKI INTERAKTYWNE ---
class BetButtons(discord.ui.View):
    def __init__(self, bet_id):
        super().__init__(timeout=None) # Przycisk działa zawsze
        self.bet_id = bet_id

    @discord.ui.button(label="LIVE", style=discord.ButtonStyle.secondary)
    async def live_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Brak uprawnień!", ephemeral=True)
        await self.update_status(interaction, "LIVE")

    @discord.ui.button(label="WIN ✅", style=discord.ButtonStyle.success)
    async def win_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Brak uprawnień!", ephemeral=True)
        await self.update_status(interaction, "WIN", final=True)

    @discord.ui.button(label="LOSE ❌", style=discord.ButtonStyle.danger)
    async def lose_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Brak uprawnień!", ephemeral=True)
        await self.update_status(interaction, "LOSE", final=True)

    async def update_status(self, interaction, new_status, final=False):
        bet = typy[self.bet_id]
        bet["status"] = new_status
        save_data(typy)
        
        conf = STATUS_CONFIG[new_status]
        embed = interaction.message.embeds[0]
        embed.title = f"{conf['label']} | {bet['rodzaj']}"
        embed.color = conf['color']
        
        if new_status == "WIN":
            profit = (bet["kurs"] * bet["stawka"]) - bet["stawka"]
            embed.add_field(name="💰 Zysk", value=f"**+{profit:.2f} PLN**", inline=False)
        
        # Jeśli WIN/LOSE, usuwamy przyciski
        new_view = None if final else self
        await interaction.response.edit_message(embed=embed, view=new_view)

# --- KOMENDY DODAWANIA ---
async def process_bet(ctx, label, kurs, stawka, opis):
    await ctx.message.delete()
    try:
        kurs_f = float(kurs.replace(",", "."))
        stawka_f = float(stawka.replace(",", "."))
    except:
        return await ctx.send("❌ Błędny kurs/stawka!", delete_after=3)

    # Formatowanie opisu (rozbijanie po | i ;)
    parts = [p.strip() for p in opis.split("|")]
    formatted_desc = ""
    for p in parts:
        sub_parts = [s.strip() for s in p.split(";")]
        if len(sub_parts) >= 2:
            mecz, m_kurs = sub_parts[0], sub_parts[1]
            analiza = sub_parts[2] if len(sub_parts) > 2 else "Brak analizy."
            formatted_desc += f"🔹 **{mecz}** [**{m_kurs}**]\n> 💡 *{analiza}*\n\n"
        else:
            formatted_desc += f"🔹 **{p}**\n\n"

    bet_id = str(max([int(k) for k in typy.keys()]) + 1) if typy else "1"
    typy[bet_id] = {
        "rodzaj": label, "kurs": kurs_f, "stawka": stawka_f,
        "opis": formatted_desc, "status": "PENDING", "data": datetime.now().strftime("%Y-%m-%d")
    }
    save_data(typy)

    embed = discord.Embed(
        title=f"🟡 OCZEKUJĄCY | {label}",
        description=formatted_desc,
        color=STATUS_CONFIG["PENDING"]["color"],
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="📈 Kurs", value=f"**{kurs_f:.2f}**", inline=True)
    embed.add_field(name="💰 Stawka", value=f"**{stawka_f:.2f} PLN**", inline=True)
    embed.set_footer(text=f"{FOOTER_TEXT} | ID: {bet_id}")

    await ctx.send(embed=embed, view=BetButtons(bet_id))

@bot.command()
@commands.has_permissions(administrator=True)
async def solo(ctx, kurs, stawka, *, opis):
    await process_bet(ctx, "SOLO DNIA", kurs, stawka, opis)

@bot.command()
@commands.has_permissions(administrator=True)
async def ako(ctx, kurs, stawka, *, opis):
    await process_bet(ctx, "AKO DNIA", kurs, stawka, opis)

# --- LISTA I PODSUMOWANIE ---
@bot.command()
async def lista(ctx):
    await ctx.message.delete()
    if not typy:
        return await ctx.send("Brak typów w bazie.", delete_after=5)
    
    text = ""
    # Pokazuje 10 ostatnich typów
    for bid, data in list(typy.items())[-10:]:
        status_icon = "🟢" if data["status"] == "WIN" else "🔴" if data["status"] == "LOSE" else "🟡"
        text += f"`ID: {bid}` | {status_icon} **{data['rodzaj']}** (Kurs: {data['kurs']})\n"
    
    embed = discord.Embed(title="📋 OSTATNIE TYPY", description=text, color=0x3498db)
    await ctx.send(embed=embed, delete_after=30)

def calculate_stats():
    today = datetime.now().strftime("%Y-%m-%d")
    win, lose, profit, total_stk = 0, 0, 0, 0
    
    for t in typy.values():
        if t["data"] == today and t["status"] in ["WIN", "LOSE"]:
            total_stk += t["stawka"]
            if t["status"] == "WIN":
                win += 1
                profit += (t["kurs"] * t["stawka"]) - t["stawka"]
            else:
                lose += 1
                profit -= t["stawka"]
    
    roi = (profit / total_stk * 100) if total_stk > 0 else 0
    return win, lose, profit, roi

@bot.command()
async def podsumowanie(ctx):
    await ctx.message.delete()
    w, l, p, r = calculate_stats()
    
    embed = discord.Embed(title=f"📊 PODSUMOWANIE DNIA", color=0x2ecc71 if p >= 0 else 0xe74c3c)
    embed.add_field(name="✅ Trafione", value=str(w), inline=True)
    embed.add_field(name="❌ Pudła", value=str(l), inline=True)
    embed.add_field(name="💰 Bilans", value=f"**{p:.2f} PLN**", inline=False)
    embed.add_field(name="📈 ROI", value=f"**{r:.2f}%**", inline=False)
    embed.set_footer(text=f"{FOOTER_TEXT} | {datetime.now().strftime('%d.%m.%Y')}")
    await ctx.send(embed=embed)

# --- AUTO ZADANIE O 23:00 ---
@tasks.loop(time=time(hour=23, minute=0))
async def auto_summary():
    channel = bot.get_channel(SUMMARY_CHANNEL_ID)
    if channel:
        w, l, p, r = calculate_stats()
        embed = discord.Embed(title=f"🌙 AUTOMATYCZNE PODSUMOWANIE DNIA", color=0x2c3e50)
        embed.add_field(name="Wynik", value=f"✅ {w} | ❌ {l}", inline=True)
        embed.add_field(name="Bilans", value=f"**{p:.2f} PLN**", inline=True)
        embed.add_field(name="ROI", value=f"**{r:.2f}%**", inline=True)
        await channel.send(embed=embed)

@bot.event
async def on_ready():
    auto_summary.start()
    print(f"✅ Bot wystartował jako {bot.user}")

bot.run(TOKEN)
