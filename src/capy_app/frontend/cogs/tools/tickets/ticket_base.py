#! turn into ABC

import logging
from typing import Any, cast

import discord
from discord import TextChannel, app_commands
from discord.ext import commands
from frontend.interactions.bases.modal_base import ButtonDynamicModalView

from config import settings

from ....config_colors import STATUS_ERROR

REQUIRED_FIELD_COUNT = 2


class TicketBase(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
        status_emoji: dict[str, str],
        command_config: dict[str, Any],
        color_config: dict[str, Any],
        reaction_footer,
    ) -> None:
        self.bot = bot
        self.logger = logging.getLogger(f"discord.cog.{self.__class__.__name__.lower()}")

        self.status_emoji: dict[str, str] = status_emoji
        self.cmd_name: str = command_config["cmd_name"]
        self.cmd_name_verbose: str = command_config["cmd_name_verbose"]
        self.cmd_emoji: str = command_config["cmd_emoji"]

        self.MODAL_CONFIGS: dict[Any, Any] = {}

        self.ticket.name = self.cmd_name
        self.ticket.description = command_config["description"]

        self.request_channel_id: int = command_config["request_channel_id"]

        self.unmarked_color = color_config["unmarked_color"]
        self.marked_colors = color_config["marked_colors"]
        self.reaction_footer = reaction_footer

    # Helper methods to reduce complexity
    async def _send_followup_error(self, interaction: discord.Interaction, title: str, description: str) -> None:
        error_embed = discord.Embed(title=title, description=description, color=STATUS_ERROR)
        await interaction.followup.send(embed=error_embed, ephemeral=True)

    async def _validate_and_get_text_channel(self, interaction: discord.Interaction) -> TextChannel | None:
        """Validate configured channel and return it if it's a TextChannel, otherwise send an error and return None."""
        channel = self.bot.get_channel(self.request_channel_id)
        if not channel:
            self.logger.error(f"{self.cmd_name_verbose} channel not found")
            await self._send_followup_error(
                interaction,
                "❌ Configuration Error",
                f"{self.cmd_name_verbose} channel not configured. Please contact an administrator.",
            )
            return None
        if not isinstance(channel, TextChannel):
            self.logger.error(f"{self.request_channel_id} for {self.cmd_name_verbose} tickets is not a Text Channel")
            await self._send_followup_error(
                interaction,
                "❌ Channel Error",
                (
                    "The channel for receiving this type of ticket is invalid "
                    "due to not being a text channel, please contact the bot "
                    "administrators."
                ),
            )
            return None
        return channel

    def _build_footer_text(self) -> str:
        footer_text = "Status: Unmarked | "
        for key, value in self.status_emoji.items():
            footer_text += f"{key} {value} • "
        return footer_text.removesuffix(" • ")

    def _build_ticket_embed(self, values: dict[str, Any], interaction: discord.Interaction) -> discord.Embed:
        title_value = cast(str, values.get(f"{self.cmd_name}_title", ""))
        embed = discord.Embed(
            title=f"{self.cmd_emoji} {self.cmd_name_verbose}: {title_value}",
            description=values.get(f"{self.cmd_name}_description"),
            color=self.unmarked_color,
        )
        embed.add_field(name="Submitted by", value=interaction.user.mention)
        embed.set_footer(text=self._build_footer_text())
        return embed

    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command()
    async def ticket(self, interaction: discord.Interaction) -> None:
        try:
            await self._process_ticket(interaction)
        except discord.HTTPException as e:
            self.logger.error(f"HTTP error processing {self.cmd_name_verbose}: {e!s}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="❌ Submission Failed",
                        description=f"Failed to submit {self.cmd_name_verbose}. Please try again later.",
                        color=STATUS_ERROR,
                    ),
                    ephemeral=True,
                )
        except Exception as e:
            self.logger.error(f"Error processing {self.cmd_name_verbose}: {e!s}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="❌ Unexpected Error",
                        description="An unexpected error occurred. Please try again later.",
                        color=STATUS_ERROR,
                    ),
                    ephemeral=True,
                )

    async def _process_ticket(self, interaction: discord.Interaction) -> None:
        modal = ButtonDynamicModalView(**self.MODAL_CONFIGS["button_modal"])
        values, message = await modal.initiate_from_interaction(
            interaction, prompt=self.MODAL_CONFIGS["button_modal"]["message_prompt"]
        )

        if not values or not message or len(values.items()) != REQUIRED_FIELD_COUNT:
            self.logger.warning(f"{self.cmd_name_verbose} missing required fields from user {interaction.user.id}")

        channel = await self._validate_and_get_text_channel(interaction)
        if channel is None:
            return

        embed = self._build_ticket_embed(values, interaction)

        message = await channel.send(embed=embed)
        for emoji in self.status_emoji:
            await message.add_reaction(emoji)

        await interaction.followup.send(f"{self.cmd_name_verbose} submitted successfully!", ephemeral=True)
        self.logger.info(
            f"{self.cmd_name_verbose} '{values.get(f'{self.cmd_name}_title')}' submitted by user {interaction.user.id}"
        )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.channel_id != self.request_channel_id:
            return
        await self._process_reaction(payload)

    async def _process_reaction(self, payload: discord.RawReactionActionEvent) -> None:
        # Ignore bot's own reactions
        bot_user = self.bot.user
        if bot_user is None or payload.user_id == bot_user.id:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not isinstance(channel, TextChannel):
            return
        message = await channel.fetch_message(payload.message_id)

        if not message.embeds:
            return
        title = message.embeds[0].title
        if title is None or not title.startswith(f"{self.cmd_emoji} {self.cmd_name_verbose}:"):
            return

        emoji = str(payload.emoji)
        if emoji not in self.status_emoji:
            return

        if not payload.member:
            self.logger.error(f"Member of payload {payload.message_id} is NoneType")
            return

        await message.remove_reaction(payload.emoji, payload.member)

        embed = message.embeds[0]
        status = self.status_emoji[emoji]
        embed.colour = self.unmarked_color if status == "Unmarked" else self.marked_colors[status]
        embed.set_footer(text=f"Status: {status} | {self.reaction_footer}")
        await message.edit(embed=embed)
