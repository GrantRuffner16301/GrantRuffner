/* This is a simple Bike light Arduino Sketch
Made by: Grant Ruffner
Email: grantruffner16301@gmail.com
Modified to include a 128x64 I2C OLED Status Display.

About:
This is for Tail-lights on the back of your bike
it has light red tail lights that will get brighter when 
brake is button is pressed and has left and right turn signal

How to wire:
1. I put a switch in to turn tail lights on from pin 5 to ground.
2. Brake I used a normally open button behind the brake lever
so when I squezzed the lever, the button released and becomes closed.
It is connected from pin 2 to ground.
3. To Connect the line of ws2812b leds connect the Leds Data in
to pin 6 and ground the leds to your power supply and the arduino board.
And connect the power to a 5 volt power suppy. I used a usb cord so i could
connect it to any power pack.
4. For the turn signals i used a SPDT spring back switch so it always
goes back to center when released. Center post goes to ground and Left post
goes to pin 3 and Right post goes to pin 4.
5. OLED: Connect SDA to A4 and SCL to A5. Power to 5V/GND.

Info:
If you use this Sketch please give credit where credit is due. You can change
it in any why that fits better for your need. It you find this sketch usefull
or have advice on how to improve it just send me a email. Enjoy.
*/

#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <FastLED.h>
#include <Wire.h>

// --- LED Settings ---
#define NUM_LEDS 8
#define DATA_PIN 6
#define LED_TYPE WS2812B
#define COLOR_ORDER GRB
#define Amber CRGB(255, 120, 0) // Close to automotive amber

// --- OLED Settings ---
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1 // Reset pin # (or -1 if sharing Arduino reset pin)
#define SCREEN_ADDRESS 0x3C // Check your OLED address, often 0x3C or 0x3D
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// --- Pin Definitions ---
const int pinBrake = 2;
const int pinLeft  = 3;
const int pinRight = 4;
const int pinTail  = 5;

CRGB leds[NUM_LEDS];

// --- Timing and Animation ---
unsigned long prevMillis = 0;
int animStep = 0;
const int stepSpeed = 70;   // Animation speed
const int totalSteps = 14;  // Animation cycle length

// --- State Tracking for OLED (Prevents screen flicker/lag) ---
bool lastBraking = false;
bool lastTurnL = false;
bool lastTurnR = false;
bool lastTailOn = false;
bool forceOLEDUpdate = true; // Forces a screen draw on startup

void setup() {
  delay(1000); // Safety startup delay
  
  // Initialize LEDS
  FastLED.addLeds<LED_TYPE, DATA_PIN, COLOR_ORDER>(leds, NUM_LEDS);
  FastLED.setBrightness(255);

  // Initialize Pins
  pinMode(pinBrake, INPUT_PULLUP);
  pinMode(pinLeft,  INPUT_PULLUP);
  pinMode(pinRight, INPUT_PULLUP);
  pinMode(pinTail,  INPUT_PULLUP);

  // Initialize OLED
  if(!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    // If screen fails to initialize, the LEDs will still work.
    // An infinite loop here would freeze the bike lights, so we just skip.
  } else {
    display.clearDisplay();
    display.display();
  }
}

void loop() {
  bool braking = !digitalRead(pinBrake);
  bool turnL   = !digitalRead(pinLeft);
  bool turnR   = !digitalRead(pinRight);
  bool tailOn  = !digitalRead(pinTail);

  // --- OLED Display Update Logic ---
  // Only update the screen if a button state has changed to prevent LED animation lag
  if (braking != lastBraking || turnL != lastTurnL || turnR != lastTurnR || tailOn != lastTailOn || forceOLEDUpdate) {
    
    // Save current states for the next check
    lastBraking = braking;
    lastTurnL = turnL;
    lastTurnR = turnR;
    lastTailOn = tailOn;
    forceOLEDUpdate = false;

    updateOLED(braking, turnL, turnR, tailOn);
  }

  // --- LED Animation Timer ---
  if (millis() - prevMillis >= stepSpeed) {
    prevMillis = millis();
    animStep = (animStep + 1) % totalSteps;
  }

  // --- LED Rendering ---
  for (int i = 0; i < NUM_LEDS; i++) {
    bool isLeft  = (i < 4);
    bool isRight = (i >= 4);

    // Default background state
    CRGB baseColor = CRGB::Black;
    if (braking) baseColor = CRGB::Red;
    else if (tailOn) baseColor = CRGB(60, 0, 0);

    // LEFT SIDE
    if (isLeft) {
      if (turnL) {
        CRGB sig = getDoubleChase(3 - i, animStep);
        if (sig == CRGB::Black) leds[i] = CRGB::Black;  // Animation gap → black
        else leds[i] = sig;                             // Amber fade
      }
      else {
        leds[i] = baseColor;      // Normal tail/brake
      }
    }

    // RIGHT SIDE
    else {
      if (turnR) {
        CRGB sig = getDoubleChase(i - 4, animStep);
        if (sig == CRGB::Black) leds[i] = CRGB::Black;
        else leds[i] = sig;
      }
      else {
        leds[i] = baseColor;
      }
    }
  }

  FastLED.show();
}

// ------------------------------------------------------------
// Updates the OLED screen with text/graphics based on state
// ------------------------------------------------------------
void updateOLED(bool braking, bool turnL, bool turnR, bool tailOn) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  
  // Draw Turn Signals
  display.setTextSize(2);
  display.setCursor(0, 0);
  if (turnL && turnR) {
    display.print(" HAZARD "); // Just in case both are pressed
  } else if (turnL) {
    display.print("<<< LEFT");
  } else if (turnR) {
    display.print("RIGHT >>>");
  } else {
    display.print("   ---   "); // Idle center graphic
  }

  // Draw Brake Status
  display.setCursor(0, 24);
  if (braking) {
    display.print("* BRAKE *");
  } else {
    // Blank line when not braking
  }

  // Draw Tail Light Status
  display.setTextSize(1);
  display.setCursor(0, 52);
  display.print("Tail Light: ");
  display.print(tailOn ? "ON" : "OFF");

  display.display(); // Push changes to the screen
}

// ------------------------------------------------------------
// Smooth fade sequential turn signal animation
// ------------------------------------------------------------
CRGB getDoubleChase(int ledPos, int currentStep) {
  const int fadeLength = 8;  // 4 fade-in + 4 fade-out

  // Offset each LED so they chase outward
  int phase = currentStep - ledPos * 2;

  if (phase < 0 || phase >= fadeLength)
    return CRGB::Black;

  uint8_t brightness;

  if (phase < 4) {
    // Fade in
    brightness = phase * 64;  // 0, 64, 128, 192
  } else {
    // Fade out
    brightness = (7 - phase) * 64; // 192, 128, 64, 0
  }

  CRGB out = Amber;
  out.nscale8(brightness);
  return out;
}
