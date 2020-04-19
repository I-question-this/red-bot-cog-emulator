import discord
import logging

from pyboy import PyBoy

from redbot.core import commands, Config
from redbot.core.bot import Red

log = logging.getLogger("red.emulator")

_DEFAULT_GLOBAL = {
    "myval": "IT WORKED!"
}

class Emulator(commands.Cog):
    """Emulator cog
    Allows users to play emulators together.
    """

    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot
        self._conf = Config.get_conf(None, 1919191991919191, cog_name=f"{self.__class__.__name__}", force_registration=True)
        self._conf.register_global(**_DEFAULT_GLOBAL)


    @commands.command()
    async def mycom(self, ctx):
        """This does stuff!"""
        # Your code will go here
        await ctx.send(f"{await self._conf.myval()}")

