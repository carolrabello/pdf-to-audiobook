import fitz
import re
from pathlib import Path

def extrair_texto_pdf(caminho_pdf: str) -> str:
    """Extrai todo o texto do PDF fornecido."""
    caminho = Path(caminho_pdf)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_pdf}")

    doc   = fitz.open(caminho_pdf)
    total = len(doc)

    print(f" Lendo PDF: '{caminho.name}' — Extraindo todas as {total} página(s)...")

    blocos_texto = []
    for num in range(total):
        texto_pag = doc[num].get_text("text")
        if texto_pag.strip():
            blocos_texto.append(texto_pag)
    doc.close()

    if not blocos_texto:
        raise ValueError("Nenhum texto extraído. O PDF pode ser escaneado.")

    texto = "\n".join(blocos_texto)
    # Limpa hifenizações de quebra de linha
    texto = re.sub(r"-\n([a-záéíóúâêôãõ])", r"\1", texto)
    # Colapsa linhas em branco excessivas
    texto = re.sub(r"\n{3,}", "\n\n", texto)

    print(f" Extração concluída: {len(texto)} caracteres.")
    return texto