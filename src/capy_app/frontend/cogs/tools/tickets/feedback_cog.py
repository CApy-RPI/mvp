"""Feedback command cog.

This module handles feedback submissions through a modal interface.
Feedback is sent to a designated channel for developer review.
"""

from discord import ButtonStyle, TextStyle
from discord.ext import commands
from frontend.config_colors import (
    STATUS_IGNORED,
    STATUS_INFO,
    STATUS_RESOLVED,
)

from config import settings

from .ticket_base import TicketBase


class FeedbackCog(TicketBase):
    def __init__(self, bot):
        command_config = {
            "cmd_name": "feedback",
            "cmd_name_verbose": "Feedback Report",
            "cmd_emoji": "📝",
            "description": "Provide general feedback",
            "request_channel_id": settings.TICKET_FEEDBACK_CHANNEL_ID,
        }
        color_config = {
            "unmarked_color": STATUS_INFO,
            "marked_colors": {
                "Acknowledged": STATUS_RESOLVED,
                "Ignored": STATUS_IGNORED,
            },
        }
        super().__init__(
            bot,
            {
                "✅": "Acknowledged",
                "❌": "Ignored",
                "🔄": "Unmarked",
            },
            command_config,
            color_config,
            " ✅ Acknowledge • ❌ Ignore • 🔄 Reset",
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
                            "label": "Feedback Title",
                            "placeholder": "Brief summary of your feedback",
                            "style": TextStyle.short,
                            "required": True,
                            "max_length": 100,
                        },
                        {
                            "label": "Feedback Description",
                            "placeholder": "Please provide your detailed feedback...",
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
    await bot.add_cog(FeedbackCog(bot))
