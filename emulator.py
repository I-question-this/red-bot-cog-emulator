from collections import namedtuple
import discord
from discord.embeds import EmptyEmbed
import logging
import os
from pyboy import PyBoy

from redbot.core import checks, commands, Config
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.menus import (
    DEFAULT_CONTROLS,
    close_menu,
    menu,
    next_page,
    prev_page,
    start_adding_reactions,
)
from redbot.core.utils.predicates import MessagePredicate, ReactionPredicate

_ = Translator("Emulator", __file__)

log = logging.getLogger("red.emulator")

_DEFAULT_GLOBAL = {
    "localpath": None,
    "gamedefs": []
}

GameDefinition=namedtuple("GameDefinition", ["name", "bootROM", "gameROM"])


class Emulator(commands.Cog):
    """Emulator cog
    Allows users to play emulators together.
    """

    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot
        self._conf = Config.get_conf(None, 1919191991919191, cog_name=f"{self.__class__.__name__}", force_registration=True)
        self._conf.register_global(**_DEFAULT_GLOBAL)


    @commands.group()
    @checks.is_owner()
    async def game(self, ctx: commands.Context):
        """Game commands"""


    @game.command(name="list")
    async def game_list(self, ctx: commands.Context):
        """List available ROMs"""
        info_msg = "```\ngb\n"
        for name, path in [("boots", await self.boots_path()), ("games", await self.games_path())]:
            if not os.path.exists(path):
                info_msg += f"|__ {name} :negative_squared_cross_mark: \n"
            else:
                info_msg += f"|__ {name} \n"
                items = list(os.listdir(path))
                if len(items) == 0:
                    info_msg += f"\t|__ <NOTHING> \n"
                else:
                    for item in items: 
                        info_msg += f"\t|__ {item} \n"
        info_msg += "```" 
        # Translate it
        info_msg = _(info_msg)


        await self._embed_msg(ctx, title=_("Available ROMs"), description=info_msg)


    # Path Related Functions
    async def gb_path(self):
        return os.path.join(await self._conf.localpath(), "gb")


    async def boots_path(self):
        return os.path.join(await self.gb_path(), "boots")


    async def games_path(self):
        return os.path.join(await self.gb_path(), "games")


    async def saves_path(self):
        return os.path.join(await self.gb_path(), "saves")


    @commands.command()
    @checks.is_owner()
    async def localpath(self, ctx: commands.Context, local_path=None):
        """Sets the path to look for ROMs
        Leave blank to reset to the default.
        """
        if not local_path:
            await self._conf.localpath.set(str(cog_data_path()))
            return await self._embed_msg(
                ctx,
                title=_("Setting Changed"),
                description=_(f"The localtracks path location has been reset to {cog_data_path(raw_name='Emulator').absolute()}")
            )

        info_msg = _(
            "This setting is only for bot owners to set a localtracks folder location "
            "In the example below, the full path for 'ParentDirectory' "
            "must be passed to this command.\n"
            "The path must not contain spaces.\n"
            "```\n"
            "ParentDirectory\n"
            "  |__ gb  (folder)\n"
            "      |__ boots  (folder)\n"
            "      |__ games  (folder)\n"
            "      |__ saves  (folder)\n"
            "```\n"
            "The folder path given to this command must contain the gb folder.\n"
        )
        info = await ctx.maybe_send_embed(info_msg)

        start_adding_reactions(info, ReactionPredicate.YES_OR_NO_EMOJIS)
        pred = ReactionPredicate.yes_or_no(info, ctx.author)
        await ctx.bot.wait_for("reaction_add", check=pred)

        # If user said no
        if not pred.result:
            with contextlib.suppress(discord.HTTPException):
                await info.delete()
            return
        # Check that the path exists
        if not os.path.isdir(local_path):
            return await self._embed_msg(
                ctx,
                title=_("Invalid Path"),
                description=_(f"{local_path} does not seem like a valid path.")
            )
        # It exists, so we set it.
        await self._conf.localpath.set(local_path)

        if not os.path.exists(await self.gb_path()):
            warn_msg = _(
                    f"`{gb_path}` does not exist. "
                    "The path will still be saved, but please check the path and "
                    "create a gb folder in `{localfolder}` before attempting "
                    "to play games."
                )
            await self._embed_msg(ctx, title=_("Invalid Environment"), description=warn_msg)
        else:
            for subfolder in [await self.boots_path(), await self.games_path(), await self.saves_path()]:
                if not os.path.exists(subfolder):
                    os.mkdir(subfolder)

        return await self._embed_msg(
                ctx,
                title=_("Setting Changed"),
                description=_(f"The ROMs path location has been set to {local_path}")
            )


    async def _embed_msg(self, ctx: commands.Context, **kwargs):
        colour = kwargs.get("colour") or kwargs.get("color") or await self.bot.get_embed_color(ctx)
        error = kwargs.get("error", False)
        success = kwargs.get("success", False)
        title = kwargs.get("title", EmptyEmbed) or EmptyEmbed
        _type = kwargs.get("type", "rich") or "rich"
        url = kwargs.get("url", EmptyEmbed) or EmptyEmbed
        description = kwargs.get("description", EmptyEmbed) or EmptyEmbed
        timestamp = kwargs.get("timestamp")
        footer = kwargs.get("footer")
        thumbnail = kwargs.get("thumbnail")
        contents = dict(title=title, type=_type, url=url, description=description)
        embed = kwargs.get("embed").to_dict() if hasattr(kwargs.get("embed"), "to_dict") else {}
        colour = embed.get("color") if embed.get("color") else colour
        contents.update(embed)
        if timestamp and isinstance(timestamp, datetime.datetime):
            contents["timestamp"] = timestamp
        embed = discord.Embed.from_dict(contents)
        embed.color = colour
        if footer:
            embed.set_footer(text=footer)
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        return await ctx.send(embed=embed)
