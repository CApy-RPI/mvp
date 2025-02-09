import discord
from discord import app_commands
from discord.ext import commands
from typing import ClassVar

from config import settings
from .request_modal import RequestModal
from frontend.config_colors import *
from .report_types import ReportType


class BaseReportCog(commands.Cog):
    report_type: ClassVar[ReportType]

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def command_name(self) -> str:
        return self.report_type.command

    @property
    def command_description(self) -> str:
        return self.report_type.description

    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="report")
    async def report(self, interaction: discord.Interaction):
        rt = self.report_type
        if not isinstance(rt.modal_title, str) or not rt.modal_title:
            raise ValueError("Modal title must be a non-empty string")

        modal = RequestModal(rt.modal_title, rt.modal_prompt)
        await interaction.response.send_modal(modal)

        try:
            await modal.wait()
        except TimeoutError:
            return

        channel = self.bot.get_channel(getattr(settings, rt.channel_id_setting))
        embed = discord.Embed(
            title=f"{rt.emoji} {rt.embed_title_prefix}: {modal.title}",
            description=modal.description,
            color=globals()[rt.embed_color],
        )
        embed.add_field(name="Submitted by", value=interaction.user.mention)
        embed.set_footer(text=f"User ID: {interaction.user.id}")

        await channel.send(embed=embed)
        await interaction.followup.send(rt.success_message, ephemeral=True)

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        cls.report.name = cls.report_type.command
        cls.report.description = cls.report_type.description
