from .fader_controller import FaderController
from ..osc.events import OSCEventManager


class LayerFXController:
    """
    The LayerFXController class manages the visualization of special effects on a given layer.
    It takes an OSCEventManager instance and the name of the layer as arguments at initialization.
    The class also creates three FaderController instances for controlling the fx_amount, feedback_amount, and feedback_fx_amount attributes.

    The set_intensity method sets the intensity of the special effects, and the update method updates the status of the FaderController instances with a given delta time in seconds.

    """

    def __init__(self, event_manager: OSCEventManager, layer: str):
        self.fx_amount = FaderController(
            event_manager, layer, "fx_amount", min=0.1, max=1.0
        )
        self.feedback_amount = FaderController(
            event_manager, layer, "feedback_amount", min=0.03, max=0.33
        )
        self.feedback_fx_amount = FaderController(
            event_manager, layer, "feedback_fx_amount", min=0.1, max=1.0
        )

    def set_intensity(self, intensity: float):
        self.fx_amount.intensity = intensity
        self.feedback_amount.intensity = intensity
        self.feedback_fx_amount.intensity = intensity

    def update(self, dt: float):
        self.fx_amount.update(dt)
        self.feedback_amount.update(dt)
        self.feedback_fx_amount.update(dt)
