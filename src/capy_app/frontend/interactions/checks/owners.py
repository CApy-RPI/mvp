import discord


def is_owner():
    def predicate(interaction: discord.Interaction):
        if interaction.user.id == interaction.guild.owner_id:
            return True

    return discord.app_commands.check(predicate)
