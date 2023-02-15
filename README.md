# micropython-es8388-driver
Micropython implementation of a ES8388-Audiocodec driver.
Partially based on the [es8388 implementation in the ESP-ADF](https://github.com/espressif/esp-adf/tree/master/components/audio_hal/driver/es8388).


# "public" interface
currently just for playing, recording should follow later.<br>
Uses some fix ESP32 audiokit settings wich will be adjustable later.<br>

## include
copy es8388.py file into your workfolder. Import the module.
```python
import es8388
```
or
```python
from es8388 import ES8388
```
## constructor
```python
ES8388(scl_pinnum, sda_pinnum, [address])
```
Codec will be initialize with default values. It needs to be started und unmute.

## constants
```python
OUTPUT_SPEAKER # based on circuit, here ESP32 audiokit v2.2
OUTPUT_HEADPHONES
OUTPUTS_STR # dict for Output to str conversion (OUTPUTS_STR[OUTPUT_SPEAKER])

MODE_ADC
MODE_DAC
MODE_ADC_DAC
MODE_LINE
```

## methods

### volume control
control volume of DAC in range 0-100(%)
```python
vol = ES8388.dacVolume() # read volume 
ES8388.dacVolume(50) # write volume
```
control output volume <br>
example for linear potentiometer connected to 9bit ADC:
```Python
# input of method is linear output logarithmic 
# read volume of headphone output in range 0-511
vol = ES8388.outputVolumeLog(output=OUTPUT_HEADPHONES, range=511)
# write volume of headphone output in range 0-511
ES8388.outputVolumeLog(ADC.read(), output=OUTPUT_HEADPHONES, range=511)
```
control output volume <br>
example for logarithmic potentiometer connected to 9bit ADC:
```Python
# input of method is logarithmic output linear 
# read volume of headphone output in range 0-511
vol = ES8388.outputVolumeLin(output=OUTPUT_HEADPHONES, range=511)
# write volume of headphone output in range 0-511
ES8388.outputVolumeLin(ADC.read(), output=OUTPUT_HEADPHONES, range=511)
```
mute/unmute

```Python
ES8388.mute()
ES8388.unmute()
```

### start/stop codec mode
every start will stop a running mode. <br>
stop running mode manually:
```python
ES8388.stop()
```
start bypass mode from Line input to headphones output:
```python
ES8388.startLineIn()
```
start dac mode and receive audio data via I2S Bus:
```python
ES8388.startDAC()
```
get current mode:
```python
cmode = ES8388.mode # -> None or ES8388.MODE_... 
```

# Test conditions
Hardware: ESP32 Audiokit v2.2 by Ai-Thinker. <br>
Firmware: Micropython v1.12 including ESP-IDF v3.3 and ESP-ADF v2.2 <br>