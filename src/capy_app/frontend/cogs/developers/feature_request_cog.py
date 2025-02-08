from discord.ext import commands

from .ticket_cog_template import BaseReportCog
from .report_types import FEATURE_REQUEST


class FeatureRequestCog(BaseReportCog):
    report_type = FEATURE_REQUEST


async def setup(bot: commands.Bot):
    await bot.add_cog(FeatureRequestCog(bot))
