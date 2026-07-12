"""
Responsabilidade única: transformar um PDF em texto limpo.
Antes: fazer_upload_pdf() usava google.colab.files (só funciona no Colab).
Agora: recebe o caminho local do arquivo (ex.: data/inputs/capitulo.pdf).
"""
import re
from pathlib import Path
import fitz  # PyMuPDF


def extrair_texto_pdf(caminho_pdf: str) -> str:
    caminho = Path(caminho_pdf)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_pdf}")

    doc = fitz.open(caminho_pdf)
    paginas = []
    for pagina in doc:
        texto_pagina = pagina.get_text("text")
        if isinstance(texto_pagina, str) and texto_pagina.strip():
            paginas.append(texto_pagina)
    doc.close()

    if not paginas:
        raise ValueError("Nenhum texto extraído. O PDF pode ser escaneado (sem OCR).")

    texto = "\n".join(paginas)
    texto = re.sub(r"-\n([a-záéíóúâêôãõ])", r"\1", texto)  # remove hifenização de fim de linha
    texto = re.sub(r"\n{3,}", "\n\n", texto)                # colapsa linhas em branco excessivas
    return _juntar_linhas_quebradas(texto)


def _juntar_linhas_quebradas(texto: str) -> str:
    """
    PDFs quebram linha pelo layout visual, não pela gramática. Isso faz uma
    única frase virar 2 "sentenças" para o nosso parser. Regra: se uma
    linha não termina em pontuação final, ela continua na próxima -> junta.

    Exceção: títulos de capítulo ("CAPÍTULO I", "Óbito do Autor") também
    não terminam em pontuação, mas NÃO são a mesma frase da narração que
    vem a seguir. Por isso, ao detectar o início de um cabeçalho, ele é
    isolado e marcado com "@CABECALHO@", pra ser pulado mais adiante na
    extração de personagens - não importa o que o NER ache dele.
    """
    paragrafos = texto.split("\n\n")
    resultado = []

    for paragrafo in paragrafos:
        linhas = [l.strip() for l in paragrafo.split("\n") if l.strip()]  # noqa: E741
        saida, atual, em_cabecalho = [], "", False

        for linha in linhas:
            inicia_cabecalho = bool(re.match(r'^cap[íi]tulo\b', linha, re.IGNORECASE))
            linha_curta = len(linha.split()) <= 5

            if inicia_cabecalho:
                if atual:
                    saida.append(atual)
                atual = "@CABECALHO@ " + linha
                em_cabecalho = True
                continue

            if em_cabecalho and linha_curta:
                atual += " " + linha  # ex.: "Óbito do Autor" continua o título
                continue
            em_cabecalho = False

            if not atual:
                atual = linha
            elif re.search(r'[\.\!\?\:\;"”]\s*$', atual):
                saida.append(atual)
                atual = linha
            else:
                atual += " " + linha

        if atual:
            saida.append(atual)
        resultado.append("\n".join(saida))

    return "\n\n".join(resultado)