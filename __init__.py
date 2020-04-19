from .emulator import Emulator

def setup(bot):
    bot.add_cog(Emulator(bot))

