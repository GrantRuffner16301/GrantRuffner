#include <EEPROM.h>
#include <Adafruit_NeoPixel.h>
#define LED_PIN 6  
#define LED_COUNT 12
#define BUTTON 2 
#define Speedpush 3
 int pres1 = 0;
byte selectedEffect=0;
int kitspeed=4;
Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

void setup() {
 pinMode(BUTTON,INPUT);
  pinMode(Speedpush,INPUT);
  attachInterrupt (digitalPinToInterrupt (BUTTON), changeEffect, CHANGE); 
  attachInterrupt (digitalPinToInterrupt (Speedpush), ButtonScan, CHANGE);
  strip.begin();
  strip.show(); 
 delay(50);
}

void loop() { 
  ButtonScan();
  EEPROM.get(0,selectedEffect); 
  if(selectedEffect>8) { 
    selectedEffect=0;
    EEPROM.put(0,0); 
  }
   
  switch(selectedEffect) {
        case 0: {
           KittScanner(kitspeed*10, 4, 0xFF0000); // Red
          break;
        }
        case 1: {
           KittScanner(kitspeed*10, 5, 0xFF4400); // orange
          break;
        }
        case 2: {
           KittScanner(kitspeed*10, 5, 0x0000FF); // blue
          break;
        }
        case 3: {
           KittScanner(kitspeed*10, 5, 0x550055); // Purlple
          break;
        }
        case 4: {
            KittScanner(kitspeed*10, 5,0x00FF00); // green
          break;
        }
        case 5: {
            KittScanner(kitspeed*10, 5, 0xFF6666); // PINK
          break;
        }     
        case 6: {
            KittScanner(kitspeed*10, 5, 0x00FFFF); // clay
          break;
        }
        case 7: {
            KittScanner(kitspeed*10, 5, 0xCC8800); // yellow
          break;
        }
        case 8:{
             KittScanner(kitspeed*10, 5, 0xFFFFFF);  // white
          break;
          }
       }
}
  void changeEffect() {
  if (digitalRead (BUTTON) == HIGH) {
    selectedEffect++;
    EEPROM.put(0, selectedEffect);
    asm volatile ("  jmp 0");
  }

}
void ButtonScan() {
if(digitalRead(Speedpush) == HIGH){
    if(pres1==0){
    kitspeed++;
    pres1=1;
   }
}
  else{
    pres1=0;
   }  

 if(kitspeed == 8) {
 kitspeed=2;
 }
 delay(50);
}

uint32_t dimColor(uint32_t color, uint8_t width){
   return (((color&0xFF0000)/width)&0xFF0000) + (((color&0x00FF00)/width)&0x00FF00) + (((color&0x0000FF)/width)&0x0000FF);
}

void KittScanner(uint16_t speed, uint8_t width, uint32_t color) {
  uint32_t old_val[LED_COUNT];
      for (int count = 1; count<LED_COUNT; count++) {
      strip.setPixelColor(count, color);
      old_val[count] = color;
      for(int x = count; x>0; x--) {
        old_val[x-1] = dimColor(old_val[x-1], width);
        strip.setPixelColor(x-1, old_val[x-1]); 
      }
      strip.show();
      delay(speed);
      }
    for (int count = LED_COUNT-1; count>=0; count--) {
      strip.setPixelColor(count, color);
      old_val[count] = color;
      for(int x = count; x<=LED_COUNT ;x++) {
        old_val[x-1] = dimColor(old_val[x-1], width);
        strip.setPixelColor(x+1, old_val[x+1]);
      }
      strip.show();
      delay(speed);
    }
  }
