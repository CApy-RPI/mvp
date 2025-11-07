import logging
import os
from pathlib import Path
from typing import Any, Literal, cast

import discord
from discord import app_commands
from discord.ext import commands
from frontend import config_colors as colors

from config import settings


class HotswapSelect(discord.ui.Select[discord.ui.View]):
    def __init__(self, cogs: list[str], operation: str, bot: commands.Bot):
        super().__init__(
            placeholder="Select a cog...",
            options=[discord.SelectOption(label=cog.split(".")[-1], value=cog) for cog in cogs],
            min_values=1,
            max_values=1,
        )

        self.bot = bot
        self.operation = operation
        self.logger = logging.getLogger("discord.cog.hotswap")

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.data, dict):
            return

        # Ensure interaction data is indeed a dict and can be indexable
        data = cast(dict[str, Any], interaction.data)
        values = data.get("values", [])
        if not values:
            return

        cog_path = values[0]
        operations = {
            "reload": self.bot.reload_extension,
            "load": self.bot.load_extension,
            "unload": self.bot.unload_extension,
        }

        try:
            await operations[self.operation](cog_path)
            embed = discord.Embed(
                title=f"{self.operation.title()}",
                description=f"✅ Successfully {self.operation}ed `{cog_path}`",
                color=colors.STATUS_RESOLVED,
            )
            self.logger.info(f"{self.operation.title()}ed cog: {cog_path}")
        except Exception as e:
            embed = discord.Embed(
                title=f"{self.operation.title()} Error",
                description=f"❌ Failed to {self.operation} `{cog_path}`\n```{e!s}```",
                color=colors.STATUS_ERROR,
            )
            self.logger.error(f"Failed to {self.operation} cog {cog_path}: {e!s}")

        await interaction.response.send_message(embed=embed, ephemeral=True)


class HotswapView(discord.ui.View):
    def __init__(self, cogs: list[str], operation: str, bot: commands.Bot):
        super().__init__()
        self.add_item(HotswapSelect(cogs, operation, bot))


class HotswapCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(f"discord.cog.{self.__class__.__name__.lower()}")
        self.cogs_path = Path(__file__).parent / ".."

    def get_cog_from_path(self, path: os.PathLike[str] | str) -> str | None:
        """Convert a file path to a cog import path."""
        rel_path = os.path.relpath(path, self.cogs_path)
        if rel_path.endswith("_cog.py"):
            # Convert path to import format
            import_path = rel_path.replace(os.path.sep, ".").replace(".py", "")
            return f"frontend.cogs.{import_path}"
        return None

    def get_loaded_cogs(self) -> list[str]:
        """Get list of currently loaded cog paths."""
        return list(self.bot.extensions.keys())

    def get_all_cogs(self) -> list[str]:
        """Get list of all available cog paths."""
        cog_paths = []
        for root, _, files in os.walk(self.cogs_path):
            for file in files:
                if file.endswith("_cog.py"):
                    full_path = Path(root) / file
                    if cog_path := self.get_cog_from_path(full_path):
                        cog_paths.append(cog_path)
        return cog_paths

    def get_unloaded_cogs(self) -> list[str]:
        """Get list of available but unloaded cog paths."""
        loaded_cogs = set(self.get_loaded_cogs())
        all_cogs = set(self.get_all_cogs())
        return list(all_cogs - loaded_cogs)

    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="hotswap", description="Manage cogs (reload/load/unload)")
    @app_commands.checks.has_permissions(administrator=True)
    async def hotswap(
        self,
        interaction: discord.Interaction,
        operation: Literal["reload", "load", "unload"],
    ):
        # Use appropriate cog list based on operation
        cogs = {
            "reload": self.get_loaded_cogs(),
            "load": self.get_unloaded_cogs(),
            "unload": self.get_loaded_cogs(),
        }[operation]

        if not cogs:
            await interaction.response.send_message(f"No cogs available to {operation}!", ephemeral=True)
            return

        view = HotswapView(cogs, operation, self.bot)
        await interaction.response.send_message(f"Select a cog to {operation}:", view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(HotswapCog(bot))
