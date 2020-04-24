"""
Redbot Cog for Interfacing with Emulators
~~~~~~~~~~~~~~~~~~~
:copyright: (c) 2020 Tyler Westland
:license: GPL-3.0, see LICENSE for more details.
"""
import asyncio
from datetime import datetime
import discord
from discord.embeds import EmptyEmbed
import logging
import os
from typing import AsyncIterator, List
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
    "local_path": None,
    "game_defs": {},
    "channels_to_defs": {},
    "defs_to_channels": {},
    "auto_loads": []
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
        self._locks = {}

    
    @commands.Cog.listener()
    async def on_ready(self):
        await self._auto_load_instances()


    @commands.Cog.listener()
    async def on_shutdown(self):
        await self._stop_all_instances()


    # Getting input
    @commands.Cog.listener()
    async def on_message(self, message: discord.message) -> None:
        """Listen to every message ever.
        This is how the bot will respond to button pushes.
        It will only respond if the message is sent within a registered channel though.
        """
        if isinstance(message.channel, discord.abc.PrivateChannel):
            return
        author = message.author
        valid_user = isinstance(author, discord.Member) and not author.bot
        if not valid_user:
            return
        if await self.bot.is_automod_immune(message):
            return


        channels_to_defs = await self._conf.channels_to_defs()
        def_name = channels_to_defs.get(str(message.channel.id), None)
        if def_name is not None:
            # They're talking to a specific instance, but is it important?
            split_mess = message.content.split(" ")
            if len(split_mess) > 3:
                return
            else:
                # Is there an instance?
                if self._instances.get(def_name, None) is None:
                    return
                # Get rid of any capitalizations.
                button = split_mess[0].lower()
                # Is the first word actually one of the buttons?
                if button not in self._instances[def_name].buttonNames:
                    return
                else:
                    if len(split_mess) != 3:
                        return
                    else:
                        action = split_mess[1].lower()
                        if action == 'p':
                            try:
                                num = min(3, max(1, int(split_mess[2])))
                            except ValueError:
                                return
                        elif action == 'h':
                            try:
                                num = min(3, max(0.5, float(split_mess[2])))
                            except ValueError:
                                return
                        else:
                            return

            # Only one may press the button.
            if not self._locks[def_name].locked():
                async with self._locks[def_name]:
                    if action == 'p':
                        # Press button X times
                        for n in range(num):
                            self._instances[def_name].pressButton(button)
                        title = f"{author.display_name} pressed \"{button}\" {num} time(s)"
                    elif action == 'h':
                        # Hold button for X seconds
                        self._instances[def_name].holdButton(button, num)
                        title=f"{author.display_name} held \"{button}\" for {num} second(s)"
                    self._instances[def_name].runForXSeconds(10)
                    await self._save_main_state_file(def_name)
                    await self._send_screenshot(def_name, title=_(title))


    # Commands
    @commands.group()
    @checks.is_owner()
    async def setup(self, ctx: commands.Context) -> None:
        """Setup commands"""


    @commands.guild_only()
    @setup.command(name="register")
    async def setup_register(self, ctx: commands.Context, definition_name:str) -> None:
        """Register the channel this message was sent from to the given game.

        Parameters
        ----------
        definition_name: str
            Name of the game to register this channel to.
        """
        game_defs = await self._conf.game_defs()
        if game_defs.get(definition_name, None) is None: 
            info_msg = "```\n"
            info_msg += f"{definition_name} does not exist\n"
            info_msg += "```\n"
            return await self._embed_msg(ctx, title=_("Improper Definition Name"),
                    description=_(info_msg), error=True)

        channels_to_defs = await self._conf.channels_to_defs()
        if str(ctx.channel.id) in channels_to_defs.keys():
            info_msg = "```\n"
            info_msg += f"This channel is already registered to \"{def_name}\"\n"
            info_msg += "```\n"
            return await self._embed_msg(ctx, title=_("Channel Already Register"),
                    description=_(info_msg), error=True)

        # Register to both
        channels_to_defs[str(ctx.channel.id)] = definition_name
        await self._conf.channels_to_defs.set(channels_to_defs)
        defs_to_channels = await self._conf.defs_to_channels()
        defs_to_channels[definition_name].append(ctx.channel.id)
        await self._conf.defs_to_channels.set(defs_to_channels)
        # Inform of success
        info_msg = "```\n"
        info_msg += f"Registered this channel to \"{definition_name}\"\n"
        info_msg += "```\n"
        return await self._embed_msg(ctx, title=_("Channel Registered"),
                description=_(info_msg), success=True)


    @commands.guild_only()
    @setup.command(name="unregister")
    async def setup_unregister(self, ctx: commands.Context):
        """Unregiseter the channel this message is sent from."""
        channels_to_defs = await self._conf.channels_to_defs()
        if str(ctx.channel.id) not in channels_to_defs.keys():
            info_msg = "```\n"
            info_msg += f"This channel isn't registered to anything\n"
            info_msg += "```\n"
            return await self._embed_msg(ctx, title=_("Channel Not Registered"),
                    description=_(info_msg), error=True)
        
        def_name = channels_to_defs[str(ctx.channel.id)]
        del channels_to_defs[str(ctx.channel.id)]
        await self._conf.channels_to_defs.set(channels_to_defs)
        defs_to_channels = await self._conf.defs_to_channels()
        defs_to_channels[def_name] = list(filter(lambda c_id: c_id != ctx.channel.id, defs_to_channels[def_name]))
        await self._conf.defs_to_channels.set(defs_to_channels)

        # Inform of success
        info_msg = "```\n"
        info_msg += f"This channel has been unregistered from \"{def_name}\"\n"
        info_msg += "```\n"
        return await self._embed_msg(ctx, title=_("Channel Unregistered"),
                description=_(info_msg), success=True)


    @setup.command(name="stop")
    async def setup_stop(self, ctx: commands.Context, definition_name: str) -> None:
        """Stop the given game.

        Parameters
        ----------
        definition_name: str
            Name of the game to stop.
        """
        game_defs = await self._conf.game_defs()
        if definition_name not in game_defs.keys():
            info_msg = "```\n"
            info_msg += f"{definition_name} does not exist\n"
            info_msg += "```\n"
            return await self._embed_msg(ctx, title=_("Improper Definition Name"),
                    description=_(info_msg), error=True)

        # Does an instance actually exist?
        if self._instances.get(definition_name, None) is None:
            info_msg = "```\n"
            info_msg += f"{definition_name} has no instance running\n"
            info_msg += "```\n"
            return await self._embed_msg(ctx, title=_("Instance Not Running"),
                    description=_(info_msg), error=True)
        
        # Is the instance actually running?
        if not self._instances[definition_name].isRunning:
            info_msg = "```\n"
            info_msg += f"{definition_name} has no instance running\n"
            info_msg += "```\n"
            return await self._embed_msg(ctx, title=_("Instance Not Running"),
                    description=_(info_msg), error=True)

        await self._stop_instance(definition_name)


    @setup.command(name="stop_all")
    async def setup_stop_all(self, ctx: commands.Context) -> None:
        """Stop all running games."""
        await self._stop_all_instances()


    @setup.command(name="start")
    async def setup_start(self, ctx: commands.Context, definition_name: str) -> None:
        """Start the given game.

        Parameters
        ----------
        definition_name: str
            Name of the game to start.
        """
        game_defs = await self._conf.game_defs()
        if definition_name not in game_defs.keys():
            info_msg = "```\n"
            info_msg += f"{definition_name} does not exist\n"
            info_msg += "```\n"
            return await self._embed_msg(ctx, title=_("Improper Definition Name"),
                    description=_(info_msg), error=True)

        # Is it already running?
        if self._instances.get(definition_name, None) is not None:
            if self._instances[definition_name].isRunning:
                info_msg = "```\n"
                info_msg += f"{definition_name} already has an instance running\n"
                info_msg += "```\n"
                return await self._embed_msg(ctx, title=_("Instance is Already Running"),
                        description=_(info_msg), error=True)

        await self._start_instance(definition_name)


    @setup.command(name="start_auto")
    async def setup_start_auto(self, ctx: commands.Context) -> None:
        """Start all games specified as auto load"""
        await self._auto_load_instances()


    @setup.command(name="ROMs", aliases=["roms"])
    async def setup_roms(self, ctx: commands.Context):
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

        await self._embed_msg(ctx, title=_("Available ROMs"), description=_(info_msg), success=True)


    @setup.command(name="definitions", aliases=["defs"])
    async def setup_definitions(self, ctx: commands.Context) -> None:
        """List defined games."""
        info_msg = "```\n"
        game_defs = await self._conf.game_defs()
        if len(game_defs) == 0:
            info_msg += "NONE"
        else:
            for definition in game_defs.keys():
                info_msg += f"{definition}:\n"
                info_msg += f"\t|__Boot ROM: {game_defs[definition]['bootROM']}\n"
                info_msg += f"\t|__Game ROM: {game_defs[definition]['gameROM']}\n"
        info_msg += "```" 
        await self._embed_msg(ctx, title=_("Defined Games"), description=_(info_msg), success=True)


    @setup.command(name="list_auto_loads", aliases=["list_als"])
    async def setup_list_auto_loads(self, ctx: commands.Context) -> None:
        """List names in the auto load list."""
        info_msg ="```\n"
        for al in await self._conf.auto_loads():
            info_msg += f"{al}\n"
        info_msg += "```"
        return await self._embed_msg(ctx, title=_("Auto Load List"), description=_(info_msg),
                success=True)


    @setup.command(name="add_auto_load", aliases=["add_al"])
    async def setup_add_auto_load(self, ctx: commands.Context, definition_name:str) -> None:
        """Add a game definition to the auto load list.

        Parameters
        ----------
        definition_name: str
            Name for this game definition to add to the auto load list.
        """
        game_defs = await self._conf.game_defs()
        if definition_name not in game_defs.keys():
            info_msg ="```\n"
            info_msg += f"The name \"{definition_name}\" does not exist\n"
            info_msg += "```"
            return await self._embed_msg(ctx, title=_("Non-Existent Name"), description=_(info_msg),
                    error=True)

        auto_loads = await self._conf.auto_loads()
        auto_loads.append(definition_name)
        await self._conf.auto_loads.set(auto_loads)

        info_msg ="```\n"
        info_msg += f"Added \"{definition_name}\" to the auto load list\n"
        info_msg += "```"
        return await self._embed_msg(ctx, title=_("Added to List"), description=_(info_msg),
                success=True)


    @setup.command(name="delete_auto_load", aliases=["del_al"])
    async def setup_delete_auto_load(self, ctx: commands.Context, definition_name:str) -> None:
        """Delete a game definition to the auto load list.

        Parameters
        ----------
        definition_name: str
            Name for this game definition to delete from the auto load list.
        """
        game_defs = await self._conf.game_defs()
        if definition_name not in game_defs.keys():
            info_msg ="```\n"
            info_msg += "The name \"{definition_name}\" does not exist\n"
            info_msg += "```"
            return await self._embed_msg(ctx, title=_("Non-Existent Name"), description=_(info_msg),
                    error=True)

        auto_loads = await self._conf.auto_loads()
        if not definition_name in auto_loads:
            info_msg ="```\n"
            info_msg += f"The name \"{definition_name}\" is not in the auto loads list.\n"
            info_msg += "```"
            return await self._embed_msg(ctx, title=_("Not in List"), description=_(info_msg),
                    error=True)

        await self._conf.auto_loads.set(list(filter(lambda dn: dn != definition_name, auto_loads)))

        info_msg ="```\n"
        info_msg += f"Removed \"{definition_name}\" from the auto load list\n"
        info_msg += "```"
        return await self._embed_msg(ctx, title=_("Removed from List"), description=_(info_msg),
                success=True)


    @setup.command(name="set_definition", aliases=["set_def"])
    async def setup_set_definition(self, ctx: commands.Context, definition_name:str, bootROM:str, gameROM:str) -> None:
        """Set a defined game.

        Parameters
        ----------
        name: str
            Name for this game definition. Must be unique.
        bootROM: str
           Boot ROM for this game. Must actually exist. 
        gameROM: str
           Game ROM for this game. Must actually exist. 
        """
        # Check that the ROMs exist
        if not os.path.exists(await self.bootROM_path(bootROM)):
            return await self._embed_msg(
                ctx,
                title=_("Invalid Boot ROM"),
                description=_(f"{bootROM} does not exist."),
                error=True
            )

        if not os.path.exists(await self.gameROM_path(gameROM)):
            return await self._embed_msg(
                ctx,
                title=_("Invalid Game ROM"),
                description=_(f"{gameROM} does not exist."),
                error=True
            )

        # Check that this name has not already been used
        game_defs = await self._conf.game_defs()
        if definition_name in game_defs.keys():
            return await self._embed_msg(
                ctx,
                title=_("Name Conflict"),
                description=_(f"{definition_name} already exist as a name."),
                error=True
            )
        # Set the definition
        game_defs[definition_name] = {"bootROM": bootROM, "gameROM": gameROM}
        await self._conf.game_defs.set(game_defs)
        # Create the list of registered channels
        defs_to_channels = await self._conf.defs_to_channels()
        defs_to_channels[definition_name] = list()
        await self._conf.defs_to_channels.set(defs_to_channels)
        return await self._embed_msg(
            ctx,
            title=_("Saved Definition"),
            description=_(f"Definition was saved successfully."),
            success=True
        )


    @setup.command(name="delete_definition", aliases=["del_def"])
    async def setup_delete_definition(self, ctx: commands.Context, definition_name:str) -> None:
        """Delete a defined game

        Note that this does delete any files or folders.

        Parameters
        ----------
        definition_name: str
            Name of the game to delete.
        """
        game_defs = await self._conf.game_defs()
        if definition_name not in game_defs.keys():
            return await self._embed_msg(
                ctx,
                title=_("No Such Definition"),
                description=_(f"{name} does not exist."),
                error=True
            )

        # Ask the user if they are really sure about this
        info_msg = _(
                "Are you sure you want to delete?:\n"
                "```\n"
                f"{definition_name}\n"
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
            # If an instance is running, shut it down
            if self._locks.get(definition_name, None) is not None:
                async with self._locks[definition_name]:
                    if self._instances.get(definition_name, None) is not None:
                        if self._instances[definition_name].isRunning():
                            self._instances[definition_name].stop()
            # Delete it from the list
            del game_defs[definition_name]
            await self._conf.game_defs.set(game_defs)
            # Delete the channel registrations
            defs_to_channels = await self._conf.defs_to_channels()
            channels_to_defs = await self._conf.channels_to_defs()
            for channel_id in channels_to_defs.keys():
                del channels_to_defs[channel_id]
            await self._conf.channels_to_defs.set(channels_to_defs)
            del defs_to_channels[definition_name]
            await self._conf.defs_to_channels.set(defs_to_channels)
            # Report success
            return await self._embed_msg(
                ctx,
                title=_("Deletion Successful"),
                description=_(f"{definition_name} has been deleted."),
                success=True
            )


    @setup.command(name="localpath")
    @checks.is_owner()
    async def setup_local_path(self, ctx: commands.Context, local_path:str=None) -> None:
        """Sets the path to look for ROMs

        Leave blank to reset to the default.

        Parameters
        ----------
        local_path: str
           Path to set the local path to.
           If unset it will be reset to the default.
        """
        if not local_path:
            await self._conf.local_path.set(str(cog_data_path()))
            return await self._embed_msg(
                ctx,
                title=_("Setting Changed"),
                description=_(f"The localpath location has been reset to {cog_data_path(raw_name='Emulator').absolute()}"),
                success=True
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
                description=_(f"{local_path} does not seem like a valid path."),
                error=True
            )
        # It exists, so we set it.
        await self._conf.local_path.set(local_path)

        if not os.path.exists(await self.gb_path()):
            warn_msg = _(
                    f"`{gb_path}` does not exist. "
                    "The path will still be saved, but please check the path and "
                    "create a gb folder in `{localfolder}` before attempting "
                    "to play games."
                )
            await self._embed_msg(ctx, title=_("Invalid Environment"), description=warn_msg, error=True)
        else:
            for subfolder in [await self.boots_dir(), await self.games_dir(), await self.saves_dir()]:
                if not os.path.exists(subfolder):
                    os.mkdir(subfolder)

        return await self._embed_msg(
                ctx,
                title=_("Setting Changed"),
                description=_(f"The ROMs path location has been set to {local_path}"),
                success=True
            )


    # Helper Functions
    # Path Related Functions
    async def gb_path(self) -> str:
        """Return '<local_path>/gb'

        Note this function does not check if this path exists.a

        Returns
        -------
        str
            '<local_path>/gb'
        """
        return os.path.join(await self._conf.local_path(), "gb")


    async def boots_dir(self) -> str:
        """Return '<local_path>/gb/boots'

        Note this function does not check if this path exists.

        Returns
        -------
        str
            '<local_path>/gb/boots'
        """
        return os.path.join(await self.gb_path(), "boots")


    async def bootROM_path(self, bootROM:str) -> str:
        """Return '<local_path>/gb/boots/<bootROM>'

        Note this function does not check if this path exists.

        Parameters
        ----------
        bootROM: str
            The name of the boot ROM to get the full path of.

        Returns
        -------
        str
            '<local_path>/gb/boots/<bootROM>'
        """
        return os.path.join(await self.boots_dir(), bootROM)


    async def games_dir(self) -> str:
        """Return '<local_path>/gb/games'

        Note this function does not check if this path exists.

        Returns
        -------
        str
            '<local_path>/gb/games'
        """
        return os.path.join(await self.gb_path(), "games")


    async def gameROM_path(self, gameROM) -> str:
        """Return '<local_path>/gb/games/<gameROM>'

        Note this function does not check if this path exists.

        Parameters
        ----------
        gameROM: str
            The name of the game ROM to get the full path of.

        Returns
        -------
        str
            '<local_path>/gb/games/<gameROM>'
        """
        return os.path.join(await self.games_dir(), gameROM)


    async def saves_dir(self) -> str:
        """Return '<local_path>/gb/saves'

        Note this function does not check if this path exists.

        Returns
        -------
        str
            '<local_path>/gb/saves'
        """
        return os.path.join(await self.gb_path(), "saves")


    async def saves_definition_dir(self, def_name) -> str:
        """Return '<local_path>/gb/saves/<def_name>'

        Note this function does not check if this path exists.

        Parameters
        ----------
        def_name: str
            The save directory for the given game definition name.

        Returns
        -------
        str
            '<local_path>/gb/saves/<def_name>'
        """
        return os.path.join(await self.saves_dir(), def_name)


    async def state_save_dir(self, def_name) -> str:
        """Return '<local_path>/gb/saves/<def_name>/states'

        Note this function does not check if this path exists.

        Parameters
        ----------
        def_name: str
            The definition name to get the state save directory of.

        Returns
        -------
        str
            '<local_path>/gb/saves/<def_name>/states'
        """
        return os.path.join(await self.saves_definition_dir(def_name), "states")


    async def state_save_path(self, def_name, save_name) -> str:
        """Return '<local_path>/gb/saves/<def_name>/states/<save_name>'

        Note this function does not check if this path exists.

        Parameters
        ----------
        def_name: str
            The definition name to get the state save file of.
        save_name: str
            The state save file name.

        Returns
        -------
        str
            '<local_path>/gb/saves/<def_name>/states/<save_name>'
        """
        return os.path.join(await self.state_save_dir(def_name), save_name)


    async def screen_shots_save_dir(self, def_name) -> str:
        """Return '<local_path>/gb/saves/<def_name>/screen_shots'

        Note this function does not check if this path exists.

        Parameters
        ----------
        def_name: str
            The screen_shot save directory for the given game definition name.

        Returns
        -------
        str
            '<local_path>/gb/saves/<def_name>/screen_shots'
        """
        return os.path.join(await self.saves_definition_dir(def_name), "screen_shots")


    async def screen_shots_save_path(self, def_name, screen_shot_name) -> str:
        """Return '<local_path>/gb/saves/<def_name>/screen_shots/<save_name>'

        Note this function does not check if this path exists.

        Parameters
        ----------
        def_name: str
            The screen shots save directory for the given game definition name.
        screen_shot_name: str
            The screen shot file name.

        Returns
        -------
        str
            '<local_path>/gb/saves/<def_name>/screen_shots/<screen_shot_name>'
        """
        return os.path.join(await self.screen_shots_save_dir(def_name), screen_shot_name)


    async def _send_message_to_registered_channels(self, definition_name:str, **kwargs) -> None:
        """Send a message to every registered channel to the given definition name

        Parameters
        ----------
        definition_name: str
            The name of the game being played by channels.
            Note that this function does not check if it exists, so it will
            simply send to no channels if it doesn't exist. This is because
            it is intended to be used by other functions that do check if the 
            given definition_name exists.
        """
        filepath = kwargs.get("filepath")
        filename = kwargs.get("filename")
        defs_to_channels = await self._conf.defs_to_channels()
        for channel_id in defs_to_channels[definition_name]:
            if filepath:
                file = discord.File(filepath, filename=filename)
            else:
                file = None
            await self._embed_msg(self.bot.get_channel(channel_id), file=file, **kwargs)


    async def _save_main_state_file(self, definition_name: str) -> None:
        """Save the current state to the main state save file.

        Parameters
        ----------
        definition_name: str
            The name of the game being played by channels.
            Note that this function does not check if it exists, so it will crash
            if there is no existing instance.
        """
        self._instances[definition_name].saveState(await self.state_save_path(definition_name, "main"))


    async def _load_main_state_file(self, definition_name: str) -> None:
        """Load the main state file.

        If the main state file does not exist it will simply not load anything.


        Parameters
        ----------
        definition_name: str
            The name of the game being played by channels.
            Note that this function does not check if it exists, so it will crash
            if there is no existing instance.
        """
        if os.path.exists(await self.state_save_path(definition_name, "main")):
            self._instances[definition_name].loadState(await self.state_save_path(definition_name, "main"))


    async def _send_screenshot(self, definition_name: str,  **kwargs) -> None:
        """Send a message and screen shot to every registered channel to the given definition name

        Parameters
        ----------
        definition_name: str
            The name of the game being played by channels.
            Note that this function does not check if it exists, so it will crash
            if there is no existing instance.
        """
        screenshot_path = await self.screen_shots_save_path(definition_name, f"{datetime.now()}.gif")
        self._instances[definition_name].makeGIF(screenshot_path)
        await self._send_message_to_registered_channels(
                definition_name, filepath=screenshot_path, filename="gameplay.gif", **kwargs)


    def _button_usage_message(self, definition_name:str) -> str:
        """Construct a help message to interacting with the emulator of the given definition name.

        Parameters
        ----------
        definition_name: str
            The name of the game being played by channels.
            Note that this function does not check if it exists, so it will crash
            if there is no existing instance.
        
        Returns
        -------
        str
            Help message.
        """
        msg = "```\n"
        msg += "Usage:\n"
        msg += "<button> := press <button> once\n"
        msg += "<button> p <number> := press <button> <number> times (max: 3)\n"
        msg += "<button> h <number> := hold <button> for <number> seconds (max: 3)\n"
        msg += f"Buttons: ({', '.join(sorted(self._instances[definition_name].buttonNames))})\n"
        msg += "```\n"
        return msg


    async def _start_instance(self, definition_name:str):
        """Start the given game.

        Parameters
        ----------
        definition_name: str
            The name of the game being started
        """
        # Lock it up, just in case someone jumps the gun.
        if self._locks.get(definition_name, None) is None:
            self._locks[definition_name] = asyncio.Lock()
        async with self._locks[definition_name]:
            # Perhaps the first time so create the folders.
            if not os.path.exists(await self.saves_definition_dir(definition_name)):
                os.mkdir(await self.saves_definition_dir(definition_name))

            if not os.path.exists(await self.state_save_dir(definition_name)):
                os.mkdir(await self.state_save_dir(definition_name))

            if not os.path.exists(await self.screen_shots_save_dir(definition_name)):
                os.mkdir(await self.screen_shots_save_dir(definition_name))

            # Does an instance already exist?
            if self._instances.get(definition_name, None) is None:
                self._instances[definition_name] = GameBoy()

            # Check that it's not already running.
            if not self._instances[definition_name].isRunning:
                game_defs = await self._conf.game_defs()
                def_info = game_defs[definition_name]
                # Start the emulator, but don't run it
                self._instances[definition_name].start(
                        bootROMPath=await self.bootROM_path(def_info["bootROM"]),
                        gameROMPath=await self.gameROM_path(def_info["gameROM"]),
                        numberOfSecondsToRun=0
                    )
                # Load the state file, if it exists
                await self._load_main_state_file(definition_name)
                # Now run the emulator 
                self._instances[definition_name].runForXSeconds(60)

                # Send a screenshot
                await self._send_screenshot(definition_name,
                        title=_(f"Started \"{definition_name}\""),
                        description=_(self._button_usage_message(definition_name)))


    async def _stop_instance(self, definition_name:str):
        """Stop the given game.

        Parameters
        ----------
        definition_name: str
            Name of the game to stop.
        """
        # Stop the instance
        # Lock it up, just in case someone jumps the gun.
        async with self._locks[definition_name]:
            if self._instances[definition_name].isRunning:
                await self._save_main_state_file(definition_name)
                self._instances[definition_name].stop()
                info_msg = "```\n"
                info_msg += f"{definition_name} has been stopped.\n"
                info_msg += "```\n"
                return await self._send_message_to_registered_channels(definition_name, 
                        title=_("Instance Stopped"), description=_(info_msg), success=True)


    async def _stop_all_instances(self):
        """Stop all instances that are currently running"""
        # Start up all the auto load instances
        for def_name in self._instances.keys():
            await self._stop_instance(def_name)


    async def _auto_load_instances(self):
        """Start all specified instances for auto loading."""
        # Start up all the auto load instances
        for def_name in await self._conf.auto_loads():
            await self._start_instance(def_name)


    async def _embed_msg(self, ctx: commands.Context, **kwargs) -> None:
        """Assemble and send an embedded message.
        Credit for this goes to the Audio cog within the core RedBot cogs.

        Parameters
        ----------
        definition_name: str
            The name of the game being played by channels.
            Note that this function does not check if it exists, so it will
            simply send to no channels if it doesn't exist. This is because
            it is intended to be used by other functions that do check if the 
            given definition_name exists.
        """
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
        if file:
            embed.set_image(url=f"attachment://{file.filename}")
        return await ctx.send(embed=embed, file=file)

