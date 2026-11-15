import hashlib
import time
import wave
from pathlib import Path

import google.genai as genai
import google.genai.types as genai_types
from google.genai import errors as genai_errors
from pydub import AudioSegment

from config import (
    GCP_PROJECT_ID, GCP_LOCATION, MODELO_TTS, IDIOMA_TTS, LIMITE_CHARS_TTS, PAUSA_ENTRE_CHAMADAS_S,
    MAX_TENTATIVAS, SILENCIO_ENTRE_SEGMENTOS_MS, DESCRICOES_IDADE, DIRECAO_PADRAO,
)

_ERROS_FATAIS = (401, 403, 404)  # credencial, permissão/billing ou modelo inexistente: repetir não resolve


class ErroFatalTTS(Exception):
    """Problema de configuração (credencial, billing, modelo) - aborta o job inteiro."""


class _RespostaBloqueada(Exception):
    """A API respondeu, mas bloqueou o conteúdo (sem candidatos)."""


# ----------------------------------------------------------------- segmentação
def agrupar_blocos(blocos: list) -> list:
    """Funde blocos sequenciais do mesmo personagem e mesma emoção."""
    agrupados = []
    for bloco in blocos:
        ultimo = agrupados[-1] if agrupados else None
        if ultimo and bloco["personagem"] == ultimo["personagem"] and bloco["emocao"] == ultimo["emocao"]:
            ultimo["texto"] += " " + bloco["texto"]
        else:
            agrupados.append(bloco.copy())
    return agrupados


def _dividir_em_segmentos(texto: str, limite: int) -> list:
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


def preparar_segmentos(blocos: list) -> list:
    """Agrupa os blocos e quebra cada um em trechos de até LIMITE_CHARS_TTS.
    Trechos sem nenhuma letra (ex.: '' ou '.') são descartados: enviados sozinhos,
    o modelo leria só a instrução de voz em voz alta e a chamada seria cobrada."""
    segmentos = []
    for bloco in agrupar_blocos(blocos):
        for parte in _dividir_em_segmentos(bloco["texto"], LIMITE_CHARS_TTS):
            parte = parte.lstrip(" ,.;:")  # sobra de pontuação do corte entre fala e narração
            if any(c.isalnum() for c in parte):
                segmentos.append({**bloco, "texto": parte})
    return segmentos


# ----------------------------------------------------------------- prompt
def _instrucao(emocao: dict | None, idade: str | None) -> str:
    """Direção de voz em linguagem natural (idade + estilo). Vazia = voz neutra."""
    partes = []
    if idade in DESCRICOES_IDADE:
        partes.append(DESCRICOES_IDADE[idade])
    if emocao and emocao["estilo"]:
        partes.append(emocao["estilo"])
    return ". ".join(partes)


def _montar_prompt(texto: str, emocao: dict | None, idade: str | None = None) -> str:
    """Formato do guia do Gemini TTS: '<instrução>: <texto>', com as tags de efeito
    ([shouting], [sigh]...) dentro do texto. TODO trecho leva instrução (a padrão,
    se não houver idade nem estilo): texto cru e curto faz o modelo errar. O idioma
    NÃO vai no prompt: é definido por language_code na chamada."""
    corpo = f"{' '.join(emocao['tags'])} {texto}".strip() if emocao else texto
    return f"{_instrucao(emocao, idade) or DIRECAO_PADRAO}: {corpo}"


def _info_voz(catalogo: dict, personagem: str) -> dict:
    return catalogo.get(personagem, catalogo["Narrador"])


# ----------------------------------------------------------------- dry run
def _resumo(segmentos: list) -> str:
    return f"{len(segmentos)} segmentos | {MODELO_TTS} | projeto {GCP_PROJECT_ID}"


def dry_run(blocos: list, catalogo: dict):
    """Mostra a segmentação final ANTES de gastar chamadas de API."""
    segmentos = preparar_segmentos(blocos)

    print(f"\n{'#':<3} {'PERSONAGEM':<13} {'VOZ':<8} {'INSTRUÇÃO':<42} TEXTO")
    for i, seg in enumerate(segmentos):
        info = _info_voz(catalogo, seg["personagem"])
        instrucao = _instrucao(seg["emocao"], info.get("idade")) or "(padrão)"
        tags = " ".join(seg["emocao"]["tags"]) if seg["emocao"] else ""
        texto = f"{tags} {seg['texto']}".strip()[:45].replace("\n", " ")
        print(f"{i:<3} {seg['personagem']:<13} {info['voz']:<8} {instrucao[:40]:<42} {texto}")

    print("\nPersonagens:")
    for nome, info in catalogo.items():
        if nome != "Narrador":
            extra = f", {info['idade']}" if info.get("idade") else ""
            print(f"  {nome} ({info['genero']}{extra}) - {info['voz']}")

    print(f"\n{_resumo(segmentos)}")


# ----------------------------------------------------------------- Gemini TTS
def _criar_cliente():
    """Cria o cliente SEMPRE pelo Vertex AI (vertexai=True): a cobrança vai para
    o projeto GCP e consome o crédito. Sem esse parâmetro, uma chave de API do
    AI Studio no ambiente faria o SDK usar outro endpoint, cobrado à parte."""
    return genai.Client(vertexai=True, project=GCP_PROJECT_ID, location=GCP_LOCATION)


def _chamar_tts(client, prompt: str, voz: str) -> bytes:
    """Uma chamada ao TTS. Retorna o áudio PCM (16 bits, 24 kHz, mono)."""
    response = client.models.generate_content(
        model=MODELO_TTS,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=genai_types.SpeechConfig(
                language_code=IDIOMA_TTS,
                voice_config=genai_types.VoiceConfig(
                    prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(voice_name=voz)
                )
            ),
        ),
    )
    if not response.candidates:
        raise _RespostaBloqueada(getattr(response, "prompt_feedback", "sem detalhes"))
    return response.candidates[0].content.parts[0].inline_data.data


def _sintetizar_com_retry(client, prompt: str, voz: str) -> bytes | None:
    """Repete só quando faz sentido (429, erro 5xx, resposta sem áudio, rede).
    Conteúdo bloqueado ou pedido inválido (400) não melhora tentando de novo;
    erro de credencial/billing/modelo (401/403/404) aborta tudo."""
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            return _chamar_tts(client, prompt, voz)
        except _RespostaBloqueada:
            print("    bloqueado pela API (não repete)")
            return None
        except genai_errors.APIError as erro:
            if erro.code in _ERROS_FATAIS:
                raise ErroFatalTTS(f"Erro {erro.code} do Vertex AI - verifique credencial, "
                                   f"billing e nome do modelo: {erro}") from erro
            if erro.code == 400:
                print("    pedido recusado (400)")
                return None
            falha = erro
        except Exception as erro:  # resposta sem áudio, queda de rede etc.
            falha = erro
        print(f"    tentativa {tentativa}/{MAX_TENTATIVAS} falhou ({getattr(falha, 'code', type(falha).__name__)})")
        if tentativa < MAX_TENTATIVAS:
            time.sleep(10 * tentativa)
    return None


def sintetizar_gemini(client, voz: str, prompt: str, texto_puro: str) -> tuple:
    """Retorna (áudio PCM ou None, usou_fallback). Se o prompt com direção de
    voz/emoção falhar, tenta 1x só com o texto puro."""
    pcm = _sintetizar_com_retry(client, prompt, voz)
    if pcm:
        return pcm, False
    print("    tentando de novo só com o texto puro")
    pcm = _sintetizar_com_retry(client, texto_puro, voz)
    return pcm, pcm is not None


def _salvar_wav(caminho: Path, pcm: bytes):
    with wave.open(str(caminho), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(pcm)


def _caminho_cache(pasta: Path, i: int, voz: str, prompt: str) -> Path:
    """O nome do arquivo inclui um hash de modelo+voz+prompt: se qualquer um
    mudar, o trecho é sintetizado de novo; se não mudou, reaproveita sem custo."""
    h = hashlib.md5(f"{MODELO_TTS}|{voz}|{prompt}".encode()).hexdigest()[:8]
    return pasta / f"seg_{i:03d}_{h}.wav"


# ----------------------------------------------------------------- audiobook
def gerar_audiobook(blocos: list, catalogo: dict, caminho_arquivo_origem: str) -> str:
    segmentos = preparar_segmentos(blocos)
    total = len(segmentos)

    nome_base = Path(caminho_arquivo_origem).stem
    pasta_saida = Path("data/outputs") / nome_base
    pasta_cache = pasta_saida / "cache"
    pasta_cache.mkdir(parents=True, exist_ok=True)
    arquivo_final = pasta_saida / f"{nome_base}.mp3"

    print(f"\n{_resumo(segmentos)}")

    client = _criar_cliente()
    wavs, pulados = [], []

    for i, seg in enumerate(segmentos):
        info = _info_voz(catalogo, seg["personagem"])
        prompt = _montar_prompt(seg["texto"], seg["emocao"], info.get("idade"))
        arquivo = _caminho_cache(pasta_cache, i, info["voz"], prompt)
        print(f"[{i + 1}/{total}] {seg['personagem']} ({info['voz']})", end="")

        if arquivo.exists():
            print(" - cache")
            wavs.append(arquivo)
            continue
        print()

        pcm, usou_fallback = sintetizar_gemini(client, info["voz"], prompt, seg["texto"])
        if pcm is None:
            pulados.append((i + 1, seg["personagem"], "descartado"))
        else:
            if usou_fallback:  # não vai pro cache: numa nova execução tenta de novo com emoção
                arquivo = arquivo.with_name(f"seg_{i:03d}_fallback.wav")
                pulados.append((i + 1, seg["personagem"], "gerado sem instrução de voz"))
            _salvar_wav(arquivo, pcm)
            wavs.append(arquivo)

        if i < total - 1:
            time.sleep(PAUSA_ENTRE_CHAMADAS_S)

    if not wavs:
        raise RuntimeError("Nenhum segmento foi sintetizado - nada para montar.")

    silencio = AudioSegment.silent(duration=SILENCIO_ENTRE_SEGMENTOS_MS)
    final = AudioSegment.empty()
    for wav in wavs:
        final += AudioSegment.from_wav(str(wav)) + silencio

    try:
        final.export(str(arquivo_final), format="mp3")
    except PermissionError:
        arquivo_final = pasta_saida / f"{nome_base}_{int(time.time())}.mp3"
        final.export(str(arquivo_final), format="mp3")

    print(f"Duração do áudio: {len(final) / 60000:.1f} min ({total} segmentos)")
    for idx, personagem, motivo in pulados:
        print(f"  atenção: segmento {idx} ({personagem}) {motivo}")
    return str(arquivo_final)