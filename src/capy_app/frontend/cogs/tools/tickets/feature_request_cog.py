"""Feature request command cog.

This module handles feature request submissions through a modal interface.
Requests are sent to a designated channel for developer review.
"""

from discord.ext import commands
from discord import TextStyle, ButtonStyle

from config import settings
from frontend.config_colors import (
    STATUS_UNMARKED,
    STATUS_IMPORTANT,
    STATUS_RESOLVED,
    STATUS_IGNORED,
)

from .ticket_base import TicketBase


class FeatureRequestCog(TicketBase):
    def __init__(self, bot):
        super().__init__(
            bot,
            {
                "✅": "Completed",
                "👍": "Approved",
                "❌": "Ignored",
                "🔄": "Unmarked",
            },
            "feature",
            "Feature Request",
            "💡",
            "Request a new feature",
            settings.TICKET_FEATURE_REQUEST_CHANNEL_ID,
            STATUS_UNMARKED,
            {
                "Completed": STATUS_RESOLVED,
                "Approved": STATUS_IMPORTANT,
                "Ignored": STATUS_IGNORED,
            },
            " ✅ Complete • 👍 Approve • ❌ Ignore • 🔄 Reset",
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
                            "label": "Feature Title",
                            "placeholder": "Brief description of the feature",
                            "style": TextStyle.short,
                            "required": True,
                            "max_length": 100,
                        },
                        {
                            "label": "Feature Description",
                            "placeholder": "Please describe the feature you'd like to see in detail...",
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
