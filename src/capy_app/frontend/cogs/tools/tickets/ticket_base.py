#! turn into ABC

import logging
from typing import Any

import discord
from discord import TextChannel, app_commands
from discord.ext import commands
from frontend.interactions.bases.modal_base import (
    ButtonDynamicModalView,
)

from config import settings

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

    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command()
    async def ticket(self, interaction: discord.Interaction) -> None:
        try:
            modal = ButtonDynamicModalView(**self.MODAL_CONFIGS["button_modal"])
            values, message = await modal.initiate_from_interaction(
                interaction, prompt=self.MODAL_CONFIGS["button_modal"]["message_prompt"]
            )

            if not values or not message or len(values.items()) != REQUIRED_FIELD_COUNT:
                self.logger.warning(
                    f"{self.cmd_name_verbose} missing required fields from user "
                    f"{interaction.user.id}"
                )

            channel = self.bot.get_channel(self.request_channel_id)

            if not channel:
                self.logger.error(f"{self.cmd_name_verbose} channel not found")
                error_embed = discord.Embed(
                    title="❌ Configuration Error",
                    description=(
                        f"{self.cmd_name_verbose} channel not configured. "
                        "Please contact an administrator."
                    ),
                    color=STATUS_ERROR,
                )
                await interaction.followup.send(
                    embed=error_embed,
                    ephemeral=True,
                )
                return
            if not isinstance(channel, TextChannel):
                self.logger.error(
                    f"{self.request_channel_id} for {self.cmd_name_verbose} "
                    "tickets is not a Text Channel"
                )
                error_embed = discord.Embed(
                    title="❌ Channel Error",
                    description=(
                        "The channel for receiving this type of ticket is invalid "
                        "due to not being a text channel, please contact the bot "
                        "administrators."
                    ),
                    color=STATUS_ERROR,
                )
                await interaction.followup.send(
                    embed=error_embed,
                    ephemeral=True,
                )
                return

            embed = discord.Embed(
                title=(
                    f"{self.cmd_emoji} {self.cmd_name_verbose}: "
                    + values.get(f"{self.cmd_name}_title")
                ),
                description=values.get(f"{self.cmd_name}_description"),
                color=self.unmarked_color,
            )
            embed.add_field(name="Submitted by", value=interaction.user.mention)

            footer_text: str = "Status: Unmarked | "
            for key, value in self.status_emoji.items():
                footer_text += f"{key} {value} • "
            footer_text = footer_text.removesuffix(" • ")

            embed.set_footer(text=footer_text)

            message = await channel.send(embed=embed)
            for emoji in self.status_emoji:
                await message.add_reaction(emoji)

            await interaction.followup.send(
                f"{self.cmd_name_verbose} submitted successfully!", ephemeral=True
            )
            self.logger.info(
                f"{self.cmd_name_verbose} "
                f"'{values.get(f'{self.cmd_name}_title')}' submitted by user "
                f"{interaction.user.id}"
            )

        except discord.HTTPException as e:
            self.logger.error(f"HTTP error processing {self.cmd_name_verbose}: {e!s}")
            if not interaction.response.is_done():
                error_embed = discord.Embed(
                    title="❌ Submission Failed",
                    description=(
                        f"Failed to submit {self.cmd_name_verbose}. Please try again later."
                    ),
                    color=STATUS_ERROR,
                )
                await interaction.response.send_message(
                    embed=error_embed,
                    ephemeral=True,
                )

        except Exception as e:
            self.logger.error(f"Error processing {self.cmd_name_verbose}: {e!s}")
            if not interaction.response.is_done():
                error_embed = discord.Embed(
                    title="❌ Unexpected Error",
                    description="An unexpected error occurred. Please try again later.",
                    color=STATUS_ERROR,
                )
                await interaction.response.send_message(
                    embed=error_embed,
                    ephemeral=True,
                )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.channel_id != self.request_channel_id:
            return

        # Ignore bot's own reactions
        if payload.user_id == self.bot.user.id:
            return

        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        if not message.embeds or not message.embeds[0].title.startswith(
            f"{self.cmd_emoji} {self.cmd_name_verbose}:"
        ):
            return

        emoji = str(payload.emoji)
        if emoji not in self.status_emoji:
            return

        # Remove the user's reaction immediately
        if not payload.member:
            self.logger.error(f"Member of payload {payload.message_id} is NoneType")
            return

        await message.remove_reaction(payload.emoji, payload.member)

        embed = message.embeds[0]
        status = self.status_emoji[emoji]

        if status == "Unmarked":
            embed.colour = self.unmarked_color
        else:
            embed.colour = self.marked_colors[status]

        embed.set_footer(text=f"Status: {status} | {self.reaction_footer}")
        await message.edit(embed=embed)
