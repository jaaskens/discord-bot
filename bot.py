import discord
from discord.ext import commands
import json
import os
from datetime import datetime

# --- KONFIGURACJA ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "typy.json"
FOOTER_TEXT = "Niedzielne Typy"

# Kolory statusów
COLOR_PENDING = 0xf1c40f  # Żółty
COLOR_LIVE = 0xe74c3c     # Czerwony (Live)
COLOR_WIN = 0x2ecc71      # Zielony
COLOR_LOSE = 0x34495e     # Grafitowy/Czarny

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return {}
    return {}

typy = load_data()

def save():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(typy, f, indent=4, ensure_ascii=False)

# --- WIDOK Z PRZYCISKAMI (INTERAKCJA) ---

class BetControl(discord.ui.View):
    def __init__(self, bet_id):
        super().__init__(timeout=None) # Przyciski nie wygasają
        self.bet_id = bet_id

    @discord.ui.button(label="LIVE 🔴", style=discord.ButtonStyle.secondary)
    async def set_live(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Brak uprawnień!", ephemeral=True)
        
        typy[self.bet_id]["status"] = "LIVE"
        save()
        await self.update_message(interaction)

    @discord.ui.button(label="WIN ✅", style=discord.ButtonStyle.success)
    async def set_win(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Brak uprawnień!", ephemeral=True)
        
        typy[self.bet_id]["status"] = "WIN"
        save()
        # Po wygranej usuwamy przyciski (view=None)
        await self.update_message(interaction, final=True)

    @discord.ui.button(label="LOSE ❌", style=discord.ButtonStyle.danger)
    async def set_lose(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Brak uprawnień!", ephemeral=True)
        
        typy[self.bet_id]["status"] = "LOSE"
        save()
        await self.update_message(interaction, final=True)

    async def update_message(self, interaction, final=False):
        bet = typy[self.bet_id]
        
        # Wybór koloru i statusu
        color = COLOR_PENDING
        status_text = "🟡 OCZEKUJĄCY"
        
        if bet["status"] == "LIVE":
            color = COLOR_LIVE
            status_text = "🔴 MECZ TRWA (LIVE)"
        elif bet["status"] == "WIN":
            color = COLOR_WIN
            status_text = "🟢 WYGRANA"
        elif bet["status"] == "LOSE":
            color = COLOR_LOSE
            status_text = "⚫ PRZEGRANA"

        embed = discord.Embed(
            title=f"{status_text} | {bet['rodzaj'].upper()}",
            description=f"**Opis:**\n{bet['opis']}",
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="📈 Kurs", value=f"**{bet['kurs']:.2f}**", inline=True)
        embed.add_field(name="💰 Stawka", value=f"**{bet['stawka']:.2f} PLN**", inline=True)
        
        if bet["status"] == "WIN":
            profit = (bet["kurs"] * bet["stawka"]) - bet["stawka"]
            embed.add_field(name="💵 Zysk", value=f"**+{profit:.2f} PLN**", inline=False)

        embed.set_footer(text=f"{FOOTER_TEXT} | ID: {self.bet_id}")
        
        if final:
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

# --- KOMENDY ---

async def create_bet(ctx, category, kurs, stawka, opis, color):
    await ctx.message.delete()
    
    try:
        kurs_f = float(kurs.replace(",", "."))
        stawka_f = float(stawka.replace(",", "."))
    except:
        return await ctx.send("Błędny kurs/stawka!", delete_after=3)

    bet_id = str(max([int(k) for k in typy.keys()]) + 1) if typy else "1"
    typy[bet_id] = {
        "rodzaj": category, "kurs": kurs_f, "stawka": stawka_f, 
        "opis": opis, "status": "PENDING"
    }
    save()

    embed = discord.Embed(
        title=f"🟡 OCZEKUJĄCY | {category.upper()}",
        description=f"**Opis:**\n{opis}",
        color=COLOR_PENDING,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="📈 Kurs", value=f"**{kurs_f:.2f}**", inline=True)
    embed.add_field(name="💰 Stawka", value=f"**{stawka_f:.2f} PLN**", inline=True)
    embed.set_footer(text=f"{FOOTER_TEXT} | ID: {bet_id}")

    # Wysyłamy wiadomość z widokiem przycisków
    await ctx.send(embed=embed, view=BetControl(bet_id))

@bot.command()
@commands.has_permissions(administrator=True)
async def solodnia(ctx, kurs, stawka, *, opis):
    await create_bet(ctx, "Solo Dnia", kurs, stawka, opis, COLOR_PENDING)

@bot.command()
@commands.has_permissions(administrator=True)
async def akodnia(ctx, kurs, stawka, *, opis):
    await create_bet(ctx, "AKO Dnia", kurs, stawka, opis, COLOR_PENDING)

@bot.command()
@commands.has_permissions(administrator=True)
async def value(ctx, kurs, stawka, *, opis):
    await create_bet(ctx, "Value Bet", kurs, stawka, opis, COLOR_PENDING)

@bot.event
async def on_ready():
    print(f"✅ Dashboard Pro Online: {bot.user}")
    
import os    
bot.run(os.getenv("TOKEN"))
