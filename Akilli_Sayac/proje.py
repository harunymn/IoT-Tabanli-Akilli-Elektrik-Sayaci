# LIBRARYS
import time
from Adafruit_CharLCD import Adafruit_CharLCD
import serial
import paho.mqtt.client as mqtt
import json
from gpiozero import LED
from gpiozero import Button
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import numpy as np
from datetime import datetime
import locale
import xlsxwriter

locale.setlocale(locale.LC_ALL, '')


# RELAY - PINS
role = LED(21)
code_state = LED(16)
button = Button(20)

def relay_button():
    global relay_state
    if relay_state == True:
        relay_state = False
    else:
        relay_state = True


# ALARM - email
mail = smtplib.SMTP("smtp.gmail.com",587)
mail.ehlo()
mail.starttls()
mail.login("akilli.elektrik.sayaci@gmail.com","smart01meter")
alarm = 100000000000
def limit_alarm(alarm,spended_energy):
    mesaj = MIMEMultipart()
    mesaj["From"] = "akilli.elektrik.sayaci@gmail.com"           # Gönderen
    mesaj["To"] = "harunyaman97@outlook.com"             # Alıcı
    mesaj["Subject"] = "Akıllı Sayaç - Limit Uyarısı"    # Konusu
    body = "Uyarı: Limit Aşıldı!!" + """ 
Belirlenen Limit Değeri: """ + str(alarm) + " Watt" + """
Şu anki değer: """ + str(spended_energy) + " Watt"
    body_text = MIMEText(body, "plain")  #
    mesaj.attach(body_text)
    mail.sendmail(mesaj["From"], mesaj["To"], mesaj.as_string())


# Mini LCD DISPLAY
lcd = Adafruit_CharLCD(rs=26, en=19,d4=13, d5=6, d6=5, d7=11,cols=16, lines=2)
lcd.clear()


# SERIAL COMMUNICATION - UART
ser = serial.Serial ("/dev/ttyS0", 115200)#Open port with baud rate
print(ser.isOpen())


# CLOUD SERVICE
broker = "demo.thingsboard.io"
accessToken = "3BCOh34U3e5ePOHcekyI"
telemetryTopic = "v1/devices/me/telemetry"
attributesTopic = "v1/devices/me/attributes"
rpcReqTopic = "v1/devices/me/rpc/request/+"

def on_connect(client, userdata, flags, rc):
    if rc==0:
        client.subscribe(topic=attributesTopic,qos=1)
        client.subscribe(topic=rpcReqTopic,qos=1)
        print("Bağlantı başarılı - rc= "+str(rc))
    else:
        print("Bağlantı başarısız! -rc="+str(rc))

def on_message(client,userdata,msg):
    global alarm
    global alarm_state
    global relay_state
    global alarm_control

    data=json.loads(msg.payload.decode("utf-8"))
    if msg.topic == attributesTopic:
        if "alarm" in data:
            alarm = data["alarm"]
            alarm_control = 0
    else:
        if data["method"] == "setLed":
            relay_state = data["params"]
        elif data["method"] == "setValue":         
            alarm_state = data["params"]

client=mqtt.Client()
client.on_connect=on_connect
client.on_message=on_message
client.username_pw_set(username=accessToken)
client.connect(broker)
client.loop_start()
telemetryData=dict()
telemetryPower=dict()
telemetryCurrent=dict()
telemetryBill=dict()
telemetryTime=dict()
telemetryVolt=dict()


# WHILE LOOP (ALL FUNCTIONS)
voltage = 227
spended_energy = 0
timer = 0
bill = 0
alarm_control = 0
zed = "for send email again"
alarm_state = False
relay_state = False
relay_count = 0
report = np.array([['Tarih','Akım(A)','Güç(W)','Harcanan Elektrik(W)','Fatura(TL)']])
datta = []

while True:
    # Code is Run?
    code_state.on()
    
    # Relay
    button.when_pressed = relay_button
    if relay_state == True:
        role.on()
    elif relay_state == False:
        role.off()
    
    
    # Arduino
    sensor_data = ser.read(5)  #read serial port
    sensor_data = float(sensor_data)
    
    
    # Data Progressing
    if relay_state == True:
        sensor_data = sensor_data - 510
        sensor_data = abs(sensor_data)
        datta.append(sensor_data)
        sensor_data = max(datta)
        if timer==2:
            old_data = sensor_data
        if timer % 8 == 0:
            datta = []
        if (len(datta) == 1 or len(datta)==2) and old_data > sensor_data:
            sensor_data = old_data
        old_data = sensor_data
        current = sensor_data / 25.6
        power = voltage * current
        energy = power / 3600 * 2 # for 2 seconds
        spended_energy = spended_energy + energy
        bill = spended_energy * 0.72 / 1000
    else:
        old_data = 0
        current = 0
        power = 0
    power = round(power,2)
    bill = round (bill , 2)
    current = round(current , 2)
    spended_energy = round (spended_energy, 2)
    
    
    # Cloud
    telemetryData["spended_energy"] = str(spended_energy)
    telemetryPower["power"] = str(power)
    telemetryCurrent["current"] = str(current)
    telemetryTime["timer"] = str(timer)
    telemetryBill["bill"] = str(bill)
    telemetryVolt["voltage"] = str(voltage)
    client.publish(topic=telemetryTopic, payload=json.dumps(telemetryTime), qos=1, retain=False)
    client.publish(topic=telemetryTopic, payload=json.dumps(telemetryData), qos=1, retain=False)
    client.publish(topic=telemetryTopic, payload=json.dumps(telemetryCurrent), qos=1, retain=False)
    client.publish(topic=telemetryTopic, payload=json.dumps(telemetryBill), qos=1, retain=False)
    client.publish(topic=telemetryTopic, payload=json.dumps(telemetryPower), qos=1, retain=False)
    client.publish(topic=telemetryTopic, payload=json.dumps(telemetryVolt), qos=1, retain=False)
    
    
    # Report
    time_now = datetime.strftime(datetime.now(), '%c')
    report = np.concatenate((report,[[time_now,current,power,spended_energy,bill]]))
    rapor= xlsxwriter.Workbook("rapor.xlsx")
    rapor_sayfa= rapor.add_worksheet("report")
    rapor_sayfa.write("A1", 'Tarih')
    rapor_sayfa.write("B1", 'Akım(A)')
    rapor_sayfa.write("C1", 'Güç(W)')
    rapor_sayfa.write("D1", 'Harcanan Elektrik(W)')
    rapor_sayfa.write("E1", 'Fatura(TL)')
    if timer==1000:
        for i in range(495):
            for j in range(5):
                rapor_sayfa.write(i+1,j,report[i+1][j])
        rapor.close()
        break
    
    
    # Alarm
    if spended_energy > alarm and alarm_state == True and alarm_control == 0:
        limit_alarm(alarm, spended_energy)
        zed = timer + 12
        alarm_control = 1
    if timer == zed:
        limit_alarm (alarm, spended_energy)
    if alarm_state == False:
        alarm_control = 0
    
    
    # Lcd Panel
    unit = " W"
    kw_w = spended_energy
    if spended_energy >= 1000:
        kw_w = spended_energy / 1000
        unit = " kW"
    kw_w = round(kw_w, 1)
    k = str(kw_w)
    d = str(bill)
    dd ="Energy= " + k + unit + "\nBill  = " + d + " TL"
    lcd.message(dd)
    
    
    # Local
    print("Power = ", power, "W")
    print("Spended Energy =", kw_w, unit)
    print("Current =", current,"A")
    print("Bill = ", bill, "TL")
    print("Alarm state: ",alarm_state," & ", alarm, "Watt")
    print("Relay state: ", relay_state)
    print("")
    timer += 2
    time.sleep(2)
    lcd.clear()

mail.close() 





