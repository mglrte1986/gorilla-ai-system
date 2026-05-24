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
- Incluye número de teléfono o link de CTA al final""",
        
        "google_ads": """Estructura de campaña publicitaria de alta conversión para Google/YouTube Ads.
- Diseña 3 variantes de títulos persuasivos que destruyan la objeción principal
- Redacta copys específicos para anuncios de búsqueda y guiones de 15s para YouTube Ads
- Incluye recomendaciones de segmentación de palabras clave y presupuesto optimizado para alto flujo
- Estructura: Headline (30 chars) → Descripción (90 chars) → URL de destino específica
- Usa números, urgencia y diferenciadores claros
- Optimiza para CTR (5-10%) y conversión (5-15%)""",
        
        "google_workspace": """Foco en automatización de procesos y productividad empresarial.
- Estructura la respuesta para ser implementada en el entorno de Google Workspace
- Proporciona el código de Google Apps Script limpio, comentado y listo para copiar/pegar
- Diseña el flujo conectando Google Sheets, Docs y Drive de manera eficiente
- Incluye triggers (onFormSubmit, onEdit, etc.) y funciones reutilizables
- Especifica qué API de Google Workspace necesita estar habilitada
- Proporciona snippet de instalación con paso a paso""",
        
        "youtube_growth": """Optimización total para posicionamiento y SEO en el algoritmo de YouTube.
- Genera 3 variantes de títulos de alto CTR (Click-Through Rate)
- Estructura una descripción dinámica optimizada que retenga al usuario
- Incluye recomendaciones de metadatos, etiquetas estratégicas y ganchos visuales
- Proporciona timestamps para mejorar navegación
- Crea brief de thumbnail con colores, emojis y elementos visuales
- Optimiza keywords naturalmente (primeras 3 palabras = keyword principal)"""
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
    platform: str = "default"
    model: str = "claude"
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
            .platforms-grid {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 10px;
                margin: 20px 0;
                font-size: 12px;
            }}
            .platform-badge {{
                background: #667eea;
                color: white;
                padding: 5px 10px;
                border-radius: 5px;
                text-align: center;
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
                    <li>9 plataformas + 5 modelos de IA</li>
                    <li>Inyección de contexto (nicho, producto, dolor)</li>
                    <li>Código Ready-to-Use (Google Apps Script)</li>
                    <li>Soporte prioritario 24/7</li>
                </ul>
                <div class="platforms-grid">
                    <div class="platform-badge">🎬 YouTube</div>
                    <div class="platform-badge">📱 TikTok</div>
                    <div class="platform-badge">𝕏 Twitter</div>
                    <div class="platform-badge">💼 LinkedIn</div>
                    <div class="platform-badge">📸 Instagram</div>
                    <div class="platform-badge">💬 WhatsApp</div>
                    <div class="platform-badge">💰 Google Ads</div>
                    <div class="platform-badge">⚙️ Workspace</div>
                    <div class="platform-badge">📈 Growth</div>
                </div>
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

@app.post("/api/create-payment")
async def create_payment(payment: PaymentRequest, db = Depends(get_db)):
    """Crear pago en PayPal para prompts"""
    try:
        price_per_prompt = float(os.getenv("PRICE_PER_PROMPT", "0.50"))
        total_amount = price_per_prompt * payment.prompts_count
        
        payment_obj = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {"payment_method": "paypal"},
            "redirect_urls": {
                "return_url": f"{payment.return_url}?payment_id={{paymentId}}",
                "cancel_url": "http://localhost:8000/"
            },
            "transactions": [{
                "item_list": {
                    "items": [{
                        "name": f"GORILLA AI - {payment.prompts_count} Prompts",
                        "sku": f"PROMPT-{payment.prompts_count}",
                        "price": str(price_per_prompt),
                        "currency": os.getenv("CURRENCY", "USD"),
                        "quantity": payment.prompts_count
                    }]
                },
                "amount": {
                    "total": f"{total_amount:.2f}",
                    "currency": os.getenv("CURRENCY", "USD"),
                    "details": {"subtotal": f"{total_amount:.2f}"}
                },
                "description": f"Compra de {payment.prompts_count} prompts para GORILLA AI"
            }]
        })
        
        if payment_obj.create():
            transaction = Transaction(
                user_id=payment.user_id,
                payment_id=payment_obj.id,
                amount=total_amount,
                prompts_count=payment.prompts_count,
                status="pending"
            )
            db.add(transaction)
            db.commit()
            
            return PaymentResponse(
                success=True,
                message="Payment created successfully",
                approval_url=payment_obj.links[1]['href'],
                payment_id=payment_obj.id
            )
        else:
            return PaymentResponse(
                success=False,
                message=f"Payment creation failed: {payment_obj.error['message']}"
            )
    except Exception as e:
        return PaymentResponse(
            success=False,
            message=f"Error: {str(e)}"
        )

@app.post("/api/execute-payment")
async def execute_payment(payment_id: str, payer_id: str, db = Depends(get_db)):
    """Ejecutar pago en PayPal"""
    try:
        payment = paypalrestsdk.Payment.find(payment_id)
        
        if payment.execute({"payer_id": payer_id}):
            transaction = db.query(Transaction).filter(
                Transaction.payment_id == payment_id
            ).first()
            
            if transaction:
                transaction.status = "completed"
                transaction.completed_at = datetime.now()
                db.commit()
            
            user_token = f"{transaction.user_id}:{payment_id}"
            
            return {
                "success": True,
                "message": "Payment executed successfully",
                "token": user_token,
                "prompts": transaction.prompts_count
            }
        else:
            return {
                "success": False,
                "message": f"Payment execution failed: {payment.error['message']}"
            }
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

@app.post("/api/grant-free-access")
async def grant_free_access(user_id: str, db = Depends(get_db)):
    """Otorgar acceso gratuito con 5 prompts"""
    try:
        user = db.query(User).filter(User.email == user_id).first()
        
        if not user:
            user = User(
                email=user_id,
                prompts_remaining=5,
                is_free_user=True
            )
            db.add(user)
            db.commit()
        
        user_token = f"{user_id}:free"
        
        return {
            "success": True,
            "message": "Free access granted",
            "token": user_token,
            "prompts": 5
        }
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

@app.post("/api/generate-specialized-prompt")
async def generate_specialized_prompt(prompt: PromptRequest, db = Depends(get_db)):
    """Generar prompt especializado según plataforma y modelo"""
    try:
        user = db.query(User).filter(User.email == prompt.user_id).first()
        
        if not user:
            return PromptGenerationResponse(
                success=False,
                message="User not found",
                original_prompt="",
                optimized_prompt="",
                platform=prompt.platform,
                model=prompt.model,
                remaining_prompts=0
            )
        
        if user.prompts_remaining <= 0:
            return PromptGenerationResponse(
                success=False,
                message="No prompts remaining. Please purchase more prompts.",
                original_prompt="",
                optimized_prompt="",
                platform=prompt.platform,
                model=prompt.model,
                remaining_prompts=0
            )
        
        # Aplicar modificadores de especialización
        optimized_prompt = apply_prompt_modifiers(
            base_prompt=prompt.prompt_text,
            platform=prompt.platform,
            model=prompt.model,
            niche=prompt.niche or "",
            product=prompt.product or "",
            pain_point=prompt.pain_point or ""
        )
        
        # Deducir un prompt
        user.prompts_remaining -= 1
        
        # Registrar en log
        log = PromptLog(
            user_id=prompt.user_id,
            prompt_text=prompt.prompt_text,
            response=optimized_prompt
        )
        db.add(log)
        db.commit()
        
        return PromptGenerationResponse(
            success=True,
            message="Prompt generated successfully",
            original_prompt=prompt.prompt_text,
            optimized_prompt=optimized_prompt,
            platform=prompt.platform,
            model=prompt.model,
            remaining_prompts=user.prompts_remaining
        )
    except Exception as e:
        return PromptGenerationResponse(
            success=False,
            message=f"Error: {str(e)}",
            original_prompt="",
            optimized_prompt="",
            platform=prompt.platform,
            model=prompt.model,
            remaining_prompts=0
        )

@app.get("/api/user-info")
async def get_user_info(user_id: str, db = Depends(get_db)):
    """Obtener información del usuario y prompts restantes"""
    try:
        user = db.query(User).filter(User.email == user_id).first()
        
        if not user:
            return {"success": False, "message": "User not found"}
        
        return {
            "success": True,
            "user_id": user.email,
            "prompts_remaining": user.prompts_remaining,
            "is_free_user": user.is_free_user,
            "created_at": user.created_at
        }
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

@app.get("/success", response_class=HTMLResponse)
async def payment_success():
    """Página de éxito de pago"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Pago Completado</title>
        <style>
            body { font-family: Arial, sans-serif; background: #667eea; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
            .container { background: white; padding: 50px; border-radius: 10px; text-align: center; }
            h1 { color: #28a745; }
            p { color: #666; margin: 20px 0; }
            a { background: #667eea; color: white; padding: 10px 30px; text-decoration: none; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>✅ ¡Pago Completado!</h1>
            <p>Tu compra ha sido procesada correctamente.</p>
            <p>Estamos redirigiendo a la aplicación...</p>
            <a href="/app">Ir a GORILLA AI</a>
        </div>
        <script>
            setTimeout(() => window.location.href = '/app', 3000);
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=int(os.getenv("API_PORT", 8000))
    )
