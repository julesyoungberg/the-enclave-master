from . import addresses
from .events import OSCEvent, OSCSleepEvent, OSCEventSequence, OSCEventStack


class OSCTransition(OSCEvent):
    """Represents the transition of an OSC message's parameter value over time.

    Attributes:
        start (float): The start value of the parameter.
        end (float): The end value of the parameter.
    """

    def __init__(self, address: str, start: float, end: float, duration: float):
        super().__init__(address, duration)
        self.start = start
        self.end = end

    def step(self, dt: float):
        """Calculates the current parameter value based on time and sends an OSC message with the current value to the specified address.

        Args:
            dt (float): The time elapsed since the last call to step.
        """
        value = ((self.time / self.duration) * (self.end - self.start) + self.start,)
        super().step(dt, value)


class ControlFade(OSCTransition):
    """Represents a control transition for a layer."""

    def __init__(
        self, layer: str, control: str, start: float, end: float, duration: float
    ):
        address = addresses.control(layer, control)
        super().__init__(address, start, end, duration)


class LayerTransition(OSCEventSequence):
    """A class that defines a sequence of events for transitioning a layer in a media player.
    The class inherits from OSCEventSequence.

    Attributes:
    - layer (str): The name of the layer to transition.
    - cue_bin (str): The name of the cue bank associated with the layer.
    - cue_index (int): The index of the cue to trigger.
    - use_mask (bool): Determines whether or not the transition should use a mask.
    - fade (float): The duration of the fade, in seconds, if any.
    """

    def __init__(
        self, layer: str, cue_bin: str, cue_index: int, use_mask=False, fade=0.0
    ):
        events = []

        if fade > 0.0:
            if use_mask:
                events.append(ControlFade(layer, "mask_opacity", 0.5, 1.0, fade))
            else:
                events.append(ControlFade(layer, "opacity", 1.0, 0.0, fade))

        events.append(
            PlayCue(
                layer,
                cue_bin,
                cue_index,
            )
        )

        events.append(OSCSleepEvent(6.0))

        if fade > 0:
            if use_mask:
                events.append(ControlFade(layer, "mask_opacity", 1.0, 0.5, fade))
            else:
                events.append(ControlFade(layer, "opacity", 0.0, 1.0, fade))

        super().__init__(events)


class LayerSwitch(OSCEventSequence):
    """
    A class that represents a layer switch event sequence.

    Args:
        prev_layer (str): The name of the previous layer to be switched.
        next_layer (str): The name of the next layer to be switched.
        cue_bin (int): The number of the cue to be triggered in the next layer.
        cue_index (int): The index of the cue to be triggered in the next layer.
        fade (float): The fade duration for all fade effects in the sequence.
        use_mask (bool): A flag indicating whether a mask should be used or not.
    """

    def __init__(
        self,
        prev_layer: str,
        next_layer: str,
        cue_bin: str,
        cue_index: int,
        fade=6.0,
        use_mask=False,
    ):
        # @todo set opacity before playing cue like in other transition
        events = [PlayCue(next_layer, cue_bin, cue_index), OSCSleepEvent(6.0)]

        if use_mask:
            events.append(ControlFade(next_layer, "mask_opacity", 0.0, 1.0, 0.0))

        events.append(ControlFade(next_layer, "opacity", 0.0, 0.5, fade))

        swap_events = [
            ControlFade(prev_layer, "opacity", 1.0, 0.5, fade),
            ControlFade(next_layer, "opacity", 0.5, 1.0, fade),
        ]

        if use_mask:
            swap_events.append(ControlFade(prev_layer, "mask_opacity", 0.7, 1.0, fade))
            swap_events.append(ControlFade(next_layer, "mask_opacity", 1.0, 0.7, fade))

        events.append(OSCEventStack(swap_events))

        events.append(ControlFade(prev_layer, "opacity", 0.5, 0.0, fade))

        super().__init__(events)


class TriggerCue(OSCEvent):
    """Represents an instantaneous OSC that triggers a cue for a specific layer, cue bank, and index."""

    def __init__(self, layer=None, cue_bin=None, cue_index=None, address=None):
        if (layer == None or cue_bin == None or cue_index == None) and address == None:
            raise Exception(
                "Invalid cue config, must provide an address, or the layer, bin, and index"
            )
        address = addresses.layer_cue(layer, cue_bin, cue_index)
        super().__init__(address)

    def step(self, dt: float):
        super().step(dt, 1.0)


class PlayOneShot(OSCEventSequence):
    def __init__(self, layer: str, cue_bin: str, cue_index: int, fade=1.0):
        events = []

        # make sure the layer is blank (blackout)
        events.append(TriggerCue(address=addresses.layer_blackout(layer)))

        # set the opacity
        events.append(ControlFade(layer, "opacity", 0.0, 1.0, 0.0))

        # play the cue
        events.append(
            TriggerCue(
                layer,
                cue_bin,
                cue_index,
            )
        )

        # sleep till movie end
        events.append(OSCSleepEvent(6.0))

        # fade out on movie end (need clip length in config)
        if fade > 0:
            events.append(ControlFade(layer, "opacity", 1.0, 0.0, fade))

        super().__init__(events)


class PlayCue(OSCEventSequence):
    def __init__(
        self, layer: str, cue_bin: str, cue_index: int, fade=1.0, use_mask=False
    ):
        events = []

        cue = addresses.MADMAPPER_CONFIG[layer]["cues"][cue_index]

        if cue.has_key("one_shot"):
            events.append(PlayOneShot(layer, cue_bin, cue_index, fade))
        else:
            events.append(TriggerCue(layer, cue_bin, cue_index))

        super().__init__(events)
