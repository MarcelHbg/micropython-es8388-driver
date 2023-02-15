# Audio amplifier driver
import math
from machine import I2C
from machine import Pin

SDA_PIN = 33 # tested with esp32 audiokit v2.2
SCL_PIN = 32 # tested with esp32 audiokit v2.2

FREQ = 100000
ES8388_ADDR = 0x10 # default tested with esp32 audiokit v2.2

# ES8388 register
ES8388_CONTROL1        = 0x00
ES8388_CONTROL2        = 0x01
ES8388_CHIPPOWER       = 0x02
ES8388_ADCPOWER        = 0x03
ES8388_DACPOWER        = 0x04
ES8388_CHIPLOPOW1      = 0x05
ES8388_CHIPLOPOW2      = 0x06
ES8388_ANAVOLMANAG     = 0x07
ES8388_MASTERMODE      = 0x08
# ADC
ES8388_ADCCONTROL1     = 0x09
ES8388_ADCCONTROL2     = 0x0a
ES8388_ADCCONTROL3     = 0x0b
ES8388_ADCCONTROL4     = 0x0c
ES8388_ADCCONTROL5     = 0x0d
ES8388_ADCCONTROL6     = 0x0e
ES8388_ADCCONTROL7     = 0x0f
ES8388_ADCCONTROL8     = 0x10
ES8388_ADCCONTROL9     = 0x11
ES8388_ADCCONTROL10    = 0x12
ES8388_ADCCONTROL11    = 0x13
ES8388_ADCCONTROL12    = 0x14
ES8388_ADCCONTROL13    = 0x15
ES8388_ADCCONTROL14    = 0x16
# DAC
ES8388_DACCONTROL1     = 0x17
ES8388_DACCONTROL2     = 0x18
ES8388_DACCONTROL3     = 0x19
ES8388_DACCONTROL4     = 0x1a
ES8388_DACCONTROL5     = 0x1b
ES8388_DACCONTROL6     = 0x1c
ES8388_DACCONTROL7     = 0x1d
ES8388_DACCONTROL8     = 0x1e
ES8388_DACCONTROL9     = 0x1f
ES8388_DACCONTROL10    = 0x20
ES8388_DACCONTROL11    = 0x21
ES8388_DACCONTROL12    = 0x22
ES8388_DACCONTROL13    = 0x23
ES8388_DACCONTROL14    = 0x24
ES8388_DACCONTROL15    = 0x25
ES8388_DACCONTROL16    = 0x26
ES8388_DACCONTROL17    = 0x27
ES8388_DACCONTROL18    = 0x28
ES8388_DACCONTROL19    = 0x29
ES8388_DACCONTROL20    = 0x2a
ES8388_DACCONTROL21    = 0x2b
ES8388_DACCONTROL22    = 0x2c
ES8388_DACCONTROL23    = 0x2d
ES8388_DACCONTROL24    = 0x2e
ES8388_DACCONTROL25    = 0x2f
ES8388_DACCONTROL26    = 0x30
ES8388_DACCONTROL27    = 0x31
ES8388_DACCONTROL28    = 0x32
ES8388_DACCONTROL29    = 0x33
ES8388_DACCONTROL30    = 0x34

# register values
DAC_OUTPUT_LOUT1 = b'\x04'
DAC_OUTPUT_LOUT2 = b'\x08'
DAC_OUTPUT_ROUT1 = b'\x10'
DAC_OUTPUT_ROUT2 = b'\x20'
DAC_OUTPUT_ALL = b'\x3c'

ADC_INPUT_LINPUT1_RINPUT1 = b'\x00'
ADC_INPUT_MIC1  = b'\x05'
ADC_INPUT_MIC2  = b'\x06'
ADC_INPUT_LINPUT2_RINPUT2 = b'\x50' # ESP-1AS LINEIN
ADC_INPUT_DIFFERENCE = b'\xf0'

#board definitions
BOARD_PA_GAIN = 10 # from LyraT 4.3
PA_ENABLE_GPIO = 21

TAG = 'ES8388'
def es_log(str: str, reg: int = None) -> None:
    if reg == None :
        print(TAG, str)
    else:
        print(TAG, str + "  reg(" + hex(reg) + ")")
        

class Reg:
    def __init__(self, scl_pinnum, sda_pinnum, address) -> None:
        self.i2c = I2C(scl=Pin(scl_pinnum), sda=Pin(sda_pinnum), freq=FREQ)
        self.i2c.start()
        addresses = self.i2c.scan()
        found = False
        for addr in addresses:
            if addr == address:
                found = True
        if found == False:
            raise AssertionError("ES8388 i2c address not found")


    def write(self, reg: int, byte) -> None:
        try:
            if type(byte) is bytes:
                self.i2c.writeto_mem(ES8388_ADDR, reg, byte)
            elif type(byte) is int:
                self.i2c.writeto_mem(ES8388_ADDR, reg, int.to_bytes(byte, 1, 'little'))
            else:
                raise TypeError("invalid byte input")
        except Exception as ex:
            es_log(TAG, ex)

    def read_byte(self, reg: int) -> bytes:
        return self.i2c.readfrom_mem(ES8388_ADDR, reg, 1)

    def read(self, reg: int) -> int:
        _reg = self.i2c.readfrom_mem(ES8388_ADDR, reg, 1)
        return int.from_bytes(_reg, 'little')

    def deinit(self) -> None:
        self.i2c.stop()
        #self.i2c.deinit() ?? not working

# private constants
ES_I2S_NORMAL = 0
ES_I2S_LEFT = 1
ES_I2S_RIGHT = 2
ES_I2S_DSP = 3

BIT_LENGTH_16BITS = 0x03
BIT_LENGTH_18BITS = 0x02
BIT_LENGTH_20BITS = 0x01
BIT_LENGTH_24BITS = 0x00
BIT_LENGTH_32BITS = 0x04

class ES8388:
    # public constants
    OUTPUT_SPEAKER = 0
    OUTPUT_HEADPHONES = 1
    OUTPUTS_STR = { 
        OUTPUT_SPEAKER : "speaker",
        OUTPUT_HEADPHONES : "headphones"
    }

    MODE_ADC = 0x01
    MODE_DAC = 0x02
    MODE_ADC_DAC = 0x03
    MODE_LINE = 0x04
    
    #################################################################################
    # Constructor and initialisation of the es8388
    #
    def __init__(self, scl_pinnum, sda_pinnum, address=ES8388_ADDR) -> None:
        es_log("initialising ...")
        self._regs = Reg(scl_pinnum, sda_pinnum, address)
        regs = self._regs

        self._mode = None
        self._out_volume = None

        # 11100100 -> 0xE4 -> 0.5 per 128RCK dacsoftramp + mute
        regs.write(ES8388_DACCONTROL3, b'\xE4')  # 0x04 mute/0x00 unmute&rampDAC unmute and  disabled digital volume control soft ramp

        # Chip Control and Power Management 
        regs.write(ES8388_CONTROL2, b'\x50')
        regs.write(ES8388_CHIPPOWER, b'\x00') #normal all and power up all

        # Disable the internal DLL to improve 8K sample rate
        regs.write(0x35, b'\xA0')
        regs.write(0x37, b'\xD0')
        regs.write(0x39, b'\xD0')

        regs.write(ES8388_MASTERMODE, b'\x00') #CODEC IN I2S SLAVE MODE

        # dac
        regs.write(ES8388_DACPOWER, b'\xC0')  #disable DAC and disable Lout/Rout/1/2
        regs.write(ES8388_CONTROL1, b'\x12')  #Enfr=0,Play&Record Mode,(0x17-both of mic&paly)
        #self.es_i2c.writeto_mem(ES8388_ADDR, ES8388_CONTROL2, 0)  #LPVrefBuf=0,Pdn_ana=0
        regs.write(ES8388_DACCONTROL1, b'\x18') #1a 0x18:16bit iis , 0x00:24
        regs.write(ES8388_DACCONTROL2, b'\x02')  #DACFsMode,SINGLE SPEED DACFsRatio,256
        regs.write(ES8388_DACCONTROL16, b'\x00') # 0x00 audio on LIN1&RIN1,  0x09 LIN2&RIN2
        regs.write(ES8388_DACCONTROL17, b'\x90') # only left DAC to left mixer enable 0db
        regs.write(ES8388_DACCONTROL20, b'\x90') # only right DAC to right mixer enable 0db
        regs.write(ES8388_DACCONTROL21, b'\x80') # set internal ADC and DAC use the same LRCK clock, ADC LRCK as internal LRCK
        regs.write(ES8388_DACCONTROL23, b'\x00') # vroi=0

        self._set_output_volume(True, 30) # OUT1 - range from 0 to 33, 30 equals 0db
        self._set_output_volume(False, 30) # OUT2 - range from 0 to 33, 30 equals 0db
        self._set_adc_dac_volume(ES8388.MODE_DAC, 0, 0)       # 0db

        regs.write(ES8388_DACPOWER, DAC_OUTPUT_ALL)  #0x3c Enable DAC and Enable Lout/Rout/1/2

        # adc
        regs.write(ES8388_ADCPOWER, b'\xFF')
        regs.write(ES8388_ADCCONTROL1, b'\xbb') # MIC Left and Right channel PGA gain

        regs.write(ES8388_ADCCONTROL2, ADC_INPUT_LINPUT2_RINPUT2) #0x50 for Linin2 #0x00 LINSEL & RINSEL, LIN1/RIN1 as ADC Input DSSEL,use one DS Reg11 DSR, LINPUT1-RINPUT1
        regs.write(ES8388_ADCCONTROL3, b'\x02')
        regs.write(ES8388_ADCCONTROL4, b'\x0c') # 16 Bits length and I2S serial audio data format
        regs.write(ES8388_ADCCONTROL5, b'\x02')  #ADCFsMode,singel SPEED,RATIO=256

        #ALC for Microphone
        self._set_adc_dac_volume(ES8388.MODE_ADC, 0, 0)      # 0db
        regs.write(ES8388_ADCPOWER, b'\x09')    # Power on ADC, enable LIN&RIN, power off MICBIAS, and set int1lp to low power mode
        
        # enable es8388 PA
        #self.pa_pin = Pin(PA_ENABLE_GPIO, Pin.OUT)
        #self.pa_power(True)

        es_log("init successfull")

    #################################################################################
    #
    #
    def _start(self, module):
        regs = self._regs
        prev_data = regs.read(ES8388_DACCONTROL21)
        #es_print("prev data", reg=prev_data)

        if module == ES8388.MODE_LINE:
            es_log("start LineIn bypass mode ...")
            regs.write(ES8388_DACCONTROL16, b'\x09') # 0x00 audio on LIN1&RIN1,  0x09 LIN2&RIN2 by pass enable
            regs.write(ES8388_DACCONTROL17, b'\x50') # left DAC to left mixer enable  and  LIN signal to left mixer enable 0db  : bupass enable
            regs.write(ES8388_DACCONTROL20, b'\x50') # right DAC to right mixer enable  and  LIN signal to right mixer enable 0db : bupass enable
            regs.write(ES8388_DACCONTROL21, b'\xC0') #enable adc clk
        else:
            regs.write(ES8388_DACCONTROL21, b'\x80')   #enable dac clk
        
        data = regs.read(ES8388_DACCONTROL21)
        #es_print("data", reg=data)

        if (prev_data != data):
            regs.write(ES8388_CHIPPOWER, b'\xF0')   #start state machine
            # regs.write(ES8388_CONTROL1, 0x16)
            # regs.write(ES8388_CONTROL2, 0x50)
            regs.write(ES8388_CHIPPOWER, b'\x00')   #start state machine
        
        if (module == ES8388.MODE_ADC or module == ES8388.MODE_ADC_DAC or module == ES8388.MODE_LINE):
            es_log("start ADC ...")
            regs.write(ES8388_ADCPOWER, b'\x00')   #power up adc and line in
        
        if (module == ES8388.MODE_DAC or module == ES8388.MODE_ADC_DAC or module == ES8388.MODE_LINE):
            es_log("start DAC ...")
            regs.write(ES8388_DACPOWER, b'\x3c')   #power up dac and line out
            self._set_voice_mute(False)
        
        es_log("start successfull")

    #################################################################################
    #
    #
    def _stop(self, module):
        regs = self._regs
        if module == ES8388.MODE_LINE:
            es_log("stop LineIn bypass mode ...")
            regs.write(ES8388_DACCONTROL21, b'\x80') #enable dac
            regs.write(ES8388_DACCONTROL16, b'\x00') # 0x00 audio on LIN1&RIN1,  0x09 LIN2&RIN2
            regs.write(ES8388_DACCONTROL17, b'\x90') # only left DAC to left mixer enable 0db
            regs.write(ES8388_DACCONTROL20, b'\x90') # only right DAC to right mixer enable 0db
            return 
        
        if (module == ES8388.MODE_DAC or module == ES8388.MODE_ADC_DAC):
            es_log("stop DAC ...")
            regs.write(ES8388_DACPOWER, b'\x00')
            self._set_voice_mute(True)      # 0db
            #regs.write(ES8388_DACPOWER, 0xC0)  #power down dac and line out
        
        if (module == ES8388.MODE_ADC or module == ES8388.MODE_ADC_DAC):
            es_log("stop ADC ...")
            #self.set_adc_dac_volume(ES8388.ES_MODULE_ADC, -96, 5)      # 0db
            regs.write(ES8388_ADCPOWER, b'\xFF')  #power down adc and line in
        
        if (module == ES8388.MODE_ADC_DAC):
            regs.write(ES8388_DACCONTROL21, b'\x9C')  #disable mclk
    #       regs.write(ES8388_CONTROL1, 0x00)
    #       regs.write(ES8388_CONTROL2, 0x58)
    #       regs.write(ES8388_CHIPPOWER, 0xF3)  #stop state machine


    #################################################################################
    # @brief Configure ES8388 DAC mute or not. Basically you can use this function to mute the output or unmute
    #
    # @param enable: enable or disable
    #
    # @return
    #     - (-1) Parameter error
    #     - (0)   Success
    #/
    def _set_voice_mute(self, enable: bool):
        reg = self._regs.read(ES8388_DACCONTROL3)
        reg &= 0xfb # set mask
        reg |= (enable << 2)
        self._regs.write(ES8388_DACCONTROL3, reg)
        if enable == True:
            es_log("mute", reg=reg)
        else:
            es_log("unmute", reg=reg)
    


    # @brief Configure ES8388 ADC and DAC volume. Basicly you can consider this as ADC and DAC gain
    #
    # @param mode:             set ADC or DAC or all
    # @param volume:           -96 ~ 0              for example Es8388SetAdcDacVolume(ES8388.ES_MODULE_ADC, 30, 6) means set ADC volume -30.5db
    # @param dot:              whether include 0.5. for example Es8388SetAdcDacVolume(ES8388.ES_MODULE_ADC, 30, 4) means set ADC volume -30db
    #
    # @return
    #     - (-1) Parameter error
    #     - (0)   Success
    #
    def _set_adc_dac_volume(self, module, volume: int, dot: int):
        regs = self._regs
        if volume < -96 or volume > 0:
            es_log(TAG, "volume < -96! or > 0!")
            if volume < -96:
                volume = -96
            else:
                volume = 0
        
        if dot >= 5:
            dot = 1
        else:
            dot = 0

        reg = (-volume << 1) + dot
        
        if module == ES8388.MODE_ADC or module == ES8388.MODE_ADC_DAC:
            regs.write(ES8388_ADCCONTROL8, reg)
            regs.write(ES8388_ADCCONTROL9, reg)  #ADC Right Volume=0db
            es_log("set ADC volume to: " + str(volume) + "db", reg=reg)
        
        if module == ES8388.MODE_DAC or module == ES8388.MODE_ADC_DAC:
            regs.write(ES8388_DACCONTROL5, reg) #RDACVOL
            regs.write(ES8388_DACCONTROL4, reg) #LDACVOL
            es_log("set DAC volume to: " + str(volume) + "db", reg=reg)

    #################################################################################

    def _set_output_volume(self, out: int, volume: int) -> None:
        if volume < 0 or volume > 33:
            es_log(TAG, "volume < 0! or > 33!")
            if volume < 0:
                volume = 0 # -45db -> mute
            else:
                volume = 33 # 4.5db
        # 30 equals 0db
        if out is self.OUTPUT_SPEAKER:
            #es_print("set output1 volume: " + str(volume))
            self._regs.write(ES8388_DACCONTROL24, volume) # Left Out1
            self._regs.write(ES8388_DACCONTROL25, volume) # Right Out1
        else: # out2
            #es_print("set output2 volume: " + str(volume))
            self._regs.write(ES8388_DACCONTROL26, volume) # Left Out2 
            self._regs.write(ES8388_DACCONTROL27, volume) # Right Out2


    #################################################################################

    def _set_mixer_volume(self, volume: int):
        if volume < 0 or volume > 7:
            es_log(TAG, "volume < 0! or > 7!")
            if volume < 0:
                volume = 0 # -15db
            else:
                volume = 7 # 6db
        # 5 equals 0db

        reg = self._regs.read(ES8388_DACCONTROL17)
        reg &= 0xc0 #just take mixer def
        reg |= ((~volume << 3) & 0x3f) # overwrite volume
        es_log("set bypass volume: " + str(volume), reg=reg)
        self._regs.write(ES8388_DACCONTROL17, reg) # Left mixer 
        self._regs.write(ES8388_DACCONTROL20, reg) # Right mixer

    #################################################################################

    def _pa_power(self, enable):
        if enable == True:
            self.pa_pin.on()
        else:
            self.pa_pin.off()

    #################################################################################

    def _i2s_config_fmt(self, module, fmt: int):
        if (module == ES8388.MODE_ADC or module == ES8388.MODE_ADC_DAC):
            reg = self._regs.read(ES8388_ADCCONTROL4)
            reg &= 0xfc
            reg |= fmt
            self._regs.write(ES8388_ADCCONTROL4, reg)
            es_log("set ADC i2s format", reg=reg)
        
        if (module == ES8388.MODE_DAC or module == ES8388.MODE_ADC_DAC):
            reg = self._regs.read(ES8388_DACCONTROL1)
            reg &= 0xf9
            reg |= (fmt << 1)
            self._regs.write(ES8388_DACCONTROL1, reg)
            es_log("set DAC i2s format", reg=reg)

    #################################################################################

    def _set_bits_per_sample(self, module, bits: int):
        if (module == ES8388.MODE_ADC or module == ES8388.MODE_ADC_DAC):
            reg = self._regs.read(ES8388_ADCCONTROL4)
            reg &= 0xe3
            reg |= (bits << 2)
            self._regs.write(ES8388_ADCCONTROL4, reg)
            es_log("set ADC bits per sample", reg=reg)
        
        if (module == ES8388.MODE_DAC or module == ES8388.MODE_ADC_DAC):
            reg = self._regs.read(ES8388_DACCONTROL1)
            reg &= 0xc7
            reg |= (bits << 3)
            self._regs.write(ES8388_DACCONTROL1, reg)
            es_log("set DAC bits per sample", reg=reg)

    #################################################################################

    def _readOutVolumeReg(self, out:int):
        reg = 0
        if out is self.OUTPUT_SPEAKER:
            reg = self._regs.read(ES8388_DACCONTROL24) #out1
        else:
            reg = self._regs.read(ES8388_DACCONTROL26) #ou12
        return reg

#######################################################################################
# Public API
#######################################################################################

    # set/get DAC volume in db in range 0-100
    def dacVolume(self, volume=None):
        # vol default = -96db
        # max is 0db = int 0
        # min is -96db = int 192 (mute)
        DAC_MAX = 192
        RESULT_MAX = 100
        if volume is None:
            return RESULT_MAX - round(RESULT_MAX*self._regs.read(ES8388_DACCONTROL5) / DAC_MAX) #RDACVOL
        else:
            if volume > RESULT_MAX:
                volume = RESULT_MAX
            if volume < 0:
                volume = 0
                
            reg = DAC_MAX - round(DAC_MAX*volume/RESULT_MAX)
            es_log("set dac volume: %d" %(volume), reg=reg)
            self._regs.write(ES8388_DACCONTROL5, reg) #RDACVOL
            self._regs.write(ES8388_DACCONTROL4, reg) #LDACVOL

    # get or set the output volume 
    # volume of codec in db from 0 to range
    def outputVolumeLog(self, volume:int=None, output:int=0, range:int=100):
        VOLMAX = 33 # db max of codec
        if volume is None:
            return round(range * self._readOutVolumeReg(output) / VOLMAX) # db

        else:
            # convert to codec range in db
            result = round(VOLMAX * volume / range)

            self._set_output_volume(output, result)
            es_log("set %s volume logarithmic: %d" %(self.OUTPUTS_STR[output], volume), reg=result)

    # get or set the output volume 
    # volume of codec is linearised from 0 to range
    def outputVolumeLin(self, volume:int=None, output:int=0, range:int=100):
        VOLMAX_LIN = 45 # lin max of codec = round 10^(33/20)
        if volume is None: # getter
            if self._out_volume is None: # volume was never set -> read fro register
                linear = 10 ** (self._readOutVolumeReg(output) / 20) # codec value to linear
                return round(range * linear / VOLMAX_LIN) # compute range

            else:
                return self._out_volume # avoid round error -> faster

        else: # setter
            result = (VOLMAX_LIN * volume / range) # compute to lin range
            if result > 1: # log10 has to be > 1 else volume is 0
                result = round(20*math.log10(result)) # convert linear value to codec log value
            else:
                result = 0
           
            self._out_volume = volume
            self._set_output_volume(output, result)
            es_log("set %s volume linear: %d" %(self.OUTPUTS_STR[output], volume), reg=result)
        
    def mute(self):
        self._set_voice_mute(True)
    
    def unmute(self):
        self._set_voice_mute(False)

    def startDac(self):
        if self._mode is not None:
            self.stop()
        self._start(ES8388.MODE_DAC)
        self._mode = ES8388.MODE_DAC

    def startLineIn(self):
        if self._mode is not None:
            self.stop()
        self._start(ES8388.MODE_LINE)
        self._mode = ES8388.MODE_LINE

    @property
    def mode(self):
        return self._mode

    def stop(self):
        self._stop(self._mode)
        self._mode = None

    def deinit(self):
        self._regs.write(ES8388_CHIPPOWER, b'\xFF')  #reset and stop es8388
        self._regs.deinit()
        es_log("deinit successfull")
