"""
Ponto de entrada. Uso:
    python main.py data/inputs/livro.pdf            -> dry run (não gasta chamada de API)
    python main.py data/inputs/livro.pdf --gerar     -> gera o MP3 de fato
    python main.py data/inputs/livro.pdf x            -> recorta o capítulo x (pode ser "titulo capitulo", "1" ou "I") do livro inteiro
"""
import argparse
import time
from pipeline import processar_pipeline
from src.core.pdf_processor import nome_da_saida
from src.services.tts_service import dry_run, gerar_audiobook


def main():
    parser = argparse.ArgumentParser(description="Gerador de audiobooks com múltiplas vozes (TCC)")
    parser.add_argument("pdf", help="Caminho do PDF de entrada, ex.: data/inputs/capitulo.pdf")
    parser.add_argument("capitulo", nargs="?", help="Capítulo a recortar de um livro completo, ex.: VIII ou 1 (opcional)")
    parser.add_argument("--gerar", action="store_true", help="Gera o MP3 (gasta chamadas ao Gemini TTS)")
    args = parser.parse_args()

    inicio = time.perf_counter()
    blocos, catalogo = processar_pipeline(args.pdf, args.capitulo)
    t_pln = time.perf_counter() - inicio
    print(f"Análise de PLN concluída em {t_pln:.1f} s")

    if args.gerar:
        arquivo = gerar_audiobook(blocos, catalogo, nome_da_saida(args.pdf, args.capitulo))
        t_total = time.perf_counter() - inicio
        print(f"\nAudiobook gerado em: {arquivo}")
        print(f"Tempo total: {t_total / 60:.1f} min (PLN: {t_pln:.1f} s | síntese e montagem: {(t_total - t_pln) / 60:.1f} min)")
    else:
        dry_run(blocos, catalogo)


if __name__ == "__main__":
    main()