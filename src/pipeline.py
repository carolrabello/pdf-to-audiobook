import time
import wave
import google.genai as genai
import google.genai.types as genai_types

from pydub import AudioSegment
from src.config import LIMITE_CHARS_TTS, CHAVE_GEMINI


def agrupar_blocos(blocos: list) -> list:
    agrupados = []
    for b in blocos:
        if not agrupados:
            agrupados.append(b.copy())
            continue
        ultimo = agrupados[-1]
        if b["personagem"] == ultimo["personagem"] and b["emocao"] == ultimo["emocao"]:
            ultimo["texto"] += " " + b["texto"]
        else:
            agrupados.append(b.copy())
    return agrupados


def _dividir_em_segmentos(texto: str, limite: int) -> list:
    if len(texto) <= limite:
        return [texto]
    segmentos = []
    while texto:
        if len(texto) <= limite:
            segmentos.append(texto)
            break
        corte = limite
        for sep in (". ", "! ", "? ", ", "):
            pos = texto.rfind(sep, 0, limite)
            if pos != -1:
                corte = pos + len(sep)
                break
        segmentos.append(texto[:corte].strip())
        texto = texto[corte:].strip()
    return [s for s in segmentos if s]


def _preparar_segmentos(blocos_agrupados: list) -> list:
    segmentos = []
    for bloco in blocos_agrupados:
        partes = _dividir_em_segmentos(bloco["texto"], LIMITE_CHARS_TTS)
        for parte in partes:
            seg = bloco.copy()
            seg["texto"] = parte
            segmentos.append(seg)
    return segmentos


def _aplicar_tag_emocao(texto: str, emocao: str) -> str:
    if not emocao or emocao == "neutral":
        return texto
    tags = [f"[{t.strip()}]" for t in emocao.split(",")]
    return f"{' '.join(tags)} {texto}"


def sintetizar_gemini(
    client, texto: str, voz: str, emocao: str, arquivo: str, max_tentativas: int = 5
) -> bool:
    texto_com_tag = _aplicar_tag_emocao(texto, emocao)
    for tentativa in range(1, max_tentativas + 1):
        try:
            response = client.models.generate_content(
                model="gemini-3.1-flash-tts-preview",
                contents=texto_com_tag,
                config=genai_types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=genai_types.SpeechConfig(
                        voice_config=genai_types.VoiceConfig(
                            prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                                voice_name=voz
                            )
                        )
                    ),
                ),
            )
            dados_pcm = response.candidates[0].content.parts[0].inline_data.data
            with wave.open(arquivo, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(dados_pcm)
            return True
        except Exception as e:
            print(f"    Tentativa {tentativa}/{max_tentativas} falhou: {e}")
            time.sleep(10)
            if tentativa == max_tentativas:
                return False
    return False


def dry_run(blocos: list, catalogo: dict):
    agrupados = agrupar_blocos(blocos)
    segmentos = _preparar_segmentos(agrupados)
    print(f"\n{'=' * 70}")
    print(f"  DRY RUN — {len(segmentos)} segmento(s) para síntese")
    print(f"{'=' * 70}")
    print(
        f"{'#':<4} {'TIPO':<9} {'PERSONAGEM':<14} {'VOZ':<10} {'EMOÇÃO':<20} TEXTO (início)"
    )
    print("-" * 70)
    for i, seg in enumerate(segmentos):
        personagem = seg["personagem"]
        info = catalogo.get(personagem, catalogo["Narrador"])
        voz = info["voz"]
        emocao = seg["emocao"] if seg["emocao"] != "neutral" else "—"
        tipo = seg["tipo"].upper()
        preview = seg["texto"][:50].replace("\n", " ")
        print(f"{i:<4} {tipo:<9} {personagem:<14} {voz:<10} {emocao:<20} {preview}...")
    print(f"\nPersonagens detectados: {[p for p in catalogo if p != 'Narrador']}")


def gerar_audiobook(
    blocos_originais: list, catalogo: dict, arquivo_final: str = "audiobook.mp3"
):
    print("\nAgrupando e segmentando blocos...")
    agrupados = agrupar_blocos(blocos_originais)
    segmentos = _preparar_segmentos(agrupados)

    print(f"Síntese: {len(segmentos)} segmento(s) | limite {LIMITE_CHARS_TTS} chars")
    client = genai.Client(api_key=CHAVE_GEMINI)
    arquivos = []

    for i, seg in enumerate(segmentos):
        personagem = seg["personagem"]
        info = catalogo.get(personagem, catalogo["Narrador"])
        voz = info["voz"]
        emocao = seg["emocao"]
        arquivo_temp = f"/tmp/seg_{i:03d}.wav"
        tag_display = f"[{emocao}]" if emocao != "neutral" else "[neutral]"
        print(
            f"[{i:02d}/{len(segmentos) - 1}] {personagem:14s} | {voz:8s} | {tag_display}"
        )

        if sintetizar_gemini(client, seg["texto"], voz, emocao, arquivo_temp):
            arquivos.append(arquivo_temp)
        if i < len(segmentos) - 1:
            time.sleep(6.5)

    print("\n🎧 Montando arquivo final...")
    final = AudioSegment.empty()
    for arq in arquivos:
        final += AudioSegment.from_file(arq, format="wav") + AudioSegment.silent(
            duration=350
        )
    final.export(arquivo_final, format="mp3")
    print(f"Audiobook exportado: {arquivo_final}")
    return arquivo_final
