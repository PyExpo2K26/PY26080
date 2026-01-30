// ================= PWM SETTINGS =================
const int PWMSpeedChannelA = 0;
const int PWMSpeedChannelB = 1;
const int PWMLightChannel  = 2;

const int PWMFreq = 1000;      // 1 kHz
const int PWMResolution = 8;   // 8-bit (0-255)

// ================= MOTOR PINS =================
const int ENA = 5;
const int IN1 = 18;
const int IN2 = 19;

const int ENB = 17;
const int IN3 = 16;
const int IN4 = 4;

const int LIGHT_PIN = 21;

// ================= SETUP =================
void setup() {
  setUpPinModes();
}

// ================= LOOP (Demo) =================
void loop() {
  moveForward(200);
  delay(2000);

  moveBackward(200);
  delay(2000);

  stopCar();
  setLightBrightness(255); // full brightness
  delay(2000);

  setLightBrightness(50);  // dim
  delay(2000);
}

// ================= PIN SETUP =================
void setUpPinModes() {
  // Motor direction pins
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);

  // Setup PWM channels
  ledcSetup(PWMSpeedChannelA, PWMFreq, PWMResolution);
  ledcSetup(PWMSpeedChannelB, PWMFreq, PWMResolution);
  ledcSetup(PWMLightChannel,  PWMFreq, PWMResolution);

  // Attach PWM to pins
  ledcAttachPin(ENA, PWMSpeedChannelA);
  ledcAttachPin(ENB, PWMSpeedChannelB);
  ledcAttachPin(LIGHT_PIN, PWMLightChannel);

  stopCar();
}

// ================= MOTOR FUNCTIONS =================
void moveForward(int speed) {
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);

  ledcWrite(PWMSpeedChannelA, speed);
  ledcWrite(PWMSpeedChannelB, speed);
}

void moveBackward(int speed) {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);

  ledcWrite(PWMSpeedChannelA, speed);
  ledcWrite(PWMSpeedChannelB, speed);
}

void stopCar() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, LOW);

  ledcWrite(PWMSpeedChannelA, 0);
  ledcWrite(PWMSpeedChannelB, 0);
}

// ================= LIGHT CONTROL =================
void setLightBrightness(int brightness) { // 0-255
  ledcWrite(PWMLightChannel, brightness);
}
