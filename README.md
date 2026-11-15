# PDF para audiolivro com múltiplas vozes

Código do TG-II *Processamento de Linguagem Natural aplicado à atribuição de falantes e síntese de voz em obras literárias* (FATEC Campinas, 2026).

O sistema recebe um capítulo em PDF, identifica quem fala em cada trecho com PLN (spaCy) e gera um audiolivro em MP3 com uma voz para o narrador e uma voz para cada personagem, usando o Gemini TTS.

## Requisitos

- Python 3.11
- FFmpeg instalado no sistema (usado pelo pydub para montar o MP3)
- Projeto no Google Cloud com a GCP ativada

```
pip install -r requirements.txt
gcloud auth application-default login
```

Em `config.py`, troque `GCP_PROJECT_ID` pelo seu projeto. O modelo de voz (`MODELO_TTS`) também é escolhido ali: `gemini-2.5-flash-tts` ou `gemini-2.5-pro-tts`.

## Uso

```
python main.py data/inputs/alice-no-pais-das-maravilhas.pdf "Viagem à toca dos coelhos"           # simulação, sem chamar a API
python main.py data/inputs/alice-no-pais-das-maravilhas.pdf "Viagem à toca dos coelhos" --gerar    # gera o MP3
```

O segundo argumento recorta um capítulo de um livro completo. Sem ele, o PDF inteiro é processado. A simulação mostra o que seria enviado ao TTS e não gera custo. O MP3 e os segmentos de áudio ficam em `data/outputs/<capítulo>/`.

## Estrutura

| Arquivo | Função |
|---|---|
| `main.py` | ponto de entrada |
| `pipeline.py` | executa as etapas de PLN em sequência |
| `config.py` | projeto, modelo de voz, vozes e parâmetros |
| `src/core/pdf_processor.py` | extrai e limpa o texto do PDF |
| `src/core/text_parser.py` | separa narração e falas |
| `src/core/nlp_analyzer.py` | atribui cada fala a um personagem (spaCy) |
| `src/core/catalog_manager.py` | catálogo de personagens e escolha da voz |
| `src/services/tts_service.py` | síntese de voz (Gemini TTS) e montagem do MP3 |

## Scripts de avaliação

| Arquivo | Função |
|---|---|
| `avaliar.py` | exporta uma planilha com uma linha por fala, para preencher à mão, e calcula a acurácia da atribuição |
| `gerar_todos.py` | gera (ou simula) os 10 capítulos avaliados e salva o levantamento de tempo e duração em CSV |
| `conferir_rotulos.py` | confere se as planilhas preenchidas ainda correspondem ao que o código atual produz |
| `teste_modelos.py` | testes iniciais de vozes e emoções nos modelos Flash e Pro |

## Dados do trabalho

- `data/inputs/`: PDFs das obras usadas (domínio público)
- `exemplos/audios_teste/`: os 12 trechos (6 em Flash, 6 em Pro) usados no teste de escuta
- `exemplos/resultados/`: respostas do teste de escuta, planilhas de acurácia preenchidas e levantamento de tempo e duração dos capítulos
