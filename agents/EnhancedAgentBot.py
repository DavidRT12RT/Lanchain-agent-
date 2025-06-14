import os
import logging
import redis
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain.utilities import WikipediaAPIWrapper
from langchain.agents import Tool
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import AgentExecutor, create_openai_functions_agent

from typing import Dict, Any

from datetime import datetime

from controllers.user_controller import UserController
from memory.redis_memory import RedisMemory
from prompts.system_prompt import system_prompt

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Configuración
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)


class EnhancedAgentBot:
    """
      Bot de agente mejorado con memoria Redis y gestion de usuarios
    """

    def __init__(self, session_id: str = "default"):

        self.session_id = session_id

        # Inicializar componentes
        self.__init_llm()
        self.__init_tools()
        self.__init_memory()
        self._init_user_controller()
        self.__init_agent()

        logger.info(f"AgentBot inicilizado para session: {session_id}")

    def __init_llm(self):
        """
          Inicializar el modelo de lenguaje
        """
        self.llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo")

    def __init_tools(self):
        self.wiki = WikipediaAPIWrapper()  # type:ignore

        def search_news_tools(topic: str) -> str:
            """Tool personalizada para obtener las noticias sobre un tema"""
            try:
                return f"Ultimas noticias sobre {topic}: Se han encontrado resultados relevantes"
            except Exception as e:
                return f"Error al buscar noticias :{str(e)}"

        def get_current_time_tool() -> str:
            """Tool personalizada para obtener la hora"""
            current_time = datetime.now()
            return f"La hora actual es: {current_time}"

        def get_weather_tool(location: str = "Ciudad de mexico") -> str:
            """Tool personalizada para obtener el clima"""
            return f"El clima en {location} es soleado con 22C"

        self.tools = [
            Tool(
                name="Wikipedia",
                func=self.wiki.run,
                description="Útil para responder preguntas sobre conocimiento general"
            ),
            Tool(
                name="News",
                func=search_news_tools,
                description="Útil para buscar noticias recientes sobre cualquier tema"
            ),
            Tool(
                name="Time",
                func=get_current_time_tool,
                description="Útil para obtener la hora actual"
            ),
            Tool(
                name="Weather",
                func=get_weather_tool,
                description="Útil para obtener información del clima de una ubicación"
            )
        ]

    def __init_memory(self):
        """Inicializar memoria redis"""
        try:
            # Si REDIS_PASSWORD está vacío, usar "123" como está definido en RedisMemory
            password = REDIS_PASSWORD if REDIS_PASSWORD else ""
            
            # Crear el cliente Redis primero
            redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=0,  # Explícitamente indicamos la base de datos
                password=password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            
            # Verificar que podemos conectarnos
            if not redis_client.ping():
                raise ConnectionError("No se pudo establecer conexión con Redis")
                
            # Crear RedisMemory con el cliente ya inicializado
            self.memory = RedisMemory(
                redis_client=redis_client,
                session_id=self.session_id,
                ttl=86400,  # 24 horas
                max_messages=100,
                memory_key_name="chat_history",  # Debe coincidir con el nombre en el prompt
                return_messages=True  # Importante: retorna objetos BaseMessage, no strings
            )
            
            logger.info("Memoria Redis inicializada correctamente!")
                
        except Exception as e:
            logger.error(f"Error inicializando memoria Redis: {e}")
            raise RuntimeError(f"Error inicializando memoria Redis: {e}")

    def _init_user_controller(self):
        """Inicializar controlador de usuarios"""
        try:
            self.user_controller = UserController(
                redis_host=REDIS_HOST,
                redis_port=REDIS_PORT,
                redis_password=REDIS_PASSWORD
            )
            logger.info("Controlador de usuarios inicializado correctamente")
        except Exception as e:
            logger.error(f"Error inicializando controlador de usuarios: {e}")
            raise

    def __init_agent(self):
        """Inicializar el agente"""
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # Crear agente
        agent = create_openai_functions_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self.prompt_template
        )

        # Crear ejecutador del agente
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=3,
            return_intermediate_steps=False
        )

    def get_response(self, question: str, user_id: str | None = None) -> Dict[str, Any]:
        """
        Obtener respuesta del agente con contexto de usuario opcional
        """

        try:
            # Obtener contexto del usuario si se proporciona user_id
            user_context = None
            if user_id:
                context_result = self.user_controller.get_user_context(user_id)
                user_context = context_result.get("user_context")

                # Registrar la sesión
                self.user_controller.add_session(user_id, {
                    "session_id": self.session_id,
                    "question": question,
                    "type": "chat"
                })

            # Construir pregunta con contexto
            if user_context:
                enhanced_question = f"""
          Contexto del usuario:
          - Nombre: {user_context.get('name', 'Usuario')}
          - ID: {user_context['user_id']}
          - Sesiones totales: {user_context.get('session_count', 0)}
          - Preferencias: {user_context.get('preferences', {})}

          Pregunta del usuario: {question}
        """
            else:
                enhanced_question = question

            # Obtener respuesta del agente
            response = self.agent_executor.invoke({"input": enhanced_question})

            return {
                "success": True,
                "question": question,
                "answer": response["output"],
                "session_id": self.session_id,
                "user_context": user_context is not None,
            }

        except Exception as e:
            logger.error(f"Error obteniendo respuesta: {e}")
            return {
                "success": False,
                "question": question,
                "error": str(e),
                "answer": "Lo siento, ocurrió un error al procesar tu pregunta."
            }

    def get_memory_info(self) -> Dict[str, Any]:
        """Obtener información de la memoria actual"""
        return self.memory.get_session_info()

    def clear_memory(self) -> Dict[str, Any]:
        """Limpiar memoria de la sesión actual"""
        try:
            self.memory.clear()
            return {
                "success": True,
                "message": f"Memoria limpiada para sesión: {self.session_id}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error limpiando memoria: {str(e)}"
            }

    def search_memory(self, query: str) -> Dict[str, Any]:
        """Buscar en la memoria de la sesión"""
        try:
            results = self.memory.search_messages(query)
            return {
                "success": True,
                "query": query,
                "results": results,
                "total_found": len(results)
            }
        except Exception as e:
            return {
                "success": False,
                "query": query,
                "error": str(e),
                "results": []
            }

    def get_recent_messages(self, count: int = 5) -> Dict[str, Any]:
        """Obtener mensajes recientes de la memoria"""
        try:
            messages = self.memory.get_recent_messages(count)
            return {
                "success": True,
                "messages": messages,
                "count": len(messages)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "messages": []
            }
