# cogs/help.py - displays all available commands
#              - displays help for a specific command

import discord
from discord.ext import commands
import logging
from frontend.utils import embed_colors as colors


class HelpCog(commands.HelpCommand):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )

    async def send_error_message(self, error):
        """Handles error messages."""
        embed = discord.Embed(
            title="Error",
            description=error,
            color=discord.Color.red(),
        )
        await self.get_destination().send(embed=embed)

    async def send_bot_help(self, mapping):
        """Handles the default help command output."""
        try:
            ctx = self.context
            embed = discord.Embed(
                title="Help",
                description="Available commands",
                color=colors.HELP,
            )
            await ctx.send("Custom Help Command Active!")

            for cog, cmds in mapping.items():
                # Filter visible commands and gather name and help description
                command_list = []
                for cmd in cmds:
                    if cmd.hidden:
                        continue

                    aliases = (
                        f" (aliases: {', '.join(cmd.aliases)})" if cmd.aliases else ""
                    )
                    command_list.append(
                        f"**{cmd.name}**{aliases} - {cmd.help or 'No description provided'}"
                    )

                if command_list:
                    cog_name = cog.qualified_name if cog else "No Category"
                    embed.add_field(
                        name=cog_name, value="\n".join(command_list), inline=False
                    )

            await ctx.send(embed=embed)
        except Exception as e:
            self.logger.error(f"Error occured in send_bot_help {e}")
            await self.send_error_message(
                "There was an error sending the help message."
            )

    async def send_cog_help(self, cog):
        """Handles help for a specific cog."""
        try:
            ctx = self.context
            embed = discord.Embed(
                title=f"{cog.qualified_name} Commands",
                description="Available commands",
                color=colors.HELP,
            )

            # Combine all commands into a single string
            command_descriptions = []
            for command in cog.get_commands():
                if not command.hidden:
                    if isinstance(command, commands.Group):
                        # For group commands, add each subcommand
                        subcommands = [
                            f"**{sub.name}** - {sub.help or 'No description'}"
                            for sub in command.commands
                        ]
                        description = (
                            f"{command.help or 'No description'}\n"
                            + "\n".join(subcommands)
                        )
                        command_descriptions.append(
                            f"**{command.name}**\n{description}"
                        )
                    else:
                        # Add standalone command
                        command_descriptions.append(
                            f"**{command.name}** - {command.help or 'No description'}"
                        )

            # Join all command descriptions with newlines and set it in the embed description
            embed.description = "\n\n".join(command_descriptions)

            await ctx.send(embed=embed)
        except commands.CommandNotFound:
            self.logger.error("Cog is not found!")
            await self.send_error_message("Cog is not found.")
        except commands.MissingPermissions:
            self.logger.error("Missing Permissions!")
            await self.send_error_message(
                "You do not have permission to view this categorie."
            )
        except Exception as e:
            self.logger.error(f"Error displaying help for command '{cog}': {e}")
            await self.send_error_message(
                "There was an error sending the help message."
            )

    async def send_command_help(self, command):
        """Handles help for a specific command."""
        try:
            ctx = self.context
            await ctx.send("Custom Help Command Active!")

            # Add aliases to the description if they exist
            description = command.help or "No description"
            if command.aliases:
                description = f"{description}\n\nAliases: {', '.join(command.aliases)}"

            embed = discord.Embed(
                title=command.name,
                description=description,
                color=colors.HELP,
            )
            await self.context.send(embed=embed)
        except commands.CommandNotFound:
            self.logger.error("Command is not found!")
            await self.send_error_message("Command is not found.")
        except commands.MissingPermissions:
            self.logger.error("Missing Permissions!")
            await self.send_error_message(
                "You do not have permission to view this command."
            )
        except Exception as e:
            self.logger.error(f"Error displaying help for command '{command}': {e}")
            await self.send_error_message(
                "There was an error sending the help message."
            )


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.help_command = HelpCog()  # Assign to bot's help command

    def cog_unload(self):
        self.bot.help_command = (
            commands.DefaultHelpCommand()
        )  # Reset the help command when the cog is unloaded


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
