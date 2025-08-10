"""Feature request command cog.

This module handles feature request submissions through a modal interface.
Requests are sent to a designated channel for developer review.
"""

from discord import ButtonStyle, TextStyle
from discord.ext import commands
from frontend.config_colors import (
    STATUS_IGNORED,
    STATUS_IMPORTANT,
    STATUS_RESOLVED,
    STATUS_UNMARKED,
)

from config import settings

from .ticket_base import TicketBase


class FeatureRequestCog(TicketBase):
    def __init__(self, bot):
        command_config = {
            "cmd_name": "feature",
            "cmd_name_verbose": "Feature Request",
            "cmd_emoji": "💡",
            "description": "Request a new feature",
            "request_channel_id": settings.TICKET_FEATURE_REQUEST_CHANNEL_ID,
        }
        color_config = {
            "unmarked_color": STATUS_UNMARKED,
            "marked_colors": {
                "Completed": STATUS_RESOLVED,
                "Approved": STATUS_IMPORTANT,
                "Ignored": STATUS_IGNORED,
            },
        }
        super().__init__(
            bot,
            {
                "✅": "Completed",
                "👍": "Approved",
                "❌": "Ignored",
                "🔄": "Unmarked",
            },
            command_config,
            color_config,
            " ✅ Complete • 👍 Approve • ❌ Ignore • 🔄 Reset",
        )
        self.MODAL_CONFIGS = {
            "button_modal": {
                "ephemeral": False,
                "button_label": "Open Survey",
                "button_style": ButtonStyle.success,
                "message_prompt": "📝 Ready to submit a feature request? Click the button below!",
                "modal": {
                    "title": "Feature Request Form",
                    "fields": [
                        {
                            "label": "Feature Title",
                            "placeholder": "Brief description of the feature",
                            "style": TextStyle.short,
                            "required": True,
                            "max_length": 100,
                        },
                        {
                            "label": "Feature Description",
                            "placeholder": "Please describe the feature you'd like"
                            "to see in detail...",
                            "style": TextStyle.paragraph,
                            "required": True,
                            "max_length": 1000,
                        },
                    ],
                },
            }
        }


async def setup(bot: commands.Bot) -> None:
    """Set up the Feedback cog."""
    await bot.add_cog(FeatureRequestCog(bot))
