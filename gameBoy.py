"""
Controller Interface For PyBoy
~~~~~~~~~~~~~~~~~~~
:copyright: (c) 2020 Tyler Westland
:license: GPL-3.0, see LICENSE for more details.
"""
import logging
import os
from PIL import Image
from pyboy import windowevent, PyBoy
from .abstract_emulator import ButtonCode, AbastractEmulator

log = logging.getLogger("red.emulator")


class GameBoy(AbastractEmulator):
  # Buttons
  def _abstractHoldButton(self, button:ButtonCode, numberOfSeconds:float) -> None:
    """Holds the specified button for the specified time.

    Parameters
    ----------
    button: ButtonCode
        Button to be held down.
    numberOfSeconds: float
        Number of seconds to hold this button.
    """
    self._pyboy.send_input(button.pressCode)
    self.runForXSeconds(numberOfSeconds)
    self._pyboy.send_input(button.releaseCode)
    self.runForXSeconds(1)


  def _abstractPressButton(self, button:ButtonCode) -> None:
    """Presses the specified button.

    Parameters
    ----------
    button: ButtonCode
        Button to be pressed.
    """
    self._pyboy.send_input(button.pressCode)
    self.runForXFrames(2)
    self._pyboy.send_input(button.releaseCode)
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
        "Se",
        windowevent.PRESS_BUTTON_SELECT,
        windowevent.RELEASE_BUTTON_SELECT
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
        "St",
        windowevent.PRESS_BUTTON_START,
        windowevent.RELEASE_BUTTON_START
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
        "U",
        windowevent.PRESS_ARROW_UP,
        windowevent.RELEASE_ARROW_UP
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
        "D",
        windowevent.PRESS_ARROW_DOWN,
        windowevent.RELEASE_ARROW_DOWN
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
        "L",
        windowevent.PRESS_ARROW_LEFT,
        windowevent.RELEASE_ARROW_LEFT
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
        "R",
        windowevent.PRESS_ARROW_RIGHT,
        windowevent.RELEASE_ARROW_RIGHT
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
    """Runs the PyBoy for one tick/frame"""
    self._pyboy.tick()


  # Screenshots
  def _abstractTakeScreenShot(self) -> Image:
    """Takes screen shot of emulator

    Returns
    -------
    Image
        Image object of the screen shot.
    """
    return self._pyboy.get_screen_image()


  # Starting
  def _abstractStart(self, gameROM, bootROM) -> None:
    """Start the PyBoy emulator.

    Parameters
    ----------
    gameROM: str
        File path to the game ROM to use.
    bootROM: str
        File path to the boot ROM to use.
    """
    self._pyboy = PyBoy(gameROM, default_ram_file=bootROM, window_type="headless")
    self._pyboy.set_emulation_speed(False)


  # Stopping
  def _abstractStop(self) -> None:
    """Stop the PyBoy emulator"""
    self._pyboy.stop(save=False)
    self._pyboy = None


  # State Management
  def loadState(self, state_file_path:str) -> None:
      """Load a save state file.

      Parameters:
      state_file_path: str
        File path to the state file to load.
      """
      with open(state_file_path, "rb") as fin:
          self._pyboy.load_state(fin)


  def saveState(self, state_file_path:str) -> None:
      """Save a save state file.

      Parameters:
      state_file_path: str
        File path to the state file to save.
      """
      with open(state_file_path, "wb") as fout:
          self._pyboy.save_state(fout)

  # Status
  @property
  def isRunning(self) -> bool:
    """Return True if the PyBoy emulator is running, False otherwise.

    Returns
    -------
    bool
        if the PyBoy emulator is running.
    """
    return self._pyboy is not None

