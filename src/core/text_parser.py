import re

from src.config import VERBOS_ELOCUCAO_REGEX


def _dividir_sentencas(texto: str) -> list:
    resultado = []
    for linha in re.split(r"\n+", texto):
        if not linha.strip():
            continue
        for p in re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕ])", linha.strip()):
            if p.strip():
                resultado.append(p.strip())
    return resultado


def _parsear_aspas(texto: str) -> list:
    blocos = []
    for parte in re.split(r'(".*?")', texto, flags=re.DOTALL):
        parte = parte.strip()
        if not parte:
            continue
        if parte.startswith('"') and parte.endswith('"'):
            blocos.append(
                {
                    "tipo": "fala",
                    "texto": parte.strip('"'),
                    "personagem": None,
                    "emocao": None,
                }
            )
        else:
            for sentenca in _dividir_sentencas(parte):
                blocos.append(
                    {
                        "tipo": "narrador",
                        "texto": sentenca,
                        "personagem": "Narrador",
                        "emocao": "neutral",
                    }
                )
    return blocos


def _parsear_travessao(texto: str) -> list:
    texto = texto.replace("--", "—").replace("\u2013", "—")
    blocos = []
    for linha in texto.split("\n"):
        linha_strip = linha.strip()
        if not linha_strip:
            continue

        if linha_strip.startswith("—"):
            conteudo = linha_strip[1:].strip()
            partes = re.split(r"\s+—\s+", conteudo)

            if len(partes) == 1:
                blocos.append(
                    {
                        "tipo": "fala",
                        "texto": partes[0].strip(),
                        "personagem": None,
                        "emocao": None,
                    }
                )
            elif len(partes) == 2:
                blocos.append(
                    {
                        "tipo": "fala",
                        "texto": partes[0].strip(),
                        "personagem": None,
                        "emocao": None,
                    }
                )
                for s in _dividir_sentencas(partes[1]):
                    blocos.append(
                        {
                            "tipo": "narrador",
                            "texto": s,
                            "personagem": "Narrador",
                            "emocao": "neutral",
                        }
                    )
            else:
                blocos.append(
                    {
                        "tipo": "fala",
                        "texto": partes[0].strip(),
                        "personagem": None,
                        "emocao": None,
                    }
                )
                for s in _dividir_sentencas(partes[1]):
                    blocos.append(
                        {
                            "tipo": "narrador",
                            "texto": s,
                            "personagem": "Narrador",
                            "emocao": "neutral",
                        }
                    )
                blocos.append(
                    {
                        "tipo": "fala",
                        "texto": " — ".join(partes[2:]).strip(),
                        "personagem": None,
                        "emocao": None,
                    }
                )
        else:
            # Substitui travessões explicativos no meio da frase por vírgulas para melhor TTS
            linha_limpa = re.sub(r"\s+[—\-]\s+", ", ", linha_strip)
            for s in _dividir_sentencas(linha_limpa):
                blocos.append(
                    {
                        "tipo": "narrador",
                        "texto": s,
                        "personagem": "Narrador",
                        "emocao": "neutral",
                    }
                )
    return blocos


def detectar_modo_dialogo(texto: str) -> str:
    n_aspas = len(re.findall(r'"[^"]{3,}"', texto))
    n_travessao = len(re.findall(r"(?m)^\s*—", texto))
    modo = "travessao" if n_travessao > n_aspas else "aspas"
    return modo


def parsear_texto(texto: str, modo: str = "auto") -> list:
    if modo == "auto":
        modo = detectar_modo_dialogo(texto)
    return _parsear_travessao(texto) if modo == "travessao" else _parsear_aspas(texto)


def selecionar_atribuidor(blocos: list, i: int) -> str:
    antes = (
        blocos[i - 1]["texto"] if i > 0 and blocos[i - 1]["tipo"] == "narrador" else ""
    )
    depois = (
        blocos[i + 1]["texto"]
        if i + 1 < len(blocos) and blocos[i + 1]["tipo"] == "narrador"
        else ""
    )
    tv_d = bool(VERBOS_ELOCUCAO_REGEX.search(depois))
    tv_a = bool(VERBOS_ELOCUCAO_REGEX.search(antes))
    if tv_d:
        return depois
    elif antes.strip().startswith(",") and len(antes.strip()) < 60 and tv_a:
        return antes
    elif tv_a:
        return antes.rstrip(":").strip()
    return ""
