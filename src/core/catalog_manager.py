"""
Responsabilidade única: manter o catálogo {personagem -> voz/gênero} e o
"estado de saliência" (quem foi mencionado por último).

Quem decide o gênero é sempre o nlp_analyzer (morfologia real do spaCy).
Este arquivo só registra e distribui vozes.
"""
from config import BANCO_VOZES_GEMINI, VOZES_POR_IDADE, GRUPO_IDADE, SUBSTANTIVOS_GENERICOS


def criar_catalogo() -> dict:
    return {"Narrador": {"voz": BANCO_VOZES_GEMINI["narrador"], "genero": "narrador"}}


def criar_estado_saliencia() -> dict:
    return {"ultimo_fem": None, "ultimo_masc": None, "ultima_entidade": None}


def _escolher_voz(genero_cat: str, idade: str | None, catalogo: dict) -> str:
    """Ordem de preferência: vozes da faixa etária explícita (se houver), vozes do adulto do
    gênero e, por último, as vozes das outras faixas do mesmo gênero. Escolhe a primeira que
    nenhum outro personagem está usando; só se todas já foram usadas, repete em rodízio."""
    da_faixa = VOZES_POR_IDADE.get((genero_cat, idade), [])
    outras = [v for (g, _), lista in VOZES_POR_IDADE.items() if g == genero_cat for v in lista]
    vozes = list(dict.fromkeys(da_faixa + BANCO_VOZES_GEMINI[genero_cat] + outras))
    usadas = {v["voz"] for v in catalogo.values()}
    n = sum(1 for v in catalogo.values() if v.get("genero") == genero_cat)
    return next((v for v in vozes if v not in usadas), vozes[n % len(vozes)])


def resolver_alias(entidade: dict, catalogo: dict) -> str:
    """Palavras diferentes costumam designar a mesma pessoa ("o velho", "o ancião", "o
    idoso"). Se a descrição traz uma faixa etária explícita e já existe um personagem
    descrito do mesmo grupo de idade e de gênero compatível, é a mesma pessoa: devolve o
    nome dele (e a voz não muda). O mesmo vale para "o homem" / "a mulher", que retomam
    um adulto já descrito. Nomes próprios e demais descrições valem por si."""
    grupo = GRUPO_IDADE.get(entidade["idade"])
    generico = entidade["chave"].lower() in SUBSTANTIVOS_GENERICOS
    if entidade["origem"] != "descricao" or not (grupo or generico):
        return entidade["chave"]
    for chave, info in reversed(list(catalogo.items())):
        compativel = info["genero"] == entidade["genero"] or "desconhecido" in (info["genero"], entidade["genero"])
        if info.get("origem") != "descricao" or not compativel:
            continue
        grupo_info = GRUPO_IDADE.get(info.get("idade"))
        if (grupo and grupo_info == grupo) or (not grupo and grupo_info != "jovens"):
            return chave
    return entidade["chave"]


def registrar_personagem(chave: str, genero: str, catalogo: dict, traco: str = "", idade: str | None = None,
                         origem: str = "nome"):
    """Cria o personagem e escolhe a voz dele NESSE momento. Se ele já existe, só
    atualiza traço e idade: uma idade que aparece numa menção posterior muda a
    instrução enviada ao TTS, mas não troca a voz já escolhida."""
    if chave in catalogo:
        if traco:
            catalogo[chave]["traco"] = traco
        if idade:
            catalogo[chave]["idade"] = idade
        return

    genero_cat = genero if genero in ("feminino", "masculino") else "desconhecido"
    catalogo[chave] = {"voz": _escolher_voz(genero_cat, idade, catalogo), "genero": genero_cat,
                       "traco": traco, "idade": idade, "origem": origem}


def atualizar_saliencia(entidades: list, estado: dict, catalogo: dict):
    """Chamado a cada trecho de narração. Registra as entidades citadas e
    atualiza 'quem foi mencionado por último' - usado depois para resolver
    pronomes e sujeitos elípticos nas falas seguintes."""
    for e in entidades:
        chave = resolver_alias(e, catalogo)
        registrar_personagem(chave, e["genero"], catalogo, e["traco"], e["idade"], e["origem"])

        if e["genero"] == "feminino":
            estado["ultimo_fem"] = chave
        elif e["genero"] == "masculino":
            estado["ultimo_masc"] = chave
        estado["ultima_entidade"] = chave