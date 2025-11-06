
#!/usr/bin/env python3
"""
Script especializado para Wispbyte/Pterodactyl
Maneja mejor los errores y la configuración específica del host
"""

import os
import sys
import subprocess
import time
import signal
import json

def log_message(message):
    """Log con timestamp"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")
    sys.stdout.flush()

def install_dependencies():
    """Instalar dependencias con mejor manejo de errores"""
    try:
        import discord
        log_message("✅ discord.py ya está disponible")
        return True
    except ImportError:
        log_message("📦 Instalando discord.py para Wispbyte...")
        
        methods = [
            [sys.executable, "-m", "pip", "install", "discord.py", "--user"],
            [sys.executable, "-m", "pip", "install", "discord.py", "--break-system-packages"],
            [sys.executable, "-m", "pip", "install", "discord.py", "--no-cache-dir"],
            ["pip3", "install", "discord.py", "--user"],
            [sys.executable, "-m", "pip", "install", "discord.py"]
        ]
        
        for i, method in enumerate(methods, 1):
            try:
                log_message(f"🔄 Método {i}/{len(methods)}: {' '.join(method)}")
                result = subprocess.run(
                    method, 
                    capture_output=True, 
                    text=True, 
                    timeout=300,
                    cwd=os.getcwd()
                )
                
                if result.returncode == 0:
                    log_message(f"✅ discord.py instalado con método {i}")
                    return True
                else:
                    log_message(f"❌ Método {i} falló: {result.stderr[:200]}")
                    
            except subprocess.TimeoutExpired:
                log_message(f"⏰ Timeout en método {i}")
            except Exception as e:
                log_message(f"❌ Excepción en método {i}: {e}")
                
        log_message("❌ No se pudo instalar discord.py")
        return False

def get_token():
    """Obtener token con mejor manejo"""
    # 1. Desde variables de entorno (Wispbyte)
    token = os.getenv('DISCORD_BOT_TOKEN')
    if token and token.strip() and token != "":
        log_message("✅ Token encontrado en variables de entorno")
        return token.strip()
    
    # 2. Desde config.json
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        token = config.get('discord_bot_token')
        if token and token.strip() and token != "":
            log_message("✅ Token encontrado en config.json")
            return token.strip()
    except Exception as e:
        log_message(f"⚠️ Error leyendo config.json: {e}")
    
    return None

def setup_signal_handlers():
    """Configurar manejo de señales para Wispbyte"""
    def signal_handler(signum, frame):
        log_message(f"🛑 Señal {signum} recibida. Cerrando bot gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

def main():
    """Función principal optimizada para Wispbyte"""
    log_message("🚀 Iniciando Discord Bot para Wispbyte/Pterodactyl...")
    log_message(f"🐍 Python: {sys.version}")
    log_message(f"📂 Directorio: {os.getcwd()}")
    log_message(f"📋 Archivos: {', '.join(os.listdir('.'))}")
    
    # Configurar manejo de señales
    setup_signal_handlers()
    
    # Verificar token ANTES de instalar dependencias
    token = get_token()
    if not token:
        log_message("❌ ERROR CRÍTICO: Token de Discord no encontrado")
        log_message("📋 Para Wispbyte/Pterodactyl configura:")
        log_message("   1. Variable DISCORD_BOT_TOKEN en tu panel")
        log_message("   2. O edita config.json con tu token")
        log_message("🔧 Reinicia el servidor después de configurar")
        return 128  # Exit code específico para falta de token
    
    # Instalar dependencias
    if not install_dependencies():
        log_message("❌ ERROR: No se pudieron instalar las dependencias")
        log_message("🔧 Soluciones:")
        log_message("   1. Verifica que pip funcione en tu servidor")
        log_message("   2. Contacta soporte de Wispbyte si persiste")
        return 1
    
    # Verificar que se puede importar después de instalar
    try:
        import discord
        log_message(f"✅ discord.py {discord.__version__} verificado")
    except ImportError as e:
        log_message(f"❌ Error importando discord después de instalación: {e}")
        return 1
    
    # Importar y ejecutar el bot
    try:
        log_message("🔄 Importando módulos del bot...")
        
        # Añadir directorio actual al path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        import bot
        log_message("✅ Bot importado correctamente")
        log_message("🔗 Conectando a Discord...")
        
        # Ejecutar bot con el token
        bot.bot.run(token)
        
    except KeyboardInterrupt:
        log_message("🛑 Bot detenido por usuario (Ctrl+C)")
        return 0
    except Exception as e:
        log_message(f"❌ Error crítico ejecutando bot: {e}")
        log_message("📋 Stacktrace:")
        import traceback
        for line in traceback.format_exc().split('\n'):
            if line.strip():
                log_message(f"   {line}")
        return 1
    
    log_message("✅ Bot terminó correctamente")
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        log_message(f"🏁 Proceso terminado con código: {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        log_message(f"💥 Error fatal no manejado: {e}")
        sys.exit(128)
