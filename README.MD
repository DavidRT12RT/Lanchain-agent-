# AgentBot con Redis Memory

Un chatbot inteligente con memoria persistente usando Redis y LangChain, con gestión avanzada de usuarios y sesiones.

## 🚀 Características

- **Memoria Persistente**: Utiliza Redis para mantener el historial de conversaciones entre sesiones
- **Gestión de Usuarios**: Sistema completo de perfiles de usuario con preferencias y contexto
- **Múltiples Herramientas**: Wikipedia, noticias, clima y hora actual
- **Arquitectura Modular**: Código organizado en controladores separados
- **Interfaz Web Redis**: Redis Commander para monitoreo y administración
- **Configuración Docker**: Fácil despliegue con docker-compose

## 📋 Requisitos

- Python 3.8+
- Docker y Docker Compose
- OpenAI API Key

## 🛠️ Instalación

### 1. Configuración Manual

```bash
# 1. Instalar dependencias de Python
pip install -r requirements.txt

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus configuraciones

# 3. Iniciar Redis con Docker
docker-compose up -d

# 4. Verificar que Redis esté funcionando
docker exec agent_redis redis-cli ping
```

## 📁 Estructura del Proyecto

```
├── main.py                    # Archivo principal del bot
├── docker-compose.yml         # Configuración de Docker
├── requirements.txt           # Dependencias de Python
├── .env.example              # Plantilla de variables de entorno
├── memory/
│   ├── __init__.py
│   └── redis_memory.py       # Memoria personalizada con Redis
├── controllers/
│   ├── __init__.py
│   └── user_controller.py    # Controlador de usuarios
└── README.md
```

## 🔧 Configuración

### Variables de Entorno (.env)

```env
# OpenAI Configuration
OPENAI_API_KEY=tu_clave_api_de_openai

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB_MEMORY=0
REDIS_DB_USERS=1

# Application Configuration
LOG_LEVEL=INFO
DEFAULT_SESSION_TTL=86400
MAX_MESSAGES_PER_SESSION=100
```

## 🚀 Uso

### Uso Básico

```python
from main import EnhancedAgentBot

# Crear instancia del bot
bot = EnhancedAgentBot(session_id="usuario123_sesion001")

# Crear usuario
user_data = {
    "user_id": "usuario123",
    "name": "Juan Pérez",
    "email": "juan@ejemplo.com",
    "preferences": {
        "language": "spanish",
        "topics_interest": ["tecnología", "ciencia"]
    }
}

# Registrar usuario
result = bot.user_controller.create_user(user_data)

# Obtener respuesta con contexto de usuario
response = bot.get_response("¡Hola! ¿Cómo estás?", user_id="usuario123")
print(response["answer"])
```

### Gestión de Memoria

```python
# Obtener información de memoria
memory_info = bot.get_memory_info()

# Buscar en el historial
search_results = bot.search_memory("inteligencia artificial")

# Obtener mensajes recientes
recent_messages = bot.get_recent_messages(5)

# Limpiar memoria de la sesión
bot.clear_memory()
```

### Gestión de Usuarios

```python
# Obtener información del usuario
user_info = bot.user_controller.get_user("usuario123")

# Actualizar preferencias
updates = {
    "preferences": {
        "language": "spanish",
        "notification_time": "evening"
    }
}
bot.user_controller.update_user("usuario123", updates)

# Obtener sesiones del usuario
sessions = bot.user_controller.get_user_sessions("usuario123")

# Listar todos los usuarios
all_users = bot.user_controller.list_all_users()
```

## 🔍 Monitoreo

### Redis Commander (Interfaz Web)

Accede a `http://localhost:8081` para:
- Ver datos en tiempo real
- Explorar claves de Redis
- Monitorear uso de memoria
- Debug de sesiones y usuarios

### Comandos Docker Útiles

```bash
# Ver logs de Redis
docker-compose logs redis

# Detener contenedores
docker-compose down

# Reiniciar contenedores
docker-compose restart

# Acceder a Redis CLI
docker exec -it agent_redis redis-cli

# Ver estadísticas de Redis
docker exec agent_redis redis-cli info memory
```

## 🏗️ Arquitectura

### Componentes Principales

1. **EnhancedAgentBot**: Clase principal que orquesta todo el sistema
2. **RedisMemory**: Memoria personalizada que extiende LangChain para usar Redis
3. **UserController**: Maneja perfiles, sesiones y contexto de usuarios
4. **Tools**: Herramientas integradas (Wikipedia, noticias, clima, tiempo)

### Bases de Datos Redis

- **DB 0**: Historial de conversaciones y memoria de sesiones
- **DB 1**: Perfiles de usuarios y datos de sesiones

### Flujo de Datos

```
Usuario → EnhancedAgentBot → LangChain Agent → Tools
                ↓
         RedisMemory ← → Redis DB 0 (conversaciones)
                ↓
       UserController ← → Redis DB 1 (usuarios)
```

## 🛡️ Características de Seguridad

- **TTL Automático**: Las sesiones expiran automáticamente
- **Límite de Mensajes**: Control de memoria por sesión
- **Aislamiento**: Bases de datos separadas para diferentes tipos de datos
- **Manejo de Errores**: Recuperación automática de fallos de conexión

## 🔄 Escalabilidad

- **Redis Cluster**: Soporte para clustering Redis
- **Múltiples Instancias**: Fácil escalado horizontal
- **Persistencia**: Datos sobreviven a reinicios
- **Backup**: Configuración automática de persistencia AOF

## 🐛 Solución de Problemas

### Redis no se conecta

```bash
# Verificar que Docker esté ejecutándose
docker ps

# Reiniciar contenedores
docker-compose down && docker-compose up -d

# Verificar logs
docker-compose logs redis
```

### Error de dependencias

```bash
# Reinstalar dependencias
pip install --upgrade -r requirements.txt

# Verificar versión de Python
python --version  # Debe ser 3.8+
```

### Problemas de memoria

```bash
# Limpiar todas las sesiones
docker exec agent_redis redis-cli FLUSHDB

# Ver uso de memoria
docker exec agent_redis redis-cli info memory
```

## 📚 API Reference

### EnhancedAgentBot

- `get_response(question, user_id)`: Obtener respuesta del agente
- `get_memory_info()`: Información de memoria actual
- `clear_memory()`: Limpiar memoria de la sesión
- `search_memory(query)`: Buscar en el historial
- `get_recent_messages(count)`: Obtener mensajes recientes

### UserController

- `create_user(user_data)`: Crear nuevo usuario
- `get_user(user_id)`: Obtener información del usuario
- `update_user(user_id, updates)`: Actualizar usuario
- `delete_user(user_id)`: Eliminar usuario
- `get_user_sessions(user_id)`: Obtener sesiones del usuario
- `get_user_context(user_id)`: Obtener contexto para el agente

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature
3. Commit tus cambios
4. Push a la rama
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la licencia MIT. Ver archivo LICENSE para más detalles.

## 🆘 Soporte

Si encuentras problemas o tienes preguntas:

1. Revisa la sección de solución de problemas
2. Verifica los logs de Docker
3. Crea un issue en el repositorio

---

¡Happy coding! 🚀