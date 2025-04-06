import logging
from typing import Optional

import asyncpg
import discord
from discord.ext import commands

from src.panel.authpanel import DB_CONFIG

logger = logging.getLogger(__name__)

ERROR_MESSAGES = {
    "not_found": "⚠️ Authentication panel not found. Please check the message ID.",
    "fetch_failed": "⚠️ Failed to fetch the message.",
    "db_error": "⚠️ An error occurred during database operation: {}"
}

SUCCESS_MESSAGES = {
    "panel_removed": "✅ Authentication panel successfully removed."
}

class AuthRemove(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.conn: Optional[asyncpg.Connection] = None

    async def cog_load(self) -> None:
        self.conn = await asyncpg.connect(**DB_CONFIG)
    
    async def cog_unload(self) -> None:
        if self.conn:
            await self.conn.close()
            self.conn = None

    @discord.app_commands.command(
        name="apanel_remove",
        description="Removes the authentication panel with the specified message ID"
    )
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.describe(
        message_id="The message ID of the authentication panel to remove"
    )
    async def remove_auth_panel(self, interaction: discord.Interaction, message_id: str) -> None:
        try:
            message_id_int = int(message_id)
            
            # Retrieve the panel information from the database
            row = await self.conn.fetchrow(
                "SELECT channel_id FROM panels WHERE message_id = $1", 
                message_id_int
            )
                
            if not row:
                await interaction.response.send_message(ERROR_MESSAGES["not_found"], ephemeral=True)
                return
                
            channel_id = row["channel_id"]
            
            # Search for and delete the message
            try:
                channel = interaction.guild.get_channel(channel_id)
                if not channel:
                    channel = await self.bot.fetch_channel(channel_id)
                    
                message = await channel.fetch_message(message_id_int)
                await message.delete()
            except discord.NotFound:
                logger.warning(f"Message with ID {message_id_int} not found for deletion")
                # Even if the message is not found, delete it from the database
            except Exception as e:
                logger.error(f"Error fetching message: {e}", exc_info=True)
                await interaction.response.send_message(ERROR_MESSAGES["fetch_failed"], ephemeral=True)
                return
            
            # Delete from the database
            await self.conn.execute("DELETE FROM panels WHERE message_id = $1", message_id_int)
            
            await interaction.response.send_message(SUCCESS_MESSAGES["panel_removed"], ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("⚠️ Please enter a valid message ID.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error removing auth panel: {e}", exc_info=True)
            await interaction.response.send_message(ERROR_MESSAGES["db_error"].format(str(e)), ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AuthRemove(bot))