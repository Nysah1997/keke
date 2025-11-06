
#!/usr/bin/env python3
"""
Archivo de inicio optimizado para Wispbyte/Pterodactyl
"""

import os
import sys
import subprocess
import time

def install_dependencies():
    """Instalar dependencias si no están disponibles"""
    try:
        import discord
        print("✅ discord.py ya está disponible")
        return True
    except ImportError:
        print("📦 Instalando discord.py...")
        
        methods = [
            [sys.executable, "-m", "pip", "install", "discord.py"],
            [sys.executable, "-m", "pip", "install", "--user", "discord.py"],
            ["pip3", "install", "discord.py"],
            [sys.executable, "-m", "pip", "install", "--break-system-packages", "discord.py"]
        ]
        
        for method in methods:
            try:
                result = subprocess.run(method, capture_output=True, text=True, timeout=180)
                if result.returncode == 0:
                    print(f"✅ discord.py instalado con: {' '.join(method)}")
                    return True
            except Exception as e:
                print(f"❌ Método falló: {e}")
                continue
        
        print("❌ No se pudo instalar discord.py")
        return False

def main():
    """Función principal"""
    print("🚀 Iniciando Discord Bot para Wispbyte...")
    print(f"🐍 Python: {sys.version}")
    
    # Instalar dependencias
    if not install_dependencies():
        print("❌ Error: No se pudieron instalar las dependencias")
        sys.exit(1)
    
    # Verificar token
    import json
    token = None
    
    # Intentar cargar desde config.json
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        token = config.get('discord_bot_token')
        if token and token.strip() and token != "":
            print("✅ Token encontrado en config.json")
    except Exception as e:
        print(f"⚠️ No se pudo leer config.json: {e}")
    
    # Intentar desde variable de entorno
    if not token or token == "":
        token = os.getenv('DISCORD_BOT_TOKEN')
        if token:
            print("✅ Token encontrado en variables de entorno")
    
    if not token or token == "":
        print("❌ ERROR: Token de Discord no encontrado")
        print("📋 Configura tu token en:")
        print("   1. config.json - cambia 'discord_bot_token'")
        print("   2. Variable de entorno DISCORD_BOT_TOKEN en Wispbyte")
        sys.exit(1)
    
    # Importar y ejecutar el bot
    try:
        print("🔄 Importando módulos del bot...")
        import bot
        print("✅ Bot importado correctamente")
        print("🔗 Conectando a Discord...")
        bot.bot.run(token)
        
    except KeyboardInterrupt:
        print("🛑 Bot detenido por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error crítico: {e}")
        print("📋 Verifica la configuración y logs")
        sys.exit(1)

if __name__ == "__main__":
    main()
