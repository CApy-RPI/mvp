from discord.ext import commands

from .ticket_cog_template import BaseReportCog
from .report_types import BUG_REPORT


class BugReportCog(BaseReportCog):
    report_type = BUG_REPORT


async def setup(bot: commands.Bot):
    await bot.add_cog(BugReportCog(bot))
