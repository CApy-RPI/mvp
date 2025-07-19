#! turn into ABC
from abc import ABC, abstractmethod

from typing import Dict, Any

import discord
from discord.ext import commands
from discord import app_commands, TextChannel
from discord import Color

import logging

from config import settings
from frontend.interactions.bases.modal_base import (
    ButtonDynamicModalView,
)
from frontend.config_colors import (
    STATUS_ERROR,
)


class TicketBase(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
        status_emoji: Dict[str, str],
        cmd_name: str,
        cmd_name_verbose: str,
        cmd_emoji: str,
        description,
        request_channel_id,
        unmarked_color: Color,
        marked_colors: Dict[str, Color],
        reaction_footer,
    ) -> None:
        self.bot = bot
        self.logger = logging.getLogger(f"discord.cog.{self.__class__.__name__.lower()}")

        self.status_emoji: Dict[str, str] = status_emoji
        self.cmd_name: str = cmd_name
        self.cmd_name_verbose: str = cmd_name_verbose
        self.cmd_emoji: str = cmd_emoji

        self.MODAL_CONFIGS: Dict[Any, Any] = {}

        self.ticket.name = self.cmd_name
        self.ticket.description = description

        self.request_channel_id: int = request_channel_id

        self.unmarked_color = unmarked_color
        self.marked_colors = marked_colors
        self.reaction_footer = reaction_footer

    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command()
    async def ticket(self, interaction: discord.Interaction) -> None:

        try:
            modal = ButtonDynamicModalView(**self.MODAL_CONFIGS["button_modal"])
            values, message = await modal.initiate_from_interaction(
                interaction, prompt="Click below to start the survey!"
            )

            if not values or not message or len(values.items()) != 2:
                self.logger.warning(
                    f"{self.cmd_name_verbose} missing required fields from user {interaction.user.id}"
                )

            channel = self.bot.get_channel(self.request_channel_id)

            if not channel:
                self.logger.error(f"{self.cmd_name_verbose} channel not found")
                await interaction.followup.send(
                    f"❌ {self.cmd_name_verbose} channel not configured. Please contact an administrator.",
                    ephemeral=True,
                )
                return
            if channel is not TextChannel:
                self.logger.error(
                    f"{self.request_channel_id} for {self.cmd_name_verbose} tickets is not a Text Channel"
                )
                await interaction.followup.send(
                    "The channel for receiving this type of ticket is invalid due to not being a text channel, please contact the bot administrators.",
                    ephemeral=True,
                )
                return

            embed = discord.Embed(
                title=f"{self.cmd_emoji} {self.cmd_name_verbose}: "
                + values.get(f"{self.cmd_name}_title"),
                description=values.get(f"{self.cmd_name}_description"),
                color=STATUS_ERROR,
            )
            embed.add_field(name="Submitted by", value=interaction.user.mention)

            footer_text: str = "Status: Unmarked | "
            for key, value in self.status_emoji.items():
                footer_text += f"{key} {value} • "
            footer_text.removesuffix(" • ")

            embed.set_footer(text=footer_text)

            message = await channel.send(embed=embed)
            for emoji in self.status_emoji.keys():
                await message.add_reaction(emoji)

            await interaction.followup.send(
                f"{self.cmd_name_verbose} submitted successfully!", ephemeral=True
            )
            self.logger.info(
                f"{self.cmd_name_verbose} '{values.get(f'{self.cmd_name}_title')}' submitted by user {interaction.user.id}"
            )

        except discord.HTTPException as e:
            self.logger.error(f"HTTP error processing {self.cmd_name_verbose}: {str(e)}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"❌ Failed to submit {self.cmd_name_verbose}. Please try again later.",
                    ephemeral=True,
                )

        except Exception as e:
            self.logger.error(f"Error processing {self.cmd_name_verbose}: {str(e)}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An unexpected error occurred. Please try again later.",
                    ephemeral=True,
                )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.channel_id != self.request_channel_id:
            return

        if payload.user_id == self.bot.user.id:  # Ignore bot's own reactions
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
