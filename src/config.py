import os
import re
from dotenv import load_dotenv

load_dotenv()

CHAVE_GEMINI = os.getenv('GEMINI_API_KEY')

BANCO_VOZES_GEMINI = {
    "narrador": "Charon",
    "feminino": ["Aoede", "Leda", "Zephyr"],
    "masculino": ["Fenrir", "Orus", "Puck"],
    "neutro": ["Puck", "Fenrir"],
}

LIMITE_CHARS_TTS = 800

VERBOS_ELOCUCAO_REGEX = re.compile(
    r"\b(disse|respondeu|perguntou|continuou|retrucou|gritou|afirmou|replicou|"
    r"discordou|retomou|chamou|exclamou|murmurou|sussurrou|dirigiu-se|falou|"
    r"começou|acrescentou)\b", re.IGNORECASE
)

VERBOS_ELOCUCAO_LEMMAS = {
    "dizer", "responder", "perguntar", "continuar", "retrucar", "gritar",
    "afirmar", "replicar", "discordar", "retomar", "chamar", "exclamar",
    "murmurar", "sussurrar", "falar", "começar", "acrescentar", "dirigir"
}

_STOPWORDS_EMOCAO = {
    "muito", "bastante", "pouco", "tão", "quase", "apenas", "bem", "mal",
    "mais", "menos", "já", "ainda", "assim", "então", "aqui", "ali", "lá",
    "cá", "agora", "hoje", "ontem", "sempre", "nunca", "talvez", "realmente"
}

_PRONOMES_FEM = {"ela", "sua", "dela", "lhe"}
_PRONOMES_MASC = {"ele", "seu", "dele", "lhe"}
_LABELS_FALANTE = {"PER", "ORG", "MISC"}