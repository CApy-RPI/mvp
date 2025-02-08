import discord
import logging
from discord.ext import commands
from discord import app_commands
from frontend.utils.embed_helpers import success_embed, error_embed
from config import settings


class SyncCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )

    async def _sync_commands(self, debug_guild: discord.Guild):
        self.logger.info("Syncing application commands...")
        if debug_guild:
            self.logger.info(f"Connected to debug guild: {debug_guild.name}")
        return await self.bot.tree.sync(guild=debug_guild)

    @commands.command(name="sync", hidden=True)
    @commands.is_owner()
    async def sync(self, ctx: commands.Context):
        try:
            debug_guild = self.bot.get_guild(settings.DEBUG_GUILD_ID)
            synced = await self._sync_commands(debug_guild)

            description = f"✅ Successfully synced {len(synced)} application commands!\nCommands:\n{"\n".join([cmd.name for cmd in synced])}"
            await ctx.send(embed=success_embed("Sync Commands", description))

        except Exception as e:
            self.logger.error(f"Failed to sync commands: {str(e)}")
            await ctx.send(
                embed=error_embed(
                    "Sync Commands", f"❌ Failed to sync commands: {str(e)}"
                )
            )

    @app_commands.is_owner()
    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="sync", description="Sync application commands")
    async def sync_slash(self, interaction: discord.Interaction):
        try:
            debug_guild = self.bot.get_guild(settings.DEBUG_GUILD_ID)
            synced = await self._sync_commands(debug_guild)

            description = f"✅ Successfully synced {len(synced)} application commands!\nCommands:\n{'\n'.join([cmd.name for cmd in synced])}"
            await interaction.response.send_message(
                embed=success_embed("Sync Commands", description)
            )

        except Exception as e:
            self.logger.error(f"Failed to sync commands: {str(e)}")
            await interaction.response.send_message(
                embed=error_embed(
                    "Sync Commands", f"❌ Failed to sync commands: {str(e)}"
                )
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(SyncCog(bot))
