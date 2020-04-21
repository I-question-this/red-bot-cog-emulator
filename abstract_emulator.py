"""
Abstract contract of what a controller should do.
~~~~~~~~~~~~~~~~~~~
:copyright: (c) 2020 Tyler Westland
:license: GPL-3.0, see LICENSE for more details.
"""
from abc import ABC, abstractmethod
import logging
from PIL import Image
from typing import List
import math

log = logging.getLogger("red.emulator")

# Exceptions for this class
class AlreadyRunning(Exception):
  """Thrown when a controller is already running an emulator"""
  pass



class ButtonNotRecognized(Exception):
  """Thrown when a button is not recognized"""
  def __init__(self, buttonName: str):
    self.buttonName = buttonName



class NoScreenShotFramesSaved(Exception):
  """Thrown when no screen shot frames are saved but a gif was requested"""
  pass



class NotRunning(Exception):
  """Thrown when a controller is not running an emulator"""
  pass



class ButtonCode:
  """The class the represents a button press and realease"""
  def __init__(self, name:str, pressCode: any, releaseCode: any=None):
    self.name = name
    self.pressCode = pressCode
    self.releaseCode = releaseCode



class AbastractEmulator(ABC):
  """Represents how a controller should behave"""
  # Magic Methods
  def __init__(self, fps:int=60):
    # Save information
    self._fps = fps
    self.__screenShots = [] 
    self.__buttons = {}

  @property
  def buttonNames(self) -> List[str]:
    """Returns button names

    Returns
    -------
    list[str]
        List of button names
    """
    return [buttonName.lower() for buttonName in self.__buttons.keys()]


  @abstractmethod
  def _abstractHoldButton(self, button:ButtonCode, numberOfSeconds:float) -> None:
    """An abstract function for holding a button.

    Parameters
    ----------
    button: ButtonCode
        Button to be held down.
    numberOfSeconds: float
        Number of seconds to hold this button.
    """
    pass


  @abstractmethod
  def _abstractPressButton(self, button:ButtonCode) -> None:
    """An abstract method for pressing the specified button.

    Parameters
    ----------
    button: ButtonCode
        Button to be pressed.
    """
    pass


  def _getButton(self, buttonName: str) -> ButtonCode:
    """Return the button code of the given name.

    Parameters
    ----------
    buttonName: str
        Name of the button to get the code of.
    """
    try:
      return self.__buttons[buttonName.lower()]
    except KeyError:
      log.critical("{}: Unrecognized button \"{}\"".format(
        self.__class__.__name__,
        buttonName
      ))
      raise ButtonNotReconized(buttonName)


  def holdButton(self, buttonName:str, numberOfSeconds:float) -> None:
    """Holds the specified button for the specified time.

    Parameters
    ----------
    button: ButtonCode
        Button to be held down.
    numberOfSeconds: float
        Number of seconds to hold this button.
    """
    self.assertIsRunning()
    if numberOfSeconds < 0:
        raise ValueError("numberOfSeconds must be greater than 0")
    button = self._getButton(buttonName)
    self._abstractHoldButton(button, numberOfSeconds)


  def pressButton(self, buttonName:str) -> None:
    """Presses the specified button.

    Parameters
    ----------
    button: ButtonCode
        Button to be pressed.
    """
    self.assertIsRunning()
    button = self._getButton(buttonName)
    self._abstractPressButton(button)


  def _registerButton(self, button:ButtonCode) -> None:
    """Register a button to this emulator.

    Parameters
    ----------
    button: ButtonCode
       Button to register to this emulator. 
    """
    self.__buttons[button.name.lower()] = button

  
  # Running
  @abstractmethod
  def _runForOneFrame(self) -> None:
    """Abstract method for running one frame"""
    pass


  def runForXFrames(self, numberOfFrames:int) -> None:
    """Run X frames

    Parameters
    ----------
    numberOfFrames: int
        Number of frames to run.
    """
    if numberOfFrames < 0:
      raise ValueError("numberOfFrames must 0 or more")

    self.assertIsRunning()

    if numberOfFrames == 0:
      return

    for _ in range(numberOfFrames):
      self._runForOneFrame()
      self._takeScreenShot()


  def runForXSeconds(self, numberOfSeconds:int) -> None:
    """Run X seconds

    Parameters
    ----------
    numberOfSeconds: int
        Number of seconds to run.
    """
    if numberOfSeconds < 0:
      raise ValueError("numberOfSeconds must 0 or more")

    self.assertIsRunning()

    numFrames = int(math.ceil(numberOfSeconds * self._fps))
    self.runForXFrames(numFrames)


  # Screenshots
  @abstractmethod
  def _abstractTakeScreenShot(self) -> Image:
    """Abstract method to take a screen shot of the emulator

    Returns
    -------
    Image
        The screen shot of the emulator
    """
    pass


  def makeGIF(self, filePath) -> None:
    """Make a GIF from the stored screen shots of this emulator.

    Parameters
    -------
    filePath: str
        File path to save the created GIF in.
    """
    self.assertIsRunning()

    if len(self.__screenShots) == 0:
      raise NoScreenShotFramesSaved()

    self.__screenShots[0].save(
      filePath,
      format='GIF',
      loop=0, save_all=True,
      append_images=self.__screenShots[1:],
      duration=int(round(len(self.__screenShots) / self._fps)))
    
    # Reset values
    self.__screenShots = [] 

    
  def _takeScreenShot(self) -> None:
    """Take and save a screen shot of the emulator"""
    self.assertIsRunning()
    self.__screenShots.append(self._abstractTakeScreenShot())



  # Starting
  @abstractmethod
  def _abstractStart(self, gameROMPath:str, bootROMPath:str=None) -> None:
    """Abstract method for starting the emulator.

    Parameters
    ----------
    gameROM: str
        File path to the game ROM to use.
    bootROM: str
        File path to the boot ROM to use.
    """
    pass
  

  def start(self, gameROMPath:str, bootROMPath:str=None,
      saveStateFilePath:str=None, numberOfSecondsToRun:float=60) -> None:
    """Start the emulator.

    Parameters
    ----------
    gameROM: str
        File path to the game ROM to use.
    bootROM: str
        File path to the boot ROM to use.
    saveStateFilePath: str
        File path of the save state file to load after start up.
    numberOfSecondsToRun: float
        Number of seconds to run after start up.
    """
    if numberOfSecondsToRun < 0:
      raise ValueError("numberOfSecondsToRun must be 0 or more")

    self.assertNotRunning()

    self._abstractStart(gameROMPath, bootROMPath)

    if saveStateFilePath is not None:
        self.loadState(saveStateFilePath)

    self.runForXSeconds(numberOfSecondsToRun)


  # Stopping 
  @abstractmethod
  def _abstractStop(self) -> None:
    """Abstract method for stopping the emulator"""
    pass


  def stop(self, saveStateFilePath:str=None) -> None:
    """Method for stopping the emulator

    Parameters
    ----------
    saveStateFilePath: str
        File path to save the state to before shutting down.
    """
    self.assertIsRunning()

    if saveStateFilePath is not None:
        self.saveState(saveStateFilePath)
    self._abstractStop()


  # State Management
  @abstractmethod
  def saveState(self, saveStateFilePath:str) -> None:
    """Save the state of the emulator.
    
    Parameters
    ----------
    saveStateFilePath: str
        File path of the save the state to.
    """
    pass


  @abstractmethod
  def loadState(self, saveStateFilePath:str) -> None:
    """Load the given state of the emulator.
    
    Parameters
    ----------
    saveStateFilePath: str
        File path of the state file to load.
    """
    pass


  # Status
  def assertIsRunning(self) -> None:
    """Assert that the emulator is running"""
    if not self.isRunning:
      log.critical("{}: Emulator is not running".format(
        self.__class__.__name__
      ))
      raise NotRunning()


  def assertNotRunning(self) -> None:
    """Assert that the emulator is NOT running"""
    if self.isRunning:
      log.critical("{}: Emulator is already running".format(
        self.__class__.__name__
      ))
      raise AlreadyRunning()


  @property
  @abstractmethod
  def isRunning(self) -> bool:
    """Return boolean as to if the emulator is running.

    Returns
    -------
    bool
        True if the emulator is running, False otherwise.
    """
    pass

