import sounddevice as sd
import soundfile as sf
import numpy as np
import threading
import os
import random
import time
from ..simulation import Simulation
from pathlib import Path
from pedalboard import Pedalboard, Distortion, Gain, LowpassFilter, HighpassFilter, Reverb, Delay, Limiter
# import ... we expect custom SoundPlayer.py in same folder as this file

DISTORTION_MIN_dB = 0
DISTORTION_MAX_dB = 25
LOWPASS_FILTER_MIN_Hz = 300
LOWPASS_FILTER_MAX_Hz = 22000
HIGHPASS_FILTER_MIN_Hz = 30
HIGHPASS_FILTER_MAX_Hz = 9000
REVERB_WET_LEVEL_MIN = 0
REVERB_WET_LEVEL_MAX = 0.6
REVERB_DRY_LEVEL_MIN = 0.5
REVERB_DRY_LEVEL_MAX = 1
REVERB_ROOM_SIZE_MIN = 0.3
REVERB_ROOM_SIZE_MAX = 0.6
DELAY_FEEDBACK_MIN = 0.1
DELAY_FEEDBACK_MAX = 0.35
DELAY_MIX_MIN = 0
DELAY_MIX_MAX = 0.5

FADE_TIME_s = 1.5  # Fade duration in seconds
AUDIO_CHUNK_SZ = 1024

# Use this path when running as a standalone test script
# where_we_at_path = str(Path.cwd().resolve().parent.parent)
# Use this path when running as part of enclave
MUSIC_FOLDER = "/music"
FOLEY_FOLDER = "/audio"

OUTPUT_DEVICE = "Macbook Pro Speakers"
# OUTPUT_DEVICE = "Speakers BlackHole"
# OUTPUT_DEVICE = "HDMI BlackHole"

class Audio_controller:

    def __init__(self, sound_type):
        self.audio_data = {} # these should all be in one structure
        self.samplerates = {}
        self.volumes = {}
        self.audio_idx = {}
        self.audio_len = {} # Used for ending sounds pre-emptively
        self.file_active = {} # If sounds are fading out, this is 0, else 1
        self.streams = {}
        self.paths = {}
        self.sound_type = sound_type

        # The ordering of these effects is critical!!
        self.board = Pedalboard()

        # if self.sound_type == 'music':
        #     self.board.append(Distortion(drive_db=0))
        #     self.board.append(Gain(gain_db=0))
        #     self.board.append(LowpassFilter(cutoff_frequency_hz=LOWPASS_FILTER_MAX_Hz))
        #     self.board.append(HighpassFilter(cutoff_frequency_hz=HIGHPASS_FILTER_MIN_Hz))
        # elif self.sound_type == 'foley':
        #     self.board.append(Delay(delay_seconds=1,feedback=DELAY_FEEDBACK_MIN,mix=DELAY_MIX_MIN))
        #     self.board.append(Reverb(room_size=0.5,wet_level=REVERB_WET_LEVEL_MIN,dry_level=REVERB_DRY_LEVEL_MAX))
        #     self.board.append(Limiter(threshold_db=0))
        # else:
        #     print("invalid sound type, no fx applied")

        where_we_at_path = str(Path.cwd().resolve())

        # NOTE Missing music files in your filepath? Download them from Jules' gdrive
        if self.sound_type == 'music':
            self.paths["healthy_forest"] = (where_we_at_path + MUSIC_FOLDER + "/HEALTHY") # Looks like "path/audio/HEALTHY"
            self.paths["burning_forest"] = (where_we_at_path + MUSIC_FOLDER + "/BURN")
            self.paths["dead_forest"] = (where_we_at_path + MUSIC_FOLDER + "/BURNT")
            self.paths["growing_forest"] = (where_we_at_path + MUSIC_FOLDER + "/GROWING")
            self.paths["storm"] = (where_we_at_path + MUSIC_FOLDER + "/STORM")
            self.paths["rain"] = (where_we_at_path + MUSIC_FOLDER + "/RAIN")
            self.paths["deforestation"] = (where_we_at_path + MUSIC_FOLDER + "/HUMAN")
            self.paths["climate_change"] = (where_we_at_path + MUSIC_FOLDER + "/CLIMATE_CHANGE")
        elif self.sound_type == 'foley':
            self.paths["healthy_forest"] = (where_we_at_path + FOLEY_FOLDER + "/HEALTHY") # Looks like "path/audio/HEALTHY"
            self.paths["burning_forest"] = (where_we_at_path + FOLEY_FOLDER + "/BURN")
            self.paths["dead_forest"] = (where_we_at_path + FOLEY_FOLDER + "/BURNT")
            self.paths["growing_forest"] = (where_we_at_path + FOLEY_FOLDER + "/GROWING")
            self.paths["storm"] = (where_we_at_path + FOLEY_FOLDER + "/STORM")
            self.paths["rain"] = (where_we_at_path + FOLEY_FOLDER + "/RAIN")
            self.paths["deforestation"] = (where_we_at_path + FOLEY_FOLDER + "/HUMAN")
            self.paths["climate_change"] = (where_we_at_path + FOLEY_FOLDER + "/CLIMATECHANGE")
        else:
            print("invalid sound type, Paths are fuked bro")

    # Scene param are from SCENES dict in scenes.py
    def set_scene(self, new_scene):
        for filename in self.audio_data:
            self.stop_audio(filename)
        
        subfolder_path = self.paths[new_scene]
        filenames = os.listdir(subfolder_path)
        if len(filenames) < 1:
            return
        file_to_play = random.sample(filenames, 1)
        self.load_audio(file_to_play[0], subfolder_path + "/" + file_to_play[0])
        self.play_audio(file_to_play[0])

    # Scene param are from SCENES dict in scenes.py
    # Call this every 100ms or so. Longer intervals will leave more of a gap on sound fadeout/fadein
    def update(self, scene, simulation):
        # Update FX
        knob_vals = self.get_effect_knob_vals(simulation)
        self.knob_val_to_effect(knob_vals)

        remaining_times = self.get_audio_time_remaining()
        for filename in remaining_times:
            if remaining_times[filename] < FADE_TIME_s and self.file_active[filename] == 1:

                # Mark the audio file that's finishing
                self.file_active[filename] = 0

                # Get list of all possible files for scene
                subfolder_path = self.paths[scene]
                filenames = os.listdir(subfolder_path)

                # Find which files area playing right now
                dictKeys = list(self.audio_data.keys())

                # Point to existing item to enter the loop
                newFile = dictKeys[0] 

                # Pick a file that isn't playing
                loops = 0 
                while newFile in self.audio_data.keys():
                    newFile = random.sample(filenames, 1)
                    newFile = newFile[0] # Convert to string from list

                    # Don't loop forever if all available files already playing
                    loops += 1
                    if(loops > 70):
                        print("we're looping forever, quik escape music")
                        break 

                self.load_audio(newFile, subfolder_path + "/" + newFile)
                self.play_audio(newFile)

    def play_audio(self, filename):
        # Fade in
        fade_in_samples = int(FADE_TIME_s * self.samplerates[filename])
        fade_in_curve = np.linspace(0, self.volumes[filename], fade_in_samples)
        self.audio_data[filename][:fade_in_samples] *= fade_in_curve[:, np.newaxis]

        # Fade out
        fade_out_samples = int(FADE_TIME_s * self.samplerates[filename])
        fade_out_curve = np.linspace(self.volumes[filename], 0, fade_out_samples)
        self.audio_data[filename][-fade_out_samples:] *= fade_out_curve[:, np.newaxis]

        # event = threading.Event()

        # def callback(outdata, frames, time, status):
        #     if self.audio_idx[filename] >= self.audio_len[filename]:
        #         raise sd.CallbackStop()

        stream = sd.OutputStream(
            channels=self.audio_data[filename].shape[1],
            device=OUTPUT_DEVICE,
            samplerate=self.samplerates[filename],
            blocksize=AUDIO_CHUNK_SZ,
            # callback=callback,
            # finished_callback=event.set,
        )
        stream.start()
        self.streams[filename] = stream

        def write_audio():
            current_index = 0
            while current_index < self.audio_len[filename]:
                chunk = self.audio_data[filename][current_index:current_index+AUDIO_CHUNK_SZ]
                chunk *= self.volumes[filename]
                if len(chunk) < AUDIO_CHUNK_SZ:
                    # NOTE: this line produces a dtype mismatch TypeError
                    # resolving this error by setting the correct dtype on np.zeros produces a pop
                    chunk = np.append(chunk, np.zeros([AUDIO_CHUNK_SZ - len(chunk), 2]), axis=0)

                # Effects
                effected = self.board(chunk, self.samplerates[filename], reset=False)
                stream.write(effected)

                self.audio_idx[filename] += AUDIO_CHUNK_SZ # TODO combine self.audio_idx[filename] & current_index
                current_index += AUDIO_CHUNK_SZ

            # print("waiting for stream to end")
            # event.wait()
            # print("ending stream")
            stream.stop()
            stream.close()
            # print("cleaning up")
            del self.streams[filename]
            del self.audio_data[filename]
            del self.samplerates[filename]
            del self.volumes[filename]
            del self.audio_idx[filename]
            del self.audio_len[filename]
            del self.file_active[filename]

        t = threading.Thread(target=write_audio)
        t.start()


    # Triggers the audio to start fading out. Thread is killed after FADE_TIME_s
    def stop_audio(self, filename):
        if filename in self.streams:

            self.file_active[filename] = 0
            
            playhead_idx = self.audio_idx[filename]

            fade_out_samples = int(FADE_TIME_s * self.samplerates[filename]) 
            if(self.audio_len[filename] - playhead_idx > fade_out_samples):

                # Add an extra buffer to account for audio player stopping one frame early
                # If this isn't here, we get audio pops when files are stopped (ie. scene changes)
                buffer_pad = AUDIO_CHUNK_SZ
                
                # Changing the length will make play_audio() stop @ appropriate time & handle cleanup
                self.audio_len[filename] = playhead_idx + fade_out_samples + buffer_pad

                # Create fade
                fade_out_curve = np.linspace(self.volumes[filename], 0, fade_out_samples)
                for i in range(0, fade_out_samples):
                    self.audio_data[filename][playhead_idx+i] *= fade_out_curve[i]

                # Add zeroes to the end to cover cases where we don't end on a frame boundary
                # Do this for two audio chunks at the end to account for player stopping one frame early
                for i in range(0, AUDIO_CHUNK_SZ + buffer_pad):
                    self.audio_data[filename][playhead_idx+fade_out_samples+i] = 0
                

    def load_audio(self, filename, filepath):
        audio, samplerate = sf.read(filepath)
        self.audio_data[filename] = np.append(audio.astype(np.float32), np.zeros([1024, 2], dtype=np.float32), axis=0)
        self.audio_len[filename] = len(audio)
        self.audio_idx[filename] = 0
        self.samplerates[filename] = samplerate
        self.volumes[filename] = 1.0
        self.file_active[filename] = 1


    # Calling this every 100ms on all playing files should give us time to select the next sound
    def get_audio_time_remaining(self):
        remaining_times_s = {}
        for filename in self.audio_data:
            remaining_samples = self.audio_len[filename] - self.audio_idx[filename]
            remaining_times_s[filename] = remaining_samples / self.samplerates[filename]

        return remaining_times_s


    def get_effect_knob_vals(self, simulation:Simulation):
        vals = [0.0, 0.0, 0.0]
        # vals = [
        #     simulation.param("climate_change").get_mean(),
        #     simulation.param("human_activity").get_mean(),
        #     simulation.param("fate").get_mean()
        # ]
        return vals

    # Expects normalized knob values (0-1)
    def knob_val_to_effect(self, knob_vals):
        dummy = 1

        # if self.sound_type == "music":
        #     # Distortion
        #     self.board[0].drive_db = knob_vals[0]*DISTORTION_MAX_dB
        #     self.board[1].gain_db = -knob_vals[0]*DISTORTION_MAX_dB # compensation gain

        #     # Filters
        #     lpf = 0
        #     hpf = 0
        #     if knob_vals[1] <= 0.5:
        #         # Scale 0-0.5 to lowpassfilter min to lowpassfilter max
        #         lpf = (knob_vals[1]/0.5)*(LOWPASS_FILTER_MAX_Hz-LOWPASS_FILTER_MIN_Hz)+LOWPASS_FILTER_MIN_Hz
        #         hpf = HIGHPASS_FILTER_MIN_Hz
        #     else:
        #         lpf = LOWPASS_FILTER_MAX_Hz
        #         # Scale 0.5-1 to highpassfilter min to highpassfilter max
        #         hpf = (((knob_vals[1]-0.5)/0.5)*(HIGHPASS_FILTER_MAX_Hz-HIGHPASS_FILTER_MIN_Hz)+HIGHPASS_FILTER_MIN_Hz)

        #     self.board[2].cutoff_frequency_hz = lpf
        #     self.board[3].cutoff_frequency_hz = hpf

        # elif self.sound_type == 'foley':
        #     knob3_max = 1
        #     knob3_min = 0
        #     # Delay
        #     self.board[0].feedback = scale_value(knob_vals[2], knob3_min, knob3_max, DELAY_FEEDBACK_MIN, DELAY_FEEDBACK_MAX)
        #     self.board[0].mix = scale_value(knob_vals[2], knob3_min, knob3_max, DELAY_MIX_MIN, DELAY_MIX_MAX)

        #     # Reverb
        #     self.board[1].room_size = scale_value(knob_vals[2], knob3_min, knob3_max, REVERB_ROOM_SIZE_MIN, REVERB_ROOM_SIZE_MAX)
        #     self.board[1].wet_level = scale_value(knob_vals[2], knob3_min, knob3_max, REVERB_WET_LEVEL_MIN, REVERB_WET_LEVEL_MAX)
        #     self.board[1].dry_level = scale_value(knob3_max-knob_vals[2], knob3_min, knob3_max, REVERB_DRY_LEVEL_MIN, REVERB_DRY_LEVEL_MAX)

def scale_value(value, in_min, in_max, out_min, out_max):
    # Check if the input range is valid
    if in_min >= in_max:
        raise ValueError("Invalid input range: in_min must be less than in_max")
    
    # Check if the output range is valid
    if out_min >= out_max:
        raise ValueError("Invalid output range: out_min must be less than out_max")
    
    # Calculate the scaled value
    scaled_value = (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
    
    # Clamp the scaled value within the output range
    if scaled_value < out_min:
        return out_min
    elif scaled_value > out_max:
        return out_max
    else:
        return scaled_value


# # For testing
# def main():
    
#     global exit_flag
#     print("Audio Playback Application")
#     print("Press 'q' to quit")
#     print(where_we_at_path)

#     # Load audio files
#     audio_files = {
#         # "thunderstorm.wav" : "thunderstorm.wav",
#         # Add test files as needed - these are cut off when set_scene() is called
#     }

#     # Initialize audio data and self.volumes
#     for filename, filepath in audio_files.items():
#         load_audio(filename, filepath)

#     # Start initial audio playback threads
#     for file in audio_files:
#         play_audio(file)

#     # Main application loop
#     while not exit_flag:
#         initialize_filepaths()

#         test_scene = "healthy_forest"
#         set_scene(test_scene)

#         while(1):   
#             update(test_scene)
#             time.sleep(0.1)

#     # Stop audio playback and join playback threads
#     for stream in self.streams.values():
#         stream.stop()
#         stream.close()
#     for t in threading.enumerate():
#         if t != threading.current_thread():
#             t.join()

#     print("Application exited successfully.")


# if __name__ == "__main__":
#     main()
