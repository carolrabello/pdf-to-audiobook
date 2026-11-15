"""
Responsabilidade única: transformar um PDF em texto limpo.
Recebe o caminho local do arquivo (ex.: data/inputs/capitulo.pdf).
"""
import re
import unicodedata
from pathlib import Path

import fitz  # PyMuPDF

_FIM_DE_FRASE = re.compile(r'[.!?:;"”]\s*$')
_INICIO_CABECALHO = re.compile(r"^cap[íi]tulo\b", re.IGNORECASE)


# Bloco que contém só o número do capítulo: "VIII" ou "CAPÍTULO VIII" / "Capítulo 8".
# Número solto ("8") não vale: seria confundido com o número da página.
_NUMERO_CAPITULO = re.compile(r"^(?:cap[íi]tulo\s+(\w+)|([IVXLC]+))$", re.IGNORECASE)
_NUMERO_DE_PAGINA = re.compile(r"^\d+$")
_MARCADOR = re.compile(r"^[•·\s]+$")           # "• • •" que alguns livros põem logo abaixo do título
_FIM_DO_LIVRO = re.compile(r"^(Sobre esta edi[çc][ãa]o|P[áa]gina do livro|Milhares de outros livros)", re.IGNORECASE)


def _normalizar(texto: str) -> str:
    """Compara títulos sem se importar com acento, maiúscula ou espaço."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\W+", " ", sem_acento).strip().lower()


def nome_da_saida(caminho_pdf: str, capitulo: str | None = None) -> str:
    """Nome da pasta de saída: 'o-cortico' (livro/capítulo inteiro) ou 'o-cortico-cap-VIII'."""
    nome = Path(caminho_pdf).stem
    if not capitulo:
        return nome
    cap = capitulo.strip().upper() if len(capitulo.strip()) <= 6 else _normalizar(capitulo).replace(" ", "-")[:40]
    return f"{nome}-cap-{cap}"


def extrair_texto_pdf(caminho_pdf: str, capitulo: str | None = None) -> str:
    """Sem 'capitulo', lê o PDF inteiro (capítulo já isolado). Com 'capitulo' (como aparece
    no livro, ex.: "VIII"), recorta só esse capítulo de um livro completo - sem copiar e
    limpar à mão."""
    if not Path(caminho_pdf).exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_pdf}")

    with fitz.open(caminho_pdf) as doc:
        if capitulo:
            paginas = [_texto_do_capitulo(doc, capitulo)]
        else:
            paginas = [_texto_da_pagina(p) for p in doc]
    paginas = [p for p in paginas if p.strip()]

    if not paginas:
        raise ValueError("Nenhum texto extraído. O PDF pode ser escaneado (sem OCR).")

    texto = "\n".join(paginas)
    texto = texto.replace("\xa0", " ")                          # espaço "não separável" vira espaço comum
    texto = re.sub(r"[-\u2010\u00ad]\n([a-záéíóúâêôãõç])", r"\1", texto)  # remove hifenização de fim de linha
    texto = re.sub(r"\n{3,}", "\n\n", texto)                # colapsa linhas em branco excessivas
    return _juntar_linhas_quebradas(texto)


def _blocos_da_pagina(pagina) -> list:
    """Parágrafos da página, sem o número da página. Alguns PDFs juntam vários parágrafos
    num único bloco e só marcam o início de cada um com o recuo da primeira linha (ex.: as
    falas de um diálogo). Por isso o bloco é quebrado onde uma linha começa mais à direita
    que a margem do texto."""
    linhas_por_bloco = []
    for b in pagina.get_text("dict", sort=True)["blocks"]:
        if b["type"] != 0:
            continue
        linhas = [("".join(s["text"] for s in l["spans"]).strip(), l["bbox"][0]) for l in b["lines"]]
        linhas = [(t, x) for t, x in linhas if t]
        if linhas:
            linhas_por_bloco.append(linhas)

    # Margem do texto = posição mais comum do início das linhas na página.
    inicios = [round(x) for linhas in linhas_por_bloco for _, x in linhas]
    margem = max(set(inicios), key=inicios.count) if inicios else 0

    blocos = []
    for linhas in linhas_por_bloco:
        grupos = []
        for texto, x in linhas:
            recuada = margem + 5 < x < margem + 40
            if grupos and not recuada:
                grupos[-1].append(texto)
            else:
                grupos.append([texto])
        blocos.extend("\n".join(g) for g in grupos)
    return [b for b in blocos if not _NUMERO_DE_PAGINA.match(b)]  # descarta o número da página


def _unir_blocos(blocos: list) -> str:
    """Cada bloco de texto do PDF é um parágrafo: entre parágrafos entra uma linha em
    branco (é ela que encerra uma fala no parser). Se o bloco anterior não terminou a
    frase, o corte é só de layout e vira uma quebra simples, que a junção de linhas resolve."""
    texto = ""
    for bloco in blocos:
        separador = "" if not texto else ("\n\n" if _FIM_DE_FRASE.search(texto) else "\n")
        texto += separador + bloco
    return texto


def _texto_da_pagina(pagina) -> str:
    return _unir_blocos(_blocos_da_pagina(pagina))


def _blocos_do_livro(doc) -> list:
    """Todos os blocos do PDF, sem os cabeçalhos que se repetem em quase toda página
    (ex.: "Monteiro Lobato / O Saci")."""
    por_pagina = [_blocos_da_pagina(p) for p in doc]
    contagem = {}
    for blocos in por_pagina:
        for b in set(blocos):
            contagem[b] = contagem.get(b, 0) + 1
    repetidos = {b for b, n in contagem.items() if n > len(doc) * 0.3 and not _MARCADOR.match(b)}
    return [b for blocos in por_pagina for b in blocos if b not in repetidos]


def _texto_do_capitulo(doc, capitulo: str) -> str:
    """Acha o início do capítulo pelo número ("VIII" ou "CAPÍTULO VIII") ou, nos livros em que o
    título vem seguido de "• • •", pelo título (ex.: "Viagem à toca dos coelhos"). Termina onde
    começa o próximo capítulo."""
    alvo = _normalizar(capitulo)
    blocos_livro = _blocos_do_livro(doc)
    blocos, dentro, titulo = [], False, ""
    titulo_depois_do_numero = ""
    k = 0
    while k < len(blocos_livro):
        bloco = blocos_livro[k]
        numero = _NUMERO_CAPITULO.match(bloco)
        tem_marcador = k + 1 < len(blocos_livro) and _MARCADOR.match(blocos_livro[k + 1])
        if dentro and not blocos and not titulo and tem_marcador and not numero:
            titulo_depois_do_numero = bloco              # "Capítulo 6" / título / "• • •"
            k += 2
            continue
        if numero or tem_marcador:                       # início de um capítulo
            rotulo = _normalizar((numero.group(1) or numero.group(2)) if numero else bloco)
            if dentro:
                break
            if rotulo == alvo:
                dentro = True
                titulo = bloco if tem_marcador else ""
            k += 2 if tem_marcador else 1
            continue
        if dentro:
            if _FIM_DO_LIVRO.match(bloco):
                break
            blocos.append(bloco)
        k += 1
    if not dentro:
        raise ValueError(f"Capítulo '{capitulo}' não encontrado no PDF.")
    if titulo_depois_do_numero:
        titulo = titulo_depois_do_numero
        cabecalho = f"CAPÍTULO {capitulo.strip().upper()}\n{titulo}"
    elif not titulo:
        # Título do capítulo (se houver, ex.: "A cartinha do Polegar") fica junto do cabeçalho,
        # separado do 1º parágrafo por linha em branco.
        if blocos and len(blocos[0].split()) <= 8 and not _FIM_DE_FRASE.search(blocos[0]):
            titulo = blocos.pop(0)
        cabecalho = f"CAPÍTULO {capitulo.strip().upper()}" + (f"\n{titulo}" if titulo else "")
    else:
        cabecalho = f"CAPÍTULO {titulo}"
    return cabecalho + "\n\n" + _unir_blocos(blocos)


def _juntar_linhas_quebradas(texto: str) -> str:
    """
    PDFs quebram linha pelo layout visual, não pela gramática. Isso faz uma
    única frase virar 2 "sentenças" para o parser. Regra: se uma linha não
    termina em pontuação final, ela continua na próxima -> junta.

    Exceção: títulos de capítulo ("CAPÍTULO I", "Óbito do Autor") também não
    terminam em pontuação, mas NÃO são a mesma frase da narração que vem a
    seguir. Por isso o cabeçalho é isolado e marcado com "@CABECALHO@", para
    ser pulado na extração de personagens - não importa o que o NER ache dele.
    """
    resultado = []

    for paragrafo in texto.split("\n\n"):
        linhas = [ln.strip() for ln in paragrafo.split("\n") if ln.strip()]
        saida, atual, em_cabecalho = [], "", False

        for linha in linhas:
            if _INICIO_CABECALHO.match(linha):
                if atual:
                    saida.append(atual)
                atual, em_cabecalho = "@CABECALHO@ " + linha, True
                continue

            if em_cabecalho and len(linha.split()) <= 5:
                atual += " " + linha  # ex.: "Óbito do Autor" continua o título
                continue
            em_cabecalho = False

            if not atual:
                atual = linha
            elif _FIM_DE_FRASE.search(atual):
                saida.append(atual)
                atual = linha
            else:
                atual += " " + linha

        if atual:
            saida.append(atual)
        resultado.append("\n".join(saida))

    return "\n\n".join(resultado)