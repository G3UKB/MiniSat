/*
* Azimuth and Elevation rotator system
*
* Control is by UDP commands from a client.
*
* Hardware used:
*  Arduino MEGA 2560
*  Arduino Ethernet Shield
*  Driver - Cytron 10Amp 5V-30V DC Motor Driver (2 Channels) 
*  Motors - Azimuth and Elevation worm gear motors with encoders
*/

// System
#include <SPI.h>                     // Needed for Arduino versions later than 0018
#include <math.h>                    // Math function lib

// Application
// These files together with their .cpp files must be in the same directory as this file.
// Don't ask me why, paths do not work.
// Take these files from the G3UKB/ArduinoLib repository.
#include "arduino_udp.h"
#include "arduino_motor.h"

// =======================================================================
// Network related
// =======================================================================
// MAC address must be specified
byte mac[] = {
  0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xEE
};
byte ip[] = {
  192, 168, 1, 178
};
// Local port to listen on
unsigned int localPort = 8888;
// Event port for status and events
unsigned int eventPort = 8889;

// Buffers for receiving and sending data
char  packet_buffer[UDP_TX_PACKET_MAX_SIZE];  // Buffer to hold incoming packet,
char  reply_buffer[128];                      // The response data
char  evnt_buffer[128];                       // The event data

// UDP instance pointer
Arduino_UDP *__udp;

// =======================================================================
// Motor related
// =======================================================================
// Azimuth pin allocations
const int M1DIR = 22;  // Motor 1 direction input
const int M1PWM = 4;   // Motor 1 PWM speed input
const int LIMIT_SW_FWD_AZ = 24; // Running forward limit of travel
const int LIMIT_SW_REV_AZ = 25; // Running forward limit of travel
const int SENSOR_AZ = 30; // Azimuth encoder output
const int SPAN_AZ = 360; // Degrees span
// Elevation pin allocations
const int M2DIR = 23;  // Motor 2 direction input
const int M2PWM = 5;   // Motor 2 PWM speed input
const int LIMIT_SW_FWD_EL = 26; // Running forward limit of travel
const int LIMIT_SW_REV_EL = 27; // Running reverse limit of travel
const int SENSOR_EL = 31; // Elevation encoder output
const int SPAN_EL = 90; // Degrees span

const int TYPE_AZ = 0;
const int TYPE_EL = 1;

// Motor instance pointer for both azimuth and elevation motors
Arduino_Motor *__az_motor;
Arduino_Motor *__el_motor;

// =======================================================================
// Misc
// =======================================================================
const int MAIN_LOOP_SLEEP = 10;   // 10ms sleep in main loop
int last_pos_az = 0;              // Last known position
int last_pos_el = 0;              // Last known position

// =======================================================================
// Setup system, called at start-of-day
// =======================================================================
void setup()
{
  // Init serial console
  Serial.begin(115200);

  // Create UDP instance
  __udp = new Arduino_UDP(mac, ip, localPort, eventPort);

  // Create motor instances
  __az_motor = new Arduino_Motor(TYPE_AZ, send_pos_az, M1DIR,M1PWM,SENSOR_AZ,LIMIT_SW_FWD_AZ,LIMIT_SW_REV_AZ,SPAN_AZ);
  __el_motor = new Arduino_Motor(TYPE_EL, send_pos_el, M2DIR,M2PWM,SENSOR_EL,LIMIT_SW_FWD_EL,LIMIT_SW_REV_EL,SPAN_EL);
  Serial.println("Mini-Sat running... ");
}

// =======================================================================
// Main execution loop, called for ever
// =======================================================================
void loop()
{ 
  // Check for request
  if (__udp->doRead(packet_buffer)) {
    // We have a request
    // Execute
    execute(packet_buffer);
    // Send response
    __udp->sendResponse(reply_buffer);
    
  } else {
    // Wait MAIN_LOOP_SLEEP ms to avoid spinning too fast
    delay(MAIN_LOOP_SLEEP);
  }
}

// ------------------------------------
// Callback to send position events
void send_pos_az(int pos) {
  static char azpos[4];

  if ((pos > (last_pos_az + 2)) || (pos < (last_pos_az - 2))) {
    //Serial.println(pos);
    sprintf(azpos, "az:%d", pos);
    __udp->sendEvent(azpos);
    last_pos_az = pos;
  }
}

void send_pos_el(int pos) {
    static char elpos[4];

  if ((pos > last_pos_el + 2) || (pos < last_pos_el - 2)) {
    //Serial.println(pos);
    sprintf(elpos, "el:%d", pos);
    __udp->sendEvent(elpos);
    last_pos_el = pos;
  }
}

// ------------------------------------
// API for commands
void execute(char *command) {
  /*
  * The command set is as follows. Commands are terminated strings.
  * Ping                      - "ping"    - connectivity test
  * Azimuth speed             - "[nnn]n   - set azimuth speed
  * Elevation speed           - "[nnn]m   - set elevation speed
  * Calibrate azimuth         - "calaz"   - run azimuth calibration
  * Calibrate elevation       - "calel"   - run elevation calibration
  * Set calibration azimuth   - "[nnn]m"  - set calibration value for azimuth
  * Set calibration elevation - "[nnn]n"  - set calibration value for elevation
  * Position azimuth          - "[nnn]z   - Run to a new azimuth position
  * Position elevation        - "[nnn]e"  - Run to a new elevation position
  * Home azimuth              - "homeaz"  - Go to home position, 0 degrees azimuth
  * Home elevation            - "homeel"  - Go to home position, 0 degrees elevation
  * Emergency stop            - "estop"   - Stop motors immediately
  */ 
  char *p;
  int value = 0;
  int cal;
 
  // Assume success
  strcpy(reply_buffer, "ack");
  if (strcmp(command, "poll") == 0) {
    // Nothing to do, just a connectivity check
  } else if (strcmp(command, "calaz") == 0) {
    // Calibrate azimuth
    cal = __az_motor->calibrate();
    if (cal == -1)
      strcpy(reply_buffer, "nak");
    else
      sprintf(reply_buffer, "%d", cal);
  } else if (strcmp(command, "calel") == 0) {
    // Calibrate elevation
    cal = __el_motor->calibrate();
    if (cal == -1)
      strcpy(reply_buffer, "nak");
    else
      sprintf(reply_buffer, "%d", cal);
  } else if (strcmp(command, "homeaz") == 0) {
    // Move to 0 deg azimuth
    if (!__az_motor->move_to_home())
      strcpy(reply_buffer, "nak");
  } else if (strcmp(command, "homeel") == 0) {
    // Move to 0 deg elevation
    if (!__el_motor->move_to_home())
      strcpy(reply_buffer, "nak");
  } else if (strcmp(command, "estop") == 0) {
    // Emergency - stop motors
    __az_motor->emergency_stop();
    __el_motor->emergency_stop();
    strcpy(reply_buffer, "nak");
  } else {
    // A speed, cal or position command?
    for(p=command; *p; p++) {
      if(*p >= '0' && *p <= '9') {
        // Numeric entered, so accumulate numeric value
        value = value*10 + *p - '0';
      } else if(*p == 'n') {
        // Instructed to change azimuth speed
        __az_motor->set_speed(value);
        __az_motor->set_backoff_speed(value);
        break;
      } else if(*p == 'm') {
        // Instructed to change elevation speed
        __el_motor->set_speed(value);
        __el_motor->set_backoff_speed(value);
        break;
      } else if(*p == 'm') {
        // Instructed to set azimuth calibration
        __az_motor->set_cal(value);
        break;
      } else if(*p == 'n') {
        // Instructed to set elevation calibration
        __el_motor->set_cal(value);
        break;
      } else if(*p == 'z') {
        // Instructed to move to new azimuth bearing
        __az_motor->move_to_position(value);
        break;
      } else if(*p == 'e') {
        // Instructed to move to new elevation
        __el_motor->move_to_position(value);
        break;
      } else {
        // Invalid command
        strcpy(reply_buffer, "nak:Invalid command");
        break;
      } 
    }
  }
}
