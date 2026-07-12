"""
Responsabilidade única: quebrar o texto bruto em blocos de "narrador" e
"fala", suportando aspas (retas ou tipográficas) e travessão - inclusive
quando o mesmo livro mistura os dois estilos (ex.: travessão pra fala,
aspas pro pensamento, como em Alice no País das Maravilhas).
"""
import re

VERBOS_ELOCUCAO_REGEX = re.compile(
    r"\b(disse|respondeu|perguntou|continuou|retrucou|gritou|afirmou|replicou|"
    r"discordou|retomou|chamou|exclamou|murmurou|sussurrou|dirigiu-se|falou|"
    r"começou|acrescentou|declarou|confessou|explicou|exigiu|dizia|diz\w*)\b",
    re.IGNORECASE,
)

# Aceita aspas retas (" ") e tipográficas (“ ”) - PDFs de e-book usam as duas.
_PADRAO_ASPAS = re.compile(r'["“]([^"”]+)["”]')


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
    return {"tipo": "narrador", "texto": texto.strip(), "personagem": "Narrador", "emocao": "neutral"}


def _dividir_fala_e_narracao_embutida(texto: str) -> list:
    """Quando a narração vem colada à fala sem um segundo travessão
    (ex.: 'Morto! morto! dizia consigo.'), localiza onde a fala termina
    (pontuação final) e o verbo de elocução começa, e separa ali."""
    match = re.search(
        r"([.!?]+)\s+(" + VERBOS_ELOCUCAO_REGEX.pattern + r"\b.*)",
        texto, re.IGNORECASE,
    )
    if not match:
        return [_bloco_fala(texto)]

    corte = match.start(2)
    fala = texto[:corte].strip()
    narracao = texto[corte:].strip()

    blocos = [_bloco_fala(fala)]
    blocos.extend(_bloco_narrador(s) for s in dividir_sentencas(narracao))
    return blocos


def _parsear_travessao_fragmento(fragmento: str) -> list:
    """Processa travessão num trecho que já NÃO contém diálogo entre aspas
    (isso foi separado antes, em _parsear_paragrafo). Mantém 'em_fala'
    entre linhas: uma fala pode continuar por mais de uma frase sem repetir
    o travessão - só o PDF quebrou a linha no meio da mesma fala."""
    blocos = []
    em_fala = False

    for linha in fragmento.replace("--", "—").replace("\u2013", "—").split("\n"):
        linha_strip = linha.strip()
        if not linha_strip:
            em_fala = False  # linha em branco = novo parágrafo, reseta
            continue

        if linha_strip.startswith("@CABECALHO@"):
            texto_limpo = linha_strip.replace("@CABECALHO@", "").strip()
            bloco = _bloco_narrador(texto_limpo)
            bloco["e_cabecalho"] = True
            blocos.append(bloco)
            em_fala = False
            continue

        if linha_strip.startswith("—"):
            conteudo = linha_strip[1:].strip()
            partes = re.split(r"\s+—\s+", conteudo)

            if len(partes) == 1:
                # Sem segundo travessão - pode ter narração colada
                # (ex.: "Morto! morto! dizia consigo.")
                novos = _dividir_fala_e_narracao_embutida(partes[0])
                blocos.extend(novos)
                em_fala = novos[-1]["tipo"] == "fala"
                continue

            blocos.append(_bloco_fala(partes[0]))
            em_fala = True
            if len(partes) >= 2:
                blocos.extend(_bloco_narrador(s) for s in dividir_sentencas(partes[1]))
                em_fala = False
            if len(partes) >= 3:
                blocos.append(_bloco_fala(" — ".join(partes[2:])))
                em_fala = True
            continue

        if em_fala:
            # Continuação da mesma fala. Pode terminar com narração colada
            # (mesma regra acima) ou com um travessão explícito no meio.
            if "—" in linha_strip:
                partes = re.split(r"\s+—\s+", linha_strip)
                blocos.append(_bloco_fala(partes[0]))
                if len(partes) >= 2:
                    blocos.extend(_bloco_narrador(s) for s in dividir_sentencas(" — ".join(partes[1:])))
                    em_fala = False
            else:
                novos = _dividir_fala_e_narracao_embutida(linha_strip)
                blocos.extend(novos)
                em_fala = novos[-1]["tipo"] == "fala"
            continue

        linha_limpa = re.sub(r"\s+[—\-]\s+", ", ", linha_strip)
        blocos.extend(_bloco_narrador(s) for s in dividir_sentencas(linha_limpa))

    return blocos


def _parsear_paragrafo(paragrafo: str) -> list:
    """Separa primeiro o que está entre aspas (fala ou pensamento); o resto
    do parágrafo passa pela lógica de travessão. Assim, o mesmo parágrafo
    pode ter os dois estilos ao mesmo tempo."""
    blocos = []
    pos = 0
    for m in _PADRAO_ASPAS.finditer(paragrafo):
        antes = paragrafo[pos:m.start()]
        if antes.strip():
            blocos.extend(_parsear_travessao_fragmento(antes))
        blocos.append(_bloco_fala(m.group(1)))
        pos = m.end()

    resto = paragrafo[pos:]
    if resto.strip():
        blocos.extend(_parsear_travessao_fragmento(resto))
    return blocos


def parsear_texto(texto: str, modo: str = "auto") -> list:
    """'modo' ficou só por compatibilidade - hoje aspas e travessão são
    sempre processados juntos, já que um mesmo livro pode misturar os dois
    estilos."""
    blocos = []
    for paragrafo in texto.split("\n\n"):
        if paragrafo.strip():
            blocos.extend(_parsear_paragrafo(paragrafo))
    return blocos


def selecionar_atribuidor(blocos: list, i: int) -> str:
    """Escolhe o trecho de narração (antes ou depois da fala) mais provável
    de conter o verbo de elocução, para depois identificar quem fala."""
    antes = blocos[i - 1]["texto"] if i > 0 and blocos[i - 1]["tipo"] == "narrador" else ""
    depois = blocos[i + 1]["texto"] if i + 1 < len(blocos) and blocos[i + 1]["tipo"] == "narrador" else ""

    tem_verbo_depois = bool(VERBOS_ELOCUCAO_REGEX.search(depois))
    tem_verbo_antes = bool(VERBOS_ELOCUCAO_REGEX.search(antes))

    if tem_verbo_depois:
        return depois
    if antes.strip().startswith(",") and len(antes.strip()) < 60 and tem_verbo_antes:
        return antes
    if tem_verbo_antes:
        return antes.rstrip(":").strip()
    return ""