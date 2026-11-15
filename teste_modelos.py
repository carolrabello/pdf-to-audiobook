"""
Script de Teste Múltiplo para Modelos Gemini TTS
Testa diferentes cenários literários (emoções, vozes e gêneros) nos modelos escolhidos.
"""
import time
import wave
import google.genai as genai
import google.genai.types as genai_types
from config import GCP_PROJECT_ID, GCP_LOCATION

# Vamos focar apenas nos dois que você gostou mais, para poupar tempo.
MODELOS = [
    "gemini-2.5-flash-preview-tts",
    "gemini-2.5-pro-tts"
]

# Lista de cenários literários para testar a flexibilidade dos modelos
CENARIOS = [
    # {
    #     "nome": "1_Tristeza",
    #     "voz": "Leda", # Voz feminina
    #     "prompt": (
    #         #"Fale em português do Brasil, com sotaque brasileiro. "
    #         "Diga a fala a seguir com voz infantil. "
    #         "[crying] Eu não acredito que ele se foi... Como vou conseguir viver nesta casa tão vazia sem ele?"
    #     )
    # },
    {
        "nome": "2_Furia",
        "voz": "Orus", # Voz masculina forte
        "prompt": (
            #"Fale em português do Brasil, com sotaque brasileiro. "
            "Diga a fala a seguir com voz de idoso."
            "[angry] Saia da minha frente agora mesmo! Eu já disse que não quero ouvir mais nenhuma palavra saindo da sua boca!"
        )
    },
    # {
    #     "nome": "3_Suspense",
    #     "voz": "Charon", # Voz de narrador/neutra
    #     "prompt": (
    #         #"Fale em português do Brasil, com sotaque brasileiro. "
    #         "Fale lentamente, criando suspense. Diga a fala a seguir sussurrando. "
    #         "A maçaneta girou devagar... e, no escuro do corredor, "
    #         "ele percebeu que não estava sozinho."
    #     )
    # }
]

def rodar_multiplos_testes():
    print("=" * 60)
    print("INICIANDO BATERIA DE TESTES DE ATUAÇÃO TTS")
    print("=" * 60)

    client = genai.Client(
        vertexai=True, 
        project=GCP_PROJECT_ID, 
        location=GCP_LOCATION
    )

    for cenario in CENARIOS:
        print(f"\n🎬 CENÁRIO: {cenario['nome']} | VOZ: {cenario['voz']}")
        print(f"Texto: '{cenario['prompt'][:80]}...'")

        for modelo in MODELOS:
            print(f"  🤖 Modelo: {modelo} ... ", end="", flush=True)
            nome_arquivo = f"teste_idoso_{cenario['nome']}_{modelo.replace('.', '_')}.wav"
            
            try:
                inicio = time.time()
                response = client.models.generate_content(
                    model=modelo,
                    contents=cenario['prompt'],
                    config=genai_types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=genai_types.SpeechConfig(
                            voice_config=genai_types.VoiceConfig(
                                prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(voice_name=cenario['voz'])
                            )
                        ),
                    ),
                )
                tempo_gasto = time.time() - inicio

                # Validações de segurança do VS Code (Type Narrowing)
                if not response.candidates or not response.candidates[0].content or not response.candidates[0].content.parts:
                    print("❌ Resposta vazia.")
                    continue

                inline_data = response.candidates[0].content.parts[0].inline_data
                if inline_data is None or inline_data.data is None:
                    print("❌ Sem dados de áudio.")
                    continue

                dados_pcm = inline_data.data
                if not isinstance(dados_pcm, bytes):
                    print("❌ Formato inválido.")
                    continue

                with wave.open(nome_arquivo, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(24000)
                    wf.writeframes(dados_pcm)

                print(f"✅ OK ({tempo_gasto:.2f}s)")

            except Exception as erro:
                print(f"❌ Erro: {erro}")

    print("\n" + "=" * 60)
    print("Testes finalizados! Ouça os arquivos gerados na sua pasta.")

if __name__ == "__main__":
    rodar_multiplos_testes()