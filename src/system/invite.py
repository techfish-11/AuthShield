import discord
from discord.ext import commands

class inviteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="invite", description="AuthShield Invite Link")
    async def info(self, interaction: discord.Interaction):
        message = (
            "https://discord.com/oauth2/authorize?client_id=1356227161832427671"
        )
        await interaction.response.send_message(content=message)

async def setup(bot):
    await bot.add_cog(inviteCog(bot))