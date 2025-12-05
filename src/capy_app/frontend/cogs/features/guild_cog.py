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
        # If we haven't responded yet, use interaction.response; otherwise use followup
        if not interaction.response.is_done():
            if embed is not None:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(content or "", ephemeral=True)
            return
        # Already responded (e.g., deferred or previous message) -> followup
        if embed is not None:
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(content or "", ephemeral=True)

    async def _verify_guild_access(self, interaction: discord.Interaction) -> tuple[bool, str]:
        """Verify the user is allowed to run server commands.

        Allowed if the invoker either:
        - Has the Discord Administrator permission, or
        - Holds the configured Admin role in guild settings.
        """
        self.logger.debug(
            "verify_access: user=%s guild=%s",
            getattr(interaction.user, "id", None),
            getattr(interaction.guild, "id", None),
        )
        if not isinstance(interaction.guild, discord.Guild):
            self.logger.info("verify_access: failed (not in guild)")
            return False, "This command can only be used in a server."

        guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
        if not guild_data:
            self.logger.warning("verify_access: failed (no guild_data)")
            return False, "Failed to access guild settings."

        # Allow Discord administrators
        try:
            if getattr(interaction.user.guild_permissions, "administrator", False):
                self.logger.debug("verify_access: ok (administrator)")
                return True, ""
        except Exception:
            pass

        # Allow members with the configured Admin role
        admin_role_id_str: str | None = getattr(getattr(guild_data, "roles", None), "admin", None)
        if admin_role_id_str and isinstance(interaction.user, discord.Member):
            try:
                admin_role_id = int(admin_role_id_str)
                if any(r.id == admin_role_id for r in interaction.user.roles):
                    self.logger.debug("verify_access: ok (admin role)")
                    return True, ""
            except Exception:
                # If role id is not an integer or any other issue, treat as not present
                self.logger.debug("verify_access: admin role not valid/assigned")

        self.logger.info(
            "verify_access: failed (no admin permission or role) user=%s guild=%s",
            getattr(interaction.user, "id", None),
            getattr(interaction.guild, "id", None),
        )
        return (
            False,
            "Only administrators or members with the configured Admin role may run server commands.",
        )

    async def _process_settings_selection(
        self,
        interaction: discord.Interaction,
        prompt_text: str = "Select what you'd like to edit:",
        *,
        ephemeral: bool = False,
        message: discord.Message | None = None,
    ) -> tuple[str | None, discord.Message | None]:
        """Process settings type selection."""
        settings_view = DynamicDropdownView(**self.config.get_settings_type_dropdown())
        settings_view._ephemeral = ephemeral
        if message is None:
            selections, message = await settings_view.initiate_from_interaction(interaction, prompt_text)
        else:
            selections, message = await settings_view.initiate_from_message(message, prompt_text)

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
        self,
        setting_type: str,
        message: discord.Message,
        guild: discord.Guild,
        *,
        ephemeral: bool = False,
        header_text: str | None = None,
    ) -> dict[str, int | str | None] | None:
        """Process configuration selection."""
        self.logger.debug("config_start: type=%s guild=%s", setting_type, getattr(guild, "id", None))
        dropdowns = await self._create_dropdowns(setting_type, guild)

        config_view = DynamicDropdownView(dropdowns=dropdowns, **self.config.get_config_view_settings())
        config_view._ephemeral = ephemeral

        prompt = f"Select {setting_type} for each category:"
        if header_text:
            prompt = f"{header_text}\n\n{prompt}"
        selections, message = await config_view.initiate_from_message(message, prompt)

        if not selections:
            await message.edit(content="Configuration cancelled.", view=None)
            self.logger.info(
                "config_cancelled: type=%s guild=%s",
                setting_type,
                getattr(guild, "id", None),
            )
            self.logger.debug("config_end")
            return None

        updates: dict[str, int | str | None] = {
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
    @app_commands.choices(action=[app_commands.Choice(name=n, value=n) for n in ["setup", "show", "edit", "clear"]])
    async def server(self, interaction: discord.Interaction, action: str) -> None:
        """Handle server setting actions."""
        self.logger.info(
            "/server invoked: action=%s user=%s guild=%s",
            action,
            getattr(interaction.user, "id", None),
            getattr(interaction.guild, "id", None),
        )
        access_ok, error_msg = await self._verify_guild_access(interaction)
        if not access_ok:
            if interaction.response.is_done():
                await interaction.edit_original_response(content=error_msg)
            else:
                await interaction.response.send_message(error_msg, ephemeral=True)
            return

        try:
            guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
            if action == "setup":
                await self.setup_flow(interaction)
            elif action == "show":
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

    async def setup_flow(self, interaction: discord.Interaction) -> None:
        """Guided onboarding with ephemeral dropdowns for channels and roles."""
        access_ok, error_msg = await self._verify_guild_access(interaction)
        if not access_ok:
            if interaction.response.is_done():
                await interaction.edit_original_response(content=error_msg)
            else:
                await interaction.response.send_message(error_msg, ephemeral=True)
            return
        intro = (
            "Welcome to Capy — let's get onboarded!\n\n"
            "You'll configure the required channels and roles Capy uses.\n\n"
            "Channels:\n"
            "• Reports — where users submit issues\n"
            "• Announcements — your official broadcast channel\n"
            "• Moderator — private coordination\n\n"
            "Roles:\n"
            "• Visitor — default for newcomers/guests\n"
            "• Member — verified community members\n"
            "• E-Board — leadership/officers\n"
            "• Admin — administrators with Manage Server\n"
            "• Advisor — mentors/advisors\n"
            "• Office Hours — mentors hosting sessions\n\n"
            "Commands:\n"
            "```\n"
            "/server setup  # start guided setup\n"
            "/server edit   # reconfigure settings\n"
            "/server show   # show current settings\n"
            "/server clear  # reset settings (confirmation)\n"
            "```"
        )
        # Present intro with Auto Create / Manual Select buttons
        start_view = SetupStartView(self)
        await interaction.response.send_message(intro, ephemeral=True, view=start_view)
        start_message = await interaction.original_response()
        await start_view.wait()

        if start_view._completed == "auto":
            # Auto path handled in callback
            return

        # Manual path
        setting_type, message = await self._process_settings_selection(
            interaction, intro, ephemeral=True, message=start_message
        )
        if not setting_type or not message:
            return
        updates = await self._process_configuration(
            setting_type, message, interaction.guild, ephemeral=True, header_text=intro
        )
        if not updates:
            return
        guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
        if not guild_data:
            await message.edit(content="Failed to access guild data.", view=None)
            return
        Database.update_document(guild_data, updates)
        # Apply role colors to selected roles in manual flow too
        await self._apply_role_colors(interaction.guild, updates)
        await self.show_settings(interaction, message)

    async def _handle_auto_create(
        self, guild: discord.Guild
    ) -> tuple[dict[str, int | str | None], list[str], list[str]]:
        """Create required channels and roles automatically and return updates and summaries.

        Returns (updates, created_channels, created_roles).
        """
        channel_updates, created_channels = await self._auto_create_channels(guild)
        role_updates, created_roles = await self._auto_create_roles(guild)

        updates: dict[str, int | str | None] = {}
        updates.update(channel_updates)
        updates.update(role_updates)

        return updates, created_channels, created_roles

    async def _auto_create_channels(self, guild: discord.Guild) -> tuple[dict[str, int | None], list[str]]:
        channel_targets = {
            "reports": "reports",
            "announcements": "announcements",
            "moderator": "moderator",
        }
        updates: dict[str, int | None] = {}
        created: list[str] = []
        for key, name in channel_targets.items():
            existing = discord.utils.get(guild.text_channels, name=name)
            if existing is None:
                try:
                    ch = await guild.create_text_channel(name)
                    created.append(f"#{name}")
                    updates[f"channels__{key}"] = ch.id
                except Exception:
                    updates[f"channels__{key}"] = None
            else:
                updates[f"channels__{key}"] = existing.id
        return updates, created

    async def _auto_create_roles(self, guild: discord.Guild) -> tuple[dict[str, str | None], list[str]]:
        role_targets = {
            "visitor": "Visitor",
            "member": "Member",
            "eboard": "E-Board",
            "admin": "Admin",
            "advisor": "Advisor",
            "office_hours": "Office Hours",
        }
        role_colors: dict[str, discord.Color] = {
            "visitor": discord.Color.light_grey(),
            "member": discord.Color.blue(),
            "eboard": discord.Color.gold(),
            "admin": discord.Color.red(),
            "advisor": discord.Color.teal(),
            "office_hours": discord.Color.purple(),
        }
        updates: dict[str, str | None] = {}
        created: list[str] = []
        for key, name in role_targets.items():
            existing = discord.utils.get(guild.roles, name=name)
            if existing is None:
                try:
                    color = role_colors.get(key, discord.Color.default())
                    role = await guild.create_role(name=name, color=color)
                    created.append(f"@{name}")
                    updates[f"roles__{key}"] = str(role.id)
                except Exception:
                    updates[f"roles__{key}"] = None
            else:
                try:
                    desired = role_colors.get(key)
                    if desired and existing.color != desired:
                        await existing.edit(color=desired, reason="Capy setup: apply role color")
                except Exception:
                    pass
                updates[f"roles__{key}"] = str(existing.id)
        return updates, created

    def _build_auto_summary(self, created_channels: list[str], created_roles: list[str]) -> str:
        lines = [
            "Auto creation completed.",
            f"Channels created: {', '.join(created_channels) if created_channels else 'none'}",
            f"Roles created: {', '.join(created_roles) if created_roles else 'none'}",
        ]
        return "\n".join(lines)

    async def _apply_role_colors(self, guild: discord.Guild, updates: dict[str, int | str | None]) -> None:
        """Apply standard colors to selected roles based on role key names.

        Expects updates keys like roles__admin -> role_id (string).
        """
        role_colors: dict[str, discord.Color] = {
            "visitor": discord.Color.light_grey(),
            "member": discord.Color.blue(),
            "eboard": discord.Color.gold(),
            "admin": discord.Color.red(),
            "advisor": discord.Color.teal(),
            "office_hours": discord.Color.purple(),
        }
        for key, value in updates.items():
            if not key.startswith("roles__") or not value:
                continue
            role_key = key.split("__", 1)[1]
            role_id_str = str(value)
            if not role_id_str.isdigit():
                continue
            role = guild.get_role(int(role_id_str))
            if not role:
                continue
            desired = role_colors.get(role_key)
            if not desired:
                continue
            try:
                if role.color != desired:
                    await role.edit(color=desired, reason="Capy setup: apply role color")
            except Exception:
                # Ignore if lacking permissions
                pass

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


class SetupStartView(discord.ui.View):
    def __init__(self, cog: GuildCog) -> None:
        super().__init__(timeout=120)
        self.cog = cog
        self._completed: str | None = None  # "auto" | "manual"

    @discord.ui.button(label="Auto Create", style=discord.ButtonStyle.green)
    async def auto_create(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:  # type: ignore[override]
        self._completed = "auto"
        await interaction.response.defer(ephemeral=True)
        self.stop()
        if not isinstance(interaction.guild, discord.Guild):
            await interaction.followup.send("This must be used in a server.", ephemeral=True)
            return
        updates, created_channels, created_roles = await self.cog._handle_auto_create(interaction.guild)
        guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
        Database.update_document(guild_data, updates)
        await interaction.followup.send(
            self.cog._build_auto_summary(created_channels, created_roles),
            ephemeral=True,
        )
        await self.cog.show_settings(interaction)

    @discord.ui.button(label="Manual Select", style=discord.ButtonStyle.blurple)
    async def manual_select(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:  # type: ignore[override]
        self._completed = "manual"
        await interaction.response.edit_message(view=None)
        self.stop()


async def setup(bot: commands.Bot) -> None:
    """Set up the Guild cog."""
    await bot.add_cog(GuildCog(bot))
