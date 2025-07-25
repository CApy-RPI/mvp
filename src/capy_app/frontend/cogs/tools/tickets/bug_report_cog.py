from discord import ButtonStyle, TextStyle
from discord.ext import commands
from frontend.config_colors import STATUS_ERROR, STATUS_IGNORED, STATUS_IMPORTANT, STATUS_RESOLVED

from config import settings

from .ticket_base import TicketBase


class BugReportCog(TicketBase):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(
            bot,
            {
                "⭐": "Important",
                "✅": "Resolved",
                "❌": "Ignored",
                "🔄": "Unmarked",
            },
            "bug",
            "Bug report",
            "🐛",
            "Report a bug in the bot",
            settings.TICKET_BUG_REPORT_CHANNEL_ID,
            STATUS_ERROR,
            {
                "Important": STATUS_IMPORTANT,
                "Resolved": STATUS_RESOLVED,
                "Ignored": STATUS_IGNORED,
            },
            " ⭐ Important • ✅ Resolve • ❌ Ignore • 🔄 Reset",
        )

        self.MODAL_CONFIGS = {
            "button_modal": {
                "ephemeral": False,
                "button_label": "Open Survey",
                "button_style": ButtonStyle.success,
                "message_prompt": "📝 Ready to submit a bug report? Click the button below!",
                "modal": {
                    "title": "Feedback Form",
                    "fields": [
                        {
                            "label": "Bug Title",
                            "placeholder": "Brief description of the bug",
                            "style": TextStyle.short,
                            "required": True,
                            "max_length": 100,
                        },
                        {
                            "label": "Bug Description",
                            "placeholder": "Please provide detailed steps to reproduce the bug...",
                            "style": TextStyle.paragraph,
                            "required": True,
                            "max_length": 1000,
                        },
                    ],
                },
            }
        }


async def setup(bot: commands.Bot):
    await bot.add_cog(BugReportCog(bot))
