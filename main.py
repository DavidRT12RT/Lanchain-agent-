import json
from fastapi import FastAPI, Query, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

# Agente mejorado
from agents.EnhancedAgentBot import EnhancedAgentBot

agent_bot = EnhancedAgentBot(session_id="api_global")

app = FastAPI(
    title="Agente Inteligente API",
    description="API para interactuar con un agente LangChain mejorado",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especifica los orígenes permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str
    user_contenxt: Optional[Dict[str, Any]] = None


class QuestionResponse(BaseModel):
    success: bool
    question: str
    answer: str
    memory_length: Optional[int] = None
    error: Optional[str] = None


class UserSession(BaseModel):
    session_id: str
    question: Optional[str] = None
    type: str
    timestamp: str


class Message(BaseModel):
    content: str
    type: str  # "human" o "ai"
    timestamp: Optional[str] = None


class UserDetailResponse(BaseModel):
    success: bool
    user_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    preferences: Dict[str, Any] = {}
    created_at: Optional[str] = None
    last_active: Optional[str] = None
    session_count: int = 0
    sessions: List[UserSession] = []
    recent_messages: List[Message] = []
    error: Optional[str] = None


@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return HTTPException(status_code=400, detail=str(exc))


@app.get("/ask")
async def ask(
    question: str = Query(..., description="Tu pregunta para el agente"),
    user_id: Optional[str] = Query(None, description="Id del usuario")
) -> QuestionResponse:
    try:
        # Crear un ID de sesión único por usuario si está disponible
        session_id = f"session_{user_id}" if user_id else "default"

        # Obtener respuesta del agente
        # Si es un usuario recurrente, podríamos crear una instancia específica para él
        response = agent_bot.get_response(question=question, user_id=user_id)

        # Obtener información de memoria para agregar al response
        memory_info = agent_bot.get_memory_info()
        response["memory_length"] = memory_info.get("total_messages", 0)

        return QuestionResponse(**response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Endpoint de salud para monitoreo
    """
    return {"status": "healthy", "timestamp": "2024-01-01T00:00:00"}


@app.get("/user/{user_id}", response_model=UserDetailResponse)
async def get_user_detail(
    user_id: str = Path(..., description="ID del usuario a consultar"),
    sessions_limit: int = Query(
        10, description="Número máximo de sesiones a retornar"),
    messages_limit: int = Query(
        5, description="Número máximo de mensajes recientes a retornar")
) -> UserDetailResponse:
    """
    Obtiene información detallada del usuario, incluyendo sus preferencias, sesiones y mensajes recientes.
    """
    try:
        # Obtener información básica del usuario
        user_result = agent_bot.user_controller.get_user(user_id)

        if not user_result["success"]:
            # Si no existe el usuario, devolver error 404
            raise HTTPException(
                status_code=404, detail=f"Usuario {user_id} no encontrado")

        user_data = user_result["user"]

        # Obtener sesiones del usuario
        sessions_result = agent_bot.user_controller.get_user_sessions(
            user_id, limit=sessions_limit)
        sessions = sessions_result.get("sessions", [])

        # Convertir sesiones al formato UserSession
        formatted_sessions = []
        for session in sessions:
            formatted_sessions.append(UserSession(
                session_id=session.get("session_id", ""),
                question=session.get("question"),
                type=session.get("type", "chat"),
                timestamp=session.get("timestamp", "")
            ))

        # Intentar obtener mensajes recientes si existe una sesión para el usuario
        recent_messages = []
        try:
            # Crear un ID de sesión basado en el ID del usuario
            session_id = f"session_{user_id}"

            # Intentar obtener mensajes de memoria para este usuario
            # Primero verificamos si se ha creado una instancia específica para el usuario
            # Si no existe, usamos la instancia global
            try:
                # Intentamos usar la instancia global con la sesión del usuario
                session_specific_bot = EnhancedAgentBot(session_id=session_id)
                messages_result = session_specific_bot.get_recent_messages(
                    count=messages_limit)
                if messages_result["success"] and messages_result["messages"]:
                    recent_messages_data = messages_result["messages"]
                else:
                    # Intentamos recuperar de la sesión global
                    messages_result = agent_bot.get_recent_messages(
                        count=messages_limit)
                    recent_messages_data = messages_result.get(
                        "messages", []) if messages_result["success"] else []
            except Exception:
                # Si falla, intentamos directamente con la instancia global
                messages_result = agent_bot.get_recent_messages(
                    count=messages_limit)
                recent_messages_data = messages_result.get(
                    "messages", []) if messages_result["success"] else []

            # Formatear los mensajes recuperados
            for msg in recent_messages_data:
                msg_type = msg.get("type", "")
                if msg_type in ["human", "ai"]:
                    recent_messages.append(Message(
                        content=msg.get("content", ""),
                        type=msg_type,
                        timestamp=msg.get("timestamp", "")
                    ))
        except Exception as e:
            # No bloqueamos la respuesta si hay errores al obtener mensajes
            print(f"Error al recuperar mensajes: {e}")
            # Podemos añadir un mensaje informativo
            recent_messages.append(Message(
                content=f"Error al recuperar mensajes: {str(e)}",
                type="system"
            ))

        # Verificar si las preferencias son un string JSON y parsearlo, o usar un diccionario vacío
        try:
            preferences = json.loads(user_data.get("preferences", "{}")) if isinstance(
                user_data.get("preferences"), str) else user_data.get("preferences", {})
        except json.JSONDecodeError:
            preferences = {}

        # Construir respuesta
        response = UserDetailResponse(
            success=True,
            user_id=user_id,
            name=user_data.get("name"),
            email=user_data.get("email"),
            preferences=preferences,
            created_at=user_data.get("created_at"),
            last_active=user_data.get("last_active"),
            session_count=int(user_data.get("session_count", 0)),
            sessions=formatted_sessions,
            recent_messages=recent_messages
        )

        return response

    except HTTPException as e:
        # Re-lanzar excepciones HTTP
        raise
    except Exception as e:
        # Cualquier otro error es un 500
        return UserDetailResponse(
            success=False,
            user_id=user_id,
            error=f"Error al procesar la solicitud: {str(e)}"
        )

if __name__ == "__main__":
    # Verificar la conexión a Redis
    import uvicorn

    print("Verificando conexión a Redis...")
    try:
        memory_info = agent_bot.get_memory_info()
        print("Redis conectado correctamente:", memory_info)

        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    except Exception as e:
        print(f"Error conectando a Redis: {e}")
