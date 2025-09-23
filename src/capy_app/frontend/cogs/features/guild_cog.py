"""Guild settings management cog."""

import logging

import discord
from backend.db.database import Database
from backend.db.documents.guild import GuildChannels, GuildRoles
from discord import app_commands
from discord.ext import commands
from frontend import config_colors as colors
from frontend.cogs.features.guild_config import ConfigConstructor
from frontend.cogs.handlers.guild_handler_cog import GuildHandlerCog
from frontend.interactions.bases.button_base import ConfirmDeleteView
from frontend.interactions.bases.dropdown_base import DynamicDropdownView

from config import settings


@app_commands.guild_only()
class GuildCog(commands.Cog):
    """Server configuration management."""

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot
        self.logger = logging.getLogger(f"discord.cog.{self.__class__.__name__.lower()}")
        self.config = ConfigConstructor()

    async def _create_dropdowns(self, setting_type: str, guild: discord.Guild):
        """Create dropdowns based on the setting type."""
        if setting_type == "channels":
            return await self.config.create_channel_dropdown(guild)
        return await self.config.create_role_dropdown(guild)

    def _mention(self, value: int | None, kind: str) -> str:
        """Return a formatted mention string for channels or roles."""
        if not value:
            return "Not Set"
        return f"<#{value}>" if kind == "channel" else f"<@&{value}>"

    def _build_settings_embed(self, guild_data) -> discord.Embed:
        """Construct the settings embed for channels and roles."""
        embed = discord.Embed(title="Server Settings", color=colors.GUILD)

        channel_text = "\n".join(
            f"{prompt['label']}: {self._mention(getattr(guild_data.channels, name), 'channel')}"
            for name, prompt in self.config.get_channel_prompts().items()
        )
        embed.add_field(
            name="Channels",
            value=channel_text or "No channels configured",
            inline=False,
        )

        role_text = "\n".join(
            f"{prompt['label']}: {self._mention(getattr(guild_data.roles, name), 'role')}"
            for name, prompt in self.config.get_role_prompts().items()
        )
        embed.add_field(name="Roles", value=role_text or "No roles configured", inline=False)

        return embed

    async def _respond(
        self,
        interaction: discord.Interaction,
        message: discord.Message | None,
        *,
        content: str | None = None,
        embed: discord.Embed | None = None,
    ) -> None:
        """Send a response or edit an existing message based on provided args."""
        if message:
            await message.edit(content=content, embed=embed, view=None)
            return
        if embed is not None:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(content or "", ephemeral=True)

    async def _verify_guild_access(
        self, interaction: discord.Interaction, require_manage: bool = False
    ) -> tuple[bool, str]:
        """Verify guild access and permissions."""
        self.logger.debug(
            "verify_access: user=%s guild=%s require_manage=%s",
            getattr(interaction.user, "id", None),
            getattr(interaction.guild, "id", None),
            require_manage,
        )
        if not isinstance(interaction.guild, discord.Guild):
            self.logger.info("verify_access: failed (not in guild)")
            return False, "This command can only be used in a server."

        if require_manage and not interaction.user.guild_permissions.manage_guild:
            self.logger.info("verify_access: failed (missing Manage Server)")
            return False, "You need 'Manage Server' permission to modify settings."

        guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
        if not guild_data:
            self.logger.warning("verify_access: failed (no guild_data)")
            return False, "Failed to access guild settings."

        self.logger.debug("verify_access: ok")
        return True, ""

    async def _process_settings_selection(
        self, interaction: discord.Interaction
    ) -> tuple[str | None, discord.Message | None]:
        """Process settings type selection."""
        settings_view = DynamicDropdownView(**self.config.get_settings_type_dropdown())
        selections, message = await settings_view.initiate_from_interaction(
            interaction, "Select what you'd like to edit:"
        )

        if not selections or "settings_type" not in selections:
            self.logger.info(
                "settings_selection: no selection (user=%s guild=%s)",
                getattr(interaction.user, "id", None),
                getattr(interaction.guild, "id", None),
            )
            return None, None

        chosen = selections["settings_type"][0]
        self.logger.info(
            "settings_selection: chosen=%s (user=%s guild=%s)",
            chosen,
            getattr(interaction.user, "id", None),
            getattr(interaction.guild, "id", None),
        )
        self.logger.debug("settings_selection_end")
        return chosen, message

    async def _process_configuration(
        self, setting_type: str, message: discord.Message, guild: discord.Guild
    ) -> dict[str, int | None] | None:
        """Process configuration selection."""
        self.logger.debug("config_start: type=%s guild=%s", setting_type, getattr(guild, "id", None))
        dropdowns = await self._create_dropdowns(setting_type, guild)

        config_view = DynamicDropdownView(dropdowns=dropdowns, **self.config.get_config_view_settings())

        selections, message = await config_view.initiate_from_message(
            message, f"Select {setting_type} for each category:"
        )

        if not selections:
            await message.edit(content="Configuration cancelled.", view=None)
            self.logger.info(
                "config_cancelled: type=%s guild=%s",
                setting_type,
                getattr(guild, "id", None),
            )
            self.logger.debug("config_end")
            return None

        updates = {
            f"{category}s__{name}": int(values[0]) if values else None
            for key, values in selections.items()
            for category, name in [key.split("_")]
        }
        self.logger.info(
            "config_selected: type=%s items=%d guild=%s",
            setting_type,
            len(updates),
            getattr(guild, "id", None),
        )
        self.logger.debug("config_end")
        return updates

    @app_commands.command(name="server", description="Manage server settings")
    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.describe(action="The action to perform with server settings")
    @app_commands.choices(action=[app_commands.Choice(name=n, value=n) for n in ["show", "edit", "clear"]])
    async def server(self, interaction: discord.Interaction, action: str) -> None:
        """Handle server setting actions."""
        self.logger.info(
            "/server invoked: action=%s user=%s guild=%s",
            action,
            getattr(interaction.user, "id", None),
            getattr(interaction.guild, "id", None),
        )
        access_ok, error_msg = await self._verify_guild_access(
            interaction, require_manage=(action in ["edit", "clear"])
        )
        # if not access_ok:
        #     await interaction.edit_original_response(content=error_msg)
        #     return

        try:
            guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
            if action == "show":
                await self.show_settings(interaction)
            elif action == "edit":
                await self.edit_settings(interaction)
            elif action == "clear":
                await self.clear_settings(interaction, guild_data)
            else:
                await interaction.edit_original_response(content=f"Unknown action: {action}")
                self.logger.warning(
                    "/server unknown action: action=%s user=%s guild=%s",
                    action,
                    getattr(interaction.user, "id", None),
                    getattr(interaction.guild, "id", None),
                )
                return

            self.logger.info(
                "/server completed: action=%s user=%s guild=%s",
                action,
                getattr(interaction.user, "id", None),
                getattr(interaction.guild, "id", None),
            )

        except Exception as e:
            self.logger.error(f"Failed to handle server action {action}: {e}")
            await interaction.edit_original_response(content=f"An error occurred while performing {action}.")

    async def show_settings(self, interaction: discord.Interaction, message: discord.Message = None) -> None:
        """Display current server settings."""
        self.logger.debug(
            "show_settings: user=%s guild=%s",
            getattr(interaction.user, "id", None),
            getattr(interaction.guild, "id", None),
        )
        if not isinstance(interaction.guild, discord.Guild):
            raise TypeError("Interaction must be in a guild.")

        guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
        if not guild_data:
            await self._respond(interaction, message, content="No settings configured.")
            self.logger.info("show_settings: no guild_data")
            return

        embed = self._build_settings_embed(guild_data)
        await self._respond(interaction, message, embed=embed)
        self.logger.debug("show_settings: sent embed")

    async def edit_settings(self, interaction: discord.Interaction) -> None:
        """Edit server settings using the new dropdown framework."""
        self.logger.info(
            "edit_settings: start user=%s guild=%s",
            getattr(interaction.user, "id", None),
            getattr(interaction.guild, "id", None),
        )
        if not isinstance(interaction.guild, discord.Guild):
            raise TypeError("Interaction must be in a guild.")

        message = None
        try:
            message = await self._edit_settings_flow(interaction)
            if message is None:
                self.logger.info("edit_settings: cancelled or no changes")
                return
            await self.show_settings(interaction, message)
            self.logger.info("edit_settings: completed")

        except Exception as e:
            self.logger.error(f"Error during settings edit: {e}")
            error_msg = "An error occurred during settings configuration."
            if message:
                await message.edit(content=error_msg, view=None)
            else:
                await interaction.followup.send(error_msg, view=None)

    async def _edit_settings_flow(self, interaction: discord.Interaction) -> discord.Message | None:
        """Inner flow for editing settings, returns the working message or None."""
        self.logger.debug("_edit_settings_flow: start")
        setting_type, message = await self._process_settings_selection(interaction)
        if not setting_type or not message:
            self.logger.info("_edit_settings_flow: no setting_type/message")
            return None

        updates = await self._process_configuration(setting_type, message, interaction.guild)
        if not updates:
            self.logger.info("_edit_settings_flow: no updates")
            return None

        guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
        if not guild_data:
            await message.edit(content="Failed to access guild data.", view=None)
            self.logger.warning("_edit_settings_flow: ensure_guild_exists failed")
            return None

        Database.update_document(guild_data, updates)
        self.logger.info(
            "_edit_settings_flow: updated %d fields for guild=%s",
            len(updates),
            getattr(interaction.guild, "id", None),
        )
        return message

    async def clear_settings(self, interaction: discord.Interaction, guild_data) -> None:
        """Clear all server settings."""
        self.logger.info(
            "clear_settings: confirm prompt user=%s guild=%s",
            getattr(interaction.user, "id", None),
            getattr(interaction.guild, "id", None),
        )
        view = ConfirmDeleteView()
        value, message = await view.initiate_from_interaction(
            interaction,
            self.config.get_clear_settings_prompt(),
        )

        if value:
            # Clear all settings by resetting embedded documents to defaults
            updates = {
                "channels": GuildChannels(),
                "roles": GuildRoles(),
            }
            Database.update_document(guild_data, updates)
            if message:
                await message.edit(content="Server settings cleared.", view=None)
            else:
                await interaction.followup.send("Server settings cleared.", ephemeral=True)
            self.logger.info("clear_settings: cleared")
        else:
            self.logger.info("clear_settings: cancelled")


async def setup(bot: commands.Bot) -> None:
    """Set up the Guild cog."""
    await bot.add_cog(GuildCog(bot))
