from datetime import datetime
import discord
from discord.embeds import EmptyEmbed
import logging
import os
from .gameBoy import GameBoy

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
    "gamedefs": [],
    "registeredchannels": [],
    "autosaves": []
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
        self._instances = {}


    # Getting input
    @commands.Cog.listener()
    async def on_message(self, message: discord.message):
        if isinstance(message.channel, discord.abc.PrivateChannel):
            return
        author = message.author
        valid_user = isinstance(author, discord.Member) and not author.bot
        if not valid_user:
            return
        if await self.bot.is_automod_immune(message):
            return

        registeredchannels = await self._conf.registeredchannels()
        for channel_id, def_name in registeredchannels:
            if message.channel.id == channel_id:
                return await self._embed_msg(message.channel, title=_("TEST"),
                        description=_("TEST"))


    async def send_message_to_registered_channels(self, definition_name, **kwargs):
        for channel in await self.filtered_registered_channels(definition_name):
            self._embed_msg(channel, **kwargs)


    # Commands
    @commands.group()
    @commands.guild_only()
    async def guild(self, ctx: commands.Context):
        """Guild commands"""


    @guild.command(name="register")
    async def guild_register(self, ctx: commands.Context, definition_name:str):
        if not await self.does_definition_name_exist(definition_name):
            info_msg = "```\n"
            info_msg += f"{definition_name} does not exist\n"
            info_msg += "```\n"
            return await self._embed_msg(ctx, title=_("Improper Definition Name"),
                    description=_(info_msg))

        registeredchannels = await self._conf.registeredchannels()
        for channel_id, def_name in registeredchannels:
            if ctx.channel.id == channel_id:
                info_msg = "```\n"
                info_msg += f"This channel is already registered to \"{def_name}\"\n"
                info_msg += "```\n"
                return await self._embed_msg(ctx, title=_("Channel Already Register"),
                        description=_(info_msg))

        registeredchannels.append([ctx.channel.id, definition_name])
        await self._conf.registeredchannels.set(registeredchannels)
        info_msg = "```\n"
        info_msg += f"Registered this channel to \"{definition_name}\"\n"
        info_msg += "```\n"
        return await self._embed_msg(ctx, title=_("Channel Registered"),
                description=_(info_msg))


    @guild.command(name="unregister")
    async def guild_unregister(self, ctx: commands.Context):
        registeredchannels = await self._conf.registeredchannels()
        for channel_id, def_name in registeredchannels:
            if ctx.channel.id == channel_id:
                info_msg = "```\n"
                info_msg += f"This channel has been unregistered from \"{def_name}\"\n"
                info_msg += "```\n"
                await self._conf.registeredchannels.set(
                        list(filter(lambda rc: rc[0] != ctx.channel.id, registeredchannels)))
                return await self._embed_msg(ctx, title=_("Channel Unregistered"),
                        description=_(info_msg))

        info_msg = "```\n"
        info_msg += f"This channel isn't registered to anything\n"
        info_msg += "```\n"
        return await self._embed_msg(ctx, title=_("Channel Not Registered"),
                description=_(info_msg))


    @commands.group()
    @checks.is_owner()
    async def game(self, ctx: commands.Context):
        """Game commands"""


    @game.command(name="stop")
    async def game_stop(self, ctx: commands.Context, definition_name: str):
        def_info = await self.definition_name_information(definition_name)
        if def_info is None:
            info_msg = "```\n"
            info_msg += f"{definition_name} does not exist\n"
            info_msg += "```\n"
            return await self._embed_msg(ctx, title=_("Improper Definition Name"),
                    description=_(info_msg))

        # Does an instance acutally exist?
        if self._instances.get(definition_name, None) is None:
            info_msg = "```\n"
            info_msg += f"{definition_name} has no instance running\n"
            info_msg += "```\n"
            return await self._embed_msg(ctx, title=_("Instance Not Running"),
                    description=_(info_msg))
        
        # Is the instance actually running?
        if not self._instances[definition_name].isRunning:
            info_msg = "```\n"
            info_msg += f"{definition_name} has no instance running\n"
            info_msg += "```\n"
            return await self._embed_msg(ctx, title=_("Instance Not Running"),
                    description=_(info_msg))

        # Stop the instance
        self._instances[definition_name].stop()
        del self._instances[definition_name]
        info_msg = "```\n"
        info_msg += f"{definition_name} has been stopped.\n"
        info_msg += "```\n"
        return await self._embed_msg(ctx, title=_("Instance Stopped"),
                description=_(info_msg))


    @game.command(name="start")
    async def game_start(self, ctx: commands.Context, definition_name: str):
        def_info = await self.definition_name_information(definition_name)
        if def_info is None:
            info_msg = "```\n"
            info_msg += f"{definition_name} does not exist\n"
            info_msg += "```\n"
            return await self._embed_msg(ctx, title=_("Improper Definition Name"),
                    description=_(info_msg))

        # Does an instance already exist?
        if self._instances.get(definition_name, None) is None:
            self._instances[definition_name] = GameBoy()
        
        # Is one already running?
        if self._instances[definition_name].isRunning:
            info_msg = "```\n"
            info_msg += f"{definition_name} already has an instance running\n"
            info_msg += "```\n"
            return await self._embed_msg(ctx, title=_("Instance is Already Running"),
                    description=_(info_msg))

        # Perhaps the first time
        if not os.path.exists(await self.saves_definition_dir(definition_name)):
            os.mkdir(await self.saves_definition_dir(definition_name))

        if not os.path.exists(await self.auto_save_dir(definition_name)):
            os.mkdir(await self.auto_save_dir(definition_name))

        if not os.path.exists(await self.named_save_dir(definition_name)):
            os.mkdir(await self.named_save_dir(definition_name))

        if not os.path.exists(await self.screen_shots_save_dir(definition_name)):
            os.mkdir(await self.screen_shots_save_dir(definition_name))

        # Time to start
        self._instances[definition_name].start(
                gameROMPath=await self.gameROM_path(def_info[2]),
                bootROMPath=await self.bootROM_path(def_info[1])
            )

        # Save a screenshot
        screenshot_path = await self.screen_shots_save_path(definition_name, f"{datetime.now()}.gif")
        self._instances[definition_name].makeGIF(screenshot_path)
        return await ctx.send(file=discord.File(screenshot_path))


    @game.command(name="ROMs", aliases=["roms"])
    async def game_roms(self, ctx: commands.Context):
        """List available ROMs"""
        info_msg = "```\ngb\n"
        for name, path in [("boots", await self.boots_dir()), ("games", await self.games_dir())]:
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

        await self._embed_msg(ctx, title=_("Available ROMs"), description=_(info_msg))


    @game.command(name="definitions", aliases=["defs"])
    async def game_definitions(self, ctx: commands.Context):
        """List defined games"""
        info_msg = "```\n"
        if len(await self._conf.gamedefs()) == 0:
            info_msg += "NONE"
        else:
            for definition in await self._conf.gamedefs():
                info_msg += f"{definition[0]}:\n"
                info_msg += f"\t|__Boot ROM: {definition[1]}\n"
                info_msg += f"\t|__Game ROM: {definition[2]}\n"
        info_msg += "```" 
        await self._embed_msg(ctx, title=_("Defined Games"), description=_(info_msg))


    @game.command(name="set")
    async def game_set(self, ctx: commands.Context, name:str, bootROM:str, gameROM:str):
        """Set a defined game"""
        # Check that the ROMs exist
        if not os.path.exists(await self.bootROM_path(bootROM)):
            return await self._embed_msg(
                ctx,
                title=_("Invalid Boot ROM"),
                description=_(f"{bootROM} does not exist.")
            )

        if not os.path.exists(await self.gameROM_path(gameROM)):
            return await self._embed_msg(
                ctx,
                title=_("Invalid Game ROM"),
                description=_(f"{gameROM} does not exist.")
            )

        # Check that this name has not already been used
        gamedefs = await self._conf.gamedefs()
        for definition in gamedefs:
            if definition[0] == name:
                return await self._embed_msg(
                    ctx,
                    title=_("Name Conflict"),
                    description=_(f"{name} already exist as a name.")
                )
        # Set the definition
        gamedefs.append((name, bootROM, gameROM))
        await self._conf.gamedefs.set(gamedefs)
        return await self._embed_msg(
            ctx,
            title=_("Saved Definition"),
            description=_(f"Definition was saved successfully.")
        )


    @game.command(name="delete", aliases=["del"])
    async def game_delete(self, ctx: commands.Context, name:str):
        """Delete a defined game"""
        for definition in await self._conf.gamedefs():
            if definition[0] == name:
                info_msg = _(
                        "Are you sure you want to delete?:\n"
                        "```\n"
                        f"{definition[0]}\n"
                        "```\n"
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
                else:
                    await self._conf.gamedefs.set(list(filter(lambda d: d[0] != name, await self._conf.gamedefs())))
                return await self._embed_msg(
                    ctx,
                    title=_("Deletion Successful"),
                    description=_(f"{name} has been deleted.")
                )

        return await self._embed_msg(
            ctx,
            title=_("No Such Definition"),
            description=_(f"{name} does not exist.")
        )


    # Helper Functions
    async def definition_name_information(self, definition_name: str):
        for definition in await self._conf.gamedefs():
            if definition[0] == definition_name:
                return definition
        return None


    async def does_definition_name_exist(self, definition_name: str):
        return self.definition_name_information(definition_name) is not None


    async def filtered_registered_channel_ids(self, definition_name: str):
        for channel_id, def_name in await self._conf.registeredchannels():
            if def_name == definition_name:
                yield channel_id


    async def filtered_registered_channels(self, definition_name: str):
        for channel_id in await self.filtered_registered_channel_ids(definition_name):
            yield await self.get_channel(channel_id)


    # Path Related Functions
    async def gb_path(self):
        return os.path.join(await self._conf.localpath(), "gb")


    async def boots_dir(self):
        return os.path.join(await self.gb_path(), "boots")


    async def bootROM_path(self, bootROM):
        return os.path.join(await self.boots_dir(), bootROM)


    async def games_dir(self):
        return os.path.join(await self.gb_path(), "games")


    async def gameROM_path(self, gameROM):
        return os.path.join(await self.games_dir(), gameROM)


    async def saves_dir(self):
        return os.path.join(await self.gb_path(), "saves")


    async def saves_definition_dir(self, def_name):
        return os.path.join(await self.saves_dir(), def_name)


    async def auto_save_dir(self, def_name):
        return os.path.join(await self.saves_definition_dir(def_name), "auto")


    async def auto_save_path(self, def_name, save_name):
        return os.path.join(await self.auto_save_dir(def_name), save_name)


    async def named_save_dir(self, def_name):
        return os.path.join(await self.saves_definition_dir(def_name), "named")


    async def named_save_path(self, def_name, save_name):
        return os.path.join(await self.named_save_dir(def_name), save_name)


    async def screen_shots_save_dir(self, def_name):
        return os.path.join(await self.saves_definition_dir(def_name), "screen_shots")


    async def screen_shots_save_path(self, def_name, save_name):
        return os.path.join(await self.screen_shots_save_dir(def_name), save_name)


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
            for subfolder in [await self.boots_dir(), await self.games_dir(), await self.saves_dir()]:
                if not os.path.exists(subfolder):
                    os.mkdir(subfolder)

        return await self._embed_msg(
                ctx,
                title=_("Setting Changed"),
                description=_(f"The ROMs path location has been set to {local_path}")
            )


    @commands.group()
    @checks.is_owner()
    async def saves(self, ctx: commands.Context):
        """Saves commands"""


    @saves.command(name="list")
    async def saves_list(self, ctx: commands.Context, definition_name:str=None):
        info_msg = "```\ngb\n"
        for def_name, bootROM, gameROM in await self._conf.gamedefs():
            if definition_name is not None:
                if def_name != definition_name:
                    continue

            info_msg += f"|__ {def_name} \n"
            for name, path in [("auto", await self.auto_save_dir(def_name)), ("named", await self.named_save_dir(def_name))]:
                info_msg += f"\t|__ {name} \n"
                if not os.path.exists(path):
                    info_msg += f"\t\t|__ <NOTHING> \n"
                else:
                    items = list(os.listdir(path))
                    if len(items) == 0:
                        info_msg += f"\t\t|__ <NOTHING> \n"
                    else:
                        for item in items: 
                            info_msg += f"\t\t|__ {item} \n"
        info_msg += "```" 

        await self._embed_msg(ctx, title=_("Save Files"), description=_(info_msg))


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
        file = kwargs.get("file")
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
        return await ctx.send(embed=embed, file=file)

