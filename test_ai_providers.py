#!/usr/bin/env python3
"""
Test de providers de IA con contador de peticiones.
Verifica que gpt-4o-mini (GitHub), gpt-4o (fallback), y Groq funcionen correctamente.
Lleva cuenta de requests para validar rate limits.
"""
import os
import sys
import time
import json
from datetime import datetime
from collections import defaultdict

# ─── Contador de peticiones ────────────────────────────────────────
request_counter = defaultdict(int)  # modelo → cantidad de peticiones

def log_request(model: str, provider: str, query: str, success: bool, tokens_used: dict = None):
    """Registra cada petición con timestamp."""
    request_counter[model] += 1
    status = "✅" if success else "❌"
    ts = datetime.now().strftime("%H:%M:%S")
    token_info = ""
    if tokens_used:
        token_info = f" | tokens: in={tokens_used.get('prompt', '?')}, out={tokens_used.get('completion', '?')}"
    print(f"  [{ts}] {status} {provider}/{model} #{request_counter[model]} — {query[:50]}{token_info}")

def print_summary():
    """Muestra resumen de peticiones."""
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE PETICIONES POR MODELO")
    print("=" * 60)
    total = 0
    for model, count in sorted(request_counter.items()):
        print(f"  {model}: {count} peticiones")
        total += count
    print(f"\n  TOTAL: {total} peticiones")
    print("=" * 60)
    
    # Rate limits conocidos
    print("\n📋 RATE LIMITS CONOCIDOS:")
    print("  GitHub gpt-4o-mini:  150 req/día")
    print("  GitHub gpt-4o:       ~15-20 req/día")
    print("  GitHub o4-mini:       12 req/día")
    print("  Groq qwen3-32b:      100K TPD (~32 interacciones/día)")
    print("  Groq Llama 3.3 70B:  100K TPD")
    print()


# ─── Test 1: GitHub gpt-4o-mini ─────────────────────────────────────
def test_github_gpt4o_mini():
    """Test function calling con GitHub Models gpt-4o-mini."""
    print("\n" + "─" * 60)
    print("🧪 TEST 1: GitHub Models — gpt-4o-mini")
    print("─" * 60)
    
    api_key = os.environ.get("AI_API_KEY", "")
    if not api_key:
        print("  ⚠️ AI_API_KEY no configurada, saltando test GitHub")
        return False
    
    client = OpenAI(
        api_key=api_key,
        base_url="https://models.inference.ai.azure.com",
    )
    
    # Cargar tools
    sys.path.insert(0, os.path.dirname(__file__))
    from app.infrastructure.ai.ai_functions import SYSTEM_MESSAGE, get_tools
    tools = get_tools()
    
    tests = [
        ("Hola, ¿qué podés hacer?", "saludar"),
        ("¿ tenés bicicletas?", "buscar_articulos"),
        ("¿Cómo está la caja?", "consultar_caja"),
        ("Abrí la caja con 50000", "abrir_caja"),
    ]
    
    model = "gpt-4o-mini"
    for query, expected_function in tests:
        try:
            messages = [
                {"role": "system", "content": SYSTEM_MESSAGE},
                {"role": "user", "content": query}
            ]
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                max_completion_tokens=500,
            )
            
            choice = response.choices[0]
            has_tool_call = bool(choice.message.tool_calls)
            called_function = choice.message.tool_calls[0].function.name if has_tool_call else None
            
            # Extraer usage
            tokens = {
                "prompt": response.usage.prompt_tokens if response.usage else "?",
                "completion": response.usage.completion_tokens if response.usage else "?",
            }
            
            success = called_function == expected_function
            log_request(model, "github", query, success, tokens)
            
            if not success:
                print(f"    ⚠️  Esperaba {expected_function}, obtuvo {called_function}")
                print(f"    Content: {choice.message.content[:100] if choice.message.content else 'None'}")
            
            time.sleep(1)  # Rate limit courtesy
            
        except Exception as e:
            log_request(model, "github", query, False)
            print(f"    ❌ Error: {e}")
            if "429" in str(e) or "rate" in str(e).lower():
                print("    ⚠️  Rate limit alcanzado — deteniendo tests de GitHub")
                return False
    
    return True


# ─── Test 2: GitHub gpt-4o (fallback) ───────────────────────────────
def test_github_gpt4o():
    """Test function calling con GitHub Models gpt-4o."""
    print("\n" + "─" * 60)
    print("🧪 TEST 2: GitHub Models — gpt-4o (fallback)")
    print("─" * 60)
    print("  ⚠️  gpt-4o tiene ~15-20 req/día — solo testeamos 1 llamada")
    
    api_key = os.environ.get("AI_API_KEY", "")
    if not api_key:
        print("  ⚠️ AI_API_KEY no configurada, saltando test gpt-4o")
        return False
    
    client = OpenAI(
        api_key=api_key,
        base_url="https://models.inference.ai.azure.com",
    )
    
    from app.infrastructure.ai.ai_functions import SYSTEM_MESSAGE, get_tools
    tools = get_tools()
    
    model = "gpt-4o"
    query = "Buscá cascos"
    
    try:
        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": query}
        ]
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            max_completion_tokens=500,
        )
        
        choice = response.choices[0]
        has_tool_call = bool(choice.message.tool_calls)
        called_function = choice.message.tool_calls[0].function.name if has_tool_call else None
        
        tokens = {
            "prompt": response.usage.prompt_tokens if response.usage else "?",
            "completion": response.usage.completion_tokens if response.usage else "?",
        }
        
        success = called_function == "buscar_articulos"
        log_request(model, "github", query, success, tokens)
        
        if not success:
            print(f"    ⚠️  Esperaba buscar_articulos, obtuvo {called_function}")
        
    except Exception as e:
        log_request(model, "github", query, False)
        print(f"    ❌ Error: {e}")
        return False
    
    return True


# ─── Test 3: Groq qwen3-32b ────────────────────────────────────────
def test_groq_qwen():
    """Test function calling con Groq qwen3-32b."""
    print("\n" + "─" * 60)
    print("🧪 TEST 3: Groq — qwen/qwen3-32b")
    print("─" * 60)
    
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        print("  ⚠️ GROQ_API_KEY no configurada, saltando test Groq")
        return False
    
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )
    
    from app.infrastructure.ai.ai_functions import SYSTEM_MESSAGE, get_tools
    tools = get_tools()
    
    tests = [
        ("Hola, ¿qué hacés?", "saludar"),
        ("¿Cuánto sale el casco Gauthier?", "consultar_precio"),
        ("¿Quién es Federico?", "buscar_clientes"),
        ("Cerrá la caja", "cerrar_caja"),
    ]
    
    model = "qwen/qwen3-32b"
    for query, expected_function in tests:
        try:
            messages = [
                {"role": "system", "content": SYSTEM_MESSAGE},
                {"role": "user", "content": query}
            ]
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                max_completion_tokens=500,
            )
            
            choice = response.choices[0]
            has_tool_call = bool(choice.message.tool_calls)
            called_function = choice.message.tool_calls[0].function.name if has_tool_call else None
            
            tokens = {
                "prompt": response.usage.prompt_tokens if response.usage else "?",
                "completion": response.usage.completion_tokens if response.usage else "?",
            }
            
            success = called_function == expected_function
            log_request(model, "groq", query, success, tokens)
            
            if not success:
                print(f"    ⚠️  Esperaba {expected_function}, obtuvo {called_function}")
                print(f"    Content: {choice.message.content[:100] if choice.message.content else 'None'}")
            
            time.sleep(2)  # Groq rate limit courtesy
            
        except Exception as e:
            log_request(model, "groq", query, False)
            print(f"    ❌ Error: {e}")
            if "429" in str(e) or "rate" in str(e).lower():
                print("    ⚠️  Rate limit alcanzado — deteniendo tests de Groq")
                return False
    
    return True


# ─── Test 4: AIService completo (integración) ──────────────────────
def test_aiservice_integration():
    """Test AIService completo a través de la app."""
    print("\n" + "─" * 60)
    print("🧪 TEST 4: AIService — integración completa (GitHub)")
    print("─" * 60)
    
    from app.infrastructure.ai.ai_service import AIService
    
    service = AIService(provider="github")
    
    tests = [
        "Hola, ¿qué podés hacer?",
        "¿Cuánto stock hay del casco Gauthier?",
        "Mostrame las facturas de la caja",
        "Generá una cotización para Federico Gauthier con bicicleta TREK y casco Gauthier",
    ]
    
    for query in tests:
        try:
            result = service.process_message("test_user", query)
            model_used = service._model  # El modelo que se usó realmente
            log_request(model_used, "github", query, bool(result))
            
            # Mostrar extracto de la respuesta
            response_text = result[:100] if result else "Sin respuesta"
            print(f"    📝 Respuesta: {response_text}...")
            
            time.sleep(1)
            
        except Exception as e:
            log_request("github-aiservice", "github", query, False)
            print(f"    ❌ Error: {e}")
            if "429" in str(e) or "rate" in str(e).lower():
                print("    ⚠️  Rate limit alcanzado — deteniendo")
                return False
    
    return True


# ─── Main ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from openai import OpenAI
    
    print("=" * 60)
    print("🚀 TEST DE PROVIDERS DE IA — Contador de Peticiones")
    print("=" * 60)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Cargar .env
    from dotenv import load_dotenv
    load_dotenv()
    
    print("📋 CONFIGURACIÓN ACTUAL:")
    print(f"  AI_PROVIDER: {os.environ.get('AI_PROVIDER', 'no configurado')}")
    print(f"  AI_API_KEY: {'✅ configurada' if os.environ.get('AI_API_KEY') else '❌ no configurada'}")
    print(f"  GROQ_API_KEY: {'✅ configurada' if os.environ.get('GROQ_API_KEY') else '❌ no configurada'}")
    print()
    
    # Ejecutar tests
    results = {}
    
    # Test 1: GitHub gpt-4o-mini
    results["github_gpt4o_mini"] = test_github_gpt4o_mini()
    
    # Test 2: GitHub gpt-4o (1 sola llamada para no agotar rate limit)
    results["github_gpt4o"] = test_github_gpt4o()
    
    # Test 3: Groq qwen3-32b
    results["groq_qwen"] = test_groq_qwen()
    
    # Test 4: Integración completa (solo si GitHub funciona)
    # results["aiservice"] = test_aiservice_integration()
    
    # Resumen
    print_summary()
    
    # Resultados
    print("📊 RESULTADOS POR TEST:")
    all_passed = True
    for name, passed in results.items():
        status = "✅ PASÓ" if passed else "❌ FALLÓ"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("🎉 TODOS LOS TESTS PASARON — Listos para WhatsApp!")
    else:
        print("⚠️  ALGUNOS TESTS FALLARON — Revisar errores arriba")
    
    sys.exit(0 if all_passed else 1)