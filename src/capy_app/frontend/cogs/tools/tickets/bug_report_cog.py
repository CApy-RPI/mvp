from discord import ButtonStyle, TextStyle
from discord.ext import commands
from frontend.config_colors import STATUS_ERROR, STATUS_IGNORED, STATUS_IMPORTANT, STATUS_RESOLVED

from config import settings

from .ticket_base import TicketBase


class BugReportCog(TicketBase):
    def __init__(self, bot: commands.Bot) -> None:
        command_config = {
            "cmd_name": "bug",
            "cmd_name_verbose": "Bug report",
            "cmd_emoji": "🐛",
            "description": "Report a bug in the bot",
            "request_channel_id": settings.TICKET_BUG_REPORT_CHANNEL_ID,
        }
        color_config = {
            "unmarked_color": STATUS_ERROR,
            "marked_colors": {
                "Important": STATUS_IMPORTANT,
                "Resolved": STATUS_RESOLVED,
                "Ignored": STATUS_IGNORED,
            },
        }
        super().__init__(
            bot,
            {
                "⭐": "Important",
                "✅": "Resolved",
                "❌": "Ignored",
                "🔄": "Unmarked",
            },
            command_config,
            color_config,
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
