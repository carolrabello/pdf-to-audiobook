"""
Responsabilidade única: falar com o Gemini TTS e montar o MP3 final.
Mantém as otimizações do item 5: agrupa blocos do mesmo personagem/emoção
(menos chamadas) e oferece dry_run() para conferir tudo sem gastar 1 chamada.
"""
import time
import wave
import google.genai as genai
import google.genai.types as genai_types
from pydub import AudioSegment
from config import GEMINI_API_KEY, LIMITE_CHARS_TTS, MODELO_TTS
from pathlib import Path

def agrupar_blocos(blocos: list) -> list:
    """Funde blocos sequenciais do mesmo personagem e mesma emoção."""
    agrupados = []
    for bloco in blocos:
        if not agrupados:
            agrupados.append(bloco.copy())
            continue
        ultimo = agrupados[-1]
        if bloco["personagem"] == ultimo["personagem"] and bloco["emocao"] == ultimo["emocao"]:
            ultimo["texto"] += " " + bloco["texto"]
        else:
            agrupados.append(bloco.copy())
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
        for separador in (". ", "! ", "? ", ", "):
            pos = texto.rfind(separador, 0, limite)
            if pos != -1:
                corte = pos + len(separador)
                break
        segmentos.append(texto[:corte].strip())
        texto = texto[corte:].strip()
    return [s for s in segmentos if s]


def preparar_segmentos(blocos_agrupados: list) -> list:
    segmentos = []
    for bloco in blocos_agrupados:
        for parte in _dividir_em_segmentos(bloco["texto"], LIMITE_CHARS_TTS):
            segmento = bloco.copy()
            segmento["texto"] = parte
            segmentos.append(segmento)
    return segmentos


def _aplicar_tag_emocao(texto: str, emocao) -> str:
    # Adiciona o comando de estilo e/ou tags oficiais no início do texto,
    # sempre em português (pt-BR é GA no Gemini TTS - não precisa traduzir).
    direcao = "Fale em português do Brasil, com sotaque brasileiro. "
    if not emocao or emocao == "neutral":
        return direcao + texto

    estilo = emocao.get("estilo") if isinstance(emocao, dict) else None
    tags = emocao.get("tags") if isinstance(emocao, dict) else []

    prefixo = f"{estilo}. " if estilo else ""
    tags_texto = (" ".join(tags) + " ") if tags else ""
    return f"{direcao}{prefixo}{tags_texto}{texto}"


def _descrever_emocao(emocao) -> str:
    """Só formata a emoção numa string curta pra exibir no dry_run."""
    if not emocao or emocao == "neutral":
        return "—"
    if isinstance(emocao, dict):
        partes = []
        if emocao.get("estilo"):
            partes.append(emocao["estilo"])
        if emocao.get("tags"):
            partes.append(" ".join(emocao["tags"]))
        return "; ".join(partes) if partes else "—"
    return str(emocao)


def dry_run(blocos: list, catalogo: dict) -> list:
    """Mostra a segmentação final ANTES de gastar chamadas de API."""
    agrupados = agrupar_blocos(blocos)
    segmentos = preparar_segmentos(agrupados)

    print(f"\n{'=' * 70}\n DRY RUN — {len(segmentos)} segmento(s) para síntese\n{'=' * 70}")
    print(f"{'#':<4} {'PERSONAGEM':<14} {'VOZ':<10} {'EMOÇÃO':<35} TEXTO (início)")
    print("-" * 70)
    for i, seg in enumerate(segmentos):
        info = catalogo.get(seg["personagem"], catalogo["Narrador"])
        emocao = _descrever_emocao(seg["emocao"])
        preview = seg["texto"][:50].replace("\n", " ")
        print(f"{i:<4} {seg['personagem']:<14} {info['voz']:<10} {emocao:<35} {preview}...")

    print(f"\nPersonagens detectados: {[p for p in catalogo if p != 'Narrador']}")
    return segmentos


def sintetizar_gemini(client, texto: str, voz: str, emocao: str, arquivo: str, max_tentativas: int = 3) -> tuple:
    """Retorna (sucesso: bool, usou_fallback: bool)."""
    def _tentar(texto_para_enviar: str) -> bool:
        for tentativa in range(1, max_tentativas + 1):
            try:
                response = client.models.generate_content(
                    model=MODELO_TTS,
                    contents=texto_para_enviar,
                    config=genai_types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=genai_types.SpeechConfig(
                            voice_config=genai_types.VoiceConfig(
                                prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(voice_name=voz)
                            )
                        ),
                    ),
                )
                if not response.candidates:
                    motivo = getattr(response, "prompt_feedback", "sem detalhes")
                    raise RuntimeError(f"Resposta bloqueada pela API. Motivo: {motivo}")

                dados_pcm = response.candidates[0].content.parts[0].inline_data.data
                with wave.open(arquivo, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(24000)
                    wf.writeframes(dados_pcm)
                return True
            except Exception as erro:
                print(f"    Tentativa {tentativa}/{max_tentativas} falhou: {erro}")
                time.sleep(10)
        return False

    texto_com_tag = _aplicar_tag_emocao(texto, emocao)
    if _tentar(texto_com_tag):
        return True, False

    print("    Todas as tentativas com tag falharam - tentando 1x com o texto puro (sem sotaque/emoção)...")
    sucesso = _tentar(texto)
    return sucesso, sucesso  # se deu certo aqui, foi via fallback


def gerar_audiobook(blocos: list, catalogo: dict, caminho_arquivo_origem: str) -> str:
    # 1. Extrai apenas o nome do arquivo base (ex: "livro.pdf" vira "livro")
    nome_base = Path(caminho_arquivo_origem).stem
    
    # 2. Cria a pasta usando o nome do livro extraído
    pasta_saida = Path(f"data/outputs/{nome_base}")
    pasta_saida.mkdir(parents=True, exist_ok=True)
    
    # 3. Define que o MP3 final terá o mesmo nome e ficará dentro da nova pasta
    arquivo_final = str(pasta_saida / f"{nome_base}.mp3")

    print(f"\nCriando pasta e salvando em: {pasta_saida}")
    print("Agrupando e segmentando blocos...")
    segmentos = preparar_segmentos(agrupar_blocos(blocos))
    print(f"Síntese: {len(segmentos)} segmento(s) | limite {LIMITE_CHARS_TTS} chars")

    client = genai.Client(api_key=GEMINI_API_KEY)
    arquivos, pulados = [], []

    for i, seg in enumerate(segmentos):
        info = catalogo.get(seg["personagem"], catalogo["Narrador"])
        
        # 4. Salva os arquivos .wav DENTRO da pasta do respectivo livro
        arquivo_temp = str(pasta_saida / f"_seg_{i:03d}.wav")
        print(f"[{i:01d}/{len(segmentos) - 1}] {seg['personagem']:<14} | {info['voz']}")

        sucesso, usou_fallback = sintetizar_gemini(client, seg["texto"], info["voz"], seg["emocao"], arquivo_temp)
        if sucesso:
            arquivos.append(arquivo_temp)
            if usou_fallback:
                pulados.append((i, seg["personagem"], "gerado SEM sotaque/emoção (fallback)"))
        else:
            pulados.append((i, seg["personagem"], "trecho totalmente descartado"))
        
        if i < len(segmentos) - 1:
            time.sleep(6.5)

    print("\nMontando arquivo final...")
    final = AudioSegment.empty()
    for arq in arquivos:
        final += AudioSegment.from_file(arq, format="wav") + AudioSegment.silent(duration=350)

    try:
        final.export(arquivo_final, format="mp3")
    except PermissionError:
        alternativo = str(pasta_saida / f"{nome_base}_{int(time.time())}.mp3")
        print(f"Não consegui sobrescrever {arquivo_final} (arquivo em uso?). Salvando como {alternativo}")
        final.export(alternativo, format="mp3")
        arquivo_final = alternativo

    print(f"Audiobook exportado: {arquivo_final}")
    if pulados:
        print(f"\nATENÇÃO: {len(pulados)} segmento(s) ficaram de fora do áudio final:")
        for idx, personagem, preview in pulados:
            print(f"  [{idx}] {personagem}: {preview}...")
            
    return arquivo_final