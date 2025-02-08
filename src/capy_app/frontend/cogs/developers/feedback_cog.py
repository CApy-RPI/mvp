from discord.ext import commands

from .ticket_cog_template import BaseReportCog
from .report_types import FEEDBACK


class FeedbackCog(BaseReportCog):
    report_type = FEEDBACK


async def setup(bot: commands.Bot):
    await bot.add_cog(FeedbackCog(bot))
