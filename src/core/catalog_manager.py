from src.config import BANCO_VOZES_GEMINI


def inferir_genero_simples(nome: str) -> str:
    n = nome.lower()
    if n.endswith(("a", "ã", "inha", "ela", "esa", "isa")):
        return "feminino"
    if n.endswith(("o", "ão", "im", "om", "or", "us")):
        return "masculino"
    return "feminino"


def registrar_personagem(nome: str, genero_inferido: str, catalogo: dict) -> str:
    if nome == "Desconhecido":
        letra = (
            "F"
            if genero_inferido == "feminino"
            else "M"
            if genero_inferido == "masculino"
            else "N"
        )
        candidatos = sorted(
            [k for k in catalogo if k.startswith(f"Personagem_{letra}")], reverse=True
        )
        if candidatos:
            return candidatos[0]

        n = sum(1 for k in catalogo if k.startswith(f"Personagem_{letra}"))
        nome_anonimo = f"Personagem_{letra}_{n + 1}"
        gen_cat = "neutro" if genero_inferido == "neutro" else genero_inferido
        vozes = BANCO_VOZES_GEMINI[gen_cat]
        idx = sum(1 for v in catalogo.values() if v.get("genero") == gen_cat)
        catalogo[nome_anonimo] = {"voz": vozes[idx % len(vozes)], "genero": gen_cat}
        return nome_anonimo

    if nome in catalogo:
        return nome

    genero = inferir_genero_simples(nome)
    vozes = BANCO_VOZES_GEMINI[genero]
    n = sum(1 for v in catalogo.values() if v.get("genero") == genero)
    catalogo[nome] = {"voz": vozes[n % len(vozes)], "genero": genero}
    return nome


def atualizar_coref(nome: str, catalogo: dict, estado_coref: dict):
    gen = catalogo.get(nome, {}).get("genero", "")
    if gen == "feminino":
        estado_coref["ultimo_fem"] = nome
    elif gen == "masculino":
        estado_coref["ultimo_masc"] = nome
