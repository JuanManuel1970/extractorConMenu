#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <UniversalTelegramBot.h>
#include "DHT.h"
#include <WiFiManager.h>
#include <ArduinoOTA.h>
#include <Preferences.h>

#define BOT_TOKEN "7855306444:AAHdd062r9jtH9xA-aBXhpD5fZ8TGnUFaJQ"

String adminID = "1705318936";
String usuarios = "";

#define DHTPIN 23
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);

#define RELAY_PIN 18
#define RELAY_ON  HIGH
#define RELAY_OFF LOW

float humedad_encendido = 80.0;
float humedad_apagado   = 75.0;
int minutosTimer = 15;

unsigned long tiempoMaxEncendido;
unsigned long tiempoForzadoON;

unsigned long intervaloLectura   = 3000;
unsigned long intervaloTelegram  = 1000;

// Espera de 40 minutos después del corte por tiempo
unsigned long tiempoEsperaReintento = 40UL * 60UL * 1000UL;
unsigned long inicioEsperaReintento = 0;
bool esperandoReintento = false;

bool estadoRelay = false;
bool sensorLeido = false;

unsigned long tiempoEncendido = 0;
unsigned long ultimaLectura = 0;
unsigned long ultimoCheckTelegram = 0;
unsigned long inicioForzadoON = 0;

float humedadActual = 0;
float temperaturaActual = 0;

unsigned long ahoraGlobal = 0;

enum Modo {
  AUTO,
  FORZADO_OFF,
  FORZADO_ON_TEMP
};

Modo modoActual = AUTO;

WiFiClientSecure client;
UniversalTelegramBot bot(BOT_TOKEN, client);
Preferences prefs;

String tecladoPrincipal =
  "[[\"📊 Estado\", \"💨 Encender 15 min\"],"
  "[\"⛔ Apagar\", \"🤖 Automático\"],"
  "[\"⚙️ Config\"]]";

// =====================================================
// USUARIOS
// =====================================================

bool esAdmin(String chat_id) {
  return chat_id == adminID;
}

bool usuarioExiste(String id) {
  String lista = "," + usuarios;
  return lista.indexOf("," + id + ",") >= 0;
}

bool usuarioAutorizado(String chat_id) {
  if (chat_id == adminID) return true;
  return usuarioExiste(chat_id);
}

void guardarUsuarios() {
  prefs.putString("lista", usuarios);
}

void agregarUsuario(String id) {
  if (id == adminID) return;

  if (!usuarioExiste(id)) {
    usuarios += id;
    usuarios += ",";
    guardarUsuarios();
  }
}

void borrarUsuario(String id) {
  usuarios.replace(id + ",", "");
  guardarUsuarios();
}

String extraerParametro(String texto, String comando) {
  texto.replace(comando, "");
  texto.trim();
  return texto;
}

// =====================================================
// CONFIGURACION
// =====================================================

void actualizarTimers() {
  tiempoMaxEncendido = minutosTimer * 60UL * 1000UL;
  tiempoForzadoON    = minutosTimer * 60UL * 1000UL;
}

void cargarConfiguracion() {
  humedad_encendido = prefs.getFloat("humON", 80.0);
  humedad_apagado   = prefs.getFloat("humOFF", 75.0);
  minutosTimer      = prefs.getInt("timer", 15);

  actualizarTimers();
}

void guardarConfiguracion() {
  prefs.putFloat("humON", humedad_encendido);
  prefs.putFloat("humOFF", humedad_apagado);
  prefs.putInt("timer", minutosTimer);
}

void enviarConfig(String chat_id) {
  String mensaje = "";

  mensaje += "⚙️ CONFIGURACION\n\n";

  mensaje += "Encendido: ";
  mensaje += String(humedad_encendido, 1);
  mensaje += "%\n";

  mensaje += "Apagado: ";
  mensaje += String(humedad_apagado, 1);
  mensaje += "%\n";

  mensaje += "Timer: ";
  mensaje += String(minutosTimer);
  mensaje += " min\n\n";

  mensaje += "Cambiar valores:\n";
  mensaje += "/seton 80\n";
  mensaje += "/setoff 75\n";
  mensaje += "/settimer 15";

  bot.sendMessageWithReplyKeyboard(
    chat_id,
    mensaje,
    "",
    tecladoPrincipal,
    true
  );
}

// =====================================================
// RELAY / ESTADO
// =====================================================

void prenderRelay() {
  digitalWrite(RELAY_PIN, RELAY_ON);

  if (!estadoRelay) {
    tiempoEncendido = ahoraGlobal;
    Serial.println("🔵 RELAY ENCENDIDO");
  }

  estadoRelay = true;
}

void apagarRelay() {
  digitalWrite(RELAY_PIN, RELAY_OFF);

  if (estadoRelay) {
    Serial.println("⚪ RELAY APAGADO");
  }

  estadoRelay = false;
}

String textoModo() {
  if (modoActual == AUTO) return "AUTO";
  if (modoActual == FORZADO_OFF) return "FORZADO_OFF";
  if (modoActual == FORZADO_ON_TEMP) return "FORZADO_ON_15";

  return "DESCONOCIDO";
}

void enviarMenu(String chat_id) {
  bot.sendMessageWithReplyKeyboard(
    chat_id,
    "📲 Control del extractor",
    "",
    tecladoPrincipal,
    true
  );
}

void enviarEstado(String chat_id) {
  String mensaje = "";

  mensaje += "📊 ESTADO\n\n";

  mensaje += "Modo: ";
  mensaje += textoModo();
  mensaje += "\n";

  if (sensorLeido) {
    mensaje += "Humedad: ";
    mensaje += String(humedadActual, 1);
    mensaje += " %\n";

    mensaje += "Temperatura: ";
    mensaje += String(temperaturaActual, 1);
    mensaje += " °C\n";
  } else {
    mensaje += "Sensor: sin lectura válida todavía\n";
  }

  mensaje += "Extractor: ";

  if (estadoRelay) {
    mensaje += "ENCENDIDO";

    unsigned long minutos =
      (ahoraGlobal - tiempoEncendido) / 60000UL;

    mensaje += "\nTiempo encendido: ";
    mensaje += String(minutos);
    mensaje += " min";

  } else {
    mensaje += "APAGADO";
  }

  if (esperandoReintento) {
    unsigned long transcurrido =
      ahoraGlobal - inicioEsperaReintento;

    unsigned long restante = 0;

    if (transcurrido < tiempoEsperaReintento) {
      restante =
        (tiempoEsperaReintento - transcurrido) / 60000UL;
    }

    mensaje += "\nEspera reintento: ";
    mensaje += String(restante);
    mensaje += " min";
  }

  bot.sendMessageWithReplyKeyboard(
    chat_id,
    mensaje,
    "",
    tecladoPrincipal,
    true
  );
}

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

void activarOn15(String chat_id) {
  modoActual = FORZADO_ON_TEMP;

  inicioForzadoON = ahoraGlobal;

  prenderRelay();

  Serial.println("💨 Modo ON15 activado");

  bot.sendMessageWithReplyKeyboard(
    chat_id,
    "💨 Extractor ENCENDIDO por " + String(minutosTimer) + " minutos",
    "",
    tecladoPrincipal,
    true
  );
}

// =====================================================
// TELEGRAM
// =====================================================

void manejarTelegram() {
  int numMensajes = bot.getUpdates(bot.last_message_received + 1);

  while (numMensajes) {
    for (int i = 0; i < numMensajes; i++) {
      String chat_id = bot.messages[i].chat_id;
      String texto = bot.messages[i].text;

      Serial.println("Mensaje: " + texto);

      if (!usuarioAutorizado(chat_id)) {
        bot.sendMessage(chat_id, "⛔ Usuario no autorizado\nTu ID es: " + chat_id, "");
        continue;
      }

      if (texto == "/start") {
        enviarMenu(chat_id);
      }

      else if (texto == "/estado" || texto == "📊 Estado") {
        enviarEstado(chat_id);
      }

      else if (texto == "/on15" || texto == "💨 Encender 15 min") {
        activarOn15(chat_id);
      }

      else if (texto == "/off" || texto == "⛔ Apagar") {
        activarApagadoForzado(chat_id);
      }

      else if (texto == "/auto" || texto == "🤖 Automático") {
        activarAutomatico(chat_id);
      }

      else if (texto == "/config" || texto == "⚙️ Config") {
        enviarConfig(chat_id);
      }

      else if (texto.startsWith("/seton")) {
        if (!esAdmin(chat_id)) {
          bot.sendMessage(chat_id, "⛔ Solo admin", "");
          continue;
        }

        String valor = extraerParametro(texto, "/seton");

        if (valor == "") {
          bot.sendMessage(chat_id, "Uso: /seton 80", "");
          continue;
        }

        humedad_encendido = valor.toFloat();
        guardarConfiguracion();

        bot.sendMessage(chat_id,
                        "✅ Nueva humedad de encendido: " +
                        String(humedad_encendido, 1) + "%",
                        "");
      }

      else if (texto.startsWith("/setoff")) {
        if (!esAdmin(chat_id)) {
          bot.sendMessage(chat_id, "⛔ Solo admin", "");
          continue;
        }

        String valor = extraerParametro(texto, "/setoff");

        if (valor == "") {
          bot.sendMessage(chat_id, "Uso: /setoff 75", "");
          continue;
        }

        humedad_apagado = valor.toFloat();
        guardarConfiguracion();

        bot.sendMessage(chat_id,
                        "✅ Nueva humedad de apagado: " +
                        String(humedad_apagado, 1) + "%",
                        "");
      }

      else if (texto.startsWith("/settimer")) {
        if (!esAdmin(chat_id)) {
          bot.sendMessage(chat_id, "⛔ Solo admin", "");
          continue;
        }

        String valor = extraerParametro(texto, "/settimer");

        if (valor == "") {
          bot.sendMessage(chat_id, "Uso: /settimer 15", "");
          continue;
        }

        minutosTimer = valor.toInt();

        if (minutosTimer < 1) minutosTimer = 1;
        if (minutosTimer > 120) minutosTimer = 120;

        actualizarTimers();
        guardarConfiguracion();

        bot.sendMessage(chat_id,
                        "✅ Nuevo timer: " +
                        String(minutosTimer) + " min",
                        "");
      }

      else if (texto.startsWith("/adduser")) {
        if (!esAdmin(chat_id)) {
          bot.sendMessage(chat_id, "⛔ Solo el admin puede agregar usuarios", "");
          continue;
        }

        String nuevoID = extraerParametro(texto, "/adduser");

        if (nuevoID == "") {
          bot.sendMessage(chat_id, "Uso: /adduser 123456789", "");
          continue;
        }

        agregarUsuario(nuevoID);

        bot.sendMessage(chat_id, "✅ Usuario agregado: " + nuevoID, "");
      }

      else if (texto.startsWith("/deluser")) {
        if (!esAdmin(chat_id)) {
          bot.sendMessage(chat_id, "⛔ Solo el admin puede borrar usuarios", "");
          continue;
        }

        String borrarID = extraerParametro(texto, "/deluser");

        if (borrarID == "") {
          bot.sendMessage(chat_id, "Uso: /deluser 123456789", "");
          continue;
        }

        borrarUsuario(borrarID);

        bot.sendMessage(chat_id, "🗑️ Usuario borrado: " + borrarID, "");
      }

      else if (texto == "/listusers") {
        if (!esAdmin(chat_id)) {
          bot.sendMessage(chat_id, "⛔ Solo el admin puede ver usuarios", "");
          continue;
        }

        String mensaje = "👤 Admin:\n";
        mensaje += adminID;
        mensaje += "\n\n👥 Usuarios:\n";

        if (usuarios == "") {
          mensaje += "Sin usuarios agregados";
        } else {
          mensaje += usuarios;
        }

        bot.sendMessage(chat_id, mensaje, "");
      }

      else if (texto == "/id") {
        bot.sendMessage(chat_id, "Tu Chat ID es:\n" + chat_id, "");
      }

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

  WiFiManager wm;

  Serial.println("Conectando WiFi...");

  bool res = wm.autoConnect("Extractor-Setup");

  if (!res) {
    Serial.println("❌ No se pudo conectar al WiFi");
    ESP.restart();
  }

  Serial.println("✅ WiFi conectado");

  client.setInsecure();

  prefs.begin("extractor", false);

  usuarios = prefs.getString("lista", "");
  cargarConfiguracion();

  Serial.print("Usuarios cargados: ");
  Serial.println(usuarios);

  Serial.print("Hum ON: ");
  Serial.println(humedad_encendido);

  Serial.print("Hum OFF: ");
  Serial.println(humedad_apagado);

  Serial.print("Timer: ");
  Serial.println(minutosTimer);

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
  Serial.println("✅ Sistema iniciado");
}

// =====================================================
// LOOP
// =====================================================

void loop() {
  yield();

  ArduinoOTA.handle();

  unsigned long ahora = millis();
  ahoraGlobal = ahora;

  if (ahora - ultimoCheckTelegram >= intervaloTelegram) {
    ultimoCheckTelegram = ahora;
    manejarTelegram();
  }

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
    sensorLeido = true;

    Serial.print("Humedad: ");
    Serial.print(h);
    Serial.print(" % | Temp: ");
    Serial.print(t);
    Serial.println(" °C");
  }

  if (modoActual == AUTO) {

    if (esperandoReintento) {
      if (ahoraGlobal - inicioEsperaReintento >= tiempoEsperaReintento) {
        esperandoReintento = false;
        Serial.println("🔁 Fin de espera. Vuelve a sensar humedad.");
      } else {
        return;
      }
    }

    if (!estadoRelay && humedadActual >= humedad_encendido) {
      prenderRelay();
    }

    if (estadoRelay && humedadActual <= humedad_apagado) {
      Serial.println("💧 Apagado por humedad");
      apagarRelay();
    }

    if (estadoRelay && tiempoMaxEncendido > 0) {
      unsigned long tiempoPrendido = ahoraGlobal - tiempoEncendido;

      if (tiempoPrendido >= tiempoMaxEncendido) {
        Serial.println("⏱️ Apagado por tiempo máximo");

        apagarRelay();

        esperandoReintento = true;
        inicioEsperaReintento = ahoraGlobal;

        Serial.println("⏳ Esperando 40 minutos antes de volver a sensar");
      }
    }
  }

  if (modoActual == FORZADO_OFF) {
    if (estadoRelay) {
      apagarRelay();
    }
  }

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

WiFi setup: Extractor-Setup
Portal: 192.168.4.1
Bot: @extractor_banio_bot