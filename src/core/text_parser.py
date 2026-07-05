"""
Responsabilidade única: quebrar o texto bruto em blocos de "narrador" e
"fala", suportando tanto aspas quanto travessão (item 1).
Baseado no TG2, que já resolvia isso bem - poucas mudanças aqui.
"""

import re

VERBOS_ELOCUCAO_REGEX = re.compile(
    r"\b(disse|respondeu|perguntou|continuou|retrucou|gritou|afirmou|replicou|"
    r"discordou|retomou|chamou|exclamou|murmurou|sussurrou|dirigiu-se|falou|"
    r"começou|acrescentou|declarou|confessou|explicou|exigiu)\b",
    re.IGNORECASE,
)


def dividir_sentencas(texto: str) -> list:
    resultado = []
    for linha in re.split(r"\n+", texto):
        if not linha.strip():
            continue
        for parte in re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕ])", linha.strip()):
            if parte.strip():
                resultado.append(parte.strip())
    return resultado


def _bloco_fala(texto: str) -> dict:
    return {"tipo": "fala", "texto": texto.strip(), "personagem": None, "emocao": None}


def _bloco_narrador(texto: str) -> dict:
    return {
        "tipo": "narrador",
        "texto": texto.strip(),
        "personagem": "Narrador",
        "emocao": "neutral",
    }


def _parsear_aspas(texto: str) -> list:
    blocos = []
    # O regex abaixo captura tudo o que está entre aspas ou tudo o que está entre pontuação
    # re.split com parênteses mantém os delimitadores no resultado
    partes = re.split(r'("[^"]+")', texto)

    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue

        if parte.startswith('"') and parte.endswith('"'):
            # É uma fala - remove as aspas e registra
            blocos.append(_bloco_fala(parte.strip('"')))
        else:
            # É narração - pode conter o "disse Alice"
            # Precisamos fatiar essa narração também para não perder o fluxo
            for sentenca in dividir_sentencas(parte):
                blocos.append(_bloco_narrador(sentenca))
    return blocos


def _parsear_travessao(texto: str) -> list:
    texto = texto.replace("--", "—").replace("\u2013", "—")
    blocos = []
    for linha in texto.split("\n"):
        linha_strip = linha.strip()
        if not linha_strip:
            continue

        # Se a linha for um diálogo
        if linha_strip.startswith("—"):
            linha_strip = linha_strip[1:].strip()  # Remove o travessão inicial

            # Caso 1: O autor usou um segundo travessão para separar a narração (ex: "— Olá — disse ele.")
            if "—" in linha_strip:
                partes = linha_strip.split("—", 1)
                blocos.append(_bloco_fala(partes[0].strip()))
                blocos.append(_bloco_narrador(partes[1].strip()))

            # Caso 2: Narração embutida sem travessão (ex: "Morto! morto! dizia consigo.")
            else:
                # Procura pontuação final (! ? .) seguida por espaço e um verbo de elocução
                match = re.search(
                    r"([.!?]+)\s+(" + VERBOS_ELOCUCAO_REGEX.pattern + r"\b.*)",
                    linha_strip,
                    re.IGNORECASE,
                )

                if match:
                    # Corta a string exatamente onde o verbo começa
                    split_idx = match.start(2)
                    fala = linha_strip[:split_idx].strip()
                    narracao = linha_strip[split_idx:].strip()

                    blocos.append(_bloco_fala(fala))
                    blocos.append(_bloco_narrador(narracao))
                else:
                    # É apenas fala até o fim da linha
                    blocos.append(_bloco_fala(linha_strip))

        # Se a linha for apenas narração
        else:
            blocos.extend(_bloco_narrador(s) for s in dividir_sentencas(linha_strip))

    return blocos


def detectar_modo_dialogo(texto: str) -> str:
    n_aspas = len(re.findall(r'"[^"]{3,}"', texto))
    n_travessao = len(re.findall(r"(?m)^\s*—", texto))
    return "travessao" if n_travessao > n_aspas else "aspas"


def parsear_texto(texto: str, modo: str = "auto") -> list:
    if modo == "auto":
        modo = detectar_modo_dialogo(texto)
    return _parsear_travessao(texto) if modo == "travessao" else _parsear_aspas(texto)


def selecionar_atribuidor(blocos: list, i: int) -> str:
    """Escolhe o trecho de narração (antes ou depois da fala) mais provável
    de conter o verbo de elocução, para depois identificar quem fala."""
    antes = (
        blocos[i - 1]["texto"] if i > 0 and blocos[i - 1]["tipo"] == "narrador" else ""
    )
    depois = (
        blocos[i + 1]["texto"]
        if i + 1 < len(blocos) and blocos[i + 1]["tipo"] == "narrador"
        else ""
    )

    tem_verbo_depois = bool(VERBOS_ELOCUCAO_REGEX.search(depois))
    tem_verbo_antes = bool(VERBOS_ELOCUCAO_REGEX.search(antes))

    if tem_verbo_depois:
        return depois
    if antes.strip().startswith(",") and len(antes.strip()) < 60 and tem_verbo_antes:
        return antes
    if tem_verbo_antes:
        return antes.rstrip(":").strip()
    return ""
