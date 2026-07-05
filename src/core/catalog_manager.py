"""
Responsabilidade única: manter o catálogo {personagem -> voz/gênero} e o
"estado de saliência" (quem foi mencionado por último).

Antes (TG1): gênero vinha de inferir_genero(nome), que adivinhava pelo
sufixo da palavra - um dicionário de regras disfarçado.
Agora: quem decide o gênero é sempre o nlp_analyzer (morfologia real do
spaCy). Este arquivo só registra e distribui vozes.
"""
from config import BANCO_VOZES_GEMINI


def criar_catalogo() -> dict:
    return {"Narrador": {"voz": BANCO_VOZES_GEMINI["narrador"], "genero": "narrador"}}


def criar_estado_saliencia() -> dict:
    return {"ultimo_fem": None, "ultimo_masc": None, "ultima_entidade": None}


def registrar_personagem(chave: str, genero: str, catalogo: dict, traco: str = "") -> str:
    """Registra um personagem (nome próprio ou descrição, ex. 'Senhora')
    e atribui a próxima voz livre daquele gênero. Se já existir, reaproveita
    (mas atualiza o traço emocional mais recente, se houver um novo)."""
    if chave in catalogo:
        if traco:
            catalogo[chave]["traco"] = traco
        return chave

    genero_cat = genero if genero in ("feminino", "masculino") else "neutro"
    vozes = BANCO_VOZES_GEMINI[genero_cat]
    n = sum(1 for v in catalogo.values() if v.get("genero") == genero_cat)
    catalogo[chave] = {"voz": vozes[n % len(vozes)], "genero": genero_cat, "traco": traco}
    return chave


def atualizar_saliencia(entidades: list, estado: dict, catalogo: dict):
    """Chamado a cada trecho de narração. Registra as entidades citadas e
    atualiza 'quem foi mencionado por último' - usado depois para resolver
    pronomes e sujeitos elípticos nas falas seguintes."""
    for entidade in entidades:
        registrar_personagem(entidade["chave"], entidade["genero"], catalogo, entidade.get("traco", ""))
        if entidade["genero"] == "feminino":
            estado["ultimo_fem"] = entidade["chave"]
        elif entidade["genero"] == "masculino":
            estado["ultimo_masc"] = entidade["chave"]
        estado["ultima_entidade"] = entidade["chave"]