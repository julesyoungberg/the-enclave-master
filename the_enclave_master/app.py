# the main app logic
# - initializes everything and handles update logic
#   - set up scene manager, event manager, randomized background
# - takes in control over MIDI
# - sends the data to the simulation
# - determines scene automations via randomized background and one hit cues
# - and then sends out OSC via the event manager

import random
import threading

from .control import control_loop
from .layer_randomizer import LayerRandomizer
from .scene import SceneManager
from .scenes import SCENES
from .simulation import Simulation

TIME_STEP_SECONDS = 1.0 / 60.0

SCENE_NAMES = list(SCENES.keys())


class App:
    def __init__(self):
        self.simulation = Simulation()
        self.scene_manager = SceneManager()
        self.bg_randomizer = LayerRandomizer(self.event_manager, layer_type="bg")
        self.fg_randomizer = LayerRandomizer(self.event_manager, layer_type="fg")
        self.control_thread = threading.Thread(target=control_loop, args=(self,))
        self.control_thread.start()

    def update(self, dt: float):
        # randomly change bin for now
        if random.uniform(0, 1) < 0.01:
            # @todo implement slow transition where fg changes first for 30 seconds or so
            new_scene = SCENE_NAMES[random.randint(0, len(SCENE_NAMES) - 1)]
            self.bg_randomizer.scene = new_scene
            self.fg_randomizer.scene = new_scene

        self.simulation.update(dt)
        self.scene_manager.step(dt)
        self.bg_randomizer.step(dt)
        self.fg_randomizer.step(dt)
