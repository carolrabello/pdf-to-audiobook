"""
Ponto de entrada. Uso:
    python main.py data/inputs/brasCubasteste.pdf            -> dry run (não gasta chamada de API)
    python main.py data/inputs/brasCubasteste.pdf --gerar     -> gera o MP3 de fato
"""
import argparse

from pipeline import processar_pipeline
from src.services.tts_service import dry_run, gerar_audiobook


def main():
    parser = argparse.ArgumentParser(description="Gerador de audiobooks com múltiplas vozes (TCC)")
    parser.add_argument("pdf", help="Caminho do PDF de entrada, ex.: data/inputs/capitulo.pdf")
    parser.add_argument("--gerar", action="store_true", help="Gera o MP3 (gasta chamadas ao Gemini TTS)")
    args = parser.parse_args()

    blocos, catalogo = processar_pipeline(args.pdf)

    if args.gerar:
        arquivo = gerar_audiobook(blocos, catalogo)
        print(f"\nAudiobook gerado em: {arquivo}")
    else:
        dry_run(blocos, catalogo)


if __name__ == "__main__":
    main()
