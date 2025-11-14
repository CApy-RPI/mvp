from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class CommandUsage:
    """
    A class representing the usage statistics of one command
    """

    # How many times the command was used
    uses: int = field(default=0)
    # How many usages were by server administrators
    admin_uses: int = field(default=0)
    # How many usages were by CApy developers
    dev_uses: int = field(default=0)


@dataclass
class Statistics:
    """
    A class representing the collected statistics of the bot
    """

    # The usage statistics for all commands
    command_usages: defaultdict[str, CommandUsage] = field(default_factory=lambda: defaultdict(CommandUsage))
