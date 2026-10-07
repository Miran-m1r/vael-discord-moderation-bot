import asyncio
import random
from urllib.parse import quote
from dataclasses import dataclass

import discord
import aiohttp
from discord.ext import commands

from utils.channels import require_channel
from utils.discord_compat import add_cog


@dataclass(frozen=True)
class CaseDefinition:
    name: str
    price: int
    items: tuple[str, ...]


CASES = {
    "prisma": CaseDefinition("Prisma Case", 100,
                             ("FAMAS | Crypsis", "AUG | Momentum", "M4A4 | The Emperor", "AWP | Atheris")),
    "revolution": CaseDefinition("Revolution Case", 500,
                                 ("P2000 | Wicked Sick", "M4A1-S | Emphorosaur-S", "AK-47 | Head Shot",
                                  "AWP | Duality")),
    "chroma3": CaseDefinition("Chroma 3 Case", 1000,
                              ("P250 | Asiimov", "SSG 08 | Ghost Crusader", "M4A1-S | Chantico's Fire",
                               "M4A4 | Hellfire")),
}

RARITIES = (
    ("Mil-Spec (Mavi)", 79.92, 1.0),
    ("Restricted (Mor)", 15.98, 1.8),
    ("Classified (Pembe)", 3.19, 3.5),
    ("Covert (Kırmızı)", 0.64, 8.0),
    ("Rare Special Item (Sarı)", 0.26, 20.0),
)
WEAR_NAMES = (
    (0.07, "Factory New"),
    (0.15, "Minimal Wear"),
    (0.38, "Field-Tested"),
    (0.45, "Well-Worn"),
    (1.01, "Battle-Scarred"),
)
OPENING_GIF_URL = "https://media.giphy.com/media/3o7TKtnuHOHHUjR38Y/giphy.gif"


def steam_market_url(item_name: str) -> str:
    """Steam Market listing URL used as the item's canonical visual source."""
    return f"https://steamcommunity.com/market/listings/730/{quote(item_name, safe='')}"


async def resolve_steam_image_url(listing_url: str) -> str | None:
    try:
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                    listing_url,
                    headers={"User-Agent": "MekanBot/1.0"},
            ) as response:
                if response.status != 200:
                    return None
                html = await response.text()
        marker = '<meta property="og:image" content="'
        start = html.find(marker)
        if start == -1:
            return None
        start += len(marker)
        end = html.find('"', start)
        return html[start:end] if end > start else None
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return None


def create_drop(case: CaseDefinition) -> tuple[str, str, str, float, int, str]:
    rarity, _, multiplier = random.choices(RARITIES, weights=[item[1] for item in RARITIES], k=1)[0]
    float_value = round(random.uniform(0.0, 1.0), 4)
    wear = next(name for upper_bound, name in WEAR_NAMES if float_value < upper_bound)
    base_name = random.choice(case.items)
    item_name = f"{base_name} ({wear})"
    price = max(1, int(case.price * multiplier * (1.15 - min(float_value, 1.0) * 0.6)))
    return item_name, wear, rarity, float_value, price, steam_market_url(base_name)


class TradeView(discord.ui.View):
    def __init__(self, cog: "Cases", sender: discord.Member, receiver: discord.Member, item_id: int):
        super().__init__(timeout=120)
        self.cog, self.sender, self.receiver, self.item_id = cog, sender, receiver, item_id
        self.done = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.receiver:
            await interaction.response.send_message("Bu takas teklifi yalnızca alıcı tarafından yanıtlanabilir.",
                                                    ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Kabul Et", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.done:
            return
        self.done = True
        item = await self.cog.bot.db.transfer_inventory_item(self.sender.id, self.receiver.id, self.item_id)
        if item is None:
            await interaction.response.edit_message(content="Eşya bulunamadı veya daha önce transfer edilmiştir.",
                                                    view=None)
            return
        await interaction.response.edit_message(content="Takas başarıyla tamamlandı.", view=None)

    @discord.ui.button(label="Reddet", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.done = True
        await interaction.response.edit_message(content="Takas teklifi reddedildi.", view=None)
        self.stop()


class InventoryView(discord.ui.View):
    def __init__(self, cog: "Cases", user_id: int, page: int, total: int):
        super().__init__(timeout=180)
        self.cog, self.user_id, self.page, self.total = cog, user_id, page, total
        self.page_size = 10
        self.previous.disabled = page == 0
        self.next.disabled = (page + 1) * self.page_size >= total

    async def render(self, interaction: discord.Interaction):
        items = await self.cog.bot.db.list_inventory(self.user_id, self.page_size, self.page * self.page_size)

        embed = discord.Embed(title="🎒 Envanterin", color=discord.Color.blurple())
        if not items:
            embed.description = "Envanterinizde eşya bulunmamaktadır."
        else:
            for item in items:
                img_link = f"[🖼️ Resmi Gör]({item['image_url']})" if item[
                    'image_url'] else f"[🔗 Steam Market]({steam_market_url(item['item_name'].split(' (')[0])})"
                embed.add_field(
                    name=f"🆔 ID: {item['id']} | 🔫 {item['item_name']}",
                    value=f"✨ **{item['rarity']}** | 🎯 Float: {item['float_value']:.4f} | 💰 {item['price']} Kredi\n{img_link}",
                    inline=False
                )

        embed.set_footer(text=f"Sayfa {self.page + 1}/{max(1, (self.total + self.page_size - 1) // self.page_size)}")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⬅️ Önceki", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        self.previous.disabled = self.page == 0
        self.next.disabled = False
        await self.render(interaction)

    @discord.ui.button(label="Sonraki ➡️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        self.previous.disabled = False
        self.next.disabled = (self.page + 1) * self.page_size >= self.total
        await self.render(interaction)


class Cases(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(name="cases", description="Satın alınabilir kasaları listeler.")
    async def cases(self, ctx: discord.ApplicationContext):
        if not await require_channel(ctx, "game_channel"):
            return

        embed = discord.Embed(title="📦 Kasa Mağazası",
                              description="İstediğin kasayı `/buycase <kasa_adi>` yazarak satın alabilirsin.",
                              color=discord.Color.gold())
        embed.set_thumbnail(url="https://media.giphy.com/media/3o7TKtnuHOHHUjR38Y/giphy.gif")

        for key, case in CASES.items():
            embed.add_field(
                name=f"🛒 {case.name} (`{key}`)",
                value=f"💸 **Fiyat:** {case.price} Kredi",
                inline=False
            )
        await ctx.respond(embed=embed)

    @discord.slash_command(name="buycase", description="Kasa satın alır ve açar.")
    async def buycase(self, ctx: discord.ApplicationContext,
                      kasa_adi: discord.Option(str, description="Satın alınacak kasanın adı")):
        try:
            # 3 saniye sınırını ezip geçmek için defer
            await ctx.defer()

            if not await require_channel(ctx, "game_channel"):
                return

            key = kasa_adi.casefold().replace(" ", "")
            case = CASES.get(key)
            if case is None:
                await ctx.respond(
                    "Belirtilen kasa bulunamadı. Kullanılabilir kasaları `/cases` komutuyla görüntüleyebilirsiniz.")
                return

            if not await self.bot.db.try_withdraw(ctx.author.id, case.price):
                await ctx.respond("Bakiyeniz bu kasayı satın almak için yeterli değildir.")
                return

            opening = discord.Embed(
                title="🎁 Kasa Açılıyor...",
                description=f"**{case.name}** açılıyor. Lütfen bekleyiniz...",
                color=discord.Color.orange(),
            )
            opening.set_image(url=OPENING_GIF_URL)

            await ctx.respond(embed=opening)

            await asyncio.sleep(3)

            item_name, wear, rarity, float_value, price, market_url = create_drop(case)
            image_url = await resolve_steam_image_url(market_url)
            item_id = await self.bot.db.add_inventory_item(
                ctx.author.id, item_name, rarity, float_value, price, image_url
            )

            result = discord.Embed(
                title="🎉 Kasa Açıldı",
                description=(
                    f"**Eşya:** {item_name}\n"
                    f"**Aşınma:** {wear}\n"
                    f"**Nadirlik:** {rarity}\n"
                    f"**Float:** {float_value:.4f}\n"
                    f"**Fiyat:** {price} kredi\n"
                    f"**Eşya ID:** {item_id}"
                ),
                color=discord.Color.green(),
                url=market_url,
            )
            if image_url:
                result.set_image(url=image_url)
            else:
                result.add_field(
                    name="Steam Market",
                    value=f"[Eşya listelemesini görüntüle]({market_url})",
                    inline=False,
                )

            await ctx.interaction.edit_original_response(embed=result)

        except Exception as e:
            await ctx.channel.send(f"🚨 **KOD PATLADI AMK:** `{str(e)}`")
            print(f"Kasa açma hatası: {e}")

    @discord.slash_command(name="inventory", description="Envanterinizi sayfalı olarak görüntüler.")
    async def inventory(self, ctx: discord.ApplicationContext):
        if not await require_channel(ctx, "game_channel"):
            return
        total = await self.bot.db.count_inventory(ctx.author.id)
        view = InventoryView(self, ctx.author.id, 0, total)
        items = await self.bot.db.list_inventory(ctx.author.id, 10, 0)

        embed = discord.Embed(title="🎒 Envanterin", color=discord.Color.blurple())
        if not items:
            embed.description = "Envanterinizde eşya bulunmamaktadır."
        else:
            for item in items:
                img_link = f"[🖼️ Resmi Gör]({item['image_url']})" if item[
                    'image_url'] else f"[🔗 Steam Market]({steam_market_url(item['item_name'].split(' (')[0])})"
                embed.add_field(
                    name=f"🆔 ID: {item['id']} | 🔫 {item['item_name']}",
                    value=f"✨ **{item['rarity']}** | 🎯 Float: {item['float_value']:.4f} | 💰 {item['price']} Kredi\n{img_link}",
                    inline=False
                )

        embed.set_footer(text=f"Sayfa 1/{max(1, (total + 9) // 10)}")
        await ctx.respond(embed=embed, view=view)

    @discord.slash_command(name="sell", description="Envanterinizdeki eşyayı satar.")
    async def sell(self, ctx: discord.ApplicationContext, item_id: int):
        if not await require_channel(ctx, "game_channel"):
            return
        price = await self.bot.db.sell_inventory_item(ctx.author.id, item_id)
        if price is None:
            await ctx.respond("Belirtilen eşya size ait değil veya mevcut değil.")
            return
        await ctx.respond(f"Eşya başarıyla satıldı. Hesabınıza **{price} kredi** eklendi.")

    @discord.slash_command(name="trade", description="Başka bir kullanıcıya eşya takası teklif eder.")
    async def trade(self, ctx: discord.ApplicationContext, kullanici: discord.Member, item_id: int):
        if not await require_channel(ctx, "game_channel"):
            return
        if kullanici == ctx.author or kullanici.bot:
            await ctx.respond("Geçerli bir kullanıcı belirtiniz.")
            return
        if not await self.bot.db.owns_inventory_item(ctx.author.id, item_id):
            await ctx.respond("Belirtilen eşya size ait değil veya mevcut değil.")
            return
        embed = discord.Embed(
            title="Takas Teklifi",
            description=f"{ctx.author.mention}, **#{item_id}** numaralı eşyayı {kullanici.mention} kullanıcısına göndermek istiyor.",
        )
        await ctx.respond(content=kullanici.mention, embed=embed, view=TradeView(self, ctx.author, kullanici, item_id))


def setup(bot):
    return add_cog(bot, Cases(bot))