import json
import redis
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

class UserProfile(BaseModel):
    """Modelo para el perfil del usuario"""
    user_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    preferences: Dict[str, Any] = {}
    created_at: str = None #type: ignore
    last_active: str = None #type: ignore
    session_count: int = 0
    
    def __init__(self, **data):
        if 'created_at' not in data:
            data['created_at'] = datetime.now().isoformat()
        if 'last_active' not in data:
            data['last_active'] = datetime.now().isoformat()
        super().__init__(**data)

class UserController:
    """Controlador para manejar información de usuarios"""
    
    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 1,  # Base de datos diferente para usuarios
        redis_password: Optional[str] = None
    ):
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
        
        try:
            self.redis_client.ping()
            logger.info("UserController conectado exitosamente a Redis")
        except redis.ConnectionError as e:
            logger.error(f"Error conectando UserController a Redis: {e}")
            raise
    
    def _get_user_key(self, user_id: str) -> str:
        """Generar clave para usuario"""
        return f"user:{user_id}"
    
    def _get_session_key(self, user_id: str) -> str:
        """Generar clave para sesiones del usuario"""
        return f"user_sessions:{user_id}"
    
    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crear un nuevo usuario"""
        try:
            if 'user_id' not in user_data:
                raise ValueError("user_id es requerido")
            
            user_id = user_data['user_id']
            user_key = self._get_user_key(user_id)
            
            # Verificar si el usuario ya existe
            if self.redis_client.exists(user_key):
                return {
                    "success": False,
                    "message": f"Usuario {user_id} ya existe"
                }
            
            # Crear perfil de usuario
            user_profile = UserProfile(**user_data)
            
            # Guardar en Redis
            self.redis_client.hset(
                user_key,
                mapping=user_profile.dict() #type: ignore
            )
            
            # Set TTL de 30 días
            self.redis_client.expire(user_key, 2592000)
            
            logger.info(f"Usuario {user_id} creado exitosamente")
            return {
                "success": True,
                "message": f"Usuario {user_id} creado exitosamente",
                "user": user_profile.dict()
            }
            
        except Exception as e:
            logger.error(f"Error creando usuario: {e}")
            return {
                "success": False,
                "message": f"Error creando usuario: {str(e)}"
            }
    
    def get_user(self, user_id: str) -> Dict[str, Any]:
        """Obtener información del usuario"""
        try:
            user_key = self._get_user_key(user_id)
            user_data = self.redis_client.hgetall(user_key)
            
            if not user_data:
                return {
                    "success": False,
                    "message": f"Usuario {user_id} no encontrado",
                    "user": None
                }
            
            # Actualizar last_active
            self.redis_client.hset(user_key, "last_active", datetime.now().isoformat())
            
            return {
                "success": True,
                "message": "Usuario encontrado",
                "user": user_data
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo usuario {user_id}: {e}")
            return {
                "success": False,
                "message": f"Error obteniendo usuario: {str(e)}",
                "user": None
            }
    
    def update_user(self, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Actualizar información del usuario"""
        try:
            user_key = self._get_user_key(user_id)
            
            # Verificar si el usuario existe
            if not self.redis_client.exists(user_key):
                return {
                    "success": False,
                    "message": f"Usuario {user_id} no encontrado"
                }
            
            # Actualizar campos
            updates["last_active"] = datetime.now().isoformat()
            self.redis_client.hset(user_key, mapping=updates) #type: ignore
            
            # Obtener datos actualizados
            updated_user = self.redis_client.hgetall(user_key)
            
            return {
                "success": True,
                "message": f"Usuario {user_id} actualizado exitosamente",
                "user": updated_user
            }
            
        except Exception as e:
            logger.error(f"Error actualizando usuario {user_id}: {e}")
            return {
                "success": False,
                "message": f"Error actualizando usuario: {str(e)}"
            }
    
    def delete_user(self, user_id: str) -> Dict[str, Any]:
        """Eliminar usuario y sus datos relacionados"""
        try:
            user_key = self._get_user_key(user_id)
            session_key = self._get_session_key(user_id)
            
            # Eliminar datos del usuario
            user_deleted = self.redis_client.delete(user_key)
            sessions_deleted = self.redis_client.delete(session_key)
            
            # Eliminar historial de chat (requiere acceso a la otra DB)
            chat_key = f"chat_history:{user_id}"
            # Nota: Esto requeriría acceso a la DB 0 donde están los chats
            
            return {
                "success": True,
                "message": f"Usuario {user_id} eliminado exitosamente",
                "deleted_records": {
                    "user": user_deleted > 0,
                    "sessions": sessions_deleted > 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error eliminando usuario {user_id}: {e}")
            return {
                "success": False,
                "message": f"Error eliminando usuario: {str(e)}"
            }
    
    def add_session(self, user_id: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Agregar una nueva sesión para el usuario"""
        try:
            session_key = self._get_session_key(user_id)
            session_data["timestamp"] = datetime.now().isoformat()
            session_data["session_id"] = session_data.get("session_id", user_id)
            
            # Agregar sesión a la lista
            self.redis_client.lpush(session_key, json.dumps(session_data))
            
            # Mantener solo las últimas 20 sesiones
            self.redis_client.ltrim(session_key, 0, 19)
            
            # Actualizar contador de sesiones del usuario
            user_key = self._get_user_key(user_id)
            self.redis_client.hincrby(user_key, "session_count", 1)
            
            return {
                "success": True,
                "message": f"Sesión agregada para usuario {user_id}",
                "session": session_data
            }
            
        except Exception as e:
            logger.error(f"Error agregando sesión para usuario {user_id}: {e}")
            return {
                "success": False,
                "message": f"Error agregando sesión: {str(e)}"
            }
    
    def get_user_sessions(self, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """Obtener las sesiones del usuario"""
        try:
            session_key = self._get_session_key(user_id)
            sessions_data = self.redis_client.lrange(session_key, 0, limit - 1)
            
            sessions = []
            for session_json in sessions_data:
                sessions.append(json.loads(session_json))
            
            return {
                "success": True,
                "message": f"Sesiones encontradas para usuario {user_id}",
                "sessions": sessions,
                "total": len(sessions)
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo sesiones para usuario {user_id}: {e}")
            return {
                "success": False,
                "message": f"Error obteniendo sesiones: {str(e)}",
                "sessions": []
            }
    
    def get_user_context(self, user_id: str) -> Dict[str, Any]:
        """Obtener contexto completo del usuario para el agente"""
        try:
            # Obtener información del usuario
            user_result = self.get_user(user_id)
            if not user_result["success"]:
                return {"user_context": None}
            
            user_data = user_result["user"]
            
            # Obtener sesiones recientes
            sessions_result = self.get_user_sessions(user_id, 5)
            recent_sessions = sessions_result.get("sessions", [])
            
            # Construir contexto para el agente
            context = {
                "user_id": user_id,
                "name": user_data.get("name", "Usuario"),
                "preferences": user_data.get("preferences", {}),
                "session_count": int(user_data.get("session_count", 0)),
                "recent_sessions": len(recent_sessions),
                "last_active": user_data.get("last_active"),
                "created_at": user_data.get("created_at")
            }
            
            return {"user_context": context}
            
        except Exception as e:
            logger.error(f"Error obteniendo contexto para usuario {user_id}: {e}")
            return {"user_context": None}
    
    def list_all_users(self, pattern: str = "*") -> Dict[str, Any]:
        """Listar todos los usuarios (con patrón opcional)"""
        try:
            keys = self.redis_client.keys(f"user:{pattern}")
            users = []
            
            for key in keys:
                user_data = self.redis_client.hgetall(key)
                if user_data:
                    users.append(user_data)
            
            return {
                "success": True,
                "message": f"Se encontraron {len(users)} usuarios",
                "users": users,
                "total": len(users)
            }
            
        except Exception as e:
            logger.error(f"Error listando usuarios: {e}")
            return {
                "success": False,
                "message": f"Error listando usuarios: {str(e)}",
                "users": []
            }