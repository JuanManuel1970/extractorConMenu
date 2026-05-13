#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <UniversalTelegramBot.h>
#include "DHT.h"
#include <WiFiManager.h>
#include <ArduinoOTA.h>
// =====================================================
// WIFI
// =====================================================

// const char* ssid = "Matias";
// const char* password = "CHEVI1970";

// =====================================================
// TELEGRAM
// =====================================================

#define BOT_TOKEN "7855306444:AAHdd062r9jtH9xA-aBXhpD5fZ8TGnUFaJQ"

String usuario1 = "1705318936";

// =====================================================
// DHT22
// =====================================================

#define DHTPIN 23
#define DHTTYPE DHT22

DHT dht(DHTPIN, DHTTYPE);

// =====================================================
// RELAY
// =====================================================

#define RELAY_PIN 18

#define RELAY_ON  HIGH
#define RELAY_OFF LOW

// =====================================================
// HUMEDAD
// =====================================================

float humedad_encendido = 80.0;
float humedad_apagado   = 75.0;

// Para probar:
// float humedad_encendido = 55.0;
// float humedad_apagado   = 50.0;

// =====================================================
// TIEMPOS
// =====================================================

unsigned long tiempoMaxEncendido = 15UL * 60UL * 1000UL;
unsigned long tiempoForzadoON    = 15UL * 60UL * 1000UL;

unsigned long intervaloLectura   = 3000;
unsigned long intervaloTelegram  = 1000;

// =====================================================
// VARIABLES
// =====================================================

bool estadoRelay = false;

unsigned long tiempoEncendido = 0;
unsigned long ultimaLectura = 0;
unsigned long ultimoCheckTelegram = 0;

unsigned long inicioForzadoON = 0;

float humedadActual = 0;
float temperaturaActual = 0;

unsigned long ahoraGlobal = 0;

// =====================================================
// MODOS
// =====================================================

enum Modo {
  AUTO,
  FORZADO_OFF,
  FORZADO_ON_TEMP
};

Modo modoActual = AUTO;

// =====================================================
// TELEGRAM
// =====================================================

WiFiClientSecure client;
UniversalTelegramBot bot(BOT_TOKEN, client);

// =====================================================
// BOTONES
// =====================================================

String tecladoPrincipal =
  "[[\"📊 Estado\", \"💨 Encender 15 min\"],"
  "[\"⛔ Apagar\", \"🤖 Automático\"]]";

// =====================================================
// FUNCIONES
// =====================================================

bool usuarioAutorizado(String chat_id) {
  return chat_id == usuario1;
}

// -----------------------------------------------------

void prenderRelay() {

  digitalWrite(RELAY_PIN, RELAY_ON);

  if (!estadoRelay) {

    tiempoEncendido = ahoraGlobal;

    Serial.println("🔵 RELAY ENCENDIDO");
  }

  estadoRelay = true;
}

// -----------------------------------------------------

void apagarRelay() {

  digitalWrite(RELAY_PIN, RELAY_OFF);

  if (estadoRelay) {
    Serial.println("⚪ RELAY APAGADO");
  }

  estadoRelay = false;
}

// -----------------------------------------------------

String textoModo() {

  if (modoActual == AUTO) return "AUTO";

  if (modoActual == FORZADO_OFF) return "FORZADO_OFF";

  if (modoActual == FORZADO_ON_TEMP) return "FORZADO_ON_15";

  return "DESCONOCIDO";
}

// -----------------------------------------------------

void enviarMenu(String chat_id) {

  bot.sendMessageWithReplyKeyboard(
    chat_id,
    "📲 Control del extractor",
    "",
    tecladoPrincipal,
    true
  );
}

// -----------------------------------------------------

void enviarEstado(String chat_id) {

  String mensaje = "";

  mensaje += "📊 ESTADO\n\n";

  mensaje += "Modo: ";
  mensaje += textoModo();
  mensaje += "\n";

  mensaje += "Humedad: ";
  mensaje += String(humedadActual, 1);
  mensaje += " %\n";

  mensaje += "Temperatura: ";
  mensaje += String(temperaturaActual, 1);
  mensaje += " °C\n";

  mensaje += "Extractor: ";

  if (estadoRelay) {
    mensaje += "ENCENDIDO";
  } else {
    mensaje += "APAGADO";
  }

  bot.sendMessageWithReplyKeyboard(
    chat_id,
    mensaje,
    "",
    tecladoPrincipal,
    true
  );
}

// -----------------------------------------------------

void activarAutomatico(String chat_id) {

  modoActual = AUTO;

  bot.sendMessageWithReplyKeyboard(
    chat_id,
    "🤖 Modo AUTOMATICO activado",
    "",
    tecladoPrincipal,
    true
  );
}

// -----------------------------------------------------

void activarApagadoForzado(String chat_id) {

  modoActual = FORZADO_OFF;

  apagarRelay();

  bot.sendMessageWithReplyKeyboard(
    chat_id,
    "⛔ Extractor APAGADO FORZADO",
    "",
    tecladoPrincipal,
    true
  );
}

// -----------------------------------------------------

void activarOn15(String chat_id) {

  modoActual = FORZADO_ON_TEMP;

  inicioForzadoON = ahoraGlobal;

  prenderRelay();

  Serial.println("💨 Modo ON15 activado");

  bot.sendMessageWithReplyKeyboard(
    chat_id,
    "💨 Extractor ENCENDIDO por 15 minutos",
    "",
    tecladoPrincipal,
    true
  );
}

// -----------------------------------------------------

void manejarTelegram() {

  int numMensajes = bot.getUpdates(bot.last_message_received + 1);

  while (numMensajes) {

    for (int i = 0; i < numMensajes; i++) {

      String chat_id = bot.messages[i].chat_id;
      String texto = bot.messages[i].text;

      Serial.println("Mensaje: " + texto);

      if (!usuarioAutorizado(chat_id)) {

        bot.sendMessage(chat_id,
                        "⛔ Usuario no autorizado",
                        "");

        continue;
      }

      // ==========================================
      // START
      // ==========================================

      if (texto == "/start") {

        enviarMenu(chat_id);
      }

      // ==========================================
      // ESTADO
      // ==========================================

      else if (texto == "/estado" ||
               texto == "📊 Estado") {

        enviarEstado(chat_id);
      }

      // ==========================================
      // ON15
      // ==========================================

      else if (texto == "/on15" ||
               texto == "💨 Encender 15 min") {

        activarOn15(chat_id);
      }

      // ==========================================
      // OFF
      // ==========================================

      else if (texto == "/off" ||
               texto == "⛔ Apagar") {

        activarApagadoForzado(chat_id);
      }

      // ==========================================
      // AUTO
      // ==========================================

      else if (texto == "/auto" ||
               texto == "🤖 Automático") {

        activarAutomatico(chat_id);
      }

      // ==========================================
      // DESCONOCIDO
      // ==========================================

      else {

        bot.sendMessageWithReplyKeyboard(
          chat_id,
          "Usá los botones 😄",
          "",
          tecladoPrincipal,
          true
        );
      }
    }

    numMensajes = bot.getUpdates(bot.last_message_received + 1);
  }
}

// =====================================================
// SETUP
// =====================================================

void setup() {

  Serial.begin(115200);

  pinMode(RELAY_PIN, OUTPUT);

  digitalWrite(RELAY_PIN, RELAY_OFF);

  delay(2000);

  dht.begin();

  // ==========================================
  // WIFI MANAGER
  // ==========================================

  WiFiManager wm;

  Serial.println("Conectando WiFi...");

  bool res = wm.autoConnect("Extractor-Setup");

  if (!res) {

    Serial.println("❌ No se pudo conectar al WiFi");

    ESP.restart();
  }

  Serial.println("✅ WiFi conectado");

  client.setInsecure();

  Serial.println("🔥 OTA FUNCIONANDO");

  ArduinoOTA.setHostname("Extractor-Banio");

  ArduinoOTA.onStart([]() {
    Serial.println("🔄 Iniciando actualización OTA");
  });

  ArduinoOTA.onEnd([]() {
    Serial.println("\n✅ OTA finalizada");
  });

  ArduinoOTA.onProgress([](unsigned int progress, unsigned int total) {
    Serial.printf("Progreso OTA: %u%%\r", (progress / (total / 100)));
  });

  ArduinoOTA.onError([](ota_error_t error) {
    Serial.printf("❌ Error OTA [%u]\n", error);
  });

  ArduinoOTA.begin();

  Serial.println("✅ OTA listo");
}

// =====================================================
// LOOP
// =====================================================

void loop() {

  yield();

  ArduinoOTA.handle();

  unsigned long ahora = millis();

  ahoraGlobal = ahora;

  // ==========================================
  // TELEGRAM
  // ==========================================

  if (ahora - ultimoCheckTelegram >= intervaloTelegram) {

    ultimoCheckTelegram = ahora;

    manejarTelegram();
  }

  // ==========================================
  // SENSOR
  // ==========================================

  if (ahora - ultimaLectura >= intervaloLectura) {

    ultimaLectura = ahora;

    float h = dht.readHumidity();
    float t = dht.readTemperature();

    if (isnan(h) || isnan(t)) {

      Serial.println("❌ Error leyendo sensor");

      return;
    }

    humedadActual = h;
    temperaturaActual = t;

    Serial.print("Humedad: ");
    Serial.print(h);

    Serial.print(" % | Temp: ");

    Serial.print(t);

    Serial.println(" °C");
  }

  // ==========================================
  // AUTO
  // ==========================================

  if (modoActual == AUTO) {

    if (!estadoRelay &&
        humedadActual >= humedad_encendido) {

      prenderRelay();
    }

    if (estadoRelay &&
        humedadActual <= humedad_apagado) {

      Serial.println("💧 Apagado por humedad");

      apagarRelay();
    }

    if (estadoRelay &&
        (ahoraGlobal - tiempoEncendido >= tiempoMaxEncendido)) {

      Serial.println("⏱️ Apagado por tiempo máximo");

      apagarRelay();
    }
  }

  // ==========================================
  // FORZADO OFF
  // ==========================================

  if (modoActual == FORZADO_OFF) {

    if (estadoRelay) {

      apagarRelay();
    }
  }

  // ==========================================
  // FORZADO ON 15 MIN
  // ==========================================

  if (modoActual == FORZADO_ON_TEMP) {

    if (!estadoRelay) {

      prenderRelay();
    }

    if (ahoraGlobal - inicioForzadoON >= tiempoForzadoON) {

      Serial.println("🤖 Fin de ON15. Volviendo a AUTO");

      apagarRelay();

      modoActual = AUTO;
    }
  }
}