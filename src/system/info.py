import discord
from discord.ext import commands

class InfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="info", description="AuthShield Information")
    async def info(self, interaction: discord.Interaction):
        """Displays information about the bot."""
        embed = discord.Embed(
            title="AuthShield Information",
            description="AuthShield is a bot specialized in authentication.\nIt helps you block malicious bots.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Developer", value="techfish", inline=False)
        embed.add_field(name="Hosting", value="TechFish_Lab", inline=False)
        embed.add_field(name="WebSite", value="[WebSite (comming soon)](https://sakana11.org/authshield)", inline=False)
        embed.set_footer(text="Thank you for using this bot!")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(InfoCog(bot))