from piotimer import Piotimer as Timer
from ssd1306 import SSD1306_I2C
from machine import Pin, ADC, I2C, PWM
from fifo import Fifo
import utime
import array
import time
import network
import urequests as requests
import ujson
import network
from time import sleep

# ADC-converter
adc = ADC(26)

# OLED
i2c = I2C(1, scl = Pin(15), sda = Pin(14))
oled = SSD1306_I2C(128, 64, i2c)

# LEDs
led_onboard = Pin("LED", Pin.OUT)
led21 = PWM(Pin(21))
led21.freq(1000)

# Rotary Encoder
pushrot = Pin(12, mode = Pin.IN, pull = Pin.PULL_UP)

samplerate = 250
samples = Fifo(32)

# Menu selection variables and switch filtering
mode = 0
count = 0
switch_state = 0

# SSID credentials
ssid = 'KME661_GROUP_6'
password = 'KME661_GROUP_6'

# Kubios credentials
APIKEY = "pbZRUi49X48I56oL1Lq8y8NDjq6rPfzX3AQeNo3a"
CLIENT_ID = "3pjgjdmamlj759te85icf0lucv"
CLIENT_SECRET = "111fqsli1eo7mejcrlffbklvftcnfl4keoadrdv1o45vt9pndlef"

LOGIN_URL = "https://kubioscloud.auth.eu-west-1.amazoncognito.com/login"
TOKEN_URL = "https://kubioscloud.auth.eu-west-1.amazoncognito.com/oauth2/token"
REDIRECT_URI = "https://analysis.kubioscloud.com/v1/portal/login"

def read_adc(tid):
    samples.put(adc.read_u16())

def connect(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    
    # Wait for connection with timeout
    timeout = 10
    while not wlan.isconnected() and timeout > 0:
        utime.sleep(1)
        timeout -= 1
    
    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print(f"The IP address is: {ip}")
        return ip
    else:
        raise RuntimeError("Connection failed")

def welcome_text():
    oled.fill(1)
    messages = [("Welcome to", 26, 17), ("Group 6's", 29, 27), ("project!", 33, 37)]
    for message in messages:
        oled.text(message[0], message[1], message[2], 0)
    oled.show()
    utime.sleep(1)  # Using 1 second instead of milliseconds

def press_to_start():
    oled.fill(0)
    oled.text("Press to start", 4, 7, 1)
    oled.text("the measurement", 4, 17, 1)
    oled.text("------------->", 5, 55, 1)  # Less complex graphic
    oled.show()

def calculation_of_PPI_mean(data):
    sumPPI = sum(data)
    rounded_PPI = round(sumPPI / len(data), 0)
    return int(rounded_PPI)

def calculation_of_HR_mean(PPI_mean):
    return int(round(60 * 1000 / PPI_mean, 0))

def calculation_of_SDNN(data, PPI):
    squared_differences = [(x - PPI) ** 2 for x in data]
    SDNN = (sum(squared_differences) / (len(data) - 1)) ** 0.5
    return int(round(SDNN, 0))

def calculation_of_RMSSD(data):
    squared_differences = [(data[i + 1] - data[i]) ** 2 for i in range(len(data) - 1)]
    RMSSD = (sum(squared_differences) / (len(data) - 1)) ** 0.5
    return int(round(RMSSD, 0))

def calculation_of_SDSD(data):
    PP_array = [data[i + 1] - data[i] for i in range(len(data) - 1)]
    first_value = sum(x ** 2 for x in PP_array) / (len(PP_array) - 1)
    second_value = (sum(PP_array) / len(PP_array)) ** 2
    SDSD = (first_value - second_value) ** 0.5
    return int(round(SDSD, 0))

welcome_text()
avg_size = 128  
buffer = array.array('H',[0]*avg_size)

while True:
    press_to_start()
    new_state = pushrot.value()

    if new_state != switch_state:
        count += 1
        if count > 3:
            if new_state == 0:
                if mode == 0:
                    mode = 1
                else:
                    mode = 0
                led_onboard.value(1)
                time.sleep(0.15)
                led_onboard.value(0)
            switch_state = new_state
            count = 0
    else:
        count = 0
    utime.sleep(0.01)
    
    if mode == 1:
        count = 0
        switch_state = 0

        oled.fill(0)
        oled.show()
        
        x1 = -1
        y1 = 32
        m0 = 65535 / 2
        a = 1 / 10

        disp_div = samplerate / 25
        disp_count = 0
        capture_length = samplerate * 30  

        index = 0
        capture_count = 0
        subtract_old_sample = 0
        sample_sum = 0

        min_bpm = 30
        max_bpm = 200
        sample_peak = 0
        sample_index = 0
        previous_peak = 0
        previous_index = 0
        interval_ms = 0
        PPI_array = []
        
        brightness = 0

        tmr = Timer(freq = samplerate, callback = read_adc)

        while capture_count < capture_length:
            if not samples.empty():
                x = samples.get()
                disp_count += 1
        
                if disp_count >= disp_div:
                    disp_count = 0
                    m0 = (1 - a) * m0 + a * x
                    y2 = int(32 * (m0 - x) / 14000 + 35)
                    y2 = max(10, min(53, y2))
                    x2 = x1 + 1
                    oled.fill_rect(0, 0, 128, 9, 1)
                    oled.fill_rect(0, 55, 128, 64, 1)
                    if len(PPI_array) > 3:
                        actual_PPI = calculation_of_PPI_mean(PPI_array)
                        actual_HR = calculation_of_HR_mean(actual_PPI)
                        oled.text(f'HR:{actual_HR}', 2, 1, 0)
                        oled.text(f'PPI:{interval_ms}', 60, 1, 0)
                    oled.text(f'Timer:  {int(capture_count/samplerate)}s', 18, 56, 0)
                    oled.line(x2, 10, x2, 53, 0)
                    oled.line(x1, y1, x2, y2, 1)
                    oled.show()
                    x1 = x2
                    if x1 > 127:
                        x1 = -1
                    y1 = y2

                if subtract_old_sample:
                    old_sample = buffer[index]
                else:
                    old_sample = 0
                sample_sum = sample_sum + x - old_sample

           

                if subtract_old_sample:
                    sample_avg = sample_sum / avg_size
                    sample_val = x
                    if sample_val > (sample_avg * 1.05):
                        if sample_val > sample_peak:
                            sample_peak = sample_val
                            sample_index = capture_count

                    else:
                        if sample_peak > 0:
                            if (sample_index - previous_index) > (60 * samplerate / min_bpm):
                                previous_peak = 0
                                previous_index = sample_index
                            else:
                                if sample_peak >= (previous_peak*0.8):
                                    if (sample_index - previous_index) > (60 * samplerate / max_bpm):
                                        if previous_peak > 0:
                                            interval = sample_index - previous_index
                                            interval_ms = int(interval * 1000 / samplerate)
                                            PPI_array.append(interval_ms)
                                            brightness = 5
                                            led21.duty_u16(4000)
                                        previous_peak = sample_peak
                                        previous_index = sample_index
                        sample_peak = 0

                    if brightness > 0:
                        brightness -= 1
                    else:
                        led21.duty_u16(0)

                buffer[index] = x
                capture_count += 1
                index += 1
                if index >= avg_size:
                    index = 0
                    subtract_old_sample = 1

        tmr.deinit()
        
        while not samples.empty():
            x = samples.get()

    
        oled.fill(0)
        if len(PPI_array) >= 3:
            try:
                connect(ssid,password)
            except KeyboardInterrupt:
                machine.reset()
                
            try:
                response = requests.post(
                    url = TOKEN_URL,
                    data = 'grant_type=client_credentials&client_id={}'.format(CLIENT_ID),
                    headers = {'Content-Type':'application/x-www-form-urlencoded'},
                    auth = (CLIENT_ID, CLIENT_SECRET))
    
                response = response.json()
                access_token = response["access_token"]
                
                data_set = {
                    "type": "RRI",
                    "data": PPI_array,
                    "analysis": {"type": "readiness"}
                    }
      
                response = requests.post(
                    url = "https://analysis.kubioscloud.com/v2/analytics/analyze",
                    headers = { "Authorization": "Bearer {}".format(access_token),
                                "X-Api-Key": APIKEY },
                    json = data_set)
    
                response = response.json()
                print(response)
    
                SNS = round(response['analysis']['sns_index'], 2)
                PNS = round(response['analysis']['pns_index'], 2)
    
            except KeyboardInterrupt:
                machine.reset()
            
                
            PPI_mean =  calculation_of_PPI_mean(PPI_array)
            mean_HR = calculation_of_HR_mean(PPI_mean)
            SDNN = calculation_of_SDNN(PPI_array, PPI_mean)
            RMSSD = calculation_of_RMSSD(PPI_array)
            SDSD = calculation_of_SDSD(PPI_array)
         
            oled.text('PPI_mean:'+ str(int(PPI_mean)) +'ms', 0, 0, 1)
            oled.text('HR_mean:'+ str(int(mean_HR)) +'bpm', 0, 9, 1)
            oled.text('SDNN:'+str(int(SDNN)) +'ms', 0, 18, 1)
            oled.text('RMSSD:'+str(int(RMSSD)) +'ms', 0, 27, 1)

        else:
            oled.text('Error', 45, 10, 1)
            oled.text('Please restart', 8, 30, 1)
            oled.text('measurement', 20, 40, 1)
        oled.show()
        
        while mode == 1:
            new_state = pushrot.value()
            if new_state != switch_state:
                count += 1
                if count > 3:
                    if new_state == 0:
                        if mode == 0:
                            mode = 1
                        else:
                            mode = 0
                        led_onboard.value(1)
                        time.sleep(0.15)
                        led_onboard.value(0)
                    switch_state = new_state
                    count = 0
            else:
                count = 0
            utime.sleep(0.01)



























b