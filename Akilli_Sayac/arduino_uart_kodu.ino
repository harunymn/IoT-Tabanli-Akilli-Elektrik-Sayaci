#include <SoftwareSerial.h>
#define sensorPin A0 
int veri=0;

SoftwareSerial mySerial(2, 3); // RX, TX

void setup() {
  mySerial.begin(115200); 
  analogReference(EXTERNAL);
  }
  
void loop(){
  veri = analogRead(sensorPin);
  mySerial.println(veri);
  delay(500); 
  }
