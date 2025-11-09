"""Configuration settings for guild management."""

from typing import TypedDict

import discord


class PromptOption(TypedDict):
    """Type definition for prompt options."""

    label: str
    description: str
    required: bool


class ConfigConstructor:
    """Constructs configuration prompts for guild settings."""

    @staticmethod
    def get_channel_prompts() -> dict[str, PromptOption]:
        """Get prompts for channel configuration."""
        return {
            "reports": {
                "label": "Reports Channel",
                "description": (
                    "The text channel where users submit reports or issues. "
                    "Staff will monitor this channel for new submissions."
                ),
                "required": True,
            },
            "announcements": {
                "label": "Announcements Channel",
                "description": (
                    "Official broadcast channel for important updates. Only staff should be able to post here."
                ),
                "required": True,
            },
            "moderator": {
                "label": "Moderator Channel",
                "description": (
                    "Private coordination channel for moderators and admins. Used for internal discussion and alerts."
                ),
                "required": True,
            },
        }

    @staticmethod
    def get_role_prompts() -> dict[str, PromptOption]:
        """Get prompts for role configuration."""
        return {
            "visitor": {
                "label": "Visitor Role",
                "description": ("Default lightweight role for newcomers/guests. Often has minimal permissions."),
                "required": True,
            },
            "member": {
                "label": "Member Role",
                "description": (
                    "Primary role for verified members of the community. Grants access to standard channels."
                ),
                "required": True,
            },
            "eboard": {
                "label": "E-Board Role",
                "description": (
                    "Role for executive/leadership members (officers, leads). May receive additional admin tools."
                ),
                "required": True,
            },
            "admin": {
                "label": "Admin Role",
                "description": (
                    "Top-level administrative role with Manage Server-level capabilities. "
                    "Required for controlling bot configuration."
                ),
                "required": True,
            },
            "advisor": {
                "label": "Advisor Role",
                "description": ("Advisor/mentor role for guidance and oversight."),
                "required": True,
            },
            "office_hours": {
                "label": "Office Hours Role",
                "description": ("Role for members who host office hours or mentoring sessions."),
                "required": True,
            },
        }

    @staticmethod
    def get_settings_type_dropdown() -> dict[str, object]:
        """Get settings type selection dropdown configuration."""
        return {
            "dropdowns": [
                {
                    "custom_id": "settings_type",
                    "placeholder": "Choose what to edit",
                    "min_values": 1,
                    "max_values": 1,
                    "selections": [
                        {
                            "label": "Channels",
                            "value": "channels",
                            "description": "Edit channel settings",
                        },
                        {
                            "label": "Roles",
                            "value": "roles",
                            "description": "Edit role settings",
                        },
                    ],
                }
            ],
            "ephemeral": False,
        }

    @staticmethod
    def get_config_view_settings() -> dict[str, object]:
        """Get configuration view settings."""
        return {
            "ephemeral": False,
            "buttons": (True, True),
        }

    @staticmethod
    def get_clear_settings_prompt() -> str:
        """Get the clear settings confirmation prompt."""
        return "⚠️ Are you sure you want to clear all server settings? This cannot be undone."

    @staticmethod
    def format_dropdown_option(name: str, id_value: int | str, description: str) -> dict[str, str]:
        """Format a dropdown option."""
        return {
            "label": name,
            "value": str(id_value),
            "description": description,
        }

    @staticmethod
    def format_dropdown(
        custom_id: str,
        placeholder: str,
        options: list[dict[str, str]],
        required: bool = False,
    ) -> dict[str, object]:
        """Format a dropdown menu configuration."""
        return {
            "custom_id": custom_id,
            "placeholder": placeholder,
            "min_values": 1 if required else 0,
            "max_values": 1,
            "selections": options,
        }

    @classmethod
    async def create_channel_dropdown(cls, guild: discord.Guild) -> list[dict[str, object]]:
        """Create channel selection options."""
        text_channels = [channel for channel in guild.channels if isinstance(channel, discord.TextChannel)]

        selections = []
        for name, prompt in cls.get_channel_prompts().items():
            options = [
                cls.format_dropdown_option(channel.name, channel.id, f"Select as {prompt['label'].lower()}")
                for channel in text_channels
            ]

            selections.append(
                cls.format_dropdown(
                    f"channel_{name}",
                    f"Select {prompt['label']}",
                    options,
                    prompt["required"],
                )
            )

        return selections

    @classmethod
    async def create_role_dropdown(cls, guild: discord.Guild) -> list[dict[str, object]]:
        """Create role selection options."""
        selections = []
        for name, prompt in cls.get_role_prompts().items():
            options = [
                cls.format_dropdown_option(role.name, role.id, f"Select as {prompt['label'].lower()}")
                for role in guild.roles
                if not role.is_default()
            ]

            selections.append(
                cls.format_dropdown(
                    f"role_{name}",
                    f"Select {prompt['label']}",
                    options,
                    prompt["required"],
                )
            )

        return selections
