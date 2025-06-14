import json
import redis
from typing import List, Dict, Any, Optional
from datetime import datetime
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain.memory.chat_memory import BaseChatMemory
from pydantic import Field
import logging

logger = logging.getLogger(__name__)


class RedisMemory(BaseChatMemory):
    """
    Memoria personalizada que usa redis para almacenamiento persistente
    Compatible con AgentExecutor (métodos síncronos)
    """

    redis_client: redis.Redis = Field()
    sessions_id: str = Field(default="default")
    ttl: int = Field(default=86400)  # 24 Horas por defecto
    max_messages: int = Field(default=50)  # Máximo mensajes por session
    # Key name for memory variables
    memory_key_name: str = Field(default="history")
    input_key: Optional[str] = Field(
        default=None
    )  # Input key for extracting input from inputs dict
    output_key: Optional[str] = Field(
        default=None
    )  # Output key for extracting output from outputs dict
    # Whether to return messages or string
    return_messages: bool = Field(default=False)

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        redis_password: Optional[str] = "",
        session_id: str = "default",
        ttl: int = 86400,
        max_messages: int = 50,
        memory_key_name: str = "history",
        input_key: Optional[str] = None,
        output_key: Optional[str] = None,
        return_messages: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)

        # Configurar cliente de Redis síncrono
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )

        self.sessions_id = session_id
        self.ttl = ttl
        self.max_messages = max_messages
        self.memory_key_name = memory_key_name
        self.input_key = input_key
        self.output_key = output_key
        self.return_messages = return_messages

    @property
    def memory_variables(self) -> List[str]:
        """Return memory variables - required by BaseMemory"""
        return [self.memory_key_name]

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Load memory variables - required by BaseMemory"""
        messages = self.messages
        if self.return_messages:
            return {self.memory_key_name: messages}
        else:
            # Convert messages to string format
            buffer = self.get_buffer_string(messages)
            return {self.memory_key_name: buffer}

    def get_buffer_string(
        self,
        messages: List[BaseMessage],
        human_prefix: str = "Human",
        ai_prefix: str = "AI",
    ) -> str:
        """Convert messages to string format"""
        string_messages = []
        for m in messages:
            if isinstance(m, HumanMessage):
                role = human_prefix
            elif isinstance(m, AIMessage):
                role = ai_prefix
            else:
                role = m.__class__.__name__
            string_messages.append(f"{role}: {m.content}")
        return "\n".join(string_messages)

    @property
    def memory_key(self) -> str:
        return f"chat_history:{self.sessions_id}"

    @property
    def chat_memory(self):  # type:ignore
        """Propiedad requerida por BaseChatMemory"""
        return self

    @property
    def messages(self) -> List[BaseMessage]:
        """
        Get messages from redis (SÍNCRONO - requerido por AgentExecutor)
        """
        try:
            messages_data = self.redis_client.lrange(self.memory_key, 0, -1)
            messages = []

            for msg_json in messages_data:
                msg_dict = json.loads(msg_json)
                if msg_dict["type"] == "human":
                    messages.append(HumanMessage(content=msg_dict["content"]))
                elif msg_dict["type"] == "ai":
                    messages.append(AIMessage(content=msg_dict["content"]))

            return messages

        except Exception as e:
            logger.error(f"Error obteniendo mensajes: {e}")
            return []

    def add_message(self, message: BaseMessage) -> None:
        """
        Agregar mensaje a Redis (SÍNCRONO - requerido por AgentExecutor)
        """
        try:
            msg_dict = {
                "type": "human" if isinstance(message, HumanMessage) else "ai",
                "content": message.content,
                "timestamp": datetime.now().isoformat(),
            }

            self.redis_client.rpush(self.memory_key, json.dumps(msg_dict))

            # Mantener solo los últimos max messages
            self.redis_client.ltrim(self.memory_key, -self.max_messages, -1)

            # Establecer TTL
            self.redis_client.expire(self.memory_key, self.ttl)

        except Exception as e:
            logger.error(f"Error agregando mensajes: {e}")

    def clear(self) -> None:
        """Limpiar memoria - requerido por BaseChatMemory"""
        try:
            self.redis_client.delete(self.memory_key)
        except Exception as e:
            logger.error(f"Error limpiando memoria: {e}")

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """Save context to memory - called by LangChain"""
        # Extract input based on input_key or use first available key
        if self.input_key is None:
            input_str = list(inputs.values())[0] if inputs else ""
        else:
            input_str = inputs.get(self.input_key, "")

        # Extract output based on output_key or use first available key
        if self.output_key is None:
            output_str = list(outputs.values())[0] if outputs else ""
        else:
            output_str = outputs.get(self.output_key, "")

        self.add_message(HumanMessage(content=input_str))
        self.add_message(AIMessage(content=output_str))

    async def aload_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Async version of load_memory_variables - required by BaseChatMemory"""
        # For Redis synchronous operations, we can reuse the sync method
        return self.load_memory_variables(inputs)

    async def asave_context(
        self, inputs: Dict[str, Any], outputs: Dict[str, str]
    ) -> None:
        """Async version of save_context - required by BaseChatMemory"""
        # For Redis synchronous operations, we can reuse the sync method
        self.save_context(inputs, outputs)

    def get_session_info(self) -> Dict[str, Any]:
        """
        Obtener información de la sesión actual
        """
        try:
            total_messages = self.redis_client.llen(self.memory_key)
            ttl_remaining = self.redis_client.ttl(self.memory_key)

            return {
                "session_id": self.sessions_id,
                "total_messages": total_messages,
                "ttl_remaining_seconds": ttl_remaining,
                "max_messages": self.max_messages,
                "memory_key": self.memory_key,
            }
        except Exception as e:
            logger.error(f"Error obteniendo info de sesión: {e}")
            return {}

    def get_recent_messages(self, count: int = 5) -> List[Dict[str, Any]]:
        """Obtener los últimos N mensajes con metadata"""
        try:
            recent_data = self.redis_client.lrange(self.memory_key, -count, -1)
            messages = []

            for msg_json in recent_data:
                msg_dict = json.loads(msg_json)
                messages.append(msg_dict)

            return messages
        except Exception as e:
            logger.error(f"Error obteniendo mensajes recientes: {e}")
            return []

    def check_connection(self) -> bool:
        """
        Verificar conexión con Redis
        """
        try:
            self.redis_client.ping()
            logger.info(
                f"Conexión exitosa a Redis para sesión: {self.sessions_id}")
            return True
        except redis.ConnectionError as e:
            logger.error(f"Error conectando a Redis: {e}")
            return False

    def search_messages(self, query: str) -> List[Dict[str, Any]]:
        """Buscar mensajes que contengan una consulta específica"""
        try:
            all_messages = self.redis_client.lrange(self.memory_key, 0, -1)
            matching_messages = []

            for msg_json in all_messages:
                msg_dict = json.loads(msg_json)
                if query.lower() in msg_dict["content"].lower():
                    matching_messages.append(msg_dict)

            return matching_messages
        except Exception as e:
            logger.error(f"Error buscando mensajes: {e}")
            return []

    def get_all_sessions(self) -> List[str]:
        """Obtener todas las sesiones activas"""
        try:
            pattern = "chat_history:*"
            keys = self.redis_client.keys(pattern)
            sessions = [key.replace("chat_history:", "") for key in keys]
            return sessions
        except Exception as e:
            logger.error(f"Error obteniendo sesiones: {e}")
            return []

    def delete_session(self, session_id: str) -> bool:
        """Eliminar una sesión específica"""
        try:
            key = f"chat_history:{session_id}"
            result = self.redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Error eliminando sesión {session_id}: {e}")
            return False
