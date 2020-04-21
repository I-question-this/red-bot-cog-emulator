"""
Controller Interface For PyBoy
~~~~~~~~~~~~~~~~~~~
:copyright: (c) 2019 i-question-this
:license: GPL-3.0, see LICENSE for more details.
"""
import logging
import os
from PIL import Image
from pyboy import windowevent, PyBoy
from .abstract_emulator import ButtonCode, AbastractEmulator

log = logging.getLogger("red.emulator.gameboy")


class GameBoy(AbastractEmulator):
  # Buttons
  def _abstractHoldButton(self, button:ButtonCode, numberOfSeconds:float) -> None:
    """Holds the specified button for the specififed time
    """
    log.info("PyBoy: Pressing button: {}".format(button.name))
    self._pyboy.sendInput(button.pressCode)
    self.runForXSeconds(numberOfSeconds)
    log.info("PyBoy: Releasing button: {}".format(button.name))
    self._pyboy.sendInput(button.releaseCode)
    self.runForXSeconds(1)


  def _abstractPressButton(self, button:ButtonCode) -> None:
    """Presses the specified button
    """
    log.info("PyBoy: Pressing button: {}".format(button.name))
    self._pyboy.sendInput(button.pressCode)
    self.runForXFrames(2)
    log.info("PyBoy: Releasing button: {}".format(button.name))
    self._pyboy.sendInput(button.releaseCode)
    self.runForXSeconds(1)
    

  # Magic methods
  def __init__(self, screenWidth:int=160, screenHeight:int=144):
    super().__init__(60)

    self._pyboy = None
    self._screenWidth = 160
    self._screenHeight = 144

    # Button registration
    self._registerButton(
      ButtonCode(
        "A",
        windowevent.PRESS_BUTTON_A,
        windowevent.RELEASE_BUTTON_A
      )
    )
    self._registerButton(
      ButtonCode(
        "B",
        windowevent.PRESS_BUTTON_B,
        windowevent.RELEASE_BUTTON_B
      )
    )
    self._registerButton(
      ButtonCode(
        "Select",
        windowevent.PRESS_BUTTON_SELECT,
        windowevent.RELEASE_BUTTON_SELECT
      )
    )
    self._registerButton(
      ButtonCode(
        "Start",
        windowevent.PRESS_BUTTON_START,
        windowevent.RELEASE_BUTTON_START
      )
    )
    self._registerButton(
      ButtonCode(
        "Up",
        windowevent.PRESS_ARROW_UP,
        windowevent.RELEASE_ARROW_UP
      )
    )
    self._registerButton(
      ButtonCode(
        "Down",
        windowevent.PRESS_ARROW_DOWN,
        windowevent.RELEASE_ARROW_DOWN
      )
    )
    self._registerButton(
      ButtonCode(
        "Left",
        windowevent.PRESS_ARROW_LEFT,
        windowevent.RELEASE_ARROW_LEFT
      )
    )
    self._registerButton(
      ButtonCode(
        "Right",
        windowevent.PRESS_ARROW_RIGHT,
        windowevent.RELEASE_ARROW_RIGHT
      )
    )


  # Running
  def _runForOneFrame(self) -> None:
    self._pyboy.tick()


  # Screenshots
  def _abstractTakeScreenShot(self) -> Image:
    """Takes screen shot of emulator
    """
    return self._pyboy.get_screen_image()


  # Starting
  def _abstractStart(self, gameROM, bootROM):
    self._pyboy = PyBoy(gameROM, default_ram_file=bootROM, window_type="headless")
    self._pyboy.set_emulation_speed(False)


  # Stopping
  def _abstractStop(self) -> None:
    self._pyboy.stop(save=True)
    self._pyboy = None


  # State Management
  def loadState(self, saveStateFilePath:str) -> None:
      self._pyboy.loadState(saveStateFilePath)


  def saveState(self, saveStateFilePath:str) -> None:
      self._pyboy.saveState(saveStateFilePath)

  # Status
  @property
  def isRunning(self) -> bool:
    return self._pyboy is not None

