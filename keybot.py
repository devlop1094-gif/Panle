#!/usr/bin/env python3
"""
노맹맹 Key Discord Bot
- /관리자등록 : 관리자 등록 (최초 라이선스 필요)
- /라이선스등록 : 패널 사용 라이선스 등록
- /패널 : 키 뽑기 패널 (버튼)
- /라이선스뽑기 : 최초 관리자만, 패널용 라이선스 1회 발급
"""

import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import secrets
import string
import asyncio
from datetime import datetime

# ================== CONFIG ==================
TOKEN = os.environ.get("DISCORD_TOKEN", "YOUR_BOT_TOKEN_HERE")
DATA_FILE = "bot_data.json"
KEYS_FILE = "keys.txt"          # 로컬 키 파일 (GitHub에 올릴 것)
GITHUB_RAW = "https://raw.githubusercontent.com/여기에유저명/레포이름/main/keys.txt"

# 최초 관리자 라이선스
MASTER_LICENSE = "노맹맹"

# ================== DATA ==================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "admins": [],           # 관리자 discord user id (str)
        "licenses": {},         # license_key -> {"used": bool, "owner": user_id or None}
        "master_used": False,   # /라이선스뽑기 1회 사용 여부
        "key_count": 0
    }

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_keys():
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            return [line.strip().upper() for line in f if line.strip()]
    return []

def save_keys(keys):
    with open(KEYS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(keys) + "\n")

def gen_key(prefix="NMM"):
    """랜덤 키 생성: NMM-XXXX-XXXX-XXXX"""
    part = lambda: ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    return f"{prefix}-{part()}-{part()}-{part()}"

def gen_license():
    """패널 사용 라이선스 키"""
    part = lambda: ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(5))
    return f"LIC-{part()}-{part()}"

# ================== BOT ==================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

data = load_data()

def is_admin(user_id: int) -> bool:
    return str(user_id) in data["admins"]

def has_valid_license(user_id: int) -> bool:
    uid = str(user_id)
    for lic, info in data["licenses"].items():
        if info.get("owner") == uid and info.get("used"):
            return True
    return False

# ---------- 패널 뷰 ----------
class KeyPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="키 뽑기 (1개)", style=discord.ButtonStyle.green, custom_id="key_1")
    async def key_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.give_keys(interaction, 1)

    @discord.ui.button(label="키 뽑기 (5개)", style=discord.ButtonStyle.blurple, custom_id="key_5")
    async def key_5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.give_keys(interaction, 5)

    @discord.ui.button(label="키 뽑기 (10개)", style=discord.ButtonStyle.red, custom_id="key_10")
    async def key_10(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.give_keys(interaction, 10)

    async def give_keys(self, interaction: discord.Interaction, count: int):
        uid = interaction.user.id

        # 관리자 or 라이선스 보유자만
        if not (is_admin(uid) or has_valid_license(uid)):
            await interaction.response.send_message("❌ 라이선스가 없거나 관리자가 아닙니다.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        keys = load_keys()
        new_keys = []
        for _ in range(count):
            k = gen_key()
            while k in keys:
                k = gen_key()
            keys.append(k)
            new_keys.append(k)
            data["key_count"] += 1

        save_keys(keys)
        save_data(data)

        # DM으로 전송
        try:
            dm = await interaction.user.create_dm()
            embed = discord.Embed(
                title="🔑 노맹맹 라이선스 키",
                description=f"**{count}개** 발급 완료\n```\n" + "\n".join(new_keys) + "\n```",
                color=0x7c3aed,
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="GitHub keys.txt 에 자동 반영됨 (직접 업로드 필요)")
            await dm.send(embed=embed)
            await interaction.followup.send(f"✅ **{count}개** 키를 DM으로 보냈습니다.", ephemeral=True)
        except discord.Forbidden:
            # DM 막혀있으면 ephemeral로
            await interaction.followup.send(
                f"✅ 키 {count}개 생성됨 (DM 불가 → 여기 표시)\n```\n" + "\n".join(new_keys) + "\n```",
                ephemeral=True
            )

# ---------- 슬래시 명령어 ----------
@bot.event
async def on_ready():
    print(f"[+] Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"[+] Synced {len(synced)} commands")
    except Exception as e:
        print(f"[!] Sync failed: {e}")
    bot.add_view(KeyPanelView())  # persistent view

@bot.tree.command(name="관리자등록", description="관리자 아이디로 등록 (최초 라이선스 필요)")
@app_commands.describe(라이선스="최초 관리자 라이선스 또는 발급받은 라이선스")
async def admin_register(interaction: discord.Interaction, 라이선스: str):
    uid = str(interaction.user.id)
    lic = 라이선스.strip()

    # 이미 관리자
    if uid in data["admins"]:
        await interaction.response.send_message("✅ 이미 관리자입니다.", ephemeral=True)
        return

    # 마스터 라이선스
    if lic == MASTER_LICENSE:
        data["admins"].append(uid)
        save_data(data)
        await interaction.response.send_message(
            f"✅ **{interaction.user.display_name}** 님이 관리자로 등록되었습니다.\n"
            f"(마스터 라이선스 사용)",
            ephemeral=True
        )
        return

    # 일반 라이선스 (발급된 것)
    if lic in data["licenses"]:
        info = data["licenses"][lic]
        if info.get("used") and info.get("owner") is None:
            # 아직 소유자 없는 사용된 라이선스 → 관리자 등록용으로 허용
            data["admins"].append(uid)
            info["owner"] = uid
            save_data(data)
            await interaction.response.send_message(
                f"✅ 관리자로 등록되었습니다. (라이선스: `{lic}`)",
                ephemeral=True
            )
            return
        elif info.get("owner") == uid:
            data["admins"].append(uid)
            save_data(data)
            await interaction.response.send_message("✅ 관리자로 등록되었습니다.", ephemeral=True)
            return

    await interaction.response.send_message("❌ 유효하지 않은 라이선스입니다.", ephemeral=True)

@bot.tree.command(name="라이선스등록", description="패널을 사용할 수 있는 라이선스 등록")
@app_commands.describe(라이선스="발급받은 라이선스 키")
async def license_register(interaction: discord.Interaction, 라이선스: str):
    uid = str(interaction.user.id)
    lic = 라이선스.strip().upper()

    if lic not in data["licenses"]:
        await interaction.response.send_message("❌ 존재하지 않는 라이선스입니다.", ephemeral=True)
        return

    info = data["licenses"][lic]
    if info.get("used") and info.get("owner") and info["owner"] != uid:
        await interaction.response.send_message("❌ 이미 다른 사람이 사용 중인 라이선스입니다.", ephemeral=True)
        return

    info["used"] = True
    info["owner"] = uid
    save_data(data)
    await interaction.response.send_message(
        f"✅ 라이선스 등록 완료!\n이제 `/패널` 로 키를 뽑을 수 있습니다.",
        ephemeral=True
    )

@bot.tree.command(name="패널", description="키 뽑기 패널 생성")
async def panel(interaction: discord.Interaction):
    uid = interaction.user.id
    if not (is_admin(uid) or has_valid_license(uid)):
        await interaction.response.send_message(
            "❌ 권한이 없습니다.\n`/라이선스등록` 으로 라이선스를 등록하거나 관리자여야 합니다.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="🔑 노맹맹 키 발급 패널",
        description=(
            "아래 버튼을 눌러 라이선스 키를 발급받으세요.\n"
            "키는 **개인 DM**으로 전송됩니다.\n\n"
            "• 1개 / 5개 / 10개 선택 가능\n"
            "• 발급된 키는 `keys.txt`에 저장됨\n"
            "• GitHub raw에 직접 업로드 필요"
        ),
        color=0x7c3aed
    )
    embed.set_footer(text=f"요청자: {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed, view=KeyPanelView())

@bot.tree.command(name="라이선스뽑기", description="[최초 관리자 전용] 패널용 라이선스 1회 발급")
async def license_gen(interaction: discord.Interaction):
    uid = str(interaction.user.id)

    # 마스터 라이선스로 등록된 관리자만 + 아직 안 뽑았을 때만
    if uid not in data["admins"]:
        await interaction.response.send_message("❌ 관리자만 사용 가능합니다.", ephemeral=True)
        return

    if data.get("master_used"):
        await interaction.response.send_message(
            "❌ 이미 `/라이선스뽑기`를 사용했습니다.\n(1회만 가능)",
            ephemeral=True
        )
        return

    # 라이선스 생성
    lic = gen_license()
    while lic in data["licenses"]:
        lic = gen_license()

    data["licenses"][lic] = {
        "used": False,
        "owner": None,
        "created_by": uid,
        "created_at": datetime.utcnow().isoformat()
    }
    data["master_used"] = True
    save_data(data)

    try:
        dm = await interaction.user.create_dm()
        embed = discord.Embed(
            title="🎫 패널 라이선스 발급",
            description=(
                f"**1회용 패널 라이선스**가 발급되었습니다.\n\n"
                f"```\n{lic}\n```\n"
                f"이 키를 다른 사람에게 주면\n"
                f"`/라이선스등록` → `/패널` 사용 가능합니다."
            ),
            color=0xf59e0b
        )
        await dm.send(embed=embed)
        await interaction.response.send_message("✅ 라이선스를 DM으로 보냈습니다. (1회 사용 완료)", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message(
            f"✅ 라이선스 생성됨 (DM 불가)\n```\n{lic}\n```",
            ephemeral=True
        )

@bot.tree.command(name="상태", description="봇 상태 / 키 개수 확인 (관리자)")
async def status(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ 관리자 전용", ephemeral=True)
        return

    keys = load_keys()
    embed = discord.Embed(title="📊 노맹맹 봇 상태", color=0x22c55e)
    embed.add_field(name="관리자 수", value=str(len(data["admins"])), inline=True)
    embed.add_field(name="등록된 라이선스", value=str(len(data["licenses"])), inline=True)
    embed.add_field(name="발급된 키 총합", value=str(len(keys)), inline=True)
    embed.add_field(name="마스터 뽑기 사용", value="✅ 사용됨" if data.get("master_used") else "❌ 미사용", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="키목록", description="현재 keys.txt 미리보기 (관리자, 최근 20개)")
async def key_list(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ 관리자 전용", ephemeral=True)
        return
    keys = load_keys()
    if not keys:
        await interaction.response.send_message("키가 없습니다.", ephemeral=True)
        return
    preview = "\n".join(keys[-20:])
    await interaction.response.send_message(f"최근 키 {min(20,len(keys))}개:\n```\n{preview}\n```", ephemeral=True)

# ================== RUN ==================
if __name__ == "__main__":
    if TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("[!] DISCORD_TOKEN 환경변수 또는 코드에 토큰을 넣어주세요")
    else:
        bot.run(TOKEN)
