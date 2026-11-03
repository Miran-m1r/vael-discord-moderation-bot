import asyncio
from dataclasses import dataclass
import io
import json
import os
import random
from urllib.parse import quote

import aiohttp
import discord
from discord.ext import commands
from PIL import Image, ImageDraw

from utils.channels import require_channel
from utils.discord_compat import add_cog


@dataclass(frozen=True)
class CaseDefinition:
    name: str
    price: int
    items: tuple[str, ...]
    image_url: str


CASES: dict[str, CaseDefinition] = {
    "revolution": CaseDefinition(
        name="Revolution Case",
        price=500,
        items=(
            "AK-47 | Head Shot", "M4A1-S | Emphorosaur-S", "AWP | Duality", "P2000 | Wicked Sick",
            "UMP-45 | Wild Child", "Glock-18 | Umbral Rabbit", "MAC-10 | Sakkaku"
        ),
        image_url="https://community.akamai.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttyVfPaERSR0Wqmu7LAocGJKz2lu_XsnXwtmkJjSU91dh8bj35VTqVBP4io_frnAVvfb6aqduc_TFVjTCxbx05OU4S3jilE9w4DzRnImtIy2Sa1JzDJEhRPlK7EcO4U8gfA",
    ),
    "clutch": CaseDefinition(
        name="Clutch Case",
        price=300,
        items=(
            "M4A4 | Neo-Noir", "USP-S | Cortex", "AWP | Mortis", "MP7 | Bloodsport",
            "Nova | Wild Six", "Glock-18 | Moonrise", "MAG-7 | SWAG-7"
        ),
        image_url="https://community.akamai.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttyVfPaERSR0Wqmu7LAocGJKz2lu_XsnXwtmkJjSU91dh8bj35VTqVBP4io_frHsVtqr8a_dsdKTAWDWVxLgjsrAwHSvgwEQk4m-ByYuqIC2eO1VyD5QiR_lK7EcxQQPYQA",
    ),
    "gamma": CaseDefinition(
        name="Gamma Case",
        price=400,
        items=(
            "M4A1-S | Mecha Industries", "Glock-18 | Wasteland Rebel", "M4A4 | Desolate Space", "AWP | Phobos",
            "SCAR-20 | Bloodsport", "P2000 | Imperial Dragon", "R8 Revolver | Reboot"
        ),
        image_url="https://community.akamai.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttyVfPaERSR0Wqmu7LAocGJKz2lu_XsnXwtmkJjSU91dh8bj35VTqVBP4io_frHEVtvP5bPZrd6XECmOSxe0v4bRoTnnjwBkitWrRm4yoeX3GagMnCZZ2FPlK7EcEv22BnQ",
    ),
    "bravo": CaseDefinition(
        name="Operation Bravo Case",
        price=2500,
        items=(
            "AK-47 | Fire Serpent", "Desert Eagle | Golden Koi", "AWP | Graphite", "P90 | Emerald Dragon",
            "P2000 | Ocean Foam", "USP-S | Overgrowth", "MAC-10 | Graven"
        ),
        image_url="https://community.akamai.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttyVfPaERSR0Wqmu7LAocGJKz2lu_XsnXwtmkJjSU91dh8bj7-lz1QAn4kZjf9CsVuvf7OfQ5IabBVzbHlb915bcwHCjikEp_sTnTn4z6eH6RblQlC8RwFPlK7EdXSP0Ibg",
    ),
    "weapon1": CaseDefinition(
        name="CS:GO Weapon Case",
        price=3000,
        items=(
            "AWP | Lightning Strike", "AK-47 | Case Hardened", "Desert Eagle | Hypnotic", "Glock-18 | Dragon Tattoo",
            "USP-S | Dark Water", "M4A1-S | Dark Water", "SG 553 | Ultraviolet"
        ),
        image_url="https://community.akamai.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttyVfPaERSR0Wqmu7LAocGJKz2lu_XsnXwtmkJjSU91dh8bji61XxRCKg0MSz_nUDvPb-OPFvdKTFDzbAkbp16bY5Gn6wkx9ysj7Xntf9IC6WZgA-Sswnnj45WXo",
    ),
    "prisma": CaseDefinition(
        name="Prisma Case",
        price=150,
        items=(
            "M4A4 | The Emperor", "Five-SeveN | Angry Mob", "AWP | Atheris", "AUG | Momentum",
            "XM1014 | Incinegator", "R8 Revolver | Skull Crusher", "Desert Eagle | Light Rail"
        ),
        image_url="https://community.akamai.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttyVfPaERSR0Wqmu7LAocGJKz2lu_XsnXwtmkJjSU91dh8bj35VTqVBP4io_fr3AV6aD8O6BpdKKQVmPEwr1zs-c8Tnngl09w52zTmY2sc3jBag8jXpohE_lK7Ede7E2Kfw",
    ),
    "chroma3": CaseDefinition(
        name="Chroma 3 Case",
        price=350,
        items=(
            "M4A1-S | Chantico's Fire", "PP-Bizon | Judgement of Anubis", "SSG 08 | Ghost Crusader", "P250 | Asiimov",
            "UMP-45 | Primal Saber", "CZ75-Auto | Red Astor", "Galil AR | Firefight"
        ),
        image_url="https://community.akamai.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttyVfPaERSR0Wqmu7LAocGJKz2lu_XsnXwtmkJjSU91dh8bj35VTqVBP4io_frHAVuKf7PaJucPLHW2TExb9z4OdvHirixEomtW7cyduvci2VZ1AiCsR2Q_lK7EdW_VBhrw",
    ),
    "dreams": CaseDefinition(
        name="Dreams & Nightmares Case",
        price=450,
        items=(
            "AK-47 | Nightwish", "MP9 | Starlight Protector", "Dual Berettas | Melondrama", "FAMAS | Rapid Eye Movement",
            "MP7 | Abyssal Apparition", "USP-S | Ticket to Hell", "M4A1-S | Night Terror"
        ),
        image_url="https://community.akamai.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttyVfPaERSR0Wqmu7LAocGJKz2lu_XsnXwtmkJjSU91dh8bj35VTqVBP4io_frnIV7Kb5OaU-JqfHDzXFle0u4LY8Gy_kkRgisGzcm4v4J3vDOAQmDMdyRvlK7EcmeCU3yw",
    ),
    "fracture": CaseDefinition(
        name="Fracture Case",
        price=250,
        items=(
            "Desert Eagle | Printstream", "AK-47 | Legion of Anubis", "M4A4 | Tooth Fairy", "Glock-18 | Vogue",
            "XM1014 | Entombed", "MAC-10 | Allure", "MAG-7 | Monster Call"
        ),
        image_url="https://community.akamai.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttyVfPaERSR0Wqmu7LAocGJKz2lu_XsnXwtmkJjSU91dh8bj35VTqVBP4io_fr3QV7aD7OP01IfbGDzPCmbsm4LU5GnvkzUsi4WvUmIqtci_CPQNyApsjE_lK7EfrhW545A",
    ),
    "recoil": CaseDefinition(
        name="Recoil Case",
        price=500,
        items=(
            "USP-S | Printstream", "AK-47 | Ice Coaled", "Sawed-Off | Kiss♥Love", "SG 553 | Dragon Tech",
            "P250 | Visions", "Dual Berettas | Flora Carnivora", "R8 Revolver | Crazy 8"
        ),
        image_url="https://community.akamai.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttyVfPaERSR0Wqmu7LAocGJKz2lu_XsnXwtmkJjSU91dh8bj35VTqVBP4io_frnMVu6b-avA-JqSSCjSWwuhz47U9TCzlxh9yt2WGnNqgIi-fbgUkWMNxFPlK7EdIJF6a2Q",
    ),
    "kilowatt": CaseDefinition(
        name="Kilowatt Case",
        price=800,
        items=(
            "AK-47 | Inheritance", "AWP | Chrome Cannon", "M4A1-S | Black Lotus", "Zeus x27 | Olympus",
            "USP-S | Jawbreaker", "Glock-18 | Block-18", "M4A4 | Etch Lord"
        ),
        image_url="https://community.akamai.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttyVfPaERSR0Wqmu7LAocGJKz2lu_XsnXwtmkJjSU91dh8bj35VTqVBP4io_frnEVvqf_a6VoIfGSXz7Hlbwg57QwSS_mxhl15jiGyN37c3_GZw91W8BwRflK7EfKsa2sfw",
    ),
}

# Load skin image mapping from static asset catalog
SKIN_IMAGES: dict[str, str] = {}
skins_json_path = os.path.join(os.path.dirname(__file__), "..", "assets", "cases", "skins.json")
if os.path.exists(skins_json_path):
    try:
        with open(skins_json_path, encoding="utf-8") as _f:
            SKIN_IMAGES = json.load(_f)
    except Exception:
        pass

RARITIES = (
    ("Mil-Spec (Mavi)", 79.92, 1.0, 0x4B69FF, (75, 105, 255)),
    ("Restricted (Mor)", 15.98, 1.8, 0x8847FF, (136, 71, 255)),
    ("Classified (Pembe)", 3.19, 3.5, 0xD32CE6, (211, 44, 230)),
    ("Covert (Kırmızı)", 0.64, 8.0, 0xEB4B4B, (235, 75, 75)),
    ("Rare Special Item (Altın)", 0.26, 20.0, 0xFFD700, (255, 215, 0)),
)

WEAR_NAMES = (
    (0.07, "Factory New"),
    (0.15, "Minimal Wear"),
    (0.38, "Field-Tested"),
    (0.45, "Well-Worn"),
    (1.01, "Battle-Scarred"),
)


def steam_market_url(item_name: str) -> str:
    return f"https://steamcommunity.com/market/listings/730/{quote(item_name, safe='')}"


async def resolve_steam_image_url(listing_url: str) -> str | None:
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                listing_url,
                headers={"User-Agent": "Mozilla/5.0 (MekanBot/2.0)"},
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
    except Exception:
        return None


def create_drop(case: CaseDefinition) -> tuple[str, str, str, float, int, str, int, tuple[int, int, int], str]:
    rarity_entry = random.choices(RARITIES, weights=[item[1] for item in RARITIES], k=1)[0]
    rarity, _, multiplier, color_code, rgb_color = rarity_entry
    float_value = round(random.uniform(0.0, 1.0), 4)
    wear = next(name for upper_bound, name in WEAR_NAMES if float_value < upper_bound)

    if rarity == "Rare Special Item (Altın)":
        base_name = random.choice(["★ Karambit | Doppler", "★ Butterfly Knife | Fade", "★ M9 Bayonet | Lore"])
    else:
        base_name = random.choice(case.items)

    item_name = f"{base_name} ({wear})"
    image_url = SKIN_IMAGES.get(base_name) or ""
    price = max(1, int(case.price * multiplier * (1.15 - min(float_value, 1.0) * 0.6)))
    return item_name, wear, rarity, float_value, price, steam_market_url(base_name), color_code, rgb_color, image_url


def render_roulette_gif(case_items: tuple[str, ...], winning_name: str, winning_rgb: tuple[int, int, int]) -> discord.File:
    """Renders a dynamic CS2 case opening roulette GIF that decelerates and stops at the winning item."""
    W, H = 640, 160
    card_w = 110
    card_h = 130
    y_card = (H - card_h) // 2

    # Build horizontal roulette strip
    strip: list[tuple[str, tuple[int, int, int]]] = []
    for _ in range(18):
        rand_item = random.choice(case_items)
        rand_rarity = random.choice(RARITIES[:3])
        strip.append((rand_item, rand_rarity[4]))
    strip.append((winning_name, winning_rgb))
    for _ in range(6):
        rand_item = random.choice(case_items)
        rand_rarity = random.choice(RARITIES[:4])
        strip.append((rand_item, rand_rarity[4]))

    target_idx = 18
    target_center_x = target_idx * card_w + card_w // 2
    total_dist = target_center_x - (W // 2)

    frames = []
    n_frames = 17
    durations = []

    for i in range(n_frames):
        # Ease-out cubic deceleration curve
        progress = 1.0 - (1.0 - (i / (n_frames - 1))) ** 3
        curr_offset = progress * total_dist

        im = Image.new("RGB", (W, H), (20, 22, 28))
        draw = ImageDraw.Draw(im)

        for idx, (name, color) in enumerate(strip):
            cx = idx * card_w - curr_offset
            if -card_w <= cx <= W:
                draw.rectangle([cx + 3, y_card, cx + card_w - 3, y_card + card_h], fill=(32, 35, 44), outline=color, width=2)
                draw.rectangle([cx + 3, y_card + card_h - 8, cx + card_w - 3, y_card + card_h], fill=color)
                clean_n = name.split("|")[-1].strip() if "|" in name else name
                draw.text((cx + 8, y_card + 35), clean_n[:12], fill=(240, 240, 240))

        # Center gold needle marker
        draw.polygon([(W // 2 - 8, 2), (W // 2 + 8, 2), (W // 2, 16)], fill=(255, 215, 0))
        draw.polygon([(W // 2 - 8, H - 2), (W // 2 + 8, H - 2), (W // 2, H - 16)], fill=(255, 215, 0))
        draw.line([(W // 2, 16), (W // 2, H - 16)], fill=(255, 215, 0), width=2)

        dur = 120 if i < n_frames - 2 else 600
        durations.append(dur)
        frames.append(im.quantize(colors=64))

    buf = io.BytesIO()
    frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:], duration=durations, loop=1)
    buf.seek(0)
    return discord.File(buf, filename="roulette.gif")


class CaseSelect(discord.ui.Select):
    def __init__(self, cog: "Cases"):
        options = [
            discord.SelectOption(
                label=case.name,
                value=key,
                description=f"{case.price} Kredi",
                emoji="📦",
            )
            for key, case in CASES.items()
        ]
        super().__init__(
            placeholder="🔎 İncelemek istediğiniz kasayı seçiniz...",
            options=options,
            row=0,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]
        case = CASES[key]
        embed = discord.Embed(
            title=f"📦 {case.name}",
            description=(
                f"💸 **Fiyat:** `{case.price} Kredi`\n"
                f"🛒 **Açmak için:** `/buycase {key}`\n\n"
                f"🔫 **Bu Kasadan Çıkabilecek Skinler:**\n"
                + "\n".join(f"• {item}" for item in case.items)
                + "\n• ★ Nadir Özel Bıçak / Eldiven (Altın)"
            ),
            color=discord.Color.gold(),
        )
        embed.set_thumbnail(url=case.image_url)
        embed.set_image(url=case.image_url)
        embed.set_footer(text="Kasayı açmak için: /buycase " + key)
        await interaction.response.edit_message(embed=embed, view=CaseCatalogView(self.cog, selected=key))


class CaseCatalogView(discord.ui.View):
    def __init__(self, cog: "Cases", selected: str | None = None):
        super().__init__(timeout=180)
        self.cog = cog
        self.selected = selected
        select = CaseSelect(cog)
        if selected:
            for opt in select.options:
                opt.default = (opt.value == selected)
        self.add_item(select)


class TradeView(discord.ui.View):
    def __init__(self, cog: "Cases", sender: discord.Member, receiver: discord.Member, item_id: int):
        super().__init__(timeout=120)
        self.cog, self.sender, self.receiver, self.item_id = cog, sender, receiver, item_id
        self.done = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.receiver:
            await interaction.response.send_message(
                "Bu takas teklifi yalnızca alıcı tarafından yanıtlanabilir.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Kabul Et", style=discord.ButtonStyle.success, emoji="🤝")
    async def accept(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.done:
            return
        self.done = True
        guild_id = interaction.guild.id if interaction.guild else self.sender.guild.id
        item = await self.cog.bot.db.transfer_inventory_item(guild_id, self.sender.id, self.receiver.id, self.item_id)
        if item is None:
            await interaction.response.edit_message(
                content="❌ Eşya bulunamadı veya daha önce transfer edilmiştir.",
                view=None,
            )
            return
        await interaction.response.edit_message(content="✅ Takas başarıyla tamamlandı!", view=None)

    @discord.ui.button(label="Reddet", style=discord.ButtonStyle.danger, emoji="✖️")
    async def decline(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.done = True
        await interaction.response.edit_message(content="❌ Takas teklifi reddedildi.", view=None)
        self.stop()


class InventoryView(discord.ui.View):
    def __init__(self, cog: "Cases", guild_id: int, user_id: int, page: int, total: int):
        super().__init__(timeout=180)
        self.cog, self.guild_id, self.user_id, self.page, self.total = cog, guild_id, user_id, page, total
        self.page_size = 10
        self.previous.disabled = page == 0
        self.next.disabled = (page + 1) * self.page_size >= total

    async def render(self, interaction: discord.Interaction):
        items = await self.cog.bot.db.list_inventory(self.guild_id, self.user_id, self.page_size, self.page * self.page_size)

        embed = discord.Embed(
            title="🎒 CS2 Envanteriniz",
            color=discord.Color.blurple(),
        )
        if not items:
            embed.description = "Envanterinizde henüz eşya bulunmamaktadır.\n`/buycase` ile kasa açabilirsiniz!"
        else:
            for item in items:
                img_link = f"[🖼️ Resmi Gör]({item['image_url']})" if item["image_url"] else f"[🔗 Steam Market]({steam_market_url(item['item_name'].split(' (')[0])})"
                embed.add_field(
                    name=f"🆔 ID: {item['id']} | 🔫 {item['item_name']}",
                    value=f"✨ **{item['rarity']}** | 🎯 Float: `{item['float_value']:.4f}` | 💰 **{item['price']} Kredi**\n{img_link}",
                    inline=False,
                )

        total_pages = max(1, (self.total + self.page_size - 1) // self.page_size)
        embed.set_footer(text=f"Sayfa {self.page + 1}/{total_pages} • Toplam {self.total} eşya")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⬅️ Önceki", style=discord.ButtonStyle.secondary)
    async def previous(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.page -= 1
        self.previous.disabled = self.page == 0
        self.next.disabled = False
        await self.render(interaction)

    @discord.ui.button(label="Sonraki ➡️", style=discord.ButtonStyle.secondary)
    async def next(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.page += 1
        self.previous.disabled = False
        self.next.disabled = (self.page + 1) * self.page_size >= self.total
        await self.render(interaction)


class Cases(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(name="cases", description="Satın alınabilir CS2 kasalarını ve görsel mağazasını listeler.")
    async def cases(self, ctx: discord.ApplicationContext):
        if not await require_channel(ctx, "game_channel"):
            return

        embed = discord.Embed(
            title="📦 CS2 Kasa Mağazası",
            description=(
                "Açmak istediğiniz kasayı seçmek için aşağıdaki menüyü kullanabilir veya\n"
                "`/buycase <kasa_adi>` yazabilirsiniz (örn: `/buycase revolution`).\n"
                "───────────────────────────────"
            ),
            color=discord.Color.gold(),
        )

        catalog_path = os.path.join(os.path.dirname(__file__), "..", "assets", "cases", "catalog.png")
        file = None
        if os.path.exists(catalog_path):
            file = discord.File(catalog_path, filename="cases_catalog.png")
            embed.set_image(url="attachment://cases_catalog.png")
        else:
            embed.set_thumbnail(url=CASES["revolution"].image_url)

        for key, case in CASES.items():
            sample_skins = ", ".join(case.items[:2]) + "..."
            embed.add_field(
                name=f"🛒 {case.name} (`{key}`)",
                value=f"💸 **Fiyat:** `{case.price} Kredi` | [🖼️ Kasa Görseli]({case.image_url})\n🔫 *{sample_skins}*",
                inline=False,
            )

        embed.set_footer(text="Kasaları incelemek için aşağıdaki seçim menüsünü kullanabilirsiniz.")
        view = CaseCatalogView(self)
        if file:
            await ctx.respond(embed=embed, file=file, view=view)
        else:
            await ctx.respond(embed=embed, view=view)

    @discord.slash_command(name="buycase", description="CS2 kasası satın alır ve animasyonlu olarak açar.")
    async def buycase(
        self,
        ctx: discord.ApplicationContext,
        kasa_adi: discord.Option(
            str,
            description="Açmak istediğiniz kasanın adı veya kodu",
            choices=list(CASES.keys()),
        ),
    ):
        try:
            if not await require_channel(ctx, "game_channel"):
                return

            key = kasa_adi.casefold().replace(" ", "")
            case = CASES.get(key)
            if case is None:
                await ctx.respond(
                    "❌ Belirtilen kasa bulunamadı. Kullanılabilir kasaları `/cases` komutuyla görüntüleyebilirsiniz.",
                    ephemeral=True,
                )
                return

            if not await self.bot.db.try_withdraw(ctx.guild.id, ctx.author.id, case.price):
                await ctx.respond("❌ Bakiyeniz bu kasayı satın almak için yeterli değildir.", ephemeral=True)
                return

            item_name, wear, rarity, float_value, price, market_url, rarity_color, rgb_color, image_url = create_drop(case)

            # Generate dynamic CS2 roulette animation GIF
            gif_file = render_roulette_gif(case.items, item_name, rgb_color)
            opening = discord.Embed(
                title=f"🎁 {case.name} Açılıyor...",
                description=(
                    f"🎰 **{case.name}** açılıyor...\n"
                    f"*Rulet dönüyor, itemler geçiyor... Şansınız belirleniyor!*"
                ),
                color=discord.Color.gold(),
            )
            opening.set_thumbnail(url=case.image_url)
            opening.set_image(url="attachment://roulette.gif")
            await ctx.respond(embed=opening, file=gif_file)

            # Roulette suspense delay
            await asyncio.sleep(3.2)

            # Fallback to scraping if skin image was not in verified catalog
            if not image_url:
                image_url = await resolve_steam_image_url(market_url) or case.image_url

            item_id = await self.bot.db.add_inventory_item(
                ctx.guild.id, ctx.author.id, item_name, rarity, float_value, price, image_url
            )

            result = discord.Embed(
                title=f"🎉 {case.name} Açıldı!",
                description=f"### 🔫 **{item_name}**\n*Tebrikler! Envanterinize yeni bir eşya eklendi.*",
                color=rarity_color,
                url=market_url,
            )
            result.add_field(name="💎 Nadirlik", value=f"**{rarity}**", inline=True)
            result.add_field(name="🎯 Float Değeri", value=f"`{float_value:.4f}` ({wear})", inline=True)
            result.add_field(name="💰 Satış Değeri", value=f"**{price} Kredi**", inline=True)
            result.add_field(name="🆔 Eşya ID", value=f"`#{item_id}`", inline=True)
            result.add_field(name="🔗 Steam Pazarı", value=f"[Pazar Fiyatı]({market_url})", inline=True)

            # Showcase: Thumbnail is the 3D Case, main image is the authentic dropped Skin!
            result.set_thumbnail(url=case.image_url)
            if image_url:
                result.set_image(url=image_url)

            result.set_footer(
                text=f"Eşyayı satmak için: /sell {item_id} | Takaslamak için: /trade @kullanici {item_id}"
            )
            await ctx.interaction.edit_original_response(embed=result)

        except Exception as e:
            await ctx.channel.send(f"🚨 **Kasa açma hatası oluştu:** `{str(e)}`")
            print(f"Kasa açma hatası: {e}")

    @discord.slash_command(name="inventory", description="Envanterinizi sayfalı olarak görüntüler.")
    async def inventory(self, ctx: discord.ApplicationContext):
        if not await require_channel(ctx, "game_channel"):
            return
        total = await self.bot.db.count_inventory(ctx.guild.id, ctx.author.id)
        view = InventoryView(self, ctx.guild.id, ctx.author.id, 0, total)
        items = await self.bot.db.list_inventory(ctx.guild.id, ctx.author.id, 10, 0)

        embed = discord.Embed(title="🎒 CS2 Envanteriniz", color=discord.Color.blurple())
        if not items:
            embed.description = "Envanterinizde henüz eşya bulunmamaktadır.\n`/buycase` komutu ile kasa açabilirsiniz!"
        else:
            for item in items:
                img_link = f"[🖼️ Resmi Gör]({item['image_url']})" if item["image_url"] else f"[🔗 Steam Market]({steam_market_url(item['item_name'].split(' (')[0])})"
                embed.add_field(
                    name=f"🆔 ID: {item['id']} | 🔫 {item['item_name']}",
                    value=f"✨ **{item['rarity']}** | 🎯 Float: `{item['float_value']:.4f}` | 💰 **{item['price']} Kredi**\n{img_link}",
                    inline=False,
                )

        embed.set_footer(text=f"Sayfa 1/{max(1, (total + 9) // 10)} • Toplam {total} eşya")
        await ctx.respond(embed=embed, view=view)

    @discord.slash_command(name="sell", description="Envanterinizdeki eşyayı satar ve hesabınıza kredi ekler.")
    async def sell(self, ctx: discord.ApplicationContext, item_id: int):
        if not await require_channel(ctx, "game_channel"):
            return
        price = await self.bot.db.sell_inventory_item(ctx.guild.id, ctx.author.id, item_id)
        if price is None:
            await ctx.respond("❌ Belirtilen eşya size ait değil veya mevcut değil.", ephemeral=True)
            return
        await ctx.respond(f"✅ **#{item_id}** numaralı eşya başarıyla satıldı! Hesabınıza **+{price} kredi** yatırıldı.")

    @discord.slash_command(name="trade", description="Başka bir kullanıcıya envanterinizden eşya takası teklif eder.")
    async def trade(self, ctx: discord.ApplicationContext, kullanici: discord.Member, item_id: int):
        if not await require_channel(ctx, "game_channel"):
            return
        if kullanici == ctx.author or kullanici.bot:
            await ctx.respond("❌ Kendinizle veya botlarla takas yapamazsınız.", ephemeral=True)
            return
        if not await self.bot.db.owns_inventory_item(ctx.guild.id, ctx.author.id, item_id):
            await ctx.respond("❌ Belirtilen eşya size ait değil veya mevcut değil.", ephemeral=True)
            return
        embed = discord.Embed(
            title="🤝 CS2 Eşya Takas Teklifi",
            description=(
                f"{ctx.author.mention}, **#{item_id}** ID'li eşyayı {kullanici.mention} kullanıcısına "
                "takaslamak istiyor.\n\n"
                "Teklifi onaylamak için alıcı aşağıdaki butona tıklamalıdır."
            ),
            color=discord.Color.gold(),
        )
        await ctx.respond(content=kullanici.mention, embed=embed, view=TradeView(self, ctx.author, kullanici, item_id))


def setup(bot):
    return add_cog(bot, Cases(bot))
