from src.core.pdf_processor import extrair_texto_pdf
from src.pipeline import dry_run
from src.services.tts_service import processar_pipeline

caminho_do_meu_pdf = "data/inputs/capitulo_teste.pdf" # Coloque um PDF nessa pasta

# 1. Extrair
texto = extrair_texto_pdf(caminho_do_meu_pdf)

# 2. Processar
blocos, catalogo = processar_pipeline(texto, modo_dialogo="auto")

# 3. Testar
dry_run(blocos, catalogo)

# 4. Gerar (Descomente quando quiser gastar tokens)
# gerar_audiobook(blocos, catalogo, "data/outputs/audiobook.mp3")