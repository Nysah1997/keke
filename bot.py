#!/usr/bin/env python3

# Auto-instalación de dependencias si no están disponibles
try:
    import discord
except ImportError:
    print("📦 discord.py no encontrado. Instalando automáticamente...")
    import subprocess
    import sys

    # Intentar instalar discord.py
    install_methods = [
        [sys.executable, "-m", "pip", "install", "discord.py"],
        [sys.executable, "-m", "pip", "install", "--user", "discord.py"],
        ["pip3", "install", "discord.py"],
        [sys.executable, "-m", "pip", "install", "--break-system-packages", "discord.py"],
    ]

    installed = False
    for method in install_methods:
        try:
            result = subprocess.run(method, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                print(f"✅ discord.py instalado con: {' '.join(method)}")
                installed = True
                break
        except:
            continue

    if not installed:
        print("❌ No se pudo instalar discord.py automáticamente")
        print("🔧 Instala manualmente con: pip install discord.py")
        exit(1)

    # Intentar importar después de la instalación
    try:
        import discord
        print("✅ discord.py importado correctamente")
    except ImportError:
        print("❌ Error: discord.py instalado pero no se puede importar")
        print("🔧 Reinicia el bot o instala manualmente")
        exit(1)

from discord.ext import commands
import json
import os
from datetime import datetime, timedelta
import asyncio
import pytz
from zoneinfo import ZoneInfo

from time_tracker import TimeTracker

# Configuración del bot
intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
time_tracker = TimeTracker()

# Configuración de zona horaria Colombia
COLOMBIA_TZ = ZoneInfo("America/Bogota")
START_TIME_HOUR = 17  # 5:00 PM Colombia
START_TIME_MINUTE = 00  # 00 minutos

# Task para verificar hora de inicio
auto_start_task = None
auto_stop_task = None
auto_reset_task = None

# Cargar configuración completa desde config.json
config = {}
GOLD_ROLE_ID = 1382198935971430440  # ID Gold hardcoded
RECLUTA_ROLE_ID = 1430689715761451114  # ID Recluta hardcoded
ROLE_TIERS = {}  # Diccionario para almacenar los nuevos roles

try:
    with open('config.json', 'r') as f:
        config = json.load(f)

    # Usar el ID del config si existe, sino usar el hardcoded
    config_gold_id = config.get('gold_role_id')
    if config_gold_id:
        GOLD_ROLE_ID = config_gold_id

    # Cargar configuración de roles por niveles
    ROLE_TIERS = config.get('role_tiers', {})

    print(f"✅ Rol Gold configurado: ID {GOLD_ROLE_ID}")
    print(f"✅ Rol Recluta configurado: ID {RECLUTA_ROLE_ID}")
    print(f"✅ Roles por niveles cargados: {len(ROLE_TIERS)} niveles")

    # Cargar IDs de canales de notificación desde config
    notification_channels = config.get('notification_channels', {})
    NOTIFICATION_CHANNEL_ID = notification_channels.get('milestones', 1430689717602615300)
    PAUSE_NOTIFICATION_CHANNEL_ID = notification_channels.get('pauses', 1430689717602615301)
    CANCELLATION_NOTIFICATION_CHANNEL_ID = notification_channels.get('cancellations', 1430689718080897125)
    MOVEMENTS_CHANNEL_ID = notification_channels.get('movements', 1430689717602615298)  # Canal para notificaciones de movimientos

    print(f"✅ Canales de notificación cargados:")
    print(f"  - Milestones: {NOTIFICATION_CHANNEL_ID}")
    print(f"  - Pausas: {PAUSE_NOTIFICATION_CHANNEL_ID}")
    print(f"  - Cancelaciones: {CANCELLATION_NOTIFICATION_CHANNEL_ID}")
    print(f"  - Movimientos: {MOVEMENTS_CHANNEL_ID}")

except Exception as e:
    print(f"⚠️ No se pudo cargar configuración: {e}")
    config = {}
    # Valores por defecto si no se puede cargar config
    NOTIFICATION_CHANNEL_ID = 1430689717602615300
    PAUSE_NOTIFICATION_CHANNEL_ID = 1430689717602615301
    CANCELLATION_NOTIFICATION_CHANNEL_ID = 1430689718080897125
    MOVEMENTS_CHANNEL_ID = 1430689717602615298
    GOLD_ROLE_ID = 1382198935971430440
    RECLUTA_ROLE_ID = 1430689715761451114

# Task para verificar milestones periódicamente
milestone_check_task = None

@bot.event
async def on_ready():
    print(f'{bot.user} se ha conectado a Discord!')

    # Verificar que el canal de notificaciones existe
    channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
    if channel:
        if hasattr(channel, 'name'):
            print(f'Canal de notificaciones encontrado: {channel.name} (ID: {channel.id})')
        else:
            print(f'Canal de notificaciones encontrado (ID: {channel.id})')
    else:
        print(f'⚠️ Canal de notificaciones no encontrado con ID: {NOTIFICATION_CHANNEL_ID}')

    try:
        # Sincronización global primero
        print("🔄 Sincronizando comandos globalmente...")
        synced_global = await bot.tree.sync()
        print(f'✅ Sincronizados {len(synced_global)} comando(s) slash globalmente')

        # Sincronización específica del guild si hay guilds
        if bot.guilds:
            for guild in bot.guilds:
                try:
                    print(f"🔄 Sincronizando comandos en {guild.name} (ID: {guild.id})...")
                    synced_guild = await bot.tree.sync(guild=guild)
                    print(f'✅ Sincronizados {len(synced_guild)} comando(s) en {guild.name}')
                except Exception as guild_error:
                    print(f'⚠️ Error sincronizando en {guild.name}: {guild_error}')

        # Listar todos los comandos registrados
        commands = [cmd.name for cmd in bot.tree.get_commands()]
        print(f'📋 Comandos registrados ({len(commands)}): {", ".join(commands)}')

        print("💡 Si los comandos no aparecen inmediatamente:")
        print("   • Espera 1-5 minutos para que Discord los propague")
        print("   • Reinicia tu cliente de Discord")
        print("   • Verifica que el bot tenga permisos de 'applications.commands'")

    except Exception as e:
        print(f'❌ Error al sincronizar comandos: {e}')

def is_admin():
    """Decorator para verificar si el usuario tiene permisos"""
    async def predicate(interaction: discord.Interaction) -> bool:
        try:
            if not hasattr(interaction, 'guild') or not interaction.guild:
                return False

            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                return False

            if member.bot:
                return False

            return True

        except Exception as e:
            print(f"Error en verificación de permisos para {interaction.user.display_name}: {e}")
            return False

    return discord.app_commands.check(predicate)

def load_config():
    """Cargar configuración desde config.json"""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Error cargando configuración: {e}")
        return {}



def calculate_credits(total_seconds: float, role_type: str = "normal", user_id: int = None) -> float:
    """Calcular créditos basado SOLO en horas completas del tiempo base (SIN contar minutos extra)"""
    try:
        if not isinstance(total_seconds, (int, float)) or total_seconds < 0:
            return 0

        # Calcular solo horas completas
        total_hours = int(total_seconds // 3600)

        # Sistema de roles por niveles
        if role_type == "medios":
            if total_hours >= 2:
                return 10  # 2 horas = 10 créditos
            elif total_hours >= 1:
                return 5   # 1 hora = 5 créditos
            else:
                return 0

        elif role_type in ["altos", "imperiales", "nobleza", "monarquia", "supremos"]:
            tier_config = ROLE_TIERS.get(role_type, {})
            credits_per_hour = tier_config.get('credits_per_hour', 0)

            # Calcular créditos proporcionales por cada hora completa trabajada
            credits = total_hours * credits_per_hour

            # Redondear al entero más cercano
            rounded_credits = round(credits)

            # Si el resultado redondeado es un número entero, devolverlo como int
            if rounded_credits == credits or abs(credits - rounded_credits) < 0.01:
                return int(rounded_credits)

            # Si tiene decimales significativos, devolverlos con 2 decimales
            return round(credits, 2)

        elif role_type == "gold":
            # Gold ahora gana créditos: 6 por hora
            credits = total_hours * 6
            return credits

        else:
            # Usuarios sin rol específico (normal/recluta)
            if total_hours >= 1:
                return 4
            else:
                return 0

    except Exception as e:
        print(f"Error calculando créditos: {e}")
        return 0

def get_confirmed_credits(user_id: int) -> int:
    """Obtener créditos YA CONFIRMADOS (solo los que se notificaron oficialmente)"""
    user_data = time_tracker.get_user_data(user_id)
    if not user_data:
        return 0
    return user_data.get('confirmed_credits', 0)

def get_user_role_type(member: discord.Member) -> str:
    """Determina el tipo de rol del usuario - SISTEMA CON NIVELES"""
    if not member:
        return "normal"

    # PRIORIDAD 1: Verificar roles por niveles PRIMERO (orden de mayor a menor jerarquía)
    # Gold ahora está DEBAJO de Altos en prioridad
    role_priority = ["supremos", "monarquia", "nobleza", "imperiales", "altos"]

    for tier_name in role_priority:
        tier_config = ROLE_TIERS.get(tier_name, {})
        tier_role_id = tier_config.get('role_id')

        # Verificar PRIMERO por ID configurado (sin ignorar ningún ID válido)
        if tier_role_id and isinstance(tier_role_id, int):
            for role in member.roles:
                if role.id == tier_role_id:
                    return tier_name

    # RESPALDO: Verificar por nombre del rol si NO se encontró por ID
    tier_names = {
        "medios": ["medios", "medio", "[⚔️]  medios", "[⚔️] medios"],
        "altos": ["altos", "alto", "[⚔️]  altos", "[⚔️] altos"],
        "imperiales": ["imperiales", "imperial", "[👑]  imperiales", "[👑] imperiales"],
        "nobleza": ["nobleza", "[🏰]  nobleza", "[🏰] nobleza"],
        "monarquia": ["monarquia", "monarquía", "[💎]  monarquia", "[💎] monarquía"],
        "supremos": ["supremos", "supremo", "[⭐]  supremos", "[⭐] supremos"]
    }

    for tier_name in role_priority:
        if tier_name in tier_names:
            for role in member.roles:
                role_name_lower = role.name.lower().strip()
                for valid_name in tier_names[tier_name]:
                    if valid_name.lower() in role_name_lower:
                        return tier_name

    # PRIORIDAD 2: Verificar Gold (después de Altos, antes de Medios)
    gold_role_ids = [GOLD_ROLE_ID, 1382198935971430440]
    for role in member.roles:
        if role.id in gold_role_ids:
            return "gold"

    # RESPALDO Gold: Verificar por nombre si no se encontró por ID
    gold_names = ["gold", "[🟡]  gold", "[🟡] gold", "🟡 gold", "[🟡]gold", "🟡gold"]
    for role in member.roles:
        role_name_lower = role.name.lower().strip()
        # Limpiar espacios extra del nombre del rol
        role_name_cleaned = ' '.join(role_name_lower.split())
        for valid_name in gold_names:
            valid_name_cleaned = ' '.join(valid_name.lower().split())
            if valid_name_cleaned in role_name_cleaned or role_name_cleaned in valid_name_cleaned:
                return "gold"

    # PRIORIDAD 3: Verificar Medios
    role_priority_medios = ["medios"]

    for tier_name in role_priority_medios:
        tier_config = ROLE_TIERS.get(tier_name, {})
        tier_role_id = tier_config.get('role_id')

        # Verificar por ID configurado
        if tier_role_id and isinstance(tier_role_id, int):
            for role in member.roles:
                if role.id == tier_role_id:
                    return tier_name

        # RESPALDO: Verificar por nombre del rol si NO se encontró por ID
        tier_names_medios = {
            "medios": ["medios", "medio", "[⚔️]  medios", "[⚔️] medios"]
        }

        if tier_name in tier_names_medios:
            for role in member.roles:
                role_name_lower = role.name.lower().strip()
                for valid_name in tier_names_medios[tier_name]:
                    if valid_name.lower() in role_name_lower:
                        return tier_name

    # PRIORIDAD 4: Si no tiene ningún rol especial, es Recluta
    return "normal"

def get_role_info(member: discord.Member) -> str:
    """Obtiene la información del rol del usuario"""
    if not member:
        return " (Recluta)"

    role_type = get_user_role_type(member)

    # Mapeo de nombres de roles
    role_names = {
        "supremos": "Supremos",
        "monarquia": "Monarquía",
        "nobleza": "Nobleza",
        "imperiales": "Imperiales",
        "altos": "Altos",
        "medios": "Medios",
        "gold": "Gold"
    }

    if role_type in role_names:
        return f" ({role_names[role_type]})"
    else:
        return " (Recluta)"

def has_unlimited_time_role(member: discord.Member) -> bool:
    """Verificar si el usuario tiene un rol que le otorga tiempo ilimitado (rol Gold)"""
    if not member:
        return False

    # En este sistema, el rol Gold otorga "tiempo ilimitado" (2 horas en lugar de 1)
    role_type = get_user_role_type(member)
    return role_type == "gold"

@bot.tree.command(name="iniciar_tiempo", description="Iniciar el seguimiento de tiempo para un usuario")
@discord.app_commands.describe(usuario="El usuario para quien iniciar el seguimiento de tiempo")
@is_admin()
async def iniciar_tiempo(interaction: discord.Interaction, usuario: discord.Member):
    if usuario.bot:
        await interaction.response.send_message("❌ No se puede rastrear el tiempo de bots.", ephemeral=True)
        return

    # Verificar que el usuario tenga el rol requerido (ID: 1430689715761451113)
    required_role_id = 1430689715761451113
    has_required_role = any(role.id == required_role_id for role in usuario.roles)

    if not has_required_role:
        await interaction.response.send_message(
            f"❌ {usuario.mention} no tiene el rol requerido para iniciar tiempo. "
            f"Se requiere el rol de Verificado.",
            ephemeral=True
        )
        return

    # Obtener hora actual en Colombia
    colombia_now = datetime.now(COLOMBIA_TZ)
    current_hour = colombia_now.hour
    current_minute = colombia_now.minute

    # NUEVA VALIDACIÓN: No permitir iniciar después de las 19:01 (7:01 PM)
    cutoff_hour = 19
    cutoff_minute = 1
    is_after_cutoff = (current_hour > cutoff_hour) or (current_hour == cutoff_hour and current_minute >= cutoff_minute)

    if is_after_cutoff:
        await interaction.response.send_message(
            f"❌ No se pueden iniciar tiempos después de las 19:01 (7:01 PM) hora Colombia.\n"
            f"⏰ Hora actual: {colombia_now.strftime('%H:%M')} Colombia",
            ephemeral=True
        )
        return

    # SIEMPRE obtener el rol actualizado del usuario desde Discord
    role_type = get_user_role_type(usuario)

    # Verificar si el usuario ya ha completado sus horas máximas
    user_data = time_tracker.get_user_data(usuario.id)
    if user_data:
        # PRIMERO verificar si milestone_completed está en True (fue marcado como terminado)
        if user_data.get("milestone_completed", False):
            await interaction.response.send_message(
                f"❌ {usuario.mention} ya ha completado su tiempo máximo y no puede iniciar tiempo nuevamente."
            )
            return

        # SOLO SI NO está marcado como completado, verificar el tiempo actual
        total_time = time_tracker.get_total_time(usuario.id)
        total_hours = total_time / 3600

        # Verificar límites según rol actual (solo si tiene tiempo registrado)
        if total_hours > 0:
            if role_type == "gold":
                if total_hours >= 2.0:
                    await interaction.response.send_message(
                        f"❌ {usuario.mention} ya ha completado sus 2 horas máximas (Gold) y no puede iniciar tiempo nuevamente."
                    )
                    return
            elif role_type in ["medios", "altos", "imperiales", "nobleza", "monarquia", "supremos"]:
                # Estos roles de tier tienen límite de 2 horas máximas
                # Solo bloquear si completó milestone_completed (2 horas completas)
                if user_data.get("milestone_completed", False):
                    role_display_names = {
                        "medios": "Medios",
                        "altos": "Altos",
                        "imperiales": "Imperiales",
                        "nobleza": "Nobleza",
                        "monarquia": "Monarquía",
                        "supremos": "Supremos"
                    }
                    role_name = role_display_names.get(role_type, role_type.capitalize())
                    await interaction.response.send_message(
                        f"❌ {usuario.mention} ya ha completado sus 2 horas máximas ({role_name}) y no puede iniciar tiempo nuevamente."
                    )
                    return
                # Si tiene 1 hora o más pero NO está marcado como completado, puede continuar
                elif total_hours >= 2.0:
                    role_display_names = {
                        "medios": "Medios",
                        "altos": "Altos",
                        "imperiales": "Imperiales",
                        "nobleza": "Nobleza",
                        "monarquia": "Monarquía",
                        "supremos": "Supremos"
                    }
                    role_name = role_display_names.get(role_type, role_type.capitalize())
                    await interaction.response.send_message(
                        f"❌ {usuario.mention} ya ha completado sus 2 horas máximas ({role_name}) y no puede iniciar tiempo nuevamente."
                    )
                    return
            else:  # normal/recluta
                if user_data.get("milestone_completed", False) or total_hours >= 1.0:
                    await interaction.response.send_message(
                        f"❌ {usuario.mention} ya ha completado su 1 hora máxima (Recluta) y no puede iniciar tiempo nuevamente."
                    )
                    return

    # Verificar si el usuario tiene tiempo pausado
    if user_data and user_data.get('is_paused', False):
        await interaction.response.send_message(
            f"⚠️ {usuario.mention} tiene tiempo pausado. Usa `/despausar_tiempo` para continuar el tiempo."
        )
        return

    # Verificar si es antes de las 17:00 (pre-registro) o después (inicio directo)
    pre_register_cutoff_hour = 17
    pre_register_cutoff_minute = 00
    is_before_17 = (current_hour < pre_register_cutoff_hour) or (current_hour == pre_register_cutoff_hour and current_minute < pre_register_cutoff_minute)

    if is_before_17:
        # Pre-registro: registrar usuario pero no iniciar cronómetro (ANTES de 17:00)
        success = time_tracker.pre_register_user(usuario.id, usuario.display_name)
        if success:
            # Guardar quién hizo el pre-registro
            time_tracker.set_pre_register_initiator(usuario.id, interaction.user.id, interaction.user.display_name)

            # Mostrar información del rol actual
            role_info = get_role_info(usuario)
            await interaction.response.send_message(
                f"📝 El tiempo de {usuario.mention}{role_info} ha sido pre-registrado por {interaction.user.mention}\n"
                f"⏰ Iniciará automáticamente a las 17:00 Colombia"
            )
        else:
            await interaction.response.send_message(f"⚠️ {usuario.mention} ya está pre-registrado", ephemeral=True)
    else:
        # A partir de las 17:00: iniciar directamente
        success = time_tracker.start_tracking(usuario.id, usuario.display_name)
        if success:
            # Mostrar información del rol actual
            role_info = get_role_info(usuario)
            await interaction.response.send_message(
                f"⏰ El tiempo de {usuario.mention}{role_info} ha sido iniciado inmediatamente por {interaction.user.mention}"
            )
        else:
            await interaction.response.send_message(f"⚠️ El tiempo de {usuario.mention} ya está activo", ephemeral=True)

@bot.tree.command(name="pausar_tiempo", description="Pausar el tiempo de un usuario")
@discord.app_commands.describe(usuario="El usuario para quien pausar el tiempo")
@is_admin()
async def pausar_tiempo(interaction: discord.Interaction, usuario: discord.Member):
    user_data = time_tracker.get_user_data(usuario.id)
    total_time_before = time_tracker.get_total_time(usuario.id)

    # Obtener el tipo de rol del usuario para pasarlo a pause_tracking
    role_type = get_user_role_type(usuario)
    success = time_tracker.pause_tracking(usuario.id, user_role_type=role_type) # Pasar el tipo de rol

    if success:
        # Obtener el tiempo total después de pausar para la notificación
        total_time_after = time_tracker.get_total_time(usuario.id)
        session_time = total_time_after - total_time_before
        pause_count = time_tracker.get_pause_count(usuario.id) # Obtener el nuevo contador de pausas

        formatted_total_time = time_tracker.format_time_human(total_time_after)
        formatted_session_time = time_tracker.format_time_human(session_time) if session_time > 0 else "0 Segundos"

        # Verificar si el usuario fue cancelado automáticamente por llegar a 3 pausas
        user_data_updated = time_tracker.get_user_data(usuario.id)
        was_auto_cancelled = (user_data_updated and
                             user_data_updated.get('pause_count', 0) == 0 and
                             not user_data_updated.get('is_paused', False) and
                             not user_data_updated.get('is_active', False))

        if was_auto_cancelled:
            # Usuario cancelado automáticamente por 3 pausas
            time_lost = user_data.get('time_lost_on_cancellation', 0) if user_data else 0
            formatted_time_lost = time_tracker.format_time_human(time_lost) if time_lost > 0 else "0 Segundos"

            await interaction.response.send_message(
                f"🚫 **{usuario.mention} ha alcanzado el límite de 3 pausas y su tiempo ha sido cancelado automáticamente.**\n"
                f"🕐 **Tiempo conservado:** {formatted_total_time} (solo horas completas)\n"
                f"❌ **Tiempo perdido:** {formatted_time_lost}"
            )

            # Enviar notificación SOLO al canal de cancelaciones (NO al de pausas)
            await send_auto_cancellation_notification(usuario.display_name, formatted_total_time, interaction.user.mention, 3, time_lost)
        else:
            # Pausa normal (usuarios Gold o pausas 1/3, 2/3 para reclutas)
            await interaction.response.send_message(f"PreviewPaused El tiempo de {usuario.mention} ha sido pausado")

            # Enviar notificación al canal de pausas SOLO si NO fue cancelado automáticamente
            await send_pause_notification(usuario.display_name, total_time_after, interaction.user.mention, formatted_session_time, pause_count, role_type)
    else:
        await interaction.response.send_message(f"⚠️ No hay tiempo activo para {usuario.mention}", ephemeral=True)

@bot.tree.command(name="despausar_tiempo", description="Despausar el tiempo de un usuario")
@discord.app_commands.describe(usuario="El usuario para quien despausar el tiempo")
@is_admin()
async def despausar_tiempo(interaction: discord.Interaction, usuario: discord.Member):
    paused_duration = time_tracker.get_paused_duration(usuario.id)
    success = time_tracker.resume_tracking(usuario.id)
    if success:
        total_time = time_tracker.get_total_time(usuario.id)
        formatted_paused_duration = time_tracker.format_time_human(paused_duration) if paused_duration > 0 else "0 Segundos"
        await interaction.response.send_message(
            f"▶️ El tiempo de {usuario.mention} ha sido despausado"
        )
        await send_unpause_notification(usuario.display_name, total_time, interaction.user.mention, formatted_paused_duration)
    else:
        await interaction.response.send_message(f"⚠️ No se puede despausar - {usuario.mention} no tiene tiempo pausado", ephemeral=True)

@bot.tree.command(name="dar_minutos", description="Dar minutos totales al tiempo de un usuario")
@discord.app_commands.describe(
    usuario="El usuario al que dar minutos",
    cantidad="Cantidad de minutos a dar"
)
@is_admin()
async def dar_minutos(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    if cantidad <= 0:
        await interaction.response.send_message("❌ La cantidad de minutos debe ser positiva", ephemeral=True)
        return

    success = time_tracker.add_minutes(usuario.id, usuario.display_name, cantidad)
    if success:
        total_time = time_tracker.get_total_time(usuario.id)
        formatted_time = time_tracker.format_time_human(total_time)

        await interaction.response.send_message(
            f"✅ Dados {cantidad} minutos a {usuario.mention} por {interaction.user.mention}\n"
            f"⏱️ Tiempo total: {formatted_time}\n"
            f"💰 Créditos se confirmarán cuando alcance el milestone"
        )

        # Verificar milestone para enviar notificación si corresponde
        await check_time_milestone(usuario.id, usuario.display_name)
    else:
        await interaction.response.send_message(f"❌ Error al dar minutos para {usuario.mention}", ephemeral=True)

@bot.tree.command(name="sumar_minutos", description="Sumar minutos extra (ajusta límite sin modificar tiempo base)")
@discord.app_commands.describe(
    usuario="El usuario al que sumar minutos extra",
    minutos="Cantidad de minutos extra a sumar"
)
@is_admin()
async def sumar_minutos(interaction: discord.Interaction, usuario: discord.Member, minutos: int):
    if minutos <= 0:
        await interaction.response.send_message("❌ La cantidad de minutos debe ser positiva", ephemeral=True)
        return

    # Usar la función de minutos extra que NO suma al tiempo base
    success = time_tracker.add_extra_minutes(usuario.id, usuario.display_name, minutos)
    if success:
        await interaction.response.send_message(
            f"⏱️ +{minutos} minutos sumados a {usuario.mention} por {interaction.user.mention}"
        )
        await check_time_milestone(usuario.id, usuario.display_name)
    else:
        await interaction.response.send_message(f"❌ Error al sumar minutos extra para {usuario.mention}", ephemeral=True)

@bot.tree.command(name="restar_minutos", description="Restar minutos del tiempo de un usuario")
@discord.app_commands.describe(
    usuario="El usuario al que restar tiempo",
    minutos="Cantidad de minutos a restar"
)
@is_admin()
async def restar_minutos(interaction: discord.Interaction, usuario: discord.Member, minutos: int):
    if minutos <= 0:
        await interaction.response.send_message("❌ La cantidad de minutos debe ser positiva", ephemeral=True)
        return

    success = time_tracker.subtract_minutes(usuario.id, minutos)
    if success:
        total_time = time_tracker.get_total_time(usuario.id)
        formatted_time = time_tracker.format_time_human(total_time)
        await interaction.response.send_message(
            f"➖ Restados {minutos} minutos de {usuario.mention} por {interaction.user.mention}\n"
            f"⏱️ Tiempo total: {formatted_time}"
        )
    else:
        await interaction.response.send_message(f"❌ Error al restar tiempo para {usuario.mention}", ephemeral=True)

@bot.tree.command(name="quitar_minutos_extras", description="Quitar minutos extra otorgados previamente")
@discord.app_commands.describe(
    usuario="El usuario al que quitar minutos extra",
    cantidad="Cantidad de minutos extra a quitar"
)
@is_admin()
async def quitar_minutos_extras(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    if cantidad <= 0:
        await interaction.response.send_message("❌ La cantidad de minutos debe ser positiva", ephemeral=True)
        return

    # Obtener minutos extra actuales
    current_extra = time_tracker.get_extra_minutes(usuario.id)

    if current_extra <= 0:
        await interaction.response.send_message(
            f"❌ {usuario.mention} no tiene minutos extra para quitar",
            ephemeral=True
        )
        return

    # Calcular cuántos minutos se pueden quitar (no exceder los que tiene)
    minutos_a_quitar = min(cantidad, current_extra)

    success = time_tracker.subtract_extra_minutes(usuario.id, minutos_a_quitar)
    if success:
        remaining_extra = time_tracker.get_extra_minutes(usuario.id)
        await interaction.response.send_message(
            f"➖ -{minutos_a_quitar} minutos extra quitados de {usuario.mention} por {interaction.user.mention}\n"
            f"➕ Minutos extra restantes: {remaining_extra} minutos"
        )
        await check_time_milestone(usuario.id, usuario.display_name)
    else:
        await interaction.response.send_message(f"❌ Error al quitar minutos extra para {usuario.mention}", ephemeral=True)

# Clase para manejar la paginación
class TimesView(discord.ui.View):
    def __init__(self, sorted_users, guild, max_per_page=20, search_term=None, filter_status=None):
        super().__init__(timeout=300)
        self.sorted_users = sorted_users
        self.guild = guild
        self.max_per_page = max_per_page
        self.current_page = 0
        self.total_pages = (len(sorted_users) + max_per_page - 1) // max_per_page if sorted_users else 1
        self.search_term = search_term
        self.filter_status = filter_status

        # Actualizar estado inicial de botones
        self.update_buttons()

    def get_embed(self):
        """Crear embed para la página actual"""
        start_idx = self.current_page * self.max_per_page
        end_idx = min(start_idx + self.max_per_page, len(self.sorted_users))
        current_users = self.sorted_users[start_idx:end_idx]
        user_list = []

        for _, user_id, data in current_users:
            try:
                user_id_int = int(user_id)
                member = self.guild.get_member(user_id_int) if self.guild else None

                if member:
                    user_mention = member.mention
                    role_type = get_user_role_type(member)
                else:
                    user_name = data.get('name', f'Usuario {user_id}')
                    user_mention = f"**{user_name}** `(ID: {user_id})`"
                    role_type = "normal"

                total_time = time_tracker.get_total_time(user_id_int)
                formatted_time = time_tracker.format_time_human(total_time)

                # Determinar estado del usuario
                total_hours = total_time / 3600

                # Verificar si ha completado su tiempo máximo
                is_finished = (data.get("milestone_completed", False) or
                             (role_type == "gold" and total_hours >= 2.0) or
                             (role_type == "normal" and total_hours >= 1.0))

                if data.get('is_active', False):
                    status = "🟢 Activo"
                elif is_finished:
                    status = "✅ Terminado"
                elif data.get('is_paused', False):
                    status = "⏸️ Pausado"
                elif data.get('daily_limit_reset', False) and total_hours > 0:
                    # Si fue reseteado y tiene tiempo histórico, mostrar como terminado
                    status = "✅ Terminado"
                else:
                    status = "🔴 Inactivo"

                credits = calculate_credits(total_time, role_type)
                # Formatear créditos sin decimales si es entero
                credits_display = f"{int(credits)}" if credits == int(credits) else f"{credits:.2f}"
                credit_info = f" 💰 {credits_display} Créditos" if credits > 0 else ""
                role_info = get_role_info(member) if member else ""
                user_list.append(f"📌 {user_mention}{role_info} - ⏱️ {formatted_time}{credit_info} {status}")

            except Exception as e:
                print(f"Error procesando usuario {user_id}: {e}")
                continue

        # Título con información de búsqueda y filtros
        title = "⏰ Tiempos Registrados"
        if self.search_term:
            title += f" (Búsqueda: '{self.search_term}')"
        if self.filter_status:
            title += f" (Filtro: {self.filter_status})"

        embed = discord.Embed(
            title=title,
            description="\n".join(user_list) if user_list else "No hay usuarios en esta página",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        footer_text = f"Página {self.current_page + 1}/{self.total_pages} • Total: {len(self.sorted_users)} usuarios"
        if self.search_term:
            footer_text += f" encontrados"

        embed.set_footer(text=footer_text)
        return embed

    @discord.ui.button(label='◀️ Anterior', style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
        self.update_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='▶️ Siguiente', style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
        self.update_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='📄 Ir a página', style=discord.ButtonStyle.primary)
    async def go_to_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PageModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='🔍 Buscar', style=discord.ButtonStyle.secondary)
    async def search_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SearchModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='🔄 Actualizar', style=discord.ButtonStyle.success)
    async def refresh_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()

            # Recargar datos con timeout extendido para muchos usuarios
            tracked_users = await asyncio.wait_for(
                asyncio.to_thread(time_tracker.get_all_tracked_users),
                timeout=15.0
            )

            # Aplicar filtros existentes con timeout
            filtered_users = await asyncio.wait_for(
                self._apply_filters(tracked_users),
                timeout=10.0
            )

            # Actualizar datos internos
            self.sorted_users = filtered_users
            self.total_pages = (len(filtered_users) + self.max_per_page - 1) // self.max_per_page if filtered_users else 1

            # Asegurar que la página actual sea válida
            if self.current_page >= self.total_pages:
                self.current_page = max(0, self.total_pages - 1)

            # Rehabilitar botones de navegación si hay múltiples páginas
            if self.total_pages > 1:
                for item in self.children:
                    if isinstance(item, discord.ui.Button) and item.label in ['◀️ Anterior', '▶️ Siguiente', '📄 Ir a página']:
                        # Rehabilitar botones que podrían haberse deshabilitado incorrectamente
                        if item.label == '📄 Ir a página':
                            item.disabled = False
                        elif item.label == '◀️ Anterior':
                            item.disabled = (self.current_page == 0)
                        elif item.label == '▶️ Siguiente':
                            item.disabled = (self.current_page >= self.total_pages - 1)

            # Actualizar botones
            self.update_buttons()

            # Obtener embed actualizado
            embed = self.get_embed()

            # Actualizar el mensaje existente
            await interaction.edit_original_response(embed=embed, view=self)

        except asyncio.TimeoutError:
            await interaction.edit_original_response(content="⚠️ Timeout al actualizar datos. Intenta de nuevo.")
        except Exception as e:
            await interaction.edit_original_response(content=f"❌ Error al actualizar: {e}")

    @discord.ui.select(
        placeholder="Filtrar por estado...",
        options=[
            discord.SelectOption(label="Todos los usuarios", value="all", emoji="📋"),
            discord.SelectOption(label="Solo Activos", value="active", emoji="🟢"),
            discord.SelectOption(label="Solo Pausados", value="paused", emoji="⏸️"),
            discord.SelectOption(label="Solo Terminados", value="finished", emoji="✅"),
            discord.SelectOption(label="Solo Inactivos", value="inactive", emoji="🔴")
        ]
    )
    async def filter_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        selected_filter = select.values[0]

        try:
            # Recargar datos
            tracked_users = await asyncio.wait_for(
                asyncio.to_thread(time_tracker.get_all_tracked_users),
                timeout=5.0
            )

            # Aplicar filtro seleccionado
            self.filter_status = selected_filter if selected_filter != "all" else None
            filtered_users = await self._apply_filters(tracked_users)

            # Actualizar datos y resetear página
            self.sorted_users = filtered_users
            self.current_page = 0
            self.total_pages = (len(filtered_users) + self.max_per_page - 1) // self.max_per_page if filtered_users else 1

            # Actualizar botones según nueva paginación
            self.update_buttons()

            # Obtener embed actualizado
            embed = self.get_embed()

            # Actualizar el mensaje existente
            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            await interaction.response.send_message(f"❌ Error aplicando filtro: {e}", ephemeral=True)

    async def _apply_filters(self, tracked_users):
        """Aplicar filtros de búsqueda y estado"""
        filtered_users = []

        for user_id, data in tracked_users.items():
            user_name = data.get('name', f'Usuario {user_id}')

            # Aplicar filtro de búsqueda
            if self.search_term and self.search_term.lower() not in user_name.lower():
                continue

            # Aplicar filtro de estado
            if self.filter_status:
                try:
                    user_id_int = int(user_id)
                    member = self.guild.get_member(user_id_int) if self.guild else None
                    total_time = time_tracker.get_total_time(user_id_int)

                    # Determinar estado actual
                    total_hours = total_time / 3600
                    role_type = get_user_role_type(member) if member else "normal"

                    # Determinar si está terminado (ha alcanzado su límite máximo)
                    is_finished = (data.get("milestone_completed", False) or
                                 (role_type == "gold" and total_hours >= 2.0) or
                                 (role_type == "normal" and total_hours >= 1.0))

                    if data.get('is_active', False):
                        status = "active"
                    elif is_finished:
                        status = "finished"
                    elif data.get('is_paused', False):
                        status = "paused"
                    elif data.get('daily_limit_reset', False) and total_hours > 0:
                        status = "finished" # Considerar terminado si fue reseteado y tiene tiempo
                    else:
                        status = "inactive"

                    # Filtrar por estado
                    if self.filter_status != status:
                        continue

                except Exception as e:
                    print(f"Error filtrando usuario {user_id}: {e}")
                    continue

            filtered_users.append((user_name.lower(), user_id, data))

        filtered_users.sort(key=lambda x: x[0])
        return filtered_users

    def update_buttons(self):
        """Actualizar estado de los botones según la página actual"""
        # Buscar los botones de navegación por su label
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if item.label == '◀️ Anterior':
                    item.disabled = (self.current_page == 0)
                elif item.label == '▶️ Siguiente':
                    item.disabled = (self.current_page >= self.total_pages - 1)
                elif item.label == '📄 Ir a página':
                    item.disabled = (self.total_pages <= 1)

    async def on_timeout(self):
        """Deshabilitar botones cuando expire el timeout"""
        for item in self.children:
            item.disabled = True

class PageModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='Ir a Página')
        self.view = view

    page_number = discord.ui.TextInput(
        label='Número de página',
        placeholder=f'Ingresa un número entre 1 y {999}',
        required=True,
        max_length=3
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            page = int(self.page_number.value)
            if 1 <= page <= self.view.total_pages:
                self.view.current_page = page - 1
                self.view.update_buttons()
                embed = self.view.get_embed()
                await interaction.response.edit_message(embed=embed, view=self.view)
            else:
                await interaction.response.send_message(
                    f"❌ Página inválida. Debe estar entre 1 y {self.view.total_pages}",
                    ephemeral=True
                )
        except ValueError:
            await interaction.response.send_message("❌ Por favor ingresa un número válido", ephemeral=True)

class SearchModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title='Buscar Usuario')
        self.view = view

    search_term = discord.ui.TextInput(
        label='Nombre del usuario',
        placeholder='Escribe parte del nombre del usuario...',
        required=True,
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        search_term = self.search_term.value.lower().strip()

        # Obtener todos los usuarios sin filtro
        try:
            tracked_users = await asyncio.wait_for(
                asyncio.to_thread(time_tracker.get_all_tracked_users),
                timeout=2.0
            )

            # Filtrar usuarios
            filtered_users = []
            for user_id, data in tracked_users.items():
                user_name = data.get('name', f'Usuario {user_id}').lower()
                if search_term in user_name:
                    filtered_users.append((user_name, user_id, data))

            filtered_users.sort(key=lambda x: x[0])

            if not filtered_users:
                await interaction.response.send_message(
                    f"❌ No se encontraron usuarios con '{self.search_term.value}' en su nombre",
                    ephemeral=True
                )
                return

            # Crear nueva vista con resultados filtrados
            new_view = TimesView(filtered_users, self.view.guild, max_per_page=self.view.max_per_page,
                               search_term=self.search_term.value, filter_status=self.view.filter_status)
            embed = new_view.get_embed()

            await interaction.response.edit_message(embed=embed, view=new_view)

        except Exception as e:
            await interaction.response.send_message(f"❌ Error en búsqueda: {e}", ephemeral=True)

@bot.tree.command(name="ver_tiempos", description="Ver todos los tiempos registrados con filtros y actualización en tiempo real")
@is_admin()
async def ver_tiempos(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=False)
    except Exception as e:
        print(f"Error al defer la interacción: {e}")
        try:
            await interaction.response.send_message("🔄 Procesando tiempos...", ephemeral=False)
        except Exception:
            return

    try:
        tracked_users = await asyncio.wait_for(
            asyncio.to_thread(time_tracker.get_all_tracked_users),
            timeout=5.0
        )

        if not tracked_users:
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("📊 No hay usuarios con tiempo registrado", ephemeral=False)
                else:
                    await interaction.followup.send("📊 No hay usuarios con tiempo registrado")
            except Exception as e:
                print(f"Error enviando mensaje de sin usuarios: {e}")
            return

        # Ordenar usuarios alfabéticamente por nombre
        sorted_users = []
        for user_id, data in tracked_users.items():
            user_name = data.get('name', f'Usuario {user_id}')
            sorted_users.append((user_name.lower(), user_id, data))

        sorted_users.sort(key=lambda x: x[0])

        # Usar paginación con filtrado mejorado y botones de actualización
        view = TimesView(sorted_users, interaction.guild, max_per_page=20)
        embed = view.get_embed()

        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await interaction.followup.send(embed=embed, view=view)

    except asyncio.TimeoutError:
        error_msg = "❌ Timeout al obtener usuarios. Intenta de nuevo."
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(error_msg, ephemeral=False)
            else:
                await interaction.followup.send(error_msg)
        except Exception as e:
            print(f"Error enviando mensaje de timeout: {e}")

    except Exception as e:
        print(f"Error general en ver_tiempos: {e}")
        import traceback
        traceback.print_exc()

        error_msg = "❌ Error interno del comando. Revisa los logs del servidor."
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(error_msg, ephemeral=False)
            else:
                await interaction.followup.send(error_msg)
        except Exception as e2:
            print(f"No se pudo enviar mensaje de error final: {e2}")

@bot.tree.command(name="reiniciar_tiempo", description="Reiniciar el tiempo de un usuario a cero")
@discord.app_commands.describe(usuario="El usuario cuyo tiempo se reiniciará")
@is_admin()
async def reiniciar_tiempo(interaction: discord.Interaction, usuario: discord.Member):
    success = time_tracker.reset_user_time(usuario.id)
    if success:
        await interaction.response.send_message(f"🔄 Tiempo reiniciado para {usuario.mention} por {interaction.user.mention}")
    else:
        await interaction.response.send_message(f"❌ No se encontró registro de tiempo para {usuario.mention}", ephemeral=True)

@bot.tree.command(name="reiniciar_todos_tiempos", description="Reiniciar todos los tiempos de todos los usuarios")
@is_admin()
async def reiniciar_todos_tiempos(interaction: discord.Interaction):
    usuarios_reiniciados = time_tracker.reset_all_user_times()
    if usuarios_reiniciados > 0:
        await interaction.response.send_message(f"🔄 Tiempos reiniciados para {usuarios_reiniciados} usuario(s)")
    else:
        await interaction.response.send_message("❌ No hay usuarios con tiempo registrado para reiniciar", ephemeral=True)

@bot.tree.command(name="limpiar_base_datos", description="ELIMINAR COMPLETAMENTE todos los usuarios registrados de la base de datos")
@discord.app_commands.describe(confirmar="Escribe 'SI' para confirmar la eliminación completa")
@is_admin()
async def limpiar_base_datos(interaction: discord.Interaction, confirmar: str):
    if confirmar.upper() != "SI":
        await interaction.response.send_message("❌ Operación cancelada. Debes escribir 'SI' para confirmar", ephemeral=True)
        return

    tracked_users = time_tracker.get_all_tracked_users()
    user_count = len(tracked_users)

    if user_count == 0:
        await interaction.response.send_message("❌ No hay usuarios registrados en la base de datos", ephemeral=True)
        return

    success = time_tracker.clear_all_data()

    if success:
        embed = discord.Embed(
            title="🗑️ BASE DE DATOS LIMPIADA",
            description="Todos los datos de usuarios han sido eliminados completamente",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(
            name="📊 Datos eliminados:",
            value=f"• {user_count} usuarios registrados\n"
                  f"• Todo el historial de tiempo\n"
                  f"• Sesiones activas\n"
                  f"• Archivo user_times.json reiniciado",
            inline=False
        )
        embed.add_field(
            name="✅ Estado actual:",
            value="Base de datos completamente limpia\n"
                  "Sistema listo para nuevos registros",
            inline=False
        )
        embed.set_footer(text=f"Ejecutado por {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ Error al limpiar la base de datos", ephemeral=True)

@bot.tree.command(name="limpiar_horas_maximas", description="Resetear límites diarios de TODOS los usuarios conservando créditos y tiempo histórico")
@discord.app_commands.describe(confirmar="Escribe 'SI' para confirmar el reseteo de límites")
@is_admin()
async def limpiar_horas_maximas(interaction: discord.Interaction, confirmar: str):
    """Resetear límites diarios de todos los usuarios que completaron sus horas máximas, conservando créditos y tiempo histórico"""
    if confirmar.upper() != "SI":
        await interaction.response.send_message("❌ Operación cancelada. Debes escribir 'SI' para confirmar", ephemeral=True)
        return

    tracked_users = time_tracker.get_all_tracked_users()

    if not tracked_users:
        await interaction.response.send_message("❌ No hay usuarios registrados en la base de datos", ephemeral=True)
        return

    # Identificar usuarios que completaron sus límites
    users_to_reset = []
    reclutas_reset = 0
    gold_reset = 0
    tier_reset = 0

    for user_id_str, data in tracked_users.items():
        try:
            user_id = int(user_id_str)
            member = interaction.guild.get_member(user_id) if interaction.guild else None

            # Verificar si completó sus horas máximas
            if data.get('milestone_completed', False):
                user_name = data.get('name', f'Usuario {user_id}')
                confirmed_credits = data.get('confirmed_credits', 0)
                total_time = time_tracker.get_total_time(user_id)

                # Determinar tipo de rol
                if member:
                    role_type = get_user_role_type(member)
                    if role_type == "gold":
                        gold_reset += 1
                    elif role_type in ROLE_TIERS:
                        tier_reset += 1
                    else:
                        reclutas_reset += 1
                else:
                    reclutas_reset += 1

                users_to_reset.append({
                    'id': user_id_str,
                    'name': user_name,
                    'credits': confirmed_credits,
                    'time': total_time
                })

        except Exception as e:
            print(f"Error procesando usuario {user_id_str}: {e}")
            continue

    if not users_to_reset:
        await interaction.response.send_message(
            "❌ No se encontraron usuarios que hayan completado sus horas máximas para resetear",
            ephemeral=True
        )
        return

    # Resetear límites conservando créditos
    reset_count = 0
    try:
        for user_info in users_to_reset:
            user_id_str = user_info['id']
            confirmed_credits = user_info['credits']
            historical_time = user_info['time']

            # Determinar qué función usar según el rol
            member = interaction.guild.get_member(int(user_id_str)) if interaction.guild else None
            role_type = get_user_role_type(member) if member else "normal"

            # Roles Altos-Supremos: resetear tiempo a 0 (conservando solo créditos)
            if role_type in ["altos", "imperiales", "nobleza", "monarquia", "supremos"]:
                success = time_tracker.reset_daily_limit_zero_time(user_id_str, confirmed_credits)
            else:
                # Otros roles (Reclutas, Gold, Medios): conservar tiempo histórico
                success = time_tracker.reset_daily_limit_keep_history(user_id_str, confirmed_credits, historical_time)

            if success:
                reset_count += 1

        embed = discord.Embed(
            title="🔄 LÍMITES DIARIOS RESETEADOS",
            description="Todos los usuarios que completaron sus horas máximas han sido reseteados",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )

        embed.add_field(
            name="📊 Usuarios reseteados:",
            value=f"• {reclutas_reset} Reclutas\n"
                  f"• {gold_reset} Gold\n"
                  f"• {tier_reset} Roles por niveles\n"
                  f"• **Total: {reset_count} usuarios reseteados**",
            inline=False
        )

        embed.add_field(
            name="✅ Cambios aplicados:",
            value=f"• Estados: Limpiados para poder trabajar nuevamente\n"
                  f"• Pausas: Reseteadas\n"
                  f"• Minutos extra: Reseteados\n"
                  f"• **Créditos: CONSERVADOS para todos**\n"
                  f"• **Tiempo Altos-Supremos: Reseteado a 0**\n"
                  f"• **Tiempo Reclutas/Gold/Medios: CONSERVADO**",
            inline=False
        )

        embed.add_field(
            name="ℹ️ Resultado:",
            value=f"• Altos-Supremos: Tiempo en 0, créditos conservados\n"
                  f"• Reclutas/Gold/Medios: Tiempo y créditos conservados\n"
                  f"• Todos pueden trabajar nuevamente",
            inline=False
        )

        embed.set_footer(text=f"Ejecutado por {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        await interaction.response.send_message(f"❌ Error al resetear límites: {e}", ephemeral=True)
        print(f"Error en reseteo de límites: {e}")

@bot.tree.command(name="limpiar_db_reclutas_gold_medios", description="Limpiar SOLO usuarios reclutas, gold y medios de la base de datos")
@discord.app_commands.describe(confirmar="Escribe 'SI' para confirmar la eliminación de reclutas, gold y medios")
@is_admin()
async def limpiar_db_reclutas_gold_medios(interaction: discord.Interaction, confirmar: str):
    """Ejecutar limpieza de solo reclutas, gold y medios - ELIMINA COMPLETAMENTE los registros + limpia minutos extras de TODOS"""
    if confirmar.upper() != "SI":
        await interaction.response.send_message("❌ Operación cancelada. Debes escribir 'SI' para confirmar", ephemeral=True)
        return

    tracked_users = time_tracker.get_all_tracked_users()

    if not tracked_users:
        await interaction.response.send_message("❌ No hay usuarios registrados en la base de datos", ephemeral=True)
        return

    # Identificar usuarios a eliminar
    users_to_delete = []
    reclutas_deleted = 0
    gold_deleted = 0
    medios_deleted = 0
    total_extra_minutes_cleaned = 0
    extra_minutes_from_deleted = 0
    extra_minutes_from_kept = 0

    for user_id_str, data in tracked_users.items():
        try:
            user_id = int(user_id_str)
            member = interaction.guild.get_member(user_id) if interaction.guild else None

            if member:
                role_type = get_user_role_type(member)
                if role_type == "gold":
                    users_to_delete.append(user_id_str)
                    gold_deleted += 1
                    # Contar minutos extras antes de eliminar
                    extra_minutes_from_deleted += data.get('extra_minutes', 0)
                elif role_type == "medios":
                    users_to_delete.append(user_id_str)
                    medios_deleted += 1
                    extra_minutes_from_deleted += data.get('extra_minutes', 0)
                elif role_type == "normal":
                    users_to_delete.append(user_id_str)
                    reclutas_deleted += 1
                    extra_minutes_from_deleted += data.get('extra_minutes', 0)
            else:
                # Si no se encuentra el miembro, asumir recluta y eliminar
                users_to_delete.append(user_id_str)
                reclutas_deleted += 1
                extra_minutes_from_deleted += data.get('extra_minutes', 0)
        except Exception as e:
            print(f"Error procesando usuario {user_id_str}: {e}")
            continue

    # SIEMPRE limpiar minutos extras de TODOS los usuarios (incluso si no hay usuarios para eliminar)
    try:
        total_deleted = 0
        total_reset = 0

        # Paso 1: Eliminar usuarios reclutas, gold y medios (si hay)
        if users_to_delete:
            for user_id_str in users_to_delete:
                if user_id_str in time_tracker.data:
                    del time_tracker.data[user_id_str]
            total_deleted = reclutas_deleted + gold_deleted + medios_deleted

        # Paso 2: Limpiar minutos extras de TODOS los usuarios restantes
        for user_id_str in list(time_tracker.data.keys()):
            user_data = time_tracker.data[user_id_str]
            extra_minutes = user_data.get('extra_minutes', 0)
            if extra_minutes > 0:
                extra_minutes_from_kept += extra_minutes
                user_data['extra_minutes'] = 0

        # Paso 3: NUEVO - Resetear límites diarios de usuarios restantes que completaron sus horas máximas
        for user_id_str in list(time_tracker.data.keys()):
            user_data = time_tracker.data[user_id_str]

            # Solo resetear si completó su milestone
            if user_data.get('milestone_completed', False):
                user_id = int(user_id_str)
                member = interaction.guild.get_member(user_id) if interaction.guild else None
                role_type = get_user_role_type(member) if member else "normal"

                confirmed_credits = user_data.get('confirmed_credits', 0)
                historical_time = time_tracker.get_total_time(user_id)

                # Roles Altos-Supremos: resetear tiempo a 0 (conservando solo créditos)
                if role_type in ["altos", "imperiales", "nobleza", "monarquia", "supremos"]:
                    success = time_tracker.reset_daily_limit_zero_time(user_id_str, confirmed_credits)
                    if success:
                        total_reset += 1

        # Guardar cambios permanentemente
        time_tracker.save_data()

        # Contar usuarios restantes
        remaining_users = len(time_tracker.data)
        total_extra_minutes_cleaned = extra_minutes_from_deleted + extra_minutes_from_kept

        embed = discord.Embed(
            title="🗑️ BASE DE DATOS LIMPIADA",
            description="Minutos extras eliminados de TODOS los usuarios" + (f" + Usuarios eliminados" if total_deleted > 0 else ""),
            color=discord.Color.green(),
            timestamp=datetime.now()
        )

        if total_deleted > 0:
            embed.add_field(
                name="📊 Datos eliminados:",
                value=f"• {reclutas_deleted} Reclutas\n"
                      f"• {gold_deleted} Gold\n"
                      f"• {medios_deleted} Medios\n"
                      f"• **Total: {total_deleted} usuarios eliminados**\n"
                      f"• Todo su historial de tiempo\n"
                      f"• Sesiones activas\n"
                      f"• Créditos acumulados",
                inline=False
            )

        embed.add_field(
            name="🧹 Minutos extras limpiados:",
            value=f"• {extra_minutes_from_deleted} minutos de usuarios eliminados\n"
                  f"• {extra_minutes_from_kept} minutos de usuarios conservados\n"
                  f"• **Total: {total_extra_minutes_cleaned} minutos extras limpiados de TODOS**",
            inline=False
        )

        embed.add_field(
            name="✅ Estado final:",
            value=f"{remaining_users} usuarios totales en la base de datos (sin minutos extras)",
            inline=False
        )
        embed.set_footer(text=f"Ejecutado por {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        await interaction.response.send_message(f"❌ Error al limpiar la base de datos: {e}", ephemeral=True)
        print(f"Error en limpieza de reclutas/gold/medios: {e}")

@bot.tree.command(name="cancelar_tiempo", description="Cancelar tiempo del usuario conservando solo horas completas")
@discord.app_commands.describe(usuario="El usuario cuyo tiempo se cancelará (conserva horas completas)")
@is_admin()
async def cancelar_tiempo(interaction: discord.Interaction, usuario: discord.Member):
    user_data = time_tracker.get_user_data(usuario.id)
    total_time = time_tracker.get_total_time(usuario.id)
    user_id = usuario.id

    if user_data:
        # Calcular horas completas y tiempo perdido
        total_hours = int(total_time // 3600)
        hours_time = total_hours * 3600  # Solo horas completas en segundos
        lost_time = total_time - hours_time  # Tiempo perdido (minutos/segundos)

        formatted_total_time = time_tracker.format_time_human(total_time)
        formatted_hours_time = time_tracker.format_time_human(hours_time)
        formatted_lost_time = time_tracker.format_time_human(lost_time)

        # Usar la nueva función de cancelación que conserva horas
        success = time_tracker.cancel_user_tracking_keep_hours(user_id)
        if success:
            if lost_time > 0:
                await interaction.response.send_message(
                    f"🗑️ El tiempo de {usuario.mention} ha sido cancelado\n"
                    f"✅ **Tiempo conservado:** {formatted_hours_time} (horas completas)\n"
                    f"❌ **Tiempo perdido:** {formatted_lost_time}"
                )
                await send_cancellation_notification(usuario.display_name, interaction.user.mention, formatted_total_time, formatted_hours_time, formatted_lost_time)
            else:
                await interaction.response.send_message(
                    f"🗑️ El tiempo de {usuario.mention} ha sido cancelado\n"
                    f"✅ **Tiempo conservado:** {formatted_hours_time}"
                )
                await send_cancellation_notification(usuario.display_name, interaction.user.mention, formatted_total_time, formatted_hours_time)
        else:
            await interaction.response.send_message(f"❌ Error al cancelar el tiempo para {usuario.mention}", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ No se encontró registro de tiempo para {usuario.mention}", ephemeral=True)

# Comandos de configuración de canales removidos - ahora se configuran directamente en config.json

@bot.tree.command(name="ver_tiempo", description="Ver estadísticas detalladas de un usuario")
@discord.app_commands.describe(usuario="El usuario del que ver estadísticas")
@is_admin()
async def ver_tiempo(interaction: discord.Interaction, usuario: discord.Member):
    user_data = time_tracker.get_user_data(usuario.id)

    if not user_data:
        await interaction.response.send_message(f"❌ No se encontraron datos para {usuario.mention}", ephemeral=True)
        return

    base_time = time_tracker.get_total_time(usuario.id)
    extra_minutes = time_tracker.get_extra_minutes(usuario.id)

    formatted_base_time = time_tracker.format_time_human(base_time)

    # Mostrar tiempo base
    time_display = formatted_base_time

    # Si tiene minutos extra, mostrarlos separadamente
    if extra_minutes > 0:
        time_display += f" + {extra_minutes} min extra"

    embed = discord.Embed(
        title=f"📊 Estadísticas de {usuario.display_name}",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )

    embed.add_field(name="⏱️ Tiempo Base", value=formatted_base_time, inline=True)

    if extra_minutes > 0:
        embed.add_field(name="➕ Minutos Extra", value=f"{extra_minutes} minutos", inline=True)

    # Determinar estado del usuario
    total_hours = base_time / 3600
    role_type = get_user_role_type(usuario)

    # Verificar si ha completado su tiempo máximo
    is_finished = (user_data.get("milestone_completed", False) or
                  (role_type == "gold" and total_hours >= 2.0) or
                  (role_type == "normal" and total_hours >= 1.0))

    if user_data.get('is_active', False):
        status = "🟢 Activo"
    elif is_finished:
        status = "✅ Terminado"
    elif user_data.get('is_paused', False):
        status = "⏸️ Pausado"
    elif user_data.get('daily_limit_reset', False) and total_hours > 0:
        status = "✅ Terminado"
    else:
        status = "🔴 Inactivo"

    embed.add_field(name="📍 Estado", value=status, inline=True)

    # SIEMPRE obtener el rol actualizado del usuario desde Discord
    role_type = get_user_role_type(usuario)

    # Mostrar tipo de rol del usuario con TODOS los roles
    if role_type == "gold":
        embed.add_field(name="🎭 Tipo de Usuario", value="🏆 Gold - Límite: 2 horas - 6 créditos/hora", inline=True)
    elif role_type in ROLE_TIERS:
        tier_config = ROLE_TIERS[role_type]
        role_display_names = {
            "supremos": "Supremos",
            "monarquia": "Monarquía",
            "nobleza": "Nobleza",
            "imperiales": "Imperiales",
            "altos": "Altos",
            "medios": "Medios"
        }
        display_name = role_display_names.get(role_type, role_type.capitalize())

        if role_type == "medios":
            credits_info = f"1h: {tier_config['credits_1h']} créditos, 2h: {tier_config['credits_2h']} créditos"
        else:
            credits_per_hour = tier_config.get('credits_per_hour', 0)
            credits_info = f"{credits_per_hour:.2f} créditos/hora"

        # TODOS los roles de tier tienen límite de 2 horas máximas
        embed.add_field(
            name="🎭 Tipo de Usuario",
            value=f"🔰 {display_name} - Límite: 2h máx - {credits_info}",
            inline=True
        )
    else:
        embed.add_field(name="🎭 Tipo de Usuario", value="👤 Recluta - Límite: 1 hora - 4 créditos/hora", inline=True)

    # Mostrar tiempo pausado si aplica
    if user_data.get('is_paused', False):
        paused_duration = time_tracker.get_paused_duration(usuario.id)
        formatted_paused_time = time_tracker.format_time_human(paused_duration) if paused_duration > 0 else "0 Segundos"
        embed.add_field(
            name="⏸️ Tiempo Pausado",
            value=formatted_paused_time,
            inline=False
        )

    # Mostrar contador de pausas (igual para todos los usuarios)
    pause_count = time_tracker.get_pause_count(usuario.id)
    pause_text = "pausa" if pause_count == 1 else "pausas"
    embed.add_field(
        name="📊 Pausas",
        value=f"{pause_count} {pause_text} de 3 máximo",
        inline=True
    )

    # Mostrar SOLO créditos confirmados (los que ya fueron notificados oficialmente)
    confirmed_credits = get_confirmed_credits(usuario.id)

    # Solo mostrar si tiene créditos confirmados
    if confirmed_credits > 0:
        # Formatear créditos sin decimales si es entero
        credits_display = f"{int(confirmed_credits)}" if confirmed_credits == int(confirmed_credits) else f"{confirmed_credits:.2f}"
        embed.add_field(name="💰 Créditos Confirmados", value=f"{credits_display} créditos", inline=True)
    else:
        embed.add_field(name="💰 Créditos Confirmados", value="0 créditos (pendiente de confirmación)", inline=True)

    embed.set_thumbnail(url=usuario.avatar.url if usuario.avatar else usuario.default_avatar.url)
    embed.set_footer(text="Estadísticas actualizadas")

    await interaction.response.send_message(embed=embed)

# =================== SISTEMA DE ROLES SIMPLIFICADO ===================







@bot.tree.command(name="ver_pre_registrados", description="Ver usuarios pre-registrados esperando las 8 PM")
@is_admin()
async def ver_pre_registrados(interaction: discord.Interaction):
    """Mostrar usuarios que están pre-registrados"""
    try:
        pre_registered_users = time_tracker.get_pre_registered_users()

        if not pre_registered_users:
            await interaction.response.send_message("📋 No hay usuarios pre-registrados actualmente", ephemeral=True)
            return

        colombia_now = datetime.now(COLOMBIA_TZ)

        embed = discord.Embed(
            title="📋 Usuarios Pre-registrados",
            description="Usuarios esperando el inicio automático a las 17:00 Colombia",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        user_list = []
        for user_id_str, data in pre_registered_users.items():
            try:
                user_id = int(user_id_str)
                member = interaction.guild.get_member(user_id) if interaction.guild else None

                if member:
                    user_mention = member.mention
                else:
                    user_name = data.get('name', f'Usuario {user_id}')
                    user_mention = f"**{user_name}** `(ID: {user_id})`"

                pre_register_time = data.get('pre_register_time', '')
                if pre_register_time:
                    try:
                        register_dt = datetime.fromisoformat(pre_register_time)
                        time_str = register_dt.strftime("%H:%M")
                    except:
                        time_str = "N/A"
                else:
                    time_str = "N/A"

                user_list.append(f"📌 {user_mention} - Registrado a las {time_str}")

            except Exception as e:
                print(f"Error procesando usuario pre-registrado {user_id_str}: {e}")
                continue

        if user_list:
            embed.add_field(
                name=f"👥 Usuarios ({len(user_list)})",
                value="\n".join(user_list),
                inline=False
            )

        embed.add_field(
            name="⏰ Hora actual Colombia",
            value=colombia_now.strftime("%H:%M:%S"),
            inline=True
        )

        embed.add_field(
            name="🕐 Próximo inicio",
            value=f"{START_TIME_HOUR}:{START_TIME_MINUTE:02d} Colombia",
            inline=True
        )

        embed.set_footer(text=f"Los tiempos se iniciarán automáticamente a las {START_TIME_HOUR}:{START_TIME_MINUTE:02d} Colombia")

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        await interaction.response.send_message("❌ Error al obtener usuarios pre-registrados.", ephemeral=True)
        print(f"Error obteniendo pre-registrados: {e}")

@bot.tree.command(name="dar_creditos", description="Otorgar créditos directamente a un usuario")
@discord.app_commands.describe(
    usuario="El usuario al que dar créditos",
    cantidad="Cantidad de créditos a otorgar"
)
@is_admin()
async def dar_creditos(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    """Otorgar créditos directamente a un usuario sin necesidad de tiempo trabajado"""
    if cantidad <= 0:
        await interaction.response.send_message("❌ La cantidad de créditos debe ser positiva", ephemeral=True)
        return

    user_id = usuario.id
    user_data = time_tracker.get_user_data(user_id)

    # Si el usuario no existe en el sistema, crearlo
    if not user_data:
        time_tracker.data[str(user_id)] = {
            'name': usuario.display_name,
            'total_time': 0,
            'sessions': [],
            'is_active': False,
            'is_paused': False,
            'pause_count': 0,
            'notified_milestones': [],
            'milestone_completed': False,
            'is_pre_registered': False,
            'confirmed_credits': 0
        }
        user_data = time_tracker.data[str(user_id)]

    # Agregar créditos confirmados
    current_credits = user_data.get('confirmed_credits', 0)
    new_credits = current_credits + cantidad
    user_data['confirmed_credits'] = new_credits

    time_tracker.save_data()

    # Formatear créditos sin decimales si es entero
    credits_display = f"{int(new_credits)}" if new_credits == int(new_credits) else f"{new_credits:.2f}"
    cantidad_display = f"{int(cantidad)}" if cantidad == int(cantidad) else f"{cantidad:.2f}"

    await interaction.response.send_message(
        f"✅ Otorgados {cantidad_display} créditos a {usuario.mention} por {interaction.user.mention}\n"
        f"💰 Créditos totales de {usuario.display_name}: {credits_display} créditos"
    )

@bot.tree.command(name="quitar_creditos", description="Quitar créditos a un usuario")
@discord.app_commands.describe(
    usuario="El usuario al que quitar créditos",
    cantidad="Cantidad de créditos a quitar"
)
@is_admin()
async def quitar_creditos(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    """Quitar créditos confirmados de un usuario"""
    if cantidad <= 0:
        await interaction.response.send_message("❌ La cantidad de créditos debe ser positiva", ephemeral=True)
        return

    user_id = usuario.id
    user_data = time_tracker.get_user_data(user_id)

    # Verificar si el usuario existe
    if not user_data:
        await interaction.response.send_message(
            f"❌ {usuario.mention} no tiene créditos registrados en el sistema",
            ephemeral=True
        )
        return

    # Obtener créditos actuales
    current_credits = user_data.get('confirmed_credits', 0)

    if current_credits <= 0:
        await interaction.response.send_message(
            f"❌ {usuario.mention} no tiene créditos confirmados para quitar",
            ephemeral=True
        )
        return

    # Calcular nuevos créditos (no puede ser menor a 0)
    new_credits = max(0, current_credits - cantidad)
    credits_removed = current_credits - new_credits

    # Actualizar créditos
    user_data['confirmed_credits'] = new_credits
    time_tracker.save_data()

    # Formatear créditos sin decimales si es entero
    credits_display = f"{int(new_credits)}" if new_credits == int(new_credits) else f"{new_credits:.2f}"
    cantidad_display = f"{int(credits_removed)}" if credits_removed == int(credits_removed) else f"{credits_removed:.2f}"

    await interaction.response.send_message(
        f"➖ Quitados {cantidad_display} créditos de {usuario.mention} por {interaction.user.mention}\n"
        f"💰 Créditos restantes de {usuario.display_name}: {credits_display} créditos"
    )

@bot.tree.command(name="mi_tiempo", description="Ver tu propio tiempo registrado")
async def mi_tiempo(interaction: discord.Interaction):
    """Comando para que los usuarios vean su propio tiempo"""
    try:
        user_id = interaction.user.id
        user_data = time_tracker.get_user_data(user_id)

        if not user_data:
            await interaction.response.send_message(
                "❌ No tienes tiempo registrado aún. Un administrador debe iniciarte el tiempo primero.",
                ephemeral=True
            )
            return

        # Obtener tipo de rol del usuario PRIMERO
        member = interaction.guild.get_member(user_id) if interaction.guild else None
        role_type = get_user_role_type(member) if member else "normal"

        total_time = time_tracker.get_total_time(user_id)
        formatted_time = time_tracker.format_time_human(total_time)

        # Crear embed con información del usuario
        embed = discord.Embed(
            title=f"⏰ Tu Tiempo - {interaction.user.display_name}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        embed.add_field(name="⏱️ Tiempo Total", value=formatted_time, inline=True)

        # Mostrar minutos extra si los tiene
        extra_minutes = time_tracker.get_extra_minutes(user_id)
        if extra_minutes > 0:
            embed.add_field(
                name="➕ Minutos Extra",
                value=f"{extra_minutes} minutos",
                inline=True
            )

        # Determinar estado (usando tiempo base para verificación)
        total_hours = total_time / 3600

        # Verificar si ha completado su tiempo máximo
        is_finished = (user_data.get("milestone_completed", False) or
                      (role_type == "gold" and total_hours >= 2.0) or
                      (role_type == "normal" and total_hours >= 1.0))

        if user_data.get('is_active', False):
            status = "🟢 Activo"
        elif is_finished:
            status = "✅ Terminado"
        elif user_data.get('is_paused', False):
            status = "⏸️ Pausado"
        elif user_data.get('daily_limit_reset', False) and total_hours > 0:
            status = "✅ Terminado" # Considerar terminado si fue reseteado y tiene tiempo
        else:
            status = "🔴 Inactivo"

        embed.add_field(name="📍 Estado", value=status, inline=True)

        # Mostrar tiempo pausado si aplica
        if user_data.get('is_paused', False):
            paused_duration = time_tracker.get_paused_duration(user_id)
            formatted_paused_time = time_tracker.format_time_human(paused_duration) if paused_duration > 0 else "0 Segundos"
            embed.add_field(
                name="⏸️ Tiempo Pausado",
                value=formatted_paused_time,
                inline=False
            )

        # Mostrar contador de pausas si hay
        pause_count = time_tracker.get_pause_count(user_id)
        if pause_count > 0:
            pause_text = "pausa" if pause_count == 1 else "pausas"
            embed.add_field(
                name="📊 Pausas",
                value=f"{pause_count} {pause_text} de 3 máximo",
                inline=True
            )

        # Mostrar SOLO créditos confirmados (los que ya fueron notificados oficialmente)
        confirmed_credits = get_confirmed_credits(user_id)

        # Formatear créditos sin decimales si es entero
        credits_display = f"{int(confirmed_credits)}" if confirmed_credits == int(confirmed_credits) else f"{confirmed_credits:.2f}"
        embed.add_field(
            name="💰 Créditos Ganados",
            value=f"{credits_display} créditos",
            inline=True
        )

        # Mostrar límites según rol (INCLUIR GOLD CORRECTAMENTE)
        if role_type == "gold":
            embed.add_field(
                name="🎭 Tu Rol",
                value="🏆 Gold - Límite: 2 horas - 6 créditos/hora",
                inline=False
            )
        elif role_type in ROLE_TIERS:
            tier_config = ROLE_TIERS[role_type]
            role_display_names = {
                "supremos": "Supremos",
                "monarquia": "Monarquía",
                "nobleza": "Nobleza",
                "imperiales": "Imperiales",
                "altos": "Altos",
                "medios": "Medios"
            }
            display_name = role_display_names.get(role_type, role_type.capitalize())

            if role_type == "medios":
                credits_info = f"1h: {tier_config['credits_1h']} créditos, 2h: {tier_config['credits_2h']} créditos"
            else:
                credits_per_hour = tier_config.get('credits_per_hour', 0)
                credits_info = f"{credits_per_hour:.2f} créditos/hora"

            # TODOS los roles de tier tienen límite de 2 horas
            embed.add_field(
                name="🎭 Tu Rol",
                value=f"🔰 {display_name} - Límite: 2h - {credits_info}",
                inline=False
            )
        else:
            embed.add_field(
                name="🎭 Tu Rol",
                value="👤 Recluta - Límite: 1 hora - 4 créditos/hora",
                inline=False
            )

        embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
        embed.set_footer(text="Tu información personal de tiempo")

        await interaction.response.send_message(embed=embed, ephemeral=False)

    except Exception as e:
        await interaction.response.send_message("❌ Error al obtener tu información de tiempo.", ephemeral=True)
        print(f"Error en comando mi_tiempo para {interaction.user.display_name}: {e}")

# =================== COMANDOS DE PAGO SIMPLIFICADOS ===================

class PaymentMainView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=300)
        self.guild = guild

    @discord.ui.select(
        placeholder="Selecciona el tipo de usuarios a ver...",
        options=[
            discord.SelectOption(
                label="Reclutas (Sin Rol)",
                value="reclutas",
                description="4 créditos por hora",
                emoji="👤"
            ),
            discord.SelectOption(
                label="Gold",
                value="gold",
                description="6 créditos por hora",
                emoji="🏆"
            ),
            discord.SelectOption(
                label="Medios",
                value="medios",
                description="1h: 5 créditos, 2h: 10 créditos",
                emoji="🔰"
            ),
            discord.SelectOption(
                label="Altos",
                value="altos",
                description="20 créditos por hora",
                emoji="⚔️"
            ),
            discord.SelectOption(
                label="Imperiales",
                value="imperiales",
                description="26.67 créditos por hora",
                emoji="👑"
            ),
            discord.SelectOption(
                label="Nobleza",
                value="nobleza",
                description="30 créditos por hora",
                emoji="🏰"
            ),
            discord.SelectOption(
                label="Monarquía",
                value="monarquia",
                description="33.33 créditos por hora",
                emoji="💎"
            ),
            discord.SelectOption(
                label="Supremos",
                value="supremos",
                description="43.33 créditos por hora",
                emoji="⭐"
            )
        ]
    )
    async def select_payment_type(self, interaction: discord.Interaction, select: discord.ui.Select):
        selected_type = select.values[0]

        try:
            await interaction.response.defer()

            # Mapeo de tipos a nombres y filtros
            role_configs = {
                "reclutas": {
                    "name": "Reclutas (Sin Rol)",
                    "filter": lambda member, data: get_user_role_type(member) == "normal" if member else True
                },
                "gold": {
                    "name": "Gold",
                    "filter": lambda member, data: get_user_role_type(member) == "gold" if member else False
                },
                "medios": {
                    "name": "Medios",
                    "filter": lambda member, data: get_user_role_type(member) == "medios" if member else False
                },
                "altos": {
                    "name": "Altos",
                    "filter": lambda member, data: get_user_role_type(member) == "altos" if member else False
                },
                "imperiales": {
                    "name": "Imperiales",
                    "filter": lambda member, data: get_user_role_type(member) == "imperiales" if member else False
                },
                "nobleza": {
                    "name": "Nobleza",
                    "filter": lambda member, data: get_user_role_type(member) == "nobleza" if member else False
                },
                "monarquia": {
                    "name": "Monarquía",
                    "filter": lambda member, data: get_user_role_type(member) == "monarquia" if member else False
                },
                "supremos": {
                    "name": "Supremos",
                    "filter": lambda member, data: get_user_role_type(member) == "supremos" if member else False
                }
            }

            config = role_configs.get(selected_type)
            if not config:
                await interaction.edit_original_response(content="❌ Tipo de rol no válido")
                return

            filtered_users = get_users_by_role_filter(config["filter"], config["name"], interaction)
            role_name = config["name"]

            if not filtered_users:
                error_embed = discord.Embed(
                    title="❌ Sin Resultados",
                    description=f"No se encontraron usuarios para {role_name} con tiempo registrado",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=error_embed, view=self)
                return

            # Crear vista con resultados y actualizar mensaje existente
            view = PaymentView(filtered_users, role_name, self.guild)
            embed = view.get_embed()
            await interaction.edit_original_response(embed=embed, view=view)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"Error cargando datos: {e}",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=error_embed, view=self)

    @discord.ui.button(label='🔄 Actualizar', style=discord.ButtonStyle.success)
    async def refresh_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Solo actualizar la vista principal, no recargar datos hasta que seleccionen una opción
        await interaction.response.edit_message(view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

class PaymentView(discord.ui.View):
    def __init__(self, filtered_users, role_name, guild, search_term=None):
        super().__init__(timeout=300)
        self.filtered_users = filtered_users
        self.role_name = role_name
        self.guild = guild
        self.search_term = search_term
        self.current_page = 0
        self.max_per_page = 15
        self.total_pages = (len(filtered_users) + self.max_per_page - 1) // self.max_per_page if filtered_users else 1

        if self.total_pages <= 1:
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.label in ['◀️ Anterior', '▶️ Siguiente']:
                    item.disabled = True

    def get_embed(self):
        """Crear embed para la página actual"""
        start_idx = self.current_page * self.max_per_page
        end_idx = min(start_idx + self.max_per_page, len(self.filtered_users))
        current_users = self.filtered_users[start_idx:end_idx]

        role_emoji = "👤"
        if "Gold" in self.role_name:
            role_emoji = "🏆"

        title = f"{role_emoji} Pago - {self.role_name}"
        if self.search_term:
            title += f" (Búsqueda: '{self.search_term}')"

        embed = discord.Embed(
            title=title,
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )

        if not current_users:
            embed.description = f"No se encontraron usuarios para {self.role_name}"
            if self.search_term:
                embed.description += f" con el término '{self.search_term}'"
            embed.set_footer(text="No hay datos para mostrar")
            return embed

        user_list = []
        total_credits = 0

        for user_data in current_users:
            try:
                user_id = user_data['user_id']
                member = self.guild.get_member(user_id) if self.guild else None

                if member:
                    user_mention = member.mention
                else:
                    user_name = user_data.get('name', f'Usuario {user_id}')
                    user_mention = f"**{user_name}** `(ID: {user_id})`"

                total_time = user_data['total_time']
                formatted_time = time_tracker.format_time_human(total_time)
                credits = user_data['credits']
                total_credits += credits

                data = user_data.get('data', {})
                total_hours = total_time / 3600
                role_type = get_user_role_type(member) if member else "normal"

                # Determinar si completó su milestone
                is_finished = (data.get("milestone_completed", False) or
                             (role_type == "gold" and total_hours >= 2.0) or
                             (role_type in ["medios", "altos", "imperiales", "nobleza", "monarquia", "supremos"] and total_hours >= 1.0) or
                             (role_type == "normal" and total_hours >= 1.0))

                # Determinar estado
                if data.get('is_active', False):
                    status = "🟢 Activo"
                elif data.get('is_paused', False):
                    if is_finished:
                        status = "✅ Terminado"
                    else:
                        status = "⏸️ Pausado"
                elif is_finished:
                    status = "✅ Terminado"
                elif data.get('daily_limit_reset', False) and total_hours > 0:
                    status = "✅ Terminado" # Considerar terminado si fue reseteado y tiene tiempo
                else:
                    status = "🔴 Inactivo"

                # Formatear créditos sin decimales si es entero
                credits_display = f"{int(credits)}" if credits == int(credits) else f"{credits:.2f}"
                user_list.append(f"📌 {user_mention} - ⏱️ {formatted_time} - 💰 {credits_display} Créditos {status}")

            except Exception as e:
                print(f"Error procesando usuario en pago: {e}")
                continue

        embed.description = "\n".join(user_list)

        embed.add_field(
            name="📊 Resumen de Página",
            value=f"Usuarios: {len(current_users)}\nCréditos en página: {total_credits}",
            inline=True
        )

        total_users = len(self.filtered_users)
        total_all_credits = sum(user['credits'] for user in self.filtered_users)

        embed.add_field(
            name="🎯 Total General",
            value=f"Usuarios: {total_users}\nCréditos totales: {total_all_credits}",
            inline=True
        )

        embed.set_footer(text=f"Página {self.current_page + 1}/{self.total_pages} • {total_users} usuarios en total")
        return embed

    @discord.ui.button(label='◀️ Anterior', style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
        self.update_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='▶️ Siguiente', style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
        self.update_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='🔍 Buscar Usuario', style=discord.ButtonStyle.primary)
    async def search_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SearchUserModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='🔄 Actualizar', style=discord.ButtonStyle.success)
    async def refresh_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()

            # Determinar el tipo de filtro basado en el nombre del rol
            if "Gold" in self.role_name:
                def filter_func(member, data):
                    if not member:
                        return False
                    if GOLD_ROLE_ID:
                        for role in member.roles:
                            if role.id == GOLD_ROLE_ID:
                                return True
                    role_type = get_user_role_type(member)
                    return role_type == "gold"
            else:  # Reclutas
                def filter_func(member, data):
                    if not member:
                        return True
                    role_type = get_user_role_type(member)
                    return role_type == "normal"

            # Recargar datos
            refreshed_users = get_users_by_role_filter(filter_func, self.role_name, interaction)

            # Aplicar filtro de búsqueda si existe
            if self.search_term and refreshed_users:
                search_filtered = []
                for user_data in refreshed_users:
                    user_name = user_data.get('name', '').lower()
                    if self.search_term.lower() in user_name:
                        search_filtered.append(user_data)
                refreshed_users = search_filtered

            # Actualizar datos internos
            self.filtered_users = refreshed_users
            self.total_pages = (len(refreshed_users) + self.max_per_page - 1) // self.max_per_page if refreshed_users else 1

            # Asegurar que la página actual sea válida
            if self.current_page >= self.total_pages:
                self.current_page = max(0, self.total_pages - 1)

            # Actualizar botones
            self.update_buttons()

            # Obtener embed actualizado
            embed = self.get_embed()

            # Actualizar mensaje existente sin reenviar
            await interaction.edit_original_response(embed=embed, view=self)

        except Exception as e:
            await interaction.followup.send(f"❌ Error al actualizar: {e}", ephemeral=True)

    @discord.ui.button(label='🔄 Limpiar búsqueda', style=discord.ButtonStyle.secondary)
    async def clear_search(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.search_term:
            await interaction.response.send_message("❌ No hay búsqueda activa para limpiar", ephemeral=True)
            return

        try:
            await interaction.response.defer()

            # Determinar el tipo de filtro basado en el nombre del rol
            if "Gold" in self.role_name:
                def filter_func(member, data):
                    if not member:
                        return False
                    if GOLD_ROLE_ID:
                        for role in member.roles:
                            if role.id == GOLD_ROLE_ID:
                                return True
                    role_type = get_user_role_type(member)
                    return role_type == "gold"
            else:  # Reclutas
                def filter_func(member, data):
                    if not member:
                        return True
                    role_type = get_user_role_type(member)
                    return role_type == "normal"

            # Recargar datos sin filtro de búsqueda
            all_users = get_users_by_role_filter(filter_func, self.role_name, interaction)

            if not all_users:
                await interaction.edit_original_response(content="❌ No se encontraron usuarios para mostrar")
                return

            # Crear nueva vista sin filtro de búsqueda
            new_view = PaymentView(all_users, self.role_name, self.guild)
            embed = new_view.get_embed()

            await interaction.edit_original_response(embed=embed, view=new_view)

        except Exception as e:
            await interaction.edit_original_response(content=f"❌ Error al recargar: {e}")



    @discord.ui.button(label='🔙 Volver al Menú', style=discord.ButtonStyle.secondary)
    async def back_to_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()

            # Crear embed del menú principal
            embed = discord.Embed(
                title="💰 Sistema de Pagos",
                description="Selecciona el tipo de usuarios que deseas ver:",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )

            embed.add_field(
                name="👤 Reclutas",
                value="• Límite: 1 hora\n• 4 créditos/hora",
                inline=True
            )

            embed.add_field(
                name="🔰 Medios",
                value="• Límite: 2 horas\n• 1h: 5 créditos\n• 2h: 10 créditos",
                inline=True
            )

            embed.add_field(
                name="⚔️ Altos",
                value="• Límite: 1 hora\n• 20 créditos/hora",
                inline=True
            )

            embed.add_field(
                name="👑 Imperiales",
                value="• Límite: 1 hora\n• 26.67 créditos/hora",
                inline=True
            )

            embed.add_field(
                name="🏰 Nobleza",
                value="• Límite: 1 hora\n• 30 créditos/hora",
                inline=True
            )

            embed.add_field(
                name="💎 Monarquía",
                value="• Límite: 1 hora\n• 33.33 créditos/hora",
                inline=True
            )

            embed.add_field(
                name="⭐ Supremos",
                value="• Límite: 1 hora\n• 43.33 créditos/hora",
                inline=True
            )

            embed.set_footer(text="Sistema de créditos por niveles")

            # Volver a la vista del menú principal
            main_view = PaymentMainView(self.guild)
            await interaction.edit_original_response(embed=embed, view=main_view)

        except Exception as e:
            await interaction.followup.send(f"❌ Error al volver al menú: {e}", ephemeral=True)

    def update_buttons(self):
        """Actualizar estado de los botones"""
        self.children[0].disabled = (self.current_page == 0)
        self.children[1].disabled = (self.current_page >= self.total_pages - 1)

    async def on_timeout(self):
        """Deshabilitar botones cuando expire"""
        for item in self.children:
            item.disabled = True

class SearchUserModal(discord.ui.Modal):
    def __init__(self, payment_view):
        super().__init__(title='Buscar Usuario')
        self.payment_view = payment_view

    search_term = discord.ui.TextInput(
        label='Nombre del usuario',
        placeholder='Escribe parte del nombre del usuario...',
        required=True,
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        search_term = self.search_term.value.lower().strip()

        matching_users = []
        for user_data in self.payment_view.filtered_users:
            user_name = user_data.get('name', '').lower()
            if search_term in user_name:
                matching_users.append(user_data)

        if not matching_users:
            await interaction.response.send_message(
                f"❌ No se encontraron usuarios con '{self.search_term.value}' en {self.payment_view.role_name}",
                ephemeral=True
            )
            return

        new_view = PaymentView(matching_users, self.payment_view.role_name, self.payment_view.guild, search_term)
        embed = new_view.get_embed()

        await interaction.response.edit_message(embed=embed, view=new_view)

def get_users_by_role_filter(role_filter_func, role_name: str, interaction: discord.Interaction):
    """Función auxiliar para obtener usuarios filtrados por rol"""
    try:
        tracked_users = time_tracker.get_all_tracked_users()
        filtered_users = []

        for user_id_str, data in tracked_users.items():
            try:
                user_id = int(user_id_str)
                member = interaction.guild.get_member(user_id) if interaction.guild else None

                if not role_filter_func(member, data):
                    continue

                total_time = time_tracker.get_total_time(user_id)

                # Usar créditos confirmados guardados en el archivo
                credits = data.get('confirmed_credits', 0)

                # Si el tiempo es 0 Y no tiene créditos confirmados, omitir
                if total_time <= 0 and credits <= 0:
                    continue

                if member:
                    role_type = get_user_role_type(member)
                else:
                    role_type = "normal"

                user_info = {
                    'user_id': user_id,
                    'name': data.get('name', f'Usuario {user_id}'),
                    'total_time': total_time,
                    'credits': credits,
                    'role_type': role_type,
                    'data': data
                }

                filtered_users.append(user_info)

            except Exception as e:
                print(f"Error procesando usuario {user_id_str}: {e}")
                continue

        filtered_users.sort(key=lambda x: x['name'].lower())
        return filtered_users

    except Exception as e:
        print(f"Error en get_users_by_role_filter: {e}")
        return []



@bot.tree.command(name="pagas", description="Ver sistema de pagos con dropdown de opciones")
@is_admin()
async def pagas(interaction: discord.Interaction):
    """Comando principal de pagos con dropdown para seleccionar tipo de usuario"""
    try:
        embed = discord.Embed(
            title="💰 Sistema de Pagos",
            description="Selecciona el tipo de usuarios que deseas ver:",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )

        embed.add_field(
            name="👤 Reclutas",
            value="• Límite: 1 hora\n• 4 créditos/hora",
            inline=True
        )

        embed.add_field(
            name="🏆 Gold",
            value="• Límite: 2 horas\n• 6 créditos/hora",
            inline=True
        )

        embed.add_field(
            name="🔰 Medios",
            value="• Límite: 2 horas\n• 1h: 5 créditos\n• 2h: 10 créditos",
            inline=True
        )

        embed.add_field(
            name="🎖️ Altos",
            value="• Límite: 2h máx (pausa en 1h)\n• 10 créditos/hora\n• Total: 20 créditos",
            inline=True
        )

        embed.add_field(
            name="👑 Imperiales",
            value="• Límite: 2h máx (pausa en 1h)\n• 13.33 créditos/hora\n• Total: 26.67 créditos",
            inline=True
        )

        embed.add_field(
            name="🏰 Nobleza",
            value="• Límite: 2h máx (pausa en 1h)\n• 15 créditos/hora\n• Total: 30 créditos",
            inline=True
        )

        embed.add_field(
            name="👑 Monarquía",
            value="• Límite: 2h máx (pausa en 1h)\n• 16.67 créditos/hora\n• Total: 33.33 créditos",
            inline=True
        )

        embed.add_field(
            name="⭐ Supremos",
            value="• Límite: 2h máx (pausa en 1h)\n• 21.67 créditos/hora\n• Total: 43.33 créditos",
            inline=True
        )

        embed.set_footer(text="Sistema de créditos por niveles")

        view = PaymentMainView(interaction.guild)
        await interaction.response.send_message(embed=embed, view=view)

    except Exception as e:
        await interaction.response.send_message(f"❌ Error al mostrar sistema de pagos: {e}", ephemeral=True)

# =================== NOTIFICACIONES ===================

async def send_milestone_notification(user_name: str, member, is_external_user: bool, hours: int, total_time: float):
    """Enviar notificación cuando un usuario completa un milestone de hora - AQUÍ SE CALCULAN Y OTORGAN LOS CRÉDITOS"""
    try:
        channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
        if not channel:
            print(f"❌ Canal de notificaciones no encontrado: {NOTIFICATION_CHANNEL_ID}")
            return

        # Determinar tipo de rol
        role_type = "normal"
        if member:
            role_type = get_user_role_type(member)

        # CALCULAR CRÉDITOS BASADO EN LAS HORAS DEL MILESTONE COMPLETADO, NO EN TIEMPO BASE
        # Esto asegura que solo se otorguen créditos por horas efectivamente confirmadas
        milestone_time_seconds = hours * 3600  # Tiempo correspondiente al milestone (1h, 2h, etc.)
        credits = calculate_credits(milestone_time_seconds, role_type, user_id=member.id if member else None)

        # GUARDAR CRÉDITOS CONFIRMADOS SOLO AL ENVIAR LA NOTIFICACIÓN
        if member:
            user_id = member.id
            user_data = time_tracker.get_user_data(user_id)
            if user_data:
                # Actualizar créditos confirmados
                user_data['confirmed_credits'] = credits
                time_tracker.save_data()

        # Crear mención del usuario si es posible
        user_mention = member.mention if member else f"**{user_name}**"

        # Mapeo de nombres de roles
        role_display_names = {
            "supremos": "Supremos",
            "monarquia": "Monarquía",
            "nobleza": "Nobleza",
            "imperiales": "Imperiales",
            "altos": "Altos",
            "medios": "Medios",
            "gold": "Gold",
            "normal": "Recluta"
        }

        role_display = role_display_names.get(role_type, "Recluta")

        # Formatear créditos SIN decimales si es un número entero
        credits_display = f"{int(credits)}" if credits == int(credits) else f"{credits:.2f}"

        # Crear mensaje según el tipo de usuario
        if role_type == "gold":
            message = f"{user_mention} ha completado **{hours} hora{'s' if hours != 1 else ''}** (Gold - 6 Créditos/Hora)"
        elif role_type in ROLE_TIERS:
            # Roles por niveles
            message = f"{user_mention} ha completado **{hours} hora{'s' if hours != 1 else ''}** ( {credits_display} Créditos / {role_display} )"
        else:
            # Recluta/Normal
            message = f"{user_mention} ha completado **{hours} hora{'s' if hours != 1 else ''}** ( {credits_display} Créditos / {role_display} )"

        # ENVIAR CONFIRMACIÓN - momento en que se otorgan oficialmente los créditos
        await channel.send(message)

    except Exception as e:
        print(f"❌ Error enviando notificación de milestone para {user_name}: {e}")

async def send_auto_cancellation_notification(user_name: str, total_time: str, cancelled_by: str, pause_count: int, time_lost: float = 0):
    """Enviar notificación cuando un usuario es cancelado automáticamente por 3 pausas"""
    max_retries = 3

    for attempt in range(max_retries):
        try:
            channel = bot.get_channel(CANCELLATION_NOTIFICATION_CHANNEL_ID)
            if not channel:
                print(f"❌ Canal de cancelaciones no encontrado: {CANCELLATION_NOTIFICATION_CHANNEL_ID}")
                return

            formatted_time_lost = time_tracker.format_time_human(time_lost) if time_lost > 0 else "0 Segundos"
            message = f"🚫 **Tiempo Cancelado Automáticamente**\n**{user_name}** ha sido cancelado automáticamente por exceder el límite de pausas\n**Tiempo conservado:** {total_time} (solo horas completas)\n**Tiempo perdido:** {formatted_time_lost}\n**Pausas alcanzadas:** {pause_count}/3\n**Última pausa ejecutada por:** {cancelled_by}"

            await asyncio.wait_for(channel.send(message), timeout=10.0)
            print(f"✅ Notificación de cancelación automática enviada para {user_name} al canal {CANCELLATION_NOTIFICATION_CHANNEL_ID}")
            return

        except asyncio.TimeoutError:
            print(f"⚠️ Timeout enviando notificación de cancelación automática para {user_name} (intento {attempt + 1}/{max_retries})")
        except Exception as e:
            print(f"⚠️ Error enviando notificación de cancelación automática para {user_name} (intento {attempt + 1}): {e}")

        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)

    print(f"❌ CRÍTICO: No se pudo enviar notificación de cancelación automática para {user_name} después de {max_retries} intentos")

async def send_cancellation_notification(user_name: str, cancelled_by: str, total_time: str = "", conserved_time: str = "", lost_time: str = ""):
    """Enviar notificación cuando un usuario es cancelado"""
    channel = bot.get_channel(CANCELLATION_NOTIFICATION_CHANNEL_ID)
    if channel:
        try:
            if conserved_time and lost_time:
                message = f"🗑️ El seguimiento de tiempo de **{user_name}** ha sido cancelado\n**Tiempo total:** {total_time}\n**Tiempo conservado:** {conserved_time} (horas completas)\n**Tiempo perdido:** {lost_time}\n**Cancelado por:** {cancelled_by}"
            elif conserved_time:
                message = f"🗑️ El seguimiento de tiempo de **{user_name}** ha sido cancelado\n**Tiempo conservado:** {conserved_time}\n**Cancelado por:** {cancelled_by}"
            elif total_time:
                message = f"🗑️ El seguimiento de tiempo de **{user_name}** ha sido cancelado\n**Tiempo cancelado:** {total_time}\n**Cancelado por:** {cancelled_by}"
            else:
                message = f"🗑️ El seguimiento de tiempo de **{user_name}** ha sido cancelado por {cancelled_by}"
            await channel.send(message)
            print(f"✅ Notificación de cancelación enviada para {user_name}")
        except Exception as e:
            print(f"❌ Error enviando notificación de cancelación: {e}")

async def send_pause_notification(user_name: str, total_time: float, paused_by: str, session_time: str = "", pause_count: int = 0, role_type: str = "normal"):
    """Enviar notificación cuando un usuario es pausado"""
    max_retries = 3

    for attempt in range(max_retries):
        try:
            channel = bot.get_channel(PAUSE_NOTIFICATION_CHANNEL_ID)
            if not channel:
                print(f"❌ Canal de pausas no encontrado: {PAUSE_NOTIFICATION_CHANNEL_ID}")
                return

            formatted_total_time = time_tracker.format_time_human(total_time)

            # Mensaje uniforme para TODOS los usuarios (incluido Gold)
            if session_time and session_time != "0 Segundos":
                message = f"⏸️ El tiempo de **{user_name}** ha sido pausado\n**Tiempo de sesión pausado:** {session_time}\n**Tiempo total acumulado:** {formatted_total_time}\n**Pausado por:** {paused_by}\n📊 **{user_name}** lleva {pause_count}/3 pausas"
            else:
                message = f"⏸️ El tiempo de **{user_name}** ha sido pausado por {paused_by}\n**Tiempo total acumulado:** {formatted_total_time}\n📊 **{user_name}** lleva {pause_count}/3 pausas"

            # Agregar advertencia cuando llegue a 2/3 pausas
            if pause_count == 2:
                message += f"\n⚠️ **ADVERTENCIA:** Si se pausa **{user_name}** una vez más, se eliminarán los minutos acumulados y solo se conservarán las horas completas."

            await channel.send(message)
            return

        except asyncio.TimeoutError:
            print(f"⚠️ Timeout enviando notificación de pausa para {user_name} (intento {attempt + 1}/{max_retries})")
        except Exception as e:
            print(f"⚠️ Error enviando notificación de pausa para {user_name} (intento {attempt + 1}): {e}")

        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)

async def send_unpause_notification(user_name: str, total_time: float, unpaused_by: str, paused_duration: str = ""):
    """Enviar notificación cuando un usuario es despausado"""
    try:
        channel = bot.get_channel(PAUSE_NOTIFICATION_CHANNEL_ID)
        if not channel:
            return

        formatted_total_time = time_tracker.format_time_human(total_time)

        if paused_duration:
            message = f"⏸️ El tiempo de **{user_name}** ha sido despausado\n**Tiempo total acumulado:** {formatted_total_time}\n**Tiempo pausado:** {paused_duration}\n**Despausado por:** {unpaused_by}"
        else:
            message = f"⏸️ El tiempo de **{user_name}** ha sido despausado por {unpaused_by}"

        await asyncio.wait_for(channel.send(message), timeout=15.0)

    except asyncio.TimeoutError:
        print(f"⚠️ Timeout enviando notificación de despausa para {user_name}")
    except Exception as e:
        print(f"⚠️ Error enviando notificación de despausa para {user_name}: {e}")

async def check_time_milestone_for_tier_users(user_id: int, user_name: str, member, user_data: dict, role_type: str):
    """Lógica para usuarios de roles por niveles - 2 horas máximas con parada automática en 1h"""
    try:
        if not user_data.get('is_active', False) or not user_data.get('last_start'):
            return

        base_time = time_tracker.get_total_time(user_id)
        extra_minutes = time_tracker.get_extra_minutes(user_id)
        extra_seconds = extra_minutes * 60

        if 'notified_milestones' not in user_data:
            user_data['notified_milestones'] = []
            time_tracker.save_data()

        notified_milestones = user_data.get('notified_milestones', [])

        # TODOS los roles tier tienen 2 horas máximas
        max_hours = 2

        # Verificar milestone de 1 hora
        milestone_1h_with_extra = 3600 + extra_seconds
        if base_time >= milestone_1h_with_extra and 3600 not in notified_milestones:
            notified_milestones.append(3600)
            user_data['notified_milestones'] = notified_milestones
            time_tracker.save_data()

            # Enviar notificación de 1 hora
            await send_milestone_notification(user_name, member, False, 1, base_time)

            # DETENER automáticamente al completar 1 hora (pueden reiniciar para la segunda hora)
            time_tracker.stop_tracking(user_id)

        # Verificar milestone de 2 horas (segunda hora completada)
        milestone_2h_with_extra = 7200 + extra_seconds
        if base_time >= milestone_2h_with_extra and 7200 not in notified_milestones:
            notified_milestones.append(7200)
            user_data['notified_milestones'] = notified_milestones
            time_tracker.save_data()

            # Enviar notificación de 2 horas
            await send_milestone_notification(user_name, member, False, 2, base_time)

            # Detener y marcar como completado (ya cumplió sus 2 horas máximas)
            time_tracker.stop_tracking(user_id)
            user_data_refresh = time_tracker.get_user_data(user_id)
            if user_data_refresh:
                user_data_refresh['milestone_completed'] = True
                time_tracker.save_data()

    except Exception as e:
        print(f"❌ Error en check_time_milestone_for_tier_users para {user_name}: {e}")
        import traceback
        traceback.print_exc()

async def check_time_milestone_for_gold_users(user_id: int, user_name: str, member, user_data: dict):
    """Lógica específica para usuarios Gold - envía notificación por cada hora completa (considerando minutos extra)"""
    try:
        if not user_data.get('is_active', False) or not user_data.get('last_start'):
            return

        base_time = time_tracker.get_total_time(user_id)
        extra_minutes = time_tracker.get_extra_minutes(user_id)
        extra_seconds = extra_minutes * 60

        if 'notified_milestones' not in user_data:
            user_data['notified_milestones'] = []
            time_tracker.save_data()

        notified_milestones = user_data.get('notified_milestones', [])

        # Verificar milestone de 1 hora
        milestone_1h_with_extra = 3600 + extra_seconds
        if base_time >= milestone_1h_with_extra and 3600 not in notified_milestones:
            notified_milestones.append(3600)
            user_data['notified_milestones'] = notified_milestones
            time_tracker.save_data()
            await send_milestone_notification(user_name, member, False, 1, base_time)

        # Verificar milestone de 2 horas
        milestone_2h_with_extra = 7200 + extra_seconds
        if base_time >= milestone_2h_with_extra and 7200 not in notified_milestones:
            notified_milestones.append(7200)
            user_data['notified_milestones'] = notified_milestones
            time_tracker.save_data()
            await send_milestone_notification(user_name, member, False, 2, base_time)

            # Detener al completar 2 horas + minutos extra
            time_tracker.stop_tracking(user_id)
            user_data_refresh = time_tracker.get_user_data(user_id)
            if user_data_refresh:
                user_data_refresh['milestone_completed'] = True
                time_tracker.save_data()

    except Exception as e:
        print(f"❌ Error en check_time_milestone_for_gold_users para {user_name}: {e}")
        import traceback
        traceback.print_exc()

async def check_time_milestone_for_normal_users(user_id: int, user_name: str, member, user_data: dict):
    """Lógica específica para usuarios normales/reclutas - envía notificación por cada hora completa (considerando minutos extra)"""
    try:
        if not user_data.get('is_active', False) or not user_data.get('last_start'):
            return

        base_time = time_tracker.get_total_time(user_id)
        extra_minutes = time_tracker.get_extra_minutes(user_id)
        extra_seconds = extra_minutes * 60

        if 'notified_milestones' not in user_data:
            user_data['notified_milestones'] = []
            time_tracker.save_data()

        notified_milestones = user_data.get('notified_milestones', [])

        # Verificar milestone de 1 hora SOLO cuando base_time alcance 1 hora + minutos extra
        milestone_1h_with_extra = 3600 + extra_seconds

        # Verificar si alcanzó 1 hora + minutos extra y enviar notificación
        if base_time >= milestone_1h_with_extra and 3600 not in notified_milestones:
            # Marcar como notificado
            notified_milestones.append(3600)
            user_data['notified_milestones'] = notified_milestones
            time_tracker.save_data()

            # Enviar notificación (solo cuando alcance el tiempo total requerido)
            await send_milestone_notification(user_name, member, False, 1, base_time)

            # Detener automáticamente al completar 1 hora + minutos extra
            time_tracker.stop_tracking(user_id)
            user_data_refresh = time_tracker.get_user_data(user_id)
            if user_data_refresh:
                user_data_refresh['milestone_completed'] = True
                time_tracker.save_data()

    except Exception as e:
        print(f"❌ Error en check_time_milestone_for_normal_users para {user_name}: {e}")
        import traceback
        traceback.print_exc()



async def check_time_milestone(user_id: int, user_name: str):
    """Verificar milestones y dirigir a la función específica según el tipo de usuario"""
    try:
        user_data = time_tracker.get_user_data(user_id)
        if not user_data:
            return

        guild = None
        member = None
        try:
            guild = bot.guilds[0] if bot.guilds else None
            if guild:
                member = guild.get_member(user_id)
        except Exception as e:
            print(f"⚠️ Error obteniendo miembro del servidor para {user_name}: {e}")

        # Determinar tipo de usuario y dirigir a función específica
        if member:
            role_type = get_user_role_type(member)

            if role_type in ROLE_TIERS:
                # Usuario con rol por niveles
                await check_time_milestone_for_tier_users(user_id, user_name, member, user_data, role_type)
            elif role_type == "gold":
                # Usuario Gold - hasta 2 horas
                await check_time_milestone_for_gold_users(user_id, user_name, member, user_data)
            else:
                # Usuario normal/recluta - hasta 1 hora
                await check_time_milestone_for_normal_users(user_id, user_name, member, user_data)
        else:
            # Si no se puede obtener el miembro, asumir usuario normal
            await check_time_milestone_for_normal_users(user_id, user_name, None, user_data)

    except Exception as e:
        print(f"❌ Error crítico en check_time_milestone para {user_name}: {e}")
        import traceback
        traceback.print_exc()

async def periodic_milestone_check():
    """Verificar milestones periódicamente para usuarios activos con optimización de recursos"""
    milestone_check_count = 0
    error_count = 0
    max_errors = 3
    last_check_time = 0

    while True:
        try:
            # Intervalo adaptativo basado en carga
            sleep_interval = 15 if error_count == 0 else min(30 + (error_count * 10), 60)
            await asyncio.sleep(sleep_interval)

            current_time = asyncio.get_event_loop().time()
            milestone_check_count += 1

            # Verificación de milestones perdidos cada 2 minutos - función removida por simplicidad
            # if milestone_check_count % 8 == 1:
            #     print("⚠️ Verificación de milestones perdidos deshabilitada")

            # Optimización: solo verificar usuarios activos si ha pasado suficiente tiempo
            if current_time - last_check_time < 10:
                continue

            try:
                tracked_users = await asyncio.wait_for(
                    asyncio.to_thread(time_tracker.get_all_tracked_users),
                    timeout=30.0
                )

                # Filtrar solo usuarios activos
                active_users = [
                    (user_id_str, data) for user_id_str, data in tracked_users.items()
                    if data.get('is_active', False) and not data.get('is_paused', False)
                ]

                # Límite aumentado pero con mejor control
                max_active_users = 120
                active_users = active_users[:max_active_users]

                if not active_users:
                    last_check_time = current_time
                    continue

                # Usar semáforo para controlar concurrencia
                semaphore = asyncio.Semaphore(6)  # Máximo 6 operaciones concurrentes

                async def process_user_milestone(user_id_str, data):
                    async with semaphore:
                        try:
                            user_id = int(user_id_str)
                            user_name = data.get('name', f'Usuario {user_id}')

                            await asyncio.wait_for(
                                check_time_milestone(user_id, user_name),
                                timeout=20.0
                            )
                        except asyncio.TimeoutError:
                            print(f"⚠️ Timeout verificando milestone para {user_id_str}")
                        except Exception as e:
                            print(f"⚠️ Error verificando milestone para {user_id_str}: {e}")

                # Procesar en lotes controlados
                batch_size = 15
                for i in range(0, len(active_users), batch_size):
                    batch = active_users[i:i + batch_size]

                    tasks = [
                        process_user_milestone(user_id_str, data)
                        for user_id_str, data in batch
                    ]

                    try:
                        await asyncio.wait_for(
                            asyncio.gather(*tasks, return_exceptions=True),
                            timeout=45.0
                        )
                    except asyncio.TimeoutError:
                        print(f"⚠️ Timeout en lote {i//batch_size + 1} de milestones")

                    # Pausa entre lotes para no sobrecargar
                    if i + batch_size < len(active_users):
                        await asyncio.sleep(0.3)

                last_check_time = current_time

            except asyncio.TimeoutError:
                print("⚠️ Timeout obteniendo usuarios activos")
            except Exception as e:
                print(f"⚠️ Error obteniendo usuarios activos: {e}")

            error_count = 0

        except Exception as e:
            error_count += 1
            print(f"❌ Error en verificación periódica de milestones (#{error_count}): {e}")

            if error_count >= max_errors:
                print(f"🚨 Demasiados errores consecutivos ({error_count}). Pausando verificaciones por 90 segundos...")
                await asyncio.sleep(90)
                error_count = 0
            else:
                sleep_time = min(20 * (2 ** error_count), 120)
                await asyncio.sleep(sleep_time)

async def auto_start_at_1pm():
    """Verificar y iniciar automáticamente tiempos a las 17:00 Colombia"""
    while True:
        try:
            await asyncio.sleep(30)  # Verificar cada 30 segundos

            colombia_now = datetime.now(COLOMBIA_TZ)
            current_hour = colombia_now.hour
            current_minute = colombia_now.minute

            # Verificar si son exactamente las 17:00 (solo en el minuto exacto)
            if current_hour == START_TIME_HOUR and current_minute == START_TIME_MINUTE:
                print(f"🕐 Son las {START_TIME_HOUR}:{START_TIME_MINUTE:02d} Colombia - Iniciando tiempos automáticamente...")

                # Obtener usuarios pre-registrados
                pre_registered_users = time_tracker.get_pre_registered_users()

                if pre_registered_users:
                    started_users = []

                    for user_id_str, data in pre_registered_users.items():
                        user_id = int(user_id_str)
                        user_name = data.get('name', f'Usuario {user_id}')

                        # Obtener información del admin que hizo el pre-registro
                        initiator_info = time_tracker.get_pre_register_initiator(user_id)

                        # Iniciar tiempo automáticamente
                        success = time_tracker.start_tracking_from_pre_register(user_id)
                        if success:
                            # Intentar obtener el objeto del miembro para la mención
                            member = None
                            try:
                                if bot.guilds:
                                    guild = bot.guilds[0]
                                    member = guild.get_member(user_id)
                            except Exception as e:
                                print(f"⚠️ Error obteniendo miembro para notificación: {e}")

                            # Usar mención si es posible, sino usar nombre
                            if member:
                                user_reference = member.mention
                            else:
                                user_reference = f"**{user_name}**"

                            if initiator_info:
                                admin_name = initiator_info.get('admin_name', 'Admin desconocido')
                                started_users.append(f"• {user_reference} - Pre-registrado por: {admin_name}")
                            else:
                                started_users.append(f"• {user_reference} - Pre-registrado por: Admin desconocido")

                    if started_users:
                        # Notificación automática deshabilitada
                        # await send_auto_start_notification(started_users, colombia_now)
                        print(f"✅ Iniciados automáticamente {len(started_users)} usuarios a las 17:00 Colombia (sin notificación)")

                # Esperar 70 segundos para evitar múltiples ejecuciones
                await asyncio.sleep(70)

        except Exception as e:
            print(f"❌ Error en auto-inicio a las 17:00 Colombia: {e}")
            await asyncio.sleep(30)

async def auto_stop_at_2225():
    """Detener automáticamente todos los tiempos a las 20:01 (8:01 PM) hora Colombia"""
    while True:
        try:
            await asyncio.sleep(30)  # Verificar cada 30 segundos

            colombia_now = datetime.now(COLOMBIA_TZ)
            current_hour = colombia_now.hour
            current_minute = colombia_now.minute

            # Verificar si son exactamente las 20:01 (8:01 PM)
            if current_hour == 20 and current_minute == 1:
                print(f"🛑 Son las 20:01 Colombia - Deteniendo todos los tiempos automáticamente...")

                # Obtener todos los usuarios con tiempo activo
                tracked_users = time_tracker.get_all_tracked_users()
                stopped_count = 0

                for user_id_str, data in tracked_users.items():
                    if data.get('is_active', False) or data.get('is_paused', False):
                        user_id = int(user_id_str)

                        # Detener el tiempo
                        success = time_tracker.stop_tracking(user_id)
                        if success:
                            stopped_count += 1
                            user_name = data.get('name', f'Usuario {user_id}')
                            print(f"  ✅ Detenido tiempo de {user_name}")

                if stopped_count > 0:
                    print(f"✅ Detenidos automáticamente {stopped_count} usuarios a las 20:01 Colombia")

                # Esperar 70 segundos para evitar múltiples ejecuciones
                await asyncio.sleep(70)

        except Exception as e:
            print(f"❌ Error en detención automática a las 20:01 Colombia: {e}")
            await asyncio.sleep(30)

async def auto_reset_daily_limits():
    """Resetear límites diarios a las 00:00 Colombia conservando créditos"""
    while True:
        try:
            await asyncio.sleep(30)  # Verificar cada 30 segundos

            colombia_now = datetime.now(COLOMBIA_TZ)
            current_hour = colombia_now.hour
            current_minute = colombia_now.minute

            # Verificar si son exactamente las 00:00 (medianoche)
            if current_hour == 0 and current_minute == 0:
                print(f"🔄 Medianoche Colombia - Reseteando límites diarios...")

                tracked_users = time_tracker.get_all_tracked_users()
                reset_count = 0

                for user_id_str, data in tracked_users.items():
                    # Solo resetear usuarios que completaron su milestone
                    if data.get('milestone_completed', False):
                        user_id = int(user_id_str)
                        user_name = data.get('name', f'Usuario {user_id}')

                        # Conservar créditos confirmados
                        confirmed_credits = data.get('confirmed_credits', 0)

                        # Resetear tiempo pero conservar créditos
                        success = time_tracker.reset_daily_time_keep_credits(user_id, confirmed_credits)
                        if success:
                            reset_count += 1
                            print(f"  ✅ Reseteado límite diario de {user_name} (créditos conservados: {confirmed_credits})")

                if reset_count > 0:
                    print(f"✅ Reseteados límites de {reset_count} usuarios a las 00:00 Colombia")

                # Esperar 70 segundos para evitar múltiples ejecuciones
                await asyncio.sleep(70)

        except Exception as e:
            print(f"❌ Error en reseteo automático a las 00:00 Colombia: {e}")
            await asyncio.sleep(30)

async def start_periodic_checks():
    """Iniciar las verificaciones periódicas"""
    global milestone_check_task, auto_start_task, auto_stop_task, auto_reset_task

    if milestone_check_task is None:
        milestone_check_task = bot.loop.create_task(periodic_milestone_check())
        print('✅ Task de verificación de milestones iniciado')

    if auto_start_task is None:
        auto_start_task = bot.loop.create_task(auto_start_at_1pm())
        print('✅ Task de inicio automático a las 17:00 Colombia iniciado')

    if 'auto_stop_task' not in globals() or auto_stop_task is None:
        auto_stop_task = bot.loop.create_task(auto_stop_at_2225())
        print('✅ Task de detención automática a las 20:01 Colombia iniciado')

    if 'auto_reset_task' not in globals() or auto_reset_task is None:
        auto_reset_task = bot.loop.create_task(auto_reset_daily_limits())
        print('✅ Task de reseteo automático a las 00:00 Colombia iniciado')

@bot.event
async def on_connect():
    """Evento que se ejecuta cuando el bot se conecta"""
    await start_periodic_checks()

# =================== MANEJO DE ERRORES ===================

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    try:
        command_name = interaction.command.name if interaction.command else 'desconocido'
        print(f"Error en comando /{command_name}: {type(error).__name__}")

        if isinstance(error, discord.app_commands.CommandInvokeError):
            original_error = error.original if hasattr(error, 'original') else error

            if isinstance(original_error, discord.NotFound) and "10062" in str(original_error):
                print(f"⚠️ Interacción /{command_name} expirada (10062) - no respondiendo")
                return
            elif "Unknown interaction" in str(original_error):
                print(f"⚠️ Interacción /{command_name} desconocida - no respondiendo")
                return

        if isinstance(error, discord.app_commands.CheckFailure):
            error_msg = "❌ No tienes permisos para usar este comando."
        elif isinstance(error, discord.app_commands.CommandInvokeError):
            error_msg = "❌ Error interno del comando. El administrador ha sido notificado."
        elif isinstance(error, discord.app_commands.TransformerError):
            error_msg = "❌ Error en los parámetros. Verifica los valores ingresados."
        elif isinstance(error, discord.app_commands.CommandOnCooldown):
            error_msg = f"⏰ Comando en cooldown. Intenta de nuevo en {error.retry_after:.1f}s"
        else:
            error_msg = "❌ Error inesperado. Intenta de nuevo."

        try:
            if not interaction.response.is_done():
                await asyncio.wait_for(
                    interaction.response.send_message(error_msg, ephemeral=True),
                    timeout=2.0
                )
            else:
                await asyncio.wait_for(
                    interaction.followup.send(error_msg, ephemeral=True),
                    timeout=2.0
                )
        except asyncio.TimeoutError:
            print(f"⚠️ Timeout respondiendo a error en /{command_name}")
        except discord.NotFound:
            print(f"⚠️ Interacción /{command_name} no encontrada al responder error")
        except discord.HTTPException as e:
            if "10062" not in str(e):
                print(f"⚠️ Error HTTP respondiendo a /{command_name}: {e}")
        except Exception as e:
            print(f"⚠️ Error inesperado respondiendo a /{command_name}: {e}")

    except Exception as e:
        print(f"❌ Error crítico en manejo global de errores: {e}")

def get_discord_token():
    """Obtener token de Discord desde config.json o variables de entorno"""
    # Primero intentar desde config.json
    try:
        with open('config.json', 'r') as f:
            config_data = json.load(f)
        token = config_data.get('discord_bot_token', '')
        if token and isinstance(token, str) and token.strip() and token != "":
            print("✅ Token cargado desde config.json")
            return token.strip()
    except FileNotFoundError:
        print("⚠️ Archivo config.json no encontrado")
    except json.JSONDecodeError:
        print("⚠️ Error al leer config.json")
    except Exception as e:
        print(f"⚠️ Error leyendo config.json: {e}")

    # Si no está en config.json, intentar desde variables de entorno
    env_token = os.getenv('DISCORD_BOT_TOKEN')
    if env_token and isinstance(env_token, str) and env_token.strip():
        print("✅ Token cargado desde variables de entorno (Secrets)")
        return env_token.strip()

    print("❌ Error: No se encontró el token de Discord")
    print("┌─ Configura tu token de Discord:")
    print("│")
    print("│ OPCIÓN 1 (Recomendada): En config.json")
    print("│ Edita config.json y pega tu token en:")
    print('│ "discord_bot_token": "TU_TOKEN_AQUI"')
    print("│")
    print("│ OPCIÓN 2: Variable de entorno DISCORD_BOT_TOKEN")
    print("│ En Replit, usa Secrets para configurar DISCORD_BOT_TOKEN")
    print("└─")
    return None

if __name__ == "__main__":
    print("🤖 Iniciando Discord Time Tracker Bot SIMPLIFICADO...")
    print("📋 Cargando configuración...")

    token = get_discord_token()
    if not token:
        exit(1)

    print("🔗 Conectando a Discord...")
    try:
        bot.run(token)
    except discord.LoginFailure:
        print("❌ Error: Token de Discord inválido")
        print("   Verifica que el token sea correcto en config.json")
        print("   O en las variables de entorno si usas esa opción")
    except KeyboardInterrupt:
        print("🛑 Bot detenido por el usuario")
    except Exception as e:
        print(f"❌ Error al iniciar el bot: {e}")
        print("   Revisa la configuración y vuelve a intentar")