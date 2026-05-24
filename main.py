from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import paypalrestsdk
import os
from dotenv import load_dotenv
import qrcode
from io import BytesIO
import base64
from database import SessionLocal, init_db, User, Transaction, PromptLog
from datetime import datetime
import json

# Load environment variables
load_dotenv()

# Initialize FastAPI
app = FastAPI(title="GORILLA AI System")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# PayPal Configuration
paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id": os.getenv("PAYPAL_CLIENT_ID"),
    "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
})

# Initialize database
init_db()

# ============================================================================
# MATRIZ DE ESPECIALIZACIÓN - MODIFICADORES DE PROMPTS POR PLATAFORMA Y MODELO
# ============================================================================

PROMPT_MODIFIERS = {
    "platforms": {
        "youtube": """Escribe en formato de guión cinematográfico. 
- Los primeros 3 segundos deben destruir la objeción principal del espectador
- Estructura: Hook (3s) → Desarrollo → Cliffhanger → Call-to-action
- Incluye [VISUAL], [AUDIO], [TEXTO] en cada sección
- Duración recomendada: 8-12 minutos
- Usa patrones de storytelling viral""",
        
        "tiktok": """Formato de ritmo rápido y ultra-viral.
- Indicaciones exactas para cambios de plano cada 1.5 segundos
- Hook emocional en el PRIMER SEGUNDO (imprescindible)
- Trending sounds y hashtags estratégicos
- Duración: 15-60 segundos máximo
- Usa transiciones dinámicas y emojis para retención visual""",
        
        "x_twitter": """Divide la respuesta estrictamente en un HILO DE X (Twitter).
- Cada fragmento MÁXIMO 280 caracteres
- Usa ganchos de apertura que generen replies
- Estructura: Problema → Dato sorprendente → Solución → Reflexión
- Incluye números, emojis estratégicos y preguntas retóricas
- Numeración clara: 1/N, 2/N, etc.""",
        
        "linkedin": """Tono profesional con storytelling corporativo.
- Usa saltos de línea amplios para lectura móvil
- Abre con una pregunta o estadística impactante
- Desarrolla con experiencia/dato verificable
- Cierra con 3 aprendizajes clave numerados
- Incluye CTA profesional sin ser agresivo""",
        
        "instagram": """Contenido visual y aspiracional.
- Estructura: Portada intrigante → Desarrollo narrativo → Inspiración → Acción
- Usa emojis decorativos y separadores visuales
- Mentalmente optimizado para scroll vertical
- Longitud: 800-1200 caracteres
- Incluye call-to-action en el primer párrafo""",
        
        "whatsapp": """Mensajería conversacional y directa.
- Tono amigable y cercano
- Párrafos cortos (máx 2-3 líneas)
- Usa emojis para separación visual
- Estructura: Saludo → Propuesta → Urgencia → Acción
- Incluye número de teléfono o link de CTA al final"""
    },
    
    "models": {
        "grok": """Personalidad audaz, ingeniosa y provocadora.
- Adopta un toque de humor negro e ironía
- No temas ser controversial o cuestionador
- Desafía suposiciones convencionales
- Usa datos duros combinados con sarcasmo
- Sé directo y sin filtros, pero inteligente""",
        
        "claude": """Redacción sofisticada y humanizada.
- Evita clichés de IA y jerga técnica innecesaria
- Estructura con lógica impecable y párrafos fluyentes
- Tono sumamente humano, como conversación entre expertos
- Incluye matices, excepciones y contextos complejos
- Escribe como un ensayista experimentado""",
        
        "gemini": """Enfoque estructurado y orientado a datos.
- Estructuración clara con tablas comparativas
- Incluye conceptos en formato de matriz o comparativa
- Optimiza para flujos lógicos de trabajo inmediatos
- Proporciona pasos accionables numerados
- Alineación visual con viñetas y espacios""",
        
        "openai": """Redacción clara, educativa y progresiva.
- Comienza con lo simple y avanza a lo complejo
- Estructura en secciones claramente delimitadas
- Incluye ejemplos prácticos en cada punto
- Tono profesional pero accesible
- Termina con resumen ejecutivo""",
        
        "llama": """Eficiencia y pragmatismo sin adornos.
- Comunicación directa y al punto
- Estructura ágil sin explicaciones excesivas
- Enfoque en lo que funciona, no en teoría
- Incluye métricas o KPIs cuando sea relevante
- Máxima claridad con mínimas palabras"""
    }
}

# ============================================================================
# MODELOS PYDANTIC
# ============================================================================

class PaymentRequest(BaseModel):
    user_id: str
    prompts_count: int
    return_url: str

class PaymentResponse(BaseModel):
    success: bool
    message: str
    approval_url: Optional[str] = None
    payment_id: Optional[str] = None

class PromptRequest(BaseModel):
    user_id: str
    prompt_text: str
    platform: str = "default"  # youtube, tiktok, x_twitter, linkedin, instagram, whatsapp
    model: str = "claude"      # grok, claude, gemini, openai, llama
    niche: Optional[str] = None
    product: Optional[str] = None
    pain_point: Optional[str] = None

class PromptResponse(BaseModel):
    success: bool
    message: str
    remaining_prompts: int
    optimized_prompt: Optional[str] = None

class PromptGenerationResponse(BaseModel):
    success: bool
    message: str
    original_prompt: str
    optimized_prompt: str
    platform: str
    model: str
    remaining_prompts: int

# ============================================================================
# DEPENDENCIAS
# ============================================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def generate_qr(data: str) -> str:
    """Genera código QR y retorna como base64"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

def apply_prompt_modifiers(base_prompt: str, platform: str, model: str, niche: str = "", product: str = "", pain_point: str = "") -> str:
    """
    Aplica modificadores de especialización según plataforma y modelo de IA
    Inyecta limpiamente las variables del usuario (nicho, producto, dolor)
    """
    
    # Obtener modificadores base
    platform_modifier = PROMPT_MODIFIERS["platforms"].get(platform.lower(), "")
    model_modifier = PROMPT_MODIFIERS["models"].get(model.lower(), "")
    
    # Construir contexto de usuario si existe
    user_context = ""
    if niche or product or pain_point:
        user_context = "\n\n## CONTEXTO DEL USUARIO:\n"
        if niche:
            user_context += f"- Nicho: {niche}\n"
        if product:
            user_context += f"- Producto/Servicio: {product}\n"
        if pain_point:
            user_context += f"- Dolor Principal: {pain_point}\n"
    
    # Estructura final del prompt optimizado
    optimized_prompt = f"""# PROMPT ESPECIALIZADO - GORILLA AI SYSTEM

## INSTRUCCIÓN BASE:
{base_prompt}

{user_context}

## ESPECIALIZACIÓN POR PLATAFORMA ({platform.upper()}):
{platform_modifier}

## ESTILO DEL MODELO ({model.upper()}):
{model_modifier}

## INDICACIONES FINALES:
- Mantén coherencia con todas las instrucciones anteriores
- Optimiza para máximo engagement y conversión
- Asegura que el contenido sea único, fresco y sin clichés
- Adapta el tono y estructura exactamente como se indicó
- Incluye un hook inicial irresistible

---
GENERA AHORA EL CONTENIDO OPTIMIZADO:"""
    
    return optimized_prompt

# ============================================================================
# RUTAS
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def landing_page():
    """Página de aterrizaje con QR y opciones de pago"""
    qr_code = generate_qr("https://mglrte1986.github.io/gorilla-ai-system/app")
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>GORILLA AI - Sistema Premium</title>
        <script src="https://www.paypal.com/sdk/js?client-id={os.getenv('PAYPAL_CLIENT_ID', 'test')}"></script>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }}
            .container {{
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                padding: 50px;
                max-width: 600px;
                width: 100%;
            }}
            h1 {{
                color: #333;
                margin-bottom: 10px;
                font-size: 36px;
                text-align: center;
            }}
            .subtitle {{
                color: #764ba2;
                text-align: center;
                margin-bottom: 30px;
                font-size: 16px;
            }}
            .qr-section {{
                display: flex;
                justify-content: center;
                margin: 30px 0;
            }}
            .qr-section img {{
                border: 4px solid #667eea;
                border-radius: 15px;
                padding: 15px;
                width: 280px;
                height: 280px;
            }}
            .pricing-box {{
                background: #f8f9fa;
                border-left: 4px solid #667eea;
                padding: 20px;
                margin: 30px 0;
                border-radius: 10px;
            }}
            .pricing-box h3 {{
                color: #333;
                margin-bottom: 10px;
            }}
            .price {{
                font-size: 28px;
                color: #667eea;
                font-weight: bold;
                margin: 10px 0;
            }}
            .features {{
                list-style: none;
                margin: 15px 0;
            }}
            .features li {{
                padding: 8px 0;
                color: #666;
                border-bottom: 1px solid #eee;
            }}
            .features li:before {{
                content: "✓ ";
                color: #667eea;
                font-weight: bold;
                margin-right: 8px;
            }}
            .payment-options {{
                margin-top: 30px;
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 15px;
            }}
            .payment-btn {{
                padding: 12px 20px;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                cursor: pointer;
                font-weight: bold;
                transition: all 0.3s ease;
            }}
            .btn-paypal {{
                background: #0070ba;
                color: white;
            }}
            .btn-paypal:hover {{
                background: #004c97;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0,112,186,0.3);
            }}
            .btn-enter {{
                background: #667eea;
                color: white;
            }}
            .btn-enter:hover {{
                background: #5568d3;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(102,126,234,0.3);
            }}
            .user-info {{
                background: #e8f4f8;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                text-align: center;
            }}
            .user-info input {{
                width: 100%;
                padding: 10px;
                margin: 10px 0;
                border: 1px solid #667eea;
                border-radius: 5px;
                font-size: 14px;
            }}
            select {{
                width: 100%;
                padding: 10px;
                margin: 10px 0;
                border: 1px solid #667eea;
                border-radius: 5px;
                font-size: 14px;
            }}
            label {{
                display: block;
                margin-top: 15px;
                font-weight: bold;
                color: #333;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🦍 GORILLA AI</h1>
            <p class="subtitle">Sistema Premium de IA con Prompts Especializados</p>
            
            <div class="qr-section">
                <img src="{qr_code}" alt="QR Code GORILLA AI">
            </div>
            
            <div class="pricing-box">
                <h3>Plan Premium - Acceso Completo</h3>
                <div class="price">${{os.getenv('PRICE_PER_PROMPT', '0.50')}} / Prompt</div>
                <ul class="features">
                    <li>Prompts especializados por plataforma</li>
                    <li>6 modelos de IA disponibles</li>
                    <li>Inyección de contexto (nicho, producto, dolor)</li>
                    <li>Optimización por audiencia</li>
                    <li>Soporte prioritario 24/7</li>
                </ul>
            </div>
            
            <div class="user-info">
                <label for="userId">Tu Email:</label>
                <input type="email" id="userId" placeholder="tu@email.com">
                
                <label for="promptsCount">Cantidad de Prompts:</label>
                <select id="promptsCount">
                    <option value="10">10 Prompts - $5.00</option>
                    <option value="25">25 Prompts - $12.50</option>
                    <option value="50">50 Prompts - $25.00</option>
                    <option value="100">100 Prompts - $50.00</option>
                </select>
            </div>
            
            <div class="payment-options">
                <button class="payment-btn btn-paypal" onclick="createPayment()">
                    💳 Pagar con PayPal
                </button>
                <button class="payment-btn btn-enter" onclick="freeAccess()">
                    🚀 Acceso Gratis (5 prompts)
                </button>
            </div>
        </div>
        
        <script>
            function createPayment() {{
                const userEmail = document.getElementById('userId').value;
                const promptsCount = document.getElementById('promptsCount').value;
                
                if (!userEmail) {{
                    alert('Por favor ingresa tu email');
                    return;
                }}
                
                fetch('/api/create-payment', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        user_id: userEmail,
                        prompts_count: parseInt(promptsCount),
                        return_url: window.location.origin + '/success'
                    }})
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success && data.approval_url) {{
                        window.location.href = data.approval_url;
                    }} else {{
                        alert('Error: ' + data.message);
                    }}
                }})
                .catch(error => {{
                    console.error('Error:', error);
                    alert('Error al procesar el pago');
                }});
            }}
            
            function freeAccess() {{
                const userEmail = document.getElementById('userId').value;
                
                if (!userEmail) {{
                    alert('Por favor ingresa tu email');
                    return;
                }}
                
                fetch('/api/grant-free-access', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{user_id: userEmail}})
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        sessionStorage.setItem('user_token', data.token);
                        window.location.href = '/app';
                    }} else {{
                        alert('Error: ' + data.message);
                    }}
                }})
                .catch(error => {{
                    console.error('Error:', error);
                    alert('Error al acceder');
                }});
            }}
        </script>
    </body>
    </html>
    """
    return html_content

@app.post(\"/api/create-payment\")\nasync def create_payment(payment: PaymentRequest, db = Depends(get_db)):\n    \"\"\"Crear pago en PayPal para prompts\"\"\"\n    try:\n        price_per_prompt = float(os.getenv(\"PRICE_PER_PROMPT\", \"0.50\"))\n        total_amount = price_per_prompt * payment.prompts_count\n        \n        payment_obj = paypalrestsdk.Payment({\n            \"intent\": \"sale\",\n            \"payer\": {\"payment_method\": \"paypal\"},\n            \"redirect_urls\": {\n                \"return_url\": f\"{payment.return_url}?payment_id={{paymentId}}\",\n                \"cancel_url\": \"http://localhost:8000/\"\n            },\n            \"transactions\": [{\n                \"item_list\": {\n                    \"items\": [{\n                        \"name\": f\"GORILLA AI - {payment.prompts_count} Prompts\",\n                        \"sku\": f\"PROMPT-{payment.prompts_count}\",\n                        \"price\": str(price_per_prompt),\n                        \"currency\": os.getenv(\"CURRENCY\", \"USD\"),\n                        \"quantity\": payment.prompts_count\n                    }]\n                },\n                \"amount\": {\n                    \"total\": f\"{total_amount:.2f}\",\n                    \"currency\": os.getenv(\"CURRENCY\", \"USD\"),\n                    \"details\": {\"subtotal\": f\"{total_amount:.2f}\"}\n                },\n                \"description\": f\"Compra de {payment.prompts_count} prompts para GORILLA AI\"\n            }]\n        })\n        \n        if payment_obj.create():\n            transaction = Transaction(\n                user_id=payment.user_id,\n                payment_id=payment_obj.id,\n                amount=total_amount,\n                prompts_count=payment.prompts_count,\n                status=\"pending\"\n            )\n            db.add(transaction)\n            db.commit()\n            \n            return PaymentResponse(\n                success=True,\n                message=\"Payment created successfully\",\n                approval_url=payment_obj.links[1]['href'],\n                payment_id=payment_obj.id\n            )\n        else:\n            return PaymentResponse(\n                success=False,\n                message=f\"Payment creation failed: {payment_obj.error['message']}\"\n            )\n    except Exception as e:\n        return PaymentResponse(\n            success=False,\n            message=f\"Error: {str(e)}\"\n        )\n\n@app.post(\"/api/execute-payment\")\nasync def execute_payment(payment_id: str, payer_id: str, db = Depends(get_db)):\n    \"\"\"Ejecutar pago en PayPal\"\"\"\n    try:\n        payment = paypalrestsdk.Payment.find(payment_id)\n        \n        if payment.execute({\"payer_id\": payer_id}):\n            transaction = db.query(Transaction).filter(\n                Transaction.payment_id == payment_id\n            ).first()\n            \n            if transaction:\n                transaction.status = \"completed\"\n                transaction.completed_at = datetime.now()\n                db.commit()\n            \n            user_token = f\"{transaction.user_id}:{payment_id}\"\n            \n            return {\n                \"success\": True,\n                \"message\": \"Payment executed successfully\",\n                \"token\": user_token,\n                \"prompts\": transaction.prompts_count\n            }\n        else:\n            return {\n                \"success\": False,\n                \"message\": f\"Payment execution failed: {payment.error['message']}\"\n            }\n    except Exception as e:\n        return {\"success\": False, \"message\": f\"Error: {str(e)}\"}\n\n@app.post(\"/api/grant-free-access\")\nasync def grant_free_access(user_id: str, db = Depends(get_db)):\n    \"\"\"Otorgar acceso gratuito con 5 prompts\"\"\"\n    try:\n        user = db.query(User).filter(User.email == user_id).first()\n        \n        if not user:\n            user = User(\n                email=user_id,\n                prompts_remaining=5,\n                is_free_user=True\n            )\n            db.add(user)\n            db.commit()\n        \n        user_token = f\"{user_id}:free\"\n        \n        return {\n            \"success\": True,\n            \"message\": \"Free access granted\",\n            \"token\": user_token,\n            \"prompts\": 5\n        }\n    except Exception as e:\n        return {\"success\": False, \"message\": f\"Error: {str(e)}\"}\n\n@app.post(\"/api/generate-specialized-prompt\")\nasync def generate_specialized_prompt(prompt: PromptRequest, db = Depends(get_db)):\n    \"\"\"Generar prompt especializado según plataforma y modelo\"\"\"\n    try:\n        user = db.query(User).filter(User.email == prompt.user_id).first()\n        \n        if not user:\n            return PromptGenerationResponse(\n                success=False,\n                message=\"User not found\",\n                original_prompt=\"\",\n                optimized_prompt=\"\",\n                platform=prompt.platform,\n                model=prompt.model,\n                remaining_prompts=0\n            )\n        \n        if user.prompts_remaining <= 0:\n            return PromptGenerationResponse(\n                success=False,\n                message=\"No prompts remaining. Please purchase more prompts.\",\n                original_prompt=\"\",\n                optimized_prompt=\"\",\n                platform=prompt.platform,\n                model=prompt.model,\n                remaining_prompts=0\n            )\n        \n        # Aplicar modificadores de especialización\n        optimized_prompt = apply_prompt_modifiers(\n            base_prompt=prompt.prompt_text,\n            platform=prompt.platform,\n            model=prompt.model,\n            niche=prompt.niche or \"\",\n            product=prompt.product or \"\",\n            pain_point=prompt.pain_point or \"\"\n        )\n        \n        # Deducir un prompt\n        user.prompts_remaining -= 1\n        \n        # Registrar en log\n        log = PromptLog(\n            user_id=prompt.user_id,\n            prompt_text=prompt.prompt_text,\n            response=optimized_prompt\n        )\n        db.add(log)\n        db.commit()\n        \n        return PromptGenerationResponse(\n            success=True,\n            message=\"Prompt generated successfully\",\n            original_prompt=prompt.prompt_text,\n            optimized_prompt=optimized_prompt,\n            platform=prompt.platform,\n            model=prompt.model,\n            remaining_prompts=user.prompts_remaining\n        )\n    except Exception as e:\n        return PromptGenerationResponse(\n            success=False,\n            message=f\"Error: {str(e)}\",\n            original_prompt=\"\",\n            optimized_prompt=\"\",\n            platform=prompt.platform,\n            model=prompt.model,\n            remaining_prompts=0\n        )\n\n@app.get(\"/api/user-info\")\nasync def get_user_info(user_id: str, db = Depends(get_db)):\n    \"\"\"Obtener información del usuario y prompts restantes\"\"\"\n    try:\n        user = db.query(User).filter(User.email == user_id).first()\n        \n        if not user:\n            return {\"success\": False, \"message\": \"User not found\"}\n        \n        return {\n            \"success\": True,\n            \"user_id\": user.email,\n            \"prompts_remaining\": user.prompts_remaining,\n            \"is_free_user\": user.is_free_user,\n            \"created_at\": user.created_at\n        }\n    except Exception as e:\n        return {\"success\": False, \"message\": f\"Error: {str(e)}\"}\n\n@app.get(\"/success\", response_class=HTMLResponse)\nasync def payment_success():\n    \"\"\"Página de éxito de pago\"\"\"\n    return \"\"\"\n    <!DOCTYPE html>\n    <html>\n    <head>\n        <title>Pago Completado</title>\n        <style>\n            body { font-family: Arial, sans-serif; background: #667eea; min-height: 100vh; display: flex; align-items: center; justify-content: center; }\n            .container { background: white; padding: 50px; border-radius: 10px; text-align: center; }\n            h1 { color: #28a745; }\n            p { color: #666; margin: 20px 0; }\n            a { background: #667eea; color: white; padding: 10px 30px; text-decoration: none; border-radius: 5px; }\n        </style>\n    </head>\n    <body>\n        <div class=\"container\">\n            <h1>✅ ¡Pago Completado!</h1>\n            <p>Tu compra ha sido procesada correctamente.</p>\n            <p>Estamos redirigiendo a la aplicación...</p>\n            <a href=\"/app\">Ir a GORILLA AI</a>\n        </div>\n        <script>\n            setTimeout(() => window.location.href = '/app', 3000);\n        </script>\n    </body>\n    </html>\n    \"\"\"\n\nif __name__ == \"__main__\":\n    import uvicorn\n    uvicorn.run(\n        app,\n        host=os.getenv(\"API_HOST\", \"127.0.0.1\"),\n        port=int(os.getenv(\"API_PORT\", 8000))\n    )\n