import discord
from discord.ext import commands
from discord import app_commands
from frontend.utils import colors


class PrivacyPolicyCog(commands.Cog):
    """Privacy policy and data handling information."""

    @app_commands.command(
        name="privacy",
        description="View our privacy policy and data handling practices",
    )
    async def privacy(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Privacy Policy & Data Handling",
            color=colors.INFO,
            description="Here's how we handle your information:",
        )

        embed.add_field(
            name="📝 Data We Collect",
            value=(
                "**Basic Discord Data:**\n"
                "• Discord User ID\n"
                "• Server (Guild) ID\n"
                "• Channel configurations\n"
                "• Role assignments\n\n"
                "**Academic Profile Data:**\n"
                "• Full name (first, middle, last)\n"
                "• School email address\n"
                "• Student ID number\n"
                "• Major(s)\n"
                "• Expected graduation year\n"
                "• Phone number (optional)\n"
            ),
            inline=False,
        )

        embed.add_field(
            name="🔒 Data Storage",
            value=(
                "• Data is stored in a secure MongoDB database\n"
                "• Regular backups are maintained\n"
            ),
            inline=False,
        )

        embed.add_field(
            name="👥 Data Access",
            value=(
                "**Who can access your data:**\n"
                "• Club/Organization officers for member management\n"
                "• Server administrators for server settings\n"
                "• Bot developers for maintenance only\n\n"
                "**How your data is used:**\n"
                "• Member verification and tracking\n"
                "• Event participation management\n"
                "• Academic program coordination\n"
                "• Communication within organizations\n\n"
                "Your information is never shared with third parties or used for marketing purposes."
            ),
            inline=False,
        )

        embed.add_field(
            name="❌ Data Deletion",
            value=(
                "You can request data deletion through:\n"
                "• Contacting the bot administrators\n\n"
                "Note: Some basic data may be retained for academic records as required."
            ),
            inline=False,
        )

        embed.set_footer(text="Last updated: February 2024")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PrivacyPolicyCog(bot))
