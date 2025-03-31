import discord
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="help", description="AuthShield Help")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Welcome to AuthShield!!",
            description=(
                "AuthShield is a bot specialized in authentication.\nIt helps you block malicious bots.\n\n"
                "[Here is the bot status(comming soon)](https://status.sakana11.org/)\n"
            ),
            color=discord.Color.yellow()
        )

        embed.add_field(
            name="system commands",
            value=(
                "**`/help`**: AuthShield Help\n"
                "**`/info`**: AuthShield Information\n"
                "**`/status`**: AuthShield Status\n"
                "**`/invite`**: Invite Link\n"),
            inline=False
        )
        
        embed.add_field(
            name="AuthShield panel commands",
            value=(
                "**`/apanel`**: Set up the authentication panel.\n"
                "**`/apanel_remove`**: Remove the authentication panel.\n"),
            inline=False
        )

        embed.set_footer(
            text="https://sakana11.org/authshield"
        )

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))