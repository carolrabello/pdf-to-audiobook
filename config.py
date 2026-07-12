"""
Configurações centrais do projeto.
Antes: chave vinha de userdata.get() do Colab.
Agora: vem de um arquivo .env local (veja .env.example).
"""
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Vozes do Gemini TTS por gênero. Isso NÃO é um dicionário de personagens,
# é só o catálogo de vozes disponíveis no serviço - precisa continuar fixo.
BANCO_VOZES_GEMINI = {
    "narrador":  "Charon",
    "feminino":  ["Aoede", "Leda", "Zephyr"],
    "masculino": ["Fenrir", "Orus", "Puck"],
    "neutro":    ["Puck", "Fenrir"],
}

# Lemmas (infinitivos) de verbos de elocução.
# Usar lemma em vez de forma conjugada cobre "disse", "dizia", "dirá" etc.
# de uma vez só - é o motivo do seu bug original (TG1 usava forma fixa).
VERBOS_ELOCUCAO_LEMMAS = {
    "dizer", "responder", "perguntar", "continuar", "retrucar", "gritar",
    "afirmar", "replicar", "discordar", "retomar", "chamar", "exclamar",
    "murmurar", "sussurrar", "falar", "começar", "acrescentar", "dirigir",
    "declarar", "confessar", "explicar", "exigir",
}

# Âncoras semânticas para reconhecer substantivos que se referem a PESSOAS
# (ex.: "senhora", "velho", "moça") por similaridade de vetor de palavra,
# em vez de manter uma lista fixa dessas palavras.
ANCORAS_HUMANO = ["pessoa", "homem", "mulher"]
LIMIAR_SIMILARIDADE_HUMANO = 0.55

PALAVRAS_TOM = {"voz", "tom", "olhar", "expressão"}

# Tags oficiais do Gemini TTS (Modo 1 = som não-verbal, Modo 2 = modificador
# de estilo — nenhuma delas é falada pelo modelo, por isso são seguras).
# "ancora" é a palavra em português usada pra comparar por similaridade de
# vetor (mesma técnica do ANCORAS_HUMANO); "tag" é o texto oficial em
# colchetes; "estilo" é um reforço em linguagem natural, recomendado pela
# própria doc do Gemini pra aumentar a confiabilidade da tag.
CATEGORIAS_EMOCAO = {
    "grito":      {"ancora": "gritar",    "tag": "[shouting]",       "estilo": "Diga a fala a seguir gritando"},
    "sussurro":   {"ancora": "sussurrar", "tag": "[whispering]",     "estilo": "Diga a fala a seguir sussurrando"},
    "velocidade": {"ancora": "rápido",    "tag": "[extremely fast]", "estilo": "Fale rapidamente"},
    "riso":       {"ancora": "rir",       "tag": "[laughing]",       "estilo": "Reaja com uma risada"},
    "suspiro":    {"ancora": "suspirar",  "tag": "[sigh]",           "estilo": "Solte um suspiro"},
    "hesitacao":  {"ancora": "hesitar",   "tag": "[uhm]",            "estilo": "Fale com uma hesitação natural"},
    "sarcasmo":   {"ancora": "irônico",   "tag": "[sarcasm]",        "estilo": "Diga a fala a seguir com sarcasmo"},
}
LIMIAR_SIMILARIDADE_EMOCAO = 0.5

STOPWORDS_EMOCAO = {
    "muito", "bastante", "pouco", "tão", "quase", "apenas", "bem", "mal",
    "mais", "menos", "já", "ainda", "assim", "então", "aqui", "ali", "lá",
    "cá", "agora", "hoje", "ontem", "sempre", "nunca", "talvez", "realmente",
}

PRONOMES_FEM  = {"ela", "sua", "dela", "lhe"}
PRONOMES_MASC = {"ele", "seu", "dele", "lhe"}
LABELS_FALANTE = {"PER", "ORG", "MISC"}

LIMITE_CHARS_TTS = 800          # tamanho máx. de texto por chamada ao TTS
MODELO_SPACY = "pt_core_news_lg"
MODELO_TTS = "gemini-2.5-flash-preview-tts"
