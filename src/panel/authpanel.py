import asyncpg
import base64
import logging
import os
from io import BytesIO
from typing import Final, Optional

import aiohttp
import discord
from discord.ext import commands

API_BASE_URL: Final[str] = "https://captcha.evex.land/api/captcha"
TIMEOUT_SECONDS: Final[int] = 30
MIN_DIFFICULTY: Final[int] = 1
MAX_DIFFICULTY: Final[int] = 10
# PostgreSQL接続設定
DB_CONFIG: Final[dict] = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", 5432),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
    "database": os.getenv("POSTGRES_DB", "authshield")
}

ERROR_MESSAGES: Final[dict] = {
    "invalid_difficulty": "Difficulty must be specified between 1 and 10.",
    "fetch_failed": "Failed to fetch CAPTCHA.",
    "http_error": "HTTP error occurred: {}",
    "unexpected_error": "An unexpected error occurred: {}"
}

SUCCESS_MESSAGES: Final[dict] = {
    "panel_created": "✅ Authentication panel has been created.",
    "correct": "✅ Correct! Authentication succeeded.",
    "incorrect": "❌ Incorrect. The correct answer was `{}`.\nAuthentication failed.",
    "timeout": "⏰ Timeout. Please try again."
}

logger = logging.getLogger(__name__)

class PersistentAuthView(discord.ui.View):
    def __init__(self, message_id: int, role_id: int, difficulty: int, session: aiohttp.ClientSession):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.role_id = role_id
        self.difficulty = difficulty
        self.session = session
        button = discord.ui.Button(
            label="Authenticate",
            style=discord.ButtonStyle.primary,
            custom_id=f"persistent_auth_button_{message_id}"
        )
        button.callback = self.auth_button_callback
        self.add_item(button)

    async def auth_button_callback(self, interaction: discord.Interaction) -> None:
        image_bytes, answer, error = await self.fetch_captcha()
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        file = discord.File(BytesIO(image_bytes), filename="captcha.png")
        embed = discord.Embed(title="CAPTCHA", description="Press the button below to continue authentication.")
        embed.set_image(url="attachment://captcha.png")
        view = PersistentModalButtonView(answer, self.message_id, self.role_id)
        await interaction.response.send_message(embed=embed, file=file, view=view, ephemeral=True)

    async def fetch_captcha(self) -> tuple[Optional[bytes], Optional[str], Optional[str]]:
        url = f"{API_BASE_URL}?difficulty={self.difficulty}"
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return None, None, ERROR_MESSAGES["fetch_failed"]
                data = await response.json()
                image_data = data["image"].split(",")[1]
                image_bytes = base64.b64decode(image_data)
                return image_bytes, data["answer"], None
        except aiohttp.ClientError as e:
            logger.error("HTTP error in captcha fetch: %s", e, exc_info=True)
            return None, None, ERROR_MESSAGES["http_error"].format(str(e))
        except Exception as e:
            logger.error("Unexpected error in captcha fetch: %s", e, exc_info=True)
            return None, None, ERROR_MESSAGES["unexpected_error"].format(str(e))

class PersistentModalButtonView(discord.ui.View):
    def __init__(self, answer: str, message_id: int, role_id: int):
        super().__init__(timeout=None)
        self.answer = answer
        self.message_id = message_id
        self.role_id = role_id
        button = discord.ui.Button(
            label="Open Authentication Screen",
            style=discord.ButtonStyle.secondary,
            custom_id=f"persistent_modal_button_{message_id}"
        )
        button.callback = self.modal_button_callback
        self.add_item(button)

    async def modal_button_callback(self, interaction: discord.Interaction) -> None:
        modal = PersistentAuthModal(self.answer, self.role_id)
        await interaction.response.send_modal(modal)

# Specify custom_id here and also for text input for stable operation after restart
class PersistentAuthModal(discord.ui.Modal):
    def __init__(self, answer: str, role_id: int):
        super().__init__(
            title="Authentication CAPTCHA",
            custom_id=f"persistent_auth_modal_{role_id}"
        )
        self.answer = answer
        self.role_id = role_id
        self.answer_input = discord.ui.TextInput(
            label="Enter the characters displayed in the image",
            placeholder="Enter characters here",
            required=True,
            max_length=10,
            custom_id=f"persistent_auth_modal_answer_input_{role_id}"
        )
        self.add_item(self.answer_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if self.answer_input.value.lower() == self.answer.lower():
            role = interaction.guild.get_role(self.role_id)
            if role:
                await interaction.user.add_roles(role)
            message = SUCCESS_MESSAGES["correct"]
        else:
            message = SUCCESS_MESSAGES["incorrect"].format(self.answer)
        await interaction.response.send_message(message, ephemeral=True)

class Auth(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._session: Optional[aiohttp.ClientSession] = None
        self.conn: Optional[asyncpg.Connection] = None

    async def _initialize_db(self) -> None:
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS panels (
                message_id BIGINT PRIMARY KEY,
                channel_id BIGINT NOT NULL,
                role_id BIGINT NOT NULL,
                difficulty INTEGER NOT NULL
            )
            """
        )

    async def cog_load(self) -> None:
        self._session = aiohttp.ClientSession()
        self.conn = await asyncpg.connect(**DB_CONFIG)
        await self._initialize_db()
        async with self.conn.transaction():
            rows = await self.conn.fetch("SELECT message_id, channel_id, role_id, difficulty FROM panels")
            for row in rows:
                view = PersistentAuthView(row["message_id"], row["role_id"], row["difficulty"], self._session)
                self.bot.add_view(view)

    async def cog_unload(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None
        if self.conn:
            await self.conn.close()
            self.conn = None

    @discord.app_commands.command(
        name="apanel",
        description="Create an authentication panel",
    )
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.describe(
        role="Role to be granted after authentication",
        difficulty="Difficulty of authentication (1-10)"
    )
    async def create_auth_panel(self, interaction: discord.Interaction, role: discord.Role, difficulty: int = MIN_DIFFICULTY) -> None:
        if not MIN_DIFFICULTY <= difficulty <= MAX_DIFFICULTY:
            await interaction.response.send_message(ERROR_MESSAGES["invalid_difficulty"], ephemeral=True)
            return

        embed = discord.Embed(
            title="Authentication Panel",
            description="Press the button below to start authentication.",
            color=discord.Color.green()
        )
        message = await interaction.channel.send(embed=embed)
        view = PersistentAuthView(message.id, role.id, difficulty, self._session)
        self.bot.add_view(view)
        await message.edit(view=view)
        await self.conn.execute(
            "INSERT INTO panels (message_id, channel_id, role_id, difficulty) VALUES ($1, $2, $3, $4)",
            message.id, interaction.channel.id, role.id, difficulty
        )
        await interaction.response.send_message(SUCCESS_MESSAGES["panel_created"], ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Auth(bot))