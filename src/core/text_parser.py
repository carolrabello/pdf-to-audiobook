"""
Responsabilidade única: quebrar o texto bruto em blocos de "narrador" e
"fala", suportando aspas (retas ou tipográficas) e travessão - inclusive
quando o mesmo livro mistura os dois estilos (ex.: travessão pra fala,
aspas pro pensamento, como em Alice no País das Maravilhas).
"""
import re

from config import VERBOS_ELOCUCAO_LEMMAS, VERBOS_ELOCUCAO_EXTRA_LEMMAS, FORMAS_VERBAIS_IRREGULARES, MODELO_SPACY

_LEMAS_DE_FALA = VERBOS_ELOCUCAO_LEMMAS | VERBOS_ELOCUCAO_EXTRA_LEMMAS

# O parser usa o spaCy só para reconhecer o verbo de fala pelo LEMA (qualquer pessoa ou
# tempo: "disse", "perguntei", "respondeu"), com a mesma lista de lemas do nlp_analyzer.
# Assim a lista fica em um lugar só (config.py) e não em formas verbais soltas.
_nlp = None


def definir_modelo(nlp) -> None:
    """Reaproveita o modelo já carregado pelo pipeline (evita carregar o spaCy duas vezes)."""
    global _nlp
    _nlp = nlp


def _modelo():
    global _nlp
    if _nlp is None:
        import spacy
        _nlp = spacy.load(MODELO_SPACY)
    return _nlp


def _sem_trema(palavra: str) -> str:
    return palavra.replace("ü", "u")


def _formas_do_preterito(lema: str) -> set:
    """Gera, pela conjugação regular, o pretérito (1ª e 3ª pessoa) e o imperfeito de um lema
    da lista ("perguntar" -> perguntei, perguntou, perguntava). O lematizador do spaCy erra
    várias formas literárias ("retorqui", "redargüiu"), por isso o parser também usa estas."""
    lema = _sem_trema(lema)
    if lema.endswith("ar"):
        r = lema[:-2]
        pri = r[:-1] + "qu" if r.endswith("c") else r[:-1] + "gu" if r.endswith("g") else r[:-1] + "c" if r.endswith("ç") else r
        return {pri + "ei", r + "ou", r + "ava"}
    if lema.endswith("er"):
        r = lema[:-2]
        return {r + "i", r + "eu", r + "ia"}
    if lema.endswith("ir"):
        r = lema[:-2]
        return {r + "i", r + "iu", r + "ia"}
    return set()


_FORMAS_DE_FALA = ({f for lema in _LEMAS_DE_FALA for f in _formas_do_preterito(lema)}
                   | FORMAS_VERBAIS_IRREGULARES)


def _verbo_de_fala(tok) -> bool:
    """Verbo de fala: pelo lema do spaCy ou, quando o spaCy erra a classe ou o lema,
    pela forma conjugada gerada a partir dos lemas ("Interrompeu-me" -> "interrompeu")."""
    # O presente fica de fora ("Fala, homem!" é fala, não etiqueta); só o presente de "dizer" vale.
    if (tok.pos_ in ("VERB", "AUX") and tok.lemma_.lower() in _LEMAS_DE_FALA
            and "Pres" not in tok.morph.get("Tense")):
        return True
    palavra = _sem_trema(tok.text.lower().split("-")[0])
    if palavra in ("diz", "dizes", "dizem") and "-" in tok.text:
        return False                                      # "diz-lhe" é imperativo, não etiqueta
    return palavra in _FORMAS_DE_FALA


def _tem_verbo_de_fala(texto: str) -> bool:
    return any(_verbo_de_fala(t) for t in _modelo()(texto))


def _primeira_pessoa(tok) -> bool:
    palavra = _sem_trema(tok.text.lower())
    return "1" in tok.morph.get("Person") or palavra.endswith(("ei", "i"))


def _achar_etiqueta(texto: str):
    """Procura o ponto em que a fala termina e a etiqueta começa: um verbo de fala logo
    depois de pontuação final ("— Que pena! disse o Papagaio.") ou de vírgula quando
    há algo depois do verbo ("— Nada, respondeu o Papagaio."). Devolve (posição do verbo,
    verbo em 1ª pessoa) ou None. O imperativo ("Fala, homem!") não conta como etiqueta, e um
    verbo em 1ª pessoa só conta quando vem seguido de "eu" ou de pontuação ("perguntei eu,",
    "respondi;"), para não cortar falas como "Pedi à Leocádia que...". """
    doc = _modelo()(texto)
    for i, t in enumerate(doc):
        if i == 0 or not _verbo_de_fala(t) or "Imp" in t.morph.get("Mood"):
            continue
        ant = doc[i - 1].text.strip()
        prox = doc[i + 1] if i + 1 < len(doc) else None
        primeira = _primeira_pessoa(t)
        if primeira and "-" not in t.text and not (prox is not None and (prox.is_punct or prox.text.lower() == "eu")):
            continue
        if ant and ant[-1] in ".!?…":
            return t.idx, primeira
        if ant == "," and prox is not None and (not prox.is_punct or primeira):
            return t.idx, primeira
    return None


# Palavras que indicam que a fala continua depois de uma etiqueta ("— Pensando bem, disse o segundo, o verdadeiro...")
# Aceita aspas retas (" ") e tipográficas (“ ”) - PDFs de e-book usam as duas.
_PADRAO_ASPAS = re.compile(r'["“]([^"”]+)["”]')

_ENTRE_TRAVESSOES = re.compile(r"\s+—\s+")


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
    return {"tipo": "narrador", "texto": texto.strip(), "personagem": "Narrador", "emocao": None}


def _blocos_narrador(texto: str, etiqueta: bool = False) -> list:
    """'etiqueta' = narração colada à fala, na mesma linha ("— Fala — disse o velho."):
    é ela que diz quem fala, seja qual for o verbo."""
    blocos = [_bloco_narrador(s) for s in dividir_sentencas(texto)]
    if etiqueta:
        for b in blocos:
            b["e_etiqueta"] = True
    return blocos


# Depois de uma etiqueta entre vírgulas ("— Pensando bem, disse o segundo, o verdadeiro é..."),
# estas palavras indicam que a fala continua.
_INICIO_DE_FALA = {"o", "os", "as", "um", "uma", "eu", "tu", "você", "nós", "vocês", "é", "são",
                   "isso", "isto", "aquilo", "meu", "minha", "seu", "sua"}


def _dividir_fala_e_narracao_embutida(texto: str) -> list:
    """Quando a narração vem colada à fala sem um segundo travessão
    (ex.: 'Morto! morto! dizia consigo.' ou 'Nada, respondeu o Papagaio.'), localiza
    onde a fala termina (pontuação final ou vírgula) e o verbo de elocução começa, e
    separa ali. Se a etiqueta termina em vírgula e a frase segue como fala
    ('Pensando bem, disse o segundo, o verdadeiro é...'), a continuação volta a ser fala."""
    achado = _achar_etiqueta(texto)
    if not achado:
        return [_bloco_fala(texto)]

    corte, verbo_1p = achado
    resto = texto[corte:]
    fim_etiqueta = re.search(r"[,.!?;]", resto)
    if fim_etiqueta:
        delim = resto[fim_etiqueta.start()]
        seguinte = resto[fim_etiqueta.end():].split()
        prox = seguinte[0].lower().strip("¿¡") if seguinte else ""
        # "a" é artigo ("disse eu, a coisa é...") ou preposição ("disse o Rato, a tremer"):
        # só continua se a palavra seguinte não for um infinitivo (termina em "r").
        artigo = (prox == "a" and len(seguinte) > 1
                  and not seguinte[1].lower().rstrip(",.;!?").endswith("r")
                  and seguinte[1].lower().strip(",") not in ("quem", "qual", "quais"))
        primeira_pessoa = delim == ";" and verbo_1p
        if (delim == "," and (prox in _INICIO_DE_FALA or artigo)) or primeira_pessoa:
            return ([_bloco_fala(texto[:corte])]
                    + _blocos_narrador(resto[:fim_etiqueta.end()], etiqueta=True)
                    + [_bloco_fala(resto[fim_etiqueta.end():])])
    return [_bloco_fala(texto[:corte])] + _blocos_narrador(resto, etiqueta=True)


import re # Certifique-se de que o import re está no topo do arquivo text_parser.py

def _parsear_travessao_fragmento(fragmento: str) -> list:
    """Processa travessão num trecho que já NÃO contém diálogo entre aspas
    (isso foi separado antes, em _parsear_paragrafo). Mantém 'em_fala'
    entre linhas: uma fala pode continuar por mais de uma frase sem repetir
    o travessão - só o PDF quebrou a linha no meio da mesma fala."""
    blocos = []
    em_fala = False

    for linha in fragmento.replace("--", "—").replace("\u2013", "—").split("\n"):
        linha = linha.strip()
        
        # --- CORREÇÃO: Normaliza o hífen simples para travessão ---
        # 1. Transforma hífen (ou meia-risca) no começo da linha em travessão longo
        linha = re.sub(r"^[-–]\s*", "— ", linha)
        # 2. Transforma hífen solto no meio da frase (cercado por espaços) em travessão longo
        linha = re.sub(r"\s+[-–]\s+", " — ", linha)
        # ----------------------------------------------------------

        if not linha:
            em_fala = False  # linha em branco = novo parágrafo, reseta
            continue

        if linha.startswith("@CABECALHO@"):
            bloco = _bloco_narrador(linha.replace("@CABECALHO@", ""))
            bloco["e_cabecalho"] = True
            blocos.append(bloco)
            em_fala = False
            continue

        if linha.startswith("—"):
            partes = _ENTRE_TRAVESSOES.split(linha[1:].strip())
            # Aposto entre travessões dentro da fala, sem verbo de fala:
            # "— A coisa vale a pena, — talvez monótona — mas vale a pena."
            if (len(partes) >= 3 and partes[0].rstrip().endswith(",") and len(partes[1].split()) <= 4
                    and not re.search(r"[A-ZÁÉÍÓÚÂÊÔÃÕ.!?,;:]", partes[1])
                    and not _tem_verbo_de_fala(partes[1])):
                partes = [partes[0].rstrip(", ") + ", " + partes[1] + ", " + partes[2]] + partes[3:]

            if len(partes) == 1:
                # Sem segundo travessão - pode ter narração colada
                novos = _dividir_fala_e_narracao_embutida(partes[0])
                em_fala = novos[-1]["tipo"] == "fala"
            else:
                primeiros = _dividir_fala_e_narracao_embutida(partes[0])
                if sum(1 for x in primeiros if x["tipo"] == "narrador") > 1:
                    primeiros = [_bloco_fala(partes[0])]  # etiqueta + mais frases: ambíguo, mantém como estava
                novos = primeiros + _blocos_narrador(partes[1], etiqueta=True)
                em_fala = len(partes) >= 3  # um 2º travessão reabre a fala
                if em_fala:
                    novos.append(_bloco_fala(" — ".join(partes[2:])))
            blocos.extend(novos)
            continue

        if em_fala:
            # Continuação da mesma fala. Pode terminar com narração colada
            # ou com um travessão explícito no meio.
            if "—" in linha:
                partes = _ENTRE_TRAVESSOES.split(linha)
                blocos.append(_bloco_fala(partes[0]))
                if len(partes) >= 2:
                    blocos.extend(_blocos_narrador(" — ".join(partes[1:]), etiqueta=True))
                    em_fala = False
            else:
                novos = _dividir_fala_e_narracao_embutida(linha)
                blocos.extend(novos)
                em_fala = novos[-1]["tipo"] == "fala"
            continue

        blocos.extend(_blocos_narrador(re.sub(r"\s+[—\-]\s+", ", ", linha)))

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
        entre_aspas = m.group(1)
        palavras = entre_aspas.split()
        if (len(palavras) <= 3 and not re.search(r"[.!?…]", entre_aspas)
                and (len(palavras) == 1 or entre_aspas.strip()[:1].islower())):
            blocos.append(_bloco_narrador(entre_aspas))  # palavra citada ("faz-de-conta"), não fala
        else:
            blocos.append(_bloco_fala(entre_aspas))
        pos = m.end()

    resto = paragrafo[pos:]
    if resto.strip():
        blocos.extend(_parsear_travessao_fragmento(resto))
    return blocos


def parsear_texto(texto: str, nlp=None) -> list:
    if nlp is not None:
        definir_modelo(nlp)
    blocos = []
    for paragrafo in texto.split("\n\n"):
        if paragrafo.strip():
            blocos.extend(_parsear_paragrafo(paragrafo))
    return blocos


def vizinhos_narracao(blocos: list, i: int) -> tuple:
    """Índices da narração imediatamente antes e depois da fala 'i'
    (None quando o vizinho não existe ou é outra fala)."""
    def _se_narracao(j):
        return j if 0 <= j < len(blocos) and blocos[j]["tipo"] == "narrador" else None
    return _se_narracao(i - 1), _se_narracao(i + 1)


def selecionar_atribuidor(blocos: list, antes, depois):
    """Escolhe qual narração vizinha (antes ou depois da fala) diz quem fala: uma
    etiqueta de diálogo ou uma narração com verbo de elocução. Devolve o índice do
    bloco ou None."""
    for j in (depois, antes):  # prefere o que vem depois: "— Fala — disse Alice."
        if j is not None and (blocos[j].get("e_etiqueta") or _tem_verbo_de_fala(blocos[j]["texto"])):
            return j
    return None